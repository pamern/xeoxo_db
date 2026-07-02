from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import json
import sys
from urllib.parse import urlparse

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
    from psycopg.types.json import Jsonb
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "collections.csv"
MEDIA_INPUT_FILE = PROJECT_ROOT / "data" / "master" / "media.csv"
BATCH_SIZE = 500
DEFAULT_COLLECTION_MEDIA_SUFFIX = "cover.webp"


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def normalize_season(value: object) -> str:
    season = normalize_text(value)
    if not season:
        raise ValueError("season must not be null")

    normalized = season.strip().lower()
    allowed = {
        "spring": "SPRING",
        "summer": "SUMMER",
        "fall": "AUTUMN",
        "autumn": "AUTUMN",
        "winter": "WINTER",
    }
    if normalized not in allowed:
        raise ValueError(
            f"Invalid season: {season!r}. Expected one of {sorted(allowed.values())}"
        )

    return allowed[normalized]


def normalize_status(value: object) -> str:
    status = normalize_text(value)
    if not status:
        raise ValueError("status must not be null")

    return status.upper()


def normalize_launch_date(value: object) -> date | None:
    text = normalize_text(value)
    if not text:
        return None

    timestamp = pd.to_datetime(text, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError(f"Invalid launch_date: {value!r}")

    return timestamp.date()


def normalize_content_json(value: object) -> dict | list | None:
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (dict, list)):
        return value

    text = normalize_text(value)
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid content_json: {value!r}") from exc


def build_media_storage_key_from_slug(slug: str) -> str:
    return f"collections/{slug}/{DEFAULT_COLLECTION_MEDIA_SUFFIX}"


def extract_storage_key_from_public_url(media_url: str) -> str | None:
    parsed = urlparse(media_url)
    parts = [part for part in parsed.path.split("/") if part]

    try:
        public_index = parts.index("public")
    except ValueError:
        return None

    if len(parts) <= public_index + 2:
        return None

    storage_key_parts = parts[public_index + 2 :]
    return "/".join(storage_key_parts) or None


