from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import random
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.file_path import INVENTORY_FILE, PRODUCT_LINE_FILE, create_dir
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


PARTIAL_OUT_RATIO = 0.30
IN_STOCK_RATIO = 0.60
FULL_OUT_RATIO = 0.10
DEFAULT_MIN_QUANTITY = 1
DEFAULT_MAX_QUANTITY = 30
DEFAULT_RANDOM_SEED = 20260708
BATCH_SIZE = 500
COLLECTION_MASTER_FILE = PROJECT_ROOT / "data" / "master" / "collections.csv"
SELLABLE_VARIANT_STATUSES = {
    "ACTIVE",
    "OUT_OF_STOCK",
    "PREORDER",
    "COMING_SOON",
}


@dataclass(frozen=True)
class BranchRecord:
    branch_id: int
    branch_name: str


@dataclass(frozen=True)
class VariantRecord:
    collection_id: int
    collection_name: str
    collection_slug: str | None
    product_line_id: int
    line_name: str
    product_line_slug: str | None
    component_id: int
    variant_id: int
    size_option_id: int | None
    size_name: str | None


@dataclass(frozen=True)
class ProductLineGroup:
    collection_id: int
    collection_name: str
    collection_slug: str | None
    product_line_id: int
    line_name: str
    product_line_slug: str | None
    variants: tuple[VariantRecord, ...]

    @property
    def variant_count(self) -> int:
        return len(self.variants)

    def inventory_row_weight(self, branch_count: int) -> int:
        return self.variant_count * branch_count

    @property
    def supports_partial_out(self) -> bool:
        return self.variant_count >= 2


@dataclass(frozen=True)
class InventorySeedRecord:
    branch_id: int
    branch_name: str
    collection_id: int
    collection_name: str
    collection_slug: str | None
    product_line_id: int
    line_name: str
    product_line_slug: str | None
    inventory_state: str
    variant_id: int
    component_id: int
    size_option_id: int | None
    size_name: str | None
    quantity: int


def chunk_records(records: list[dict], size: int) -> list[list[dict]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def normalize_text(value: object) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"null", "none", "n/a", "na"}:
        return None

    return text


