from __future__ import annotations

from pathlib import Path
import sys
import unicodedata

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection_db import get_postgres_connection_kwargs

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "product_line.csv"
BATCH_SIZE = 500
SET_CATEGORY_MAP = {
    "set ha chi": ["Áo sơ mi", "Chân váy"],
    "set ha nhu": ["Áo sơ mi", "Chân váy"],
}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def fold_text(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(
        char for char in folded
        if unicodedata.category(char) != "Mn"
    )

    return " ".join(folded.replace("đ", "d").split())


def read_master_product_lines(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "collection_name",
        "line_name",
        "design_style",
        "usage_context",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    for column in required_columns:
        working_df[column] = working_df[column].map(normalize_text)

    working_df = working_df.dropna(subset=["collection_name", "line_name"])
    working_df = (
        working_df.sort_values(by=["collection_name", "line_name"], kind="stable")
        .drop_duplicates(subset=["collection_name", "line_name"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "collection_name",
            "line_name",
            "design_style",
            "usage_context",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def infer_line_categories(row: dict) -> list[str]:
    line_name = normalize_text(row.get("line_name")) or ""
    design_style = normalize_text(row.get("design_style")) or ""
    usage_context = normalize_text(row.get("usage_context")) or ""

    line_fold = fold_text(line_name)
    style_fold = fold_text(design_style)
    usage_fold = fold_text(usage_context)
    combined_fold = " | ".join(
        part for part in [line_fold, style_fold, usage_fold] if part
    )
    line_lower = line_name.lower()
    style_lower = design_style.lower()
    usage_lower = usage_context.lower()
    combined_lower = " | ".join(
        part for part in [line_lower, style_lower, usage_lower] if part
    )

    if line_fold in SET_CATEGORY_MAP:
        return SET_CATEGORY_MAP[line_fold]

    if line_lower.startswith("quần") or line_fold.startswith("quan"):
        return ["Quần"]

    if line_lower.startswith("chân váy") or line_fold.startswith("chan vay"):
        return ["Chân váy"]

    if (
        line_lower.startswith("yếm")
        or line_lower.startswith("áo yếm")
        or "cổ yếm" in combined_lower
        or style_fold.startswith("yem")
    ):
        return ["Áo yếm"]

    if "áo choàng" in combined_lower or "ao choang" in combined_fold:
        return ["Áo choàng"]

    if "áo dài" in combined_lower or "ao dai" in combined_fold:
        if any(keyword in combined_fold for keyword in ["4 ta", "bon ta"]):
            return ["Áo dài 4 tà"]
        if any(keyword in combined_fold for keyword in ["2 lop", "hai lop"]):
            return ["Áo dài 2 lớp"]
        if any(keyword in combined_fold for keyword in ["2 ta", "hai ta"]):
            return ["Áo dài 2 tà"]
        if "chiet eo" in combined_fold:
            return ["Áo dài chiết eo"]
        if "tay ngan" in combined_fold:
            return ["Áo dài tay ngắn"]
        if "tay loe lung" in combined_fold:
            return ["Áo dài suông tay loe lửng"]
        if "tay loe dai" in combined_fold:
            return ["Áo dài suông tay loe dài"]
        if "vat cheo" in combined_fold or "vat cuc cheo" in combined_fold:
            return ["Áo dài vạt chéo"]
        if "cuc thang" in combined_fold and "dang ngan" in combined_fold:
            return ["Áo dài ngắn cúc thẳng"]
        if "cuc lech" in combined_fold and "dang ngan" in combined_fold:
            return ["Áo dài ngắn cúc lệnh"]
        if "cuc lech" in combined_fold:
            return ["Áo dài cúc lệch"]
        if "le cuoi" in combined_fold:
            if "nam" in combined_fold:
                return ["Áo dài cưới nam"]
            return ["Áo dài cưới nữ"]
        return ["Áo dài"]

    if (
        line_lower.startswith("đầm")
        or line_fold.startswith("dam")
        or "đầm " in combined_lower
        or "dam " in combined_fold
        or "maxi" in combined_fold
    ):
        if "2 dây" in combined_lower or "2 day" in combined_fold:
            return ["Đầm 2 dây"]
        if any(
            keyword in combined_fold
            for keyword in ["da hoi", "tiec", "su kien", "trong dai", "le cuoi"]
        ):
            return ["Đầm dạ hội"]
        if any(
            keyword in combined_fold
            for keyword in ["dao pho", "di choi", "hang ngay", "thuong ngay", "di lam", "cuoi tuan"]
        ):
            return ["Đầm dạo phố"]
        return ["Đầm dài"]

    if line_lower.startswith("áo") or line_fold.startswith("ao "):
        if any(keyword in combined_lower for keyword in ["yếm", "cổ yếm", "hở lưng"]):
            return ["Áo yếm"]
        return ["Áo sơ mi"]

    return []


def fetch_existing_categories(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            category_id,
            category_name
        FROM catalog.category
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        category_name = normalize_text(row.get("category_name"))
        if category_name and category_name not in existing_by_name:
            existing_by_name[category_name] = row

    return existing_by_name


def fetch_existing_product_lines(connection: psycopg.Connection) -> dict[tuple[str, str], dict]:
    query = """
        SELECT
            pl.product_line_id,
            pl.line_name,
            c.collection_name
        FROM catalog.product_line pl
        LEFT JOIN catalog.collection c
            ON c.collection_id = pl.collection_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        collection_name = normalize_text(row.get("collection_name"))
        line_name = normalize_text(row.get("line_name"))
        if not collection_name or not line_name:
            continue

        key = (collection_name, line_name)
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def fetch_existing_line_categories(connection: psycopg.Connection) -> dict[tuple[int, int], dict]:
    query = """
        SELECT
            category_id,
            product_line_id,
            is_primary
        FROM catalog.line_category
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_pair: dict[tuple[int, int], dict] = {}
    for row in rows:
        category_id = row.get("category_id")
        product_line_id = row.get("product_line_id")
        if category_id is None or product_line_id is None:
            continue

        pair = (category_id, product_line_id)
        if pair not in existing_by_pair:
            existing_by_pair[pair] = row

    return existing_by_pair


def insert_line_category_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.line_category (
            category_id,
            product_line_id,
            is_primary
        )
        VALUES (
            %(category_id)s,
            %(product_line_id)s,
            %(is_primary)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_line_category(
    connection: psycopg.Connection,
    category_id: int,
    product_line_id: int,
    is_primary: bool,
) -> None:
    query = """
        UPDATE catalog.line_category
        SET is_primary = %(is_primary)s,
            updated_at = NOW()
        WHERE category_id = %(category_id)s
          AND product_line_id = %(product_line_id)s
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            {
                "category_id": category_id,
                "product_line_id": product_line_id,
                "is_primary": is_primary,
            },
        )


def sync_line_categories(product_lines_df: pd.DataFrame) -> tuple[int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        categories_by_name = fetch_existing_categories(connection)
        product_lines_by_key = fetch_existing_product_lines(connection)
        existing_pairs = fetch_existing_line_categories(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, int, bool]] = []
        unresolved_product_lines: list[tuple[str, str]] = []
        unresolved_categories: list[tuple[str, str, tuple[str, ...]]] = []
        skipped_count = 0

        for record in product_lines_df.to_dict(orient="records"):
            collection_name = normalize_text(record["collection_name"])
            line_name = normalize_text(record["line_name"])

            product_line = product_lines_by_key.get((collection_name, line_name))
            if product_line is None:
                unresolved_product_lines.append((collection_name or "", line_name or ""))
                continue

            category_names = infer_line_categories(record)
            if not category_names:
                unresolved_categories.append(
                    (
                        collection_name or "",
                        line_name or "",
                        (),
                    )
                )
                continue

            missing_category_names = tuple(
                category_name
                for category_name in category_names
                if category_name not in categories_by_name
            )
            if missing_category_names:
                unresolved_categories.append(
                    (
                        collection_name or "",
                        line_name or "",
                        missing_category_names,
                    )
                )
                continue

            for index, category_name in enumerate(category_names):
                category_id = categories_by_name[category_name]["category_id"]
                product_line_id = product_line["product_line_id"]
                pair = (category_id, product_line_id)
                is_primary = index == 0

                existing_pair = existing_pairs.get(pair)
                if existing_pair is not None:
                    if bool(existing_pair.get("is_primary")) != is_primary:
                        updates.append((category_id, product_line_id, is_primary))
                    skipped_count += 1
                    continue

                inserts.append(
                    {
                        "category_id": category_id,
                        "product_line_id": product_line_id,
                        "is_primary": is_primary,
                    }
                )
                existing_pairs[pair] = {
                    "category_id": category_id,
                    "product_line_id": product_line_id,
                    "is_primary": is_primary,
                }

        if unresolved_product_lines:
            raise ValueError(
                "Unable to resolve product_line_id for line_category rows: "
                f"{sorted(unresolved_product_lines)}"
            )

        if unresolved_categories:
            raise ValueError(
                "Unable to infer/resolve categories for product lines: "
                f"{sorted(unresolved_categories)}"
            )

        inserted_count = 0
        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_line_category_batch(connection, insert_batch)

        for category_id, product_line_id, is_primary in updates:
            update_line_category(
                connection=connection,
                category_id=category_id,
                product_line_id=product_line_id,
                is_primary=is_primary,
            )

        connection.commit()

    return inserted_count, skipped_count


def print_summary(
    product_lines_df: pd.DataFrame,
    inserted_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total source product lines: {len(product_lines_df)}")
    print(f"Inserted line_category rows: {inserted_count}")
    print(f"Skipped existing rows: {skipped_count}")

    if not product_lines_df.empty:
        preview_df = product_lines_df.copy()
        preview_df["inferred_categories"] = preview_df.apply(
            lambda row: ", ".join(infer_line_categories(row.to_dict())),
            axis=1,
        )
        print("\nPreview:")
        print(
            preview_df[
                ["collection_name", "line_name", "design_style", "inferred_categories"]
            ].head(10).to_string(index=False)
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    product_lines_df = read_master_product_lines(INPUT_FILE)
    inserted_count, skipped_count = sync_line_categories(product_lines_df)
    print_summary(
        product_lines_df=product_lines_df,
        inserted_count=inserted_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
