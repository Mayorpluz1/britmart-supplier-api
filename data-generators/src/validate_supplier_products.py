"""Validate BritMart supplier-product agreements."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


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

AGREEMENT_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_products.csv"
)

MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_product_manifest.json"
)

REQUIRED_COLUMNS = {
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
}


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    if not path.exists():
        raise AssertionError(
            f"Required JSON file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def load_csv(
    path: Path,
) -> list[dict[str, str]]:
    """Load a CSV file as dictionaries."""

    if not path.exists():
        raise AssertionError(
            f"Required CSV file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        return list(csv.DictReader(source_file))


def as_boolean(value: Any) -> bool:
    """Convert common Boolean representations."""

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def calculate_sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def validate_required_columns(
    agreements: list[dict[str, str]],
) -> None:
    """Confirm the agreement output schema."""

    if not agreements:
        raise AssertionError(
            "The supplier-product file contains no records."
        )

    actual_columns = set(agreements[0])

    missing_columns = (
        REQUIRED_COLUMNS - actual_columns
    )

    if missing_columns:
        raise AssertionError(
            "Supplier-product output is missing columns: "
            f"{sorted(missing_columns)}"
        )


def validate_record_counts(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    agreements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Confirm expected master and agreement counts."""

    expected = config["expected_counts"]

    if len(products) != int(expected["products"]):
        raise AssertionError(
            "Product source count does not match configuration."
        )

    if len(suppliers) != int(expected["suppliers"]):
        raise AssertionError(
            "Supplier source count does not match configuration."
        )

    if len(agreements) != int(
        expected["total_agreements"]
    ):
        raise AssertionError(
            f"Expected {expected['total_agreements']} "
            f"agreements but found {len(agreements)}."
        )

    role_counts = Counter(
        row["agreement_role"]
        for row in agreements
    )

    if role_counts["PRIMARY"] != int(
        expected["primary_agreements"]
    ):
        raise AssertionError(
            "Primary agreement count is incorrect."
        )

    if role_counts["SECONDARY"] != int(
        expected["secondary_agreements"]
    ):
        raise AssertionError(
            "Secondary agreement count is incorrect."
        )


def validate_unique_identifiers(
    agreements: list[dict[str, str]],
) -> None:
    """Confirm agreement technical and business key uniqueness."""

    agreement_ids = [
        row["supplier_product_id"]
        for row in agreements
    ]

    business_codes = [
        row["supplier_product_code"]
        for row in agreements
    ]

    relationship_keys = [
        (
            row["supplier_id"],
            row["product_id"],
        )
        for row in agreements
    ]

    if len(agreement_ids) != len(
        set(agreement_ids)
    ):
        raise AssertionError(
            "Duplicate supplier_product_id values detected."
        )

    if len(business_codes) != len(
        set(business_codes)
    ):
        raise AssertionError(
            "Duplicate supplier_product_code values detected."
        )

    if len(relationship_keys) != len(
        set(relationship_keys)
    ):
        raise AssertionError(
            "A supplier has duplicate agreements "
            "for the same product."
        )

    for agreement_id in agreement_ids:
        UUID(agreement_id)


def validate_referential_integrity(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    agreements: list[dict[str, str]],
) -> None:
    """Confirm every agreement references valid master data."""

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    for agreement in agreements:
        product_id = agreement["product_id"]
        supplier_id = agreement["supplier_id"]

        if product_id not in products_by_id:
            raise AssertionError(
                f"Unknown product_id in agreement: {product_id}"
            )

        if supplier_id not in suppliers_by_id:
            raise AssertionError(
                f"Unknown supplier_id in agreement: {supplier_id}"
            )

        product = products_by_id[product_id]
        supplier = suppliers_by_id[supplier_id]

        if (
            agreement["product_code"]
            != product["product_code"]
        ):
            raise AssertionError(
                "Agreement product_code does not match "
                f"product_id {product_id}."
            )

        if agreement["sku"] != product["sku"]:
            raise AssertionError(
                f"Agreement SKU mismatch for {product_id}."
            )

        if (
            agreement["supplier_code"]
            != supplier["supplier_code"]
        ):
            raise AssertionError(
                "Agreement supplier_code does not match "
                f"supplier_id {supplier_id}."
            )


