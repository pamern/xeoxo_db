from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.utils.loggers import get_logger


# ==================================================
# CONFIG
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
STAGING_DIR = PROJECT_ROOT / "data" / "staging"
COLLECTIONS_FILE = RAW_DIR / "collections.csv"
OUTPUT_FILE = STAGING_DIR / "collections.csv"

logger = get_logger(__name__)


# ==================================================
# HELPERS
# ==================================================

def add_months(base_date: date, months: int) -> date:
    """
    Dịch chuyển ngày theo số tháng, tự clamp ngày cuối tháng nếu cần.
    """
    total_month = (base_date.month - 1) + months
    target_year = base_date.year + (total_month // 12)
    target_month = (total_month % 12) + 1
    target_day = min(base_date.day, monthrange(target_year, target_month)[1])

    return date(target_year, target_month, target_day)


def infer_season(launch_date: date) -> str:
    """
    Quy ước mùa theo tháng:
    - Spring: 3-5
    - Summer: 6-8
    - Fall: 9-11
    - Winter: 12-2
    """
    month = launch_date.month

    if month in {3, 4, 5}:
        season_name = "Spring"
    elif month in {6, 7, 8}:
        season_name = "Summer"
    elif month in {9, 10, 11}:
        season_name = "Fall"
    else:
        season_name = "Winter"

    return season_name


def build_launch_dates(total_collections: int, start_date: date) -> list[date]:
    """
    Tạo danh sách ngày ra mắt theo thứ tự mới nhất -> cũ nhất.
    Nhịp phát hành lần lượt lùi 1 tháng, rồi 2 tháng, rồi lặp lại.
    """
    launch_dates: list[date] = []
    current_date = start_date

    for index in range(total_collections):
        if index == 0:
            launch_dates.append(current_date)
            continue

        step = -1 if index % 2 == 1 else -2
        current_date = add_months(current_date, step)
        launch_dates.append(current_date)

    return launch_dates


def read_collections() -> pd.DataFrame:
    if not COLLECTIONS_FILE.exists():
        raise FileNotFoundError(f"Collections file not found: {COLLECTIONS_FILE}")

    df = pd.read_csv(COLLECTIONS_FILE)

    required_columns = {"collection_name", "season", "launch_date"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns in {COLLECTIONS_FILE}: {sorted(missing_columns)}"
        )

    return df


def assign_collection_launch_dates(
    df: pd.DataFrame,
    start_date: date | None = None,
) -> pd.DataFrame:
    """
    Gán launch_date và season theo thứ tự hiện có trong file.
    Giả định dữ liệu đang được sắp từ collection mới nhất đến cũ nhất.
    """
    if df.empty:
        logger.warning("collections.csv is empty, nothing to update")
        return df

    anchor_date = start_date or datetime.now().date()
    launch_dates = build_launch_dates(len(df), anchor_date)

    updated_df = df.copy()
    updated_df["launch_date"] = [
        launch_date.strftime("%Y-%m-%d") for launch_date in launch_dates
    ]
    updated_df["season"] = [
        infer_season(launch_date) for launch_date in launch_dates
    ]

    return updated_df


def save_collections(df: pd.DataFrame) -> None:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")


def main() -> None:
    logger.info("Starting launch date assignment for collections")

    df = read_collections()
    updated_df = assign_collection_launch_dates(df)
    save_collections(updated_df)

    logger.info(
        "Updated %s collections with launch_date and season in %s",
        len(updated_df),
        COLLECTIONS_FILE,
    )
    logger.info(
        "Latest launch_date: %s | Oldest launch_date: %s",
        updated_df["launch_date"].iloc[0],
        updated_df["launch_date"].iloc[-1],
    )


if __name__ == "__main__":
    main()
