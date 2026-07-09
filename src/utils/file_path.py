from pathlib import Path


# ==================================================
# ROOT PATHS
# ==================================================

# file_path.py nằm ở: src/utils/file_path.py
# parents[0] = utils
# parents[1] = src
# parents[2] = xeoxo-ecommerce
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
SRC_DIR = PROJECT_ROOT / "src"

RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
MASTER_DIR = DATA_DIR / "master"
LOG_DIR = DATA_DIR / "logs"


# ==================================================
# RAW FILES
# ==================================================

RAW_PRODUCT_URLS_FILE = RAW_DIR / "raw_product_urls.csv"
RAW_PRODUCTS_FILE = RAW_DIR / "raw_products.csv"
RAW_COLLECTIONS_FILE = RAW_DIR / "raw_collections.csv"
RAW_MEDIA_FILE = RAW_DIR / "raw_media.csv"


# ==================================================
# STAGING FILES
# ==================================================

STG_PRODUCTS_FILE = STAGING_DIR / "stg_products.csv"
STG_COLLECTIONS_FILE = STAGING_DIR / "stg_collections.csv"
STG_MEDIA_FILE = STAGING_DIR / "stg_media.csv"


# ==================================================
# MASTER FILES
# ==================================================

CATEGORY_FILE = MASTER_DIR / "category.csv"
COLLECTION_FILE = MASTER_DIR / "collection.csv"
PRODUCT_LINE_FILE = MASTER_DIR / "product_line.csv"
PRODUCT_VARIANT_FILE = MASTER_DIR / "product_variant.csv"

COLOR_FILE = MASTER_DIR / "color.csv"
SIZE_FILE = MASTER_DIR / "size.csv"
MATERIAL_FILE = MASTER_DIR / "material.csv"

MEDIA_FILE = MASTER_DIR / "media.csv"
PRODUCT_LINE_MEDIA_FILE = MASTER_DIR / "product_line_media.csv"

BRANCH_FILE = MASTER_DIR / "branch.csv"
INVENTORY_FILE = MASTER_DIR / "inventory.csv"
PAYMENT_METHOD_FILE = MASTER_DIR / "payment_method.csv"
LOYALTY_TIER_FILE = MASTER_DIR / "loyalty_tier.csv"
PROVINCE_SQL_FILE = MASTER_DIR / "province.sql"


# ==================================================
# LOG FILES
# ==================================================

SCRAPE_LOG_FILE = LOG_DIR / "scrape_log.csv"
FAILED_URLS_FILE = LOG_DIR / "failed_urls.csv"


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def create_dir(path: Path) -> None:
    """
    Tạo thư mục nếu chưa tồn tại.
    """
    path.mkdir(parents=True, exist_ok=True)


def create_project_dirs() -> None:
    """
    Tạo toàn bộ thư mục data cần thiết cho scraper.
    Gọi hàm này ở đầu pipeline để tránh lỗi thiếu folder.
    """
    dirs = [
        DATA_DIR,
        RAW_DIR,
        STAGING_DIR,
        MASTER_DIR,
        LOG_DIR,
    ]

    for directory in dirs:
        create_dir(directory)


def get_project_root() -> Path:
    """
    Trả về đường dẫn root của project.
    """
    return PROJECT_ROOT


def get_data_dir(layer: str) -> Path:
    """
    Lấy thư mục theo layer dữ liệu.

    Ví dụ:
        get_data_dir("raw")     -> data/raw
        get_data_dir("staging") -> data/staging
        get_data_dir("master")  -> data/master
        get_data_dir("logs")    -> data/logs
    """
    layer_map = {
        "raw": RAW_DIR,
        "staging": STAGING_DIR,
        "master": MASTER_DIR,
        "logs": LOG_DIR,
    }

    if layer not in layer_map:
        raise ValueError(
            f"Layer không hợp lệ: {layer}. "
            f"Chỉ nhận: {list(layer_map.keys())}"
        )

    return layer_map[layer]


def get_data_path(filename: str, layer: str = "raw") -> Path:
    """
    Tạo đường dẫn file trong data theo layer.

    Ví dụ:
        get_data_path("raw_products.csv", "raw")
        -> data/raw/raw_products.csv

        get_data_path("product_line.csv", "master")
        -> data/master/product_line.csv
    """
    return get_data_dir(layer) / filename


def ensure_parent_dir(file_path: Path) -> None:
    """
    Tạo thư mục cha của một file nếu chưa tồn tại.

    Dùng trước khi ghi file CSV.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_file_ready(file_path: Path) -> Path:
    """
    Đảm bảo thư mục cha của file tồn tại,
    sau đó trả lại chính file_path.

    Ví dụ:
        df.to_csv(ensure_file_ready(RAW_PRODUCTS_FILE), index=False)
    """
    ensure_parent_dir(file_path)
    return file_path
