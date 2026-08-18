"""Validate the BritMart integrated operational-data release."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from generate_operational_data_release import (
    CONFIG_PATH,
    MANIFEST_FILE_NAME,
    build_release_manifest,
    load_json,
    resolve_output_directory,
    validate_release_configuration,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_GENERATORS_DIRECTORY = PROJECT_ROOT / "data-generators"
SOURCE_DIRECTORY = DATA_GENERATORS_DIRECTORY / "src"
VALIDATION_REPORT_FILE_NAME = (
    "operational_data_validation_report.json"
)

VALIDATION_NAMESPACE = uuid.UUID(
    "8103a260-135c-4d84-bf23-fd79fc618267"
)

REQUIRED_COMPONENT_VALIDATORS = [
    {
        "validation_name": "MASTER_DATA",
        "script_name": "validate_master_data.py",
        "controls": [
            "MASTER_DATA_REFERENTIAL_INTEGRITY",
            "SUPPLIER_PRODUCT_AGREEMENT_INTEGRITY",
        ],
    },
    {
        "validation_name": "PURCHASE_ORDERS",
        "script_name": "validate_purchase_orders.py",
        "controls": [
            "PURCHASE_ORDER_HEADER_TO_LINE",
        ],
    },
    {
        "validation_name": "SHIPMENTS",
        "script_name": "validate_shipments.py",
        "controls": [
            "PURCHASE_ORDER_TO_SHIPMENT",
            "SHIPMENT_HEADER_TO_LINE",
        ],
    },
    {
        "validation_name": "WAREHOUSE_GOODS_RECEIPTS",
        "script_name": "validate_goods_receipts.py",
        "controls": [
            "SHIPMENT_TO_GOODS_RECEIPT",
            "GOODS_RECEIPT_HEADER_TO_LINE",
            "GOODS_RECEIPT_TO_INVENTORY_MOVEMENT",
            "AVAILABLE_AND_QUARANTINE_INVENTORY",
            "REJECTED_QUANTITY_ZERO_STOCK_EFFECT",
        ],
    },
    {
        "validation_name": "SUPPLIER_PERFORMANCE",
        "script_name": "validate_supplier_performance.py",
        "controls": [
            "DELIVERY_TO_SUPPLIER_PERFORMANCE",
            "WAREHOUSE_QUALITY_TO_SUPPLIER_PERFORMANCE",
            "MONTHLY_OTIF_SCORECARD",
        ],
    },
]


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write deterministic formatted JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            value,
            file,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        file.write("\n")


def canonical_json(value: Any) -> str:
    """Return a canonical JSON representation."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def create_validation_identity(
    release_id: str,
    release_fingerprint: str,
    validation_results: list[dict[str, Any]],
) -> tuple[str, str]:
    """Create deterministic validation fingerprint and identifier."""

    identity_payload = {
        "release_id": release_id,
        "release_fingerprint": release_fingerprint,
        "component_validations": [
            {
                "validation_name": result["validation_name"],
                "status": result["status"],
                "controls": result["controls"],
            }
            for result in validation_results
        ],
    }

    validation_fingerprint = hashlib.sha256(
        canonical_json(identity_payload).encode("utf-8")
    ).hexdigest()

    validation_id = str(
        uuid.uuid5(
            VALIDATION_NAMESPACE,
            validation_fingerprint,
        )
    )

    return validation_id, validation_fingerprint


def run_component_validator(
    definition: dict[str, Any],
) -> dict[str, Any]:
    """Run one existing domain validator."""

    script_path = SOURCE_DIRECTORY / definition["script_name"]

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required validator does not exist: {script_path}"
        )

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    standard_output = result.stdout.strip()
    standard_error = result.stderr.strip()

    validation_result = {
        "validation_name": definition["validation_name"],
        "script_name": definition["script_name"],
        "controls": definition["controls"],
        "return_code": result.returncode,
        "status": "PASSED" if result.returncode == 0 else "FAILED",
        "standard_output": standard_output.splitlines(),
        "standard_error": standard_error.splitlines(),
    }

    if result.returncode != 0:
        error_message = (
            standard_error
            or standard_output
            or "No validator error output was returned."
        )

        raise AssertionError(
            f"{definition['validation_name']} validation failed.\n"
            f"{error_message}"
        )

    return validation_result


def validate_manifest_identity(
    stored_manifest: dict[str, Any],
    expected_manifest: dict[str, Any],
) -> None:
    """Confirm the stored release identity is unchanged."""

    required_identity_fields = [
        "release_id",
        "release_fingerprint",
        "release_name",
        "release_version",
        "release_type",
        "release_timestamp_utc",
    ]

    for field in required_identity_fields:
        if stored_manifest.get(field) != expected_manifest.get(field):
            raise AssertionError(
                f"Release manifest identity field changed: {field}"
            )


