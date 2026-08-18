"""Generate deterministic BritMart category, subcategory and product data."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import uuid
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


GENERATOR_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = GENERATOR_ROOT / "config" / "product_config.json"
OUTPUT_DIRECTORY = GENERATOR_ROOT / "output"

CATEGORIES_OUTPUT_PATH = OUTPUT_DIRECTORY / "categories.csv"
SUBCATEGORIES_OUTPUT_PATH = OUTPUT_DIRECTORY / "subcategories.csv"
PRODUCTS_OUTPUT_PATH = OUTPUT_DIRECTORY / "products.csv"
MANIFEST_OUTPUT_PATH = OUTPUT_DIRECTORY / "product_manifest.json"

MONEY_PRECISION = Decimal("0.0001")
PRICE_PRECISION = Decimal("0.01")

TIER_INVENTORY_RANGES = {
    "A": {
        "reorder": (120, 250),
        "safety": (60, 150),
    },
    "B": {
        "reorder": (70, 180),
        "safety": (35, 100),
    },
    "C": {
        "reorder": (25, 100),
        "safety": (12, 60),
    },
    "D": {
        "reorder": (5, 40),
        "safety": (3, 25),
    },
}


def load_configuration() -> dict[str, Any]:
    """Load and validate the product configuration."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Product configuration was not found: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        configuration = json.load(config_file)

    required_sections = {
        "project",
        "expected_counts",
        "brand_distribution",
        "brand_names",
        "demand_tiers",
        "country_of_origin_distribution",
        "country_pools",
        "common_rules",
        "categories",
    }
    missing_sections = required_sections.difference(configuration)

    if missing_sections:
        raise ValueError(
            f"Configuration is missing sections: "
            f"{sorted(missing_sections)}"
        )

    validate_configuration_counts(configuration)
    validate_probability_distribution(
        configuration["brand_distribution"],
        "brand_distribution",
    )
    validate_probability_distribution(
        configuration["country_of_origin_distribution"],
        "country_of_origin_distribution",
    )

    demand_distribution = {
        tier_name: tier_config["product_share"]
        for tier_name, tier_config in configuration[
            "demand_tiers"
        ].items()
    }
    validate_probability_distribution(
        demand_distribution,
        "demand_tiers",
    )

    return configuration


def validate_probability_distribution(
    distribution: dict[str, float],
    distribution_name: str,
) -> None:
    """Confirm that configured probabilities total one."""

    total_probability = sum(
        float(value) for value in distribution.values()
    )

    if abs(total_probability - 1.0) > 0.000001:
        raise ValueError(
            f"{distribution_name} probabilities must total 1.0; "
            f"found {total_probability}."
        )

    if any(float(value) < 0 for value in distribution.values()):
        raise ValueError(
            f"{distribution_name} contains a negative probability."
        )


def validate_configuration_counts(
    configuration: dict[str, Any],
) -> None:
    """Confirm category, subcategory and product totals."""

    categories = configuration["categories"]
    expected_counts = configuration["expected_counts"]

    if len(categories) != int(expected_counts["categories"]):
        raise ValueError(
            "Configured category count does not match "
            "expected_counts."
        )

    subcategories = [
        subcategory
        for category in categories
        for subcategory in category["subcategories"]
    ]

    if len(subcategories) != int(
        expected_counts["subcategories"]
    ):
        raise ValueError(
            "Configured subcategory count does not match "
            "expected_counts."
        )

    configured_product_count = sum(
        int(subcategory["product_count"])
        for subcategory in subcategories
    )

    if configured_product_count != int(
        expected_counts["products"]
    ):
        raise ValueError(
            f"Configured product count is "
            f"{configured_product_count}; expected "
            f"{expected_counts['products']}."
        )

    category_codes = [
        category["category_code"] for category in categories
    ]
    subcategory_codes = [
        subcategory["subcategory_code"]
        for subcategory in subcategories
    ]

    if len(category_codes) != len(set(category_codes)):
        raise ValueError("Category codes must be unique.")

    if len(subcategory_codes) != len(set(subcategory_codes)):
        raise ValueError("Subcategory codes must be unique.")

    for category in categories:
        category_product_count = sum(
            int(subcategory["product_count"])
            for subcategory in category["subcategories"]
        )

        if category_product_count != int(
            category["product_count"]
        ):
            raise ValueError(
                f"{category['category_code']} contains "
                f"{category_product_count} products but declares "
                f"{category['product_count']}."
            )


def deterministic_uuid(
    namespace: uuid.UUID,
    entity_type: str,
    business_code: str,
) -> str:
    """Return a stable UUID derived from a business code."""

    canonical_name = f"britmart:{entity_type}:{business_code}"
    return str(uuid.uuid5(namespace, canonical_name))


