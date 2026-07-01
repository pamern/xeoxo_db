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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "product_variant.csv"
BATCH_SIZE = 500

ALLOWED_STATUSES = {
    "ACTIVE",
    "INACTIVE",
    "OUT_OF_STOCK",
    "COMING_SOON",
    "PREORDER",
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


def normalize_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None

    text = normalize_text(value)
    if not text:
        return None

    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer value: {value!r}") from exc


def normalize_decimal(value: object) -> Decimal:
    text = normalize_text(value)
    if text is None:
        raise ValueError("price must not be null")

    try:
        price = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc

    if price < 0:
        raise ValueError(f"price must be >= 0, got {price}")

    return price


def normalize_status(value: object) -> str:
    status = normalize_text(value)
    if not status:
        return "ACTIVE"

    normalized = status.upper()
    if normalized not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status: {status!r}. Expected one of {sorted(ALLOWED_STATUSES)}"
        )

    return normalized


def read_master_product_variants(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "sku",
        "product_line_id",
        "component_order",
        "chart_name",
        "size_name",
        "price",
        "status",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    for column in ["sku", "chart_name", "size_name", "status"]:
        working_df[column] = working_df[column].map(normalize_text)

    working_df["product_line_id"] = working_df["product_line_id"].map(normalize_int)
    working_df["component_order"] = working_df["component_order"].map(normalize_int)
    working_df["price"] = working_df["price"].map(normalize_decimal)
    working_df["status"] = working_df["status"].map(normalize_status)

    working_df = working_df.dropna(subset=["sku", "product_line_id", "component_order"])
    working_df = (
        working_df.sort_values(
            by=["product_line_id", "component_order", "size_name", "sku"],
            kind="stable",
        )
        .drop_duplicates(subset=["sku"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "sku",
            "product_line_id",
            "component_order",
            "chart_name",
            "size_name",
            "price",
            "status",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_components(
    connection: psycopg.Connection,
) -> dict[tuple[int, int], dict]:
    query = """
        SELECT
            component_id,
            product_line_id,
            display_order
        FROM catalog.product_component
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    components_by_key: dict[tuple[int, int], dict] = {}
    for row in rows:
        product_line_id = row.get("product_line_id")
        display_order = row.get("display_order")
        if product_line_id is None or display_order is None:
            continue

        key = (int(product_line_id), int(display_order))
        if key not in components_by_key:
            components_by_key[key] = row

    return components_by_key


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

    size_options_by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        chart_name = normalize_text(row.get("chart_name"))
        size_name = normalize_text(row.get("size_name"))
        if not chart_name or not size_name:
            continue

        key = (chart_name, size_name)
        if key not in size_options_by_key:
            size_options_by_key[key] = row

    return size_options_by_key


def fetch_existing_product_variants(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            variant_id,
            sku,
            component_id,
            size_option_id,
            price,
            status
        FROM catalog.product_variant
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    variants_by_sku: dict[str, dict] = {}
    for row in rows:
        sku = normalize_text(row.get("sku"))
        if sku and sku not in variants_by_sku:
            variants_by_sku[sku] = row

    return variants_by_sku


def build_product_variant_payload(
    row: dict,
    component_id: int,
    size_option_id: int | None,
) -> dict:
    return {
        "sku": normalize_text(row["sku"]),
        "component_id": component_id,
        "size_option_id": size_option_id,
        "price": normalize_decimal(row["price"]),
        "status": normalize_status(row["status"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"component_id", "size_option_id", "price"}:
            existing_value = existing.get(key)
            incoming_value = value
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_product_variant_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.product_variant (
            sku,
            component_id,
            size_option_id,
            price,
            status
        )
        VALUES (
            %(sku)s,
            %(component_id)s,
            %(size_option_id)s,
            %(price)s,
            %(status)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_product_variant(
    connection: psycopg.Connection,
    variant_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.product_variant
        SET {assignments}, updated_at = NOW()
        WHERE variant_id = %(variant_id)s
    """

    params = dict(update_payload)
    params["variant_id"] = variant_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_product_variants(product_variants_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        components_by_key = fetch_existing_components(connection)
        size_options_by_key = fetch_existing_size_options(connection)
        existing_variants = fetch_existing_product_variants(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_components: list[tuple[str, int, int]] = []
        unresolved_size_options: list[tuple[str, str, str]] = []

        for record in product_variants_df.to_dict(orient="records"):
            sku = normalize_text(record["sku"])
            product_line_id = normalize_int(record["product_line_id"])
            component_order = normalize_int(record["component_order"])
            chart_name = normalize_text(record["chart_name"])
            size_name = normalize_text(record["size_name"])

            component = (
                components_by_key.get((product_line_id, component_order))
                if product_line_id is not None and component_order is not None
                else None
            )
            if component is None:
                unresolved_components.append(
                    (sku or "", product_line_id or 0, component_order or 0)
                )
                continue

            size_option_id = None
            if chart_name and size_name:
                size_option = size_options_by_key.get((chart_name, size_name))
                if size_option is None:
                    unresolved_size_options.append(
                        (sku or "", chart_name, size_name)
                    )
                    continue
                size_option_id = size_option["size_option_id"]

            payload = build_product_variant_payload(
                row=record,
                component_id=component["component_id"],
                size_option_id=size_option_id,
            )
            existing = existing_variants.get(payload["sku"])

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["variant_id"], update_payload))

        if unresolved_components:
            raise ValueError(
                "Unable to resolve component_id for product variants: "
                f"{sorted(unresolved_components)}"
            )

        if unresolved_size_options:
            raise ValueError(
                "Unable to resolve size_option_id for product variants: "
                f"{sorted(unresolved_size_options)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_product_variant_batch(connection, insert_batch)

        for variant_id, update_payload in updates:
            update_product_variant(connection, variant_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(product_variants_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    product_variants_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master product variants: {len(product_variants_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not product_variants_df.empty:
        preview_df = product_variants_df.copy()
        preview_df["chart_name"] = preview_df["chart_name"].fillna("")
        preview_df["size_name"] = preview_df["size_name"].fillna("")
        print("\nPreview:")
        print(preview_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    product_variants_df = read_master_product_variants(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_product_variants(
        product_variants_df
    )
    print_summary(
        product_variants_df=product_variants_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
