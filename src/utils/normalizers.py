import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Chuẩn hoá text bằng cách gộp khoảng trắng thừa và trim hai đầu.
    """
    return " ".join(str(text).split()).strip()


def normalize_label(text: str) -> str:
    """
    Chuẩn hoá label để so khớp ổn định:
    - lower case
    - bỏ dấu tiếng Việt
    - bỏ ký tự đặc biệt
    - gộp khoảng trắng
    """
    normalized = normalize_text(text).lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def normalize_price(price_text: str) -> int | None:
    """
    Chuẩn hoá text giá về số nguyên.

    Ví dụ:
        '3.750.000 VND' -> 3750000
    """
    if not price_text:
        return None

    digits = re.sub(r"[^\d]", "", str(price_text))

    if not digits:
        return None

    return int(digits)
