"""Validate the complete BritMart master-data release."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


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

VALIDATION_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "master_data_validation_report.json"
)

GENERATED_TIMESTAMP = "2026-08-16T00:00:00Z"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    if not path.exists():
        raise AssertionError(
            f"Required JSON file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def load_csv(
    path: Path,
) -> list[dict[str, str]]:
    """Load a CSV file as dictionaries."""

    if not path.exists():
        raise AssertionError(
            f"Required CSV file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        return list(csv.DictReader(source_file))


def calculate_sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def as_boolean(value: Any) -> bool:
    """Convert common Boolean representations."""

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def validate_release_identity(
    release_manifest: dict[str, Any],
) -> None:
    """Validate release identity and metadata."""

    UUID(release_manifest["release_id"])

    if (
        release_manifest["company_name"]
        != "BritMart"
    ):
        raise AssertionError(
            "Release company name must be BritMart."
        )

    if (
        release_manifest["release_version"]
        != "1.0.0"
    ):
        raise AssertionError(
            "Unexpected master-data release version."
        )

    if (
        release_manifest["release_status"]
        != "READY_FOR_VALIDATION"
    ):
        raise AssertionError(
            "Release must be READY_FOR_VALIDATION."
        )

    timestamp = datetime.fromisoformat(
        release_manifest[
            "generated_at"
        ].replace(
            "Z",
            "+00:00",
        )
    )

    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
        or timestamp.utcoffset().total_seconds()
        != 0
    ):
        raise AssertionError(
            "Release timestamp must be UTC."
        )


def load_release_datasets(
    release_manifest: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    """Load and verify all release datasets."""

    datasets: dict[
        str,
        list[dict[str, str]],
    ] = {}

    for dataset_name, metadata in (
        release_manifest["datasets"].items()
    ):
        dataset_path = (
            OUTPUT_DIRECTORY
            / metadata["file_name"]
        )

        rows = load_csv(dataset_path)

        if len(rows) != int(
            metadata["record_count"]
        ):
            raise AssertionError(
                f"{dataset_name} count differs "
                "from the release manifest."
            )

        if (
            calculate_sha256(dataset_path)
            != metadata["sha256"]
        ):
            raise AssertionError(
                f"{dataset_name} hash differs "
                "from the release manifest."
            )

        datasets[dataset_name] = rows

    return datasets


def validate_dataset_keys(
    release_manifest: dict[str, Any],
    datasets: dict[
        str,
        list[dict[str, str]],
    ],
) -> None:
    """Validate every declared business and technical key."""

    for dataset_name, metadata in (
        release_manifest["datasets"].items()
    ):
        rows = datasets[dataset_name]

        business_key = metadata[
            "business_key"
        ]
        technical_key = metadata[
            "technical_key"
        ]

        business_values = [
            row[business_key]
            for row in rows
        ]

        technical_values = [
            row[technical_key]
            for row in rows
        ]

        if any(
            not value
            for value in business_values
        ):
            raise AssertionError(
                f"{dataset_name} contains an empty "
                f"{business_key}."
            )

        if any(
            not value
            for value in technical_values
        ):
            raise AssertionError(
                f"{dataset_name} contains an empty "
                f"{technical_key}."
            )

        if len(business_values) != len(
            set(business_values)
        ):
            raise AssertionError(
                f"{dataset_name} contains duplicate "
                f"{business_key} values."
            )

        if len(technical_values) != len(
            set(technical_values)
        ):
            raise AssertionError(
                f"{dataset_name} contains duplicate "
                f"{technical_key} values."
            )

        for technical_value in technical_values:
            UUID(technical_value)


def validate_relationships(
    release_manifest: dict[str, Any],
    datasets: dict[
        str,
        list[dict[str, str]],
    ],
) -> list[dict[str, Any]]:
    """Validate all registered parent-child relationships."""

    results = []

    for relationship in release_manifest[
        "relationships"
    ]:
        parent_rows = datasets[
            relationship["parent_dataset"]
        ]
        child_rows = datasets[
            relationship["child_dataset"]
        ]

        parent_key = relationship[
            "parent_key"
        ]
        child_key = relationship[
            "child_key"
        ]

        parent_values = {
            row[parent_key]
            for row in parent_rows
        }

        orphan_values = [
            row[child_key]
            for row in child_rows
            if row[child_key] not in parent_values
        ]

        orphan_count = len(orphan_values)

        if orphan_count != int(
            relationship[
                "expected_orphan_count"
            ]
        ):
            raise AssertionError(
                f"{relationship['relationship_name']} "
                f"contains {orphan_count} orphan records."
            )

        results.append(
            {
                "relationship_name": (
                    relationship[
                        "relationship_name"
                    ]
                ),
                "status": "PASSED",
                "child_record_count": len(
                    child_rows
                ),
                "orphan_count": orphan_count,
            }
        )

    return results


def validate_location_domain(
    datasets: dict[
        str,
        list[dict[str, str]],
    ],
) -> dict[str, Any]:
    """Validate location-domain business rules."""

    regions = datasets["regions"]
    distribution_centres = datasets[
        "distribution_centres"
    ]
    stores = datasets["stores"]

    region_ids = {
        row["region_id"]
        for row in regions
    }

    distribution_centres_by_id = {
        row["distribution_centre_id"]: row
        for row in distribution_centres
    }

    stores_by_distribution_centre = Counter(
        row["primary_distribution_centre_id"]
        for row in stores
    )

    if len(
        stores_by_distribution_centre
    ) != len(distribution_centres):
        raise AssertionError(
            "Every distribution centre must serve "
            "at least one store."
        )

    for distribution_centre in (
        distribution_centres
    ):
        if (
            distribution_centre["region_id"]
            not in region_ids
        ):
            raise AssertionError(
                "A distribution centre references "
                "an unknown region."
            )

    for store in stores:
        if store["region_id"] not in region_ids:
            raise AssertionError(
                f"{store['store_code']} references "
                "an unknown region."
            )

        distribution_centre_id = store[
            "primary_distribution_centre_id"
        ]

        if (
            distribution_centre_id
            not in distribution_centres_by_id
        ):
            raise AssertionError(
                f"{store['store_code']} references an "
                "unknown primary distribution centre."
            )

        distribution_centre = (
            distribution_centres_by_id[
                distribution_centre_id
            ]
        )

        if (
            store[
                "primary_distribution_centre_code"
            ]
            != distribution_centre[
                "distribution_centre_code"
            ]
        ):
            raise AssertionError(
                f"{store['store_code']} has inconsistent "
                "distribution-centre identifiers."
            )

        if Decimal(
            store["floor_area_square_metres"]
        ) <= 0:
            raise AssertionError(
                f"{store['store_code']} has an "
                "invalid floor area."
            )

        if Decimal(
            store["sales_weight"]
        ) <= 0:
            raise AssertionError(
                f"{store['store_code']} has an "
                "invalid sales weight."
            )

    return {
        "status": "PASSED",
        "regions": len(regions),
        "distribution_centres": len(
            distribution_centres
        ),
        "stores": len(stores),
        "active_stores": sum(
            as_boolean(row["active_flag"])
            for row in stores
        ),
        "distribution_centres_with_stores": (
            len(stores_by_distribution_centre)
        ),
    }


def validate_product_domain(
    datasets: dict[
        str,
        list[dict[str, str]],
    ],
) -> dict[str, Any]:
    """Validate product hierarchy and commercial rules."""

    categories = datasets["categories"]
    subcategories = datasets[
        "subcategories"
    ]
    products = datasets["products"]

    categories_by_id = {
        row["category_id"]: row
        for row in categories
    }

    subcategories_by_id = {
        row["subcategory_id"]: row
        for row in subcategories
    }

    subcategory_counts = Counter(
        row["category_id"]
        for row in subcategories
    )

    if len(
        subcategory_counts
    ) != len(categories):
        raise AssertionError(
            "A category has no subcategories."
        )

    if any(
        count != 8
        for count in subcategory_counts.values()
    ):
        raise AssertionError(
            "Every category must have exactly "
            "eight subcategories."
        )

    for subcategory in subcategories:
        if (
            subcategory["category_id"]
            not in categories_by_id
        ):
            raise AssertionError(
                "A subcategory references an "
                "unknown category."
            )

    for product in products:
        if (
            product["category_id"]
            not in categories_by_id
        ):
            raise AssertionError(
                f"{product['product_code']} references "
                "an unknown category."
            )

        if (
            product["subcategory_id"]
            not in subcategories_by_id
        ):
            raise AssertionError(
                f"{product['product_code']} references "
                "an unknown subcategory."
            )

        subcategory = subcategories_by_id[
            product["subcategory_id"]
        ]

        if (
            subcategory["category_id"]
            != product["category_id"]
        ):
            raise AssertionError(
                f"{product['product_code']} has an "
                "inconsistent category hierarchy."
            )

        unit_cost = Decimal(
            product["unit_cost"]
        )

        retail_price = Decimal(
            product["standard_retail_price"]
        )

        if unit_cost <= 0:
            raise AssertionError(
                f"{product['product_code']} has a "
                "non-positive unit cost."
            )

        if retail_price <= unit_cost:
            raise AssertionError(
                f"{product['product_code']} has a "
                "retail price not exceeding cost."
            )

        if Decimal(
            product["case_pack_quantity"]
        ) <= 0:
            raise AssertionError(
                f"{product['product_code']} has an "
                "invalid case-pack quantity."
            )

        if product["storage_type"] not in {
            "AMBIENT",
            "CHILLED",
            "FROZEN",
        }:
            raise AssertionError(
                f"{product['product_code']} has an "
                "invalid storage type."
            )

    return {
        "status": "PASSED",
        "categories": len(categories),
        "subcategories": len(
            subcategories
        ),
        "products": len(products),
        "active_products": sum(
            as_boolean(row["active_flag"])
            for row in products
        ),
    }


def validate_supplier_domain(
    datasets: dict[
        str,
        list[dict[str, str]],
    ],
) -> dict[str, Any]:
    """Validate supplier portfolio rules."""

    suppliers = datasets["suppliers"]

    status_counts = Counter(
        row["supplier_status"]
        for row in suppliers
    )

    risk_counts = Counter(
        row["risk_rating"]
        for row in suppliers
    )

    expected_status_counts = Counter(
        {
            "ACTIVE": 46,
            "SUSPENDED": 2,
            "PENDING": 1,
            "INACTIVE": 1,
        }
    )

    expected_risk_counts = Counter(
        {
            "LOW": 20,
            "MEDIUM": 22,
            "HIGH": 7,
            "CRITICAL": 1,
        }
    )

    if status_counts != expected_status_counts:
        raise AssertionError(
            "Supplier status distribution is incorrect."
        )

    if risk_counts != expected_risk_counts:
        raise AssertionError(
            "Supplier risk distribution is incorrect."
        )

    inactive_suppliers = [
        row
        for row in suppliers
        if row["supplier_status"]
        == "INACTIVE"
    ]

    if len(inactive_suppliers) != 1:
        raise AssertionError(
            "Exactly one supplier must be inactive."
        )

    if (
        inactive_suppliers[0]["risk_rating"]
        != "CRITICAL"
    ):
        raise AssertionError(
            "The inactive supplier must have "
            "CRITICAL risk."
        )

    for supplier in suppliers:
        category_codes = [
            value.strip()
            for value in supplier[
                "category_codes"
            ].split("|")
            if value.strip()
        ]

        if not category_codes:
            raise AssertionError(
                f"{supplier['supplier_code']} has no "
                "category capability."
            )

        if not any(
            as_boolean(
                supplier[column]
            )
            for column in [
                "supports_ambient",
                "supports_chilled",
                "supports_frozen",
            ]
        ):
            raise AssertionError(
                f"{supplier['supplier_code']} supports "
                "no storage type."
            )

        if (
            supplier["supplier_status"]
            == "INACTIVE"
        ):
            if as_boolean(
                supplier["active_flag"]
            ):
                raise AssertionError(
                    "Inactive supplier has "
                    "active_flag=true."
                )
        else:
            if not as_boolean(
                supplier["active_flag"]
            ):
                raise AssertionError(
                    "Operational supplier has "
                    "active_flag=false."
                )

    return {
        "status": "PASSED",
        "suppliers": len(suppliers),
        "supplier_status_counts": dict(
            sorted(status_counts.items())
        ),
        "supplier_risk_counts": dict(
            sorted(risk_counts.items())
        ),
        "countries_represented": len(
            {
                row["country_code"]
                for row in suppliers
            }
        ),
    }


def validate_supplier_product_domain(
    datasets: dict[
        str,
        list[dict[str, str]],
    ],
) -> dict[str, Any]:
    """Validate supplier-product relationships."""

    products = datasets["products"]
    suppliers = datasets["suppliers"]
    agreements = datasets[
        "supplier_products"
    ]

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    agreements_by_product: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    storage_columns = {
        "AMBIENT": "supports_ambient",
        "CHILLED": "supports_chilled",
        "FROZEN": "supports_frozen",
    }

    for agreement in agreements:
        product_id = agreement["product_id"]
        supplier_id = agreement["supplier_id"]

        if product_id not in products_by_id:
            raise AssertionError(
                "An agreement references an "
                "unknown product."
            )

        if supplier_id not in suppliers_by_id:
            raise AssertionError(
                "An agreement references an "
                "unknown supplier."
            )

        product = products_by_id[product_id]
        supplier = suppliers_by_id[
            supplier_id
        ]

        agreements_by_product[
            product_id
        ].append(agreement)

        if supplier["supplier_status"] != "ACTIVE":
            raise AssertionError(
                "A non-active supplier has an "
                "active product agreement."
            )

        if not as_boolean(
            supplier["active_flag"]
        ):
            raise AssertionError(
                "An agreement supplier has "
                "active_flag=false."
            )

        supplier_categories = {
            value.strip()
            for value in supplier[
                "category_codes"
            ].split("|")
            if value.strip()
        }

        if (
            product["category_code"]
            not in supplier_categories
        ):
            raise AssertionError(
                "Supplier-product category mismatch."
            )

        storage_column = storage_columns[
            product["storage_type"]
        ]

        if not as_boolean(
            supplier[storage_column]
        ):
            raise AssertionError(
                "Supplier-product storage mismatch."
            )

        if (
            agreement[
                "agreement_currency_code"
            ]
            != supplier[
                "default_currency_code"
            ]
        ):
            raise AssertionError(
                "Supplier-product currency mismatch."
            )

    products_with_secondary = 0

    for product in products:
        product_agreements = (
            agreements_by_product[
                product["product_id"]
            ]
        )

        primary_agreements = [
            row
            for row in product_agreements
            if row["agreement_role"]
            == "PRIMARY"
        ]

        secondary_agreements = [
            row
            for row in product_agreements
            if row["agreement_role"]
            == "SECONDARY"
        ]

        if len(primary_agreements) != 1:
            raise AssertionError(
                f"{product['product_code']} does not "
                "have exactly one primary supplier."
            )

        if len(secondary_agreements) > 1:
            raise AssertionError(
                f"{product['product_code']} has more "
                "than one secondary supplier."
            )

        if secondary_agreements:
            products_with_secondary += 1

            if (
                primary_agreements[0][
                    "supplier_id"
                ]
                == secondary_agreements[0][
                    "supplier_id"
                ]
            ):
                raise AssertionError(
                    "Primary and secondary suppliers "
                    "cannot be the same."
                )

    primary_count = sum(
        row["agreement_role"] == "PRIMARY"
        for row in agreements
    )

    secondary_count = sum(
        row["agreement_role"]
        == "SECONDARY"
        for row in agreements
    )

    if primary_count != 2000:
        raise AssertionError(
            "Primary agreement count must equal 2000."
        )

    if secondary_count != 600:
        raise AssertionError(
            "Secondary agreement count must equal 600."
        )

    if products_with_secondary != 600:
        raise AssertionError(
            "Exactly 600 products must have "
            "secondary suppliers."
        )

    return {
        "status": "PASSED",
        "agreements": len(agreements),
        "primary_agreements": primary_count,
        "secondary_agreements": (
            secondary_count
        ),
        "products_with_primary_supplier": (
            len(products)
        ),
        "products_with_secondary_supplier": (
            products_with_secondary
        ),
    }


def validate_source_manifests(
    release_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Validate source-manifest integrity."""

    validated_manifests = []

    for manifest_name, metadata in (
        release_manifest[
            "source_manifests"
        ].items()
    ):
        manifest_path = (
            OUTPUT_DIRECTORY
            / metadata["file_name"]
        )

        if (
            calculate_sha256(manifest_path)
            != metadata["sha256"]
        ):
            raise AssertionError(
                f"{manifest_name} hash mismatch."
            )

        validated_manifests.append(
            manifest_name
        )

    return {
        "status": "PASSED",
        "validated_manifest_count": len(
            validated_manifests
        ),
        "validated_manifests": sorted(
            validated_manifests
        ),
    }


