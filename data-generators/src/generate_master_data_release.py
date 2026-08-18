"""Generate the BritMart master-data release manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "output"
)

RELEASE_MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "master_data_release_manifest.json"
)

MASTER_SEED = 20260816

UUID_NAMESPACE = UUID(
    "6f3f2d6a-75b1-5f12-9a76-0de2a31bd8d0"
)

GENERATED_TIMESTAMP = "2026-08-16T00:00:00Z"

DATASET_DEFINITIONS = {
    "regions": {
        "file": "regions.csv",
        "expected_count": 12,
        "business_key": "region_code",
        "technical_key": "region_id",
        "domain": "LOCATION",
    },
    "distribution_centres": {
        "file": "distribution_centres.csv",
        "expected_count": 6,
        "business_key": "distribution_centre_code",
        "technical_key": "distribution_centre_id",
        "domain": "LOCATION",
    },
    "stores": {
        "file": "stores.csv",
        "expected_count": 120,
        "business_key": "store_code",
        "technical_key": "store_id",
        "domain": "LOCATION",
    },
    "categories": {
        "file": "categories.csv",
        "expected_count": 5,
        "business_key": "category_code",
        "technical_key": "category_id",
        "domain": "PRODUCT",
    },
    "subcategories": {
        "file": "subcategories.csv",
        "expected_count": 40,
        "business_key": "subcategory_code",
        "technical_key": "subcategory_id",
        "domain": "PRODUCT",
    },
    "products": {
        "file": "products.csv",
        "expected_count": 2000,
        "business_key": "product_code",
        "technical_key": "product_id",
        "domain": "PRODUCT",
    },
    "suppliers": {
        "file": "suppliers.csv",
        "expected_count": 50,
        "business_key": "supplier_code",
        "technical_key": "supplier_id",
        "domain": "SUPPLIER",
    },
    "supplier_products": {
        "file": "supplier_products.csv",
        "expected_count": 2600,
        "business_key": "supplier_product_code",
        "technical_key": "supplier_product_id",
        "domain": "SUPPLIER_PRODUCT",
    },
}

SOURCE_MANIFESTS = {
    "location_manifest": "location_manifest.json",
    "product_manifest": "product_manifest.json",
    "supplier_manifest": "supplier_manifest.json",
    "supplier_product_manifest": (
        "supplier_product_manifest.json"
    ),
}


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


def load_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    """Load CSV columns and records."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required master-data file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        reader = csv.DictReader(source_file)
        rows = list(reader)
        columns = reader.fieldnames or []

    return columns, rows


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required source manifest does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def validate_timestamp_is_utc(
    timestamp_value: str,
) -> None:
    """Confirm the release timestamp is UTC."""

    timestamp = datetime.fromisoformat(
        timestamp_value.replace(
            "Z",
            "+00:00",
        )
    )

    if timestamp.tzinfo is None:
        raise ValueError(
            "Release timestamp must be timezone-aware."
        )

    utc_timestamp = timestamp.astimezone(
        timezone.utc
    )

    if utc_timestamp.utcoffset().total_seconds() != 0:
        raise ValueError(
            "Release timestamp must be UTC."
        )


def build_dataset_metadata() -> dict[str, Any]:
    """Build metadata for every master-data dataset."""

    dataset_metadata: dict[str, Any] = {}

    for dataset_name, definition in (
        DATASET_DEFINITIONS.items()
    ):
        file_path = (
            OUTPUT_DIRECTORY
            / definition["file"]
        )

        columns, rows = load_csv(file_path)

        actual_count = len(rows)
        expected_count = int(
            definition["expected_count"]
        )

        if actual_count != expected_count:
            raise ValueError(
                f"{dataset_name} contains {actual_count} "
                f"records instead of {expected_count}."
            )

        business_key = definition[
            "business_key"
        ]
        technical_key = definition[
            "technical_key"
        ]

        if business_key not in columns:
            raise ValueError(
                f"{dataset_name} does not contain "
                f"business key {business_key}."
            )

        if technical_key not in columns:
            raise ValueError(
                f"{dataset_name} does not contain "
                f"technical key {technical_key}."
            )

        business_key_values = [
            row[business_key]
            for row in rows
        ]

        technical_key_values = [
            row[technical_key]
            for row in rows
        ]

        if any(
            not value
            for value in business_key_values
        ):
            raise ValueError(
                f"{dataset_name} contains a null "
                f"{business_key}."
            )

        if any(
            not value
            for value in technical_key_values
        ):
            raise ValueError(
                f"{dataset_name} contains a null "
                f"{technical_key}."
            )

        if len(business_key_values) != len(
            set(business_key_values)
        ):
            raise ValueError(
                f"{dataset_name} contains duplicate "
                f"{business_key} values."
            )

        if len(technical_key_values) != len(
            set(technical_key_values)
        ):
            raise ValueError(
                f"{dataset_name} contains duplicate "
                f"{technical_key} values."
            )

        for technical_key_value in (
            technical_key_values
        ):
            UUID(technical_key_value)

        dataset_metadata[dataset_name] = {
            "domain": definition["domain"],
            "file_name": definition["file"],
            "record_count": actual_count,
            "column_count": len(columns),
            "columns": columns,
            "business_key": business_key,
            "technical_key": technical_key,
            "sha256": calculate_sha256(
                file_path
            ),
        }

    return dataset_metadata


