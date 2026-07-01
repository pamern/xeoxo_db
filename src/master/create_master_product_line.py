from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "product_line.csv"

REQUIRED_COLUMNS = {
    "collection_name",
    "product_name",
    "slug",
    "description",
    "material_name",
    "short_description",
    "design_style",
    "color_name",
    "usage_context",
    "error",
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
    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    return df


def build_master_product_line(df: pd.DataFrame) -> pd.DataFrame:
    working_df = df.copy()

    for column in REQUIRED_COLUMNS:
        working_df[column] = working_df[column].map(normalize_text)

    working_df = working_df[working_df["error"].isna()].copy()
    working_df = working_df.dropna(
        subset=["collection_name", "product_name", "slug", "material_name"]
    )

    master_df = pd.DataFrame(
        {
            "collection_name": working_df["collection_name"],
            "color_name": working_df["color_name"],
            "line_name": working_df["product_name"],
            "description": working_df["description"],
            "material_name": working_df["material_name"],
            "design_style": working_df["design_style"],
            "features": working_df["short_description"],
            "usage_context": working_df["usage_context"],
            "status": "ACTIVE",
            "is_featured": False,
            "slug": working_df["slug"],
        }
    )

    master_df = (
        master_df.sort_values(by=["collection_name", "line_name", "slug"], kind="stable")
        .drop_duplicates(subset=["slug"], keep="first")
        .drop(columns=["slug"])
        .reset_index(drop=True)
    )

    return master_df


def save_master_product_line(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print(f"Created file: {output_file}")
    print(f"Total master product lines: {len(df)}")

    if not df.empty:
        print("\nPreview:")
        print(df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    transformed_df = read_transformed_product_lines(INPUT_FILE)
    master_df = build_master_product_line(transformed_df)
    save_master_product_line(master_df, OUTPUT_FILE)
    print_summary(master_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()
