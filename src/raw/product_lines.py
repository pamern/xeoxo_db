import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.utils.loggers import get_logger
from src.utils.normalizers import (
    normalize_label,
    normalize_price,
    normalize_text,
)


# ==================================================
# CONFIG
# ==================================================

BASE_URL = "https://xeoxo.com"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

INPUT_FILE = RAW_DIR / "product_url.csv"
OUTPUT_FILE = RAW_DIR / "product_lines.csv"

logger = get_logger(__name__)


# ==================================================
# HELPERS
# ==================================================


def fetch_html(url: str) -> str:
    logger.info("Fetching HTML from %s", url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    logger.info("Fetched HTML successfully from %s", url)

    return response.text


def extract_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        tag = soup.select_one(selector)

        if not tag:
            continue

        text = normalize_text(tag.get_text(" ", strip=True))

        if text:
            return text

    return ""


def extract_html_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        tag = soup.select_one(selector)

        if not tag:
            continue

        text = normalize_text(tag.get_text("\n", strip=True))

        if text:
            return text

    return ""


def extract_product_type(soup: BeautifulSoup) -> str:
    form = soup.select_one("form.cart")

    if form:
        classes = form.get("class", [])

        for cls in classes:
            if cls.startswith("variations_form"):
                return "VARIABLE"

    body = soup.select_one("body")

    if body:
        classes = body.get("class", [])

        for cls in classes:
            if cls.startswith("postid-"):
                continue
            if cls.startswith("product-template"):
                continue

    variation_table = soup.select_one("form.variations_form")

    if variation_table:
        return "VARIABLE"

    grouped_form = soup.select_one("form.cart.grouped_form")

    if grouped_form:
        return "GROUPED"

    return "SIMPLE"


def extract_price_text(soup: BeautifulSoup) -> str:
    return extract_text(
        soup,
        [
            ".summary .price",
            ".product-main .price",
            "p.price",
            "span.price",
        ],
    )


def extract_image_urls(soup: BeautifulSoup, product_url: str) -> tuple[str, str]:
    image_urls: list[str] = []

    selectors = [
        ".woocommerce-product-gallery__wrapper img",
        ".product-gallery-slider img",
        ".product-thumbnails img",
        ".product-main img",
    ]

    for selector in selectors:
        for img_tag in soup.select(selector):
            image_url = (
                img_tag.get("data-large_image")
                or img_tag.get("data-src")
                or img_tag.get("src")
                or ""
            )

            if not image_url:
                continue

            absolute_url = urljoin(product_url, image_url)

            if absolute_url not in image_urls:
                image_urls.append(absolute_url)

    thumbnail_url = image_urls[0] if image_urls else ""
    gallery_urls = json.dumps(image_urls, ensure_ascii=False)

    return thumbnail_url, gallery_urls


def extract_product_attributes(soup: BeautifulSoup) -> dict[str, str]:
    attributes = {
        "material_name": "",
        "design_style": "",
        "raw_color": "",
        "usage_context": "",
    }

    label_map = {
        "chat lieu": "material_name",
        "kieu dang": "design_style",
        "mau sac": "raw_color",
        "ung dung": "usage_context",
    }

    tables = soup.select(".product-content table, .woocommerce-tabs table, table")

    for table in tables:
        for row in table.select("tr"):
            cells = row.select("td")

            if len(cells) < 3:
                continue

            label = normalize_label(cells[0].get_text(" ", strip=True))
            value = normalize_text(cells[2].get_text(" ", strip=True))

            if not label or not value:
                continue

            target_field = label_map.get(label)

            if target_field and not attributes[target_field]:
                attributes[target_field] = value

    return attributes


def read_product_urls() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "collection_name",
        "collection_url",
        "collection_slug",
        "product_name",
        "product_url",
        "slug",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns in {INPUT_FILE}: {sorted(missing_columns)}"
        )

    df = (
        df[
            [
                "collection_name",
                "collection_url",
                "collection_slug",
                "product_name",
                "product_url",
                "slug",
            ]
        ]
        .dropna(subset=["product_url"])
        .drop_duplicates(subset=["product_url"])
        .reset_index(drop=True)
    )

    logger.info("Loaded %s product URLs from %s", len(df), INPUT_FILE)

    return df


