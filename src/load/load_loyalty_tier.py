from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.file_path import LOYALTY_TIER_FILE
from src.utils.load_connection import (
    add_loader_connection_args,
    build_connection_kwargs,
    describe_connection,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


BATCH_SIZE = 500
ALLOWED_TIER_IDS = {"SILVER", "GOLD", "DIAMOND", "MVG"}


def normalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def normalize_tier_id(value: object) -> str:
    tier_id = normalize_text(value)
    if not tier_id:
        raise ValueError("loyalty_tier_id must not be null")

    normalized = tier_id.upper()
    if normalized not in ALLOWED_TIER_IDS:
        raise ValueError(
            f"Invalid loyalty_tier_id: {tier_id!r}. "
            f"Expected one of {sorted(ALLOWED_TIER_IDS)}"
        )

    return normalized


def normalize_decimal(value: object, field_name: str) -> Decimal | None:
    text = normalize_text(value)
    if text is None:
        return None

    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}") from exc

    if number < 0:
        raise ValueError(f"{field_name} must be >= 0, got {number}")

    return number


def normalize_smallint(value: object, field_name: str) -> int:
    text = normalize_text(value)
    if text is None:
        raise ValueError(f"{field_name} must not be null")

    try:
        number = int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}") from exc

    if number < 0 or number > 32767:
        raise ValueError(f"{field_name} must be between 0 and 32767, got {number}")

    return number


def read_master_loyalty_tiers(input_file: Path) -> pd.DataFrame:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    df = pd.read_csv(input_file)
    required_columns = {
        "loyalty_tier_id",
        "tier_name",
        "min_accumulated_amount",
        "maintain_amount",
        "birthday_voucher_value",
        "free_shipping_quota",
        "free_tailor_quota",
        "special_gift",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {input_file}: {sorted(missing_columns)}"
        )

    working_df = df.copy()
    working_df["loyalty_tier_id"] = working_df["loyalty_tier_id"].map(normalize_tier_id)
    working_df["tier_name"] = working_df["tier_name"].map(normalize_text)
    working_df["min_accumulated_amount"] = working_df["min_accumulated_amount"].map(
        lambda value: normalize_decimal(value, "min_accumulated_amount")
    )
    working_df["maintain_amount"] = working_df["maintain_amount"].map(
        lambda value: normalize_decimal(value, "maintain_amount")
    )
    working_df["birthday_voucher_value"] = working_df["birthday_voucher_value"].map(
        lambda value: normalize_decimal(value, "birthday_voucher_value")
    )
    working_df["free_shipping_quota"] = working_df["free_shipping_quota"].map(
        lambda value: normalize_smallint(value, "free_shipping_quota")
    )
    working_df["free_tailor_quota"] = working_df["free_tailor_quota"].map(
        lambda value: normalize_smallint(value, "free_tailor_quota")
    )
    working_df["special_gift"] = working_df["special_gift"].map(normalize_text)

    working_df = working_df.dropna(
        subset=[
            "loyalty_tier_id",
            "tier_name",
            "min_accumulated_amount",
            "maintain_amount",
            "free_shipping_quota",
            "free_tailor_quota",
        ]
    )
    working_df = (
        working_df.sort_values(by=["loyalty_tier_id"], kind="stable")
        .drop_duplicates(subset=["loyalty_tier_id"], keep="first")
        .reset_index(drop=True)
    )

    return working_df[
        [
            "loyalty_tier_id",
            "tier_name",
            "min_accumulated_amount",
            "maintain_amount",
            "birthday_voucher_value",
            "free_shipping_quota",
            "free_tailor_quota",
            "special_gift",
        ]
    ]


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def build_loyalty_tier_payload(row: dict) -> dict:
    return {
        "loyalty_tier_id": normalize_tier_id(row["loyalty_tier_id"]),
        "tier_name": normalize_text(row["tier_name"]),
        "min_accumulated_amount": normalize_decimal(
            row["min_accumulated_amount"],
            "min_accumulated_amount",
        ),
        "maintain_amount": normalize_decimal(
            row["maintain_amount"],
            "maintain_amount",
        ),
        "birthday_voucher_value": normalize_decimal(
            row["birthday_voucher_value"],
            "birthday_voucher_value",
        ),
        "free_shipping_quota": normalize_smallint(
            row["free_shipping_quota"],
            "free_shipping_quota",
        ),
        "free_tailor_quota": normalize_smallint(
            row["free_tailor_quota"],
            "free_tailor_quota",
        ),
        "special_gift": normalize_text(row["special_gift"]),
    }


