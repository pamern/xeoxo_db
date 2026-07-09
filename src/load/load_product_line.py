# IMPORTANCE: Cấm chạy lại cái file này. 

from __future__ import annotations

from pathlib import Path
import re
import sys
import unicodedata

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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "product_line.csv"
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


def normalize_status(value: object) -> str:
    status = normalize_text(value)
    if not status:
        return "ACTIVE"

    return status.upper()


def normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value

    text = normalize_text(value)
    if text is None:
        return False

    return text.lower() in {"true", "1", "yes", "y"}


def build_slug(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None

    normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    slug = re.sub(r"[^a-z0-9]+", "-", without_accents).strip("-")
    return slug or None


def read_master_product_lines(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "collection_name",
        "color_name",
        "line_name",
        "description",
        "material_name",
        "design_style",
        "features",
        "usage_context",
        "status",
        "is_featured",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    if "slug" not in working_df.columns:
        working_df["slug"] = None

    for column in [
        "collection_name",
        "color_name",
        "line_name",
        "description",
        "material_name",
        "design_style",
        "features",
        "usage_context",
        "status",
    ]:
        working_df[column] = working_df[column].map(normalize_text)

    working_df["slug"] = working_df["slug"].map(normalize_text)
    working_df["status"] = working_df["status"].map(normalize_status)
    working_df["is_featured"] = working_df["is_featured"].map(normalize_bool)
    working_df["slug"] = working_df.apply(
        lambda row: normalize_text(row["slug"]) or build_slug(row["line_name"]),
        axis=1,
    )

    working_df = working_df.dropna(
        subset=["collection_name", "line_name", "slug"]
    )
    working_df = (
        working_df.sort_values(
            by=["collection_name", "line_name", "slug", "material_name"],
            kind="stable",
        )
        .drop_duplicates(subset=["collection_name", "line_name", "slug"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "collection_name",
            "color_name",
            "line_name",
            "slug",
            "description",
            "material_name",
            "design_style",
            "features",
            "usage_context",
            "status",
            "is_featured",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_collections(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            collection_id,
            collection_name
        FROM catalog.collection
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        collection_name = normalize_text(row.get("collection_name"))
        if collection_name and collection_name not in existing_by_name:
            existing_by_name[collection_name] = row

    return existing_by_name


def fetch_existing_colors(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            color_id,
            color_name
        FROM catalog.color
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        color_name = normalize_text(row.get("color_name"))
        if color_name and color_name not in existing_by_name:
            existing_by_name[color_name] = row

    return existing_by_name


def fetch_existing_materials(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            material_id,
            material_name
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


def fetch_existing_product_lines(connection: psycopg.Connection) -> dict[tuple[int, str], dict]:
    query = """
        SELECT
            product_line_id,
            collection_id,
            color_id,
            line_name,
            slug,
            description,
            material_id,
            design_style,
            features,
            usage_context,
            status,
            is_featured
        FROM catalog.product_line
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[int, str], dict] = {}
    for row in rows:
        collection_id = row.get("collection_id")
        line_name = normalize_text(row.get("line_name"))
        if collection_id is None or not line_name:
            continue

        key = (collection_id, line_name)
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def build_product_line_payload(
    row: dict,
    collection_id: int,
    color_id: int | None,
    material_id: int,
) -> dict:
    return {
        "collection_id": collection_id,
        "color_id": color_id,
        "line_name": normalize_text(row["line_name"]),
        "slug": normalize_text(row.get("slug")) or build_slug(row["line_name"]),
        "description": normalize_text(row["description"]),
        "material_id": material_id,
        "design_style": normalize_text(row["design_style"]),
        "features": normalize_text(row["features"]),
        "usage_context": normalize_text(row["usage_context"]),
        "status": normalize_status(row["status"]),
        "is_featured": normalize_bool(row["is_featured"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"collection_id", "color_id", "material_id", "is_featured"}:
            existing_value = existing.get(key)
            incoming_value = value
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_product_line_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.product_line (
            collection_id,
            color_id,
            line_name,
            slug,
            description,
            material_id,
            design_style,
            features,
            usage_context,
            status,
            is_featured
        )
        VALUES (
            %(collection_id)s,
            %(color_id)s,
            %(line_name)s,
            %(slug)s,
            %(description)s,
            %(material_id)s,
            %(design_style)s,
            %(features)s,
            %(usage_context)s,
            %(status)s,
            %(is_featured)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_product_line(
    connection: psycopg.Connection,
    product_line_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.product_line
        SET {assignments}, updated_at = NOW()
        WHERE product_line_id = %(product_line_id)s
    """

    params = dict(update_payload)
    params["product_line_id"] = product_line_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_product_lines(product_lines_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        collections_by_name = fetch_existing_collections(connection)
        colors_by_name = fetch_existing_colors(connection)
        materials_by_name = fetch_existing_materials(connection)
        existing_product_lines = fetch_existing_product_lines(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_collections: list[tuple[str, str]] = []
        unresolved_materials: list[tuple[str, str]] = []
        unresolved_colors: list[tuple[str, str]] = []

        for record in product_lines_df.to_dict(orient="records"):
            collection_name = normalize_text(record["collection_name"])
            material_name = normalize_text(record["material_name"])
            color_name = normalize_text(record["color_name"])
            line_name = normalize_text(record["line_name"])

            collection = collections_by_name.get(collection_name)
            if collection is None:
                unresolved_collections.append((collection_name, line_name))
                continue

            material = None
            if material_name:
                material = materials_by_name.get(material_name)
            if material_name and material is None:
                unresolved_materials.append((material_name, line_name))
                continue

            color = None
            if color_name:
                color = colors_by_name.get(color_name)
                if color is None:
                    unresolved_colors.append((color_name, line_name))
                    continue

            payload = build_product_line_payload(
                row=record,
                collection_id=collection["collection_id"],
                color_id=color["color_id"] if color else None,
                material_id=material["material_id"] if material else None,
            )

            key = (payload["collection_id"], payload["line_name"])
            existing = existing_product_lines.get(key)
            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["product_line_id"], update_payload))

        if unresolved_collections:
            raise ValueError(
                "Unable to resolve collection_id for product lines: "
                f"{sorted(unresolved_collections)}"
            )

        if unresolved_materials:
            raise ValueError(
                "Unable to resolve material_id for product lines: "
                f"{sorted(unresolved_materials)}"
            )

        if unresolved_colors:
            raise ValueError(
                "Unable to resolve color_id for product lines: "
                f"{sorted(unresolved_colors)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_product_line_batch(connection, insert_batch)

        for product_line_id, update_payload in updates:
            update_product_line(connection, product_line_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(product_lines_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    product_lines_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master product lines: {len(product_lines_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not product_lines_df.empty:
        preview_df = product_lines_df.copy()
        preview_df["color_name"] = preview_df["color_name"].fillna("")
        print("\nPreview:")
        print(preview_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    product_lines_df = read_master_product_lines(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_product_lines(product_lines_df)
    print_summary(
        product_lines_df=product_lines_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