def validate_manifest_dataset_inventory(
    stored_manifest: dict[str, Any],
    expected_manifest: dict[str, Any],
) -> None:
    """Validate dataset counts and total record counts."""

    if (
        stored_manifest.get("actual_dataset_count")
        != expected_manifest.get("actual_dataset_count")
    ):
        raise AssertionError(
            "Operational release dataset count is incorrect."
        )

    if (
        stored_manifest.get("actual_total_record_count")
        != expected_manifest.get("actual_total_record_count")
    ):
        raise AssertionError(
            "Operational release total record count is incorrect."
        )

    if not stored_manifest.get("dataset_count_reconciled"):
        raise AssertionError(
            "Dataset-count reconciliation is not approved."
        )

    if not stored_manifest.get("record_count_reconciled"):
        raise AssertionError(
            "Record-count reconciliation is not approved."
        )


def validate_manifest_datasets(
    stored_manifest: dict[str, Any],
    expected_manifest: dict[str, Any],
) -> None:
    """Validate every stored dataset manifest entry."""

    stored_datasets = stored_manifest.get("datasets")
    expected_datasets = expected_manifest.get("datasets")

    if not isinstance(stored_datasets, list):
        raise AssertionError(
            "Stored manifest datasets must be a list."
        )

    if stored_datasets != expected_datasets:
        stored_by_name = {
            item.get("dataset_name"): item
            for item in stored_datasets
            if isinstance(item, dict)
        }
        expected_by_name = {
            item.get("dataset_name"): item
            for item in expected_datasets
            if isinstance(item, dict)
        }

        all_dataset_names = sorted(
            set(stored_by_name) | set(expected_by_name)
        )

        changed_datasets = [
            dataset_name
            for dataset_name in all_dataset_names
            if stored_by_name.get(dataset_name)
            != expected_by_name.get(dataset_name)
        ]

        raise AssertionError(
            "Operational dataset manifest entries changed: "
            f"{changed_datasets}"
        )


def validate_approval_flags(
    manifest: dict[str, Any],
) -> None:
    """Confirm the release is explicitly approved downstream."""

    if not manifest.get("approved_for_database_loading"):
        raise AssertionError(
            "Release is not approved for database loading."
        )

    if not manifest.get("approved_for_fabric_ingestion"):
        raise AssertionError(
            "Release is not approved for Fabric ingestion."
        )


def validate_reconciliation_control_configuration(
    config: dict[str, Any],
    manifest: dict[str, Any],
) -> list[str]:
    """Validate configured reconciliation-control coverage."""

    configured_controls = config[
        "required_reconciliation_controls"
    ]

    manifest_controls = manifest.get(
        "required_reconciliation_controls"
    )

    if manifest_controls != configured_controls:
        raise AssertionError(
            "Manifest reconciliation controls do not match "
            "the operational release configuration."
        )

    validator_controls = [
        control
        for definition in REQUIRED_COMPONENT_VALIDATORS
        for control in definition["controls"]
        if control in configured_controls
    ]

    missing_controls = sorted(
        set(configured_controls) - set(validator_controls)
    )

    duplicate_controls = sorted(
        {
            control
            for control in validator_controls
            if validator_controls.count(control) > 1
        }
    )

    if missing_controls:
        raise AssertionError(
            "Required reconciliation controls are not covered: "
            f"{missing_controls}"
        )

    if duplicate_controls:
        raise AssertionError(
            "Reconciliation controls have duplicate validator "
            f"ownership: {duplicate_controls}"
        )

    if len(configured_controls) != 11:
        raise AssertionError(
            "The operational release must contain exactly "
            "11 reconciliation controls."
        )

    return configured_controls


