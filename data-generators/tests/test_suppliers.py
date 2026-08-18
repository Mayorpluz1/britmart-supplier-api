"""Automated tests for BritMart supplier master data."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
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

GENERATOR_PATH = SOURCE_DIRECTORY / "generate_suppliers.py"
VALIDATOR_PATH = SOURCE_DIRECTORY / "validate_suppliers.py"

SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_manifest.json"
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "data-generators"
    / "config"
    / "supplier_config.json"
)

EXPECTED_SUPPLIER_COUNT = 50

EXPECTED_ORIGIN_COUNTS = {
    "GB": 34,
    "EU": 10,
    "OTHER": 6,
}

EXPECTED_STATUS_COUNTS = {
    "ACTIVE": 46,
    "SUSPENDED": 2,
    "PENDING": 1,
    "INACTIVE": 1,
}

EXPECTED_RISK_COUNTS = {
    "LOW": 20,
    "MEDIUM": 22,
    "HIGH": 7,
    "CRITICAL": 1,
}

EXPECTED_TYPE_COUNTS = {
    "FRESH_PRODUCE_SUPPLIER": 6,
    "MEAT_AND_POULTRY_SUPPLIER": 5,
    "DAIRY_SUPPLIER": 4,
    "BAKERY_SUPPLIER": 4,
    "GROCERY_MANUFACTURER": 7,
    "BEVERAGE_MANUFACTURER": 5,
    "FROZEN_FOOD_SUPPLIER": 4,
    "HOUSEHOLD_GOODS_MANUFACTURER": 4,
    "PERSONAL_CARE_SUPPLIER": 3,
    "IMPORTER_AND_DISTRIBUTOR": 5,
    "REGIONAL_SPECIALIST_SUPPLIER": 3,
}


def run_python_script(
    script_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Run a Python script using the active virtual environment."""

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
    """Load a CSV file as a list of dictionaries."""

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
    """Calculate a SHA-256 digest for a file."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def ensure_supplier_outputs_exist() -> None:
    """Generate supplier outputs if they do not already exist."""

    if (
        SUPPLIER_PATH.exists()
        and MANIFEST_PATH.exists()
    ):
        return

    result = run_python_script(GENERATOR_PATH)

    assert result.returncode == 0, (
        "Supplier generation failed.\n"
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )


def test_supplier_project_files_exist() -> None:
    """Confirm supplier source and configuration files exist."""

    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()


def test_supplier_generator_runs_successfully() -> None:
    """Confirm the supplier generator completes successfully."""

    result = run_python_script(GENERATOR_PATH)

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "generated successfully"
        in result.stdout.lower()
    )


def test_expected_supplier_output_files_exist() -> None:
    """Confirm expected supplier output files exist."""

    ensure_supplier_outputs_exist()

    assert SUPPLIER_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_expected_supplier_record_count() -> None:
    """Confirm the expected supplier portfolio size."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    assert len(supplier_rows) == EXPECTED_SUPPLIER_COUNT


def test_supplier_business_keys_are_unique_and_sequential() -> None:
    """Confirm supplier business keys are unique and sequential."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    supplier_codes = [
        row["supplier_code"]
        for row in supplier_rows
    ]

    assert len(supplier_codes) == len(
        set(supplier_codes)
    )

    assert set(supplier_codes) == {
        f"SUP-{number:04d}"
        for number in range(
            1,
            EXPECTED_SUPPLIER_COUNT + 1,
        )
    }


def test_supplier_technical_identifiers_are_valid_and_unique() -> None:
    """Confirm supplier technical identifiers are valid UUIDs."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    supplier_ids = [
        row["supplier_id"]
        for row in supplier_rows
    ]

    assert len(supplier_ids) == len(
        set(supplier_ids)
    )

    for supplier_id in supplier_ids:
        assert str(UUID(supplier_id)) == supplier_id


def test_supplier_names_and_emails_are_unique() -> None:
    """Confirm supplier names and synthetic emails are unique."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    supplier_names = [
        row["supplier_name"]
        for row in supplier_rows
    ]
    contact_emails = [
        row["contact_email"]
        for row in supplier_rows
    ]

    assert len(supplier_names) == len(
        set(supplier_names)
    )
    assert len(contact_emails) == len(
        set(contact_emails)
    )

    for email in contact_emails:
        assert email.endswith(
            "@supplier.britmart.example"
        )


def test_supplier_type_counts_match_configuration() -> None:
    """Confirm supplier type counts match the business model."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    actual_counts = Counter(
        row["supplier_type"]
        for row in supplier_rows
    )

    assert actual_counts == Counter(
        EXPECTED_TYPE_COUNTS
    )


def test_supplier_origin_distribution_is_exact() -> None:
    """Confirm the configured supplier origin distribution."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    actual_counts = Counter(
        row["origin_group"]
        for row in supplier_rows
    )

    assert actual_counts == Counter(
        EXPECTED_ORIGIN_COUNTS
    )


def test_supplier_status_distribution_is_exact() -> None:
    """Confirm the configured supplier status distribution."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    actual_counts = Counter(
        row["supplier_status"]
        for row in supplier_rows
    )

    assert actual_counts == Counter(
        EXPECTED_STATUS_COUNTS
    )


