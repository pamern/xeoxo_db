import json
import logging
import mimetypes
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from PIL import Image, UnidentifiedImageError
from supabase import Client

from src.utils.connection_db import (
    get_bucket_name,
    get_overwrite_flag,
    get_supabase_client,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "media.csv"

DEFAULT_BUCKET_NAME = "product-media"
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_RETRIES = 2

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def slugify(value: str | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None

    normalized = unicodedata.normalize("NFD", text.lower())
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"[\s_]+", "-", normalized)
    slug = normalized.strip("-")
    return slug or None


def parse_gallery_urls(value: object) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []

    urls: list[str] = []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            urls = [normalize_text(item) for item in parsed]
        elif isinstance(parsed, str):
            urls = [parsed]
    except json.JSONDecodeError:
        if "|" in text:
            urls = text.split("|")
        else:
            urls = re.split(r"\s*,\s*", text)

    cleaned_urls: list[str] = []
    for url in urls:
        normalized = normalize_text(url)
        if normalized and normalized not in cleaned_urls:
            cleaned_urls.append(normalized)

    return cleaned_urls


def dedupe_gallery_urls(
    thumbnail_url: str | None,
    gallery_urls: list[str],
) -> list[str]:
    deduped_urls: list[str] = []
    seen_urls: set[str] = set()

    if thumbnail_url:
        seen_urls.add(thumbnail_url)

    for url in gallery_urls:
        normalized = normalize_text(url)
        if not normalized or normalized in seen_urls:
            continue

        seen_urls.add(normalized)
        deduped_urls.append(normalized)

    return deduped_urls


def get_extension_from_mime(mime_type: str | None, source_url: str | None) -> str:
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type.split(";")[0].strip())
        if guessed:
            return ".jpg" if guessed == ".jpe" else guessed

    if source_url:
        path = urlparse(source_url).path.lower()
        if path.endswith(".jpeg"):
            return ".jpg"
        for ext in [".jpg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"]:
            if path.endswith(ext):
                return ext

    return ".bin"


def convert_image_to_webp(image_bytes: bytes) -> tuple[bytes, str, int] | None:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()

        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

        output = BytesIO()
        image.save(output, format="WEBP", quality=90, method=6)
        webp_bytes = output.getvalue()
        return webp_bytes, "image/webp", len(webp_bytes)
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("Failed to convert image to webp: %s", exc)
        return None


def download_image_to_bytes(
    url: str,
    timeout: int = DOWNLOAD_TIMEOUT,
    retries: int = DOWNLOAD_RETRIES,
) -> tuple[bytes, str | None, int] | None:
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            content = response.content
            mime_type = normalize_text(response.headers.get("Content-Type"))
            return content, mime_type, len(content)
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "Download failed (%s/%s): %s",
                attempt + 1,
                retries + 1,
                url,
            )

    logger.warning("Skip broken image: %s | %s", url, last_error)
    return None


def get_public_url(client: Client, bucket_name: str, storage_key: str) -> str | None:
    result = client.storage.from_(bucket_name).get_public_url(storage_key)

    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        return result.get("publicURL") or result.get("publicUrl")

    return getattr(result, "public_url", None)


def storage_object_exists(
    client: Client,
    bucket_name: str,
    storage_key: str,
) -> bool:
    folder = str(Path(storage_key).parent).replace("\\", "/")
    filename = Path(storage_key).name

    try:
        objects = client.storage.from_(bucket_name).list(
            folder,
            {"search": filename},
        )
    except Exception as exc:
        logger.warning("Could not check existing object %s: %s", storage_key, exc)
        return False

    if not isinstance(objects, list):
        return False

    return any(
        isinstance(item, dict) and item.get("name") == filename
        for item in objects
    )


def upload_bytes_to_supabase(
    client: Client,
    bucket_name: str,
    storage_key: str,
    content: bytes,
    mime_type: str,
    overwrite: bool,
) -> bool:
    try:
        client.storage.from_(bucket_name).upload(
            path=storage_key,
            file=content,
            file_options={
                "content-type": mime_type,
                "upsert": str(overwrite).lower(),
            },
        )
        return True
    except Exception as exc:
        logger.warning("Upload failed for %s: %s", storage_key, exc)
        return False


