"""Tests for the BritMart integrated operational-data release."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_GENERATORS_DIRECTORY = PROJECT_ROOT / "data-generators"
CONFIG_DIRECTORY = DATA_GENERATORS_DIRECTORY / "config"
SOURCE_DIRECTORY = DATA_GENERATORS_DIRECTORY / "src"
OUTPUT_DIRECTORY = DATA_GENERATORS_DIRECTORY / "output"

CONFIG_PATH = (
    CONFIG_DIRECTORY / "operational_release_config.json"
)
GENERATOR_PATH = (
    SOURCE_DIRECTORY
    / "generate_operational_data_release.py"
)
VALIDATOR_PATH = (
    SOURCE_DIRECTORY
    / "validate_operational_data_release.py"
)
MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "operational_data_release_manifest.json"
)
VALIDATION_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "operational_data_validation_report.json"
)

EXPECTED_DATASET_COUNT = 18
EXPECTED_RECORD_COUNT = 278424
EXPECTED_COMPONENT_VALIDATION_COUNT = 5
EXPECTED_RECONCILIATION_CONTROL_COUNT = 11

EXPECTED_DATASET_NAMES = {
    "regions",
    "distribution_centres",
    "stores",
    "categories",
    "subcategories",
    "products",
    "suppliers",
    "supplier_products",
    "purchase_orders",
    "purchase_order_lines",
    "shipments",
    "shipment_lines",
    "shipment_status_history",
    "goods_receipts",
    "goods_receipt_lines",
    "inventory_movements",
    "supplier_performance_events",
    "supplier_monthly_scorecards",
}


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object."""

    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)

    assert isinstance(value, dict)
    return value


