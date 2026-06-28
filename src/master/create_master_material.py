from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = PROJECT_ROOT / "data" / "staging" / "product_lines.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "master"
OUTPUT_FILE = OUTPUT_DIR / "material.csv"

MATERIAL_COLUMN = "material_name"
DESCRIPTION_COLUMN = "short_description"


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

    if MATERIAL_COLUMN not in df.columns:
        raise ValueError(
            f"Missing required column '{MATERIAL_COLUMN}' in {input_file}"
        )

    if DESCRIPTION_COLUMN not in df.columns:
        raise ValueError(
            f"Missing required column '{DESCRIPTION_COLUMN}' in {input_file}"
        )

    return df


def merge_descriptions(series: pd.Series) -> str | None:
    descriptions: list[str] = []

    for value in series:
        normalized = normalize_text(value)
        if normalized and normalized not in descriptions:
            descriptions.append(normalized)

    if not descriptions:
        return None

    return " | ".join(descriptions)


def build_master_material(df: pd.DataFrame) -> pd.DataFrame:
    working_df = df[[MATERIAL_COLUMN, DESCRIPTION_COLUMN]].copy()
    working_df[MATERIAL_COLUMN] = working_df[MATERIAL_COLUMN].map(normalize_text)
    working_df[DESCRIPTION_COLUMN] = working_df[DESCRIPTION_COLUMN].map(
        normalize_text
    )

    working_df = working_df.dropna(subset=[MATERIAL_COLUMN])

    master_df = (
        working_df.groupby(MATERIAL_COLUMN, dropna=False)[DESCRIPTION_COLUMN]
        .agg(merge_descriptions)
        .reset_index()
        .rename(
            columns={
                MATERIAL_COLUMN: "material_name",
                DESCRIPTION_COLUMN: "description",
            }
        )
        .sort_values(by="material_name", kind="stable")
        .reset_index(drop=True)
    )

    return master_df


def save_master_material(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")


def print_summary(df: pd.DataFrame, output_file: Path) -> None:
    print(f"Created file: {output_file}")
    print(f"Total master materials: {len(df)}")

    if not df.empty:
        print("\nPreview:")
        print(df.head(10).to_string(index=False))


def main() -> None:
    transformed_df = read_transformed_product_lines(INPUT_FILE)
    master_df = build_master_material(transformed_df)
    save_master_material(master_df, OUTPUT_FILE)
    print_summary(master_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()
