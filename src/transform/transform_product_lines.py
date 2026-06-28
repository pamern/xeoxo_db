from pathlib import Path

import pandas as pd

from src.utils.loggers import get_logger
from src.utils.normalizers import normalize_price, normalize_text

# ==================================================
# CONFIG
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STAGING_DIR = PROJECT_ROOT / "data" / "staging"

INPUT_FILE = RAW_DIR / "product_lines.csv"
OUTPUT_FILE = STAGING_DIR / "product_lines.csv"

DEFAULT_MATERIAL_NAME = "Lụa tổng hợp dệt kim tuyến"
DEFAULT_USAGE_CONTEXT = (
    "Thiết kế đơn giản được chú trọng vào các chi tiết về họa tiết "
    "đơn giản nhưng không kém phần nổi bật, phù hợp sử dụng được "
    "cho nhiều dịp khác nhau từ hàng ngày đến trọng đại."
)

logger = get_logger(__name__)


# ==================================================
# HELPERS
# ==================================================

def read_raw_product_lines() -> pd.DataFrame:
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
        "description",
        "material_name",
        "design_style",
        "raw_color",
        "usage_context",
        "thumbnail_url",
        "gallery_urls",
        "crawl_at",
        "error",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns in {INPUT_FILE}: {sorted(missing_columns)}"
        )

    logger.info("Loaded %s raw product lines from %s", len(df), INPUT_FILE)

    return df


def fill_default_text(series: pd.Series, default_value: str) -> pd.Series:
    return series.fillna("").map(normalize_text).replace("", default_value)


def transform_product_lines(df: pd.DataFrame) -> pd.DataFrame:
    transformed_df = df.copy()

    transformed_df["material_name"] = fill_default_text(
        transformed_df["material_name"],
        DEFAULT_MATERIAL_NAME,
    )
    transformed_df["usage_context"] = fill_default_text(
        transformed_df["usage_context"],
        DEFAULT_USAGE_CONTEXT,
    )

    transformed_df["price"] = transformed_df["raw_price_text"].fillna("").map(
        normalize_price
    )

    transformed_df = transformed_df[
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
            "price",
            "thumbnail_url",
            "gallery_urls",
            "crawl_at",
            "error",
        ]
    ]

    return transformed_df


def save_staging_product_lines(df: pd.DataFrame) -> None:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")


def main() -> None:
    logger.info("Starting product lines transform")

    raw_df = read_raw_product_lines()
    transformed_df = transform_product_lines(raw_df)
    save_staging_product_lines(transformed_df)

    logger.info("Created file: %s", OUTPUT_FILE)
    logger.info("Total transformed product lines: %s", len(transformed_df))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Product lines transform failed")
        raise
