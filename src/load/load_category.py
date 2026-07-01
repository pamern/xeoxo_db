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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "category.csv"
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


def normalize_department(value: object) -> str | None:
    department = normalize_text(value)
    if not department:
        return None

    normalized = department.strip().lower()
    allowed = {
        "men": "Men",
        "women": "Women",
        "kids": "Kids",
    }
    if normalized not in allowed:
        raise ValueError(
            f"Invalid department: {department!r}. Expected one of {sorted(allowed.values())}"
        )

    return allowed[normalized]


def read_master_categories(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "category_name",
        "description",
        "parent_name",
        "department",
        "slug",
        "is_active",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["category_name"] = working_df["category_name"].map(normalize_text)
    working_df["description"] = working_df["description"].map(normalize_text)
    working_df["parent_name"] = working_df["parent_name"].map(normalize_text)
    working_df["department"] = working_df["department"].map(normalize_department)
    working_df["slug"] = working_df["slug"].map(normalize_text)
    working_df["is_active"] = working_df["is_active"].map(normalize_bool)

    working_df = working_df.dropna(subset=["category_name", "slug"])
    working_df = (
        working_df.sort_values(by=["category_name", "slug"], kind="stable")
        .drop_duplicates(subset=["category_name"], keep="first")
        .reset_index(drop=True)
    )

    parent_names = set(working_df["parent_name"].dropna())
    category_names = set(working_df["category_name"])
    missing_parents = sorted(parent_names - category_names)
    if missing_parents:
        raise ValueError(
            "Missing parent categories in master file: "
            f"{missing_parents}"
        )

    return working_df[
        [
            "category_name",
            "description",
            "parent_name",
            "department",
            "slug",
            "is_active",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_category_payload(row: dict, parent_id: int | None) -> dict:
    return {
        "category_name": normalize_text(row["category_name"]),
        "description": normalize_text(row["description"]),
        "parent_id": parent_id,
        "department": normalize_department(row["department"]),
        "slug": normalize_text(row["slug"]),
        "is_active": normalize_bool(row["is_active"]),
    }


def fetch_existing_categories(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            category_id,
            category_name,
            description,
            parent_id,
            department,
            slug,
            is_active
        FROM catalog.category
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        category_name = normalize_text(row.get("category_name"))
        if category_name and category_name not in existing_by_name:
            existing_by_name[category_name] = row

    return existing_by_name


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        existing_value = existing.get(key) if key in {"parent_id", "is_active"} else normalize_text(
            existing.get(key)
        )
        incoming_value = value if key in {"parent_id", "is_active"} else normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_category_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.category (
            category_name,
            description,
            parent_id,
            department,
            slug,
            is_active
        )
        VALUES (
            %(category_name)s,
            %(description)s,
            %(parent_id)s,
            %(department)s,
            %(slug)s,
            %(is_active)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_category(
    connection: psycopg.Connection,
    category_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.category
        SET {assignments}, updated_at = NOW()
        WHERE category_id = %(category_id)s
    """

    params = dict(update_payload)
    params["category_id"] = category_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def insert_missing_categories(
    connection: psycopg.Connection,
    categories_df: pd.DataFrame,
    existing_by_name: dict[str, dict],
) -> int:
    pending_records = categories_df.to_dict(orient="records")
    inserted_count = 0

    while pending_records:
        ready_records: list[dict] = []
        waiting_records: list[dict] = []

        for record in pending_records:
            parent_name = normalize_text(record["parent_name"])
            parent = existing_by_name.get(parent_name) if parent_name else None

            if parent_name and parent is None:
                waiting_records.append(record)
                continue

            ready_records.append(
                build_category_payload(
                    row=record,
                    parent_id=parent["category_id"] if parent else None,
                )
            )

        if not ready_records:
            unresolved = sorted(
                {
                    record["category_name"]: record["parent_name"]
                    for record in waiting_records
                }.items()
            )
            raise ValueError(f"Unable to resolve parent categories: {unresolved}")

        for insert_batch in chunk_records(ready_records, BATCH_SIZE):
            insert_category_batch(connection, insert_batch)
            inserted_count += len(insert_batch)

        existing_by_name.clear()
        existing_by_name.update(fetch_existing_categories(connection))
        pending_records = waiting_records

    return inserted_count


def update_existing_categories(
    connection: psycopg.Connection,
    categories_df: pd.DataFrame,
    existing_by_name: dict[str, dict],
) -> int:
    updated_count = 0

    for record in categories_df.to_dict(orient="records"):
        existing = existing_by_name[record["category_name"]]
        parent_name = normalize_text(record["parent_name"])
        parent = existing_by_name.get(parent_name) if parent_name else None
        payload = build_category_payload(
            row=record,
            parent_id=parent["category_id"] if parent else None,
        )
        update_payload = build_update_payload(payload, existing)

        if update_payload is None:
            continue

        update_category(connection, existing["category_id"], update_payload)
        updated_count += 1

    return updated_count


def sync_categories(categories_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_name = fetch_existing_categories(connection)

        missing_df = categories_df[
            ~categories_df["category_name"].isin(existing_by_name.keys())
        ].copy()

        inserted_count = insert_missing_categories(
            connection=connection,
            categories_df=missing_df,
            existing_by_name=existing_by_name,
        )

        existing_by_name = fetch_existing_categories(connection)
        updated_count = update_existing_categories(
            connection=connection,
            categories_df=categories_df,
            existing_by_name=existing_by_name,
        )

        connection.commit()

    skipped_count = len(categories_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    categories_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master categories: {len(categories_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not categories_df.empty:
        print("\nPreview:")
        print(categories_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    categories_df = read_master_categories(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_categories(categories_df)
    print_summary(
        categories_df=categories_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
