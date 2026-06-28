from __future__ import annotations

import re
from typing import TypedDict


NULL_LIKE_VALUES = {"", "null", "n/a", "na", "none"}

PRIMARY_COLOR_PATTERNS: list[tuple[str, str]] = [
    (r"\btrang\s+kem\b", "Trắng kem"),
    (r"\bxanh\s+ngoc\b", "Xanh ngọc"),
    (r"\bxanh\s+co[m]?\b", "Xanh cốm"),
    (r"\bxanh\s+oliu\b", "Xanh oliu"),
    (r"\bxanh\s+la\b", "Xanh lá"),
    (r"\bxanh\s+luc\b", "Xanh lục"),
    (r"\bxanh\s+coban\b", "Xanh coban"),
    (r"\bxanh\s+bien\s+nhat\b", "Xanh biển nhạt"),
    (r"\bxanh\s+bien\b", "Xanh biển"),
    (r"\bxanh\s+lam\b", "Xanh lam"),
    (r"\bxanh\s+xam\b", "Xanh xám"),
    (r"\bhong\s+phan\s+nhat\b", "Hồng phấn nhạt"),
    (r"\bhong\s+phan\b", "Hồng phấn"),
    (r"\bhong\s+dam\b", "Hồng đậm"),
    (r"\bhong\s+nhat\b", "Hồng nhạt"),
    (r"\bhong\s+sen\b", "Hồng sen"),
    (r"\bhong\s+tim\b", "Hồng tím"),
    (r"\bhong\s+cam\b", "Hồng cam"),
    (r"\bhong\s+do\b", "Hồng đỗ"),
    (r"\bdo\s+man\b", "Đỏ mận"),
    (r"\bdo\s+dam\b", "Đỏ đậm"),
    (r"\bvang\s+nhat\b", "Vàng nhạt"),
    (r"\bvang\s+kem\b", "Vàng kem"),
    (r"\bvang\s+nau\b", "Vàng nâu"),
    (r"\btim\s+nhat\b", "Tím nhạt"),
    (r"\bxam\s+bac\b", "Xám bạc"),
    (r"\btrang\s+xam\b", "Trắng xám"),
    (r"\btrang\b", "Trắng"),
    (r"\bden\b", "Đen"),
    (r"\bbe\b", "Be"),
    (r"\bxanh\b", "Xanh"),
    (r"\bhong\b", "Hồng"),
    (r"\bdo\b", "Đỏ"),
    (r"\bvang\b", "Vàng"),
    (r"\btim\b", "Tím"),
    (r"\bcam\b", "Cam"),
    (r"\bkem\b", "Kem"),
    (r"\bnau\b", "Nâu"),
    (r"\bxam\b", "Xám"),
]

# Palette tổng quát cho filter:
# Xanh, Hồng, Đỏ, Vàng, Cam, Tím, Trắng, Đen, Xám, Nâu, Be, Kem, Khác
COLOR_GROUP_MAP = {
    "Xanh cốm": "Xanh",
    "Xanh oliu": "Xanh",
    "Xanh lá": "Xanh",
    "Xanh lục": "Xanh",
    "Xanh coban": "Xanh",
    "Xanh biển": "Xanh",
    "Xanh biển nhạt": "Xanh",
    "Xanh lam": "Xanh",
    "Xanh ngọc": "Xanh",
    "Xanh": "Xanh",
    "Hồng": "Hồng",
    "Hồng đậm": "Hồng",
    "Hồng sen": "Hồng",
    "Hồng phấn": "Hồng",
    "Hồng phấn nhạt": "Hồng",
    "Hồng nhạt": "Hồng",
    "Hồng tím": "Tím",
    "Tím": "Tím",
    "Tím nhạt": "Tím",
    "Hồng cam": "Cam",
    "Cam": "Cam",
    "Hồng đỗ": "Đỏ",
    "Đỏ": "Đỏ",
    "Đỏ đậm": "Đỏ",
    "Đỏ mận": "Đỏ",
    "Vàng": "Vàng",
    "Vàng nhạt": "Vàng",
    "Vàng kem": "Vàng",
    "Vàng nâu": "Nâu",
    "Kem": "Kem",
    "Trắng kem": "Kem",
    "Trắng": "Trắng",
    "Trắng xám": "Trắng",
    "Đen": "Đen",
    "Xám bạc": "Xám",
    "Xanh xám": "Xám",
    "Xám": "Xám",
    "Nâu": "Nâu",
    "Be": "Be",
}


