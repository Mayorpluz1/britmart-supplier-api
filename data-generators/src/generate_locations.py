"""Generate deterministic BritMart region, distribution-centre and store data."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


GENERATOR_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = GENERATOR_ROOT / "config" / "location_config.json"
OUTPUT_DIRECTORY = GENERATOR_ROOT / "output"

REGIONS_OUTPUT_PATH = OUTPUT_DIRECTORY / "regions.csv"
DISTRIBUTION_CENTRES_OUTPUT_PATH = (
    OUTPUT_DIRECTORY / "distribution_centres.csv"
)
STORES_OUTPUT_PATH = OUTPUT_DIRECTORY / "stores.csv"
MANIFEST_OUTPUT_PATH = OUTPUT_DIRECTORY / "location_manifest.json"


# Approximate regional centres are used only to generate fictional coordinates.
REGION_CENTRES: dict[str, tuple[float, float, float]] = {
    "REG-001": (51.5074, -0.1278, 0.25),
    "REG-002": (51.2500, -0.5000, 0.80),
    "REG-003": (53.4808, -2.2426, 0.65),
    "REG-004": (52.4862, -1.8904, 0.55),
    "REG-005": (53.8008, -1.5491, 0.60),
    "REG-006": (52.2400, 0.4200, 0.75),
    "REG-007": (51.4545, -2.5879, 0.80),
    "REG-008": (52.9548, -1.1581, 0.60),
    "REG-009": (54.9783, -1.6178, 0.45),
    "REG-010": (51.4816, -3.1791, 0.85),
    "REG-011": (55.9533, -3.1883, 1.10),
    "REG-012": (54.5973, -5.9301, 0.55),
}

STORE_NAME_SUFFIXES = [
    "Central",
    "North",
    "South",
    "East",
    "West",
    "Retail Park",
    "Town Centre",
    "Riverside",
    "Market",
    "Gateway",
]


def load_configuration() -> dict[str, Any]:
    """Load and perform basic validation of the location configuration."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Location configuration was not found: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        configuration = json.load(config_file)

    required_sections = {
        "project",
        "expected_counts",
        "store_formats",
        "regions",
        "distribution_centres",
    }
    missing_sections = required_sections.difference(configuration)

    if missing_sections:
        raise ValueError(
            f"Configuration is missing sections: {sorted(missing_sections)}"
        )

    return configuration


def deterministic_uuid(
    namespace: uuid.UUID,
    entity_type: str,
    business_code: str,
) -> str:
    """Return a repeatable UUID based on an entity type and business code."""

    canonical_name = f"britmart:{entity_type}:{business_code}"
    return str(uuid.uuid5(namespace, canonical_name))


def random_date(
    random_generator: random.Random,
    start_date: date,
    end_date: date,
) -> date:
    """Return a deterministic random date inside the supplied range."""

    day_range = (end_date - start_date).days
    return start_date + timedelta(
        days=random_generator.randint(0, day_range)
    )


