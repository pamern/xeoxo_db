from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unicodedata

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


BATCH_SIZE = 500


def normalize_text(value: object) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"null", "n/a", "na", "none"}:
        return None

    return text


def fold_text(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(
        char for char in folded if unicodedata.category(char) != "Mn"
    )
    return " ".join(folded.replace("đ", "d").split())


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_categories(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            category_id,
            category_name
        FROM catalog.category
    """
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        name = normalize_text(row.get("category_name"))
        if name and name not in result:
            result[name] = row
    return result


def fetch_size_charts(connection: psycopg.Connection) -> list[dict]:
    query = """
        SELECT
            size_chart_id,
            chart_name,
            product_line_id
        FROM catalog.size_chart
        ORDER BY size_chart_id
    """
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def fetch_line_categories(connection: psycopg.Connection) -> dict[int, list[int]]:
    query = """
        SELECT
            product_line_id,
            category_id,
            is_primary
        FROM catalog.line_category
        ORDER BY product_line_id, is_primary DESC, category_id
    """
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    result: dict[int, list[int]] = {}
    for row in rows:
        product_line_id = row.get("product_line_id")
        category_id = row.get("category_id")
        if product_line_id is None or category_id is None:
            continue
        result.setdefault(int(product_line_id), [])
        if int(category_id) not in result[int(product_line_id)]:
            result[int(product_line_id)].append(int(category_id))
    return result


def fetch_existing_size_chart_categories(
    connection: psycopg.Connection,
) -> set[tuple[int, int]]:
    query = """
        SELECT
            size_chart_id,
            category_id
        FROM catalog.size_chart_category
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return {tuple(map(int, row)) for row in cursor.fetchall()}


def infer_category_names_for_chart(
    chart_name: str,
    categories_by_name: dict[str, dict],
) -> list[str]:
    folded = fold_text(chart_name)
    available_names = list(categories_by_name.keys())

    if "ao dai nam" in folded:
        preferred = ["Áo dài", "Áo dài cưới nam"]
        return [name for name in preferred if name in categories_by_name]

    if "ao dai nu" in folded or "ao dai" in folded:
        return [
            name
            for name in available_names
            if name.startswith("Áo dài") and name != "Áo dài cưới nam"
        ]

    if "vay" in folded or "dam" in folded:
        preferred_prefixes = ("Đầm",)
        inferred = [
            name for name in available_names if name.startswith(preferred_prefixes)
        ]
        if "Chân váy" in categories_by_name:
            inferred.append("Chân váy")
        return inferred

    return []


def insert_size_chart_category_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.size_chart_category (
            size_chart_id,
            category_id
        )
        VALUES (
            %(size_chart_id)s,
            %(category_id)s
        )
    """
    with connection.cursor() as cursor:
        cursor.executemany(query, records)
    return len(records)


def sync_size_chart_categories(
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        categories_by_name = fetch_categories(connection)
        size_charts = fetch_size_charts(connection)
        line_categories_by_product_line = fetch_line_categories(connection)
        existing_pairs = fetch_existing_size_chart_categories(connection)

        inserts: list[dict] = []
        skipped_count = 0
        unresolved_charts: list[str] = []

        for chart in size_charts:
            size_chart_id = int(chart["size_chart_id"])
            product_line_id = chart.get("product_line_id")
            chart_name = normalize_text(chart.get("chart_name")) or ""

            category_ids: list[int] = []
            if product_line_id is not None:
                category_ids = line_categories_by_product_line.get(int(product_line_id), [])
            else:
                inferred_names = infer_category_names_for_chart(
                    chart_name=chart_name,
                    categories_by_name=categories_by_name,
                )
                category_ids = [
                    int(categories_by_name[name]["category_id"])
                    for name in inferred_names
                    if name in categories_by_name
                ]

            if not category_ids:
                unresolved_charts.append(chart_name)
                continue

            for category_id in category_ids:
                pair = (size_chart_id, category_id)
                if pair in existing_pairs:
                    skipped_count += 1
                    continue

                inserts.append(
                    {
                        "size_chart_id": size_chart_id,
                        "category_id": category_id,
                    }
                )
                existing_pairs.add(pair)

        if unresolved_charts:
            raise ValueError(
                "Unable to infer categories for size charts: "
                f"{sorted(unresolved_charts)}"
            )

        inserted_count = 0
        for batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_size_chart_category_batch(connection, batch)

        connection.commit()

    return inserted_count, skipped_count


def print_summary(
    connection_label: str,
    inserted_count: int,
    skipped_count: int,
) -> None:
    print(f"Target database: {connection_label}")
    print(f"Inserted size_chart_category rows: {inserted_count}")
    print(f"Skipped existing rows: {skipped_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assign matching categories to catalog.size_chart via catalog.size_chart_category."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    inserted_count, skipped_count = sync_size_chart_categories(connection_kwargs)
    print_summary(
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
