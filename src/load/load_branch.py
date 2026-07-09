from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.file_path import BRANCH_FILE
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


def read_master_branches(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"branch_name", "address", "phone", "is_active"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["branch_name"] = working_df["branch_name"].map(normalize_text)
    working_df["address"] = working_df["address"].map(normalize_text)
    working_df["phone"] = working_df["phone"].map(normalize_text)
    working_df["is_active"] = working_df["is_active"].map(normalize_bool)

    working_df = working_df.dropna(subset=["branch_name", "address", "phone"])
    working_df = (
        working_df.sort_values(by=["branch_name", "address"], kind="stable")
        .drop_duplicates(subset=["branch_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[["branch_name", "address", "phone", "is_active"]]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_branch_payload(row: dict) -> dict:
    return {
        "branch_name": normalize_text(row["branch_name"]),
        "address": normalize_text(row["address"]),
        "phone": normalize_text(row["phone"]),
        "is_active": normalize_bool(row["is_active"]),
    }


def fetch_existing_branches(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            branch_id,
            branch_name,
            address,
            phone,
            is_active
        FROM iam.branch
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        branch_name = normalize_text(row.get("branch_name"))
        if branch_name and branch_name not in existing_by_name:
            existing_by_name[branch_name] = row

    return existing_by_name


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        existing_value = (
            existing.get(key) if key == "is_active" else normalize_text(existing.get(key))
        )
        incoming_value = value if key == "is_active" else normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_branch_batch(connection: psycopg.Connection, records: list[dict]) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO iam.branch (
            branch_name,
            address,
            phone,
            is_active
        )
        VALUES (
            %(branch_name)s,
            %(address)s,
            %(phone)s,
            %(is_active)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_branch(
    connection: psycopg.Connection,
    branch_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE iam.branch
        SET {assignments}, updated_at = NOW()
        WHERE branch_id = %(branch_id)s
    """

    params = dict(update_payload)
    params["branch_id"] = branch_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_branches(
    branches_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_name = fetch_existing_branches(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in branches_df.to_dict(orient="records"):
            payload = build_branch_payload(record)
            existing = existing_by_name.get(payload["branch_name"])

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["branch_id"], update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_branch_batch(connection, insert_batch)

        for branch_id, update_payload in updates:
            update_branch(connection, branch_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(branches_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    branches_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Target database: {connection_label}")
    print(f"Input file: {BRANCH_FILE}")
    print(f"Total master branches: {len(branches_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not branches_df.empty:
        print("\nPreview:")
        print(branches_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update master branches into iam.branch."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    branches_df = read_master_branches(BRANCH_FILE)
    inserted_count, updated_count, skipped_count = sync_branches(
        branches_df,
        connection_kwargs,
    )
    print_summary(
        branches_df=branches_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
