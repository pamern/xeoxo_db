import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.utils.loggers import get_logger


# ==================================================
# CONFIG
# ==================================================

BASE_URL = "https://xeoxo.com"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INPUT_FILE = RAW_DIR / "collection_url.csv"
OUTPUT_FILE = RAW_DIR / "product_url.csv"

REQUEST_DELAY_SECONDS = 0.5
MAX_PAGES_PER_COLLECTION = 50

logger = get_logger(__name__)


# ==================================================
# HELPERS
# ==================================================

def make_slug(text: str) -> str:
    text = str(text).strip().lower()

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")

    return text


def normalize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()


def canonicalize_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/") + "/",
            "",
            "",
        )
    )


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


def read_collection_urls() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "collection_name",
        "collection_url",
        "slug",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns in {INPUT_FILE}: {sorted(missing_columns)}"
        )

    logger.info("Loaded %s collection URLs from %s", len(df), INPUT_FILE)

    return df


# ==================================================
# PARSE PRODUCT LINKS
# ==================================================

def is_product_url(url: str) -> bool:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") + "/"

    return "/san-pham/" in path or "/product/" in path


def extract_product_name(a_tag) -> str:
    product_card = a_tag.find_parent("li", class_=lambda c: c and "product" in c)

    if product_card:
        title_tag = product_card.select_one(
            ".woocommerce-loop-product__title, h2, h3"
        )

        if title_tag:
            return normalize_text(title_tag.get_text(" ", strip=True))

    img_tag = a_tag.find("img")

    if img_tag and img_tag.get("alt"):
        return normalize_text(img_tag["alt"])

    return normalize_text(a_tag.get_text(" ", strip=True))


def parse_product_links_from_page(
    soup: BeautifulSoup,
    collection_row: pd.Series,
) -> list[dict]:
    products = []
    crawl_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for a_tag in soup.find_all("a", href=True):
        product_url = canonicalize_url(urljoin(BASE_URL, a_tag["href"]))

        if not is_product_url(product_url):
            continue

        product_name = extract_product_name(a_tag)

        products.append(
            {
                "collection_name": collection_row["collection_name"],
                "collection_url": collection_row["collection_url"],
                "collection_slug": collection_row["slug"],
                "product_name": product_name,
                "product_url": product_url,
                "slug": make_slug(product_name) if product_name else "",
                "source": "collection_page",
                "crawl_at": crawl_at,
            }
        )

    return products


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    next_tag = soup.select_one("a[rel='next'], a.next, a.next.page-numbers")

    if not next_tag or not next_tag.get("href"):
        return None

    next_url = canonicalize_url(urljoin(current_url, next_tag["href"]))
    current_url = canonicalize_url(current_url)

    if next_url == current_url:
        return None

    return next_url


# ==================================================
# MAIN CRAWLER
# ==================================================

def crawl_product_urls_for_collection(collection_row: pd.Series) -> list[dict]:
    collection_url = canonicalize_url(collection_row["collection_url"])
    logger.info(
        "Starting product URL crawl for %s: %s",
        collection_row["collection_name"],
        collection_url,
    )

    products = []
    visited_pages = set()
    current_url = collection_url

    for page_number in range(1, MAX_PAGES_PER_COLLECTION + 1):
        if current_url in visited_pages:
            logger.warning("Skip repeated page URL: %s", current_url)
            break

        visited_pages.add(current_url)

        html = fetch_html(current_url)
        soup = BeautifulSoup(html, "lxml")

        page_products = parse_product_links_from_page(soup, collection_row)
        products.extend(page_products)

        logger.info(
            "Parsed %s product URLs from page %s of %s",
            len(page_products),
            page_number,
            collection_row["collection_name"],
        )

        next_url = find_next_page_url(soup, current_url)

        if not next_url:
            break

        current_url = next_url
        time.sleep(REQUEST_DELAY_SECONDS)

    logger.info(
        "Finished %s with %s raw product URL rows",
        collection_row["collection_name"],
        len(products),
    )

    return products


def crawl_product_urls() -> pd.DataFrame:
    logger.info("Starting product URL crawl")

    collections_df = read_collection_urls()
    products = []

    for _, collection_row in collections_df.iterrows():
        products.extend(crawl_product_urls_for_collection(collection_row))
        time.sleep(REQUEST_DELAY_SECONDS)

    if not products:
        logger.error("No product URL crawled")
        raise ValueError("No product URL crawled.")

    df = pd.DataFrame(products)

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["product_url"])
    df = df.reset_index(drop=True)
    logger.info("Dropped %s duplicate product URLs", before_dedup - len(df))

    df = df[
        [
            "collection_name",
            "collection_url",
            "collection_slug",
            "product_name",
            "product_url",
            "slug",
            "source",
            "crawl_at",
        ]
    ]

    logger.info("Finished product URL crawl with %s rows", len(df))

    return df


def save_product_urls() -> None:
    logger.info("Saving product URLs to %s", OUTPUT_FILE)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df = crawl_product_urls()

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    logger.info("Created file: %s", OUTPUT_FILE)
    logger.info("Total product URLs: %s", len(df))
    logger.info("\n%s", df)


if __name__ == "__main__":
    try:
        save_product_urls()
    except Exception:
        logger.exception("Product URL crawler failed")
        raise
