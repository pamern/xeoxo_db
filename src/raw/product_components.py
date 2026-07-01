from datetime import datetime
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://xeoxo.com"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

INPUT_FILE = STAGING_DIR / "product_lines.csv"
OUTPUT_FILE = RAW_DIR / "product_components.csv"
FAILED_FILE = LOG_DIR / "failed_urls.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def normalize_text(text: object) -> str | None:
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
    normalized = normalized.replace("\u0111", "d")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def parse_price(value: str | None) -> int | None:
    normalized = normalize_text(value)
    if not normalized:
        return None

    digits = "".join(char for char in normalized if char.isdigit())
    return int(digits) if digits else None


def safe_log_text(text: str | None) -> str:
    value = normalize_text(text) or ""
    return value.encode("ascii", errors="ignore").decode("ascii")


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def infer_component_type(name: str | None) -> str:
    normalized_name = normalize_key(name)

    if normalized_name.startswith("set"):
        return "SET"
    if normalized_name.startswith("ao choang"):
        return "AO"
    if normalized_name.startswith("ao dai") or normalized_name.startswith("ad "):
        return "AO"
    if normalized_name.startswith("ao"):
        return "AO"
    if normalized_name.startswith("quan"):
        return "QUAN"
    if normalized_name.startswith("chan vay") or normalized_name.startswith("vay"):
        return "VAY"
    if normalized_name.startswith("dam"):
        return "DAM"
    if normalized_name.startswith("yem"):
        return "YEM"

    return "KHAC"


def clean_component_name(name: str | None) -> str | None:
    value = normalize_text(name)
    if not value:
        return None

    value = re.sub(r"\d[\d\.\,]*\s*VND.*$", "", value, flags=re.IGNORECASE)
    normalized_value = normalize_key(value)
    marker = normalized_value.find("chon mot tuy chon")
    if marker >= 0:
        value = value[:marker]

    value = normalize_text(value)
    return value


def extract_source_component_product_id(item) -> str | None:
    for attr in ["data-id", "data-product_id", "data-product-id", "value"]:
        value = item.get(attr)
        if value and str(value).isdigit():
            return str(value)

    input_tag = item.select_one(
        "input[name*='woosg'], input[name*='grouped'], input[value]"
    )
    if input_tag:
        value = input_tag.get("value")
        if value and str(value).isdigit():
            return str(value)

    return None


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


def extract_product_components(
    soup: BeautifulSoup,
    product_line: dict,
) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()

    selectors = [
        ".woosg-products .woosg-product",
        ".woosg-wrap .woosg-product",
        ".woosg-product",
        ".woosg-item",
        ".grouped_form tr",
        ".woocommerce-grouped-product-list-item",
    ]

    candidates = []
    for selector in selectors:
        candidates.extend(soup.select(selector))

    for item in candidates:
        item_text = normalize_text(item.get_text(" ", strip=True))
        if not item_text:
            continue

        link_tag = item.select_one(
            ".woosg-title a[href], "
            ".woosg-name a[href], "
            ".product-title a[href], "
            "a[href]"
        )
        component_url = urljoin(BASE_URL, link_tag["href"]) if link_tag else None

        name_tag = item.select_one(
            ".woosg-title, "
            ".woosg-name, "
            ".woocommerce-grouped-product-list-item__label, "
            ".product-title"
        )
        if name_tag:
            component_name = normalize_text(name_tag.get_text(" ", strip=True))
        elif link_tag:
            component_name = normalize_text(link_tag.get_text(" ", strip=True))
        else:
            component_name = item_text

        component_name = clean_component_name(component_name)
        if not component_name:
            continue

        price_tag = item.select_one(
            ".woosg-price .amount, "
            ".price .amount, "
            ".amount, "
            ".price"
        )
        component_price_text = (
            normalize_text(price_tag.get_text(" ", strip=True))
            if price_tag
            else None
        )
        source_component_product_id = extract_source_component_product_id(item)

        key = (component_name, component_url, source_component_product_id)
        if key in seen:
            continue
        seen.add(key)

        rows.append(
            {
                "parent_line_name": normalize_text(product_line.get("product_name")),
                "parent_product_url": normalize_text(product_line.get("product_url")),
                "component_order": len(rows) + 1,
                "source_component_product_id": source_component_product_id,
                "component_name": component_name,
                "component_url": component_url,
                "component_price_text": component_price_text,
                "component_price": parse_price(component_price_text),
                "component_type": infer_component_type(component_name),
                "is_required": True,
                "crawl_at": normalize_text(product_line.get("crawl_at")),
            }
        )

    if rows:
        return rows

    product_name = normalize_text(product_line.get("product_name"))
    product_url = normalize_text(product_line.get("product_url"))
    product_price_text = normalize_text(product_line.get("price"))

    return [
        {
            "parent_line_name": product_name,
            "parent_product_url": product_url,
            "component_order": 1,
            "source_component_product_id": None,
            "component_name": product_name,
            "component_url": product_url,
            "component_price_text": product_price_text,
            "component_price": parse_price(product_price_text),
            "component_type": infer_component_type(product_name),
            "is_required": True,
            "crawl_at": normalize_text(product_line.get("crawl_at")),
        }
    ]


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
            f"[{index}/{len(product_lines)}] Extracting components: "
            f"{safe_log_text(product_name)}"
        )

        try:
            if not product_url:
                raise ValueError("Missing product_url")

            html = fetch_html(product_url)
            soup = BeautifulSoup(html, "lxml")
            component_rows = extract_product_components(soup, row)

            for component_row in component_rows:
                if not component_row.get("crawl_at"):
                    component_row["crawl_at"] = crawl_at
                rows.append(component_row)
        except Exception as exc:
            failed_rows.append(
                {
                    "source": "extract_product_components",
                    "collection_name": row.get("collection_name"),
                    "url": product_url,
                    "error_type": type(exc).__name__,
                    "status_code": getattr(
                        getattr(exc, "response", None),
                        "status_code",
                        None,
                    ),
                    "error": str(exc),
                    "crawl_at": crawl_at,
                }
            )

    components_df = pd.DataFrame(rows)
    failed_df = pd.DataFrame(failed_rows)

    if not components_df.empty:
        components_df = components_df.drop_duplicates(
            subset=[
                "parent_product_url",
                "component_order",
                "component_name",
                "component_url",
                "source_component_product_id",
            ]
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
        "source_component_product_id",
        "component_name",
        "component_url",
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
        for column in component_columns:
            if column not in components_df.columns:
                components_df[column] = None
        components_df = components_df[component_columns]

    if failed_df.empty:
        failed_df = pd.DataFrame(columns=failed_columns)
    else:
        for column in failed_columns:
            if column not in failed_df.columns:
                failed_df[column] = None
        failed_df = failed_df[failed_columns]

    components_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    failed_df.to_csv(FAILED_FILE, index=False, encoding="utf-8-sig")

    print(f"\nCreated file: {OUTPUT_FILE}")
    print(f"Total product components: {len(components_df)}")
    print(f"\nFailed rows saved to: {FAILED_FILE}")
    print(f"Total failed rows: {len(failed_df)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    save_raw_product_components()
