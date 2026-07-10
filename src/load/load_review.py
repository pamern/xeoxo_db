from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys
from typing import Any
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


DEFAULT_MIN_REVIEWS = 5
DEFAULT_MAX_REVIEWS = 10
DEFAULT_SEED = 20260710
SEED_EMAIL_PREFIX = "review.seed"
SEED_PHONE_PREFIX = "09888"
SEED_ADDRESS = "123 Seed Review Street"
SEED_DISTRICT = "Quận 1"
REVIEW_STATUS = "DISPLAY"
RATING_WEIGHTS = (0.04, 0.08, 0.18, 0.35, 0.35)
CUSTOMER_NAME_POOL = [
    "Nguyen Minh Anh",
    "Tran Bao Chau",
    "Le Hoang My",
    "Pham Gia Han",
    "Do Khanh Linh",
    "Vu Thu Trang",
    "Bui Ngoc Ha",
    "Dang Thanh Huyen",
    "Phan Quynh Anh",
    "Hoang Bao Ngoc",
    "Mai Tuan Kiet",
    "Nguyen Gia Bao",
]
GENERIC_REVIEW_BY_RATING = {
    5: "Sản phẩm đẹp, mặc ổn, mình rất hài lòng.",
    4: "Sản phẩm ổn, form đẹp, trải nghiệm tốt.",
    3: "Sản phẩm khá ổn, nhìn chung dùng tốt.",
    2: "Sản phẩm tạm ổn nhưng chưa thật sự như kỳ vọng.",
    1: "Trải nghiệm chưa tốt lắm, sản phẩm chưa hợp với mình.",
}


