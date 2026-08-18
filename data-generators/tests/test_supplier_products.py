"""Tests for BritMart supplier-product agreements."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "src"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "output"
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "data-generators"
    / "config"
    / "supplier_product_config.json"
)

GENERATOR_PATH = (
    SOURCE_DIRECTORY
    / "generate_supplier_products.py"
)

VALIDATOR_PATH = (
    SOURCE_DIRECTORY
    / "validate_supplier_products.py"
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

EXPECTED_TOTAL_AGREEMENTS = 2600
EXPECTED_PRIMARY_AGREEMENTS = 2000
EXPECTED_SECONDARY_AGREEMENTS = 600


def run_python_script(
    script_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Run a Python script using the active interpreter."""

    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def load_csv(
    path: Path,
) -> list[dict[str, str]]:
    """Load a CSV file into dictionaries."""

    if not path.exists():
        raise AssertionError(
            f"Expected CSV file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        return list(csv.DictReader(source_file))


def load_json(path: Path) -> dict:
    """Load a JSON file."""

    if not path.exists():
        raise AssertionError(
            f"Expected JSON file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def calculate_sha256(path: Path) -> str:
    """Calculate a SHA-256 digest."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def ensure_outputs_exist() -> None:
    """Generate agreement outputs when required."""

    if (
        AGREEMENT_PATH.exists()
        and MANIFEST_PATH.exists()
    ):
        return

    result = run_python_script(GENERATOR_PATH)

    assert result.returncode == 0, (
        "Supplier-product generation failed.\n"
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )


def test_supplier_product_project_files_exist() -> None:
    """Confirm all supplier-product project files exist."""

    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()
    assert PRODUCT_PATH.exists()
    assert SUPPLIER_PATH.exists()


def test_supplier_product_generator_runs_successfully() -> None:
    """Confirm agreement generation succeeds."""

    result = run_python_script(GENERATOR_PATH)

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "generated successfully"
        in result.stdout.lower()
    )


def test_expected_agreement_output_files_exist() -> None:
    """Confirm agreement and manifest files exist."""

    ensure_outputs_exist()

    assert AGREEMENT_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_expected_agreement_record_counts() -> None:
    """Confirm total, primary and secondary counts."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    role_counts = Counter(
        row["agreement_role"]
        for row in agreements
    )

    assert (
        len(agreements)
        == EXPECTED_TOTAL_AGREEMENTS
    )
    assert (
        role_counts["PRIMARY"]
        == EXPECTED_PRIMARY_AGREEMENTS
    )
    assert (
        role_counts["SECONDARY"]
        == EXPECTED_SECONDARY_AGREEMENTS
    )


def test_agreement_technical_keys_are_valid_and_unique() -> None:
    """Confirm agreement UUIDs are valid and unique."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    agreement_ids = [
        row["supplier_product_id"]
        for row in agreements
    ]

    assert len(agreement_ids) == len(
        set(agreement_ids)
    )

    for agreement_id in agreement_ids:
        assert str(UUID(agreement_id)) == agreement_id


def test_agreement_business_keys_are_unique() -> None:
    """Confirm supplier-product business keys are unique."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    business_keys = [
        row["supplier_product_code"]
        for row in agreements
    ]

    assert len(business_keys) == len(
        set(business_keys)
    )


def test_supplier_product_relationships_are_unique() -> None:
    """Confirm a supplier cannot duplicate a product relationship."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    relationship_keys = [
        (
            row["supplier_id"],
            row["product_id"],
        )
        for row in agreements
    ]

    assert len(relationship_keys) == len(
        set(relationship_keys)
    )


def test_all_agreements_reference_valid_products() -> None:
    """Confirm agreement product references exist."""

    ensure_outputs_exist()

    products = load_csv(PRODUCT_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    for agreement in agreements:
        assert (
            agreement["product_id"]
            in products_by_id
        )

        product = products_by_id[
            agreement["product_id"]
        ]

        assert (
            agreement["product_code"]
            == product["product_code"]
        )
        assert agreement["sku"] == product["sku"]


def test_all_agreements_reference_valid_suppliers() -> None:
    """Confirm agreement supplier references exist."""

    ensure_outputs_exist()

    suppliers = load_csv(SUPPLIER_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    for agreement in agreements:
        assert (
            agreement["supplier_id"]
            in suppliers_by_id
        )

        supplier = suppliers_by_id[
            agreement["supplier_id"]
        ]

        assert (
            agreement["supplier_code"]
            == supplier["supplier_code"]
        )


def test_only_active_suppliers_have_agreements() -> None:
    """Confirm only active suppliers receive agreements."""

    ensure_outputs_exist()

    suppliers = load_csv(SUPPLIER_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    for agreement in agreements:
        supplier = suppliers_by_id[
            agreement["supplier_id"]
        ]

        assert (
            supplier["supplier_status"]
            == "ACTIVE"
        )
        assert (
            supplier["active_flag"]
            == "true"
        )


def test_supplier_categories_match_products() -> None:
    """Confirm every supplier supports its product category."""

    ensure_outputs_exist()

    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    for agreement in agreements:
        product = products_by_id[
            agreement["product_id"]
        ]
        supplier = suppliers_by_id[
            agreement["supplier_id"]
        ]

        supplier_categories = {
            value.strip()
            for value in supplier[
                "category_codes"
            ].split("|")
            if value.strip()
        }

        assert (
            product["category_code"]
            in supplier_categories
        )


def test_supplier_storage_capabilities_match_products() -> None:
    """Confirm every supplier supports product storage needs."""

    ensure_outputs_exist()

    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)
    agreements = load_csv(AGREEMENT_PATH)

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

        storage_column = storage_columns[
            product["storage_type"]
        ]

        assert supplier[storage_column] == "true"


def test_every_product_has_exactly_one_primary_supplier() -> None:
    """Confirm complete primary supplier coverage."""

    ensure_outputs_exist()

    products = load_csv(PRODUCT_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    primary_counts = Counter(
        row["product_id"]
        for row in agreements
        if row["agreement_role"] == "PRIMARY"
    )

    assert len(primary_counts) == len(products)

    for product in products:
        assert (
            primary_counts[product["product_id"]]
            == 1
        )


def test_secondary_supplier_coverage_is_correct() -> None:
    """Confirm exactly 600 products have secondary suppliers."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    secondary_counts = Counter(
        row["product_id"]
        for row in agreements
        if row["agreement_role"]
        == "SECONDARY"
    )

    assert (
        len(secondary_counts)
        == EXPECTED_SECONDARY_AGREEMENTS
    )

    assert all(
        count == 1
        for count in secondary_counts.values()
    )


