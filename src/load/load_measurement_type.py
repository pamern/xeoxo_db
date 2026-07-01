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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "measurement_type.csv"
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


def normalize_measurement_code(value: object) -> str:
    measurement_code = normalize_text(value)
    if not measurement_code:
        raise ValueError("measurement_code must not be null")

    return measurement_code.upper()


def normalize_unit(value: object) -> str:
    unit = normalize_text(value)
    if not unit:
        raise ValueError("unit must not be null")

    return unit.lower()


def read_master_measurement_types(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "measurement_code",
        "measurement_name",
        "unit",
        "description",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["measurement_code"] = working_df["measurement_code"].map(
        normalize_measurement_code
    )
    working_df["measurement_name"] = working_df["measurement_name"].map(
        normalize_text
    )
    working_df["unit"] = working_df["unit"].map(normalize_unit)
    working_df["description"] = working_df["description"].map(normalize_text)

    working_df = working_df.dropna(
        subset=["measurement_code", "measurement_name", "unit"]
    )
    working_df = (
        working_df.sort_values(
            by=["measurement_code", "measurement_name"],
            kind="stable",
        )
        .drop_duplicates(subset=["measurement_code"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "measurement_code",
            "measurement_name",
            "unit",
            "description",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_measurement_types(
    connection: psycopg.Connection,
) -> dict[str, dict]:
    query = """
        SELECT
            measurement_type_id,
            measurement_code,
            measurement_name,
            unit,
            description
        FROM catalog.measurement_type
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_code: dict[str, dict] = {}
    for row in rows:
        measurement_code = normalize_text(row.get("measurement_code"))
        if measurement_code and measurement_code not in existing_by_code:
            existing_by_code[measurement_code] = row

    return existing_by_code


def build_measurement_type_payload(row: dict) -> dict:
    return {
        "measurement_code": normalize_measurement_code(row["measurement_code"]),
        "measurement_name": normalize_text(row["measurement_name"]),
        "unit": normalize_unit(row["unit"]),
        "description": normalize_text(row["description"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        existing_value = normalize_text(existing.get(key))
        incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_measurement_type_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.measurement_type (
            measurement_code,
            measurement_name,
            unit,
            description
        )
        VALUES (
            %(measurement_code)s,
            %(measurement_name)s,
            %(unit)s,
            %(description)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_measurement_type(
    connection: psycopg.Connection,
    measurement_type_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.measurement_type
        SET {assignments}, updated_at = NOW()
        WHERE measurement_type_id = %(measurement_type_id)s
    """

    params = dict(update_payload)
    params["measurement_type_id"] = measurement_type_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_measurement_types(
    measurement_types_df: pd.DataFrame,
) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        existing_measurement_types = fetch_existing_measurement_types(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in measurement_types_df.to_dict(orient="records"):
            payload = build_measurement_type_payload(record)
            existing = existing_measurement_types.get(payload["measurement_code"])

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["measurement_type_id"], update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_measurement_type_batch(connection, insert_batch)

        for measurement_type_id, update_payload in updates:
            update_measurement_type(connection, measurement_type_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(measurement_types_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    measurement_types_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master measurement types: {len(measurement_types_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not measurement_types_df.empty:
        print("\nPreview:")
        print(measurement_types_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    measurement_types_df = read_master_measurement_types(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_measurement_types(
        measurement_types_df
    )
    print_summary(
        measurement_types_df=measurement_types_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
