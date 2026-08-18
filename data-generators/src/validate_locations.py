"""Validate generated BritMart location master data."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


GENERATOR_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = GENERATOR_ROOT / "config" / "location_config.json"
OUTPUT_DIRECTORY = GENERATOR_ROOT / "output"

REGIONS_PATH = OUTPUT_DIRECTORY / "regions.csv"
DISTRIBUTION_CENTRES_PATH = (
    OUTPUT_DIRECTORY / "distribution_centres.csv"
)
STORES_PATH = OUTPUT_DIRECTORY / "stores.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "location_manifest.json"


class LocationValidationError(Exception):
    """Raised when generated location data fails validation."""


def load_json(file_path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    if not file_path.exists():
        raise LocationValidationError(
            f"Required JSON file does not exist: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def load_csv(file_path: Path) -> list[dict[str, str]]:
    """Load a CSV file as a list of dictionaries."""

    if not file_path.exists():
        raise LocationValidationError(
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
    """Confirm that required columns and values are present."""

    if not rows:
        raise LocationValidationError(
            f"{entity_name} contains no records."
        )

    actual_fields = set(rows[0])

    missing_columns = required_fields.difference(actual_fields)
    if missing_columns:
        raise LocationValidationError(
            f"{entity_name} is missing columns: "
            f"{sorted(missing_columns)}"
        )

    for row_number, row in enumerate(rows, start=2):
        for field_name in required_fields:
            value = row.get(field_name)

            if value is None or value.strip() == "":
                raise LocationValidationError(
                    f"{entity_name} row {row_number} has an empty "
                    f"required field: {field_name}"
                )


def require_unique(
    rows: list[dict[str, str]],
    field_name: str,
    entity_name: str,
) -> None:
    """Confirm that a field contains unique values."""

    values = [row[field_name] for row in rows]
    duplicates = [
        value
        for value, count in Counter(values).items()
        if count > 1
    ]

    if duplicates:
        raise LocationValidationError(
            f"{entity_name}.{field_name} contains duplicates: "
            f"{duplicates[:10]}"
        )


def require_positive_integer(
    value: str,
    field_name: str,
    entity_name: str,
) -> None:
    """Confirm that a value is a positive integer."""

    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise LocationValidationError(
            f"{entity_name}.{field_name} must be an integer: "
            f"{value}"
        ) from exc

    if parsed_value <= 0:
        raise LocationValidationError(
            f"{entity_name}.{field_name} must be positive: "
            f"{value}"
        )


def validate_regions(
    regions: list[dict[str, str]],
    expected_count: int,
) -> set[str]:
    """Validate region records and return their identifiers."""

    required_fields = {
        "region_id",
        "region_code",
        "region_name",
        "country_name",
        "active_flag",
        "created_at",
        "updated_at",
    }
    require_fields(regions, required_fields, "regions")

    if len(regions) != expected_count:
        raise LocationValidationError(
            f"Expected {expected_count} regions but found "
            f"{len(regions)}."
        )

    require_unique(regions, "region_id", "regions")
    require_unique(regions, "region_code", "regions")
    require_unique(regions, "region_name", "regions")

    for row in regions:
        if not row["region_code"].startswith("REG-"):
            raise LocationValidationError(
                f"Invalid region code: {row['region_code']}"
            )

        if row["active_flag"].lower() != "true":
            raise LocationValidationError(
                f"Initial region must be active: "
                f"{row['region_code']}"
            )

    return {row["region_id"] for row in regions}


def validate_distribution_centres(
    centres: list[dict[str, str]],
    expected_count: int,
    valid_region_ids: set[str],
) -> set[str]:
    """Validate distribution-centre records."""

    required_fields = {
        "distribution_centre_id",
        "distribution_centre_code",
        "distribution_centre_name",
        "region_id",
        "region_code",
        "location_area",
        "postcode_area",
        "latitude",
        "longitude",
        "supports_ambient",
        "supports_chilled",
        "supports_frozen",
        "daily_receiving_capacity_cases",
        "daily_dispatch_capacity_cases",
        "opened_date",
        "active_flag",
        "created_at",
        "updated_at",
    }
    require_fields(
        centres,
        required_fields,
        "distribution_centres",
    )

    if len(centres) != expected_count:
        raise LocationValidationError(
            f"Expected {expected_count} distribution centres but "
            f"found {len(centres)}."
        )

    require_unique(
        centres,
        "distribution_centre_id",
        "distribution_centres",
    )
    require_unique(
        centres,
        "distribution_centre_code",
        "distribution_centres",
    )
    require_unique(
        centres,
        "distribution_centre_name",
        "distribution_centres",
    )

    chilled_count = 0
    frozen_count = 0

    for row in centres:
        if row["region_id"] not in valid_region_ids:
            raise LocationValidationError(
                "Distribution centre references an unknown region: "
                f"{row['distribution_centre_code']}"
            )

        if not row["distribution_centre_code"].startswith("DC-"):
            raise LocationValidationError(
                "Invalid distribution-centre code: "
                f"{row['distribution_centre_code']}"
            )

        if row["supports_ambient"].lower() != "true":
            raise LocationValidationError(
                "Every initial distribution centre must support "
                f"ambient products: "
                f"{row['distribution_centre_code']}"
            )

        if row["supports_chilled"].lower() == "true":
            chilled_count += 1

        if row["supports_frozen"].lower() == "true":
            frozen_count += 1

        require_positive_integer(
            row["daily_receiving_capacity_cases"],
            "daily_receiving_capacity_cases",
            "distribution_centres",
        )
        require_positive_integer(
            row["daily_dispatch_capacity_cases"],
            "daily_dispatch_capacity_cases",
            "distribution_centres",
        )

        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        if not 49.0 <= latitude <= 61.0:
            raise LocationValidationError(
                f"Unexpected UK latitude for "
                f"{row['distribution_centre_code']}: {latitude}"
            )

        if not -9.0 <= longitude <= 3.0:
            raise LocationValidationError(
                f"Unexpected UK longitude for "
                f"{row['distribution_centre_code']}: {longitude}"
            )

    if chilled_count < 5:
        raise LocationValidationError(
            "At least five distribution centres must support chilled "
            "products."
        )

    if frozen_count < 4:
        raise LocationValidationError(
            "At least four distribution centres must support frozen "
            "products."
        )

    return {
        row["distribution_centre_id"]
        for row in centres
    }


def validate_stores(
    stores: list[dict[str, str]],
    configuration: dict[str, Any],
    valid_region_ids: set[str],
    valid_centre_ids: set[str],
) -> None:
    """Validate store master records."""

    required_fields = {
        "store_id",
        "store_code",
        "store_name",
        "region_id",
        "region_code",
        "primary_distribution_centre_id",
        "primary_distribution_centre_code",
        "store_format",
        "city",
        "postcode_area",
        "latitude",
        "longitude",
        "floor_area_square_metres",
        "sales_weight",
        "opening_date",
        "online_collection_flag",
        "home_delivery_support_flag",
        "active_flag",
        "created_at",
        "updated_at",
    }
    require_fields(stores, required_fields, "stores")

    expected_count = int(
        configuration["expected_counts"]["stores"]
    )

    if len(stores) != expected_count:
        raise LocationValidationError(
            f"Expected {expected_count} stores but found "
            f"{len(stores)}."
        )

    require_unique(stores, "store_id", "stores")
    require_unique(stores, "store_code", "stores")
    require_unique(stores, "store_name", "stores")

    actual_format_counts = Counter(
        row["store_format"] for row in stores
    )
    expected_format_counts = {
        format_name: int(format_config["count"])
        for format_name, format_config in configuration[
            "store_formats"
        ].items()
    }

    if dict(actual_format_counts) != expected_format_counts:
        raise LocationValidationError(
            "Store-format counts do not match configuration. "
            f"Expected {expected_format_counts}; found "
            f"{dict(actual_format_counts)}."
        )

    expected_region_counts = {
        region["region_code"]: int(region["store_count"])
        for region in configuration["regions"]
    }
    actual_region_counts = Counter(
        row["region_code"] for row in stores
    )

    if dict(actual_region_counts) != expected_region_counts:
        raise LocationValidationError(
            "Regional store counts do not match configuration. "
            f"Expected {expected_region_counts}; found "
            f"{dict(actual_region_counts)}."
        )

    region_centre_mapping = {
        region["region_code"]: region[
            "primary_distribution_centre_code"
        ]
        for region in configuration["regions"]
    }

    for row in stores:
        store_format = row["store_format"]

        if row["region_id"] not in valid_region_ids:
            raise LocationValidationError(
                f"Store references an unknown region: "
                f"{row['store_code']}"
            )

        if (
            row["primary_distribution_centre_id"]
            not in valid_centre_ids
        ):
            raise LocationValidationError(
                f"Store references an unknown distribution centre: "
                f"{row['store_code']}"
            )

        expected_centre_code = region_centre_mapping[
            row["region_code"]
        ]

        if (
            row["primary_distribution_centre_code"]
            != expected_centre_code
        ):
            raise LocationValidationError(
                f"Store {row['store_code']} has distribution centre "
                f"{row['primary_distribution_centre_code']}; expected "
                f"{expected_centre_code}."
            )

        if store_format not in configuration["store_formats"]:
            raise LocationValidationError(
                f"Unsupported store format: {store_format}"
            )

        format_config = configuration["store_formats"][
            store_format
        ]
        floor_area = int(row["floor_area_square_metres"])
        minimum_area = int(
            format_config[
                "minimum_floor_area_square_metres"
            ]
        )
        maximum_area = int(
            format_config[
                "maximum_floor_area_square_metres"
            ]
        )

        if not minimum_area <= floor_area <= maximum_area:
            raise LocationValidationError(
                f"Store {row['store_code']} floor area "
                f"{floor_area} is invalid for {store_format}."
            )

        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        if not 49.0 <= latitude <= 61.0:
            raise LocationValidationError(
                f"Store {row['store_code']} has unexpected latitude "
                f"{latitude}."
            )

        if not -9.0 <= longitude <= 3.0:
            raise LocationValidationError(
                f"Store {row['store_code']} has unexpected longitude "
                f"{longitude}."
            )

        if row["active_flag"].lower() != "true":
            raise LocationValidationError(
                f"Initial store must be active: {row['store_code']}"
            )


def validate_manifest(
    manifest: dict[str, Any],
    region_count: int,
    centre_count: int,
    store_count: int,
) -> None:
    """Validate manifest counts and file hashes."""

    expected_counts = {
        "regions": region_count,
        "distribution_centres": centre_count,
        "stores": store_count,
    }

    if manifest.get("record_counts") != expected_counts:
        raise LocationValidationError(
            "Manifest record counts do not match generated files."
        )

    file_paths = {
        "regions.csv": REGIONS_PATH,
        "distribution_centres.csv": (
            DISTRIBUTION_CENTRES_PATH
        ),
        "stores.csv": STORES_PATH,
    }

    for file_name, file_path in file_paths.items():
        expected_hash = manifest["files"][file_name]["sha256"]
        actual_hash = calculate_sha256(file_path)

        if actual_hash != expected_hash:
            raise LocationValidationError(
                f"Manifest hash does not match {file_name}."
            )


def validate_all() -> dict[str, int]:
    """Run the complete location validation suite."""

    configuration = load_json(CONFIG_PATH)
    regions = load_csv(REGIONS_PATH)
    distribution_centres = load_csv(
        DISTRIBUTION_CENTRES_PATH
    )
    stores = load_csv(STORES_PATH)
    manifest = load_json(MANIFEST_PATH)

    valid_region_ids = validate_regions(
        regions,
        int(configuration["expected_counts"]["regions"]),
    )

    valid_centre_ids = validate_distribution_centres(
        distribution_centres,
        int(
            configuration["expected_counts"][
                "distribution_centres"
            ]
        ),
        valid_region_ids,
    )

    validate_stores(
        stores,
        configuration,
        valid_region_ids,
        valid_centre_ids,
    )

    validate_manifest(
        manifest,
        len(regions),
        len(distribution_centres),
        len(stores),
    )

    return {
        "regions": len(regions),
        "distribution_centres": len(
            distribution_centres
        ),
        "stores": len(stores),
    }


def main() -> None:
    """Execute validation and print a concise result."""

    counts = validate_all()

    print("BritMart location validation passed.")
    print(f"Regions validated: {counts['regions']}")
    print(
        "Distribution centres validated: "
        f"{counts['distribution_centres']}"
    )
    print(f"Stores validated: {counts['stores']}")


if __name__ == "__main__":
    main()