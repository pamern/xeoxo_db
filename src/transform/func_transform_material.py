from __future__ import annotations

import re
from typing import TypedDict


class NormalizedMaterial(TypedDict):
    raw_material: str | None
    material_name: str | None
    short_description: str | None


class MaterialPattern(TypedDict):
    canonical: str
    pattern: str


class LayerInfo(TypedDict):
    label: str
    content: str


NULL_LIKE_VALUES = {"", "null", "n/a", "na", "none"}

MATERIAL_PATTERNS: list[MaterialPattern] = [
    {"canonical": "Tơ tằm 70%", "pattern": r"\blụa\s+tơ\s+tằm\s*70%|\btơ\s+tằm\s*70%"},
    {"canonical": "Lụa tổng hợp", "pattern": r"\blụa\s+tổng\s+hợp\b"},
    {"canonical": "Tơ tổng hợp", "pattern": r"\btơ\s+tổng\s+hợp\b"},
    {"canonical": "Vải tổng hợp", "pattern": r"\bvải\s+tổng\s+hợp\b"},
    {"canonical": "Lụa Habutai", "pattern": r"\blụa\s+habutai\b|\bhabutai\b"},
    {"canonical": "Organza", "pattern": r"\borganza\b"},
    {"canonical": "Tencel", "pattern": r"\btencel\b"},
    {"canonical": "Gấm", "pattern": r"\bgấm\b"},
    {"canonical": "Ren", "pattern": r"\bren\b"},
]

MATERIAL_DESCRIPTION_MAP: dict[str, str] = {
    "Gấm": (
        "Chất liệu có bề mặt dày dặn, đứng form, thường được dệt họa tiết "
        "nổi hoặc chìm, tạo cảm giác sang trọng và cổ điển."
    ),
    "Lụa tổng hợp": (
        "Chất liệu mềm, nhẹ, có độ rũ vừa phải, dễ tạo phom và phù hợp "
        "với các thiết kế cần sự thanh thoát."
    ),
    "Lụa tổng hợp và Organza": (
        "Sự kết hợp giữa độ mềm rũ của lụa tổng hợp và độ nhẹ, trong, bay "
        "của Organza, tạo hiệu ứng nhiều lớp tinh tế."
    ),
    "Organza": (
        "Chất liệu mỏng nhẹ, hơi trong, có độ phồng tự nhiên, thường tạo "
        "cảm giác thanh thoát và trang trọng."
    ),
    "Organza và Lụa tổng hợp": (
        "Sự kết hợp giữa lớp Organza nhẹ, trong và lớp lụa tổng hợp mềm mại, "
        "giúp sản phẩm vừa có độ bay vừa dễ mặc."
    ),
    "Organza và Tơ tằm 70%": (
        "Sự kết hợp giữa vẻ nhẹ, trong của Organza và độ mềm mịn, cao cấp "
        "của tơ tằm, tạo cảm giác tinh tế và sang trọng."
    ),
    "Ren": (
        "Chất liệu có bề mặt hoa văn xuyên thấu, tạo cảm giác nữ tính, mềm mại "
        "và giàu tính trang trí."
    ),
    "Tencel": (
        "Chất liệu mềm mịn, thoáng nhẹ, có độ rũ tự nhiên và mang lại cảm giác "
        "dễ chịu khi mặc."
    ),
    "Tơ tằm 70%": (
        "Chất liệu có thành phần tơ tằm cao, mềm mịn, nhẹ và có độ bóng tự nhiên, "
        "phù hợp với sản phẩm cao cấp."
    ),
    "Tơ tổng hợp": (
        "Chất liệu nhẹ, mềm, dễ ứng dụng trong nhiều kiểu dáng và có khả năng "
        "giữ màu, giữ phom ổn định."
    ),
    "Vải tổng hợp": (
        "Nhóm chất liệu linh hoạt, dễ tạo phom, bền màu và phù hợp với nhiều "
        "kỹ thuật dệt, in hoặc xử lý bề mặt."
    ),
}

