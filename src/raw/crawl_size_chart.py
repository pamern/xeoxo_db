from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import sys
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://xeoxo.com"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MEDIA_DIR = PROJECT_ROOT / "data" / "media"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

INPUT_FILE = STAGING_DIR / "product_lines.csv"
OUTPUT_FILE = RAW_DIR / "size_chart_images.csv"
FAILED_FILE = LOG_DIR / "failed_size_chart_urls.csv"
SIZE_CHART_DIR = MEDIA_DIR / "size_chart"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none", "nan"}:
        return None

    return text


def safe_log_text(value: object) -> str:
    text = normalize_text(value) or ""
    return text.encode("ascii", errors="ignore").decode("ascii")


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def read_product_lines() -> list[dict]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE, dtype=str)
    required_columns = {"product_name", "product_url", "slug"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns in {INPUT_FILE}: {sorted(missing_columns)}"
        )

    df = df.dropna(subset=["product_name", "product_url", "slug"])
    df = df.drop_duplicates(subset=["product_url"]).reset_index(drop=True)
    return df.to_dict("records")


def extract_size_chart_url(soup: BeautifulSoup, page_url: str) -> str | None:
    selectors = [
        "#view-size-chart img",
        "div#view-size-chart img",
        "#view-size-chart a[href]",
    ]

    for selector in selectors:
        tag = soup.select_one(selector)
        if tag is None:
            continue

        if tag.name == "img":
            image_url = tag.get("data-src") or tag.get("src")
        else:
            image_url = tag.get("href")

        normalized_url = normalize_text(image_url)
        if normalized_url:
            return urljoin(page_url, normalized_url)

    container = soup.find(id="view-size-chart")
    if container is None:
        return None

    image_tag = container.find("img")
    if image_tag is not None:
        image_url = image_tag.get("data-src") or image_tag.get("src")
        normalized_url = normalize_text(image_url)
        if normalized_url:
            return urljoin(page_url, normalized_url)

    link_tag = container.find("a", href=True)
    if link_tag is not None:
        normalized_url = normalize_text(link_tag.get("href"))
        if normalized_url:
            return urljoin(page_url, normalized_url)

    return None


def build_local_filename(image_url: str) -> str:
    parsed = urlparse(image_url)
    source_name = Path(parsed.path).name or "size-chart.jpg"
    stem = Path(source_name).stem or "size-chart"
    suffix = Path(source_name).suffix or ".jpg"
    url_hash = hashlib.md5(image_url.encode("utf-8")).hexdigest()[:10]
    return f"{stem}_{url_hash}{suffix.lower()}"


def download_image(image_url: str, target_path: Path) -> tuple[bool, int]:
    if target_path.exists():
        return False, target_path.stat().st_size

    response = requests.get(image_url, headers=HEADERS, timeout=60)
    response.raise_for_status()

    target_path.write_bytes(response.content)
    return True, len(response.content)


def crawl_size_charts() -> tuple[pd.DataFrame, pd.DataFrame]:
    SIZE_CHART_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    product_lines = read_product_lines()
    rows: list[dict] = []
    failed_rows: list[dict] = []
    downloaded_by_url: dict[str, Path] = {}

    for index, product_line in enumerate(product_lines, start=1):
        product_name = normalize_text(product_line.get("product_name"))
        product_url = normalize_text(product_line.get("product_url"))
        slug = normalize_text(product_line.get("slug"))
        crawl_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(
            f"[{index}/{len(product_lines)}] Crawling size chart: "
            f"{safe_log_text(product_name)}"
        )

        try:
            if not product_url:
                raise ValueError("Missing product_url")

            html = fetch_html(product_url)
            soup = BeautifulSoup(html, "lxml")
            size_chart_url = extract_size_chart_url(soup, product_url)

            if not size_chart_url:
                rows.append(
                    {
                        "collection_name": normalize_text(product_line.get("collection_name")),
                        "product_name": product_name,
                        "product_url": product_url,
                        "slug": slug,
                        "size_chart_url": None,
                        "local_path": None,
                        "file_name": None,
                        "downloaded": False,
                        "file_size": None,
                        "crawl_at": crawl_at,
                    }
                )
                continue

            existing_path = downloaded_by_url.get(size_chart_url)
            if existing_path is None:
                file_name = build_local_filename(size_chart_url)
                local_path = SIZE_CHART_DIR / file_name
                downloaded, file_size = download_image(size_chart_url, local_path)
                downloaded_by_url[size_chart_url] = local_path
            else:
                local_path = existing_path
                downloaded = False
                file_size = local_path.stat().st_size if local_path.exists() else None

            rows.append(
                {
                    "collection_name": normalize_text(product_line.get("collection_name")),
                    "product_name": product_name,
                    "product_url": product_url,
                    "slug": slug,
                    "size_chart_url": size_chart_url,
                    "local_path": str(local_path.relative_to(PROJECT_ROOT)),
                    "file_name": local_path.name,
                    "downloaded": downloaded,
                    "file_size": file_size,
                    "crawl_at": crawl_at,
                }
            )
        except Exception as exc:
            failed_rows.append(
                {
                    "source": "crawl_size_chart",
                    "collection_name": normalize_text(product_line.get("collection_name")),
                    "product_name": product_name,
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

    result_df = pd.DataFrame(rows)
    failed_df = pd.DataFrame(failed_rows)

    if not result_df.empty:
        result_df = result_df.sort_values(
            by=["collection_name", "product_name", "product_url"],
            kind="stable",
        ).reset_index(drop=True)

    return result_df, failed_df


def save_size_chart_data() -> None:
    result_df, failed_df = crawl_size_charts()

    output_columns = [
        "collection_name",
        "product_name",
        "product_url",
        "slug",
        "size_chart_url",
        "local_path",
        "file_name",
        "downloaded",
        "file_size",
        "crawl_at",
    ]
    failed_columns = [
        "source",
        "collection_name",
        "product_name",
        "url",
        "error_type",
        "status_code",
        "error",
        "crawl_at",
    ]

    if result_df.empty:
        result_df = pd.DataFrame(columns=output_columns)
    else:
        for column in output_columns:
            if column not in result_df.columns:
                result_df[column] = None
        result_df = result_df[output_columns]

    if failed_df.empty:
        failed_df = pd.DataFrame(columns=failed_columns)
    else:
        for column in failed_columns:
            if column not in failed_df.columns:
                failed_df[column] = None
        failed_df = failed_df[failed_columns]

    result_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    failed_df.to_csv(FAILED_FILE, index=False, encoding="utf-8-sig")

    found_count = int(result_df["size_chart_url"].notna().sum()) if not result_df.empty else 0
    print(f"\nCreated file: {OUTPUT_FILE}")
    print(f"Total product lines: {len(result_df)}")
    print(f"Found size chart images: {found_count}")
    print(f"Downloaded new files: {int(result_df['downloaded'].fillna(False).sum()) if not result_df.empty else 0}")
    print(f"Failed rows saved to: {FAILED_FILE}")
    print(f"Total failed rows: {len(failed_df)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    save_size_chart_data()