def normalize_csv_fieldnames(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        return []
    return [name.lstrip("\ufeff").strip() for name in fieldnames]


def read_collection_slug_map(input_file: Path) -> dict[str, str]:
    if not input_file.exists():
        return {}

    with input_file.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        reader.fieldnames = normalize_csv_fieldnames(reader.fieldnames)

        if not reader.fieldnames or "collection_name" not in reader.fieldnames:
            return {}
        if "slug" not in reader.fieldnames:
            return {}

        slug_map: dict[str, str] = {}
        for row in reader:
            collection_name = normalize_text(row.get("collection_name"))
            slug = normalize_text(row.get("slug"))
            if not collection_name or not slug:
                continue
            slug_map.setdefault(collection_name, slug)

    return slug_map


def read_product_line_slug_map(input_file: Path) -> dict[str, str]:
    if not input_file.exists():
        return {}

    with input_file.open("r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        reader.fieldnames = normalize_csv_fieldnames(reader.fieldnames)

        if not reader.fieldnames or "line_name" not in reader.fieldnames:
            return {}
        if "slug" not in reader.fieldnames:
            return {}

        slug_map: dict[str, str] = {}
        for row in reader:
            line_name = normalize_text(row.get("line_name"))
            slug = normalize_text(row.get("slug"))
            if not line_name or not slug:
                continue
            slug_map.setdefault(line_name, slug)

    return slug_map


def parse_branch_ids(raw_values: list[str] | None) -> list[int] | None:
    if not raw_values:
        return None

    branch_ids: list[int] = []
    for raw_value in raw_values:
        for part in raw_value.split(","):
            text = part.strip()
            if not text:
                continue
            branch_ids.append(int(text))

    return sorted(set(branch_ids))


def parse_collection_ids(raw_values: list[str] | None) -> list[int] | None:
    if not raw_values:
        return None

    collection_ids: list[int] = []
    for raw_value in raw_values:
        for part in raw_value.split(","):
            text = part.strip()
            if not text:
                continue
            collection_ids.append(int(text))

    return sorted(set(collection_ids))


def compute_target_row_counts(total_rows: int) -> dict[str, int]:
    if total_rows <= 0:
        return {
            "PARTIAL_OUT": 0,
            "IN_STOCK": 0,
            "FULL_OUT": 0,
        }

    # Dùng round để bám gần nhất với tỷ lệ 30% / 60% / 10%.
    partial_rows = round(total_rows * PARTIAL_OUT_RATIO)
    full_out_rows = round(total_rows * FULL_OUT_RATIO)

    if partial_rows + full_out_rows > total_rows:
        overflow = partial_rows + full_out_rows - total_rows
        if partial_rows >= full_out_rows:
            partial_rows -= overflow
        else:
            full_out_rows -= overflow

    in_stock_rows = total_rows - partial_rows - full_out_rows

    return {
        "PARTIAL_OUT": max(partial_rows, 0),
        "IN_STOCK": max(in_stock_rows, 0),
        "FULL_OUT": max(full_out_rows, 0),
    }


def choose_groups_for_target(
    groups: list[ProductLineGroup],
    branch_count: int,
    target_rows: int,
    rng: random.Random,
) -> set[int]:
    if target_rows <= 0 or not groups:
        return set()

    best_selected_ids: set[int] = set()
    best_diff = float("inf")
    attempts = max(12, len(groups) * 4)

    for _ in range(attempts):
        shuffled = list(groups)
        rng.shuffle(shuffled)

        total_rows = 0
        selected_ids: set[int] = set()
        current_diff = abs(target_rows)
        improved = True

        while improved:
            improved = False
            for group in shuffled:
                if group.product_line_id in selected_ids:
                    continue

                candidate_total = total_rows + group.inventory_row_weight(branch_count)
                candidate_diff = abs(target_rows - candidate_total)
                if candidate_diff <= current_diff or total_rows < target_rows:
                    selected_ids.add(group.product_line_id)
                    total_rows = candidate_total
                    current_diff = candidate_diff
                    improved = True

        if current_diff < best_diff:
            best_diff = current_diff
            best_selected_ids = selected_ids
            if best_diff == 0:
                break

    return best_selected_ids


def assign_inventory_states(
    groups: list[ProductLineGroup],
    branch_count: int,
    rng: random.Random,
) -> dict[int, str]:
    if not groups:
        return {}

    total_rows = sum(group.inventory_row_weight(branch_count) for group in groups)
    targets = compute_target_row_counts(total_rows)

    full_out_ids = choose_groups_for_target(
        groups=groups,
        branch_count=branch_count,
        target_rows=targets["FULL_OUT"],
        rng=rng,
    )

    remaining_groups = [
        group for group in groups if group.product_line_id not in full_out_ids
    ]
    partial_candidates = [
        group for group in remaining_groups if group.supports_partial_out
    ]
    partial_ids = choose_groups_for_target(
        groups=partial_candidates,
        branch_count=branch_count,
        target_rows=targets["PARTIAL_OUT"],
        rng=rng,
    )

    states: dict[int, str] = {}
    for group in groups:
        if group.product_line_id in full_out_ids:
            states[group.product_line_id] = "FULL_OUT"
        elif group.product_line_id in partial_ids:
            states[group.product_line_id] = "PARTIAL_OUT"
        else:
            states[group.product_line_id] = "IN_STOCK"

    return states


def generate_quantities_for_product_line(
    group: ProductLineGroup,
    state: str,
    min_quantity: int,
    max_quantity: int,
    rng: random.Random,
) -> dict[int, int]:
    if min_quantity <= 0 or max_quantity < min_quantity:
        raise ValueError(
            "Invalid quantity range. Expected 0 < min_quantity <= max_quantity."
        )

    quantities: dict[int, int] = {}
    variants = list(group.variants)

    if state == "FULL_OUT":
        for variant in variants:
            quantities[variant.variant_id] = 0
        return quantities

    if state == "IN_STOCK":
        for variant in variants:
            quantities[variant.variant_id] = rng.randint(min_quantity, max_quantity)
        return quantities

    if state != "PARTIAL_OUT":
        raise ValueError(f"Unsupported inventory state: {state}")

    if len(variants) < 2:
        for variant in variants:
            quantities[variant.variant_id] = rng.randint(min_quantity, max_quantity)
        return quantities

    # Với trạng thái "hết hàng một số size", luôn giữ ít nhất 1 size = 0
    # và ít nhất 1 size > 0 để tránh rơi vào tình huống hết hàng toàn bộ.
    max_zero_count = max(1, len(variants) - 1)
    suggested_zero_count = max(1, round(len(variants) * 0.35))
    zero_count = min(max_zero_count, suggested_zero_count)
    zero_count = rng.randint(1, zero_count)

    zero_variant_ids = {
        variant.variant_id
        for variant in rng.sample(variants, k=zero_count)
    }

    for variant in variants:
        if variant.variant_id in zero_variant_ids:
            quantities[variant.variant_id] = 0
        else:
            quantities[variant.variant_id] = rng.randint(min_quantity, max_quantity)

    return quantities


def fetch_active_branches(
    connection: psycopg.Connection,
    branch_ids: list[int] | None,
) -> list[BranchRecord]:
    params: dict[str, object] = {}
    query = """
        SELECT
            branch_id,
            branch_name
        FROM iam.branch
        WHERE is_active = TRUE
    """

    if branch_ids:
        params["branch_ids"] = branch_ids
        query += " AND branch_id = ANY(%(branch_ids)s)"

    query += " ORDER BY branch_id"

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    branches = [
        BranchRecord(
            branch_id=int(row["branch_id"]),
            branch_name=str(row["branch_name"]),
        )
        for row in rows
    ]

    if branch_ids and len(branches) != len(set(branch_ids)):
        found_ids = {branch.branch_id for branch in branches}
        missing_ids = sorted(set(branch_ids) - found_ids)
        raise ValueError(f"Unknown or inactive branch_ids: {missing_ids}")

    if not branches:
        raise ValueError(
            "No active branches found in iam.branch. Seed branch data before inventory."
        )

    return branches


def fetch_collection_variant_rows(
    connection: psycopg.Connection,
    collection_ids: list[int] | None,
    collection_slug_by_name: dict[str, str],
    product_line_slug_by_name: dict[str, str],
) -> list[VariantRecord]:
    params: dict[str, object] = {}
    query = """
        SELECT
            c.collection_id,
            c.collection_name,
            pl.product_line_id,
            pl.line_name,
            pc.component_id,
            pv.variant_id,
            pv.size_option_id,
            so.size_name
        FROM catalog.collection AS c
        INNER JOIN catalog.product_line AS pl
            ON pl.collection_id = c.collection_id
        INNER JOIN catalog.product_component AS pc
            ON pc.product_line_id = pl.product_line_id
        INNER JOIN catalog.product_variant AS pv
            ON pv.component_id = pc.component_id
        LEFT JOIN catalog.size_option AS so
            ON so.size_option_id = pv.size_option_id
        WHERE pv.status = ANY(%(variant_statuses)s)
    """
    params["variant_statuses"] = sorted(SELLABLE_VARIANT_STATUSES)

    if collection_ids:
        params["collection_ids"] = collection_ids
        query += " AND c.collection_id = ANY(%(collection_ids)s)"

    query += """
        ORDER BY
            c.collection_id,
            pl.product_line_id,
            pc.component_id,
            pv.variant_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    if collection_ids:
        found_collection_ids = {int(row["collection_id"]) for row in rows}
        missing_ids = sorted(set(collection_ids) - found_collection_ids)
        if missing_ids:
            raise ValueError(
                "No product variants found for collection_ids: "
                f"{missing_ids}"
            )

    return [
        VariantRecord(
            collection_id=int(row["collection_id"]),
            collection_name=str(row["collection_name"]),
            collection_slug=collection_slug_by_name.get(str(row["collection_name"])),
            product_line_id=int(row["product_line_id"]),
            line_name=str(row["line_name"]),
            product_line_slug=product_line_slug_by_name.get(str(row["line_name"])),
            component_id=int(row["component_id"]),
            variant_id=int(row["variant_id"]),
            size_option_id=(
                int(row["size_option_id"])
                if row["size_option_id"] is not None
                else None
            ),
            size_name=str(row["size_name"]) if row["size_name"] is not None else None,
        )
        for row in rows
    ]


def group_product_lines_by_collection(
    variant_rows: list[VariantRecord],
) -> dict[int, list[ProductLineGroup]]:
    grouped: dict[tuple[int, int], list[VariantRecord]] = {}

    for row in variant_rows:
        key = (row.collection_id, row.product_line_id)
        grouped.setdefault(key, []).append(row)

    collections: dict[int, list[ProductLineGroup]] = {}
    for (collection_id, product_line_id), variants in grouped.items():
        first = variants[0]
        group = ProductLineGroup(
            collection_id=collection_id,
            collection_name=first.collection_name,
            collection_slug=first.collection_slug,
            product_line_id=product_line_id,
            line_name=first.line_name,
            product_line_slug=first.product_line_slug,
            variants=tuple(variants),
        )
        collections.setdefault(collection_id, []).append(group)

    for groups in collections.values():
        groups.sort(key=lambda group: group.product_line_id)

    return collections


def build_seed_records(
    collection_groups: dict[int, list[ProductLineGroup]],
    branches: list[BranchRecord],
    min_quantity: int,
    max_quantity: int,
    seed: int,
) -> list[InventorySeedRecord]:
    records: list[InventorySeedRecord] = []
    branch_count = len(branches)

    for collection_id, groups in sorted(collection_groups.items()):
        collection_rng = random.Random(seed + collection_id)
        states = assign_inventory_states(
            groups=groups,
            branch_count=branch_count,
            rng=collection_rng,
        )

        for branch in branches:
            for group in groups:
                branch_rng = random.Random(
                    seed + (collection_id * 10_000) + (branch.branch_id * 100) + group.product_line_id
                )
                state = states[group.product_line_id]
                quantities = generate_quantities_for_product_line(
                    group=group,
                    state=state,
                    min_quantity=min_quantity,
                    max_quantity=max_quantity,
                    rng=branch_rng,
                )

                for variant in group.variants:
                    records.append(
                        InventorySeedRecord(
                            branch_id=branch.branch_id,
                            branch_name=branch.branch_name,
                            collection_id=group.collection_id,
                            collection_name=group.collection_name,
                            collection_slug=group.collection_slug,
                            product_line_id=group.product_line_id,
                            line_name=group.line_name,
                            product_line_slug=group.product_line_slug,
                            inventory_state=state,
                            variant_id=variant.variant_id,
                            component_id=variant.component_id,
                            size_option_id=variant.size_option_id,
                            size_name=variant.size_name,
                            quantity=quantities[variant.variant_id],
                        )
                    )

    return records


def upsert_inventory_records(
    connection: psycopg.Connection,
    records: list[InventorySeedRecord],
) -> tuple[int, int]:
    if not records:
        return 0, 0

    payloads = [
        {
            "branch_id": record.branch_id,
            "variant_id": record.variant_id,
            "quantity": record.quantity,
        }
        for record in records
    ]

    query = """
        INSERT INTO inventory.inventory (
            branch_id,
            variant_id,
            quantity
        )
        VALUES (
            %(branch_id)s,
            %(variant_id)s,
            %(quantity)s
        )
        ON CONFLICT (branch_id, variant_id)
        DO UPDATE SET
            quantity = EXCLUDED.quantity,
            updated_at = NOW()
    """

    inserted_or_updated = 0
    with connection.cursor() as cursor:
        for batch in chunk_records(payloads, BATCH_SIZE):
            cursor.executemany(query, batch)
            inserted_or_updated += len(batch)

    return inserted_or_updated, 0


def export_inventory_plan(
    records: list[InventorySeedRecord],
    output_file: Path,
) -> None:
    create_dir(output_file.parent)
    fieldnames = [
        "branch_id",
        "branch_name",
        "collection_id",
        "collection_name",
        "collection_slug",
        "product_line_id",
        "line_name",
        "product_line_slug",
        "inventory_state",
        "variant_id",
        "component_id",
        "size_option_id",
        "size_name",
        "quantity",
    ]

    with output_file.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "branch_id": record.branch_id,
                    "branch_name": record.branch_name,
                    "collection_id": record.collection_id,
                    "collection_name": record.collection_name,
                    "collection_slug": record.collection_slug,
                    "product_line_id": record.product_line_id,
                    "line_name": record.line_name,
                    "product_line_slug": record.product_line_slug,
                    "inventory_state": record.inventory_state,
                    "variant_id": record.variant_id,
                    "component_id": record.component_id,
                    "size_option_id": record.size_option_id,
                    "size_name": record.size_name,
                    "quantity": record.quantity,
                }
            )


def summarize_records(records: list[InventorySeedRecord]) -> dict[str, int]:
    summary = {
        "collections": 0,
        "product_lines": 0,
        "branches": 0,
        "inventory_rows": len(records),
        "IN_STOCK": 0,
        "PARTIAL_OUT": 0,
        "FULL_OUT": 0,
    }

    summary["collections"] = len({record.collection_id for record in records})
    summary["product_lines"] = len({record.product_line_id for record in records})
    summary["branches"] = len({record.branch_id for record in records})

    for state in ("IN_STOCK", "PARTIAL_OUT", "FULL_OUT"):
        summary[state] = len(
            [record for record in records if record.inventory_state == state]
        )

    return summary


def print_summary(
    connection_label: str,
    records: list[InventorySeedRecord],
    dry_run: bool,
    output_file: Path,
) -> None:
    summary = summarize_records(records)

    print(f"Target database: {connection_label}")
    print(f"Collections seeded: {summary['collections']}")
    print(f"Product lines seeded: {summary['product_lines']}")
    print(f"Branches seeded: {summary['branches']}")
    print(f"Inventory rows prepared: {summary['inventory_rows']}")
    print(
        "Rows by state: "
        f"IN_STOCK={summary['IN_STOCK']}, "
        f"PARTIAL_OUT={summary['PARTIAL_OUT']}, "
        f"FULL_OUT={summary['FULL_OUT']}"
    )
    print(f"Inventory plan CSV: {output_file}")
    print(f"Mode: {'dry-run' if dry_run else 'upsert'}")

    preview = records[:10]
    if preview:
        print("\nPreview:")
        for record in preview:
            print(
                f"- branch={record.branch_id} collection={record.collection_id} "
                f"product_line={record.product_line_id} variant={record.variant_id} "
                f"state={record.inventory_state} quantity={record.quantity}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed inventory.inventory from existing collections/product lines/variants "
            "using a 30% partial-out, 60% in-stock, 10% full-out distribution."
        )
    )
    add_loader_connection_args(parser)
    parser.add_argument(
        "--branch-id",
        action="append",
        help="Only seed the provided branch_id values. Supports repeated flag or comma-separated ids.",
    )
    parser.add_argument(
        "--collection-id",
        action="append",
        help="Only seed the provided collection_id values. Supports repeated flag or comma-separated ids.",
    )
    parser.add_argument(
        "--min-quantity",
        type=int,
        default=DEFAULT_MIN_QUANTITY,
        help=f"Minimum positive quantity for in-stock variants. Default: {DEFAULT_MIN_QUANTITY}.",
    )
    parser.add_argument(
        "--max-quantity",
        type=int,
        default=DEFAULT_MAX_QUANTITY,
        help=f"Maximum positive quantity for in-stock variants. Default: {DEFAULT_MAX_QUANTITY}.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Random seed for deterministic inventory generation. Default: {DEFAULT_RANDOM_SEED}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate inventory plan without writing to database.",
    )
    parser.add_argument(
        "--output-file",
        default=str(INVENTORY_FILE),
        help=f"CSV path to export generated inventory plan. Default: {INVENTORY_FILE}.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    branch_ids = parse_branch_ids(args.branch_id)
    collection_ids = parse_collection_ids(args.collection_id)
    output_file = Path(args.output_file)
    collection_slug_by_name = read_collection_slug_map(COLLECTION_MASTER_FILE)
    product_line_slug_by_name = read_product_line_slug_map(PRODUCT_LINE_FILE)

    with psycopg.connect(**connection_kwargs) as connection:
        branches = fetch_active_branches(connection, branch_ids=branch_ids)
        variant_rows = fetch_collection_variant_rows(
            connection,
            collection_ids=collection_ids,
            collection_slug_by_name=collection_slug_by_name,
            product_line_slug_by_name=product_line_slug_by_name,
        )
        collection_groups = group_product_lines_by_collection(variant_rows)
        records = build_seed_records(
            collection_groups=collection_groups,
            branches=branches,
            min_quantity=args.min_quantity,
            max_quantity=args.max_quantity,
            seed=args.seed,
        )

        if not args.dry_run:
            upsert_inventory_records(connection, records)
            connection.commit()

    export_inventory_plan(records, output_file)
    print_summary(
        connection_label=describe_connection(connection_kwargs),
        records=records,
        dry_run=args.dry_run,
        output_file=output_file,
    )


if __name__ == "__main__":
    main()
