from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "color.csv"

COLOR_NAME_COLUMN = "color_name"
COLOR_GROUP_COLUMN = "color_group"

CANONICAL_COLOR_CODES = {
    "Be": "#D8C3A5",
    "Cam": "#F28C28",
    "Hồng cam": "#F4A08A",
    "Hồng": "#E88DA1",
    "Hồng nhạt": "#F6C1CC",
    "Hồng phấn": "#F4B6C2",
    "Hồng phấn nhạt": "#F8D7DF",
    "Hồng sen": "#D96C8A",
    "Hồng đậm": "#C75A7C",
    "Kem": "#F3E5C8",
    "Trắng kem": "#F8F1E3",
    "Vàng nâu": "#B88A3B",
    "Trắng": "#FFFFFF",
    "Trắng xám": "#E5E5E0",
    "Hồng tím": "#C97BB8",
    "Tím": "#8E6BBE",
    "Tím nhạt": "#C8B4E3",
    "Vàng": "#E3B23C",
    "Vàng kem": "#F0D98A",
    "Vàng nhạt": "#F6E27A",
    "Xanh": "#3F7FBF",
    "Xanh biển": "#2F6FA3",
    "Xanh biển nhạt": "#8CBFD9",
    "Xanh coban": "#0047AB",
    "Xanh cốm": "#9DC183",
    "Xanh lam": "#1F5AA6",
    "Xanh lá": "#4F8A3C",
    "Xanh lục": "#2E8B57",
    "Xanh ngọc": "#48A9A6",
    "Xanh oliu": "#708238",
    "Xanh xám": "#7E8F99",
    "Xám bạc": "#BFC5CC",
    "Đen": "#1F1F1F",
    "Hồng đỗ": "#A63D57",
    "Đỏ": "#C62828",
    "Đỏ mận": "#7B1E3A",
    "Đỏ đậm": "#8B1E2D",
}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"null", "n/a", "na", "none"}:
        return None

    return text


def read_transformed_product_lines(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)

    required_columns = {COLOR_NAME_COLUMN, COLOR_GROUP_COLUMN}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    return df


def build_master_color(df: pd.DataFrame) -> pd.DataFrame:
    working_df = df[[COLOR_NAME_COLUMN, COLOR_GROUP_COLUMN]].copy()
    working_df[COLOR_NAME_COLUMN] = working_df[COLOR_NAME_COLUMN].map(
        normalize_text
    )
    working_df[COLOR_GROUP_COLUMN] = working_df[COLOR_GROUP_COLUMN].map(
        normalize_text
    )

    working_df = working_df.dropna(subset=[COLOR_NAME_COLUMN])
    working_df = working_df.drop_duplicates(
        subset=[COLOR_NAME_COLUMN, COLOR_GROUP_COLUMN]
    ).reset_index(drop=True)

    master_df = (
        working_df.rename(
            columns={
                COLOR_NAME_COLUMN: "color_name",
                COLOR_GROUP_COLUMN: "color_group",
            }
        )
        .sort_values(by=["color_group", "color_name"], kind="stable")
        .reset_index(drop=True)
    )
    master_df["color_code"] = master_df["color_name"].map(CANONICAL_COLOR_CODES)

    missing_color_codes = master_df.loc[
        master_df["color_code"].isna(), "color_name"
    ].tolist()
    if missing_color_codes:
        raise ValueError(
            "Missing canonical color_code mapping for colors: "
            f"{missing_color_codes}"
        )

    master_df = master_df[["color_name", "color_group", "color_code"]]

    return master_df


def save_master_color(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print(f"Created file: {output_file}")
    print(f"Total master colors: {len(df)}")

    if not df.empty:
        print("\nPreview:")
        print(df.head(10).to_string(index=False))


def main() -> None:
    transformed_df = read_transformed_product_lines(INPUT_FILE)
    master_df = build_master_color(transformed_df)
    save_master_color(master_df, OUTPUT_FILE)
    print_summary(master_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()