def build_control_results(
    configured_controls: list[str],
    component_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a result for every configured control."""

    result_by_control: dict[str, dict[str, Any]] = {}

    for component_result in component_results:
        for control in component_result["controls"]:
            if control not in configured_controls:
                continue

            result_by_control[control] = {
                "control_name": control,
                "validation_name": component_result[
                    "validation_name"
                ],
                "validator_script": component_result[
                    "script_name"
                ],
                "status": component_result["status"],
            }

    control_results = [
        result_by_control[control]
        for control in configured_controls
    ]

    if any(
        result["status"] != "PASSED"
        for result in control_results
    ):
        raise AssertionError(
            "One or more operational reconciliation controls failed."
        )

    return control_results


def validate_full_manifest_equality(
    stored_manifest: dict[str, Any],
    expected_manifest: dict[str, Any],
) -> None:
    """Confirm the complete stored manifest is reproducible."""

    if stored_manifest != expected_manifest:
        raise AssertionError(
            "Stored operational release manifest is not reproducible."
        )


def build_validation_report(
    config: dict[str, Any],
    manifest: dict[str, Any],
    component_results: list[dict[str, Any]],
    control_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the integrated operational validation report."""

    validation_id, validation_fingerprint = (
        create_validation_identity(
            release_id=manifest["release_id"],
            release_fingerprint=manifest[
                "release_fingerprint"
            ],
            validation_results=component_results,
        )
    )

    passed_component_count = sum(
        result["status"] == "PASSED"
        for result in component_results
    )

    passed_control_count = sum(
        result["status"] == "PASSED"
        for result in control_results
    )

    return {
        "validation_id": validation_id,
        "validation_fingerprint": validation_fingerprint,
        "release_id": manifest["release_id"],
        "release_fingerprint": manifest[
            "release_fingerprint"
        ],
        "release_name": manifest["release_name"],
        "release_version": manifest["release_version"],
        "validated_at_utc": config[
            "release_timestamp_utc"
        ],
        "dataset_count": manifest[
            "actual_dataset_count"
        ],
        "record_count": manifest[
            "actual_total_record_count"
        ],
        "manifest_integrity_status": "PASSED",
        "dataset_hash_validation_status": "PASSED",
        "dataset_schema_validation_status": "PASSED",
        "dataset_record_count_status": "PASSED",
        "primary_key_validation_status": "PASSED",
        "component_validation_count": len(
            component_results
        ),
        "passed_component_validation_count": (
            passed_component_count
        ),
        "reconciliation_control_count": len(
            control_results
        ),
        "passed_reconciliation_control_count": (
            passed_control_count
        ),
        "component_validations": component_results,
        "reconciliation_controls": control_results,
        "approved_for_database_loading": True,
        "approved_for_fabric_ingestion": True,
        "overall_status": "PASSED",
    }


def run_all_validations() -> dict[str, Any]:
    """Run the complete operational release validation."""

    config = load_json(CONFIG_PATH)
    validate_release_configuration(config)

    output_directory = resolve_output_directory(config)
    manifest_path = (
        output_directory / MANIFEST_FILE_NAME
    )

    stored_manifest = load_json(manifest_path)

    expected_manifest = build_release_manifest(
        config=config,
        output_directory=output_directory,
    )

    validate_manifest_identity(
        stored_manifest,
        expected_manifest,
    )
    validate_manifest_dataset_inventory(
        stored_manifest,
        expected_manifest,
    )
    validate_manifest_datasets(
        stored_manifest,
        expected_manifest,
    )
    validate_approval_flags(stored_manifest)

    configured_controls = (
        validate_reconciliation_control_configuration(
            config,
            stored_manifest,
        )
    )

    validate_full_manifest_equality(
        stored_manifest,
        expected_manifest,
    )

    component_results = [
        run_component_validator(definition)
        for definition in REQUIRED_COMPONENT_VALIDATORS
    ]

    control_results = build_control_results(
        configured_controls,
        component_results,
    )

    validation_report = build_validation_report(
        config=config,
        manifest=stored_manifest,
        component_results=component_results,
        control_results=control_results,
    )

    report_path = (
        output_directory
        / VALIDATION_REPORT_FILE_NAME
    )
    write_json(report_path, validation_report)

    return validation_report


def main() -> None:
    """Validate the integrated operational-data release."""

    report = run_all_validations()

    output_directory = resolve_output_directory(
        load_json(CONFIG_PATH)
    )
    report_path = (
        output_directory
        / VALIDATION_REPORT_FILE_NAME
    )

    print(
        "BritMart integrated operational-data validation passed."
    )
    print(f"Validation ID: {report['validation_id']}")
    print(f"Release ID: {report['release_id']}")
    print(f"Datasets validated: {report['dataset_count']}")
    print(f"Records validated: {report['record_count']}")
    print(
        "Component validations passed: "
        f"{report['passed_component_validation_count']}/"
        f"{report['component_validation_count']}"
    )
    print(
        "Reconciliation controls passed: "
        f"{report['passed_reconciliation_control_count']}/"
        f"{report['reconciliation_control_count']}"
    )
    print(
        "Approved for database loading: "
        f"{report['approved_for_database_loading']}"
    )
    print(
        "Approved for Fabric ingestion: "
        f"{report['approved_for_fabric_ingestion']}"
    )
    print(f"Overall status: {report['overall_status']}")
    print(f"Validation report: {report_path}")


if __name__ == "__main__":
    main()