LAYER_MARKER_REGEX = re.compile(
    r"(lớp\s+áo\s+ngoài|lớp\s+ngoài|lớp\s+áo\s+trong|lớp\s+trong|lớp\s+lót)\s*(?:là|:)?",
    re.IGNORECASE,
)


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    if not cleaned:
        return None

    return None if cleaned.lower() in NULL_LIKE_VALUES else cleaned


def normalize_spelling(value: str) -> str:
    return (
        value.replace("hoạ", "họa")
        .replace("Hoạ", "Họa")
        .replace("metalic", "metallic")
        .replace("Metalic", "Metallic")
    )


def clean_punctuation(value: str) -> str:
    return (
        value.replace(" ,", ",")
        .replace(" .", ".")
        .replace(" , ", ", ")
        .replace(" . ", ". ")
        .strip(" ,.")
    )


def normalize_layer_label(raw_label: str) -> str:
    lowered = raw_label.lower()

    if "lót" in lowered:
        return "Lớp lót"

    if "trong" in lowered:
        return "Lớp trong"

    return "Lớp ngoài"


def extract_layers(value: str) -> list[LayerInfo]:
    matches = list(LAYER_MARKER_REGEX.finditer(value))
    if not matches:
        return []

    layers: list[LayerInfo] = []

    for index, match in enumerate(matches):
        content_start = match.end()
        next_start = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(value)
        )
        content = value[content_start:next_start].strip().lstrip(",:. ").strip()
        content = clean_punctuation(content)

        if not content:
            continue

        layers.append(
            {
                "label": normalize_layer_label(match.group(1)),
                "content": content,
            }
        )

    return layers


def detect_materials(value: str) -> list[str]:
    found: list[tuple[int, str]] = []

    for material_pattern in MATERIAL_PATTERNS:
        match = re.search(
            material_pattern["pattern"], value, flags=re.IGNORECASE
        )
        if match:
            found.append((match.start(), material_pattern["canonical"]))

    found.sort(key=lambda item: item[0])

    materials: list[str] = []
    for _, material in found:
        if material not in materials:
            materials.append(material)

    return materials


def build_combined_material_name(materials: list[str]) -> str | None:
    if not materials:
        return None

    if len(materials) == 1:
        return materials[0]

    return " và ".join(materials)


def get_material_description(material_name: str | None) -> str | None:
    if not material_name:
        return None

    return MATERIAL_DESCRIPTION_MAP.get(material_name)


def pick_primary_material(materials: list[str]) -> str | None:
    return materials[0] if materials else None


def normalize_single_layer_material(value: str) -> NormalizedMaterial:
    materials = detect_materials(value)
    primary_material = pick_primary_material(materials)

    if not primary_material:
        return {
            "raw_material": value,
            "material_name": None,
            "short_description": None,
        }

    has_lining_lua_tong_hop = bool(
        re.search(r"\blót\s+lụa\s+tổng\s+hợp\b", value, flags=re.IGNORECASE)
    )
    has_lining_habutai = bool(
        re.search(r"\blót\s+(?:lụa\s+)?habutai\b", value, flags=re.IGNORECASE)
    )
    has_lining_organza = bool(
        re.search(r"\blót\s+organza\b", value, flags=re.IGNORECASE)
    )

    material_name = primary_material
    ordered_unique = list(dict.fromkeys(materials))

    if has_lining_habutai and primary_material in {
        "Lụa tổng hợp",
        "Tơ tổng hợp",
    }:
        material_name = primary_material
    elif has_lining_lua_tong_hop and primary_material != "Lụa tổng hợp":
        material_name = primary_material
    elif has_lining_organza and primary_material != "Organza":
        material_name = build_combined_material_name(
            list(dict.fromkeys([primary_material, "Organza"]))
        )
    elif len(ordered_unique) > 1:
        material_name = build_combined_material_name(ordered_unique)

    return {
        "raw_material": value,
        "material_name": material_name,
        "short_description": get_material_description(material_name),
    }


