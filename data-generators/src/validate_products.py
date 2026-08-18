"""Validate generated BritMart product master data."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any


GENERATOR_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = GENERATOR_ROOT / "config" / "product_config.json"
OUTPUT_DIRECTORY = GENERATOR_ROOT / "output"

CATEGORIES_PATH = OUTPUT_DIRECTORY / "categories.csv"
SUBCATEGORIES_PATH = OUTPUT_DIRECTORY / "subcategories.csv"
PRODUCTS_PATH = OUTPUT_DIRECTORY / "products.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "product_manifest.json"


class ProductValidationError(Exception):
    """Raised when generated product data fails validation."""


def load_json(file_path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    if not file_path.exists():
        raise ProductValidationError(
            f"Required JSON file does not exist: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def load_csv(file_path: Path) -> list[dict[str, str]]:
    """Load a UTF-8 CSV file."""

    if not file_path.exists():
        raise ProductValidationError(
            f"Required CSV file does not exist: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as input_file:
        return list(csv.DictReader(input_file))


def calculate_sha256(file_path: Path) -> str:
    """Calculate a SHA-256 file hash."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(65536), b""):
            sha256.update(block)

    return sha256.hexdigest()


def require_fields(
    rows: list[dict[str, str]],
    required_fields: set[str],
    entity_name: str,
) -> None:
    """Confirm required columns and field values are present."""

    if not rows:
        raise ProductValidationError(
            f"{entity_name} contains no records."
        )

    missing_columns = required_fields.difference(rows[0])

    if missing_columns:
        raise ProductValidationError(
            f"{entity_name} is missing columns: "
            f"{sorted(missing_columns)}"
        )

    for row_number, row in enumerate(rows, start=2):
        for field_name in required_fields:
            value = row.get(field_name)

            if value is None or value.strip() == "":
                raise ProductValidationError(
                    f"{entity_name} row {row_number} has an empty "
                    f"required field: {field_name}"
                )


def require_unique(
    rows: list[dict[str, str]],
    field_name: str,
    entity_name: str,
) -> None:
    """Confirm a field is unique."""

    values = [row[field_name] for row in rows]
    duplicates = [
        value
        for value, count in Counter(values).items()
        if count > 1
    ]

    if duplicates:
        raise ProductValidationError(
            f"{entity_name}.{field_name} contains duplicates: "
            f"{duplicates[:10]}"
        )


def expected_distribution_counts(
    distribution: dict[str, float],
    total_count: int,
) -> dict[str, int]:
    """Calculate expected exact counts using generator allocation."""

    item_names = list(distribution)
    expected_counts: dict[str, int] = {}
    running_total = 0

    for item_name in item_names[:-1]:
        item_count = round(
            float(distribution[item_name]) * total_count
        )
        expected_counts[item_name] = item_count
        running_total += item_count

    expected_counts[item_names[-1]] = (
        total_count - running_total
    )

    return expected_counts


def validate_categories(
    categories: list[dict[str, str]],
    expected_count: int,
) -> dict[str, str]:
    """Validate categories and return code-to-ID mapping."""

    required_fields = {
        "category_id",
        "category_code",
        "category_name",
        "active_flag",
        "effective_from",
        "created_at",
        "updated_at",
    }
    require_fields(categories, required_fields, "categories")

    if len(categories) != expected_count:
        raise ProductValidationError(
            f"Expected {expected_count} categories but found "
            f"{len(categories)}."
        )

    require_unique(categories, "category_id", "categories")
    require_unique(categories, "category_code", "categories")
    require_unique(categories, "category_name", "categories")

    for row in categories:
        if not row["category_code"].startswith("CAT-"):
            raise ProductValidationError(
                f"Invalid category code: "
                f"{row['category_code']}"
            )

        if row["active_flag"].lower() != "true":
            raise ProductValidationError(
                f"Initial category must be active: "
                f"{row['category_code']}"
            )

    return {
        row["category_code"]: row["category_id"]
        for row in categories
    }