class NormalizedColor(TypedDict):
    raw_color: str | None
    color_name: str | None
    color_group: str | None


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_accents(value: str) -> str:
    replacements = str.maketrans(
        {
            "à": "a",
            "á": "a",
            "ả": "a",
            "ã": "a",
            "ạ": "a",
            "ă": "a",
            "ằ": "a",
            "ắ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "ặ": "a",
            "â": "a",
            "ầ": "a",
            "ấ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ậ": "a",
            "è": "e",
            "é": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ẹ": "e",
            "ê": "e",
            "ề": "e",
            "ế": "e",
            "ể": "e",
            "ễ": "e",
            "ệ": "e",
            "ì": "i",
            "í": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ị": "i",
            "ò": "o",
            "ó": "o",
            "ỏ": "o",
            "õ": "o",
            "ọ": "o",
            "ô": "o",
            "ồ": "o",
            "ố": "o",
            "ổ": "o",
            "ỗ": "o",
            "ộ": "o",
            "ơ": "o",
            "ờ": "o",
            "ớ": "o",
            "ở": "o",
            "ỡ": "o",
            "ợ": "o",
            "ù": "u",
            "ú": "u",
            "ủ": "u",
            "ũ": "u",
            "ụ": "u",
            "ư": "u",
            "ừ": "u",
            "ứ": "u",
            "ử": "u",
            "ữ": "u",
            "ự": "u",
            "ỳ": "y",
            "ý": "y",
            "ỷ": "y",
            "ỹ": "y",
            "ỵ": "y",
            "đ": "d",
        }
    )
    return value.translate(replacements)


def _clean_raw_color_value(raw_color: str | None) -> str | None:
    if raw_color is None:
        return None

    cleaned = _collapse_spaces(str(raw_color))
    if not cleaned:
        return None

    if cleaned.lower() in NULL_LIKE_VALUES:
        return None

    return cleaned


def _extract_primary_segment(value: str) -> str:
    normalized = _strip_accents(value.lower())
    normalized = re.sub(r"\blop\s+ngoai\b", "", normalized)
    normalized = re.sub(r"\blop\s+trong\b", "", normalized)
    normalized = re.sub(r"\bco\s+\w+\b", "", normalized)

    split_patterns = [
        r"\s*,\s*",
        r"\s+diem\s+",
        r"\s*\/\s*",
        r"\s*-\s*",
    ]

    primary = normalized
    for pattern in split_patterns:
        parts = re.split(pattern, primary, maxsplit=1)
        primary = parts[0]

    return _collapse_spaces(primary)


def _extract_color_name(value: str) -> str | None:
    primary_segment = _extract_primary_segment(value)

    for pattern, color_name in PRIMARY_COLOR_PATTERNS:
        if re.search(pattern, primary_segment):
            return color_name

    return None


def _map_color_group(color_name: str | None) -> str | None:
    if color_name is None:
        return None

    return COLOR_GROUP_MAP.get(color_name, "Khác")


def normalizeColor(rawColor: str | None) -> NormalizedColor:
    cleaned_raw_color = _clean_raw_color_value(rawColor)

    if cleaned_raw_color is None:
        return {
            "raw_color": None,
            "color_name": None,
            "color_group": None,
        }

    color_name = _extract_color_name(cleaned_raw_color)
    color_group = _map_color_group(color_name)

    return {
        "raw_color": cleaned_raw_color,
        "color_name": color_name,
        "color_group": color_group,
    }


def _run_examples() -> None:
    test_cases = [
        ("Xanh cốm", "Xanh cốm", "Xanh"),
        ("Xanh oliu", "Xanh oliu", "Xanh"),
        ("Hồng đậm", "Hồng đậm", "Hồng"),
        ("Hồng phấn", "Hồng phấn", "Hồng"),
        ("Đỏ mận", "Đỏ mận", "Đỏ"),
        ("Hồng, xanh", "Hồng", "Hồng"),
        ("Trắng, đen, nâu", "Trắng", "Trắng"),
        ("Be xám, cổ xanh", "Be", "Be"),
        ("Hồng điểm xanh", "Hồng", "Hồng"),
        ("Xanh điểm cam", "Xanh", "Xanh"),
        ("Lớp ngoài đỏ, lớp trong vàng", "Đỏ", "Đỏ"),
        (None, None, None),
        ("", None, None),
        ("null", None, None),
        ("NULL", None, None),
        ("N/A", None, None),
        ("  xanh    biển nhạt  ", "Xanh biển nhạt", "Xanh"),
        ("Vàng nâu", "Vàng nâu", "Nâu"),
        ("Trắng kem", "Trắng kem", "Kem"),
        ("Xanh xám", "Xanh xám", "Xám"),
        ("Hồng tím", "Hồng tím", "Tím"),
        ("Hồng cam", "Hồng cam", "Cam"),
        ("Đen", "Đen", "Đen"),
        ("Xám bạc", "Xám bạc", "Xám"),
    ]

    for raw_color, expected_name, expected_group in test_cases:
        result = normalizeColor(raw_color)
        assert result["color_name"] == expected_name, (
            raw_color,
            result,
            expected_name,
        )
        assert result["color_group"] == expected_group, (
            raw_color,
            result,
            expected_group,
        )


if __name__ == "__main__":
    _run_examples()
