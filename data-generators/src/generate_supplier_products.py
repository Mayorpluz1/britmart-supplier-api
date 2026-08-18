"""Generate deterministic BritMart supplier-product agreements."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "data-generators"
    / "config"
    / "supplier_product_config.json"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "output"
)

PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"

AGREEMENT_OUTPUT_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_products.csv"
)

MANIFEST_OUTPUT_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_product_manifest.json"
)

AGREEMENT_FIELDS = [
    "supplier_product_id",
    "supplier_id",
    "supplier_code",
    "product_id",
    "product_code",
    "sku",
    "supplier_product_code",
    "agreement_role",
    "is_primary_supplier",
    "agreement_status",
    "agreement_currency_code",
    "base_unit_cost_gbp",
    "agreed_unit_cost",
    "gbp_value_per_currency_unit",
    "minimum_order_quantity",
    "order_multiple",
    "agreed_lead_time_days",
    "minimum_remaining_shelf_life_days",
    "effective_from",
    "effective_to",
    "created_at",
    "updated_at",
    "version_number",
]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON configuration file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required JSON file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def load_csv(path: Path) -> list[dict[str, str]]:
    """Load a CSV file as dictionaries."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required CSV file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        return list(csv.DictReader(source_file))


def as_boolean(value: Any) -> bool:
    """Convert common Boolean representations to Python Boolean."""

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def boolean_text(value: bool) -> str:
    """Return a consistent CSV Boolean value."""

    return "true" if value else "false"


def decimal_value(value: Any) -> Decimal:
    """Convert a value into a Decimal safely."""

    return Decimal(str(value))


def random_decimal(
    minimum: Any,
    maximum: Any,
    decimal_places: int,
    random_generator: random.Random,
) -> Decimal:
    """Generate a deterministic decimal within a range."""

    multiplier = 10**decimal_places

    minimum_integer = int(
        decimal_value(minimum) * multiplier
    )
    maximum_integer = int(
        decimal_value(maximum) * multiplier
    )

    selected_integer = random_generator.randint(
        minimum_integer,
        maximum_integer,
    )

    quantizer = Decimal("1").scaleb(
        -decimal_places
    )

    return (
        Decimal(selected_integer)
        / Decimal(multiplier)
    ).quantize(quantizer)


def calculate_sha256(path: Path) -> str:
    """Calculate a SHA-256 digest for a file."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def validate_source_counts(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Validate source master-data record counts."""

    expected_counts = config["expected_counts"]

    expected_products = int(
        expected_counts["products"]
    )
    expected_suppliers = int(
        expected_counts["suppliers"]
    )

    if len(products) != expected_products:
        raise ValueError(
            f"Expected {expected_products} products, "
            f"but found {len(products)}."
        )

    if len(suppliers) != expected_suppliers:
        raise ValueError(
            f"Expected {expected_suppliers} suppliers, "
            f"but found {len(suppliers)}."
        )


def validate_source_keys(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
) -> None:
    """Validate source business and technical key uniqueness."""

    product_ids = [
        row["product_id"]
        for row in products
    ]
    product_codes = [
        row["product_code"]
        for row in products
    ]
    supplier_ids = [
        row["supplier_id"]
        for row in suppliers
    ]
    supplier_codes = [
        row["supplier_code"]
        for row in suppliers
    ]

    if len(product_ids) != len(set(product_ids)):
        raise ValueError(
            "Duplicate product_id values detected."
        )

    if len(product_codes) != len(
        set(product_codes)
    ):
        raise ValueError(
            "Duplicate product_code values detected."
        )

    if len(supplier_ids) != len(
        set(supplier_ids)
    ):
        raise ValueError(
            "Duplicate supplier_id values detected."
        )

    if len(supplier_codes) != len(
        set(supplier_codes)
    ):
        raise ValueError(
            "Duplicate supplier_code values detected."
        )