def validate_subcategories(
    subcategories: list[dict[str, str]],
    expected_count: int,
    category_id_by_code: dict[str, str],
) -> dict[str, str]:
    """Validate subcategories and parent relationships."""

    required_fields = {
        "subcategory_id",
        "subcategory_code",
        "subcategory_name",
        "category_id",
        "category_code",
        "storage_type",
        "active_flag",
        "effective_from",
        "created_at",
        "updated_at",
    }
    require_fields(
        subcategories,
        required_fields,
        "subcategories",
    )

    if len(subcategories) != expected_count:
        raise ProductValidationError(
            f"Expected {expected_count} subcategories but found "
            f"{len(subcategories)}."
        )

    require_unique(
        subcategories,
        "subcategory_id",
        "subcategories",
    )
    require_unique(
        subcategories,
        "subcategory_code",
        "subcategories",
    )
    require_unique(
        subcategories,
        "subcategory_name",
        "subcategories",
    )

    allowed_storage_types = {
        "AMBIENT",
        "CHILLED",
        "FROZEN",
    }

    category_counts = Counter(
        row["category_code"] for row in subcategories
    )

    if any(count != 8 for count in category_counts.values()):
        raise ProductValidationError(
            "Every category must contain exactly eight "
            f"subcategories: {dict(category_counts)}"
        )

    for row in subcategories:
        category_code = row["category_code"]

        if category_code not in category_id_by_code:
            raise ProductValidationError(
                f"Subcategory references unknown category: "
                f"{row['subcategory_code']}"
            )

        if (
            row["category_id"]
            != category_id_by_code[category_code]
        ):
            raise ProductValidationError(
                f"Subcategory {row['subcategory_code']} contains "
                "an inconsistent category identifier."
            )

        if row["storage_type"] not in allowed_storage_types:
            raise ProductValidationError(
                f"Invalid storage type for "
                f"{row['subcategory_code']}: "
                f"{row['storage_type']}"
            )

        if row["active_flag"].lower() != "true":
            raise ProductValidationError(
                f"Initial subcategory must be active: "
                f"{row['subcategory_code']}"
            )

    return {
        row["subcategory_code"]: row["subcategory_id"]
        for row in subcategories
    }


