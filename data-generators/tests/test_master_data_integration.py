"""Integration tests for the BritMart master-data release."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
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

RELEASE_GENERATOR_PATH = (
    SOURCE_DIRECTORY
    / "generate_master_data_release.py"
)

VALIDATOR_PATH = (
    SOURCE_DIRECTORY
    / "validate_master_data.py"
)

RELEASE_MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "master_data_release_manifest.json"
)

VALIDATION_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "master_data_validation_report.json"
)

EXPECTED_DATASET_COUNTS = {
    "regions": 12,
    "distribution_centres": 6,
    "stores": 120,
    "categories": 5,
    "subcategories": 40,
    "products": 2000,
    "suppliers": 50,
    "supplier_products": 2600,
}

EXPECTED_TOTAL_RECORD_COUNT = sum(
    EXPECTED_DATASET_COUNTS.values()
)


def run_python_script(
    script_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Run a Python script with the active interpreter."""

    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


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


def load_csv(
    file_name: str,
) -> list[dict[str, str]]:
    """Load a master-data CSV file."""

    file_path = OUTPUT_DIRECTORY / file_name

    if not file_path.exists():
        raise AssertionError(
            f"Expected CSV file does not exist: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        return list(csv.DictReader(source_file))


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


def ensure_release_exists() -> None:
    """Generate the release manifest when required."""

    if RELEASE_MANIFEST_PATH.exists():
        return

    result = run_python_script(
        RELEASE_GENERATOR_PATH
    )

    assert result.returncode == 0, (
        "Release generation failed.\n"
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )


def ensure_validation_report_exists() -> None:
    """Generate the validation report when required."""

    ensure_release_exists()

    if VALIDATION_REPORT_PATH.exists():
        return

    result = run_python_script(VALIDATOR_PATH)

    assert result.returncode == 0, (
        "Master-data validation failed.\n"
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )


def test_master_data_integration_files_exist() -> None:
    """Confirm integration source files exist."""

    assert RELEASE_GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()


def test_release_generator_runs_successfully() -> None:
    """Confirm release generation succeeds."""

    result = run_python_script(
        RELEASE_GENERATOR_PATH
    )

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "generated successfully"
        in result.stdout.lower()
    )


def test_release_manifest_exists() -> None:
    """Confirm the release manifest exists."""

    ensure_release_exists()

    assert RELEASE_MANIFEST_PATH.exists()


def test_release_identity_is_valid() -> None:
    """Confirm release identity and status."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    assert (
        str(UUID(release["release_id"]))
        == release["release_id"]
    )
    assert (
        release["company_name"]
        == "BritMart"
    )
    assert (
        release["release_version"]
        == "1.0.0"
    )
    assert (
        release["release_status"]
        == "READY_FOR_VALIDATION"
    )
    assert release["master_seed"] == 20260816


def test_release_contains_all_expected_datasets() -> None:
    """Confirm all required datasets are registered."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    assert set(
        release["datasets"]
    ) == set(
        EXPECTED_DATASET_COUNTS
    )

    assert (
        release["total_dataset_count"]
        == len(EXPECTED_DATASET_COUNTS)
    )


def test_release_dataset_counts_are_correct() -> None:
    """Confirm every dataset count."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    for dataset_name, expected_count in (
        EXPECTED_DATASET_COUNTS.items()
    ):
        assert (
            release["datasets"][
                dataset_name
            ]["record_count"]
            == expected_count
        )

    assert (
        release["total_record_count"]
        == EXPECTED_TOTAL_RECORD_COUNT
    )


def test_release_dataset_hashes_are_correct() -> None:
    """Confirm release hashes match all CSV files."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    for metadata in (
        release["datasets"].values()
    ):
        file_path = (
            OUTPUT_DIRECTORY
            / metadata["file_name"]
        )

        assert file_path.exists()

        assert (
            metadata["sha256"]
            == calculate_sha256(file_path)
        )


def test_release_dataset_keys_are_unique() -> None:
    """Confirm every declared key is complete and unique."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    for metadata in (
        release["datasets"].values()
    ):
        rows = load_csv(
            metadata["file_name"]
        )

        business_values = [
            row[metadata["business_key"]]
            for row in rows
        ]

        technical_values = [
            row[metadata["technical_key"]]
            for row in rows
        ]

        assert all(business_values)
        assert all(technical_values)

        assert len(
            business_values
        ) == len(
            set(business_values)
        )

        assert len(
            technical_values
        ) == len(
            set(technical_values)
        )

        for technical_value in (
            technical_values
        ):
            assert (
                str(UUID(technical_value))
                == technical_value
            )


def test_all_declared_relationships_have_no_orphans() -> None:
    """Confirm registered relationships have no orphans."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    datasets = {
        dataset_name: load_csv(
            metadata["file_name"]
        )
        for dataset_name, metadata
        in release["datasets"].items()
    }

    for relationship in release[
        "relationships"
    ]:
        parent_values = {
            row[
                relationship["parent_key"]
            ]
            for row in datasets[
                relationship["parent_dataset"]
            ]
        }

        orphan_values = [
            row[
                relationship["child_key"]
            ]
            for row in datasets[
                relationship["child_dataset"]
            ]
            if row[
                relationship["child_key"]
            ]
            not in parent_values
        ]

        assert orphan_values == []


