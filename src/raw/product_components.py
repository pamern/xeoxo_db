from datetime import datetime
from pathlib import Path
import re
import unicodedata

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

INPUT_FILE = STAGING_DIR / "product_lines.csv"
OUTPUT_FILE = RAW_DIR / "product_components.csv"
FAILED_FILE = LOG_DIR / "failed_urls.csv"


def normalize_text(text: str | None) -> str | None:
    if text is None or pd.isna(text):
        return None

    value = " ".join(str(text).split()).strip()
    return value or None


def normalize_key(text: str | None) -> str:
    value = normalize_text(text)

    if not value:
        return ""

    normalized = unicodedata.normalize("NFD", value.lower())
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def parse_price(value: str | None) -> int | None:
    normalized_value = normalize_text(value)

    if not normalized_value:
        return None

    digits = "".join(char for char in normalized_value if char.isdigit())
    return int(digits) if digits else None


def safe_log_text(text: str | None) -> str:
    value = normalize_text(text) or ""
    return value.encode("ascii", errors="ignore").decode("ascii")


def extract_component(name: str | None) -> tuple[str | None, str | None]:
    normalized_name = normalize_key(name)

    if normalized_name.startswith("set"):
        return "Set", "SET"

    if normalized_name.startswith("ao choang"):
        return "Ao choang", "AO"

    if normalized_name.startswith("ao dai"):
        return "Ao dai", "AO"

    if normalized_name.startswith("ao"):
        return "Ao", "AO"

    if normalized_name.startswith("quan"):
        return "Quan", "QUAN"

    if normalized_name.startswith("dam"):
        return "Dam", "DAM"

    if normalized_name.startswith("chan vay"):
        return "Chan vay", "VAY"

    if normalized_name.startswith("vay"):
        return "Vay", "VAY"

    if normalized_name.startswith("yem"):
        return "Yem", "YEM"

    return normalize_text(name), "KHAC"


def load_product_lines() -> list[dict]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE, dtype=str)

    required_columns = {"product_name", "product_url"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns in {INPUT_FILE}: {sorted(missing_columns)}"
        )

    df = df.dropna(subset=["product_name", "product_url"])
    df = df.drop_duplicates(subset=["product_url"]).reset_index(drop=True)

    return df.to_dict("records")


def build_component_rows(
    product_lines: list[dict],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    failed_rows: list[dict] = []

    for index, row in enumerate(product_lines, start=1):
        product_name = normalize_text(row.get("product_name"))
        product_url = normalize_text(row.get("product_url"))
        crawl_at = (
            normalize_text(row.get("crawl_at"))
            or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        print(
            f"[{index}/{len(product_lines)}] Building component: "
            f"{safe_log_text(product_name)}"
        )

        try:
            component_name, component_type = extract_component(product_name)

            rows.append(
                {
                    "parent_line_name": product_name,
                    "parent_product_url": product_url,
                    "component_order": 1,
                    "component_name": component_name,
                    "component_price_text": normalize_text(row.get("price")),
                    "component_price": parse_price(row.get("price")),
                    "component_type": component_type,
                    "is_required": True,
                    "crawl_at": crawl_at,
                }
            )
        except Exception as exc:
            failed_rows.append(
                {
                    "source": "build_component_rows",
                    "collection_name": row.get("collection_name"),
                    "url": product_url,
                    "error_type": type(exc).__name__,
                    "status_code": None,
                    "error": str(exc),
                    "crawl_at": crawl_at,
                }
            )

    components_df = pd.DataFrame(rows)
    failed_df = pd.DataFrame(failed_rows)

    if not components_df.empty:
        components_df = components_df.drop_duplicates(
            subset=["parent_product_url", "component_name", "component_type"]
        ).reset_index(drop=True)

    return components_df, failed_df


def save_raw_product_components() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    product_lines = load_product_lines()
    components_df, failed_df = build_component_rows(product_lines)

    component_columns = [
        "parent_line_name",
        "parent_product_url",
        "component_order",
        "component_name",
        "component_price_text",
        "component_price",
        "component_type",
        "is_required",
        "crawl_at",
    ]
    failed_columns = [
        "source",
        "collection_name",
        "url",
        "error_type",
        "status_code",
        "error",
        "crawl_at",
    ]

    if components_df.empty:
        components_df = pd.DataFrame(columns=component_columns)
    else:
        components_df = components_df[component_columns]

    if failed_df.empty:
        failed_df = pd.DataFrame(columns=failed_columns)
    else:
        failed_df = failed_df[failed_columns]

    components_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    failed_df.to_csv(FAILED_FILE, index=False, encoding="utf-8-sig")

    print(f"\nCreated file: {OUTPUT_FILE}")
    print(f"Total product components: {len(components_df)}")
    print(f"\nFailed rows saved to: {FAILED_FILE}")
    print(f"Total failed rows: {len(failed_df)}")

if __name__ == "__main__":
    save_raw_product_components()