def read_input_data(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)

    required_columns = {
        "product_name",
        "collection_name",
        "collection_slug",
        "thumbnail_url",
        "gallery_urls",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    if "slug" not in df.columns and "product_slug" not in df.columns:
        raise ValueError(
            f"Missing slug column in {input_file}. Expected 'slug' or 'product_slug'."
        )

    if "slug" not in df.columns and "product_slug" in df.columns:
        df["slug"] = df["product_slug"]

    return df


def build_collection_cover_candidates(df: pd.DataFrame) -> list[dict]:
    candidates: list[dict] = []
    seen_storage_keys: set[str] = set()

    for _, row in df.iterrows():
        collection_slug = normalize_text(row.get("collection_slug")) or slugify(
            row.get("collection_name")
        )
        collection_name = normalize_text(row.get("collection_name"))
        thumbnail_url = normalize_text(row.get("thumbnail_url"))
        gallery_urls = parse_gallery_urls(row.get("gallery_urls"))
        source_url = thumbnail_url or (gallery_urls[0] if gallery_urls else None)

        if not collection_slug or not collection_name or not source_url:
            continue

        storage_stub = f"collections/{collection_slug}/cover"
        if storage_stub in seen_storage_keys:
            continue

        seen_storage_keys.add(storage_stub)
        candidates.append(
            {
                "kind": "cover",
                "source_url": source_url,
                "storage_stub": storage_stub,
                "alt_text": f"{collection_name} - ảnh bìa bộ sưu tập",
            }
        )

    return candidates


def build_media_candidates(df: pd.DataFrame) -> list[dict]:
    candidates: list[dict] = []

    for _, row in df.iterrows():
        product_slug = normalize_text(row.get("slug")) or slugify(
            row.get("product_name")
        )
        product_name = normalize_text(row.get("product_name"))
        thumbnail_url = normalize_text(row.get("thumbnail_url"))

        if product_slug and product_name and thumbnail_url:
            candidates.append(
                {
                    "kind": "main",
                    "source_url": thumbnail_url,
                    "storage_stub": f"product-lines/{product_slug}/main",
                    "alt_text": f"{product_name} - ảnh chính",
                }
            )

        if not product_slug or not product_name:
            continue

        gallery_urls = dedupe_gallery_urls(
            thumbnail_url=thumbnail_url,
            gallery_urls=parse_gallery_urls(row.get("gallery_urls")),
        )
        for index, url in enumerate(gallery_urls, start=1):
            candidates.append(
                {
                    "kind": "gallery",
                    "source_url": url,
                    "storage_stub": (
                        f"product-lines/{product_slug}/gallery-{index:02d}"
                    ),
                    "alt_text": f"{product_name} - ảnh {index}",
                }
            )

    candidates.extend(build_collection_cover_candidates(df))
    return candidates


def build_media_records(
    client: Client,
    df: pd.DataFrame,
    bucket_name: str,
    overwrite: bool,
) -> tuple[list[dict], int, int, int]:
    candidates = build_media_candidates(df)
    records: list[dict] = []
    success_count = 0
    skip_count = 0
    error_count = 0
    seen_storage_keys: set[str] = set()

    for candidate in candidates:
        source_url = candidate["source_url"]
        storage_stub = candidate["storage_stub"]

        download_result = download_image_to_bytes(source_url)
        if not download_result:
            error_count += 1
            continue

        content, mime_type, file_size = download_result
        fallback_mime = mimetypes.guess_type(source_url)[0]
        final_mime = mime_type or fallback_mime or "application/octet-stream"
        converted = convert_image_to_webp(content)

        if not converted:
            error_count += 1
            continue

        upload_bytes, upload_mime_type, upload_file_size = converted
        storage_key = f"{storage_stub}.webp"

        if storage_key in seen_storage_keys:
            skip_count += 1
            logger.info("Skip duplicate storage_key in run: %s", storage_key)
            continue

        if not overwrite and storage_object_exists(client, bucket_name, storage_key):
            skip_count += 1
            seen_storage_keys.add(storage_key)
            logger.info("Skip existing storage_key: %s", storage_key)
            continue

        uploaded = upload_bytes_to_supabase(
            client=client,
            bucket_name=bucket_name,
            storage_key=storage_key,
            content=upload_bytes,
            mime_type=upload_mime_type,
            overwrite=overwrite,
        )

        if not uploaded:
            error_count += 1
            continue

        seen_storage_keys.add(storage_key)
        public_url = get_public_url(client, bucket_name, storage_key)
        records.append(
            {
                "media_url": public_url,
                "storage_key": storage_key,
                "alt_text": candidate["alt_text"],
                "media_type": "IMAGE",
                "mime_type": upload_mime_type,
                "file_size": upload_file_size,
                "bucket_name": bucket_name,
            }
        )
        success_count += 1
        logger.info("Uploaded: %s", storage_key)

    return records, success_count, skip_count, error_count


def save_media_csv(records: list[dict], output_file: Path) -> pd.DataFrame:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        records,
        columns=[
            "media_url",
            "storage_key",
            "alt_text",
            "media_type",
            "mime_type",
            "file_size",
            "bucket_name",
        ],
    )
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    return df


def create_supabase_client_from_env() -> tuple[Client, str, bool]:
    return (
        get_supabase_client(),
        get_bucket_name(DEFAULT_BUCKET_NAME),
        get_overwrite_flag(False),
    )


def main() -> None:
    logger.info("Reading input file: %s", INPUT_FILE)
    df = read_input_data(INPUT_FILE)

    logger.info("Creating Supabase client")
    client, bucket_name, overwrite = create_supabase_client_from_env()

    logger.info(
        "Uploading media to bucket '%s' | overwrite=%s",
        bucket_name,
        overwrite,
    )
    records, success_count, skip_count, error_count = build_media_records(
        client=client,
        df=df,
        bucket_name=bucket_name,
        overwrite=overwrite,
    )

    media_df = save_media_csv(records, OUTPUT_FILE)

    print(f"Total images uploaded successfully: {success_count}")
    print(f"Total images skipped: {skip_count}")
    print(f"Total images failed: {error_count}")
    print(f"media.csv path: {OUTPUT_FILE}")

    if not media_df.empty:
        print("\nPreview:")
        print(media_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