def supplier_supports_product(
    supplier: dict[str, str],
    product: dict[str, str],
    config: dict[str, Any],
) -> bool:
    """Determine whether a supplier can supply a product."""

    eligibility = config[
        "supplier_eligibility"
    ]

    if (
        supplier["supplier_status"]
        not in eligibility["eligible_statuses"]
    ):
        return False

    if (
        eligibility["require_active_flag"]
        and not as_boolean(supplier["active_flag"])
    ):
        return False

    supplier_categories = {
        value.strip()
        for value in supplier[
            "category_codes"
        ].split("|")
        if value.strip()
    }

    if (
        eligibility["require_category_match"]
        and product["category_code"]
        not in supplier_categories
    ):
        return False

    if eligibility["require_storage_match"]:
        storage_column = {
            "AMBIENT": "supports_ambient",
            "CHILLED": "supports_chilled",
            "FROZEN": "supports_frozen",
        }.get(product["storage_type"])

        if storage_column is None:
            return False

        if not as_boolean(
            supplier[storage_column]
        ):
            return False

    return True


def build_candidate_map(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    """Build eligible suppliers for each product."""

    candidate_map: dict[
        str,
        list[dict[str, str]],
    ] = {}

    for product in products:
        candidates = [
            supplier
            for supplier in suppliers
            if supplier_supports_product(
                supplier,
                product,
                config,
            )
        ]

        if not candidates:
            raise ValueError(
                "No eligible supplier found for "
                f"{product['product_code']} "
                f"({product['category_code']}, "
                f"{product['storage_type']})."
            )

        candidate_map[
            product["product_id"]
        ] = candidates

    return candidate_map


def choose_balanced_supplier(
    candidates: list[dict[str, str]],
    primary_counts: Counter,
    total_counts: Counter,
    config: dict[str, Any],
    random_generator: random.Random,
    agreement_role: str,
    excluded_supplier_id: str | None = None,
    preferred_different_origin: str | None = None,
) -> dict[str, str]:
    """Choose an eligible supplier while balancing workload."""

    controls = config["allocation_controls"]

    maximum_primary = int(
        controls[
            "maximum_primary_products_per_supplier"
        ]
    )
    maximum_total = int(
        controls[
            "maximum_total_products_per_supplier"
        ]
    )

    available_candidates = []

    for supplier in candidates:
        supplier_id = supplier["supplier_id"]

        if (
            excluded_supplier_id
            and supplier_id == excluded_supplier_id
        ):
            continue

        if total_counts[supplier_id] >= maximum_total:
            continue

        if (
            agreement_role == "PRIMARY"
            and primary_counts[supplier_id]
            >= maximum_primary
        ):
            continue

        available_candidates.append(supplier)

    if not available_candidates:
        raise ValueError(
            f"No supplier capacity remains for "
            f"{agreement_role} allocation."
        )

    if preferred_different_origin:
        diversified_candidates = [
            supplier
            for supplier in available_candidates
            if supplier["origin_group"]
            != preferred_different_origin
        ]

        if diversified_candidates:
            available_candidates = (
                diversified_candidates
            )

    random_generator.shuffle(
        available_candidates
    )

    available_candidates.sort(
        key=lambda supplier: (
            total_counts[
                supplier["supplier_id"]
            ],
            primary_counts[
                supplier["supplier_id"]
            ],
            supplier["supplier_code"],
        )
    )

    lowest_total = total_counts[
        available_candidates[0]["supplier_id"]
    ]

    lowest_group = [
        supplier
        for supplier in available_candidates
        if total_counts[supplier["supplier_id"]]
        == lowest_total
    ]

    return random_generator.choice(
        lowest_group
    )


def demand_tier_name(
    product: dict[str, str],
) -> str:
    """Map product demand tiers to configuration names."""

    return {
        "A": "HIGH",
        "B": "MEDIUM",
        "C": "LOW",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
    }.get(
        product["demand_tier"].upper(),
        "MEDIUM",
    )


def select_secondary_products(
    products: list[dict[str, str]],
    secondary_count: int,
    config: dict[str, Any],
    random_generator: random.Random,
) -> list[dict[str, str]]:
    """Select products requiring secondary supply resilience."""

    priority_weights = config[
        "secondary_supplier_priority"
    ]

    scored_products = []

    for product in products:
        tier = demand_tier_name(product)
        weight = Decimal(
            str(priority_weights[tier])
        )

        random_value = max(
            random_generator.random(),
            0.0000001,
        )

        score = random_value ** (
            1.0 / float(weight)
        )

        scored_products.append(
            (
                score,
                product["product_code"],
                product,
            )
        )

    scored_products.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    return [
        item[2]
        for item in scored_products[
            :secondary_count
        ]
    ]


def calculate_agreement_values(
    product: dict[str, str],
    supplier: dict[str, str],
    agreement_role: str,
    config: dict[str, Any],
    random_generator: random.Random,
) -> dict[str, Any]:
    """Calculate agreement cost, quantity and logistics terms."""

    commercial_rules = config[
        "commercial_rules"
    ]

    multiplier_key = (
        "primary_cost_multiplier"
        if agreement_role == "PRIMARY"
        else "secondary_cost_multiplier"
    )

    multiplier_config = commercial_rules[
        multiplier_key
    ]

    cost_multiplier = random_decimal(
        multiplier_config["minimum"],
        multiplier_config["maximum"],
        4,
        random_generator,
    )

    base_unit_cost_gbp = decimal_value(
        product["unit_cost"]
    )

    currency_code = supplier[
        "default_currency_code"
    ]

    currency_rates = config[
        "currency_conversion"
    ]["rates"]

    if currency_code not in currency_rates:
        raise ValueError(
            f"No currency rate configured for "
            f"{currency_code}."
        )

    gbp_value_per_currency_unit = (
        decimal_value(
            currency_rates[currency_code]
        )
    )

    agreed_cost_gbp = (
        base_unit_cost_gbp
        * cost_multiplier
    )

    agreed_unit_cost = (
        agreed_cost_gbp
        / gbp_value_per_currency_unit
    ).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )

    demand_tier = demand_tier_name(product)

    quantity_config = commercial_rules[
        "minimum_order_quantity_by_demand_tier"
    ][demand_tier]

    minimum_cases = random_generator.randint(
        int(quantity_config["minimum_cases"]),
        int(quantity_config["maximum_cases"]),
    )

    case_pack_quantity = decimal_value(
        product["case_pack_quantity"]
    )

    minimum_order_quantity = (
        case_pack_quantity
        * Decimal(minimum_cases)
    ).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )

    lead_adjustment = commercial_rules[
        "lead_time_adjustment_days"
    ]

    agreed_lead_time_days = max(
        1,
        int(
            supplier[
                "standard_lead_time_days"
            ]
        )
        + random_generator.randint(
            int(lead_adjustment["minimum"]),
            int(lead_adjustment["maximum"]),
        ),
    )

    shelf_life_days = int(
        product["shelf_life_days"]
    )

    if shelf_life_days > 0:
        remaining_rate = decimal_value(
            commercial_rules[
                "minimum_remaining_shelf_life_rate"
            ][product["storage_type"]]
        )

        minimum_remaining_shelf_life_days = (
            math.ceil(
                shelf_life_days
                * float(remaining_rate)
            )
        )
    else:
        minimum_remaining_shelf_life_days = ""

    return {
        "base_unit_cost_gbp": format(
            base_unit_cost_gbp.quantize(
                Decimal("0.0001")
            ),
            ".4f",
        ),
        "agreed_unit_cost": format(
            agreed_unit_cost,
            ".4f",
        ),
        "agreement_currency_code": (
            currency_code
        ),
        "gbp_value_per_currency_unit": format(
            gbp_value_per_currency_unit.quantize(
                Decimal("0.000001")
            ),
            ".6f",
        ),
        "minimum_order_quantity": format(
            minimum_order_quantity,
            ".3f",
        ),
        "order_multiple": format(
            case_pack_quantity.quantize(
                Decimal("0.001")
            ),
            ".3f",
        ),
        "agreed_lead_time_days": (
            agreed_lead_time_days
        ),
        "minimum_remaining_shelf_life_days": (
            minimum_remaining_shelf_life_days
        ),
    }


