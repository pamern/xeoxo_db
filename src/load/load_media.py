from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection_db import get_postgres_connection_kwargs

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "media.csv"
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


def normalize_file_size(value: object) -> int:
    if value is None or pd.isna(value):
        raise ValueError("file_size must not be null")

    try:
        file_size = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid file_size value: {value!r}") from exc

    if file_size < 0:
        raise ValueError(f"file_size must be >= 0, got {file_size}")

    return file_size


def read_master_media(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "storage_key",
        "alt_text",
        "media_type",
        "mime_type",
        "file_size",
        "bucket_name",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["storage_key"] = working_df["storage_key"].map(normalize_text)
    working_df["alt_text"] = working_df["alt_text"].map(normalize_text)
    working_df["media_type"] = working_df["media_type"].map(normalize_text)
    working_df["mime_type"] = working_df["mime_type"].map(normalize_text)
    working_df["bucket_name"] = working_df["bucket_name"].map(normalize_text)
    working_df["file_size"] = working_df["file_size"].map(normalize_file_size)

    working_df = working_df.dropna(
        subset=["storage_key", "media_type", "mime_type", "bucket_name"]
    )
    working_df = (
        working_df.sort_values(by="storage_key", kind="stable")
        .drop_duplicates(subset=["storage_key"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "storage_key",
            "alt_text",
            "media_type",
            "mime_type",
            "file_size",
            "bucket_name",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_media_payload(row: dict) -> dict:
    return {
        "storage_key": row["storage_key"],
        "alt_text": row["alt_text"],
        "media_type": row["media_type"],
        "mime_type": row["mime_type"],
        "file_size": row["file_size"],
        "bucket_name": row["bucket_name"],
    }


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

    existing_by_storage_key: dict[str, dict] = {}
    for row in rows:
        storage_key = normalize_text(row.get("storage_key"))
        if storage_key and storage_key not in existing_by_storage_key:
            existing_by_storage_key[storage_key] = row

    return existing_by_storage_key


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    payload = build_media_payload(incoming)
    changed_fields: dict = {}

    for key, value in payload.items():
        existing_value = (
            existing.get(key)
            if key == "file_size"
            else normalize_text(existing.get(key))
        )
        incoming_value = value if key == "file_size" else normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_media_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
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


def update_media(
    connection: psycopg.Connection,
    media_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.media
        SET {assignments}, updated_at = NOW()
        WHERE media_id = %(media_id)s
    """

    params = dict(update_payload)
    params["media_id"] = media_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_media(media_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_storage_key = fetch_existing_media(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in media_df.to_dict(orient="records"):
            storage_key = record["storage_key"]
            existing = existing_by_storage_key.get(storage_key)

            if existing is None:
                inserts.append(build_media_payload(record))
                continue

            update_payload = build_update_payload(record, existing)
            if update_payload is not None:
                updates.append((existing["media_id"], update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_media_batch(connection, insert_batch)

        for media_id, update_payload in updates:
            update_media(connection, media_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(media_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    media_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master media rows: {len(media_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not media_df.empty:
        print("\nPreview:")
        print(media_df.head(10).to_string(index=False))


def main() -> None:
    media_df = read_master_media(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_media(media_df)
    print_summary(
        media_df=media_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