def build_subcategory_config_mapping(
    configuration: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Create a subcategory-code configuration mapping."""

    return {
        subcategory["subcategory_code"]: {
            **subcategory,
            "category_code": category["category_code"],
        }
        for category in configuration["categories"]
        for subcategory in category["subcategories"]
    }


def validate_product_counts(
    products: list[dict[str, str]],
    configuration: dict[str, Any],
) -> None:
    """Validate total, category and subcategory product counts."""

    expected_total = int(
        configuration["expected_counts"]["products"]
    )

    if len(products) != expected_total:
        raise ProductValidationError(
            f"Expected {expected_total} products but found "
            f"{len(products)}."
        )

    expected_category_counts = {
        category["category_code"]: int(
            category["product_count"]
        )
        for category in configuration["categories"]
    }
    actual_category_counts = Counter(
        row["category_code"] for row in products
    )

    if dict(actual_category_counts) != expected_category_counts:
        raise ProductValidationError(
            "Category product counts do not match configuration. "
            f"Expected {expected_category_counts}; found "
            f"{dict(actual_category_counts)}."
        )

    expected_subcategory_counts = {
        subcategory["subcategory_code"]: int(
            subcategory["product_count"]
        )
        for category in configuration["categories"]
        for subcategory in category["subcategories"]
    }
    actual_subcategory_counts = Counter(
        row["subcategory_code"] for row in products
    )

    if (
        dict(actual_subcategory_counts)
        != expected_subcategory_counts
    ):
        raise ProductValidationError(
            "Subcategory product counts do not match "
            "configuration."
        )

    if any(
        count < 25
        for count in actual_subcategory_counts.values()
    ):
        raise ProductValidationError(
            "Every subcategory must contain at least 25 products."
        )


def validate_configured_distributions(
    products: list[dict[str, str]],
    configuration: dict[str, Any],
) -> None:
    """Validate brand, demand-tier and origin distributions."""

    product_count = len(products)

    actual_brand_counts = Counter(
        row["brand_type"] for row in products
    )
    expected_brand_counts = expected_distribution_counts(
        configuration["brand_distribution"],
        product_count,
    )

    if dict(actual_brand_counts) != expected_brand_counts:
        raise ProductValidationError(
            "Brand distribution does not match configuration. "
            f"Expected {expected_brand_counts}; found "
            f"{dict(actual_brand_counts)}."
        )

    demand_distribution = {
        tier_name: tier_config["product_share"]
        for tier_name, tier_config in configuration[
            "demand_tiers"
        ].items()
    }
    expected_demand_counts = expected_distribution_counts(
        demand_distribution,
        product_count,
    )
    actual_demand_counts = Counter(
        row["demand_tier"] for row in products
    )

    if dict(actual_demand_counts) != expected_demand_counts:
        raise ProductValidationError(
            "Demand-tier distribution does not match "
            "configuration."
        )

    expected_origin_counts = expected_distribution_counts(
        configuration["country_of_origin_distribution"],
        product_count,
    )
    actual_origin_counts = Counter(
        row["origin_group"] for row in products
    )

    if dict(actual_origin_counts) != expected_origin_counts:
        raise ProductValidationError(
            "Country-of-origin distribution does not match "
            "configuration."
        )


def validate_products(
    products: list[dict[str, str]],
    configuration: dict[str, Any],
    category_id_by_code: dict[str, str],
    subcategory_id_by_code: dict[str, str],
) -> None:
    """Run detailed product validation rules."""

    required_fields = {
        "product_id",
        "product_code",
        "sku",
        "product_name",
        "category_id",
        "category_code",
        "subcategory_id",
        "subcategory_code",
        "brand_type",
        "brand_name",
        "unit_of_measure",
        "package_size",
        "case_pack_quantity",
        "storage_type",
        "shelf_life_days",
        "unit_cost",
        "standard_retail_price",
        "gross_margin_rate",
        "vat_rate",
        "reorder_level",
        "safety_stock_quantity",
        "demand_tier",
        "relative_demand_weight",
        "country_of_origin",
        "origin_group",
        "perishable_flag",
        "age_restricted_flag",
        "active_flag",
        "effective_from",
        "created_at",
        "updated_at",
    }
    require_fields(products, required_fields, "products")

    validate_product_counts(products, configuration)

    require_unique(products, "product_id", "products")
    require_unique(products, "product_code", "products")
    require_unique(products, "sku", "products")
    require_unique(products, "product_name", "products")

    subcategory_config_by_code = (
        build_subcategory_config_mapping(configuration)
    )
    permitted_brand_types = set(
        configuration["brand_distribution"]
    )
    permitted_demand_tiers = set(
        configuration["demand_tiers"]
    )
    permitted_origin_groups = set(
        configuration["country_of_origin_distribution"]
    )
    permitted_vat_rates = {
        Decimal("0.000000"),
        Decimal("0.200000"),
    }

    for row in products:
        category_code = row["category_code"]
        subcategory_code = row["subcategory_code"]

        if category_code not in category_id_by_code:
            raise ProductValidationError(
                f"Product references unknown category: "
                f"{row['product_code']}"
            )

        if (
            row["category_id"]
            != category_id_by_code[category_code]
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has an "
                "inconsistent category identifier."
            )

        if (
            subcategory_code
            not in subcategory_id_by_code
        ):
            raise ProductValidationError(
                f"Product references unknown subcategory: "
                f"{row['product_code']}"
            )

        if (
            row["subcategory_id"]
            != subcategory_id_by_code[subcategory_code]
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has an "
                "inconsistent subcategory identifier."
            )

        subcategory_config = (
            subcategory_config_by_code[subcategory_code]
        )

        if (
            category_code
            != subcategory_config["category_code"]
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} category and "
                "subcategory do not agree."
            )

        if (
            row["storage_type"]
            != subcategory_config["storage_type"]
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "storage type."
            )

        if row["brand_type"] not in permitted_brand_types:
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "brand type."
            )

        if (
            row["demand_tier"]
            not in permitted_demand_tiers
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "demand tier."
            )

        if (
            row["origin_group"]
            not in permitted_origin_groups
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "origin group."
            )

        valid_country_pool = set(
            configuration["country_pools"][
                row["origin_group"]
            ]
        )

        if row["country_of_origin"] not in valid_country_pool:
            raise ProductValidationError(
                f"Product {row['product_code']} country does not "
                "match its origin group."
            )

        unit_cost = Decimal(row["unit_cost"])
        retail_price = Decimal(
            row["standard_retail_price"]
        )
        gross_margin_rate = Decimal(
            row["gross_margin_rate"]
        )
        vat_rate = Decimal(row["vat_rate"])

        if unit_cost < 0:
            raise ProductValidationError(
                f"Product {row['product_code']} has negative cost."
            )

        if retail_price <= 0:
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "retail price."
            )

        if unit_cost > retail_price:
            raise ProductValidationError(
                f"Product {row['product_code']} cost exceeds "
                "retail price."
            )

        minimum_margin = Decimal(
            str(
                configuration["common_rules"][
                    "minimum_gross_margin_rate"
                ]
            )
        )
        maximum_margin = Decimal(
            str(
                configuration["common_rules"][
                    "maximum_gross_margin_rate"
                ]
            )
        )

        if not (
            minimum_margin
            <= gross_margin_rate
            <= maximum_margin
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has an invalid "
                "gross margin."
            )

        if vat_rate not in permitted_vat_rates:
            raise ProductValidationError(
                f"Product {row['product_code']} has unsupported "
                f"VAT rate {vat_rate}."
            )

        if int(row["case_pack_quantity"]) <= 0:
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "case-pack quantity."
            )

        if int(row["shelf_life_days"]) <= 0:
            raise ProductValidationError(
                f"Product {row['product_code']} has invalid "
                "shelf life."
            )

        if int(row["reorder_level"]) < 0:
            raise ProductValidationError(
                f"Product {row['product_code']} has negative "
                "reorder level."
            )

        if int(row["safety_stock_quantity"]) < 0:
            raise ProductValidationError(
                f"Product {row['product_code']} has negative "
                "safety stock."
            )

        expected_perishable = str(
            subcategory_config["perishable_flag"]
        ).lower()

        if row["perishable_flag"].lower() != expected_perishable:
            raise ProductValidationError(
                f"Product {row['product_code']} has incorrect "
                "perishable status."
            )

        expected_age_restricted = str(
            subcategory_config["age_restricted_flag"]
        ).lower()

        if (
            row["age_restricted_flag"].lower()
            != expected_age_restricted
        ):
            raise ProductValidationError(
                f"Product {row['product_code']} has incorrect "
                "age-restriction status."
            )

        if row["active_flag"].lower() != "true":
            raise ProductValidationError(
                f"Initial product must be active: "
                f"{row['product_code']}"
            )

    validate_configured_distributions(
        products,
        configuration,
    )


def validate_manifest(
    manifest: dict[str, Any],
    category_count: int,
    subcategory_count: int,
    product_count: int,
) -> None:
    """Validate manifest record counts and file hashes."""

    expected_counts = {
        "categories": category_count,
        "subcategories": subcategory_count,
        "products": product_count,
    }

    if manifest.get("record_counts") != expected_counts:
        raise ProductValidationError(
            "Product manifest counts do not match generated files."
        )

    file_paths = {
        "categories.csv": CATEGORIES_PATH,
        "subcategories.csv": SUBCATEGORIES_PATH,
        "products.csv": PRODUCTS_PATH,
    }

    for file_name, file_path in file_paths.items():
        expected_hash = manifest["files"][file_name]["sha256"]
        actual_hash = calculate_sha256(file_path)

        if expected_hash != actual_hash:
            raise ProductValidationError(
                f"Manifest hash does not match {file_name}."
            )


def validate_all() -> dict[str, int]:
    """Run the complete product validation framework."""

    configuration = load_json(CONFIG_PATH)
    categories = load_csv(CATEGORIES_PATH)
    subcategories = load_csv(SUBCATEGORIES_PATH)
    products = load_csv(PRODUCTS_PATH)
    manifest = load_json(MANIFEST_PATH)

    category_id_by_code = validate_categories(
        categories,
        int(configuration["expected_counts"]["categories"]),
    )

    subcategory_id_by_code = validate_subcategories(
        subcategories,
        int(
            configuration["expected_counts"][
                "subcategories"
            ]
        ),
        category_id_by_code,
    )

    validate_products(
        products,
        configuration,
        category_id_by_code,
        subcategory_id_by_code,
    )

    validate_manifest(
        manifest,
        len(categories),
        len(subcategories),
        len(products),
    )

    return {
        "categories": len(categories),
        "subcategories": len(subcategories),
        "products": len(products),
    }


def main() -> None:
    """Execute validation and print a concise result."""

    counts = validate_all()

    print("BritMart product validation passed.")
    print(f"Categories validated: {counts['categories']}")
    print(
        f"Subcategories validated: "
        f"{counts['subcategories']}"
    )
    print(f"Products validated: {counts['products']}")


if __name__ == "__main__":
    main()