def create_agreement(
    product: dict[str, str],
    supplier: dict[str, str],
    agreement_role: str,
    sequence_number: int,
    config: dict[str, Any],
    namespace_uuid: UUID,
    random_generator: random.Random,
) -> dict[str, Any]:
    """Create one supplier-product agreement record."""

    project_config = config["project"]
    commercial_rules = config[
        "commercial_rules"
    ]

    supplier_product_code = (
        f"{supplier['supplier_code']}-"
        f"{product['sku']}"
    )

    supplier_product_id = uuid5(
        namespace_uuid,
        (
            "britmart:supplier-product:"
            f"{supplier['supplier_id']}:"
            f"{product['product_id']}:"
            f"{agreement_role}"
        ),
    )

    agreement_values = (
        calculate_agreement_values(
            product,
            supplier,
            agreement_role,
            config,
            random_generator,
        )
    )

    return {
        "supplier_product_id": str(
            supplier_product_id
        ),
        "supplier_id": supplier[
            "supplier_id"
        ],
        "supplier_code": supplier[
            "supplier_code"
        ],
        "product_id": product[
            "product_id"
        ],
        "product_code": product[
            "product_code"
        ],
        "sku": product["sku"],
        "supplier_product_code": (
            supplier_product_code
        ),
        "agreement_role": agreement_role,
        "is_primary_supplier": boolean_text(
            agreement_role == "PRIMARY"
        ),
        "agreement_status": "ACTIVE",
        **agreement_values,
        "effective_from": commercial_rules[
            "effective_from"
        ],
        "effective_to": (
            commercial_rules["effective_to"]
            or ""
        ),
        "created_at": project_config[
            "generated_timestamp"
        ],
        "updated_at": project_config[
            "generated_timestamp"
        ],
        "version_number": 1,
    }


