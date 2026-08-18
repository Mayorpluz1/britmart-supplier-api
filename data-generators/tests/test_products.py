"""Automated tests for BritMart product master data."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest


GENERATOR_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = GENERATOR_ROOT / "src"
OUTPUT_DIRECTORY = GENERATOR_ROOT / "output"
CONFIG_PATH = (
    GENERATOR_ROOT / "config" / "product_config.json"
)

sys.path.insert(0, str(SOURCE_DIRECTORY))

import generate_products  # noqa: E402
import validate_products  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def generated_product_data() -> None:
    """Generate the product dataset once for this test module."""

    generate_products.main()


def read_csv(file_name: str) -> list[dict[str, str]]:
    """Read a generated CSV file."""

    file_path = OUTPUT_DIRECTORY / file_name

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as input_file:
        return list(csv.DictReader(input_file))


def load_configuration() -> dict:
    """Load the approved product configuration."""

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as input_file:
        return json.load(input_file)


def test_expected_product_output_files_exist() -> None:
    """Confirm all product output files were generated."""

    expected_files = {
        "categories.csv",
        "subcategories.csv",
        "products.csv",
        "product_manifest.json",
    }

    actual_files = {
        file_path.name
        for file_path in OUTPUT_DIRECTORY.iterdir()
        if file_path.is_file()
    }

    assert expected_files.issubset(actual_files)


def test_expected_product_record_counts() -> None:
    """Confirm approved product master record counts."""

    configuration = load_configuration()
    categories = read_csv("categories.csv")
    subcategories = read_csv("subcategories.csv")
    products = read_csv("products.csv")

    assert len(categories) == int(
        configuration["expected_counts"]["categories"]
    )
    assert len(subcategories) == int(
        configuration["expected_counts"][
            "subcategories"
        ]
    )
    assert len(products) == int(
        configuration["expected_counts"]["products"]
    )


def test_product_business_keys_are_unique() -> None:
    """Confirm product codes, SKUs and names are unique."""

    products = read_csv("products.csv")

    for field_name in [
        "product_code",
        "sku",
        "product_name",
    ]:
        values = [
            product[field_name] for product in products
        ]
        assert len(values) == len(set(values))


def test_product_technical_identifiers_are_unique() -> None:
    """Confirm technical identifiers are unique."""

    entity_fields = {
        "categories.csv": "category_id",
        "subcategories.csv": "subcategory_id",
        "products.csv": "product_id",
    }

    for file_name, field_name in entity_fields.items():
        rows = read_csv(file_name)
        values = [row[field_name] for row in rows]

        assert len(values) == len(set(values))


def test_every_category_has_eight_subcategories() -> None:
    """Confirm the approved five-by-eight hierarchy."""

    subcategories = read_csv("subcategories.csv")
    counts = Counter(
        row["category_code"] for row in subcategories
    )

    assert len(counts) == 5
    assert all(count == 8 for count in counts.values())


def test_product_category_relationships_are_valid() -> None:
    """Confirm category and subcategory referential integrity."""

    categories = read_csv("categories.csv")
    subcategories = read_csv("subcategories.csv")
    products = read_csv("products.csv")

    category_id_by_code = {
        row["category_code"]: row["category_id"]
        for row in categories
    }
    subcategory_reference = {
        row["subcategory_code"]: {
            "subcategory_id": row["subcategory_id"],
            "category_code": row["category_code"],
        }
        for row in subcategories
    }

    for product in products:
        assert (
            product["category_id"]
            == category_id_by_code[
                product["category_code"]
            ]
        )

        reference = subcategory_reference[
            product["subcategory_code"]
        ]

        assert (
            product["subcategory_id"]
            == reference["subcategory_id"]
        )
        assert (
            product["category_code"]
            == reference["category_code"]
        )


def test_product_counts_match_each_subcategory() -> None:
    """Confirm exact configured subcategory product counts."""

    configuration = load_configuration()
    products = read_csv("products.csv")

    expected_counts = {
        subcategory["subcategory_code"]: int(
            subcategory["product_count"]
        )
        for category in configuration["categories"]
        for subcategory in category["subcategories"]
    }
    actual_counts = Counter(
        product["subcategory_code"]
        for product in products
    )

    assert dict(actual_counts) == expected_counts


def test_product_prices_and_costs_are_valid() -> None:
    """Confirm positive prices and cost below retail price."""

    products = read_csv("products.csv")

    for product in products:
        unit_cost = Decimal(product["unit_cost"])
        retail_price = Decimal(
            product["standard_retail_price"]
        )
        margin_rate = Decimal(
            product["gross_margin_rate"]
        )

        assert unit_cost >= Decimal("0")
        assert retail_price > Decimal("0")
        assert unit_cost <= retail_price
        assert Decimal("0.18") <= margin_rate <= Decimal(
            "0.55"
        )


def test_storage_matches_subcategory_configuration() -> None:
    """Confirm products use the correct storage type."""

    configuration = load_configuration()
    products = read_csv("products.csv")

    expected_storage = {
        subcategory["subcategory_code"]: (
            subcategory["storage_type"]
        )
        for category in configuration["categories"]
        for subcategory in category["subcategories"]
    }

    for product in products:
        assert (
            product["storage_type"]
            == expected_storage[
                product["subcategory_code"]
            ]
        )


def test_exact_demand_tier_counts() -> None:
    """Confirm exact A, B, C and D demand-tier allocation."""

    products = read_csv("products.csv")
    actual_counts = Counter(
        product["demand_tier"] for product in products
    )

    assert actual_counts == {
        "A": 400,
        "B": 600,
        "C": 700,
        "D": 300,
    }


def test_age_restricted_products_are_controlled() -> None:
    """Confirm alcohol subcategories are age restricted."""

    products = read_csv("products.csv")
    restricted_subcategories = {
        "SUB-023",
        "SUB-024",
    }

    for product in products:
        expected_value = (
            product["subcategory_code"]
            in restricted_subcategories
        )

        assert (
            product["age_restricted_flag"].lower()
            == str(expected_value).lower()
        )


def test_full_product_validation_suite_passes() -> None:
    """Run the independent product validation framework."""

    counts = validate_products.validate_all()

    assert counts == {
        "categories": 5,
        "subcategories": 40,
        "products": 2000,
    }


def test_product_generation_is_reproducible() -> None:
    """Confirm repeated generation produces identical files."""

    file_names = [
        "categories.csv",
        "subcategories.csv",
        "products.csv",
    ]

    first_versions = {
        file_name: (
            OUTPUT_DIRECTORY / file_name
        ).read_bytes()
        for file_name in file_names
    }

    generate_products.main()

    second_versions = {
        file_name: (
            OUTPUT_DIRECTORY / file_name
        ).read_bytes()
        for file_name in file_names
    }

    assert first_versions == second_versions