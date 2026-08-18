"""Automated tests for BritMart location master data."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import pytest


GENERATOR_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = GENERATOR_ROOT / "src"
OUTPUT_DIRECTORY = GENERATOR_ROOT / "output"
CONFIG_PATH = (
    GENERATOR_ROOT / "config" / "location_config.json"
)

sys.path.insert(0, str(SOURCE_DIRECTORY))

import generate_locations  # noqa: E402
import validate_locations  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def generated_location_data() -> None:
    """Generate the location dataset once for this test module."""

    generate_locations.main()


def read_csv(file_name: str) -> list[dict[str, str]]:
    """Read one generated CSV file."""

    file_path = OUTPUT_DIRECTORY / file_name

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as input_file:
        return list(csv.DictReader(input_file))


def load_configuration() -> dict:
    """Load the approved location configuration."""

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as input_file:
        return json.load(input_file)


def test_expected_output_files_exist() -> None:
    """Confirm that all location output files were produced."""

    expected_files = {
        "regions.csv",
        "distribution_centres.csv",
        "stores.csv",
        "location_manifest.json",
    }

    actual_files = {
        file_path.name
        for file_path in OUTPUT_DIRECTORY.iterdir()
        if file_path.is_file()
    }

    assert expected_files.issubset(actual_files)


def test_expected_record_counts() -> None:
    """Confirm that record counts match the approved specification."""

    configuration = load_configuration()
    regions = read_csv("regions.csv")
    centres = read_csv("distribution_centres.csv")
    stores = read_csv("stores.csv")

    assert len(regions) == int(
        configuration["expected_counts"]["regions"]
    )
    assert len(centres) == int(
        configuration["expected_counts"][
            "distribution_centres"
        ]
    )
    assert len(stores) == int(
        configuration["expected_counts"]["stores"]
    )


def test_business_codes_are_unique() -> None:
    """Confirm that important business codes are unique."""

    entity_fields = {
        "regions.csv": "region_code",
        "distribution_centres.csv": (
            "distribution_centre_code"
        ),
        "stores.csv": "store_code",
    }

    for file_name, field_name in entity_fields.items():
        rows = read_csv(file_name)
        values = [row[field_name] for row in rows]

        assert len(values) == len(set(values))


def test_technical_identifiers_are_unique() -> None:
    """Confirm that technical identifiers are unique."""

    entity_fields = {
        "regions.csv": "region_id",
        "distribution_centres.csv": (
            "distribution_centre_id"
        ),
        "stores.csv": "store_id",
    }

    for file_name, field_name in entity_fields.items():
        rows = read_csv(file_name)
        values = [row[field_name] for row in rows]

        assert len(values) == len(set(values))


def test_store_format_counts_match_configuration() -> None:
    """Confirm exact superstore, supermarket and convenience counts."""

    configuration = load_configuration()
    stores = read_csv("stores.csv")

    actual_counts = Counter(
        row["store_format"] for row in stores
    )
    expected_counts = {
        format_name: int(format_config["count"])
        for format_name, format_config in configuration[
            "store_formats"
        ].items()
    }

    assert dict(actual_counts) == expected_counts


def test_regional_store_counts_match_configuration() -> None:
    """Confirm the approved store allocation across UK regions."""

    configuration = load_configuration()
    stores = read_csv("stores.csv")

    actual_counts = Counter(
        row["region_code"] for row in stores
    )
    expected_counts = {
        region["region_code"]: int(region["store_count"])
        for region in configuration["regions"]
    }

    assert dict(actual_counts) == expected_counts


def test_every_store_has_valid_region() -> None:
    """Confirm store-to-region referential integrity."""

    regions = read_csv("regions.csv")
    stores = read_csv("stores.csv")

    valid_region_ids = {
        row["region_id"] for row in regions
    }

    assert all(
        store["region_id"] in valid_region_ids
        for store in stores
    )


def test_every_store_has_valid_distribution_centre() -> None:
    """Confirm store-to-distribution-centre integrity."""

    centres = read_csv("distribution_centres.csv")
    stores = read_csv("stores.csv")

    valid_centre_ids = {
        row["distribution_centre_id"]
        for row in centres
    }

    assert all(
        store["primary_distribution_centre_id"]
        in valid_centre_ids
        for store in stores
    )


def test_store_floor_areas_match_store_formats() -> None:
    """Confirm that floor area follows format-specific rules."""

    configuration = load_configuration()
    stores = read_csv("stores.csv")

    for store in stores:
        format_config = configuration["store_formats"][
            store["store_format"]
        ]
        floor_area = int(
            store["floor_area_square_metres"]
        )

        assert (
            int(
                format_config[
                    "minimum_floor_area_square_metres"
                ]
            )
            <= floor_area
            <= int(
                format_config[
                    "maximum_floor_area_square_metres"
                ]
            )
        )


def test_full_validation_suite_passes() -> None:
    """Run the production-style validation framework."""

    counts = validate_locations.validate_all()

    assert counts == {
        "regions": 12,
        "distribution_centres": 6,
        "stores": 120,
    }


def test_generation_is_reproducible() -> None:
    """Confirm identical output when the generator runs again."""

    file_names = [
        "regions.csv",
        "distribution_centres.csv",
        "stores.csv",
    ]

    first_versions = {
        file_name: (
            OUTPUT_DIRECTORY / file_name
        ).read_bytes()
        for file_name in file_names
    }

    generate_locations.main()

    second_versions = {
        file_name: (
            OUTPUT_DIRECTORY / file_name
        ).read_bytes()
        for file_name in file_names
    }

    assert first_versions == second_versions