def test_every_category_has_eight_subcategories() -> None:
    """Confirm the retail category hierarchy."""

    categories = load_csv(
        "categories.csv"
    )

    subcategories = load_csv(
        "subcategories.csv"
    )

    subcategory_counts = Counter(
        row["category_id"]
        for row in subcategories
    )

    assert len(
        subcategory_counts
    ) == len(categories)

    assert all(
        count == 8
        for count in subcategory_counts.values()
    )


def test_every_product_has_valid_category_and_subcategory() -> None:
    """Confirm product hierarchy references."""

    categories = load_csv(
        "categories.csv"
    )

    subcategories = load_csv(
        "subcategories.csv"
    )

    products = load_csv(
        "products.csv"
    )

    category_ids = {
        row["category_id"]
        for row in categories
    }

    subcategories_by_id = {
        row["subcategory_id"]: row
        for row in subcategories
    }

    for product in products:
        assert (
            product["category_id"]
            in category_ids
        )

        assert (
            product["subcategory_id"]
            in subcategories_by_id
        )

        subcategory = subcategories_by_id[
            product["subcategory_id"]
        ]

        assert (
            subcategory["category_id"]
            == product["category_id"]
        )


def test_every_distribution_centre_has_valid_region() -> None:
    """Confirm distribution-centre region references."""

    regions = load_csv(
        "regions.csv"
    )

    distribution_centres = load_csv(
        "distribution_centres.csv"
    )

    region_ids = {
        row["region_id"]
        for row in regions
    }

    for distribution_centre in (
        distribution_centres
    ):
        assert (
            distribution_centre["region_id"]
            in region_ids
        )


def test_every_store_has_valid_location_references() -> None:
    """Confirm store location references."""

    regions = load_csv(
        "regions.csv"
    )

    distribution_centres = load_csv(
        "distribution_centres.csv"
    )

    stores = load_csv(
        "stores.csv"
    )

    region_ids = {
        row["region_id"]
        for row in regions
    }

    distribution_centres_by_id = {
        row["distribution_centre_id"]: row
        for row in distribution_centres
    }

    for store in stores:
        assert (
            store["region_id"]
            in region_ids
        )

        distribution_centre_id = store[
            "primary_distribution_centre_id"
        ]

        assert (
            distribution_centre_id
            in distribution_centres_by_id
        )

        distribution_centre = (
            distribution_centres_by_id[
                distribution_centre_id
            ]
        )

        assert (
            store[
                "primary_distribution_centre_code"
            ]
            == distribution_centre[
                "distribution_centre_code"
            ]
        )


def test_every_distribution_centre_serves_stores() -> None:
    """Confirm every distribution centre serves stores."""

    distribution_centres = load_csv(
        "distribution_centres.csv"
    )

    stores = load_csv(
        "stores.csv"
    )

    assigned_distribution_centre_ids = {
        row["primary_distribution_centre_id"]
        for row in stores
    }

    expected_distribution_centre_ids = {
        row["distribution_centre_id"]
        for row in distribution_centres
    }

    assert (
        assigned_distribution_centre_ids
        == expected_distribution_centre_ids
    )


def test_supplier_status_and_risk_distributions_are_correct() -> None:
    """Confirm supplier scenario distributions."""

    suppliers = load_csv(
        "suppliers.csv"
    )

    status_counts = Counter(
        row["supplier_status"]
        for row in suppliers
    )

    risk_counts = Counter(
        row["risk_rating"]
        for row in suppliers
    )

    assert status_counts == Counter(
        {
            "ACTIVE": 46,
            "SUSPENDED": 2,
            "PENDING": 1,
            "INACTIVE": 1,
        }
    )

    assert risk_counts == Counter(
        {
            "LOW": 20,
            "MEDIUM": 22,
            "HIGH": 7,
            "CRITICAL": 1,
        }
    )


def test_only_active_suppliers_have_product_agreements() -> None:
    """Confirm agreement supplier eligibility."""

    suppliers = load_csv(
        "suppliers.csv"
    )

    agreements = load_csv(
        "supplier_products.csv"
    )

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


def test_supplier_product_categories_match() -> None:
    """Confirm supplier and product categories align."""

    products = load_csv(
        "products.csv"
    )

    suppliers = load_csv(
        "suppliers.csv"
    )

    agreements = load_csv(
        "supplier_products.csv"
    )

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


