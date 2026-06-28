import re
import unicodedata
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

BASE_URL = "https://xeoxo.com"
HOME_URL = "https://xeoxo.com/vn/"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = RAW_DIR / "collection_url.csv"

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


def clean_collection_name(name: str) -> str:
    name = normalize_text(name)
    name = name.replace("▾", "").strip()
    return name


# ==================================================
# PARSE COLLECTION MENU
# ==================================================

def find_collection_menu_li(soup: BeautifulSoup):
    for li in soup.find_all("li"):
        a_tag = li.find("a", recursive=False)

        if not a_tag:
            continue

        menu_text = normalize_text(a_tag.get_text(" ", strip=True)).upper()
        menu_slug = make_slug(menu_text)

        if menu_text == "BỘ SƯU TẬP" or menu_slug == "bo-suu-tap":
            return li

    return None


def parse_collection_links_from_menu(soup: BeautifulSoup) -> list[dict]:
    logger.info("Parsing collection links from header menu")

    parent_li = find_collection_menu_li(soup)

    if not parent_li:
        logger.error("Collection menu not found in HTML")
        raise ValueError("Không tìm thấy menu BỘ SƯU TẬP trong HTML.")

    sub_menu = parent_li.find("ul", class_=lambda c: c and "sub-menu" in c)

    if not sub_menu:
        logger.error("Collection submenu not found in HTML")
        raise ValueError("Không tìm thấy submenu của BỘ SƯU TẬP.")

    collections = []
    crawl_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for a_tag in sub_menu.find_all("a", href=True):
        collection_name = clean_collection_name(
            a_tag.get_text(" ", strip=True)
        )
        collection_url = urljoin(BASE_URL, a_tag["href"])

        if not collection_name:
            logger.debug("Skip collection link because name is empty: %s", a_tag["href"])
            continue

        # Chỉ lấy URL danh mục thật
        if "/danh-muc/" not in collection_url:
            logger.debug("Skip non-category URL: %s", collection_url)
            continue

        collections.append(
            {
                "collection_name": collection_name,
                "collection_url": collection_url,
                "slug": make_slug(collection_name),
                "source": "header_menu",
                "crawl_at": crawl_at,
            }
        )

    logger.info("Parsed %s collection links from header menu", len(collections))

    return collections


# ==================================================
# MAIN CRAWLER
# ==================================================

def crawl_collection_urls() -> pd.DataFrame:
    logger.info("Starting collection URL crawl")

    html = fetch_html(HOME_URL)
    soup = BeautifulSoup(html, "lxml")

    collections = parse_collection_links_from_menu(soup)

    if not collections:
        logger.error("No collection URL crawled")
        raise ValueError("Không crawl được collection URL nào.")

    df = pd.DataFrame(collections)

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["collection_url"])
    df = df.reset_index(drop=True)
    logger.info("Dropped %s duplicate collection URLs", before_dedup - len(df))

    df = df[
        [
            "collection_name",
            "collection_url",
            "slug",
            "source",
            "crawl_at",
        ]
    ]

    logger.info("Finished collection URL crawl with %s rows", len(df))

    return df


def save_collection_urls() -> None:
    logger.info("Saving collection URLs to %s", OUTPUT_FILE)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df = crawl_collection_urls()

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    logger.info("Created file: %s", OUTPUT_FILE)
    logger.info("Total collection URLs: %s", len(df))
    logger.info("\n%s", df)


if __name__ == "__main__":
    try:
        save_collection_urls()
    except Exception:
        logger.exception("Collection URL crawler failed")
        raise