def build_exact_distribution_sequence(
    distribution: dict[str, float],
    total_count: int,
    random_generator: random.Random,
) -> list[str]:
    """Build a shuffled sequence with exact configured proportions."""

    item_names = list(distribution)
    allocated_counts: dict[str, int] = {}
    running_total = 0

    for item_name in item_names[:-1]:
        item_count = round(
            float(distribution[item_name]) * total_count
        )
        allocated_counts[item_name] = item_count
        running_total += item_count

    final_item = item_names[-1]
    allocated_counts[final_item] = total_count - running_total

    sequence: list[str] = []

    for item_name, item_count in allocated_counts.items():
        sequence.extend([item_name] * item_count)

    if len(sequence) != total_count:
        raise ValueError(
            "Distribution sequence does not match total count."
        )

    random_generator.shuffle(sequence)
    return sequence


def write_csv(
    file_path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    """Write records using a stable UTF-8 CSV structure."""

    if not rows:
        raise ValueError(f"No records supplied for {file_path.name}")

    with file_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def calculate_sha256(file_path: Path) -> str:
    """Return the SHA-256 hash of a generated file."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(65536), b""):
            sha256.update(block)

    return sha256.hexdigest()


def random_decimal(
    random_generator: random.Random,
    minimum: float,
    maximum: float,
    precision: Decimal,
) -> Decimal:
    """Return a deterministic decimal between two boundaries."""

    minimum_decimal = Decimal(str(minimum))
    maximum_decimal = Decimal(str(maximum))
    random_fraction = Decimal(
        str(random_generator.random())
    )

    value = minimum_decimal + (
        maximum_decimal - minimum_decimal
    ) * random_fraction

    return value.quantize(
        precision,
        rounding=ROUND_HALF_UP,
    )


def generate_categories(
    configuration: dict[str, Any],
    namespace: uuid.UUID,
    generated_at: str,
) -> list[dict[str, Any]]:
    """Generate category records."""

    records: list[dict[str, Any]] = []

    for category in configuration["categories"]:
        category_code = category["category_code"]

        records.append(
            {
                "category_id": deterministic_uuid(
                    namespace,
                    "category",
                    category_code,
                ),
                "category_code": category_code,
                "category_name": category["category_name"],
                "active_flag": True,
                "effective_from": configuration["common_rules"][
                    "effective_from"
                ],
                "effective_to": "",
                "created_at": generated_at,
                "updated_at": generated_at,
            }
        )

    return records


def generate_subcategories(
    configuration: dict[str, Any],
    namespace: uuid.UUID,
    category_id_by_code: dict[str, str],
    generated_at: str,
) -> list[dict[str, Any]]:
    """Generate subcategory records."""

    records: list[dict[str, Any]] = []

    for category in configuration["categories"]:
        category_code = category["category_code"]

        for subcategory in category["subcategories"]:
            subcategory_code = subcategory["subcategory_code"]

            records.append(
                {
                    "subcategory_id": deterministic_uuid(
                        namespace,
                        "subcategory",
                        subcategory_code,
                    ),
                    "subcategory_code": subcategory_code,
                    "subcategory_name": subcategory[
                        "subcategory_name"
                    ],
                    "category_id": category_id_by_code[
                        category_code
                    ],
                    "category_code": category_code,
                    "storage_type": subcategory["storage_type"],
                    "active_flag": True,
                    "effective_from": configuration[
                        "common_rules"
                    ]["effective_from"],
                    "effective_to": "",
                    "created_at": generated_at,
                    "updated_at": generated_at,
                }
            )

    return records


def select_brand_name(
    configuration: dict[str, Any],
    brand_type: str,
    random_generator: random.Random,
) -> str:
    """Select a synthetic brand belonging to the configured type."""

    brand_pool = configuration["brand_names"][brand_type]

    if not brand_pool:
        raise ValueError(
            f"No brand names configured for {brand_type}."
        )

    return random_generator.choice(brand_pool)


def select_country_of_origin(
    configuration: dict[str, Any],
    origin_group: str,
    random_generator: random.Random,
) -> str:
    """Select a country from a configured origin group."""

    country_pool = configuration["country_pools"][
        origin_group
    ]

    if not country_pool:
        raise ValueError(
            f"No countries configured for {origin_group}."
        )

    return random_generator.choice(country_pool)


def create_unique_product_name(
    brand_name: str,
    name_term: str,
    package_size: str,
    existing_names: set[str],
) -> str:
    """Create a readable and unique synthetic product name."""

    base_name = f"{brand_name} {name_term} {package_size}"
    product_name = base_name
    variant_number = 2

    while product_name in existing_names:
        product_name = (
            f"{base_name} Variant {variant_number}"
        )
        variant_number += 1

    existing_names.add(product_name)
    return product_name


def generate_products(
    configuration: dict[str, Any],
    namespace: uuid.UUID,
    random_generator: random.Random,
    category_id_by_code: dict[str, str],
    subcategory_id_by_code: dict[str, str],
    generated_at: str,
) -> list[dict[str, Any]]:
    """Generate the complete 2,000-product catalogue."""

    product_count = int(
        configuration["expected_counts"]["products"]
    )

    brand_types = build_exact_distribution_sequence(
        configuration["brand_distribution"],
        product_count,
        random_generator,
    )

    demand_distribution = {
        tier_name: tier_config["product_share"]
        for tier_name, tier_config in configuration[
            "demand_tiers"
        ].items()
    }
    demand_tiers = build_exact_distribution_sequence(
        demand_distribution,
        product_count,
        random_generator,
    )

    origin_groups = build_exact_distribution_sequence(
        configuration["country_of_origin_distribution"],
        product_count,
        random_generator,
    )

    records: list[dict[str, Any]] = []
    existing_product_names: set[str] = set()
    product_sequence = 1

    common_rules = configuration["common_rules"]

    for category in configuration["categories"]:
        category_code = category["category_code"]

        for subcategory in category["subcategories"]:
            subcategory_code = subcategory[
                "subcategory_code"
            ]

            for _ in range(int(subcategory["product_count"])):
                product_code = f"PRD-{product_sequence:06d}"
                sku = f"BM-{product_sequence:08d}"

                brand_type = brand_types[
                    product_sequence - 1
                ]
                demand_tier = demand_tiers[
                    product_sequence - 1
                ]
                origin_group = origin_groups[
                    product_sequence - 1
                ]

                brand_name = select_brand_name(
                    configuration,
                    brand_type,
                    random_generator,
                )
                name_term = random_generator.choice(
                    subcategory["name_terms"]
                )
                package_size = random_generator.choice(
                    subcategory["package_options"]
                )
                unit_of_measure = random_generator.choice(
                    subcategory["unit_options"]
                )

                product_name = create_unique_product_name(
                    brand_name,
                    name_term,
                    package_size,
                    existing_product_names,
                )

                retail_price = random_decimal(
                    random_generator,
                    subcategory["retail_price"]["minimum"],
                    subcategory["retail_price"]["maximum"],
                    PRICE_PRECISION,
                )

                gross_margin_rate = random_decimal(
                    random_generator,
                    common_rules["minimum_gross_margin_rate"],
                    common_rules["maximum_gross_margin_rate"],
                    Decimal("0.000001"),
                )

                unit_cost = (
                    retail_price
                    * (Decimal("1") - gross_margin_rate)
                ).quantize(
                    MONEY_PRECISION,
                    rounding=ROUND_HALF_UP,
                )

                shelf_life_days = random_generator.randint(
                    int(
                        subcategory["shelf_life_days"][
                            "minimum"
                        ]
                    ),
                    int(
                        subcategory["shelf_life_days"][
                            "maximum"
                        ]
                    ),
                )

                case_pack_quantity = random_generator.randint(
                    int(
                        common_rules[
                            "minimum_case_pack_quantity"
                        ]
                    ),
                    int(
                        common_rules[
                            "maximum_case_pack_quantity"
                        ]
                    ),
                )

                inventory_range = TIER_INVENTORY_RANGES[
                    demand_tier
                ]
                reorder_level = random_generator.randint(
                    inventory_range["reorder"][0],
                    inventory_range["reorder"][1],
                )
                safety_stock_quantity = (
                    random_generator.randint(
                        inventory_range["safety"][0],
                        inventory_range["safety"][1],
                    )
                )

                country_of_origin = select_country_of_origin(
                    configuration,
                    origin_group,
                    random_generator,
                )

                demand_weight = configuration[
                    "demand_tiers"
                ][demand_tier]["relative_demand_weight"]

                records.append(
                    {
                        "product_id": deterministic_uuid(
                            namespace,
                            "product",
                            product_code,
                        ),
                        "product_code": product_code,
                        "sku": sku,
                        "product_name": product_name,
                        "category_id": category_id_by_code[
                            category_code
                        ],
                        "category_code": category_code,
                        "subcategory_id": (
                            subcategory_id_by_code[
                                subcategory_code
                            ]
                        ),
                        "subcategory_code": subcategory_code,
                        "brand_type": brand_type,
                        "brand_name": brand_name,
                        "unit_of_measure": unit_of_measure,
                        "package_size": package_size,
                        "case_pack_quantity": (
                            case_pack_quantity
                        ),
                        "storage_type": subcategory[
                            "storage_type"
                        ],
                        "shelf_life_days": shelf_life_days,
                        "unit_cost": format(
                            unit_cost,
                            ".4f",
                        ),
                        "standard_retail_price": format(
                            retail_price,
                            ".2f",
                        ),
                        "gross_margin_rate": format(
                            gross_margin_rate,
                            ".6f",
                        ),
                        "vat_rate": format(
                            Decimal(
                                str(subcategory["vat_rate"])
                            ),
                            ".6f",
                        ),
                        "reorder_level": reorder_level,
                        "safety_stock_quantity": (
                            safety_stock_quantity
                        ),
                        "demand_tier": demand_tier,
                        "relative_demand_weight": (
                            demand_weight
                        ),
                        "country_of_origin": (
                            country_of_origin
                        ),
                        "origin_group": origin_group,
                        "perishable_flag": subcategory[
                            "perishable_flag"
                        ],
                        "age_restricted_flag": subcategory[
                            "age_restricted_flag"
                        ],
                        "active_flag": True,
                        "effective_from": common_rules[
                            "effective_from"
                        ],
                        "effective_to": "",
                        "created_at": generated_at,
                        "updated_at": generated_at,
                    }
                )

                product_sequence += 1

    if len(records) != product_count:
        raise ValueError(
            f"Generated {len(records)} products; expected "
            f"{product_count}."
        )

    return records


def write_manifest(
    configuration: dict[str, Any],
    generated_at: str,
    category_count: int,
    subcategory_count: int,
    product_count: int,
) -> None:
    """Write an auditable product-generation manifest."""

    output_files = [
        CATEGORIES_OUTPUT_PATH,
        SUBCATEGORIES_OUTPUT_PATH,
        PRODUCTS_OUTPUT_PATH,
    ]

    manifest = {
        "dataset_name": "BritMart product master data",
        "dataset_version": configuration["project"][
            "dataset_version"
        ],
        "master_seed": configuration["project"][
            "master_seed"
        ],
        "generated_at": generated_at,
        "record_counts": {
            "categories": category_count,
            "subcategories": subcategory_count,
            "products": product_count,
        },
        "files": {
            file_path.name: {
                "sha256": calculate_sha256(file_path),
                "size_bytes": file_path.stat().st_size,
            }
            for file_path in output_files
        },
    }

    with MANIFEST_OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as manifest_file:
        json.dump(
            manifest,
            manifest_file,
            indent=2,
            sort_keys=True,
        )
        manifest_file.write("\n")


def main() -> None:
    """Generate the complete BritMart product master dataset."""

    configuration = load_configuration()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    namespace = uuid.UUID(
        configuration["project"]["uuid_namespace"]
    )
    random_generator = random.Random(
        int(configuration["project"]["master_seed"])
        + 1000
    )
    generated_at = str(
        configuration["project"]["generated_timestamp"]
    )

    categories = generate_categories(
        configuration,
        namespace,
        generated_at,
    )

    category_id_by_code = {
        record["category_code"]: record["category_id"]
        for record in categories
    }

    subcategories = generate_subcategories(
        configuration,
        namespace,
        category_id_by_code,
        generated_at,
    )

    subcategory_id_by_code = {
        record["subcategory_code"]: record[
            "subcategory_id"
        ]
        for record in subcategories
    }

    products = generate_products(
        configuration,
        namespace,
        random_generator,
        category_id_by_code,
        subcategory_id_by_code,
        generated_at,
    )

    write_csv(
        CATEGORIES_OUTPUT_PATH,
        categories,
        [
            "category_id",
            "category_code",
            "category_name",
            "active_flag",
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        ],
    )

    write_csv(
        SUBCATEGORIES_OUTPUT_PATH,
        subcategories,
        [
            "subcategory_id",
            "subcategory_code",
            "subcategory_name",
            "category_id",
            "category_code",
            "storage_type",
            "active_flag",
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        ],
    )

    write_csv(
        PRODUCTS_OUTPUT_PATH,
        products,
        [
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
            "effective_to",
            "created_at",
            "updated_at",
        ],
    )

    write_manifest(
        configuration,
        generated_at,
        len(categories),
        len(subcategories),
        len(products),
    )

    print("BritMart product master data generated successfully.")
    print(f"Categories: {len(categories)}")
    print(f"Subcategories: {len(subcategories)}")
    print(f"Products: {len(products)}")
    print(f"Output directory: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()