@dataclass(frozen=True)
class ReviewPlan:
    product_line_id: int
    line_name: str
    slug: str
    target_count: int
    existing_count: int
    insert_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed fake reviews into sales.review for as many product lines as possible. "
            "The loader reuses eligible order items first, then auto-creates minimal "
            "completed order history to backfill missing reviews."
        )
    )
    add_loader_connection_args(parser)
    parser.add_argument(
        "--min-per-product",
        type=int,
        default=DEFAULT_MIN_REVIEWS,
        help="Minimum target reviews per product line.",
    )
    parser.add_argument(
        "--max-per-product",
        type=int,
        default=DEFAULT_MAX_REVIEWS,
        help="Maximum target reviews per product line.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Deterministic random seed.",
    )
    parser.add_argument(
        "--limit-product-lines",
        type=int,
        help="Limit the number of product lines to seed.",
    )
    parser.add_argument(
        "--allow-create-orders",
        action="store_true",
        help=(
            "Deprecated compatibility flag. Synthetic completed orders are now "
            "created automatically when needed."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the seeding plan without inserting anything.",
    )
    return parser.parse_args()


def build_rng(args: argparse.Namespace) -> random.Random:
    return random.Random(args.seed)


def fetch_product_lines(
    connection: psycopg.Connection,
    limit_product_lines: int | None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            pl.product_line_id,
            pl.line_name,
            pl.slug,
            COUNT(DISTINCT rv.review_id)::INT AS existing_review_count
        FROM catalog.product_line AS pl
        LEFT JOIN catalog.product_component AS pc
            ON pc.product_line_id = pl.product_line_id
        LEFT JOIN catalog.product_variant AS pv
            ON pv.component_id = pc.component_id
        LEFT JOIN sales.order_item AS oi
            ON oi.variant_id = pv.variant_id
        LEFT JOIN sales.review AS rv
            ON rv.order_item_id = oi.order_item_id
        GROUP BY
            pl.product_line_id,
            pl.line_name,
            pl.slug
        ORDER BY
            pl.product_line_id
    """

    params: list[Any] = []
    if limit_product_lines is not None:
        query += "\nLIMIT %s"
        params.append(limit_product_lines)

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return list(cursor.fetchall())


def build_review_plans(
    product_lines: list[dict[str, Any]],
    rng: random.Random,
    min_per_product: int,
    max_per_product: int,
) -> list[ReviewPlan]:
    plans: list[ReviewPlan] = []
    for row in product_lines:
        target_count = rng.randint(min_per_product, max_per_product)
        existing_count = int(row["existing_review_count"] or 0)
        insert_count = max(target_count - existing_count, 0)
        plans.append(
            ReviewPlan(
                product_line_id=row["product_line_id"],
                line_name=row["line_name"],
                slug=row["slug"],
                target_count=target_count,
                existing_count=existing_count,
                insert_count=insert_count,
            )
        )
    return plans


def fetch_existing_reviewed_order_item_ids(
    connection: psycopg.Connection,
) -> set[int]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT order_item_id FROM sales.review")
        return {row[0] for row in cursor.fetchall()}


def fetch_eligible_order_items(
    connection: psycopg.Connection,
) -> dict[int, list[dict[str, Any]]]:
    query = """
        SELECT
            pl.product_line_id,
            oi.order_item_id,
            so.customer_id,
            oi.variant_id,
            oi.created_at AS order_item_created_at,
            so.order_date
        FROM sales.order_item AS oi
        INNER JOIN sales.sales_order AS so
            ON so.order_id = oi.order_id
        INNER JOIN catalog.product_variant AS pv
            ON pv.variant_id = oi.variant_id
        INNER JOIN catalog.product_component AS pc
            ON pc.component_id = pv.component_id
        INNER JOIN catalog.product_line AS pl
            ON pl.product_line_id = pc.product_line_id
        LEFT JOIN sales.review AS rv
            ON rv.order_item_id = oi.order_item_id
        WHERE so.customer_id IS NOT NULL
          AND so.order_status = 'COMPLETED'
          AND oi.item_type = 'STANDARD'
          AND oi.variant_id IS NOT NULL
          AND rv.review_id IS NULL
        ORDER BY
            pl.product_line_id,
            so.order_date,
            oi.order_item_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    eligible_by_line: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        eligible_by_line.setdefault(row["product_line_id"], []).append(dict(row))
    return eligible_by_line


def fetch_reference_data(connection: psycopg.Connection) -> dict[str, Any]:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT province_id
            FROM iam.province
            ORDER BY province_id
            LIMIT 1
            """
        )
        province = cursor.fetchone()

        cursor.execute(
            """
            SELECT method_id, method_code
            FROM sales.payment_method
            WHERE is_active = TRUE
            ORDER BY
                CASE
                    WHEN method_code = 'COD' THEN 0
                    ELSE 1
                END,
                method_id
            LIMIT 1
            """
        )
        payment_method = cursor.fetchone()

    if province is None:
        raise ValueError(
            "iam.province is empty. Seed province data before generating synthetic reviews."
        )

    if payment_method is None:
        raise ValueError(
            "sales.payment_method is empty. Seed payment method data before generating synthetic reviews."
        )

    return {
        "province_id": province["province_id"],
        "payment_method_id": payment_method["method_id"],
        "payment_method_code": payment_method["method_code"],
    }


def ensure_seed_customers(
    connection: psycopg.Connection,
    required_count: int,
    province_id: int,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            c.customer_id,
            c.customer_name,
            c.email,
            c.phone,
            a.address_id
        FROM iam.customer AS c
        LEFT JOIN LATERAL (
            SELECT address_id
            FROM iam.address
            WHERE customer_id = c.customer_id
              AND is_active = TRUE
            ORDER BY is_default DESC, address_id
            LIMIT 1
        ) AS a
            ON TRUE
        WHERE c.email LIKE %s
        ORDER BY c.customer_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, (f"{SEED_EMAIL_PREFIX}.%@xeoxo.local",))
        existing_rows = [dict(row) for row in cursor.fetchall()]

    seeded_customers: list[dict[str, Any]] = []

    for row in existing_rows:
        address_id = row["address_id"]
        if address_id is None:
            address_id = insert_seed_address(
                connection=connection,
                customer_id=row["customer_id"],
                province_id=province_id,
                recipient_name=row["customer_name"],
                recipient_phone=row["phone"],
            )
        seeded_customers.append(
            {
                "customer_id": row["customer_id"],
                "customer_name": row["customer_name"],
                "address_id": address_id,
            }
        )

    start_index = len(seeded_customers)
    for index in range(start_index, required_count):
        customer_name = CUSTOMER_NAME_POOL[index % len(CUSTOMER_NAME_POOL)]
        customer_id = insert_seed_customer(connection, index=index, customer_name=customer_name)
        address_id = insert_seed_address(
            connection=connection,
            customer_id=customer_id,
            province_id=province_id,
            recipient_name=customer_name,
            recipient_phone=build_seed_phone(index),
        )
        seeded_customers.append(
            {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "address_id": address_id,
            }
        )

    return seeded_customers


def insert_seed_customer(
    connection: psycopg.Connection,
    index: int,
    customer_name: str,
) -> int:
    email = build_seed_email(index)
    phone = build_seed_phone(index)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO iam.customer (
                customer_name,
                email,
                phone,
                customer_type,
                created_at,
                updated_at
            )
            VALUES (
                %(customer_name)s,
                %(email)s,
                %(phone)s,
                'GUEST',
                NOW(),
                NOW()
            )
            RETURNING customer_id
            """,
            {
                "customer_name": customer_name,
                "email": email,
                "phone": phone,
            },
        )
        return cursor.fetchone()[0]


def insert_seed_address(
    connection: psycopg.Connection,
    customer_id: int,
    province_id: int,
    recipient_name: str,
    recipient_phone: str,
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO iam.address (
                customer_id,
                recipient_name,
                recipient_phone,
                province_id,
                district_name,
                address_detail,
                is_default,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                %(customer_id)s,
                %(recipient_name)s,
                %(recipient_phone)s,
                %(province_id)s,
                %(district_name)s,
                %(address_detail)s,
                TRUE,
                TRUE,
                NOW(),
                NOW()
            )
            RETURNING address_id
            """,
            {
                "customer_id": customer_id,
                "recipient_name": recipient_name,
                "recipient_phone": recipient_phone,
                "province_id": province_id,
                "district_name": SEED_DISTRICT,
                "address_detail": SEED_ADDRESS,
            },
        )
        return cursor.fetchone()[0]


def build_seed_email(index: int) -> str:
    return f"{SEED_EMAIL_PREFIX}.{index + 1:04d}@xeoxo.local"


def build_seed_phone(index: int) -> str:
    suffix = str(index + 1).zfill(5)
    return f"{SEED_PHONE_PREFIX}{suffix}"


def choose_rating(rng: random.Random) -> int:
    return rng.choices([1, 2, 3, 4, 5], weights=RATING_WEIGHTS, k=1)[0]


def build_review_content(
    rng: random.Random,
    rating: int,
    line_name: str,
) -> str:
    _ = rng
    _ = line_name
    return GENERIC_REVIEW_BY_RATING[rating]


def insert_review(
    connection: psycopg.Connection,
    customer_id: int,
    order_item_id: int,
    rating: int,
    review_content: str,
    created_at: datetime,
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sales.review (
                customer_id,
                order_item_id,
                rating,
                review_content,
                review_status,
                created_at,
                updated_at
            )
            VALUES (
                %(customer_id)s,
                %(order_item_id)s,
                %(rating)s,
                %(review_content)s,
                %(review_status)s,
                %(created_at)s,
                %(updated_at)s
            )
            RETURNING review_id
            """,
            {
                "customer_id": customer_id,
                "order_item_id": order_item_id,
                "rating": rating,
                "review_content": review_content,
                "review_status": REVIEW_STATUS,
                "created_at": created_at,
                "updated_at": created_at,
            },
        )
        return cursor.fetchone()[0]


def create_synthetic_order_item(
    connection: psycopg.Connection,
    customer_id: int,
    address_id: int,
    variant_id: int,
    unit_price: float,
    payment_method_id: int,
    payment_method_code: str,
    rng: random.Random,
    synthetic_index: int,
) -> dict[str, Any]:
    ordered_at = datetime.now(timezone.utc) - timedelta(days=rng.randint(10, 320))
    shipped_at = ordered_at + timedelta(days=rng.randint(1, 3))
    delivered_at = shipped_at + timedelta(days=rng.randint(1, 4))
    shipping_fee = 30000
    total_amount = unit_price + shipping_fee
    unique_suffix = uuid4().hex[:10].upper()
    order_code = (
        f"RV{ordered_at.strftime('%Y%m%d%H%M%S%f')}{synthetic_index:05d}{unique_suffix[:4]}"
    )
    transaction_code = f"{payment_method_code}-RV-{unique_suffix}"
    tracking_code = f"RVTRACK{unique_suffix}"

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sales.sales_order (
                order_code,
                customer_id,
                order_date,
                reward_discount_amount,
                shipping_fee,
                total_amount,
                order_status,
                payment_status,
                customer_note,
                created_at,
                updated_at
            )
            VALUES (
                %(order_code)s,
                %(customer_id)s,
                %(order_date)s,
                0,
                %(shipping_fee)s,
                %(total_amount)s,
                'COMPLETED',
                'PAID',
                'Seeded review order',
                %(created_at)s,
                %(updated_at)s
            )
            RETURNING order_id
            """,
            {
                "order_code": order_code,
                "customer_id": customer_id,
                "order_date": ordered_at,
                "shipping_fee": shipping_fee,
                "total_amount": total_amount,
                "created_at": ordered_at,
                "updated_at": delivered_at,
            },
        )
        order_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO sales.order_item (
                order_id,
                variant_id,
                customization_id,
                customization_snapshot,
                item_type,
                quantity,
                unit_price,
                discount_amount,
                line_total,
                created_at
            )
            VALUES (
                %(order_id)s,
                %(variant_id)s,
                NULL,
                NULL,
                'STANDARD',
                1,
                %(unit_price)s,
                0,
                %(line_total)s,
                %(created_at)s
            )
            RETURNING order_item_id
            """,
            {
                "order_id": order_id,
                "variant_id": variant_id,
                "unit_price": unit_price,
                "line_total": unit_price,
                "created_at": ordered_at,
            },
        )
        order_item_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO sales.payment (
                order_id,
                method_id,
                amount,
                payment_status,
                transaction_code,
                paid_at,
                created_at,
                updated_at
            )
            VALUES (
                %(order_id)s,
                %(method_id)s,
                %(amount)s,
                'PAID',
                %(transaction_code)s,
                %(paid_at)s,
                %(created_at)s,
                %(updated_at)s
            )
            """,
            {
                "order_id": order_id,
                "method_id": payment_method_id,
                "amount": total_amount,
                "transaction_code": transaction_code,
                "paid_at": ordered_at,
                "created_at": ordered_at,
                "updated_at": delivered_at,
            },
        )

        cursor.execute(
            """
            INSERT INTO sales.shipping (
                order_id,
                address_id,
                shipping_provider,
                tracking_code,
                shipping_status,
                shipped_at,
                delivered_at,
                created_at,
                updated_at
            )
            VALUES (
                %(order_id)s,
                %(address_id)s,
                'SEED_INTERNAL',
                %(tracking_code)s,
                'DELIVERED',
                %(shipped_at)s,
                %(delivered_at)s,
                %(created_at)s,
                %(updated_at)s
            )
            """,
            {
                "order_id": order_id,
                "address_id": address_id,
                "tracking_code": tracking_code,
                "shipped_at": shipped_at,
                "delivered_at": delivered_at,
                "created_at": ordered_at,
                "updated_at": delivered_at,
            },
        )

    return {
        "order_item_id": order_item_id,
        "customer_id": customer_id,
        "order_date": ordered_at,
    }


def fetch_variants_by_product_line(
    connection: psycopg.Connection,
) -> dict[int, list[dict[str, Any]]]:
    query = """
        SELECT
            pl.product_line_id,
            pv.variant_id,
            pv.price
        FROM catalog.product_line AS pl
        INNER JOIN catalog.product_component AS pc
            ON pc.product_line_id = pl.product_line_id
        INNER JOIN catalog.product_variant AS pv
            ON pv.component_id = pc.component_id
        ORDER BY pl.product_line_id, pv.variant_id
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    variants_by_line: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        variants_by_line.setdefault(row["product_line_id"], []).append(dict(row))
    return variants_by_line