def test_supplier_product_storage_capabilities_match() -> None:
    """Confirm supplier storage capabilities align."""

    products = load_csv(
        "products.csv"
    )

    suppliers = load_csv(
        "suppliers.csv"
    )

    agreements = load_csv(
        "supplier_products.csv"
    )

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

        assert (
            supplier[storage_column]
            == "true"
        )


def test_every_product_has_exactly_one_primary_supplier() -> None:
    """Confirm complete primary supplier coverage."""

    products = load_csv(
        "products.csv"
    )

    agreements = load_csv(
        "supplier_products.csv"
    )

    primary_counts = Counter(
        row["product_id"]
        for row in agreements
        if row["agreement_role"]
        == "PRIMARY"
    )

    assert len(primary_counts) == len(products)

    assert all(
        count == 1
        for count in primary_counts.values()
    )


def test_secondary_supplier_resilience_is_correct() -> None:
    """Confirm 600 products have distinct secondary suppliers."""

    agreements = load_csv(
        "supplier_products.csv"
    )

    agreements_by_product: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for agreement in agreements:
        agreements_by_product[
            agreement["product_id"]
        ].append(agreement)

    products_with_secondary = 0

    for product_agreements in (
        agreements_by_product.values()
    ):
        primary_ids = {
            row["supplier_id"]
            for row in product_agreements
            if row["agreement_role"]
            == "PRIMARY"
        }

        secondary_ids = {
            row["supplier_id"]
            for row in product_agreements
            if row["agreement_role"]
            == "SECONDARY"
        }

        if secondary_ids:
            products_with_secondary += 1

            assert primary_ids.isdisjoint(
                secondary_ids
            )

    assert products_with_secondary == 600


def test_source_manifest_hashes_are_correct() -> None:
    """Confirm source-manifest integrity."""

    ensure_release_exists()

    release = load_json(
        RELEASE_MANIFEST_PATH
    )

    for metadata in (
        release["source_manifests"].values()
    ):
        manifest_path = (
            OUTPUT_DIRECTORY
            / metadata["file_name"]
        )

        assert manifest_path.exists()

        assert (
            metadata["sha256"]
            == calculate_sha256(manifest_path)
        )


def test_master_data_validator_runs_successfully() -> None:
    """Confirm the cross-domain validator succeeds."""

    ensure_release_exists()

    result = run_python_script(
        VALIDATOR_PATH
    )

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "validation passed"
        in result.stdout.lower()
    )


def test_validation_report_is_approved() -> None:
    """Confirm the release is approved downstream."""

    ensure_validation_report_exists()

    report = load_json(
        VALIDATION_REPORT_PATH
    )

    assert (
        report["validation_status"]
        == "PASSED"
    )

    assert (
        report[
            "approved_for_downstream_generation"
        ]
        is True
    )

    assert report["dataset_count"] == 8

    assert (
        report["total_record_count"]
        == EXPECTED_TOTAL_RECORD_COUNT
    )

    assert (
        report["relationship_check_count"]
        == 8
    )


def test_all_validation_domains_passed() -> None:
    """Confirm every validation domain passed."""

    ensure_validation_report_exists()

    report = load_json(
        VALIDATION_REPORT_PATH
    )

    expected_domains = {
        "location",
        "product",
        "supplier",
        "supplier_product",
    }

    assert set(
        report["domain_results"]
    ) == expected_domains

    for result in (
        report["domain_results"].values()
    ):
        assert result["status"] == "PASSED"


def test_release_generation_is_reproducible() -> None:
    """Confirm release generation is deterministic."""

    first_result = run_python_script(
        RELEASE_GENERATOR_PATH
    )

    assert first_result.returncode == 0, (
        first_result.stderr
    )

    first_bytes = (
        RELEASE_MANIFEST_PATH.read_bytes()
    )

    second_result = run_python_script(
        RELEASE_GENERATOR_PATH
    )

    assert second_result.returncode == 0, (
        second_result.stderr
    )

    second_bytes = (
        RELEASE_MANIFEST_PATH.read_bytes()
    )

    assert first_bytes == second_bytes


def test_validation_report_is_reproducible() -> None:
    """Confirm validation report generation is deterministic."""

    first_result = run_python_script(
        VALIDATOR_PATH
    )

    assert first_result.returncode == 0, (
        first_result.stderr
    )

    first_bytes = (
        VALIDATION_REPORT_PATH.read_bytes()
    )

    second_result = run_python_script(
        VALIDATOR_PATH
    )

    assert second_result.returncode == 0, (
        second_result.stderr
    )

    second_bytes = (
        VALIDATION_REPORT_PATH.read_bytes()
    )

    assert first_bytes == second_bytes