def read_master_media(input_file: Path) -> dict[str, dict[str, str]]:
    if not input_file.exists():
        raise FileNotFoundError(f"Media master file not found: {input_file}")

    media_df = pd.read_csv(input_file)
    required_columns = {"storage_key"}
    missing_columns = required_columns - set(media_df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    if "media_url" not in media_df.columns:
        media_df["media_url"] = None

    media_by_storage_key: dict[str, dict[str, str]] = {}
    for record in media_df.to_dict(orient="records"):
        storage_key = normalize_text(record.get("storage_key"))
        media_url = normalize_text(record.get("media_url"))
        if not storage_key or storage_key in media_by_storage_key:
            continue

        media_by_storage_key[storage_key] = {
            "storage_key": storage_key,
            "media_url": media_url,
        }

    return media_by_storage_key


def read_master_collections(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "collection_name",
        "slug",
        "description",
        "cultural_story",
        "season",
        "launch_date",
        "status",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["collection_name"] = working_df["collection_name"].map(normalize_text)
    working_df["slug"] = working_df["slug"].map(normalize_text)
    working_df["description"] = working_df["description"].map(normalize_text)
    working_df["cultural_story"] = working_df["cultural_story"].map(normalize_text)
    working_df["media_url"] = (
        working_df["media_url"].map(normalize_text)
        if "media_url" in working_df.columns
        else None
    )
    working_df["content_json"] = (
        working_df["content_json"].map(normalize_content_json)
        if "content_json" in working_df.columns
        else None
    )
    working_df["season"] = working_df["season"].map(normalize_season)
    working_df["launch_date"] = working_df["launch_date"].map(normalize_launch_date)
    working_df["status"] = working_df["status"].map(normalize_status)

    working_df = working_df.dropna(
        subset=[
            "collection_name",
            "slug",
            "season",
            "status",
        ]
    )
    working_df = (
        working_df.sort_values(by=["collection_name", "slug"], kind="stable")
        .drop_duplicates(subset=["collection_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "collection_name",
            "slug",
            "description",
            "media_url",
            "content_json",
            "season",
            "launch_date",
            "status",
        ]
    ]


def resolve_media_storage_key(
    row: dict,
    master_media_by_storage_key: dict[str, dict[str, str]],
) -> str | None:
    media_url = normalize_text(row.get("media_url"))
    if media_url:
        public_url_storage_key = extract_storage_key_from_public_url(media_url)
        if public_url_storage_key and public_url_storage_key in master_media_by_storage_key:
            return public_url_storage_key

    slug = normalize_text(row.get("slug"))
    if slug:
        derived_storage_key = build_media_storage_key_from_slug(slug)
        if derived_storage_key in master_media_by_storage_key:
            return derived_storage_key

    return None


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_media(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            media_id,
            storage_key
        FROM catalog.media
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_storage_key: dict[str, dict] = {}
    for row in rows:
        storage_key = normalize_text(row.get("storage_key"))
        if storage_key and storage_key not in existing_by_storage_key:
            existing_by_storage_key[storage_key] = row

    return existing_by_storage_key


def fetch_existing_collections(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            collection_id,
            collection_name,
            description,
            media_id,
            content_json,
            season,
            launch_date,
            status
        FROM catalog.collection
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        collection_name = normalize_text(row.get("collection_name"))
        if collection_name and collection_name not in existing_by_name:
            existing_by_name[collection_name] = row

    return existing_by_name


def build_collection_payload(
    row: dict,
    media_id: int | None,
) -> dict:
    return {
        "collection_name": normalize_text(row["collection_name"]),
        "description": normalize_text(row["description"]),
        "media_id": media_id,
        "content_json": Jsonb(row["content_json"]) if row["content_json"] is not None else None,
        "season": normalize_season(row["season"]),
        "launch_date": normalize_launch_date(row["launch_date"]),
        "status": normalize_status(row["status"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"media_id", "launch_date"}:
            existing_value = existing.get(key)
            incoming_value = value
        elif key == "content_json":
            existing_json = existing.get(key)
            existing_value = json.dumps(existing_json, ensure_ascii=False, sort_keys=True) if existing_json is not None else None
            incoming_value = (
                json.dumps(value.obj, ensure_ascii=False, sort_keys=True)
                if value is not None
                else None
            )
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_collection_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.collection (
            collection_name,
            description,
            media_id,
            content_json,
            season,
            launch_date,
            status
        )
        VALUES (
            %(collection_name)s,
            %(description)s,
            %(media_id)s,
            %(content_json)s,
            %(season)s,
            %(launch_date)s,
            %(status)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_collection(
    connection: psycopg.Connection,
    collection_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.collection
        SET {assignments}, updated_at = NOW()
        WHERE collection_id = %(collection_id)s
    """

    params = dict(update_payload)
    params["collection_id"] = collection_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_collections(
    collections_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    master_media_by_storage_key = read_master_media(MEDIA_INPUT_FILE)

    with psycopg.connect(**connection_kwargs) as connection:
        existing_media_by_storage_key = fetch_existing_media(connection)
        existing_collections_by_name = fetch_existing_collections(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_media: list[tuple[str, str | None, str | None]] = []

        for record in collections_df.to_dict(orient="records"):
            collection_name = record["collection_name"]
            storage_key = resolve_media_storage_key(record, master_media_by_storage_key)
            media_row = existing_media_by_storage_key.get(storage_key) if storage_key else None

            if storage_key and media_row is None:
                unresolved_media.append(
                    (
                        collection_name,
                        normalize_text(record.get("slug")),
                        storage_key,
                    )
                )
                continue

            if normalize_text(record.get("media_url")) and storage_key is None:
                unresolved_media.append(
                    (
                        collection_name,
                        normalize_text(record.get("slug")),
                        normalize_text(record.get("media_url")),
                    )
                )
                continue

            payload = build_collection_payload(
                row=record,
                media_id=media_row["media_id"] if media_row else None,
            )
            existing = existing_collections_by_name.get(collection_name)

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["collection_id"], update_payload))

        if unresolved_media:
            raise ValueError(
                "Unable to resolve media_id for collections: "
                f"{sorted(unresolved_media)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_collection_batch(connection, insert_batch)

        for collection_id, update_payload in updates:
            update_collection(connection, collection_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(collections_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    collections_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Target database: {connection_label}")
    print(f"Total master collections: {len(collections_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not collections_df.empty:
        preview_df = collections_df.copy()
        preview_df["media_url"] = preview_df["media_url"].fillna("")
        preview_df["content_json"] = preview_df["content_json"].map(
            lambda value: json.dumps(value, ensure_ascii=False)[:120] + "..."
            if value is not None
            else None
        )
        print("\nPreview:")
        print(preview_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update master collections into catalog.collection."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    collections_df = read_master_collections(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_collections(
        collections_df,
        connection_kwargs,
    )
    print_summary(
        collections_df=collections_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