def seed_reviews(
    connection_kwargs: dict[str, str | int],
    args: argparse.Namespace,
) -> dict[str, Any]:
    rng = build_rng(args)
    with psycopg.connect(**connection_kwargs) as connection:
        product_lines = fetch_product_lines(connection, args.limit_product_lines)
        plans = build_review_plans(
            product_lines=product_lines,
            rng=rng,
            min_per_product=args.min_per_product,
            max_per_product=args.max_per_product,
        )
        eligible_by_line = fetch_eligible_order_items(connection)
        variants_by_line = fetch_variants_by_product_line(connection)

        total_existing = sum(plan.existing_count for plan in plans)
        total_target = sum(plan.target_count for plan in plans)
        total_to_insert = sum(plan.insert_count for plan in plans)

        synthetic_needed = 0
        for plan in plans:
            reusable = len(eligible_by_line.get(plan.product_line_id, []))
            synthetic_needed += max(plan.insert_count - reusable, 0)

        if args.dry_run:
            return {
                "plans": plans,
                "inserted_reviews": 0,
                "reused_order_items": 0,
                "synthetic_order_items": synthetic_needed,
                "synthetic_customers": 0,
                "total_existing": total_existing,
                "total_target": total_target,
                "total_to_insert": total_to_insert,
            }

        seed_customers: list[dict[str, Any]] = []
        reference_data: dict[str, Any] | None = None
        synthetic_customer_index = 0
        synthetic_order_index = 0
        inserted_reviews = 0
        reused_order_items = 0
        synthetic_order_items = 0

        for plan in plans:
            if plan.insert_count == 0:
                continue

            variants = variants_by_line.get(plan.product_line_id, [])
            if not variants:
                continue

            reusable_items = eligible_by_line.get(plan.product_line_id, [])

            for _ in range(plan.insert_count):
                if reusable_items:
                    order_item = reusable_items.pop(0)
                    reused_order_items += 1
                else:
                    if reference_data is None:
                        reference_data = fetch_reference_data(connection)

                    if synthetic_needed > len(seed_customers):
                        seed_customers = ensure_seed_customers(
                            connection=connection,
                            required_count=synthetic_needed,
                            province_id=reference_data["province_id"],
                        )

                    seed_customer = seed_customers[
                        synthetic_customer_index % len(seed_customers)
                    ]
                    synthetic_customer_index += 1
                    variant = rng.choice(variants)
                    order_item = create_synthetic_order_item(
                        connection=connection,
                        customer_id=seed_customer["customer_id"],
                        address_id=seed_customer["address_id"],
                        variant_id=variant["variant_id"],
                        unit_price=float(variant["price"]),
                        payment_method_id=reference_data["payment_method_id"],
                        payment_method_code=reference_data["payment_method_code"],
                        rng=rng,
                        synthetic_index=synthetic_order_index,
                    )
                    synthetic_order_index += 1
                    synthetic_order_items += 1

                review_created_at = order_item["order_date"] + timedelta(
                    days=rng.randint(2, 30)
                )
                rating = choose_rating(rng)
                review_content = build_review_content(rng, rating, plan.line_name)
                insert_review(
                    connection=connection,
                    customer_id=order_item["customer_id"],
                    order_item_id=order_item["order_item_id"],
                    rating=rating,
                    review_content=review_content,
                    created_at=review_created_at,
                )
                inserted_reviews += 1

        connection.commit()

        return {
            "plans": plans,
            "inserted_reviews": inserted_reviews,
            "reused_order_items": reused_order_items,
            "synthetic_order_items": synthetic_order_items,
            "synthetic_customers": len(seed_customers),
            "total_existing": total_existing,
            "total_target": total_target,
            "total_to_insert": total_to_insert,
        }


