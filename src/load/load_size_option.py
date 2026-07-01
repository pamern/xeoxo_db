from __future__ import annotations

from pathlib import Path
import sys

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


INPUT_FILE = PROJECT_ROOT / "data" / "master" / "size_option.csv"
BATCH_SIZE = 500


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def normalize_display_order(value: object) -> int:
    if value is None or pd.isna(value):
        raise ValueError("display_order must not be null")

    try:
        display_order = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid display_order value: {value!r}") from exc

    if display_order <= 0:
        raise ValueError(f"display_order must be > 0, got {display_order}")

    return display_order


def read_master_size_options(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "chart_name",
        "size_name",
        "display_order",
        "description",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["chart_name"] = working_df["chart_name"].map(normalize_text)
    working_df["size_name"] = working_df["size_name"].map(normalize_text)
    working_df["description"] = working_df["description"].map(normalize_text)
    working_df["display_order"] = working_df["display_order"].map(
        normalize_display_order
    )

    working_df = working_df.dropna(subset=["chart_name", "size_name"])
    working_df = (
        working_df.sort_values(
            by=["chart_name", "display_order", "size_name"],
            kind="stable",
        )
        .drop_duplicates(
            subset=["chart_name", "size_name"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return working_df[
        [
            "chart_name",
            "size_name",
            "display_order",
            "description",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def fetch_existing_size_charts(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            size_chart_id,
            chart_name
        FROM catalog.size_chart
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_name: dict[str, dict] = {}
    for row in rows:
        chart_name = normalize_text(row.get("chart_name"))
        if chart_name and chart_name not in existing_by_name:
            existing_by_name[chart_name] = row

    return existing_by_name


def fetch_existing_size_options(
    connection: psycopg.Connection,
) -> dict[tuple[int, str], dict]:
    query = """
        SELECT
            size_option_id,
            size_chart_id,
            size_name,
            display_order,
            description
        FROM catalog.size_option
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_key: dict[tuple[int, str], dict] = {}
    for row in rows:
        size_chart_id = row.get("size_chart_id")
        size_name = normalize_text(row.get("size_name"))
        if size_chart_id is None or not size_name:
            continue

        key = (int(size_chart_id), size_name)
        if key not in existing_by_key:
            existing_by_key[key] = row

    return existing_by_key


def build_size_option_payload(
    row: dict,
    size_chart_id: int,
) -> dict:
    return {
        "size_chart_id": size_chart_id,
        "size_name": normalize_text(row["size_name"]),
        "display_order": normalize_display_order(row["display_order"]),
        "description": normalize_text(row["description"]),
    }


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    changed_fields: dict = {}

    for key, value in incoming.items():
        if key in {"size_chart_id", "display_order"}:
            existing_value = existing.get(key)
            incoming_value = value
        else:
            existing_value = normalize_text(existing.get(key))
            incoming_value = normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_size_option_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO catalog.size_option (
            size_chart_id,
            size_name,
            display_order,
            description
        )
        VALUES (
            %(size_chart_id)s,
            %(size_name)s,
            %(display_order)s,
            %(description)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_size_option(
    connection: psycopg.Connection,
    size_option_id: int,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE catalog.size_option
        SET {assignments}, updated_at = NOW()
        WHERE size_option_id = %(size_option_id)s
    """

    params = dict(update_payload)
    params["size_option_id"] = size_option_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_size_options(size_options_df: pd.DataFrame) -> tuple[int, int, int]:
    connection_kwargs = get_postgres_connection_kwargs()

    with psycopg.connect(**connection_kwargs) as connection:
        size_charts_by_name = fetch_existing_size_charts(connection)
        existing_size_options = fetch_existing_size_options(connection)

        inserts: list[dict] = []
        updates: list[tuple[int, dict]] = []
        unresolved_size_charts: list[tuple[str, str]] = []

        for record in size_options_df.to_dict(orient="records"):
            chart_name = normalize_text(record["chart_name"])
            size_name = normalize_text(record["size_name"])

            size_chart = size_charts_by_name.get(chart_name)
            if size_chart is None:
                unresolved_size_charts.append((chart_name or "", size_name or ""))
                continue

            payload = build_size_option_payload(
                row=record,
                size_chart_id=size_chart["size_chart_id"],
            )
            key = (payload["size_chart_id"], payload["size_name"])
            existing = existing_size_options.get(key)

            if existing is None:
                inserts.append(payload)
                continue

            update_payload = build_update_payload(payload, existing)
            if update_payload is not None:
                updates.append((existing["size_option_id"], update_payload))

        if unresolved_size_charts:
            raise ValueError(
                "Unable to resolve size_chart_id for size options: "
                f"{sorted(unresolved_size_charts)}"
            )

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_size_option_batch(connection, insert_batch)

        for size_option_id, update_payload in updates:
            update_size_option(connection, size_option_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(size_options_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    size_options_df: pd.DataFrame,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Input file: {INPUT_FILE}")
    print(f"Total master size options: {len(size_options_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not size_options_df.empty:
        print("\nPreview:")
        print(size_options_df.head(10).to_string(index=False))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    size_options_df = read_master_size_options(INPUT_FILE)
    inserted_count, updated_count, skipped_count = sync_size_options(size_options_df)
    print_summary(
        size_options_df=size_options_df,
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
