from __future__ import annotations

from decimal import Decimal, InvalidOperation
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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "size_measurement.csv"
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


def normalize_decimal(value: object) -> Decimal | None:
    text = normalize_text(value)
    if text is None:
        return None

    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def normalize_measurement_code(value: object) -> str:
    measurement_code = normalize_text(value)
    if not measurement_code:
        raise ValueError("measurement_code must not be null")

    return measurement_code.upper()


def validate_measurement_fields(
    measurement_value: Decimal | None,
    measurement_min: Decimal | None,
    measurement_max: Decimal | None,
) -> None:
    if measurement_value is not None:
        return

    if measurement_min is None or measurement_max is None:
        raise ValueError(
            "Expected measurement_value or both measurement_min and measurement_max"
        )


def read_master_size_measurements(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "chart_name",
        "size_name",
        "measurement_code",
        "measurement_value",
        "measurement_min",
        "measurement_max",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["chart_name"] = working_df["chart_name"].map(normalize_text)
    working_df["size_name"] = working_df["size_name"].map(normalize_text)
    working_df["measurement_code"] = working_df["measurement_code"].map(
        normalize_measurement_code
    )
    working_df["measurement_value"] = working_df["measurement_value"].map(
        normalize_decimal
    )
    working_df["measurement_min"] = working_df["measurement_min"].map(normalize_decimal)
    working_df["measurement_max"] = working_df["measurement_max"].map(normalize_decimal)

    working_df = working_df.dropna(
        subset=["chart_name", "size_name", "measurement_code"]
    )

    for record in working_df.to_dict(orient="records"):
        validate_measurement_fields(
            record["measurement_value"],
            record["measurement_min"],
            record["measurement_max"],
        )

    working_df = (
        working_df.sort_values(
            by=["chart_name", "size_name", "measurement_code"],
            kind="stable",
        )
        .drop_duplicates(
            subset=["chart_name", "size_name", "measurement_code"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return working_df[
        [
            "chart_name",
            "size_name",
            "measurement_code",
            "measurement_value",
            "measurement_min",
            "measurement_max",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_size_options(
    connection: psycopg.Connection,
) -> dict[tuple[str, str], dict]:
    query = """
        SELECT
            so.size_option_id,
            so.size_name,
            sc.chart_name
        FROM catalog.size_option so
        INNER JOIN catalog.size_chart sc
            ON sc.size_chart_id = so.size_chart_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        chart_name = normalize_text(row.get("chart_name"))
        size_name = normalize_text(row.get("size_name"))
        if not chart_name or not size_name:
            continue

        key = (chart_name, size_name)
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def fetch_existing_measurement_types(
    connection: psycopg.Connection,
) -> dict[str, dict]:
    query = """
        SELECT
            measurement_type_id,
            measurement_code
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


def fetch_existing_size_measurements(
    connection: psycopg.Connection,
) -> dict[tuple[int, int], dict]:
    query = """
        SELECT
            measurement_id,
            size_option_id,
            measurement_type_id,
            measurement_value,
            measurement_min,
            measurement_max
        FROM catalog.size_measurement
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[int, int], dict] = {}
    for row in rows:
        size_option_id = row.get("size_option_id")
        measurement_type_id = row.get("measurement_type_id")
        if size_option_id is None or measurement_type_id is None:
            continue

        key = (int(size_option_id), int(measurement_type_id))
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def build_size_measurement_payload(
    row: dict,
    size_option_id: int,
    measurement_type_id: int,
) -> dict:
    measurement_value = normalize_decimal(row["measurement_value"])
    measurement_min = normalize_decimal(row["measurement_min"])
    measurement_max = normalize_decimal(row["measurement_max"])

    validate_measurement_fields(
        measurement_value,
        measurement_min,
        measurement_max,
    )

    return {
        "size_option_id": size_option_id,
        "measurement_type_id": measurement_type_id,
        "measurement_value": measurement_value,
        "measurement_min": measurement_min,
        "measurement_max": measurement_max,
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        existing_value = existing.get(key)
        incoming_value = value

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_size_measurement_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.size_measurement (
            size_option_id,
            measurement_type_id,
            measurement_value,
            measurement_min,
            measurement_max
        )
        VALUES (
            %(size_option_id)s,
            %(measurement_type_id)s,
            %(measurement_value)s,
            %(measurement_min)s,
            %(measurement_max)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_size_measurement(
    connection: psycopg.Connection,
    measurement_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.size_measurement
        SET {assignments}, updated_at = NOW()
        WHERE measurement_id = %(measurement_id)s
    """

    params = dict(update_payload)
    params["measurement_id"] = measurement_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_size_measurements(
    size_measurements_df: pd.DataFrame,
) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        size_options_by_key = fetch_existing_size_options(connection)
        measurement_types_by_code = fetch_existing_measurement_types(connection)
        existing_size_measurements = fetch_existing_size_measurements(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_size_options: list[tuple[str, str, str]] = []
        unresolved_measurement_types: list[tuple[str, str, str]] = []

        for record in size_measurements_df.to_dict(orient="records"):
            chart_name = normalize_text(record["chart_name"])
            size_name = normalize_text(record["size_name"])
            measurement_code = normalize_measurement_code(record["measurement_code"])

            size_option = size_options_by_key.get((chart_name, size_name))
            if size_option is None:
                unresolved_size_options.append(
                    (chart_name or "", size_name or "", measurement_code)
                )
                continue

            measurement_type = measurement_types_by_code.get(measurement_code)
            if measurement_type is None:
                unresolved_measurement_types.append(
                    (measurement_code, chart_name or "", size_name or "")
                )
                continue

            payload = build_size_measurement_payload(
                row=record,
                size_option_id=size_option["size_option_id"],
                measurement_type_id=measurement_type["measurement_type_id"],
            )
            key = (payload["size_option_id"], payload["measurement_type_id"])
            existing = existing_size_measurements.get(key)

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["measurement_id"], update_payload))

        if unresolved_size_options:
            raise ValueError(
                "Unable to resolve size_option_id for size measurements: "
                f"{sorted(unresolved_size_options)}"
            )

        if unresolved_measurement_types:
            raise ValueError(
                "Unable to resolve measurement_type_id for size measurements: "
                f"{sorted(unresolved_measurement_types)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_size_measurement_batch(connection, insert_batch)

        for measurement_id, update_payload in updates:
            update_size_measurement(connection, measurement_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(size_measurements_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    size_measurements_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master size measurements: {len(size_measurements_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not size_measurements_df.empty:
        print("\nPreview:")
        print(size_measurements_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    size_measurements_df = read_master_size_measurements(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_size_measurements(
        size_measurements_df
    )
    print_summary(
        size_measurements_df=size_measurements_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
