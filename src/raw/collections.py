from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.utils.loggers import get_logger


# ==================================================
# CONFIG
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INPUT_FILE = RAW_DIR / "product_url.csv"
OUTPUT_FILE = RAW_DIR / "collections.csv"

logger = get_logger(__name__)


# ==================================================
# HELPERS
# ==================================================

def normalize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()


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


def read_collection_sources() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "collection_name",
        "collection_url",
        "collection_slug",
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
            ]
        ]
        .drop_duplicates(subset=["collection_slug"])
        .reset_index(drop=True)
    )

    logger.info("Loaded %s collections from %s", len(df), INPUT_FILE)

    return df


def get_meta_content(soup: BeautifulSoup, selector: str) -> str:
    tag = soup.select_one(selector)

    if not tag:
        return ""

    content = tag.get("content") or tag.get_text(" ", strip=True)

    return normalize_text(content)


def parse_cultural_story(soup: BeautifulSoup) -> str:
    selectors = [
        ".product-category-description",
        ".term-description",
        ".archive-description",
        ".woocommerce-products-header__description",
    ]

    for selector in selectors:
        block = soup.select_one(selector)

        if not block:
            continue

        text = normalize_text(block.get_text(" ", strip=True))

        if text:
            return text

    return get_meta_content(soup, "meta[property='og:description']")


def parse_cover_image(soup: BeautifulSoup, collection_url: str) -> str:
    og_image = get_meta_content(soup, "meta[property='og:image']")

    if og_image:
        return urljoin(collection_url, og_image)

    img_tag = soup.select_one(
        ".woocommerce-products-header img, .term-description img, main img"
    )

    if not img_tag:
        return ""

    image_url = (
        img_tag.get("src")
        or img_tag.get("data-src")
        or img_tag.get("data-lazy-src")
        or ""
    )

    if not image_url:
        return ""

    return urljoin(collection_url, image_url)


def parse_collection_detail(collection_row: pd.Series) -> dict:
    collection_url = collection_row["collection_url"]

    try:
        html = fetch_html(collection_url)
        soup = BeautifulSoup(html, "lxml")

        return {
            "collection_name": collection_row["collection_name"],
            "slug": collection_row["collection_slug"],
            "description": "",
            "media_url": parse_cover_image(soup, collection_url),
            "cultural_story": parse_cultural_story(soup),
            "season": "",
            "launch_date": "",
            "status": "ACTIVE",
            "source": "collection_page",
            "crawl_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": "",
        }
    except Exception as exc:
        logger.exception(
            "Failed to crawl collection detail for %s",
            collection_row["collection_name"],
        )

        return {
            "collection_name": collection_row["collection_name"],
            "slug": collection_row["collection_slug"],
            "description": "",
            "media_url": "",
            "cultural_story": "",
            "season": "",
            "launch_date": "",
            "status": "ERROR",
            "source": "collection_page",
            "crawl_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(exc),
        }


# ==================================================
# MAIN CRAWLER
# ==================================================

def crawl_collections() -> pd.DataFrame:
    logger.info("Starting collection detail crawl")

    collections_df = read_collection_sources()
    rows = []

    for _, collection_row in collections_df.iterrows():
        logger.info(
            "Crawling collection detail for %s",
            collection_row["collection_name"],
        )
        rows.append(parse_collection_detail(collection_row))

    if not rows:
        logger.error("No collection detail crawled")
        raise ValueError("No collection detail crawled.")

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["slug"])
    df = df.reset_index(drop=True)

    df = df[
        [
            "collection_name",
            "slug",
            "description",
            "media_url",
            "cultural_story",
            "season",
            "launch_date",
            "status",
            "source",
            "crawl_at",
            "error",
        ]
    ]

    logger.info("Finished collection detail crawl with %s rows", len(df))

    return df


def save_raw_collections() -> None:
    logger.info("Saving collection details to %s", OUTPUT_FILE)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df = crawl_collections()
    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    logger.info("Created file: %s", OUTPUT_FILE)
    logger.info("Total collections: %s", len(df))
    logger.info("\n%s", df)


if __name__ == "__main__":
    try:
        save_raw_collections()
    except Exception:
        logger.exception("Collection detail crawler failed")
        raise
