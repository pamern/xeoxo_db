from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd
from PIL import Image, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection_db import (
    get_bucket_name,
    get_overwrite_flag,
    get_supabase_client,
)
from src.utils.file_path import MATERIAL_FILE
from src.utils.load_connection import (
    add_loader_connection_args,
    build_connection_kwargs,
    describe_connection,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


MATERIAL_MEDIA_DIR = PROJECT_ROOT / "data" / "media" / "material"
DEFAULT_BUCKET_NAME = "product-media"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "data" / "master" / "material_media.csv"
BATCH_SIZE = 500


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def slugify(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None

    normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    slug = re.sub(r"[^a-z0-9]+", "-", without_accents).strip("-")
    return slug or None


def convert_image_to_webp(image_path: Path) -> tuple[bytes, str, int]:
    try:
        image = Image.open(image_path)
        image.load()

        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

        output = BytesIO()
        image.save(output, format="WEBP", quality=90, method=6)
        webp_bytes = output.getvalue()
        return webp_bytes, "image/webp", len(webp_bytes)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Failed to convert image to webp: {image_path}") from exc


def storage_object_exists(bucket_api, storage_key: str) -> bool:
    folder = str(Path(storage_key).parent).replace("\\", "/")
    filename = Path(storage_key).name
    objects = bucket_api.list(folder, {"search": filename})
    return any(
        isinstance(item, dict) and item.get("name") == filename
        for item in objects or []
    )


def upload_bytes_to_supabase(
    bucket_api,
    storage_key: str,
    content: bytes,
    mime_type: str,
    overwrite: bool,
) -> None:
    bucket_api.upload(
        path=storage_key,
        file=content,
        file_options={
            "content-type": mime_type,
            "upsert": str(overwrite).lower(),
        },
    )


def get_public_url(bucket_api, storage_key: str) -> str | None:
    result = bucket_api.get_public_url(storage_key)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("publicURL") or result.get("publicUrl")
    return getattr(result, "public_url", None)


def read_master_material_media(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"material_name", "description"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    if "media_filename" not in df.columns:
        df["media_filename"] = None

    working_df = df.copy()
    working_df["material_name"] = working_df["material_name"].map(normalize_text)
    working_df["description"] = working_df["description"].map(normalize_text)
    working_df["media_filename"] = working_df["media_filename"].map(normalize_text)
    working_df["slug"] = working_df["material_name"].map(slugify)

    working_df = working_df.dropna(subset=["material_name", "slug"])
    working_df = (
        working_df.sort_values(by=["material_name", "slug"], kind="stable")
        .drop_duplicates(subset=["material_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        ["material_name", "slug", "description", "media_filename"]
    ]


def resolve_image_path(row: dict) -> Path:
    media_filename = normalize_text(row.get("media_filename"))
    if media_filename:
        candidate = MATERIAL_MEDIA_DIR / media_filename
        if candidate.exists():
            return candidate

    slug = normalize_text(row.get("slug"))
    if slug:
        for extension in (".webp", ".png", ".jpg", ".jpeg"):
            candidate = MATERIAL_MEDIA_DIR / f"{slug}{extension}"
            if candidate.exists():
                return candidate

    raise FileNotFoundError(
        "Missing material media file for "
        f"{row.get('material_name')!r}. Checked media_filename and slug fallback."
    )


def build_media_records(
    bucket_name: str,
    overwrite: bool,
) -> tuple[list[dict], pd.DataFrame]:
    client = get_supabase_client()
    bucket_api = client.storage.from_(bucket_name)
    materials_df = read_master_material_media(MATERIAL_FILE)
    records: list[dict] = []

    for row in materials_df.to_dict(orient="records"):
        image_path = resolve_image_path(row)
        upload_bytes, upload_mime_type, upload_file_size = convert_image_to_webp(image_path)
        storage_key = f"materials/{row['slug']}/swatch.webp"

        if not overwrite and storage_object_exists(bucket_api, storage_key):
            public_url = get_public_url(bucket_api, storage_key)
        else:
            upload_bytes_to_supabase(
                bucket_api=bucket_api,
                storage_key=storage_key,
                content=upload_bytes,
                mime_type=upload_mime_type,
                overwrite=overwrite,
            )
            public_url = get_public_url(bucket_api, storage_key)

        records.append(
            {
                "material_name": row["material_name"],
                "material_slug": row["slug"],
                "storage_key": storage_key,
                "media_url": public_url,
                "alt_text": f"{row['material_name']} - swatch chất liệu",
                "media_type": "IMAGE",
                "mime_type": upload_mime_type,
                "file_size": upload_file_size,
                "bucket_name": bucket_name,
            }
        )

    return records, materials_df


def fetch_existing_media(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            media_id,
            storage_key,
            alt_text,
            media_type,
            mime_type,
            file_size,
            bucket_name
        FROM catalog.media
    """
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    return {
        normalize_text(row["storage_key"]): row
        for row in rows
        if normalize_text(row.get("storage_key"))
    }


def fetch_existing_materials(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            material_id,
            material_name,
            media_id
        FROM catalog.material
    """
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    return {
        normalize_text(row["material_name"]): row
        for row in rows
        if normalize_text(row.get("material_name"))
    }


def build_media_update_payload(record: dict, existing: dict) -> dict | None:
    changed: dict = {}
    for key in ["alt_text", "media_type", "mime_type", "file_size", "bucket_name"]:
        existing_value = existing.get(key)
        incoming_value = record.get(key)
        if existing_value != incoming_value:
            changed[key] = incoming_value
    return changed or None


def insert_media_batch(connection: psycopg.Connection, records: list[dict]) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.media (
            storage_key,
            alt_text,
            media_type,
            mime_type,
            file_size,
            bucket_name
        )
        VALUES (
            %(storage_key)s,
            %(alt_text)s,
            %(media_type)s,
            %(mime_type)s,
            %(file_size)s,
            %(bucket_name)s
        )
    """
    with connection.cursor() as cursor:
        cursor.executemany(query, records)
    return len(records)


def update_media(connection: psycopg.Connection, media_id: int, payload: dict) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in payload)
    query = f"""
        UPDATE catalog.media
        SET {assignments}, updated_at = NOW()
        WHERE media_id = %(media_id)s
    """
    params = dict(payload)
    params["media_id"] = media_id
    with connection.cursor() as cursor:
        cursor.execute(query, params)


def update_material_media_id(
    connection: psycopg.Connection,
    material_id: int,
    media_id: int,
) -> None:
    query = """
        UPDATE catalog.material
        SET media_id = %(media_id)s,
            updated_at = NOW()
        WHERE material_id = %(material_id)s
          AND media_id IS DISTINCT FROM %(media_id)s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, {"material_id": material_id, "media_id": media_id})


def sync_material_media_to_db(
    records: list[dict],
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        existing_media = fetch_existing_media(connection)
        existing_materials = fetch_existing_materials(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in records:
            storage_key = record["storage_key"]
            existing = existing_media.get(storage_key)
            if existing is None:
                inserts.append(record)
            else:
                payload = build_media_update_payload(record, existing)
                if payload is not None:
                    updates.append((existing["media_id"], payload))

        inserted_count = 0
        updated_count = 0

        for batch in [inserts[i : i + BATCH_SIZE] for i in range(0, len(inserts), BATCH_SIZE)]:
            inserted_count += insert_media_batch(connection, batch)

        for media_id, payload in updates:
            update_media(connection, media_id, payload)
            updated_count += 1

        refreshed_media = fetch_existing_media(connection)
        for record in records:
            material = existing_materials.get(record["material_name"])
            if material is None:
                raise ValueError(
                    "Material must exist before loading its media: "
                    f"{record['material_name']}"
                )
            media = refreshed_media.get(record["storage_key"])
            if media is None:
                raise ValueError(
                    f"Media row not found after sync for storage_key={record['storage_key']}"
                )
            update_material_media_id(
                connection=connection,
                material_id=int(material["material_id"]),
                media_id=int(media["media_id"]),
            )

        connection.commit()

    skipped_count = len(records) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def save_report(records: list[dict], output_file: Path) -> pd.DataFrame:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload material images to Supabase Storage as WEBP, sync catalog.media, "
            "and attach media_id to catalog.material."
        )
    )
    add_loader_connection_args(parser)
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_OUTPUT_FILE),
        help=f"CSV report path. Default: {DEFAULT_OUTPUT_FILE}.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    bucket_name = get_bucket_name(DEFAULT_BUCKET_NAME)
    overwrite = get_overwrite_flag(False)

    records, materials_df = build_media_records(
        bucket_name=bucket_name,
        overwrite=overwrite,
    )
    inserted_count, updated_count, skipped_count = sync_material_media_to_db(
        records=records,
        connection_kwargs=connection_kwargs,
    )
    report_df = save_report(records, Path(args.output_file))

    print(f"Target database: {describe_connection(connection_kwargs)}")
    print(f"Bucket: {bucket_name}")
    print(f"Overwrite storage objects: {overwrite}")
    print(f"Materials processed: {len(materials_df)}")
    print(f"Media inserted: {inserted_count}")
    print(f"Media updated: {updated_count}")
    print(f"Media unchanged: {skipped_count}")
    print(f"Report file: {args.output_file}")

    if not report_df.empty:
        print("\nPreview:")
        print(report_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