def write_csv(
    file_path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    """Write rows to a UTF-8 CSV file using a stable column order."""

    if not rows:
        raise ValueError(f"No records were supplied for {file_path.name}")

    with file_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def calculate_sha256(file_path: Path) -> str:
    """Calculate the SHA-256 hash of an output file."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(65536), b""):
            sha256.update(block)

    return sha256.hexdigest()


def build_store_format_sequence(
    configuration: dict[str, Any],
    random_generator: random.Random,
) -> list[str]:
    """Create an exact but randomly distributed store-format sequence."""

    store_formats: list[str] = []

    for format_name, format_config in configuration[
        "store_formats"
    ].items():
        store_formats.extend(
            [format_name] * int(format_config["count"])
        )

    random_generator.shuffle(store_formats)
    return store_formats


def generate_regions(
    configuration: dict[str, Any],
    namespace: uuid.UUID,
    generated_at: str,
) -> list[dict[str, Any]]:
    """Generate the region master records."""

    records: list[dict[str, Any]] = []

    for region in configuration["regions"]:
        records.append(
            {
                "region_id": deterministic_uuid(
                    namespace,
                    "region",
                    region["region_code"],
                ),
                "region_code": region["region_code"],
                "region_name": region["region_name"],
                "country_name": region["country_name"],
                "active_flag": True,
                "created_at": generated_at,
                "updated_at": generated_at,
            }
        )

    return records


def generate_distribution_centres(
    configuration: dict[str, Any],
    namespace: uuid.UUID,
    region_id_by_code: dict[str, str],
    generated_at: str,
) -> list[dict[str, Any]]:
    """Generate the distribution-centre master records."""

    records: list[dict[str, Any]] = []

    for centre in configuration["distribution_centres"]:
        region_code = centre["region_code"]

        if region_code not in region_id_by_code:
            raise ValueError(
                f"Distribution centre references unknown region: "
                f"{region_code}"
            )

        centre_code = centre["distribution_centre_code"]

        records.append(
            {
                "distribution_centre_id": deterministic_uuid(
                    namespace,
                    "distribution_centre",
                    centre_code,
                ),
                "distribution_centre_code": centre_code,
                "distribution_centre_name": centre[
                    "distribution_centre_name"
                ],
                "region_id": region_id_by_code[region_code],
                "region_code": region_code,
                "location_area": centre["location_area"],
                "postcode_area": centre["postcode_area"],
                "latitude": centre["latitude"],
                "longitude": centre["longitude"],
                "supports_ambient": centre["supports_ambient"],
                "supports_chilled": centre["supports_chilled"],
                "supports_frozen": centre["supports_frozen"],
                "daily_receiving_capacity_cases": centre[
                    "daily_receiving_capacity_cases"
                ],
                "daily_dispatch_capacity_cases": centre[
                    "daily_dispatch_capacity_cases"
                ],
                "opened_date": centre["opened_date"],
                "active_flag": True,
                "created_at": generated_at,
                "updated_at": generated_at,
            }
        )

    return records


def generate_stores(
    configuration: dict[str, Any],
    namespace: uuid.UUID,
    random_generator: random.Random,
    region_id_by_code: dict[str, str],
    centre_id_by_code: dict[str, str],
    generated_at: str,
) -> list[dict[str, Any]]:
    """Generate exactly 120 logically distributed fictional stores."""

    records: list[dict[str, Any]] = []
    store_formats = build_store_format_sequence(
        configuration,
        random_generator,
    )

    expected_store_count = int(
        configuration["expected_counts"]["stores"]
    )

    if len(store_formats) != expected_store_count:
        raise ValueError(
            "Store-format counts do not equal the expected store count."
        )

    store_sequence = 1
    format_position = 0

    for region in configuration["regions"]:
        region_code = region["region_code"]
        centre_code = region[
            "primary_distribution_centre_code"
        ]

        if region_code not in REGION_CENTRES:
            raise ValueError(
                f"No coordinate reference exists for {region_code}."
            )

        if region_code not in region_id_by_code:
            raise ValueError(
                f"Store region does not exist: {region_code}"
            )

        if centre_code not in centre_id_by_code:
            raise ValueError(
                f"Store distribution centre does not exist: "
                f"{centre_code}"
            )

        centre_latitude, centre_longitude, coordinate_spread = (
            REGION_CENTRES[region_code]
        )

        city_usage: dict[str, int] = {}

        for local_position in range(int(region["store_count"])):
            store_code = f"STR-{store_sequence:04d}"
            store_format = store_formats[format_position]
            format_config = configuration["store_formats"][
                store_format
            ]

            city = region["city_pool"][
                local_position % len(region["city_pool"])
            ]
            postcode_area = region["postcode_area_pool"][
                local_position % len(region["postcode_area_pool"])
            ]

            city_usage[city] = city_usage.get(city, 0) + 1
            city_occurrence = city_usage[city]

            if city_occurrence == 1:
                suffix = "Central"
            else:
                suffix = STORE_NAME_SUFFIXES[
                    (city_occurrence - 1) % len(STORE_NAME_SUFFIXES)
                ]

            store_name = f"BritMart {city} {suffix}"

            floor_area = random_generator.randint(
                int(
                    format_config[
                        "minimum_floor_area_square_metres"
                    ]
                ),
                int(
                    format_config[
                        "maximum_floor_area_square_metres"
                    ]
                ),
            )

            latitude = round(
                centre_latitude
                + random_generator.uniform(
                    -coordinate_spread,
                    coordinate_spread,
                ),
                6,
            )
            longitude = round(
                centre_longitude
                + random_generator.uniform(
                    -coordinate_spread,
                    coordinate_spread,
                ),
                6,
            )

            opening_date = random_date(
                random_generator,
                date(2005, 1, 1),
                date(2024, 12, 31),
            ).isoformat()

            online_collection_flag = (
                random_generator.random()
                < float(
                    format_config[
                        "online_collection_probability"
                    ]
                )
            )
            home_delivery_support_flag = (
                random_generator.random()
                < float(
                    format_config[
                        "home_delivery_probability"
                    ]
                )
            )

            records.append(
                {
                    "store_id": deterministic_uuid(
                        namespace,
                        "store",
                        store_code,
                    ),
                    "store_code": store_code,
                    "store_name": store_name,
                    "region_id": region_id_by_code[region_code],
                    "region_code": region_code,
                    "primary_distribution_centre_id": (
                        centre_id_by_code[centre_code]
                    ),
                    "primary_distribution_centre_code": (
                        centre_code
                    ),
                    "store_format": store_format,
                    "city": city,
                    "postcode_area": postcode_area,
                    "latitude": latitude,
                    "longitude": longitude,
                    "floor_area_square_metres": floor_area,
                    "sales_weight": format_config["sales_weight"],
                    "opening_date": opening_date,
                    "online_collection_flag": (
                        online_collection_flag
                    ),
                    "home_delivery_support_flag": (
                        home_delivery_support_flag
                    ),
                    "active_flag": True,
                    "created_at": generated_at,
                    "updated_at": generated_at,
                }
            )

            store_sequence += 1
            format_position += 1

    if len(records) != expected_store_count:
        raise ValueError(
            f"Generated {len(records)} stores; expected "
            f"{expected_store_count}."
        )

    return records


def write_manifest(
    configuration: dict[str, Any],
    generated_at: str,
    region_count: int,
    distribution_centre_count: int,
    store_count: int,
) -> None:
    """Write an auditable manifest for the generated location files."""

    output_files = [
        REGIONS_OUTPUT_PATH,
        DISTRIBUTION_CENTRES_OUTPUT_PATH,
        STORES_OUTPUT_PATH,
    ]

    manifest = {
        "dataset_name": "BritMart location master data",
        "dataset_version": configuration["project"][
            "dataset_version"
        ],
        "master_seed": configuration["project"]["master_seed"],
        "generated_at": generated_at,
        "record_counts": {
            "regions": region_count,
            "distribution_centres": distribution_centre_count,
            "stores": store_count,
        },
        "files": {
            file_path.name: {
                "sha256": calculate_sha256(file_path),
                "size_bytes": file_path.stat().st_size,
            }
            for file_path in output_files
        },
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
    """Generate the complete BritMart location master dataset."""

    configuration = load_configuration()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    namespace = uuid.UUID(
        configuration["project"]["uuid_namespace"]
    )
    random_generator = random.Random(
        int(configuration["project"]["master_seed"])
    )
    generated_at = str(
        configuration["project"]["generated_timestamp"]
    )

    regions = generate_regions(
        configuration,
        namespace,
        generated_at,
    )

    region_id_by_code = {
        record["region_code"]: record["region_id"]
        for record in regions
    }

    distribution_centres = generate_distribution_centres(
        configuration,
        namespace,
        region_id_by_code,
        generated_at,
    )

    centre_id_by_code = {
        record["distribution_centre_code"]: record[
            "distribution_centre_id"
        ]
        for record in distribution_centres
    }

    stores = generate_stores(
        configuration,
        namespace,
        random_generator,
        region_id_by_code,
        centre_id_by_code,
        generated_at,
    )

    write_csv(
        REGIONS_OUTPUT_PATH,
        regions,
        [
            "region_id",
            "region_code",
            "region_name",
            "country_name",
            "active_flag",
            "created_at",
            "updated_at",
        ],
    )

    write_csv(
        DISTRIBUTION_CENTRES_OUTPUT_PATH,
        distribution_centres,
        [
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
        ],
    )

    write_csv(
        STORES_OUTPUT_PATH,
        stores,
        [
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
        ],
    )

    write_manifest(
        configuration,
        generated_at,
        len(regions),
        len(distribution_centres),
        len(stores),
    )

    print("BritMart location master data generated successfully.")
    print(f"Regions: {len(regions)}")
    print(
        "Distribution centres: "
        f"{len(distribution_centres)}"
    )
    print(f"Stores: {len(stores)}")
    print(f"Output directory: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()