def generate_agreements(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate primary and secondary supplier agreements."""

    validate_source_counts(
        products,
        suppliers,
        config,
    )
    validate_source_keys(
        products,
        suppliers,
    )

    project_config = config["project"]
    expected_counts = config[
        "expected_counts"
    ]

    random_generator = random.Random(
        int(project_config["master_seed"])
    )

    namespace_uuid = UUID(
        project_config["uuid_namespace"]
    )

    candidate_map = build_candidate_map(
        products,
        suppliers,
        config,
    )

    primary_counts: Counter = Counter()
    total_counts: Counter = Counter()

    primary_supplier_by_product: dict[
        str,
        dict[str, str],
    ] = {}

    agreements: list[dict[str, Any]] = []

    ordered_products = sorted(
        products,
        key=lambda product: (
            product["category_code"],
            product["storage_type"],
            product["product_code"],
        ),
    )

    sequence_number = 1

    for product in ordered_products:
        candidates = candidate_map[
            product["product_id"]
        ]

        selected_supplier = (
            choose_balanced_supplier(
                candidates,
                primary_counts,
                total_counts,
                config,
                random_generator,
                agreement_role="PRIMARY",
            )
        )

        agreement = create_agreement(
            product,
            selected_supplier,
            "PRIMARY",
            sequence_number,
            config,
            namespace_uuid,
            random_generator,
        )

        agreements.append(agreement)

        supplier_id = selected_supplier[
            "supplier_id"
        ]

        primary_counts[supplier_id] += 1
        total_counts[supplier_id] += 1

        primary_supplier_by_product[
            product["product_id"]
        ] = selected_supplier

        sequence_number += 1

    secondary_count = int(
        expected_counts[
            "secondary_agreements"
        ]
    )

    secondary_products = (
        select_secondary_products(
            products,
            secondary_count,
            config,
            random_generator,
        )
    )

    for product in secondary_products:
        primary_supplier = (
            primary_supplier_by_product[
                product["product_id"]
            ]
        )

        selected_supplier = (
            choose_balanced_supplier(
                candidate_map[
                    product["product_id"]
                ],
                primary_counts,
                total_counts,
                config,
                random_generator,
                agreement_role="SECONDARY",
                excluded_supplier_id=(
                    primary_supplier[
                        "supplier_id"
                    ]
                ),
                preferred_different_origin=(
                    primary_supplier[
                        "origin_group"
                    ]
                ),
            )
        )

        agreement = create_agreement(
            product,
            selected_supplier,
            "SECONDARY",
            sequence_number,
            config,
            namespace_uuid,
            random_generator,
        )

        agreements.append(agreement)

        total_counts[
            selected_supplier["supplier_id"]
        ] += 1

        sequence_number += 1

    expected_total = int(
        expected_counts["total_agreements"]
    )

    if len(agreements) != expected_total:
        raise ValueError(
            f"Expected {expected_total} agreements, "
            f"but generated {len(agreements)}."
        )

    return agreements


def write_agreement_csv(
    agreements: list[dict[str, Any]],
) -> None:
    """Write agreements with a stable schema."""

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with AGREEMENT_OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=AGREEMENT_FIELDS,
        )

        writer.writeheader()
        writer.writerows(agreements)


def write_manifest(
    agreements: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    """Write supplier-product output metadata."""

    role_counts = Counter(
        row["agreement_role"]
        for row in agreements
    )

    supplier_counts = Counter(
        row["supplier_code"]
        for row in agreements
    )

    product_ids = {
        row["product_id"]
        for row in agreements
    }

    manifest = {
        "dataset_name": (
            "britmart_supplier_product_agreements"
        ),
        "dataset_version": config[
            "project"
        ]["dataset_version"],
        "schema_version": "1.0.0",
        "generated_at": config[
            "project"
        ]["generated_timestamp"],
        "record_count": len(agreements),
        "product_count": len(product_ids),
        "supplier_count": len(
            supplier_counts
        ),
        "role_counts": dict(
            sorted(role_counts.items())
        ),
        "maximum_agreements_per_supplier": (
            max(supplier_counts.values())
        ),
        "minimum_agreements_per_supplier": (
            min(supplier_counts.values())
        ),
        "output_file": (
            AGREEMENT_OUTPUT_PATH.name
        ),
        "output_sha256": calculate_sha256(
            AGREEMENT_OUTPUT_PATH
        ),
        "source_files": {
            PRODUCT_PATH.name: calculate_sha256(
                PRODUCT_PATH
            ),
            SUPPLIER_PATH.name: calculate_sha256(
                SUPPLIER_PATH
            ),
        },
        "business_key": (
            "supplier_product_code"
        ),
        "technical_key": (
            "supplier_product_id"
        ),
        "incremental_columns": [
            "updated_at",
            "supplier_product_id",
        ],
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
    """Execute supplier-product agreement generation."""

    config = load_json(CONFIG_PATH)
    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)

    agreements = generate_agreements(
        products,
        suppliers,
        config,
    )

    write_agreement_csv(agreements)
    write_manifest(agreements, config)

    primary_count = sum(
        row["agreement_role"] == "PRIMARY"
        for row in agreements
    )
    secondary_count = sum(
        row["agreement_role"] == "SECONDARY"
        for row in agreements
    )

    print(
        "BritMart supplier-product agreements "
        "generated successfully."
    )
    print(
        f"Primary agreements: {primary_count}"
    )
    print(
        f"Secondary agreements: {secondary_count}"
    )
    print(
        f"Total agreements: {len(agreements)}"
    )
    print(
        f"Output directory: {OUTPUT_DIRECTORY}"
    )


if __name__ == "__main__":
    main()