def test_supplier_risk_distribution_is_exact() -> None:
    """Confirm the configured supplier risk distribution."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    actual_counts = Counter(
        row["risk_rating"]
        for row in supplier_rows
    )

    assert actual_counts == Counter(
        EXPECTED_RISK_COUNTS
    )


def test_supplier_operational_values_are_valid() -> None:
    """Validate commercial and operational supplier values."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    for row in supplier_rows:
        minimum_order_value = Decimal(
            row["minimum_order_value"]
        )
        target_otif_rate = Decimal(
            row["target_otif_rate"]
        )
        target_quality_rate = Decimal(
            row[
                "target_quality_acceptance_rate"
            ]
        )

        assert minimum_order_value > 0

        assert (
            0
            < int(
                row["standard_lead_time_days"]
            )
            <= 90
        )

        assert int(
            row["payment_terms_days"]
        ) in {
            14,
            30,
            45,
            60,
        }

        assert (
            Decimal("0.88")
            <= target_otif_rate
            <= Decimal("0.98")
        )

        assert (
            Decimal("0.97")
            <= target_quality_rate
            <= Decimal("0.999")
        )

        storage_values = [
            row["supports_ambient"],
            row["supports_chilled"],
            row["supports_frozen"],
        ]

        assert any(
            value == "true"
            for value in storage_values
        )

        if row["supplier_status"] == "INACTIVE":
            assert row["active_flag"] == "false"
        else:
            assert row["active_flag"] == "true"

        if row["origin_group"] == "GB":
            assert (
                row["default_currency_code"]
                == "GBP"
            )
            assert row["incoterm"] in {
                "DAP",
                "DDP",
            }


def test_supplier_category_capabilities_are_populated() -> None:
    """Confirm every supplier has category capabilities."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    for row in supplier_rows:
        category_codes = [
            category_code.strip()
            for category_code
            in row["category_codes"].split("|")
            if category_code.strip()
        ]

        assert category_codes


def test_supplier_category_references_are_valid() -> None:
    """Confirm supplier categories belong to BritMart categories."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    valid_category_codes = {
        "CAT-01",
        "CAT-02",
        "CAT-03",
        "CAT-04",
        "CAT-05",
    }

    for row in supplier_rows:
        category_codes = {
            category_code.strip()
            for category_code
            in row["category_codes"].split("|")
            if category_code.strip()
        }

        assert category_codes.issubset(
            valid_category_codes
        )


def test_supplier_risk_and_status_are_logically_related() -> None:
    """Confirm non-active statuses affect riskier suppliers."""

    ensure_supplier_outputs_exist()
    supplier_rows = load_csv(SUPPLIER_PATH)

    inactive_suppliers = [
        row
        for row in supplier_rows
        if row["supplier_status"] == "INACTIVE"
    ]

    suspended_suppliers = [
        row
        for row in supplier_rows
        if row["supplier_status"] == "SUSPENDED"
    ]

    assert len(inactive_suppliers) == 1
    assert (
        inactive_suppliers[0]["risk_rating"]
        == "CRITICAL"
    )

    assert len(suspended_suppliers) == 2

    assert all(
        row["risk_rating"] in {
            "HIGH",
            "CRITICAL",
        }
        for row in suspended_suppliers
    )


def test_supplier_manifest_matches_output() -> None:
    """Confirm manifest metadata matches suppliers.csv."""

    ensure_supplier_outputs_exist()

    supplier_rows = load_csv(SUPPLIER_PATH)
    manifest = load_json(MANIFEST_PATH)

    assert (
        manifest["record_count"]
        == len(supplier_rows)
    )
    assert (
        manifest["output_file"]
        == "suppliers.csv"
    )
    assert (
        manifest["output_sha256"]
        == calculate_sha256(SUPPLIER_PATH)
    )
    assert (
        manifest["business_key"]
        == "supplier_code"
    )
    assert (
        manifest["technical_key"]
        == "supplier_id"
    )
    assert manifest["incremental_columns"] == [
        "updated_at",
        "supplier_id",
    ]


def test_full_supplier_validation_suite_passes() -> None:
    """Confirm the independent validator succeeds."""

    ensure_supplier_outputs_exist()
    result = run_python_script(VALIDATOR_PATH)

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "validation passed"
        in result.stdout.lower()
    )


def test_supplier_generation_is_reproducible() -> None:
    """Confirm repeated generation produces identical files."""

    first_result = run_python_script(
        GENERATOR_PATH
    )

    assert first_result.returncode == 0, (
        first_result.stderr
    )

    first_supplier_hash = calculate_sha256(
        SUPPLIER_PATH
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

    second_supplier_hash = calculate_sha256(
        SUPPLIER_PATH
    )
    second_manifest_bytes = (
        MANIFEST_PATH.read_bytes()
    )

    assert (
        first_supplier_hash
        == second_supplier_hash
    )
    assert (
        first_manifest_bytes
        == second_manifest_bytes
    )