def fetch_existing_loyalty_tiers(connection: psycopg.Connection) -> dict[str, dict]:
    query = """
        SELECT
            loyalty_tier_id,
            tier_name,
            min_accumulated_amount,
            maintain_amount,
            birthday_voucher_value,
            free_shipping_quota,
            free_tailor_quota,
            special_gift
        FROM iam.loyalty_tier
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    existing_by_tier_id: dict[str, dict] = {}
    for row in rows:
        tier_id = normalize_text(row.get("loyalty_tier_id"))
        if tier_id and tier_id not in existing_by_tier_id:
            existing_by_tier_id[tier_id] = row

    return existing_by_tier_id


def build_update_payload(incoming: dict, existing: dict) -> dict | None:
    payload = build_loyalty_tier_payload(incoming)
    changed_fields: dict = {}

    for key, value in payload.items():
        existing_value = existing.get(key) if key in {
            "min_accumulated_amount",
            "maintain_amount",
            "birthday_voucher_value",
            "free_shipping_quota",
            "free_tailor_quota",
        } else normalize_text(existing.get(key))
        incoming_value = value if key in {
            "min_accumulated_amount",
            "maintain_amount",
            "birthday_voucher_value",
            "free_shipping_quota",
            "free_tailor_quota",
        } else normalize_text(value)

        if existing_value != incoming_value:
            changed_fields[key] = value

    return changed_fields or None


def insert_loyalty_tier_batch(
    connection: psycopg.Connection,
    records: list[dict],
) -> int:
    if not records:
        return 0

    query = """
        INSERT INTO iam.loyalty_tier (
            loyalty_tier_id,
            tier_name,
            min_accumulated_amount,
            maintain_amount,
            birthday_voucher_value,
            free_shipping_quota,
            free_tailor_quota,
            special_gift
        )
        VALUES (
            %(loyalty_tier_id)s,
            %(tier_name)s,
            %(min_accumulated_amount)s,
            %(maintain_amount)s,
            %(birthday_voucher_value)s,
            %(free_shipping_quota)s,
            %(free_tailor_quota)s,
            %(special_gift)s
        )
    """

    with connection.cursor() as cursor:
        cursor.executemany(query, records)

    return len(records)


def update_loyalty_tier(
    connection: psycopg.Connection,
    loyalty_tier_id: str,
    update_payload: dict,
) -> None:
    assignments = ", ".join(f"{column} = %({column})s" for column in update_payload)
    query = f"""
        UPDATE iam.loyalty_tier
        SET {assignments}, updated_at = NOW()
        WHERE loyalty_tier_id = %(loyalty_tier_id)s
    """

    params = dict(update_payload)
    params["loyalty_tier_id"] = loyalty_tier_id

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def sync_loyalty_tiers(
    loyalty_tiers_df: pd.DataFrame,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        existing_by_tier_id = fetch_existing_loyalty_tiers(connection)

        inserts: list[dict] = []
        updates: list[tuple[str, dict]] = []

        for record in loyalty_tiers_df.to_dict(orient="records"):
            tier_id = record["loyalty_tier_id"]
            existing = existing_by_tier_id.get(tier_id)

            if existing is None:
                inserts.append(build_loyalty_tier_payload(record))
                continue

            update_payload = build_update_payload(record, existing)
            if update_payload is not None:
                updates.append((tier_id, update_payload))

        inserted_count = 0
        updated_count = 0

        for insert_batch in chunk_records(inserts, BATCH_SIZE):
            inserted_count += insert_loyalty_tier_batch(connection, insert_batch)

        for tier_id, update_payload in updates:
            update_loyalty_tier(connection, tier_id, update_payload)
            updated_count += 1

        connection.commit()

    skipped_count = len(loyalty_tiers_df) - inserted_count - updated_count
    return inserted_count, updated_count, skipped_count


def print_summary(
    loyalty_tiers_df: pd.DataFrame,
    connection_label: str,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
) -> None:
    print(f"Target database: {connection_label}")
    print(f"Input file: {LOYALTY_TIER_FILE}")
    print(f"Total master loyalty tiers: {len(loyalty_tiers_df)}")
    print(f"Inserted: {inserted_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")

    if not loyalty_tiers_df.empty:
        print("\nPreview:")
        print(loyalty_tiers_df.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert/update master loyalty tiers into iam.loyalty_tier."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    loyalty_tiers_df = read_master_loyalty_tiers(LOYALTY_TIER_FILE)
    inserted_count, updated_count, skipped_count = sync_loyalty_tiers(
        loyalty_tiers_df,
        connection_kwargs,
    )
    print_summary(
        loyalty_tiers_df=loyalty_tiers_df,
        connection_label=describe_connection(connection_kwargs),
        inserted_count=inserted_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


if __name__ == "__main__":
    main()
