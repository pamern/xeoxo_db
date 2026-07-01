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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "color.csv"
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


def normalize_color_code(value: object) -> str | None:
    color_code = normalize_text(value)
    if not color_code:
        return None

    return color_code.upper()


def read_master_colors(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"color_name", "color_group"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["color_name"] = working_df["color_name"].map(normalize_text)
    working_df["color_group"] = working_df["color_group"].map(normalize_text)
    working_df["color_code"] = (
        working_df["color_code"].map(normalize_color_code)
        if "color_code" in working_df.columns
        else None
    )
    working_df["media_id"] = None

    working_df = working_df.dropna(subset=["color_name"])
    working_df = (
        working_df.sort_values(by=["color_name", "color_group"], kind="stable")
        .drop_duplicates(subset=["color_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[["color_name", "color_code", "color_group", "media_id"]]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_color_payload(row: dict) -> dict:
    return {
        "color_name": row["color_name"],
        "color_code": row["color_code"],
        "color_group": row["color_group"],
        "media_id": row["media_id"],
    }


def fetch_existing_colors(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            color_id,
            color_name,
            color_code,
            color_group,
            media_id
        FROM catalog.color
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        color_name = normalize_text(row.get("color_name"))
        if color_name and color_name not in existing_by_name:
            existing_by_name[color_name] = row

    return existing_by_name


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    payload = build_color_payload(incoming)
    changed_fields: dict = {}

    for key, value in payload.items():
        existing_value = existing.get(key) if key == "media_id" else normalize_text(
            existing.get(key)
        )
        incoming_value = value if key == "media_id" else normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_color_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.color (
            color_name,
            color_code,
            color_group,
            media_id
        )
        VALUES (
            %(color_name)s,
            %(color_code)s,
            %(color_group)s,
            %(media_id)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_color(
    connection: psycopg.Connection,
    color_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.color
        SET {assignments}, updated_at = NOW()
        WHERE color_id = %(color_id)s
    """

    params = dict(update_payload)
    params["color_id"] = color_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_colors(colors_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_name = fetch_existing_colors(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in colors_df.to_dict(orient="records"):
            color_name = record["color_name"]
            existing = existing_by_name.get(color_name)

            if existing is None:
                inserts.append(build_color_payload(record))
                continue

            update_payload = build_update_payload(record, existing)
            if update_payload is not None:
                updates.append((existing["color_id"], update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_color_batch(connection, insert_batch)

        for color_id, update_payload in updates:
            update_color(connection, color_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(colors_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    colors_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master colors: {len(colors_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not colors_df.empty:
        print("\nPreview:")
        print(colors_df.head(10).to_string(index=False))


def main() -> None:
    colors_df = read_master_colors(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_colors(colors_df)
    print_summary(
        colors_df=colors_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
