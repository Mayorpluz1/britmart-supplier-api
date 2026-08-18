"""Validate BritMart supplier master data."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "supplier_config.json"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"

SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "supplier_manifest.json"
CATEGORY_PATH = OUTPUT_DIRECTORY / "categories.csv"

REQUIRED_COLUMNS = {
    "supplier_id",
    "supplier_code",
    "supplier_name",
    "legal_name",
    "supplier_type",
    "category_codes",
    "country_code",
    "origin_group",
    "default_currency_code",
    "standard_lead_time_days",
    "minimum_order_value",
    "supports_ambient",
    "supports_chilled",
    "supports_frozen",
    "risk_rating",
    "supplier_status",
    "active_flag",
    "payment_terms_days",
    "incoterm",
    "target_otif_rate",
    "target_quality_acceptance_rate",
    "contact_email",
    "effective_from",
    "effective_to",
    "created_at",
    "updated_at",
    "version_number",
}

ALLOWED_ORIGINS = {"GB", "EU", "OTHER"}
ALLOWED_RISK_RATINGS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
ALLOWED_STATUSES = {"ACTIVE", "SUSPENDED", "PENDING", "INACTIVE"}
ALLOWED_BOOLEAN_VALUES = {"true", "false"}
ALLOWED_INCOTERMS = {"DAP", "DDP", "FCA", "CPT"}

SUPPLIER_CODE_PATTERN = re.compile(r"^SUP-\d{4}$")
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")
EMAIL_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9.]*@supplier\.britmart\.example$"
)


def load_json(path: Path) -> dict:
    """Load a JSON document."""

    if not path.exists():
        raise AssertionError(f"Required file does not exist: {path}")

    with path.open("r", encoding="utf-8") as source_file:
        return json.load(source_file)


def load_csv(path: Path) -> list[dict[str, str]]:
    """Load a CSV document as dictionaries."""

    if not path.exists():
        raise AssertionError(f"Required file does not exist: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as source_file:
        return list(csv.DictReader(source_file))


def get_expected_supplier_count(config: dict) -> int:
    """Resolve the expected supplier count from the configuration."""

    project_config = config.get("project", {})

    return int(
        config.get(
            "expected_supplier_count",
            config.get(
                "supplier_count",
                project_config.get("expected_supplier_count", 50),
            ),
        )
    )


def calculate_sha256(path: Path) -> str:
    """Calculate a file SHA-256 digest."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(65_536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def validate_required_columns(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Confirm that the supplier extract has the expected schema."""

    if not supplier_rows:
        raise AssertionError("The supplier file contains no records.")

    actual_columns = set(supplier_rows[0].keys())
    missing_columns = REQUIRED_COLUMNS - actual_columns

    if missing_columns:
        raise AssertionError(
            f"Supplier file is missing columns: {sorted(missing_columns)}"
        )


def validate_record_count(
    supplier_rows: list[dict[str, str]],
    expected_count: int,
) -> None:
    """Confirm the configured supplier count."""

    if len(supplier_rows) != expected_count:
        raise AssertionError(
            f"Expected {expected_count} suppliers, "
            f"but found {len(supplier_rows)}."
        )