def validate_supplier_eligibility(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    agreements: list[dict[str, str]],
) -> None:
    """Validate status, category and storage eligibility."""

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    storage_columns = {
        "AMBIENT": "supports_ambient",
        "CHILLED": "supports_chilled",
        "FROZEN": "supports_frozen",
    }

    for agreement in agreements:
        product = products_by_id[
            agreement["product_id"]
        ]
        supplier = suppliers_by_id[
            agreement["supplier_id"]
        ]

        if supplier["supplier_status"] != "ACTIVE":
            raise AssertionError(
                f"Non-active supplier "
                f"{supplier['supplier_code']} has an "
                "active agreement."
            )

        if not as_boolean(
            supplier["active_flag"]
        ):
            raise AssertionError(
                f"Supplier {supplier['supplier_code']} "
                "has active_flag=false."
            )

        supplier_categories = {
            value.strip()
            for value in supplier[
                "category_codes"
            ].split("|")
            if value.strip()
        }

        if (
            product["category_code"]
            not in supplier_categories
        ):
            raise AssertionError(
                f"Category mismatch between "
                f"{supplier['supplier_code']} and "
                f"{product['product_code']}."
            )

        storage_column = storage_columns.get(
            product["storage_type"]
        )

        if storage_column is None:
            raise AssertionError(
                f"Unknown storage type "
                f"{product['storage_type']}."
            )

        if not as_boolean(
            supplier[storage_column]
        ):
            raise AssertionError(
                f"Storage capability mismatch between "
                f"{supplier['supplier_code']} and "
                f"{product['product_code']}."
            )