def write_validation_report(
    release_manifest: dict[str, Any],
    relationship_results: list[
        dict[str, Any]
    ],
    domain_results: dict[str, Any],
    source_manifest_result: dict[str, Any],
) -> dict[str, Any]:
    """Write a deterministic validation report."""

    validation_report = {
        "release_id": release_manifest[
            "release_id"
        ],
        "release_version": release_manifest[
            "release_version"
        ],
        "validation_status": "PASSED",
        "validated_at": GENERATED_TIMESTAMP,
        "dataset_count": release_manifest[
            "total_dataset_count"
        ],
        "total_record_count": (
            release_manifest[
                "total_record_count"
            ]
        ),
        "relationship_check_count": len(
            relationship_results
        ),
        "relationship_results": (
            relationship_results
        ),
        "domain_results": domain_results,
        "source_manifest_result": (
            source_manifest_result
        ),
        "release_manifest_sha256": (
            calculate_sha256(
                RELEASE_MANIFEST_PATH
            )
        ),
        "approved_for_downstream_generation": (
            True
        ),
    }

    with VALIDATION_REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            validation_report,
            output_file,
            indent=2,
            sort_keys=True,
        )
        output_file.write("\n")

    return validation_report


def run_all_validations() -> dict[str, Any]:
    """Run the complete cross-domain validation gate."""

    release_manifest = load_json(
        RELEASE_MANIFEST_PATH
    )

    validate_release_identity(
        release_manifest
    )

    datasets = load_release_datasets(
        release_manifest
    )

    validate_dataset_keys(
        release_manifest,
        datasets,
    )

    relationship_results = (
        validate_relationships(
            release_manifest,
            datasets,
        )
    )

    domain_results = {
        "location": validate_location_domain(
            datasets
        ),
        "product": validate_product_domain(
            datasets
        ),
        "supplier": validate_supplier_domain(
            datasets
        ),
        "supplier_product": (
            validate_supplier_product_domain(
                datasets
            )
        ),
    }

    source_manifest_result = (
        validate_source_manifests(
            release_manifest
        )
    )

    return write_validation_report(
        release_manifest,
        relationship_results,
        domain_results,
        source_manifest_result,
    )


def main() -> None:
    """Execute master-data validation."""

    validation_report = (
        run_all_validations()
    )

    print(
        "BritMart master-data validation passed."
    )
    print(
        "Release ID: "
        f"{validation_report['release_id']}"
    )
    print(
        "Datasets validated: "
        f"{validation_report['dataset_count']}"
    )
    print(
        "Records validated: "
        f"{validation_report['total_record_count']}"
    )
    print(
        "Relationships validated: "
        f"{validation_report['relationship_check_count']}"
    )
    print(
        "Approved for downstream generation: True"
    )


if __name__ == "__main__":
    main()