def normalize_layered_material(
    value: str, layers: list[LayerInfo]
) -> NormalizedMaterial:
    primary_materials: list[str] = []

    for layer in layers:
        material = pick_primary_material(detect_materials(layer["content"]))
        if material and material not in primary_materials:
            primary_materials.append(material)

    return {
        "raw_material": value,
        "material_name": build_combined_material_name(primary_materials),
        "short_description": get_material_description(
            build_combined_material_name(primary_materials)
        ),
    }


def normalize_material(raw_material: str | None) -> NormalizedMaterial:
    raw_value = clean_text(raw_material)

    if raw_value is None:
        return {
            "raw_material": None,
            "material_name": None,
            "short_description": None,
        }

    normalized_value = normalize_spelling(raw_value)
    layers = extract_layers(normalized_value)

    if layers:
        return normalize_layered_material(raw_value, layers)

    return normalize_single_layer_material(raw_value)


def normalizeMaterial(rawMaterial: str | None) -> NormalizedMaterial:
    return normalize_material(rawMaterial)


MATERIAL_DEMO_INPUTS = [
    "Lụa tổng hợp dệt kim tuyến",
    "Lụa tổng hợp dệt hoạ tiết nổi in hoa lót lụa tổng hợp dệt kim tuyến (metalic)",
    "Tencel dệt chìm hoạ tiết",
    "Organza đính kết thủ công lót lụa tổng hợp",
    "Lụa tổng hợp dệt họa tiết",
    "Ren lót lụa tổng hợp",
    "Tơ tằm 70% dệt hoạ tiết",
    "Lớp ngoài Organza đính kết họa tiết. Lớp trong: tơ tằm 70% dệt họa tiết",
    "Tơ tằm 70% dệt họa tiết",
    "Lớp ngoài: Organza dệt chìm hoạ tiết Lớp trong: Lụa tổng hợp",
    "Tencel dệt chìm hoạ tiết lót lụa tổng hợp",
    "Gấm lót lụa tổng hợp",
    "Tơ tổng hợp lót lụa habutai",
    "Organza dệt chìm hoạ tiết lót lụa tổng hợp",
    "Lụa tổng hợp dệt kim tuyến lót habutai",
    "Organza",
    "Lụa tổng hợp dệt hoạ tiết lót organza",
    "Lớp áo ngoài: Lụa tổng hợp dệt hoạ tiết Lớp áo trong: Organza siêu nhẹ",
    "Organza đính kết thủ công",
    "Lụa tổng hợp",
    "Gấm dệt chìm hoạ tiết, lót lụa tổng hợp",
    "Gấm dệt chìm hoạ tiết lót lụa tổng hợp",
    "Gấm hoạ tiết đính kết thủ công, lót lụa tổng hợp",
    "Lụa tổng hợp dệt hoạ tiết lót lụa habutai",
    "Lụa tổng hợp dệt hoạ tiết, lót lụa habutai",
    "Organza dệt chìm hoạ tiết, đính kết thủ công",
    "Organza thêu hoạ tiết",
    "Tencel thêu hoạ tiết",
    "Lụa tơ tằm 70%",
    "Organza thêu họa tiết",
    "Organza đính kết họa tiết",
    "Lớp ngoài là organza, lớp lót là lụa tổng hợp",
    "Lụa tổng hợp dệt chìm hoạ tiết",
    "Organza dệt chìm hoạ tiết",
    "Vải tổng hợp dệt hoạ tiết kim sa",
    "Gấm dệt họa tiết cùng lót lụa tổng hợp",
]


def demo_normalize_material() -> list[NormalizedMaterial]:
    return [normalize_material(item) for item in MATERIAL_DEMO_INPUTS]
