from pathlib import Path
import re
import unicodedata

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MASTER_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = MASTER_DIR / "category.csv"


def make_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"[\s_]+", "-", normalized)
    return normalized.strip("-")


CATEGORIES = [
    {
        "category_name": "Áo sơ mi",
        "description": "Danh mục các thiết kế áo sơ mi mang phong cách thanh lịch, dễ phối trong nhiều hoàn cảnh.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Áo choàng",
        "description": "Danh mục áo choàng dùng để khoác ngoài, tạo điểm nhấn mềm mại và sang trọng cho trang phục.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Áo dài",
        "description": "Danh mục chính gồm các thiết kế áo dài truyền thống và cách tân, tôn vinh vẻ đẹp Á Đông.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Áo yếm",
        "description": "Danh mục áo yếm lấy cảm hứng từ trang phục truyền thống, phù hợp với phong cách nữ tính và duyên dáng.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Đầm dài",
        "description": "Danh mục các mẫu đầm dài nhẹ nhàng, thanh lịch, phù hợp cho dạo phố, sự kiện hoặc dịp đặc biệt.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Đầm 2 dây",
        "description": "Danh mục đầm hai dây với phom dáng mềm mại, thoải mái và phù hợp với phong cách nữ tính hiện đại.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Đầm dạ hội",
        "description": "Danh mục đầm dành cho tiệc, sự kiện và những dịp cần vẻ ngoài nổi bật, sang trọng.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Đầm dạo phố",
        "description": "Danh mục đầm mặc hàng ngày, ưu tiên sự thoải mái, tinh tế và dễ ứng dụng.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Quần",
        "description": "Danh mục các mẫu quần phối cùng áo dài, áo sơ mi hoặc các thiết kế khác trong bộ sưu tập.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Chân váy",
        "description": "Danh mục chân váy mang tinh thần nữ tính, dễ phối cùng áo sơ mi, áo yếm hoặc áo kiểu.",
        "parent_name": None,
        "department": "Women",
    },
    {
        "category_name": "Áo dài chiết eo",
        "description": "Thiết kế áo dài có phần eo được xử lý gọn gàng, giúp tôn dáng và tạo vẻ thanh thoát.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài tay ngắn",
        "description": "Thiết kế áo dài tay ngắn trẻ trung, thoải mái, phù hợp với thời tiết ấm và nhu cầu mặc hàng ngày.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài suông tay loe dài",
        "description": "Thiết kế áo dài dáng suông với tay loe dài, tạo cảm giác mềm mại, bay bổng và trang nhã.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài suông tay loe lửng",
        "description": "Thiết kế áo dài dáng suông với tay loe lửng, cân bằng giữa nét truyền thống và sự tiện dụng.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài 2 tà",
        "description": "Dòng áo dài hai tà quen thuộc, giữ tinh thần truyền thống và phù hợp với nhiều dịp sử dụng.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài 4 tà",
        "description": "Thiết kế áo dài bốn tà tạo độ chuyển động mềm mại, tăng chiều sâu và sự nổi bật cho trang phục.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài 2 lớp",
        "description": "Thiết kế áo dài hai lớp tạo hiệu ứng thị giác tinh tế, tăng độ mềm mại và sang trọng.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài ngắn cúc lệnh",
        "description": "Thiết kế áo dài ngắn với hàng cúc lệch, mang hơi hướng cách tân nhưng vẫn giữ nét duyên truyền thống.",
        "parent_name": "Áo dài",
        "department": "Men",
    },
    {
        "category_name": "Áo dài ngắn cúc thẳng",
        "description": "Thiết kế áo dài ngắn với hàng cúc thẳng, tạo cảm giác gọn gàng, hiện đại và dễ mặc.",
        "parent_name": "Áo dài",
        "department": "Men",
    },
    {
        "category_name": "Áo dài cúc lệch",
        "description": "Thiết kế áo dài có chi tiết cúc lệch làm điểm nhấn, tạo nét mềm mại và khác biệt.",
        "parent_name": "Áo dài",
        "department": "Men",
    },
    {
        "category_name": "Áo dài vạt chéo",
        "description": "Thiết kế áo dài với phần vạt chéo tạo hiệu ứng thị giác độc đáo, phù hợp với phong cách cách tân.",
        "parent_name": "Áo dài",
        "department": "Men",
    },
    {
        "category_name": "Áo dài cưới nữ",
        "description": "Danh mục áo dài cưới dành cho nữ, phù hợp với lễ cưới, lễ hỏi và các dịp trọng đại.",
        "parent_name": "Áo dài",
        "department": "Women",
    },
    {
        "category_name": "Áo dài cưới nam",
        "description": "Danh mục áo dài cưới dành cho nam, thường được thiết kế đồng điệu với trang phục nữ trong ngày cưới.",
        "parent_name": "Áo dài",
        "department": "Men",
    },
    {
        "category_name": "Áo dài đôi",
        "description": "Danh mục áo dài đôi dành cho nam và nữ, phù hợp với chụp ảnh, lễ cưới, lễ hỏi hoặc sự kiện đặc biệt.",
        "parent_name": "Áo dài",
        "department": None,
    },
]


def generate_category_master() -> pd.DataFrame:
    df = pd.DataFrame(CATEGORIES)
    df["slug"] = df["category_name"].apply(lambda x: make_slug(str(x)))
    df["is_active"] = True

    return df[
        [
            "category_name",
            "description",
            "parent_name",
            "department",
            "slug",
            "is_active",
        ]
    ]


def save_category_master() -> None:
    MASTER_DIR.mkdir(parents=True, exist_ok=True)

    df = generate_category_master()
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"Created category master file: {OUTPUT_FILE}")
    print(f"Total categories: {len(df)}")


if __name__ == "__main__":
    save_category_master()