def print_summary(
    connection_label: str,
    result: dict[str, Any],
    dry_run: bool,
) -> None:
    print(f"Target database: {connection_label}")
    print(f"Dry run: {dry_run}")
    print(f"Current reviews across planned product lines: {result['total_existing']}")
    print(f"Target reviews across planned product lines: {result['total_target']}")
    print(f"Planned inserts: {result['total_to_insert']}")
    print(f"Inserted reviews: {result['inserted_reviews']}")
    print(f"Reused eligible order items: {result['reused_order_items']}")
    print(f"Synthetic order items created: {result['synthetic_order_items']}")
    print(f"Seed customers touched: {result['synthetic_customers']}")

    plans: list[ReviewPlan] = result["plans"]
    if plans:
        print("\nPreview:")
        for plan in plans[:15]:
            print(
                f"- {plan.slug}: existing={plan.existing_count}, "
                f"target={plan.target_count}, insert={plan.insert_count}"
            )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()

    if args.min_per_product < 0:
        raise ValueError("--min-per-product must be >= 0")
    if args.max_per_product < args.min_per_product:
        raise ValueError("--max-per-product must be >= --min-per-product")

    connection_kwargs = build_connection_kwargs(args)
    result = seed_reviews(connection_kwargs=connection_kwargs, args=args)
    print_summary(
        connection_label=describe_connection(connection_kwargs),
        result=result,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
