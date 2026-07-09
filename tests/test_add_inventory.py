from __future__ import annotations

import random
import unittest

from src.load.add_inventory import (
    ProductLineGroup,
    VariantRecord,
    assign_inventory_states,
    compute_target_row_counts,
    generate_quantities_for_product_line,
)


def make_group(
    collection_id: int,
    product_line_id: int,
    variant_count: int,
) -> ProductLineGroup:
    variants = tuple(
        VariantRecord(
            collection_id=collection_id,
            collection_name=f"Collection {collection_id}",
            collection_slug=f"collection-{collection_id}",
            product_line_id=product_line_id,
            line_name=f"Line {product_line_id}",
            product_line_slug=f"line-{product_line_id}",
            component_id=product_line_id * 10,
            variant_id=(product_line_id * 100) + index,
            size_option_id=index,
            size_name=f"Size {index}",
        )
        for index in range(1, variant_count + 1)
    )

    return ProductLineGroup(
        collection_id=collection_id,
        collection_name=f"Collection {collection_id}",
        collection_slug=f"collection-{collection_id}",
        product_line_id=product_line_id,
        line_name=f"Line {product_line_id}",
        product_line_slug=f"line-{product_line_id}",
        variants=variants,
    )


class AddInventoryUnitTest(unittest.TestCase):
    def test_compute_target_row_counts_matches_ratios(self) -> None:
        targets = compute_target_row_counts(100)

        self.assertEqual(30, targets["PARTIAL_OUT"])
        self.assertEqual(60, targets["IN_STOCK"])
        self.assertEqual(10, targets["FULL_OUT"])

    def test_assign_inventory_states_returns_expected_buckets(self) -> None:
        groups = [make_group(1, product_line_id=index, variant_count=4) for index in range(1, 11)]
        states = assign_inventory_states(
            groups=groups,
            branch_count=1,
            rng=random.Random(20260708),
        )

        self.assertEqual(10, len(states))
        self.assertEqual(1, sum(1 for state in states.values() if state == "FULL_OUT"))
        self.assertEqual(3, sum(1 for state in states.values() if state == "PARTIAL_OUT"))
        self.assertEqual(6, sum(1 for state in states.values() if state == "IN_STOCK"))

    def test_generate_quantities_for_partial_out_contains_zero_and_positive(self) -> None:
        group = make_group(1, 101, 4)
        quantities = generate_quantities_for_product_line(
            group=group,
            state="PARTIAL_OUT",
            min_quantity=1,
            max_quantity=30,
            rng=random.Random(42),
        )

        self.assertEqual(4, len(quantities))
        self.assertTrue(any(quantity == 0 for quantity in quantities.values()))
        self.assertTrue(any(quantity > 0 for quantity in quantities.values()))

    def test_generate_quantities_for_full_out_is_zero_everywhere(self) -> None:
        group = make_group(1, 202, 3)
        quantities = generate_quantities_for_product_line(
            group=group,
            state="FULL_OUT",
            min_quantity=1,
            max_quantity=30,
            rng=random.Random(99),
        )

        self.assertTrue(all(quantity == 0 for quantity in quantities.values()))

    def test_generate_quantities_for_in_stock_is_positive_everywhere(self) -> None:
        group = make_group(1, 303, 5)
        quantities = generate_quantities_for_product_line(
            group=group,
            state="IN_STOCK",
            min_quantity=1,
            max_quantity=30,
            rng=random.Random(7),
        )

        self.assertTrue(all(quantity > 0 for quantity in quantities.values()))


if __name__ == "__main__":
    unittest.main()
