from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "color.csv"

COLOR_NAME_COLUMN = "color_name"
COLOR_GROUP_COLUMN = "color_group"


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
