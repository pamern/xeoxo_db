from __future__ import annotations

from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd

if str(PROJECT_ROOT := Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection_db import get_postgres_connection_kwargs

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


RAW_COMPONENTS_FILE = PROJECT_ROOT / "data" / "raw" / "product_components.csv"
MASTER_PRODUCT_LINE_FILE = PROJECT_ROOT / "data" / "master" / "product_line.csv"
MASTER_SIZE_OPTION_FILE = PROJECT_ROOT / "data" / "master" / "size_option.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "product_variant.csv"

REQUIRED_COMPONENT_COLUMNS = {
    "parent_line_name",
    "parent_product_url",
    "component_order",
    "component_name",
    "component_price",
    "component_type",
}
REQUIRED_SIZE_OPTION_COLUMNS = {
    "chart_name",
    "size_name",
    "display_order",
}

FEMALE_AO_DAI_CHART = "Bảng size áo dài nữ XÉO XỌ"
MALE_AO_DAI_CHART = "Bảng size áo dài nam XÉO XỌ"
DRESS_CHART = "Bảng size váy XÉO XỌ"


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"null", "n/a", "na", "none", "nan"}:
        return None

    return text


def normalize_number(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None

    text = normalize_text(value)
    if text is None:
        return None

    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def normalize_key(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    normalized = unicodedata.normalize("NFD", text.lower())
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.replace("\u0111", "d")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())

def read_components(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    missing_columns = REQUIRED_COMPONENT_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    for column in [
        "parent_line_name",
        "parent_product_url",
        "component_name",
        "component_type",
    ]:
        working_df[column] = working_df[column].map(normalize_text)

    working_df["component_order"] = working_df["component_order"].map(normalize_number)
    working_df["component_price"] = working_df["component_price"].map(normalize_number)

    working_df = working_df.dropna(
        subset=[
            "parent_line_name",
            "parent_product_url",
            "component_name",
            "component_order",
            "component_price",
        ]
    )
    working_df = (
        working_df.sort_values(
            by=["parent_line_name", "component_order", "component_name"],
            kind="stable",
        )
        .drop_duplicates(
            subset=["parent_product_url", "component_order", "component_name"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return working_df


def read_master_product_lines(input_file: Path) -> dict[str, dict]:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {"collection_name", "line_name", "description", "design_style"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    lookup: dict[str, dict] = {}
    for record in df.to_dict(orient="records"):
        line_name = normalize_text(record.get("line_name"))
        if not line_name:
            continue

        lookup[line_name] = {
            "collection_name": normalize_text(record.get("collection_name")),
            "description": normalize_text(record.get("description")),
            "design_style": normalize_text(record.get("design_style")),
        }

    return lookup


def read_size_options(input_file: Path) -> dict[str, list[dict]]:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    missing_columns = REQUIRED_SIZE_OPTION_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["chart_name"] = working_df["chart_name"].map(normalize_text)
    working_df["size_name"] = working_df["size_name"].map(normalize_text)
    working_df["display_order"] = working_df["display_order"].map(normalize_number)
    working_df = working_df.dropna(subset=["chart_name", "size_name", "display_order"])

    size_options_by_chart: dict[str, list[dict]] = {}
    for record in working_df.to_dict(orient="records"):
        chart_name = record["chart_name"]
        size_options_by_chart.setdefault(chart_name, []).append(
            {
                "size_name": record["size_name"],
                "display_order": record["display_order"],
            }
        )

    for chart_name in size_options_by_chart:
        size_options_by_chart[chart_name] = sorted(
            size_options_by_chart[chart_name],
            key=lambda item: (item["display_order"], item["size_name"]),
        )

    return size_options_by_chart


def fetch_existing_product_lines() -> dict[tuple[str, str], dict]:
    connection_kwargs = get_postgres_connection_kwargs()
    query = """
        SELECT
            pl.product_line_id,
            pl.line_name,
            c.collection_name
        FROM catalog.product_line pl
        INNER JOIN catalog.collection c
            ON c.collection_id = pl.collection_id
    """

    with psycopg.connect(**connection_kwargs) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    product_lines_by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        collection_name = normalize_text(row.get("collection_name"))
        line_name = normalize_text(row.get("line_name"))
        product_line_id = row.get("product_line_id")
        if not collection_name or not line_name or product_line_id is None:
            continue

        key = (collection_name, line_name)
        if key not in product_lines_by_key:
            product_lines_by_key[key] = row

    return product_lines_by_key


def is_male_ao_dai_context(
    parent_line_name: str | None,
    component_name: str | None,
    product_line_info: dict | None,
) -> bool:
    texts = [
        normalize_key(parent_line_name),
        normalize_key(component_name),
        normalize_key(product_line_info.get("description") if product_line_info else None),
        normalize_key(product_line_info.get("design_style") if product_line_info else None),
    ]

    return any("ao dai nam" in text for text in texts if text)


def infer_chart_name(
    parent_line_name: str | None,
    component_name: str | None,
    component_type: str | None,
    product_line_info: dict | None,
) -> str | None:
    parent_key = normalize_key(parent_line_name)
    component_key = normalize_key(component_name)
    component_type_key = normalize_key(component_type)

    if is_male_ao_dai_context(parent_line_name, component_name, product_line_info):
        return MALE_AO_DAI_CHART

    if "ao dai" in parent_key or "ao dai" in component_key:
        return FEMALE_AO_DAI_CHART

    if component_type_key == "dam":
        return DRESS_CHART

    if "dam" in parent_key or "dam" in component_key:
        return DRESS_CHART

    if "chan vay" in parent_key or "chan vay" in component_key:
        return DRESS_CHART

    return None


def build_sku(
    product_line_id: int,
    component_order: int,
    size_name: str | None,
) -> str:
    size_token = normalize_text(size_name) or "OS"
    return f"XV-PL{int(product_line_id):03d}-C{component_order:02d}-{size_token.upper()}"


def build_master_product_variant(
    components_df: pd.DataFrame,
    product_line_lookup: dict[str, dict],
    size_options_by_chart: dict[str, list[dict]],
    existing_product_lines: dict[tuple[str, str], dict],
) -> pd.DataFrame:
    rows: list[dict] = []
    unresolved_product_lines: list[tuple[str, str]] = []

    for record in components_df.to_dict(orient="records"):
        parent_line_name = record["parent_line_name"]
        component_name = record["component_name"]
        component_type = record["component_type"]
        component_price = record["component_price"]
        component_order = int(record["component_order"])

        product_line_info = product_line_lookup.get(parent_line_name)
        collection_name = (
            normalize_text(product_line_info.get("collection_name"))
            if product_line_info
            else None
        )
        product_line = (
            existing_product_lines.get((collection_name, parent_line_name))
            if collection_name and parent_line_name
            else None
        )
        if product_line is None:
            unresolved_product_lines.append((collection_name or "", parent_line_name or ""))
            continue

        product_line_id = int(product_line["product_line_id"])
        chart_name = infer_chart_name(
            parent_line_name=parent_line_name,
            component_name=component_name,
            component_type=component_type,
            product_line_info=product_line_info,
        )
        size_options = size_options_by_chart.get(chart_name, []) if chart_name else []

        if not size_options:
            rows.append(
                {
                    "sku": build_sku(
                        product_line_id=product_line_id,
                        component_order=component_order,
                        size_name=None,
                    ),
                    "product_line_id": product_line_id,
                    "parent_line_name": parent_line_name,
                    "component_order": component_order,
                    "component_name": component_name,
                    "chart_name": None,
                    "size_name": None,
                    "price": component_price,
                    "status": "ACTIVE",
                }
            )
            continue

        for size_option in size_options:
            rows.append(
                {
                    "sku": build_sku(
                        product_line_id=product_line_id,
                        component_order=component_order,
                        size_name=size_option["size_name"],
                    ),
                    "product_line_id": product_line_id,
                    "parent_line_name": parent_line_name,
                    "component_order": component_order,
                    "component_name": component_name,
                    "chart_name": chart_name,
                    "size_name": size_option["size_name"],
                    "price": component_price,
                    "status": "ACTIVE",
                }
            )

    if unresolved_product_lines:
        raise ValueError(
            "Unable to resolve product_line_id for product variants: "
            f"{sorted(set(unresolved_product_lines))}"
        )

    master_df = pd.DataFrame(rows)
    if master_df.empty:
        return pd.DataFrame(
            columns=[
                "sku",
                "product_line_id",
                "parent_line_name",
                "component_order",
                "component_name",
                "chart_name",
                "size_name",
                "price",
                "status",
            ]
        )

    master_df = (
        master_df.sort_values(
            by=["parent_line_name", "component_order", "component_name", "size_name", "sku"],
            kind="stable",
        )
        .drop_duplicates(subset=["sku"], keep="first")
        .reset_index(drop=True)
    )

    return master_df


def save_master_product_variant(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print(f"Created file: {output_file}")
    print(f"Total master product variants: {len(df)}")

    if not df.empty:
        print("\nPreview:")
        print(df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    components_df = read_components(RAW_COMPONENTS_FILE)
    product_line_lookup = read_master_product_lines(MASTER_PRODUCT_LINE_FILE)
    size_options_by_chart = read_size_options(MASTER_SIZE_OPTION_FILE)
    existing_product_lines = fetch_existing_product_lines()

    master_df = build_master_product_variant(
        components_df=components_df,
        product_line_lookup=product_line_lookup,
        size_options_by_chart=size_options_by_chart,
        existing_product_lines=existing_product_lines,
    )
    save_master_product_variant(master_df, OUTPUT_FILE)
    print_summary(master_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()