def build_source_manifest_metadata() -> dict[str, Any]:
    """Capture hashes and details from source manifests."""

    manifest_metadata: dict[str, Any] = {}

    for manifest_name, file_name in (
        SOURCE_MANIFESTS.items()
    ):
        manifest_path = (
            OUTPUT_DIRECTORY
            / file_name
        )

        manifest_content = load_json(
            manifest_path
        )

        manifest_metadata[manifest_name] = {
            "file_name": file_name,
            "sha256": calculate_sha256(
                manifest_path
            ),
            "record_count": manifest_content.get(
                "record_count"
            ),
            "generated_at": manifest_content.get(
                "generated_at"
            ),
        }

    return manifest_metadata


def build_relationship_metadata() -> list[dict[str, Any]]:
    """Define all required cross-domain relationships."""

    return [
        {
            "relationship_name": (
                "distribution_centre_to_region"
            ),
            "parent_dataset": "regions",
            "parent_key": "region_id",
            "child_dataset": (
                "distribution_centres"
            ),
            "child_key": "region_id",
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "store_to_region"
            ),
            "parent_dataset": "regions",
            "parent_key": "region_id",
            "child_dataset": "stores",
            "child_key": "region_id",
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "store_to_distribution_centre"
            ),
            "parent_dataset": (
                "distribution_centres"
            ),
            "parent_key": (
                "distribution_centre_id"
            ),
            "child_dataset": "stores",
            "child_key": (
                "primary_distribution_centre_id"
            ),
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "subcategory_to_category"
            ),
            "parent_dataset": "categories",
            "parent_key": "category_id",
            "child_dataset": "subcategories",
            "child_key": "category_id",
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "product_to_category"
            ),
            "parent_dataset": "categories",
            "parent_key": "category_id",
            "child_dataset": "products",
            "child_key": "category_id",
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "product_to_subcategory"
            ),
            "parent_dataset": "subcategories",
            "parent_key": "subcategory_id",
            "child_dataset": "products",
            "child_key": "subcategory_id",
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "supplier_product_to_supplier"
            ),
            "parent_dataset": "suppliers",
            "parent_key": "supplier_id",
            "child_dataset": (
                "supplier_products"
            ),
            "child_key": "supplier_id",
            "expected_orphan_count": 0,
        },
        {
            "relationship_name": (
                "supplier_product_to_product"
            ),
            "parent_dataset": "products",
            "parent_key": "product_id",
            "child_dataset": (
                "supplier_products"
            ),
            "child_key": "product_id",
            "expected_orphan_count": 0,
        },
    ]


def generate_release_manifest() -> dict[str, Any]:
    """Generate the complete master-data release manifest."""

    validate_timestamp_is_utc(
        GENERATED_TIMESTAMP
    )

    dataset_metadata = (
        build_dataset_metadata()
    )

    source_manifest_metadata = (
        build_source_manifest_metadata()
    )

    relationships = (
        build_relationship_metadata()
    )

    release_id = uuid5(
        UUID_NAMESPACE,
        (
            "britmart:master-data-release:"
            "1.0.0"
        ),
    )

    total_record_count = sum(
        dataset["record_count"]
        for dataset in dataset_metadata.values()
    )

    return {
        "release_id": str(release_id),
        "release_name": (
            "BritMart Master Data Release 1.0.0"
        ),
        "release_version": "1.0.0",
        "release_status": "READY_FOR_VALIDATION",
        "company_name": "BritMart",
        "master_seed": MASTER_SEED,
        "generated_at": GENERATED_TIMESTAMP,
        "total_dataset_count": len(
            dataset_metadata
        ),
        "total_record_count": (
            total_record_count
        ),
        "datasets": dataset_metadata,
        "source_manifests": (
            source_manifest_metadata
        ),
        "relationships": relationships,
        "downstream_consumers": [
            "Supplier Procurement API",
            "Warehouse Operational Database",
            "Store POS Sales Files",
            "E-commerce Order Source",
            "Microsoft Fabric",
        ],
        "incremental_ordering_standard": {
            "watermark_column": "updated_at",
            "tie_breaker_strategy": (
                "technical primary key"
            ),
            "timestamp_timezone": "UTC",
        },
    }


def write_release_manifest(
    release_manifest: dict[str, Any],
) -> None:
    """Write the master-data release manifest."""

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RELEASE_MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            release_manifest,
            output_file,
            indent=2,
            sort_keys=True,
        )
        output_file.write("\n")


def main() -> None:
    """Execute master-data release generation."""

    release_manifest = (
        generate_release_manifest()
    )

    write_release_manifest(
        release_manifest
    )

    print(
        "BritMart master-data release "
        "manifest generated successfully."
    )
    print(
        "Release ID: "
        f"{release_manifest['release_id']}"
    )
    print(
        "Datasets: "
        f"{release_manifest['total_dataset_count']}"
    )
    print(
        "Total records: "
        f"{release_manifest['total_record_count']}"
    )
    print(
        f"Manifest: {RELEASE_MANIFEST_PATH}"
    )


if __name__ == "__main__":
    main()