def test_primary_and_secondary_suppliers_are_different() -> None:
    """Confirm resilient products use distinct suppliers."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    agreements_by_product: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for agreement in agreements:
        agreements_by_product[
            agreement["product_id"]
        ].append(agreement)

    for product_agreements in (
        agreements_by_product.values()
    ):
        primary_suppliers = {
            row["supplier_id"]
            for row in product_agreements
            if row["agreement_role"] == "PRIMARY"
        }

        secondary_suppliers = {
            row["supplier_id"]
            for row in product_agreements
            if row["agreement_role"]
            == "SECONDARY"
        }

        assert primary_suppliers.isdisjoint(
            secondary_suppliers
        )


def test_agreement_roles_match_primary_flags() -> None:
    """Confirm role and Boolean primary flag consistency."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    for agreement in agreements:
        if agreement["agreement_role"] == "PRIMARY":
            assert (
                agreement[
                    "is_primary_supplier"
                ]
                == "true"
            )
        else:
            assert (
                agreement[
                    "is_primary_supplier"
                ]
                == "false"
            )

        assert (
            agreement["agreement_status"]
            == "ACTIVE"
        )


def test_agreement_currency_matches_supplier_currency() -> None:
    """Confirm agreement and supplier currencies align."""

    ensure_outputs_exist()

    suppliers = load_csv(SUPPLIER_PATH)
    agreements = load_csv(AGREEMENT_PATH)

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    for agreement in agreements:
        supplier = suppliers_by_id[
            agreement["supplier_id"]
        ]

        assert (
            agreement[
                "agreement_currency_code"
            ]
            == supplier[
                "default_currency_code"
            ]
        )


def test_agreement_quantities_are_case_pack_multiples() -> None:
    """Confirm minimum quantities respect case packs."""

    ensure_outputs_exist()
    agreements = load_csv(AGREEMENT_PATH)

    for agreement in agreements:
        minimum_quantity = Decimal(
            agreement[
                "minimum_order_quantity"
            ]
        )
        order_multiple = Decimal(
            agreement["order_multiple"]
        )

        assert minimum_quantity > 0
        assert order_multiple > 0
        assert (
            minimum_quantity
            % order_multiple
            == 0
        )


def test_supplier_capacity_limits_are_respected() -> None:
    """Confirm supplier allocation caps are respected."""

    ensure_outputs_exist()

    config = load_json(CONFIG_PATH)
    agreements = load_csv(AGREEMENT_PATH)

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

    assert max(
        primary_counts.values()
    ) <= int(
        controls[
            "maximum_primary_products_per_supplier"
        ]
    )

    assert max(
        total_counts.values()
    ) <= int(
        controls[
            "maximum_total_products_per_supplier"
        ]
    )


def test_manifest_matches_agreement_output() -> None:
    """Confirm manifest counts and hashes are correct."""

    ensure_outputs_exist()

    agreements = load_csv(AGREEMENT_PATH)
    manifest = load_json(MANIFEST_PATH)

    assert (
        manifest["record_count"]
        == len(agreements)
    )
    assert (
        manifest["output_file"]
        == "supplier_products.csv"
    )
    assert (
        manifest["output_sha256"]
        == calculate_sha256(AGREEMENT_PATH)
    )
    assert (
        manifest["business_key"]
        == "supplier_product_code"
    )
    assert (
        manifest["technical_key"]
        == "supplier_product_id"
    )
    assert manifest["incremental_columns"] == [
        "updated_at",
        "supplier_product_id",
    ]


def test_full_supplier_product_validation_passes() -> None:
    """Confirm the independent validation suite succeeds."""

    ensure_outputs_exist()

    result = run_python_script(VALIDATOR_PATH)

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "validation passed"
        in result.stdout.lower()
    )


def test_supplier_product_generation_is_reproducible() -> None:
    """Confirm repeated generation produces identical files."""

    first_result = run_python_script(
        GENERATOR_PATH
    )

    assert first_result.returncode == 0, (
        first_result.stderr
    )

    first_output_hash = calculate_sha256(
        AGREEMENT_PATH
    )
    first_manifest_bytes = (
        MANIFEST_PATH.read_bytes()
    )

    second_result = run_python_script(
        GENERATOR_PATH
    )

    assert second_result.returncode == 0, (
        second_result.stderr
    )

    second_output_hash = calculate_sha256(
        AGREEMENT_PATH
    )
    second_manifest_bytes = (
        MANIFEST_PATH.read_bytes()
    )

    assert (
        first_output_hash
        == second_output_hash
    )
    assert (
        first_manifest_bytes
        == second_manifest_bytes
    )