def validate_product_coverage(
    products: list[dict[str, str]],
    agreements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Confirm primary and secondary agreement coverage."""

    agreements_by_product: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for agreement in agreements:
        agreements_by_product[
            agreement["product_id"]
        ].append(agreement)

    secondary_product_count = 0

    for product in products:
        product_agreements = (
            agreements_by_product[
                product["product_id"]
            ]
        )

        primary_agreements = [
            row
            for row in product_agreements
            if row["agreement_role"] == "PRIMARY"
        ]

        secondary_agreements = [
            row
            for row in product_agreements
            if row["agreement_role"]
            == "SECONDARY"
        ]

        if len(primary_agreements) != 1:
            raise AssertionError(
                f"{product['product_code']} must have "
                "exactly one primary supplier."
            )

        if len(secondary_agreements) > 1:
            raise AssertionError(
                f"{product['product_code']} has more "
                "than one secondary supplier."
            )

        if secondary_agreements:
            secondary_product_count += 1

            if (
                primary_agreements[0]["supplier_id"]
                == secondary_agreements[0][
                    "supplier_id"
                ]
            ):
                raise AssertionError(
                    f"{product['product_code']} uses "
                    "the same primary and secondary supplier."
                )

    expected_secondary = int(
        config["expected_counts"][
            "secondary_agreements"
        ]
    )

    if secondary_product_count != expected_secondary:
        raise AssertionError(
            f"Expected {expected_secondary} products "
            f"with secondary suppliers, but found "
            f"{secondary_product_count}."
        )


def validate_roles_and_flags(
    agreements: list[dict[str, str]],
) -> None:
    """Confirm agreement roles and primary flags align."""

    for agreement in agreements:
        role = agreement["agreement_role"]

        if role not in {
            "PRIMARY",
            "SECONDARY",
        }:
            raise AssertionError(
                f"Invalid agreement role: {role}"
            )

        expected_primary_flag = (
            role == "PRIMARY"
        )

        if (
            as_boolean(
                agreement["is_primary_supplier"]
            )
            != expected_primary_flag
        ):
            raise AssertionError(
                "Agreement role and primary flag "
                f"do not match for "
                f"{agreement['supplier_product_code']}."
            )

        if (
            agreement["agreement_status"]
            != "ACTIVE"
        ):
            raise AssertionError(
                "Initial supplier-product agreements "
                "must have ACTIVE status."
            )


def demand_tier_name(
    product: dict[str, str],
) -> str:
    """Map product demand tiers to configuration tiers."""

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


def validate_commercial_values(
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    agreements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Validate costs, quantities, currencies and lead times."""

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    commercial_rules = config[
        "commercial_rules"
    ]

    currency_rates = config[
        "currency_conversion"
    ]["rates"]

    for agreement in agreements:
        product = products_by_id[
            agreement["product_id"]
        ]
        supplier = suppliers_by_id[
            agreement["supplier_id"]
        ]

        agreement_code = agreement[
            "supplier_product_code"
        ]

        base_cost = Decimal(
            agreement["base_unit_cost_gbp"]
        )
        product_cost = Decimal(
            product["unit_cost"]
        )

        if base_cost != product_cost.quantize(
            Decimal("0.0001")
        ):
            raise AssertionError(
                f"Base cost mismatch for {agreement_code}."
            )

        currency_code = agreement[
            "agreement_currency_code"
        ]

        if (
            currency_code
            != supplier["default_currency_code"]
        ):
            raise AssertionError(
                f"Currency mismatch for {agreement_code}."
            )

        if currency_code not in currency_rates:
            raise AssertionError(
                f"Unknown currency {currency_code}."
            )

        configured_rate = Decimal(
            str(currency_rates[currency_code])
        )

        agreement_rate = Decimal(
            agreement[
                "gbp_value_per_currency_unit"
            ]
        )

        if agreement_rate != (
            configured_rate.quantize(
                Decimal("0.000001")
            )
        ):
            raise AssertionError(
                f"Currency rate mismatch for {agreement_code}."
            )

        agreed_unit_cost = Decimal(
            agreement["agreed_unit_cost"]
        )

        agreed_cost_gbp = (
            agreed_unit_cost
            * agreement_rate
        )

        multiplier_name = (
            "primary_cost_multiplier"
            if agreement["agreement_role"]
            == "PRIMARY"
            else "secondary_cost_multiplier"
        )

        multiplier_config = commercial_rules[
            multiplier_name
        ]

        minimum_allowed = (
            base_cost
            * Decimal(
                str(
                    multiplier_config[
                        "minimum"
                    ]
                )
            )
        )

        maximum_allowed = (
            base_cost
            * Decimal(
                str(
                    multiplier_config[
                        "maximum"
                    ]
                )
            )
        )

        tolerance = Decimal("0.0002")

        if not (
            minimum_allowed - tolerance
            <= agreed_cost_gbp
            <= maximum_allowed + tolerance
        ):
            raise AssertionError(
                f"Agreed cost outside allowed range "
                f"for {agreement_code}."
            )

        order_multiple = Decimal(
            agreement["order_multiple"]
        )

        case_pack_quantity = Decimal(
            product["case_pack_quantity"]
        ).quantize(
            Decimal("0.001")
        )

        if order_multiple != case_pack_quantity:
            raise AssertionError(
                f"Order multiple mismatch for {agreement_code}."
            )

        minimum_order_quantity = Decimal(
            agreement[
                "minimum_order_quantity"
            ]
        )

        if (
            minimum_order_quantity
            % order_multiple
            != 0
        ):
            raise AssertionError(
                f"Minimum order quantity is not a "
                f"case-pack multiple for {agreement_code}."
            )

        demand_tier = demand_tier_name(
            product
        )

        quantity_rules = commercial_rules[
            "minimum_order_quantity_by_demand_tier"
        ][demand_tier]

        number_of_cases = (
            minimum_order_quantity
            / order_multiple
        )

        if not (
            Decimal(
                quantity_rules["minimum_cases"]
            )
            <= number_of_cases
            <= Decimal(
                quantity_rules["maximum_cases"]
            )
        ):
            raise AssertionError(
                f"Minimum order quantity outside "
                f"the demand-tier range for {agreement_code}."
            )

        supplier_lead_time = int(
            supplier[
                "standard_lead_time_days"
            ]
        )

        agreement_lead_time = int(
            agreement[
                "agreed_lead_time_days"
            ]
        )

        lead_adjustment = commercial_rules[
            "lead_time_adjustment_days"
        ]

        minimum_lead_time = max(
            1,
            supplier_lead_time
            + int(lead_adjustment["minimum"]),
        )

        maximum_lead_time = max(
            1,
            supplier_lead_time
            + int(lead_adjustment["maximum"]),
        )

        if not (
            minimum_lead_time
            <= agreement_lead_time
            <= maximum_lead_time
        ):
            raise AssertionError(
                f"Lead time outside allowed range "
                f"for {agreement_code}."
            )


def validate_shelf_life_rules(
    products: list[dict[str, str]],
    agreements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Validate minimum remaining shelf-life controls."""

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    shelf_life_rates = config[
        "commercial_rules"
    ][
        "minimum_remaining_shelf_life_rate"
    ]

    for agreement in agreements:
        product = products_by_id[
            agreement["product_id"]
        ]

        shelf_life_days = int(
            product["shelf_life_days"]
        )

        actual_value = agreement[
            "minimum_remaining_shelf_life_days"
        ]

        if shelf_life_days <= 0:
            if actual_value:
                raise AssertionError(
                    "Non-shelf-life product has a "
                    "remaining shelf-life requirement."
                )
            continue

        expected_value = math.ceil(
            shelf_life_days
            * float(
                shelf_life_rates[
                    product["storage_type"]
                ]
            )
        )

        if int(actual_value) != expected_value:
            raise AssertionError(
                "Minimum remaining shelf life is incorrect "
                f"for {agreement['supplier_product_code']}."
            )


def validate_supplier_capacity(
    agreements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Confirm supplier agreement allocation caps."""

    primary_counts = Counter(
        row["supplier_id"]
        for row in agreements
        if row["agreement_role"] == "PRIMARY"
    )

    total_counts = Counter(
        row["supplier_id"]
        for row in agreements
    )

    controls = config[
        "allocation_controls"
    ]

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

    if primary_counts and (
        max(primary_counts.values())
        > maximum_primary
    ):
        raise AssertionError(
            "A supplier exceeds the primary-product cap."
        )

    if total_counts and (
        max(total_counts.values())
        > maximum_total
    ):
        raise AssertionError(
            "A supplier exceeds the total-product cap."
        )


def validate_dates_and_audit_fields(
    agreements: list[dict[str, str]],
) -> None:
    """Validate dates, UTC timestamps and version numbers."""

    for agreement in agreements:
        datetime.fromisoformat(
            agreement["effective_from"]
        )

        if agreement["effective_to"]:
            effective_from = datetime.fromisoformat(
                agreement["effective_from"]
            )
            effective_to = datetime.fromisoformat(
                agreement["effective_to"]
            )

            if effective_to < effective_from:
                raise AssertionError(
                    "Agreement effective_to precedes "
                    "effective_from."
                )

        for timestamp_column in [
            "created_at",
            "updated_at",
        ]:
            timestamp = datetime.fromisoformat(
                agreement[
                    timestamp_column
                ].replace(
                    "Z",
                    "+00:00",
                )
            )

            if timestamp.tzinfo is None:
                raise AssertionError(
                    f"{timestamp_column} is not "
                    "timezone-aware."
                )

            if (
                timestamp.utcoffset()
                is None
                or timestamp.utcoffset().total_seconds()
                != 0
            ):
                raise AssertionError(
                    f"{timestamp_column} is not UTC."
                )

        if int(
            agreement["version_number"]
        ) != 1:
            raise AssertionError(
                "Initial agreement version must equal 1."
            )


def validate_manifest(
    agreements: list[dict[str, str]],
) -> None:
    """Validate manifest counts, keys and file integrity."""

    manifest = load_json(MANIFEST_PATH)

    if manifest["record_count"] != len(
        agreements
    ):
        raise AssertionError(
            "Manifest record count does not match output."
        )

    if (
        manifest["output_file"]
        != AGREEMENT_PATH.name
    ):
        raise AssertionError(
            "Manifest output filename is incorrect."
        )

    if (
        manifest["output_sha256"]
        != calculate_sha256(AGREEMENT_PATH)
    ):
        raise AssertionError(
            "Manifest output hash does not match."
        )

    source_files = manifest["source_files"]

    if (
        source_files[PRODUCT_PATH.name]
        != calculate_sha256(PRODUCT_PATH)
    ):
        raise AssertionError(
            "Manifest product source hash is incorrect."
        )

    if (
        source_files[SUPPLIER_PATH.name]
        != calculate_sha256(SUPPLIER_PATH)
    ):
        raise AssertionError(
            "Manifest supplier source hash is incorrect."
        )

    if (
        manifest["business_key"]
        != "supplier_product_code"
    ):
        raise AssertionError(
            "Manifest business key is incorrect."
        )

    if (
        manifest["technical_key"]
        != "supplier_product_id"
    ):
        raise AssertionError(
            "Manifest technical key is incorrect."
        )

    if manifest["incremental_columns"] != [
        "updated_at",
        "supplier_product_id",
    ]:
        raise AssertionError(
            "Manifest incremental ordering is incorrect."
        )


def run_all_validations() -> list[dict[str, str]]:
    """Run the complete agreement validation suite."""

    config = load_json(CONFIG_PATH)
    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    validate_required_columns(agreements)
    validate_record_counts(
        products,
        suppliers,
        agreements,
        config,
    )
    validate_unique_identifiers(agreements)
    validate_referential_integrity(
        products,
        suppliers,
        agreements,
    )
    validate_supplier_eligibility(
        products,
        suppliers,
        agreements,
    )
    validate_product_coverage(
        products,
        agreements,
        config,
    )
    validate_roles_and_flags(agreements)
    validate_commercial_values(
        products,
        suppliers,
        agreements,
        config,
    )
    validate_shelf_life_rules(
        products,
        agreements,
        config,
    )
    validate_supplier_capacity(
        agreements,
        config,
    )
    validate_dates_and_audit_fields(
        agreements
    )
    validate_manifest(agreements)

    return agreements


def main() -> None:
    """Execute validation and print the result."""

    agreements = run_all_validations()

    primary_count = sum(
        row["agreement_role"] == "PRIMARY"
        for row in agreements
    )

    secondary_count = sum(
        row["agreement_role"] == "SECONDARY"
        for row in agreements
    )

    print(
        "BritMart supplier-product validation passed."
    )
    print(
        f"Agreements validated: {len(agreements)}"
    )
    print(
        f"Primary agreements: {primary_count}"
    )
    print(
        f"Secondary agreements: {secondary_count}"
    )


if __name__ == "__main__":
    main()