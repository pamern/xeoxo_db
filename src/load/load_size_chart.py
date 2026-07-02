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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "size_chart.csv"
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


def read_master_size_charts(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"chart_name", "description", "is_active"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["chart_name"] = working_df["chart_name"].map(normalize_text)
    working_df["description"] = working_df["description"].map(normalize_text)
    working_df["is_active"] = working_df["is_active"].map(normalize_bool)

    if "collection_name" not in working_df.columns:
        working_df["collection_name"] = None
    if "line_name" not in working_df.columns:
        working_df["line_name"] = None

    working_df["collection_name"] = working_df["collection_name"].map(normalize_text)
    working_df["line_name"] = working_df["line_name"].map(normalize_text)

    working_df = working_df.dropna(subset=["chart_name"])
    working_df = (
        working_df.sort_values(
            by=["chart_name", "collection_name", "line_name"],
            kind="stable",
        )
        .drop_duplicates(subset=["chart_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "chart_name",
            "description",
            "is_active",
            "collection_name",
            "line_name",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_product_lines(
    connection: psycopg.Connection,
) -> dict[tuple[str, str], dict]:
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


def fetch_existing_size_charts(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            size_chart_id,
            chart_name,
            product_line_id,
            description,
            is_active
        FROM catalog.size_chart
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        chart_name = normalize_text(row.get("chart_name"))
        if chart_name and chart_name not in existing_by_name:
            existing_by_name[chart_name] = row

    return existing_by_name


def build_size_chart_payload(
    row: dict,
    product_line_id: int | None,
) -> dict:
    return {
        "chart_name": normalize_text(row["chart_name"]),
        "product_line_id": product_line_id,
        "description": normalize_text(row["description"]),
        "is_active": normalize_bool(row["is_active"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"product_line_id", "is_active"}:
            existing_value = existing.get(key)
            incoming_value = value
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_size_chart_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.size_chart (
            chart_name,
            product_line_id,
            description,
            is_active
        )
        VALUES (
            %(chart_name)s,
            %(product_line_id)s,
            %(description)s,
            %(is_active)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_size_chart(
    connection: psycopg.Connection,
    size_chart_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.size_chart
        SET {assignments}, updated_at = NOW()
        WHERE size_chart_id = %(size_chart_id)s
    """

    params = dict(update_payload)
    params["size_chart_id"] = size_chart_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_size_charts(
    size_charts_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        product_lines_by_key = fetch_existing_product_lines(connection)
        existing_size_charts = fetch_existing_size_charts(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_product_lines: list[tuple[str, str, str]] = []

        for record in size_charts_df.to_dict(orient="records"):
            collection_name = normalize_text(record.get("collection_name"))
            line_name = normalize_text(record.get("line_name"))
            chart_name = normalize_text(record.get("chart_name"))

            product_line_id = None
            if collection_name or line_name:
                if not collection_name or not line_name:
                    unresolved_product_lines.append(
                        (chart_name or "", collection_name or "", line_name or "")
                    )
                    continue

                product_line = product_lines_by_key.get((collection_name, line_name))
                if product_line is None:
                    unresolved_product_lines.append(
                        (chart_name or "", collection_name, line_name)
                    )
                    continue

                product_line_id = product_line["product_line_id"]

            payload = build_size_chart_payload(
                row=record,
                product_line_id=product_line_id,
            )
            existing = existing_size_charts.get(payload["chart_name"])

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["size_chart_id"], update_payload))

        if unresolved_product_lines:
            raise ValueError(
                "Unable to resolve product_line_id for size charts: "
                f"{sorted(unresolved_product_lines)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_size_chart_batch(connection, insert_batch)

        for size_chart_id, update_payload in updates:
            update_size_chart(connection, size_chart_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(size_charts_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    size_charts_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Target database: {connection_label}")
    print(f"Total master size charts: {len(size_charts_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not size_charts_df.empty:
        preview_df = size_charts_df.copy()
        preview_df["collection_name"] = preview_df["collection_name"].fillna("")
        preview_df["line_name"] = preview_df["line_name"].fillna("")
        print("\nPreview:")
        print(preview_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update master size charts into catalog.size_chart."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    size_charts_df = read_master_size_charts(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_size_charts(
        size_charts_df,
        connection_kwargs,
    )
    print_summary(
        size_charts_df=size_charts_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
