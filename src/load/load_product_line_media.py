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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "product_line_media.csv"
BATCH_SIZE = 500
ALLOWED_MEDIA_ROLES = {"Main", "Gallery", "Detail", "Lookbook"}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def normalize_int(value: object, field_name: str) -> int:
    if value is None or pd.isna(value):
        raise ValueError(f"{field_name} must not be null")

    text = normalize_text(value)
    if text is None:
        raise ValueError(f"{field_name} must not be null")

    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}") from exc


def normalize_media_role(value: object) -> str:
    media_role = normalize_text(value)
    if not media_role:
        raise ValueError("media_role must not be null")

    normalized = media_role.capitalize()
    if normalized not in ALLOWED_MEDIA_ROLES:
        raise ValueError(
            f"Invalid media_role: {media_role!r}. Expected one of {sorted(ALLOWED_MEDIA_ROLES)}"
        )

    return normalized


def normalize_display_order(value: object) -> int:
    display_order = normalize_int(value, "display_order")
    if display_order <= 0:
        raise ValueError(f"display_order must be > 0, got {display_order}")

    return display_order


def read_master_product_line_media(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "product_line_id",
        "media_id",
        "media_role",
        "display_order",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["product_line_id"] = working_df["product_line_id"].map(
        lambda value: normalize_int(value, "product_line_id")
    )
    working_df["media_id"] = working_df["media_id"].map(
        lambda value: normalize_int(value, "media_id")
    )
    working_df["media_role"] = working_df["media_role"].map(normalize_media_role)
    working_df["display_order"] = working_df["display_order"].map(
        normalize_display_order
    )

    working_df = (
        working_df.sort_values(
            by=["product_line_id", "display_order", "media_id"],
            kind="stable",
        )
        .drop_duplicates(subset=["product_line_id", "media_id"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        ["product_line_id", "media_id", "media_role", "display_order"]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_product_lines(connection: psycopg.Connection) -> set[int]:
    query = """
        SELECT product_line_id
        FROM catalog.product_line
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    return {int(row[0]) for row in rows if row and row[0] is not None}


def fetch_existing_media(connection: psycopg.Connection) -> set[int]:
    query = """
        SELECT media_id
        FROM catalog.media
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    return {int(row[0]) for row in rows if row and row[0] is not None}


def fetch_existing_product_line_media(
    connection: psycopg.Connection,
) -> dict[tuple[int, int], dict]:
    query = """
        SELECT
            product_line_id,
            media_id,
            media_role,
            display_order
        FROM catalog.product_line_media
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[int, int], dict] = {}
    for row in rows:
        product_line_id = row.get("product_line_id")
        media_id = row.get("media_id")
        if product_line_id is None or media_id is None:
            continue

        key = (int(product_line_id), int(media_id))
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def build_product_line_media_payload(row: dict) -> dict:
    return {
        "product_line_id": normalize_int(row["product_line_id"], "product_line_id"),
        "media_id": normalize_int(row["media_id"], "media_id"),
        "media_role": normalize_media_role(row["media_role"]),
        "display_order": normalize_display_order(row["display_order"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"product_line_id", "media_id", "display_order"}:
            existing_value = existing.get(key)
            incoming_value = value
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_product_line_media_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.product_line_media (
            product_line_id,
            media_id,
            media_role,
            display_order
        )
        VALUES (
            %(product_line_id)s,
            %(media_id)s,
            %(media_role)s,
            %(display_order)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_product_line_media(
    connection: psycopg.Connection,
    product_line_id: int,
    media_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.product_line_media
        SET {assignments}
        WHERE product_line_id = %(product_line_id)s
          AND media_id = %(media_id)s
    """

    params = dict(update_payload)
    params["product_line_id"] = product_line_id
    params["media_id"] = media_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_product_line_media(product_line_media_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        existing_product_line_ids = fetch_existing_product_lines(connection)
        existing_media_ids = fetch_existing_media(connection)
        existing_product_line_media = fetch_existing_product_line_media(connection)

        inserts: list[dict] = []
        updates: list[tuple[tuple[int, int], dict]] = []
        unresolved_product_lines: list[int] = []
        unresolved_media: list[int] = []

        for record in product_line_media_df.to_dict(orient="records"):
            payload = build_product_line_media_payload(record)

            if payload["product_line_id"] not in existing_product_line_ids:
                unresolved_product_lines.append(payload["product_line_id"])
                continue

            if payload["media_id"] not in existing_media_ids:
                unresolved_media.append(payload["media_id"])
                continue

            key = (payload["product_line_id"], payload["media_id"])
            existing = existing_product_line_media.get(key)
            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((key, update_payload))

        if unresolved_product_lines:
            raise ValueError(
                "Unable to resolve product_line_id for product_line_media: "
                f"{sorted(set(unresolved_product_lines))}"
            )

        if unresolved_media:
            raise ValueError(
                "Unable to resolve media_id for product_line_media: "
                f"{sorted(set(unresolved_media))}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_product_line_media_batch(connection, insert_batch)

        for (product_line_id, media_id), update_payload in updates:
            update_product_line_media(
                connection,
                product_line_id=product_line_id,
                media_id=media_id,
                update_payload=update_payload,
            )
            updated_count += 1

        connection.commit()

    skipped_count = len(product_line_media_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    product_line_media_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master product_line_media rows: {len(product_line_media_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not product_line_media_df.empty:
        print("\nPreview:")
        print(product_line_media_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    product_line_media_df = read_master_product_line_media(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_product_line_media(
        product_line_media_df
    )
    print_summary(
        product_line_media_df=product_line_media_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