def run_python_script(path: Path) -> subprocess.CompletedProcess[str]:
    """Run a project Python script."""

    return subprocess.run(
        [sys.executable, str(path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def calculate_sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def count_csv_records(path: Path) -> int:
    """Count CSV data records, excluding the header."""

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader, None)

        assert header is not None
        return sum(1 for _ in reader)


def read_primary_keys(
    path: Path,
    primary_key_columns: list[str],
) -> list[tuple[str, ...]]:
    """Read composite primary-key values from a CSV file."""

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        assert reader.fieldnames is not None

        for column in primary_key_columns:
            assert column in reader.fieldnames

        return [
            tuple(
                (row.get(column) or "").strip()
                for column in primary_key_columns
            )
            for row in reader
        ]


def test_operational_release_project_files_exist() -> None:
    """Confirm all operational release project files exist."""

    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()
    assert Path(__file__).exists()


def test_operational_release_generator_runs_successfully() -> None:
    """Confirm the release generator completes successfully."""

    result = run_python_script(GENERATOR_PATH)

    assert result.returncode == 0, result.stderr
    assert (
        "operational-data release manifest generated successfully"
        in result.stdout
    )
    assert "Datasets: 18" in result.stdout
    assert "Total records: 278424" in result.stdout


def test_operational_release_validator_runs_successfully() -> None:
    """Confirm the release validator completes successfully."""

    result = run_python_script(VALIDATOR_PATH)

    assert result.returncode == 0, result.stderr
    assert (
        "integrated operational-data validation passed"
        in result.stdout
    )
    assert "Overall status: PASSED" in result.stdout


def test_operational_release_outputs_exist() -> None:
    """Confirm the manifest and validation report exist."""

    assert MANIFEST_PATH.exists()
    assert VALIDATION_REPORT_PATH.exists()


def test_release_identity_values_are_valid() -> None:
    """Confirm release identifiers and fingerprints are valid."""

    manifest = load_json(MANIFEST_PATH)

    uuid.UUID(manifest["release_id"])

    release_fingerprint = manifest["release_fingerprint"]

    assert len(release_fingerprint) == 64
    assert all(
        character in "0123456789abcdef"
        for character in release_fingerprint
    )


def test_validation_identity_values_are_valid() -> None:
    """Confirm validation identifiers and fingerprints are valid."""

    report = load_json(VALIDATION_REPORT_PATH)

    uuid.UUID(report["validation_id"])

    validation_fingerprint = report[
        "validation_fingerprint"
    ]

    assert len(validation_fingerprint) == 64
    assert all(
        character in "0123456789abcdef"
        for character in validation_fingerprint
    )


def test_release_dataset_and_record_counts_are_correct() -> None:
    """Confirm the integrated release totals."""

    manifest = load_json(MANIFEST_PATH)

    assert (
        manifest["expected_dataset_count"]
        == EXPECTED_DATASET_COUNT
    )
    assert (
        manifest["actual_dataset_count"]
        == EXPECTED_DATASET_COUNT
    )
    assert (
        manifest["expected_total_record_count"]
        == EXPECTED_RECORD_COUNT
    )
    assert (
        manifest["actual_total_record_count"]
        == EXPECTED_RECORD_COUNT
    )
    assert manifest["dataset_count_reconciled"] is True
    assert manifest["record_count_reconciled"] is True


def test_release_contains_all_expected_datasets() -> None:
    """Confirm the exact expected dataset inventory."""

    manifest = load_json(MANIFEST_PATH)

    actual_names = {
        dataset["dataset_name"]
        for dataset in manifest["datasets"]
    }

    assert actual_names == EXPECTED_DATASET_NAMES


def test_dataset_names_and_file_names_are_unique() -> None:
    """Confirm logical and physical dataset names are unique."""

    manifest = load_json(MANIFEST_PATH)

    dataset_names = [
        dataset["dataset_name"]
        for dataset in manifest["datasets"]
    ]
    file_names = [
        dataset["file_name"]
        for dataset in manifest["datasets"]
    ]

    assert len(dataset_names) == len(set(dataset_names))
    assert len(file_names) == len(set(file_names))


def test_all_manifest_dataset_files_exist() -> None:
    """Confirm every manifested dataset file exists."""

    manifest = load_json(MANIFEST_PATH)

    for dataset in manifest["datasets"]:
        dataset_path = OUTPUT_DIRECTORY / dataset["file_name"]

        assert dataset_path.exists()
        assert dataset_path.is_file()
        assert dataset_path.stat().st_size > 0


def test_all_dataset_record_counts_match_manifest() -> None:
    """Recalculate every dataset record count."""

    manifest = load_json(MANIFEST_PATH)

    calculated_total = 0

    for dataset in manifest["datasets"]:
        dataset_path = OUTPUT_DIRECTORY / dataset["file_name"]
        actual_count = count_csv_records(dataset_path)

        assert actual_count == dataset["expected_record_count"]
        assert actual_count == dataset["actual_record_count"]
        assert dataset["record_count_reconciled"] is True

        calculated_total += actual_count

    assert calculated_total == EXPECTED_RECORD_COUNT


def test_all_dataset_hashes_match_manifest() -> None:
    """Recalculate and confirm every dataset hash."""

    manifest = load_json(MANIFEST_PATH)

    for dataset in manifest["datasets"]:
        dataset_path = OUTPUT_DIRECTORY / dataset["file_name"]

        assert dataset["hash_algorithm"] == "sha256"
        assert (
            calculate_sha256(dataset_path)
            == dataset["file_hash"]
        )


def test_all_dataset_schemas_match_manifest() -> None:
    """Confirm stored CSV headers match manifested schemas."""

    manifest = load_json(MANIFEST_PATH)

    for dataset in manifest["datasets"]:
        dataset_path = OUTPUT_DIRECTORY / dataset["file_name"]

        with dataset_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.reader(file)
            actual_columns = next(reader)

        assert actual_columns == dataset["columns"]
        assert len(actual_columns) == dataset["column_count"]
        assert len(actual_columns) == len(set(actual_columns))


def test_all_dataset_primary_keys_are_complete_and_unique() -> None:
    """Independently validate every dataset primary key."""

    manifest = load_json(MANIFEST_PATH)

    for dataset in manifest["datasets"]:
        dataset_path = OUTPUT_DIRECTORY / dataset["file_name"]

        primary_keys = read_primary_keys(
            dataset_path,
            dataset["primary_key"],
        )

        assert primary_keys
        assert all(
            all(value for value in key)
            for key in primary_keys
        )
        assert len(primary_keys) == len(set(primary_keys))
        assert dataset["primary_key_unique"] is True
        assert dataset["primary_key_null_count"] == 0


def test_release_approval_flags_are_true() -> None:
    """Confirm the release is approved for both consumers."""

    manifest = load_json(MANIFEST_PATH)

    assert manifest["approved_for_database_loading"] is True
    assert manifest["approved_for_fabric_ingestion"] is True


def test_release_reconciliation_controls_are_complete() -> None:
    """Confirm the required release-control inventory."""

    manifest = load_json(MANIFEST_PATH)

    controls = manifest["required_reconciliation_controls"]

    assert (
        manifest["reconciliation_control_count"]
        == EXPECTED_RECONCILIATION_CONTROL_COUNT
    )
    assert len(controls) == EXPECTED_RECONCILIATION_CONTROL_COUNT
    assert len(controls) == len(set(controls))


def test_validation_report_matches_release() -> None:
    """Confirm the validation report belongs to this release."""

    manifest = load_json(MANIFEST_PATH)
    report = load_json(VALIDATION_REPORT_PATH)

    assert report["release_id"] == manifest["release_id"]
    assert (
        report["release_fingerprint"]
        == manifest["release_fingerprint"]
    )
    assert report["dataset_count"] == EXPECTED_DATASET_COUNT
    assert report["record_count"] == EXPECTED_RECORD_COUNT


def test_all_component_validations_passed() -> None:
    """Confirm all independent component validators passed."""

    report = load_json(VALIDATION_REPORT_PATH)

    component_validations = report[
        "component_validations"
    ]

    assert (
        report["component_validation_count"]
        == EXPECTED_COMPONENT_VALIDATION_COUNT
    )
    assert (
        report["passed_component_validation_count"]
        == EXPECTED_COMPONENT_VALIDATION_COUNT
    )
    assert (
        len(component_validations)
        == EXPECTED_COMPONENT_VALIDATION_COUNT
    )

    assert all(
        validation["status"] == "PASSED"
        for validation in component_validations
    )
    assert all(
        validation["return_code"] == 0
        for validation in component_validations
    )


def test_all_reconciliation_controls_passed() -> None:
    """Confirm every cross-system reconciliation passed."""

    report = load_json(VALIDATION_REPORT_PATH)

    controls = report["reconciliation_controls"]

    assert (
        report["reconciliation_control_count"]
        == EXPECTED_RECONCILIATION_CONTROL_COUNT
    )
    assert (
        report["passed_reconciliation_control_count"]
        == EXPECTED_RECONCILIATION_CONTROL_COUNT
    )
    assert (
        len(controls)
        == EXPECTED_RECONCILIATION_CONTROL_COUNT
    )
    assert all(
        control["status"] == "PASSED"
        for control in controls
    )


def test_validation_report_control_names_match_manifest() -> None:
    """Confirm report controls match the release contract."""

    manifest = load_json(MANIFEST_PATH)
    report = load_json(VALIDATION_REPORT_PATH)

    manifest_controls = set(
        manifest["required_reconciliation_controls"]
    )
    report_controls = {
        control["control_name"]
        for control in report["reconciliation_controls"]
    }

    assert report_controls == manifest_controls


def test_all_release_quality_statuses_passed() -> None:
    """Confirm every top-level release quality gate passed."""

    report = load_json(VALIDATION_REPORT_PATH)

    assert report["manifest_integrity_status"] == "PASSED"
    assert report["dataset_hash_validation_status"] == "PASSED"
    assert report["dataset_schema_validation_status"] == "PASSED"
    assert report["dataset_record_count_status"] == "PASSED"
    assert report["primary_key_validation_status"] == "PASSED"
    assert report["overall_status"] == "PASSED"


def test_validation_report_approval_flags_are_true() -> None:
    """Confirm the validated release remains approved."""

    report = load_json(VALIDATION_REPORT_PATH)

    assert report["approved_for_database_loading"] is True
    assert report["approved_for_fabric_ingestion"] is True


def test_operational_release_generation_is_reproducible() -> None:
    """Confirm release generation produces identical output."""

    first_result = run_python_script(GENERATOR_PATH)
    assert first_result.returncode == 0, first_result.stderr

    first_manifest = MANIFEST_PATH.read_bytes()

    second_result = run_python_script(GENERATOR_PATH)
    assert second_result.returncode == 0, second_result.stderr

    second_manifest = MANIFEST_PATH.read_bytes()

    assert first_manifest == second_manifest


def test_operational_release_validation_is_reproducible() -> None:
    """Confirm validation produces an identical report."""

    first_result = run_python_script(VALIDATOR_PATH)
    assert first_result.returncode == 0, first_result.stderr

    first_report = VALIDATION_REPORT_PATH.read_bytes()

    second_result = run_python_script(VALIDATOR_PATH)
    assert second_result.returncode == 0, second_result.stderr

    second_report = VALIDATION_REPORT_PATH.read_bytes()

    assert first_report == second_report