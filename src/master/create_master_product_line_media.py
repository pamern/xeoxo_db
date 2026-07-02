from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


INPUT_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "product_line_media.csv"

REQUIRED_COLUMNS = {
    "collection_name",
    "product_name",
    "slug",
    "thumbnail_url",
    "gallery_urls",
}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none", "nan"}:
        return None

    return text


def parse_gallery_urls(value: object) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    urls: list[str] = []
    if isinstance(parsed, list):
        urls = [normalize_text(item) for item in parsed]
    elif isinstance(parsed, str):
        urls = [parsed]
    else:
        urls = re.split(r"\s*,\s*|\s*\|\s*", text)

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
    normalized_thumbnail = normalize_text(thumbnail_url)

    for url in gallery_urls:
        normalized_url = normalize_text(url)
        if not normalized_url:
            continue

        if normalized_thumbnail and normalized_url == normalized_thumbnail:
            continue

        if normalized_url not in deduped_urls:
            deduped_urls.append(normalized_url)

    return deduped_urls


def read_staging_product_lines(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    for column in REQUIRED_COLUMNS:
        working_df[column] = working_df[column].map(normalize_text)

    working_df = working_df.dropna(subset=["collection_name", "product_name", "slug"])
    working_df = (
        working_df.sort_values(
            by=["collection_name", "product_name", "slug"],
            kind="stable",
        )
        .drop_duplicates(subset=["collection_name", "product_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df


def fetch_existing_product_lines(
    connection_kwargs: dict[str, str | int],
) -> dict[tuple[str, str], dict]:
    query = """
        SELECT
            pl.product_line_id,
            pl.line_name,
            c.collection_name
        FROM catalog.product_line pl
        INNER JOIN catalog.collection c
            ON c.collection_id = pl.collection_id
    """

    with psycopg.connect(**connection_kwargs) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    product_lines_by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        collection_name = normalize_text(row.get("collection_name"))
        line_name = normalize_text(row.get("line_name"))
        product_line_id = row.get("product_line_id")
        if not collection_name or not line_name or product_line_id is None:
            continue

        key = (collection_name, line_name)
        if key not in product_lines_by_key:
            product_lines_by_key[key] = row

    return product_lines_by_key


def fetch_existing_media(
    connection_kwargs: dict[str, str | int],
) -> dict[str, dict]:
    query = """
        SELECT
            media_id,
            storage_key
        FROM catalog.media
    """

    with psycopg.connect(**connection_kwargs) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    media_by_storage_key: dict[str, dict] = {}
    for row in rows:
        storage_key = normalize_text(row.get("storage_key"))
        media_id = row.get("media_id")
        if not storage_key or media_id is None:
            continue

        if storage_key not in media_by_storage_key:
            media_by_storage_key[storage_key] = row

    return media_by_storage_key


def build_main_storage_key(slug: str) -> str:
    return f"product-lines/{slug}/main.webp"


def build_gallery_storage_key(slug: str, index: int) -> str:
    return f"product-lines/{slug}/gallery-{index:02d}.webp"


def build_master_product_line_media(
    staging_df: pd.DataFrame,
    product_lines_by_key: dict[tuple[str, str], dict],
    media_by_storage_key: dict[str, dict],
) -> pd.DataFrame:
    rows: list[dict] = []
    unresolved_product_lines: list[tuple[str, str]] = []
    unresolved_media: list[tuple[str, str, str]] = []

    for record in staging_df.to_dict(orient="records"):
        collection_name = record["collection_name"]
        product_name = record["product_name"]
        slug = record["slug"]

        product_line = product_lines_by_key.get((collection_name, product_name))
        if product_line is None:
            unresolved_product_lines.append((collection_name, product_name))
            continue

        product_line_id = int(product_line["product_line_id"])

        main_storage_key = build_main_storage_key(slug)
        main_media = media_by_storage_key.get(main_storage_key)
        if main_media is None:
            unresolved_media.append((product_name, "Main", main_storage_key))
        else:
            rows.append(
                {
                    "product_line_id": product_line_id,
                    "media_id": int(main_media["media_id"]),
                    "media_role": "Main",
                    "display_order": 1,
                }
            )

        gallery_urls = dedupe_gallery_urls(
            thumbnail_url=record.get("thumbnail_url"),
            gallery_urls=parse_gallery_urls(record.get("gallery_urls")),
        )
        for index, _ in enumerate(gallery_urls, start=1):
            gallery_storage_key = build_gallery_storage_key(slug, index)
            gallery_media = media_by_storage_key.get(gallery_storage_key)
            if gallery_media is None:
                unresolved_media.append((product_name, "Gallery", gallery_storage_key))
                continue

            rows.append(
                {
                    "product_line_id": product_line_id,
                    "media_id": int(gallery_media["media_id"]),
                    "media_role": "Gallery",
                    "display_order": index,
                }
            )

    if unresolved_product_lines:
        raise ValueError(
            "Unable to resolve product_line_id for product_line_media: "
            f"{sorted(set(unresolved_product_lines))}"
        )

    if unresolved_media:
        raise ValueError(
            "Unable to resolve media_id for product_line_media: "
            f"{sorted(unresolved_media)}"
        )

    master_df = pd.DataFrame(rows)
    if master_df.empty:
        return pd.DataFrame(
            columns=["product_line_id", "media_id", "media_role", "display_order"]
        )

    master_df = (
        master_df.sort_values(
            by=["product_line_id", "media_role", "display_order", "media_id"],
            kind="stable",
        )
        .drop_duplicates(subset=["product_line_id", "media_id"], keep="first")
        .reset_index(drop=True)
    )

    return master_df


def save_master_product_line_media(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print(f"Created file: {output_file}")
    print(f"Total master product_line_media rows: {len(df)}")

    if not df.empty:
        print("\nPreview:")
        print(df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create data/master/product_line_media.csv from staging product lines "
            "and existing catalog.product_line/catalog.media records."
        ),
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    connection_target = describe_connection(connection_kwargs)
    staging_df = read_staging_product_lines(INPUT_FILE)
    product_lines_by_key = fetch_existing_product_lines(connection_kwargs)
    media_by_storage_key = fetch_existing_media(connection_kwargs)

    master_df = build_master_product_line_media(
        staging_df=staging_df,
        product_lines_by_key=product_lines_by_key,
        media_by_storage_key=media_by_storage_key,
    )
    save_master_product_line_media(master_df, OUTPUT_FILE)
    print(f"Target database: {connection_target}")
    print_summary(master_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()
