from __future__ import annotations

import os
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` before running tests."
    ) from exc

from src.utils.load_connection import LOCAL_DB_URL


TEST_DB_URL = os.getenv("TEST_DB_URL", LOCAL_DB_URL)

EXPECTED_INDEXES = {
    "idx_category_active_department_parent",
    "idx_product_line_collection_status",
    "idx_product_line_color_status",
    "idx_line_category_category_product_line",
    "idx_product_component_product_line_display",
    "idx_product_variant_component_status",
    "idx_product_line_media_line_role_order",
    "idx_size_chart_product_line",
    "idx_size_measurement_size_option_measurement_type",
    "idx_cart_customer",
    "idx_cart_item_cart",
    "idx_sales_order_customer_created_at",
    "idx_address_customer_default_created",
    "_measurement_profile_customer_active",
}

EXPECTED_VIEWS = {
    ("catalog", "v_product_line_card"),
    ("catalog", "v_product_line_media_ordered"),
    ("catalog", "v_size_chart_detail"),
    ("sales", "v_my_order_summary"),
}

EXPECTED_POLICIES = {
    ("catalog", "category", "category_public_select"),
    ("catalog", "collection", "collection_public_select"),
    ("catalog", "product_line", "product_line_public_select"),
    ("catalog", "line_category", "line_category_public_select"),
    ("catalog", "product_component", "product_component_public_select"),
    ("catalog", "product_variant", "product_variant_public_select"),
    ("catalog", "color", "color_public_select"),
    ("catalog", "material", "material_public_select"),
    ("catalog", "size_chart", "size_chart_public_select"),
    ("catalog", "size_chart_category", "size_chart_category_public_select"),
    ("catalog", "size_option", "size_option_public_select"),
    ("catalog", "size_measurement", "size_measurement_public_select"),
    ("catalog", "measurement_type", "measurement_type_public_select"),
    ("catalog", "media", "media_public_select"),
    ("catalog", "product_line_media", "product_line_media_public_select"),
    ("iam", "customer", "customer_self_select"),
    ("iam", "customer", "customer_self_update"),
    ("iam", "address", "address_self_all"),
    ("iam", "loyalty_reward", "loyalty_reward_self_select"),
    ("iam", "reward_usage", "reward_usage_self_select"),
    ("sales", "cart", "cart_self_all"),
    ("sales", "cart_item", "cart_item_self_all"),
    ("sales", "sales_order", "sales_order_self_select"),
    ("sales", "order_item", "order_item_self_select"),
    ("customization", "measurement_profile", "measurement_profile_self_all"),
    (
        "customization",
        "measurement_profile_detail",
        "measurement_profile_detail_self_all",
    ),
    ("catalog", "personal_color_result", "personal_color_result_self_all"),
    (
        "catalog",
        "personal_color_result_color",
        "personal_color_result_color_self_all",
    ),
}

EXPECTED_RLS_TABLES = {
    ("catalog", "category"),
    ("catalog", "collection"),
    ("catalog", "product_line"),
    ("catalog", "line_category"),
    ("catalog", "product_component"),
    ("catalog", "product_variant"),
    ("catalog", "color"),
    ("catalog", "material"),
    ("catalog", "size_chart"),
    ("catalog", "size_chart_category"),
    ("catalog", "size_option"),
    ("catalog", "size_measurement"),
    ("catalog", "measurement_type"),
    ("catalog", "media"),
    ("catalog", "product_line_media"),
    ("catalog", "personal_color_result"),
    ("catalog", "personal_color_result_color"),
    ("iam", "customer"),
    ("iam", "address"),
    ("iam", "loyalty_reward"),
    ("iam", "reward_usage"),
    ("sales", "cart"),
    ("sales", "cart_item"),
    ("sales", "sales_order"),
    ("sales", "order_item"),
    ("customization", "measurement_profile"),
    ("customization", "measurement_profile_detail"),
}


class WebAccessSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = psycopg.connect(TEST_DB_URL)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def test_expected_indexes_exist(self) -> None:
        query = """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname IN ('catalog', 'iam', 'sales', 'customization')
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            actual = {row[0] for row in cursor.fetchall()}

        missing = EXPECTED_INDEXES - actual
        self.assertEqual(set(), missing, f"Missing indexes: {sorted(missing)}")

    def test_expected_views_exist(self) -> None:
        query = """
            SELECT table_schema, table_name
            FROM information_schema.views
            WHERE (table_schema, table_name) IN (
                ('catalog', 'v_product_line_card'),
                ('catalog', 'v_product_line_media_ordered'),
                ('catalog', 'v_size_chart_detail'),
                ('sales', 'v_my_order_summary')
            )
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            actual = {tuple(row) for row in cursor.fetchall()}

        missing = EXPECTED_VIEWS - actual
        self.assertEqual(set(), missing, f"Missing views: {sorted(missing)}")

    def test_views_are_queryable(self) -> None:
        queries = [
            "SELECT * FROM catalog.v_product_line_card LIMIT 0",
            "SELECT * FROM catalog.v_product_line_media_ordered LIMIT 0",
            "SELECT * FROM catalog.v_size_chart_detail LIMIT 0",
            "SELECT * FROM sales.v_my_order_summary LIMIT 0",
        ]
        with self.connection.cursor() as cursor:
            for query in queries:
                cursor.execute(query)

    def test_expected_policies_exist(self) -> None:
        query = """
            SELECT schemaname, tablename, policyname
            FROM pg_policies
            WHERE schemaname IN ('catalog', 'iam', 'sales', 'customization')
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            actual = {tuple(row) for row in cursor.fetchall()}

        missing = EXPECTED_POLICIES - actual
        self.assertEqual(set(), missing, f"Missing policies: {sorted(missing)}")

    def test_rls_enabled_on_expected_tables(self) -> None:
        query = """
            SELECT n.nspname, c.relname
            FROM pg_class AS c
            INNER JOIN pg_namespace AS n
                ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND c.relrowsecurity = TRUE
              AND n.nspname IN ('catalog', 'iam', 'sales', 'customization')
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            actual = {tuple(row) for row in cursor.fetchall()}

        missing = EXPECTED_RLS_TABLES - actual
        self.assertEqual(set(), missing, f"RLS not enabled on: {sorted(missing)}")

    def test_owner_helper_function_exists(self) -> None:
        query = """
            SELECT 1
            FROM pg_proc AS p
            INNER JOIN pg_namespace AS n
                ON n.oid = p.pronamespace
            WHERE n.nspname = 'util'
              AND p.proname = 'current_customer_id'
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

        self.assertIsNotNone(row, "Missing function util.current_customer_id()")


if __name__ == "__main__":
    unittest.main()
