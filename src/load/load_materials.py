from __future__ import annotations

import argparse
from pathlib import Path
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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "material.csv"
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


def read_master_materials(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"material_name", "description"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["material_name"] = working_df["material_name"].map(normalize_text)
    working_df["description"] = working_df["description"].map(normalize_text)
    working_df["care_instruction"] = None
    working_df["media_id"] = None
    working_df["is_active"] = True

    working_df = working_df.dropna(subset=["material_name"])
    working_df = (
        working_df.sort_values(by="material_name", kind="stable")
        .drop_duplicates(subset=["material_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        ["material_name", "description", "care_instruction", "media_id", "is_active"]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_material_payload(row: dict) -> dict:
    return {
        "material_name": row["material_name"],
        "description": row["description"],
        "care_instruction": row["care_instruction"],
        "media_id": row["media_id"],
        "is_active": row["is_active"],
    }


def fetch_existing_materials(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            material_id,
            material_name,
            description,
            care_instruction,
            media_id,
            is_active
        FROM catalog.material
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        material_name = normalize_text(row.get("material_name"))
        if material_name and material_name not in existing_by_name:
            existing_by_name[material_name] = row

    return existing_by_name


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    payload = build_material_payload(incoming)
    changed_fields: dict = {}

    for key, value in payload.items():
        existing_value = (
            normalize_text(existing.get(key))
            if key != "is_active"
            else existing.get(key)
        )
        incoming_value = normalize_text(value) if key != "is_active" else value

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_material_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.material (
            material_name,
            description,
            care_instruction,
            media_id,
            is_active
        )
        VALUES (
            %(material_name)s,
            %(description)s,
            %(care_instruction)s,
            %(media_id)s,
            %(is_active)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_material(
    connection: psycopg.Connection,
    material_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.material
        SET {assignments}, updated_at = NOW()
        WHERE material_id = %(material_id)s
    """

    params = dict(update_payload)
    params["material_id"] = material_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_materials(
    materials_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_name = fetch_existing_materials(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []

        for record in materials_df.to_dict(orient="records"):
            material_name = record["material_name"]
            existing = existing_by_name.get(material_name)

            if existing is None:
                inserts.append(build_material_payload(record))
                continue

            update_payload = build_update_payload(record, existing)
            if update_payload is not None:
                updates.append((existing["material_id"], update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_material_batch(connection, insert_batch)

        for material_id, update_payload in updates:
            update_material(connection, material_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(materials_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    materials_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Target database: {connection_label}")
    print(f"Total master materials: {len(materials_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not materials_df.empty:
        print("\nPreview:")
        print(materials_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update master materials into catalog.material."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    materials_df = read_master_materials(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_materials(
        materials_df,
        connection_kwargs,
    )
    print_summary(
        materials_df=materials_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