def validate_unique_keys(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Confirm uniqueness of technical and business identifiers."""

    supplier_ids = [row["supplier_id"] for row in supplier_rows]
    supplier_codes = [row["supplier_code"] for row in supplier_rows]
    supplier_names = [row["supplier_name"] for row in supplier_rows]
    contact_emails = [row["contact_email"] for row in supplier_rows]

    if len(supplier_ids) != len(set(supplier_ids)):
        raise AssertionError("Duplicate supplier_id values detected.")

    if len(supplier_codes) != len(set(supplier_codes)):
        raise AssertionError("Duplicate supplier_code values detected.")

    if len(supplier_names) != len(set(supplier_names)):
        raise AssertionError("Duplicate supplier_name values detected.")

    if len(contact_emails) != len(set(contact_emails)):
        raise AssertionError("Duplicate supplier contact emails detected.")


def validate_identifier_formats(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Validate UUIDs, business codes and reference-code formats."""

    expected_codes = {
        f"SUP-{number:04d}"
        for number in range(1, len(supplier_rows) + 1)
    }

    actual_codes = {row["supplier_code"] for row in supplier_rows}

    if actual_codes != expected_codes:
        raise AssertionError(
            "Supplier codes are not a complete sequential SUP-0001 series."
        )

    for row in supplier_rows:
        UUID(row["supplier_id"])

        if not SUPPLIER_CODE_PATTERN.fullmatch(row["supplier_code"]):
            raise AssertionError(
                f"Invalid supplier code: {row['supplier_code']}"
            )

        if not COUNTRY_CODE_PATTERN.fullmatch(row["country_code"]):
            raise AssertionError(
                f"Invalid country code for {row['supplier_code']}."
            )

        if not CURRENCY_CODE_PATTERN.fullmatch(
            row["default_currency_code"]
        ):
            raise AssertionError(
                f"Invalid currency code for {row['supplier_code']}."
            )

        if not EMAIL_PATTERN.fullmatch(row["contact_email"]):
            raise AssertionError(
                f"Invalid synthetic email for {row['supplier_code']}."
            )


def validate_enumerated_values(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Validate controlled operational values."""

    for row in supplier_rows:
        supplier_code = row["supplier_code"]

        if row["origin_group"] not in ALLOWED_ORIGINS:
            raise AssertionError(
                f"Invalid origin group for {supplier_code}."
            )

        if row["risk_rating"] not in ALLOWED_RISK_RATINGS:
            raise AssertionError(
                f"Invalid risk rating for {supplier_code}."
            )

        if row["supplier_status"] not in ALLOWED_STATUSES:
            raise AssertionError(
                f"Invalid supplier status for {supplier_code}."
            )

        if row["incoterm"] not in ALLOWED_INCOTERMS:
            raise AssertionError(
                f"Invalid Incoterm for {supplier_code}."
            )

        for boolean_column in [
            "supports_ambient",
            "supports_chilled",
            "supports_frozen",
            "active_flag",
        ]:
            if row[boolean_column] not in ALLOWED_BOOLEAN_VALUES:
                raise AssertionError(
                    f"Invalid Boolean value in {boolean_column} "
                    f"for {supplier_code}."
                )


def validate_business_rules(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Validate supplier operational rules."""

    for row in supplier_rows:
        supplier_code = row["supplier_code"]

        try:
            minimum_order_value = Decimal(row["minimum_order_value"])
            target_otif_rate = Decimal(row["target_otif_rate"])
            target_quality_rate = Decimal(
                row["target_quality_acceptance_rate"]
            )
        except InvalidOperation as error:
            raise AssertionError(
                f"Invalid decimal value for {supplier_code}."
            ) from error

        if minimum_order_value <= 0:
            raise AssertionError(
                f"Minimum order value must be positive for {supplier_code}."
            )

        lead_time = int(row["standard_lead_time_days"])

        if lead_time <= 0 or lead_time > 90:
            raise AssertionError(
                f"Invalid lead time for {supplier_code}: {lead_time}"
            )

        payment_terms = int(row["payment_terms_days"])

        if payment_terms not in {14, 30, 45, 60}:
            raise AssertionError(
                f"Invalid payment terms for {supplier_code}."
            )

        if not Decimal("0.88") <= target_otif_rate <= Decimal("0.98"):
            raise AssertionError(
                f"OTIF target outside the configured range "
                f"for {supplier_code}."
            )

        if not (
            Decimal("0.97")
            <= target_quality_rate
            <= Decimal("0.999")
        ):
            raise AssertionError(
                f"Quality target outside the configured range "
                f"for {supplier_code}."
            )

        if not any(
            row[column] == "true"
            for column in [
                "supports_ambient",
                "supports_chilled",
                "supports_frozen",
            ]
        ):
            raise AssertionError(
                f"{supplier_code} supports no storage type."
            )

        if (
            row["supplier_status"] == "INACTIVE"
            and row["active_flag"] != "false"
        ):
            raise AssertionError(
                f"Inactive supplier {supplier_code} has active_flag=true."
            )

        if (
            row["supplier_status"] != "INACTIVE"
            and row["active_flag"] != "true"
        ):
            raise AssertionError(
                f"Operational supplier {supplier_code} "
                "has active_flag=false."
            )

        if row["origin_group"] == "GB":
            if row["default_currency_code"] != "GBP":
                raise AssertionError(
                    f"Domestic supplier {supplier_code} must use GBP."
                )

            if row["incoterm"] not in {"DAP", "DDP"}:
                raise AssertionError(
                    f"Domestic supplier {supplier_code} "
                    "has an invalid Incoterm."
                )


def validate_dates_and_timestamps(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Validate effective dates, audit timestamps and versions."""

    for row in supplier_rows:
        supplier_code = row["supplier_code"]

        datetime.fromisoformat(row["effective_from"])

        if row["effective_to"]:
            effective_from = datetime.fromisoformat(
                row["effective_from"]
            )
            effective_to = datetime.fromisoformat(row["effective_to"])

            if effective_to < effective_from:
                raise AssertionError(
                    f"effective_to precedes effective_from "
                    f"for {supplier_code}."
                )

        for timestamp_column in ["created_at", "updated_at"]:
            timestamp = datetime.fromisoformat(
                row[timestamp_column].replace("Z", "+00:00")
            )

            if timestamp.tzinfo is None:
                raise AssertionError(
                    f"{timestamp_column} is not timezone-aware "
                    f"for {supplier_code}."
                )

            if timestamp.utcoffset().total_seconds() != 0:
                raise AssertionError(
                    f"{timestamp_column} is not UTC "
                    f"for {supplier_code}."
                )

        if int(row["version_number"]) != 1:
            raise AssertionError(
                f"Initial supplier version must equal 1 "
                f"for {supplier_code}."
            )


def load_category_codes() -> set[str]:
    """Load valid product-category business codes when available."""

    if not CATEGORY_PATH.exists():
        return set()

    category_rows = load_csv(CATEGORY_PATH)

    if not category_rows:
        return set()

    possible_columns = [
        "category_code",
        "category_id",
        "code",
    ]

    for column in possible_columns:
        if column in category_rows[0]:
            return {
                row[column]
                for row in category_rows
                if row[column]
            }

    raise AssertionError(
        "categories.csv has no recognised category-code column."
    )


def validate_category_references(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Confirm supplier category capabilities reference valid categories."""

    valid_category_codes = load_category_codes()

    for row in supplier_rows:
        category_codes = {
            value.strip()
            for value in row["category_codes"].split("|")
            if value.strip()
        }

        if not category_codes:
            raise AssertionError(
                f"{row['supplier_code']} has no category capability."
            )

        if valid_category_codes:
            unknown_codes = category_codes - valid_category_codes

            if unknown_codes:
                raise AssertionError(
                    f"{row['supplier_code']} references unknown "
                    f"categories: {sorted(unknown_codes)}"
                )


def validate_distribution_totals(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Confirm the agreed exact supplier distributions."""

    expected_origins = {
        "GB": 34,
        "EU": 10,
        "OTHER": 6,
    }
    expected_statuses = {
        "ACTIVE": 46,
        "SUSPENDED": 2,
        "PENDING": 1,
        "INACTIVE": 1,
    }
    expected_risks = {
        "LOW": 20,
        "MEDIUM": 22,
        "HIGH": 7,
        "CRITICAL": 1,
    }

    actual_origins = Counter(
        row["origin_group"] for row in supplier_rows
    )
    actual_statuses = Counter(
        row["supplier_status"] for row in supplier_rows
    )
    actual_risks = Counter(
        row["risk_rating"] for row in supplier_rows
    )

    if dict(actual_origins) != expected_origins:
        raise AssertionError(
            f"Origin distribution mismatch: {dict(actual_origins)}"
        )

    if dict(actual_statuses) != expected_statuses:
        raise AssertionError(
            f"Status distribution mismatch: {dict(actual_statuses)}"
        )

    if dict(actual_risks) != expected_risks:
        raise AssertionError(
            f"Risk distribution mismatch: {dict(actual_risks)}"
        )


def validate_risk_status_relationship(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Confirm controlled non-active statuses target riskier suppliers."""

    inactive_suppliers = [
        row
        for row in supplier_rows
        if row["supplier_status"] == "INACTIVE"
    ]

    if len(inactive_suppliers) != 1:
        raise AssertionError(
            "Exactly one supplier must have INACTIVE status."
        )

    if inactive_suppliers[0]["risk_rating"] != "CRITICAL":
        raise AssertionError(
            "The inactive supplier should hold CRITICAL risk."
        )

    suspended_suppliers = [
        row
        for row in supplier_rows
        if row["supplier_status"] == "SUSPENDED"
    ]

    if any(
        row["risk_rating"] not in {"HIGH", "CRITICAL"}
        for row in suspended_suppliers
    ):
        raise AssertionError(
            "Suspended suppliers must be HIGH or CRITICAL risk."
        )


def validate_manifest(
    supplier_rows: list[dict[str, str]],
) -> None:
    """Validate supplier manifest completeness and file integrity."""

    manifest = load_json(MANIFEST_PATH)

    if manifest.get("record_count") != len(supplier_rows):
        raise AssertionError(
            "Supplier manifest record count does not match suppliers.csv."
        )

    if manifest.get("output_file") != SUPPLIER_PATH.name:
        raise AssertionError(
            "Supplier manifest contains an incorrect output filename."
        )

    actual_hash = calculate_sha256(SUPPLIER_PATH)

    if manifest.get("output_sha256") != actual_hash:
        raise AssertionError(
            "Supplier manifest SHA-256 does not match suppliers.csv."
        )

    if manifest.get("business_key") != "supplier_code":
        raise AssertionError(
            "Supplier manifest has the wrong business key."
        )

    if manifest.get("technical_key") != "supplier_id":
        raise AssertionError(
            "Supplier manifest has the wrong technical key."
        )

    if manifest.get("incremental_columns") != [
        "updated_at",
        "supplier_id",
    ]:
        raise AssertionError(
            "Supplier manifest incremental ordering is incorrect."
        )


def run_all_validations() -> list[dict[str, str]]:
    """Run the complete supplier validation suite."""

    config = load_json(CONFIG_PATH)
    supplier_rows = load_csv(SUPPLIER_PATH)
    expected_count = get_expected_supplier_count(config)

    validate_required_columns(supplier_rows)
    validate_record_count(supplier_rows, expected_count)
    validate_unique_keys(supplier_rows)
    validate_identifier_formats(supplier_rows)
    validate_enumerated_values(supplier_rows)
    validate_business_rules(supplier_rows)
    validate_dates_and_timestamps(supplier_rows)
    validate_category_references(supplier_rows)
    validate_distribution_totals(supplier_rows)
    validate_risk_status_relationship(supplier_rows)
    validate_manifest(supplier_rows)

    return supplier_rows


def main() -> None:
    """Execute validation and display a concise result."""

    supplier_rows = run_all_validations()

    print("BritMart supplier validation passed.")
    print(f"Suppliers validated: {len(supplier_rows)}")
    print(
        "Active suppliers: "
        f"{sum(row['supplier_status'] == 'ACTIVE' for row in supplier_rows)}"
    )
    print(
        "Countries represented: "
        f"{len({row['country_code'] for row in supplier_rows})}"
    )


if __name__ == "__main__":
    main()