from __future__ import annotations

import argparse
from pathlib import Path
import re
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


INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "product_components.csv"
PRODUCT_LINES_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
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
        return False

    return text.lower() in {"true", "1", "yes", "y"}


def normalize_display_order(value: object) -> int:
    if value is None or pd.isna(value):
        return 1

    try:
        display_order = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid component_order value: {value!r}") from exc

    if display_order <= 0:
        raise ValueError(f"component_order must be > 0, got {display_order}")

    return display_order


def normalize_component_type(value: object) -> str:
    component_type = normalize_text(value)
    if not component_type:
        raise ValueError("component_type must not be null")

    normalized = component_type.strip().upper()
    allowed = {"AO", "QUAN", "DAM", "SET", "VAY", "KHAC"}
    if normalized not in allowed:
        raise ValueError(
            f"Invalid component_type: {component_type!r}. Expected one of {sorted(allowed)}"
        )

    return normalized


def normalize_component_name(value: object) -> str | None:
    component_name = normalize_text(value)
    if not component_name:
        return None

    component_name = re.sub(
        r"\bAD\b",
        "Áo dài",
        component_name,
        flags=re.IGNORECASE,
    )
    return normalize_text(component_name)


def read_raw_product_components(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "parent_line_name",
        "parent_product_url",
        "component_order",
        "component_name",
        "component_type",
        "is_required",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["parent_line_name"] = working_df["parent_line_name"].map(normalize_text)
    working_df["parent_product_url"] = working_df["parent_product_url"].map(normalize_text)
    working_df["component_name"] = working_df["component_name"].map(
        normalize_component_name
    )
    working_df["component_type"] = working_df["component_type"].map(normalize_component_type)
    working_df["is_required"] = working_df["is_required"].map(normalize_bool)
    working_df["display_order"] = working_df["component_order"].map(normalize_display_order)
    if "component_url" in working_df.columns:
        working_df["component_url"] = working_df["component_url"].map(normalize_text)
    else:
        working_df["component_url"] = None
    if "source_component_product_id" in working_df.columns:
        working_df["source_component_product_id"] = (
            working_df["source_component_product_id"].map(normalize_text)
        )
    else:
        working_df["source_component_product_id"] = None

    working_df = working_df.dropna(
        subset=["parent_line_name", "parent_product_url", "component_name", "component_type"]
    )
    working_df = (
        working_df.sort_values(
            by=[
                "parent_product_url",
                "display_order",
                "component_name",
                "component_type",
                "component_url",
                "source_component_product_id",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "parent_product_url",
                "display_order",
                "component_name",
                "component_type",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return working_df[
        [
            "parent_line_name",
            "parent_product_url",
            "component_name",
            "component_type",
            "is_required",
            "display_order",
        ]
    ]


def read_staging_product_lines(input_file: Path) -> dict[str, dict]:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"collection_name", "product_name", "product_url"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    lookup_by_url: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        product_url = normalize_text(record.get("product_url"))
        collection_name = normalize_text(record.get("collection_name"))
        product_name = normalize_text(record.get("product_name"))

        if not product_url or product_url in lookup_by_url:
            continue

        lookup_by_url[product_url] = {
            "collection_name": collection_name,
            "line_name": product_name,
        }

    return lookup_by_url


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_product_lines(connection: psycopg.Connection) -> dict[tuple[str, str], dict]:
    query = """
        SELECT
            pl.product_line_id,
            pl.line_name,
            c.collection_name
        FROM catalog.product_line pl
        LEFT JOIN catalog.collection c
            ON c.collection_id = pl.collection_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        collection_name = normalize_text(row.get("collection_name"))
        line_name = normalize_text(row.get("line_name"))
        if not collection_name or not line_name:
            continue

        key = (collection_name, line_name)
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def fetch_existing_product_components(
    connection: psycopg.Connection,
) -> dict[tuple[int, int], dict]:
    query = """
        SELECT
            component_id,
            product_line_id,
            component_name,
            component_type,
            is_required,
            display_order
        FROM catalog.product_component
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[int, int], dict] = {}
    for row in rows:
        product_line_id = row.get("product_line_id")
        display_order = row.get("display_order")

        if product_line_id is None or display_order is None:
            continue

        key = (product_line_id, int(display_order))
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def build_product_component_payload(
    row: dict,
    product_line_id: int,
) -> dict:
    return {
        "component_name": normalize_component_name(row["component_name"]),
        "product_line_id": product_line_id,
        "component_type": normalize_component_type(row["component_type"]),
        "is_required": normalize_bool(row["is_required"]),
        "display_order": normalize_display_order(row["display_order"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"product_line_id", "is_required", "display_order"}:
            existing_value = existing.get(key)
            incoming_value = value
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_product_component_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.product_component (
            component_name,
            product_line_id,
            component_type,
            is_required,
            display_order
        )
        VALUES (
            %(component_name)s,
            %(product_line_id)s,
            %(component_type)s,
            %(is_required)s,
            %(display_order)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_product_component(
    connection: psycopg.Connection,
    component_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.product_component
        SET {assignments}, updated_at = NOW()
        WHERE component_id = %(component_id)s
    """

    params = dict(update_payload)
    params["component_id"] = component_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_product_components(
    components_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    staging_product_lines = read_staging_product_lines(PRODUCT_LINES_FILE)

    with psycopg.connect(**connection_kwargs) as connection:
        product_lines_by_key = fetch_existing_product_lines(connection)
        existing_components = fetch_existing_product_components(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_staging_links: list[tuple[str, str]] = []
        unresolved_product_lines: list[tuple[str, str, str]] = []
        duplicate_component_slots: list[tuple[str, int, str, str]] = []
        seen_slots: set[tuple[int, int]] = set()

        for record in components_df.to_dict(orient="records"):
            parent_product_url = normalize_text(record["parent_product_url"])
            parent_line_name = normalize_text(record["parent_line_name"])

            staging_line = staging_product_lines.get(parent_product_url)
            if staging_line is None:
                unresolved_staging_links.append((parent_line_name or "", parent_product_url or ""))
                continue

            collection_name = normalize_text(staging_line["collection_name"])
            line_name = normalize_text(staging_line["line_name"])
            product_line = product_lines_by_key.get((collection_name, line_name))
            if product_line is None:
                unresolved_product_lines.append(
                    (collection_name or "", line_name or "", parent_product_url or "")
                )
                continue

            payload = build_product_component_payload(
                row=record,
                product_line_id=product_line["product_line_id"],
            )
            key = (payload["product_line_id"], payload["display_order"])

            if key in seen_slots:
                duplicate_component_slots.append(
                    (
                        line_name or "",
                        payload["display_order"],
                        payload["component_name"] or "",
                        payload["component_type"] or "",
                    )
                )
                continue

            seen_slots.add(key)

            existing = existing_components.get(key)
            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["component_id"], update_payload))

        if unresolved_staging_links:
            raise ValueError(
                "Unable to resolve staging product_line for product components: "
                f"{sorted(unresolved_staging_links)}"
            )

        if unresolved_product_lines:
            raise ValueError(
                "Unable to resolve product_line_id for product components: "
                f"{sorted(unresolved_product_lines)}"
            )

        if duplicate_component_slots:
            raise ValueError(
                "Duplicate component slots detected for the same product_line/display_order: "
                f"{sorted(duplicate_component_slots)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_product_component_batch(connection, insert_batch)

        for component_id, update_payload in updates:
            update_product_component(connection, component_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(components_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    components_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Target database: {connection_label}")
    print(f"Total raw product components: {len(components_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not components_df.empty:
        print("\nPreview:")
        print(components_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update raw product components into catalog.product_component."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    components_df = read_raw_product_components(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_product_components(
        components_df,
        connection_kwargs,
    )
    print_summary(
        components_df=components_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