def parse_product_detail(product_row: pd.Series) -> dict:
    product_url = product_row["product_url"]

    try:
        html = fetch_html(product_url)
        soup = BeautifulSoup(html, "lxml")

        product_name = extract_text(
            soup,
            [
                ".product_title",
                "h1.product-title",
                "h1.entry-title",
            ],
        ) or product_row["product_name"]

        raw_price_text = extract_price_text(soup)
        thumbnail_url, gallery_urls = extract_image_urls(soup, product_url)
        attributes = extract_product_attributes(soup)

        return {
            "collection_name": product_row["collection_name"],
            "collection_url": product_row["collection_url"],
            "collection_slug": product_row["collection_slug"],
            "product_name": product_name,
            "product_url": product_url,
            "slug": product_row["slug"],
            "product_type": extract_product_type(soup),
            "description": extract_html_text(
                soup,
                [
                    ".woocommerce-Tabs-panel--description",
                    "#tab-description",
                    ".product-short-description",
                ],
            ),
            "material_name": attributes["material_name"],
            "design_style": attributes["design_style"],
            "raw_color": attributes["raw_color"],
            "usage_context": attributes["usage_context"],
            "short_description": extract_html_text(
                soup,
                [
                    ".summary .short-description",
                    ".summary .woocommerce-product-details__short-description",
                    ".product-short-description",
                ],
            ),
            "raw_price_text": raw_price_text,
            "price": normalize_price(raw_price_text),
            "currency": (
                "VND" if raw_price_text and "VND" in raw_price_text.upper() else ""
            ),
            "thumbnail_url": thumbnail_url,
            "gallery_urls": gallery_urls,
            "source": "product_page",
            "crawl_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": "",
        }
    except Exception as exc:
        logger.exception(
            "Failed to crawl product detail for %s",
            product_row["product_url"],
        )

        return {
            "collection_name": product_row["collection_name"],
            "collection_url": product_row["collection_url"],
            "collection_slug": product_row["collection_slug"],
            "product_name": product_row["product_name"],
            "product_url": product_url,
            "slug": product_row["slug"],
            "description": "",
            "material_name": "",
            "design_style": "",
            "raw_color": "",
            "usage_context": "",
            "raw_price_text": "",
            "thumbnail_url": "",
            "gallery_urls": "[]",
            "crawl_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(exc),
        }


# ==================================================
# MAIN CRAWLER
# ==================================================

def crawl_product_lines() -> pd.DataFrame:
    logger.info("Starting product detail crawl")

    product_urls_df = read_product_urls()
    rows = []

    for _, product_row in product_urls_df.iterrows():
        logger.info(
            "Crawling product detail for %s",
            product_row["product_url"],
        )
        rows.append(parse_product_detail(product_row))

    if not rows:
        logger.error("No product detail crawled")
        raise ValueError("No product detail crawled.")

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["product_url"]).reset_index(drop=True)

    df = df[
        [
            "collection_name",
            "collection_url",
            "collection_slug",
            "product_name",
            "product_url",
            "slug",
            "description",
            "material_name",
            "design_style",
            "raw_color",
            "usage_context",
            "raw_price_text",
            "thumbnail_url",
            "gallery_urls",
            "crawl_at",
            "error",
        ]
    ]

    logger.info("Finished product detail crawl with %s rows", len(df))

    return df


def save_product_lines() -> None:
    logger.info("Saving product details to %s", OUTPUT_FILE)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df = crawl_product_lines()
    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    logger.info("Created file: %s", OUTPUT_FILE)
    logger.info("Total product lines: %s", len(df))


if __name__ == "__main__":
    try:
        save_product_lines()
    except Exception:
        logger.exception("Product detail crawler failed")
        raise
