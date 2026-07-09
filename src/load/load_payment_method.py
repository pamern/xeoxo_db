from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.file_path import PAYMENT_METHOD_FILE
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


BATCH_SIZE = 500
ALLOWED_METHOD_CODES = {
    "COD",
    "MOMO",
    "VNPAY",
    "CARD",
    "BANK_TRANSFER",
}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value

    text = normalize_text(value)
    if text is None:
        return True

    return text.lower() in {"true", "1", "yes", "y"}


def normalize_method_code(value: object) -> str:
    method_code = normalize_text(value)
    if not method_code:
        raise ValueError("method_code must not be null")

    normalized = method_code.upper()
    if normalized not in ALLOWED_METHOD_CODES:
        raise ValueError(
            f"Invalid method_code: {method_code!r}. "
            f"Expected one of {sorted(ALLOWED_METHOD_CODES)}"
        )

    return normalized


def read_master_payment_methods(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"method_name", "method_code", "is_active"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["method_name"] = working_df["method_name"].map(normalize_text)
    working_df["method_code"] = working_df["method_code"].map(normalize_method_code)
    working_df["is_active"] = working_df["is_active"].map(normalize_bool)

    working_df = working_df.dropna(subset=["method_name", "method_code"])
    working_df = (
        working_df.sort_values(by=["method_code", "method_name"], kind="stable")
        .drop_duplicates(subset=["method_code"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[["method_name", "method_code", "is_active"]]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_payment_method_payload(row: dict) -> dict:
    return {
        "method_name": normalize_text(row["method_name"]),
        "method_code": normalize_method_code(row["method_code"]),
        "is_active": normalize_bool(row["is_active"]),
    }


def fetch_existing_payment_methods(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            method_id,
            method_name,
            method_code,
            is_active
        FROM sales.payment_method
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_code: dict[str, dict] = {}
    for row in rows:
        method_code = normalize_text(row.get("method_code"))
        if method_code and method_code not in existing_by_code:
            existing_by_code[method_code] = row

    return existing_by_code


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    payload = build_payment_method_payload(incoming)
    changed_fields: dict = {}

    for key, value in payload.items():
        existing_value = existing.get(key) if key == "is_active" else normalize_text(
            existing.get(key)
        )
        incoming_value = value if key == "is_active" else normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_payment_method_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO sales.payment_method (
            method_name,
            method_code,
            is_active
        )
        VALUES (
            %(method_name)s,
            %(method_code)s,
            %(is_active)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_payment_method(
    connection: psycopg.Connection,
    method_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE sales.payment_method
        SET {assignments}, updated_at = NOW()
        WHERE method_id = %(method_id)s
    """

    params = dict(update_payload)
    params["method_id"] = method_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_payment_methods(
    payment_methods_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_code = fetch_existing_payment_methods(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in payment_methods_df.to_dict(orient="records"):
            method_code = record["method_code"]
            existing = existing_by_code.get(method_code)

            if existing is None:
                inserts.append(build_payment_method_payload(record))
                continue

            update_payload = build_update_payload(record, existing)
            if update_payload is not None:
                updates.append((existing["method_id"], update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_payment_method_batch(connection, insert_batch)

        for method_id, update_payload in updates:
            update_payment_method(connection, method_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(payment_methods_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    payment_methods_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Target database: {connection_label}")
    print(f"Input file: {PAYMENT_METHOD_FILE}")
    print(f"Total master payment methods: {len(payment_methods_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not payment_methods_df.empty:
        print("\nPreview:")
        print(payment_methods_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update master payment methods into sales.payment_method."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    payment_methods_df = read_master_payment_methods(PAYMENT_METHOD_FILE)
    inserted_count, updated_count, skipped_count = sync_payment_methods(
        payment_methods_df,
        connection_kwargs,
    )
    print_summary(
        payment_methods_df=payment_methods_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
