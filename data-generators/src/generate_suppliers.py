"""Generate deterministic BritMart supplier master data."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    PROJECT_ROOT
    / "data-generators"
    / "config"
    / "supplier_config.json"
)
OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "output"
)

SUPPLIER_OUTPUT_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
MANIFEST_OUTPUT_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_manifest.json"
)

DEFAULT_SEED = 20260816
DEFAULT_NAMESPACE = (
    "6f3f2d6a-75b1-5f12-9a76-0de2a31bd8d0"
)
DEFAULT_GENERATED_TIMESTAMP = "2026-08-16T00:00:00Z"

SUPPLIER_FIELDS = [
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
]


def load_config() -> dict[str, Any]:
    """Load the supplier generator configuration."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Supplier configuration not found: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as config_file:
        return json.load(config_file)


def validate_config(config: dict[str, Any]) -> None:
    """Validate essential supplier configuration sections."""

    required_sections = {
        "project",
        "expected_counts",
        "origin_group_distribution",
        "supplier_status_distribution",
        "risk_rating_distribution",
        "countries",
        "supplier_types",
        "company_suffixes",
        "performance_targets",
        "commercial_rules",
    }

    missing_sections = required_sections - set(config)

    if missing_sections:
        raise ValueError(
            "Supplier configuration is missing sections: "
            f"{sorted(missing_sections)}"
        )

    expected_count = int(
        config["expected_counts"]["suppliers"]
    )

    configured_type_count = sum(
        int(supplier_type["count"])
        for supplier_type in config["supplier_types"]
    )

    if configured_type_count != expected_count:
        raise ValueError(
            "Supplier-type counts produce "
            f"{configured_type_count} records instead of "
            f"{expected_count}."
        )

    for distribution_name in [
        "origin_group_distribution",
        "supplier_status_distribution",
        "risk_rating_distribution",
    ]:
        distribution_total = sum(
            Decimal(str(value))
            for value in config[distribution_name].values()
        )

        if distribution_total != Decimal("1"):
            raise ValueError(
                f"{distribution_name} must total 1.0; "
                f"actual total is {distribution_total}."
            )

    for supplier_type in config["supplier_types"]:
        count = int(supplier_type["count"])
        names = supplier_type.get("name_terms", [])

        if len(names) != count:
            raise ValueError(
                f"{supplier_type['supplier_type']} requires "
                f"{count} unique name terms but contains "
                f"{len(names)}."
            )

        if not supplier_type.get("category_codes"):
            raise ValueError(
                f"{supplier_type['supplier_type']} has no "
                "category capability."
            )

        if not any(
            [
                supplier_type.get("supports_ambient", False),
                supplier_type.get("supports_chilled", False),
                supplier_type.get("supports_frozen", False),
            ]
        ):
            raise ValueError(
                f"{supplier_type['supplier_type']} supports "
                "no storage type."
            )


def expand_distribution(
    distribution: dict[str, Any],
    expected_count: int,
) -> list[str]:
    """Convert configured proportions into exact record counts."""

    calculated_counts: dict[str, int] = {}
    distribution_items = list(distribution.items())
    allocated_count = 0

    for label, proportion in distribution_items[:-1]:
        count = int(
            (
                Decimal(str(proportion))
                * Decimal(expected_count)
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        calculated_counts[label] = count
        allocated_count += count

    final_label = distribution_items[-1][0]
    calculated_counts[final_label] = (
        expected_count - allocated_count
    )

    expanded_values = [
        label
        for label, count in calculated_counts.items()
        for _ in range(count)
    ]

    if len(expanded_values) != expected_count:
        raise ValueError(
            "Distribution expansion produced "
            f"{len(expanded_values)} values instead of "
            f"{expected_count}."
        )

    return expanded_values


def build_supplier_assignments(
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one assignment for every configured supplier."""

    assignments: list[dict[str, Any]] = []

    for type_config in config["supplier_types"]:
        supplier_type = type_config["supplier_type"]
        supplier_count = int(type_config["count"])

        for index in range(supplier_count):
            assignments.append(
                {
                    "supplier_type": supplier_type,
                    "supplier_name": type_config[
                        "name_terms"
                    ][index],
                    "category_codes": type_config[
                        "category_codes"
                    ],
                    "supports_ambient": bool(
                        type_config["supports_ambient"]
                    ),
                    "supports_chilled": bool(
                        type_config["supports_chilled"]
                    ),
                    "supports_frozen": bool(
                        type_config["supports_frozen"]
                    ),
                    "minimum_order_range": type_config[
                        "minimum_order_value"
                    ],
                }
            )

    return assignments


def assign_statuses_by_risk(
    risk_ratings: list[str],
    status_values: list[str],
) -> list[str]:
    """
    Assign non-active statuses to higher-risk suppliers.

    Exact configured status and risk totals are preserved.
    """

    risk_priority = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
    }

    status_priority = {
        "INACTIVE": 0,
        "SUSPENDED": 1,
        "PENDING": 2,
        "ACTIVE": 3,
    }

    supplier_indexes_by_risk = sorted(
        range(len(risk_ratings)),
        key=lambda index: (
            risk_priority[risk_ratings[index]],
            index,
        ),
    )

    ordered_statuses = sorted(
        status_values,
        key=lambda status: status_priority[status],
    )

    assigned_statuses = ["ACTIVE"] * len(risk_ratings)

    for supplier_index, status in zip(
        supplier_indexes_by_risk,
        ordered_statuses,
    ):
        assigned_statuses[supplier_index] = status

    return assigned_statuses


def choose_country(
    origin_group: str,
    countries: dict[str, list[dict[str, Any]]],
    random_generator: random.Random,
) -> dict[str, Any]:
    """Choose a configured country for an origin group."""

    country_options = countries.get(origin_group)

    if not country_options:
        raise ValueError(
            f"No countries configured for {origin_group}."
        )

    return random_generator.choice(country_options)


def random_decimal(
    minimum: Any,
    maximum: Any,
    decimal_places: int,
    random_generator: random.Random,
) -> Decimal:
    """Create a deterministic decimal within a range."""

    multiplier = 10**decimal_places

    minimum_integer = int(
        Decimal(str(minimum)) * multiplier
    )
    maximum_integer = int(
        Decimal(str(maximum)) * multiplier
    )

    selected_integer = random_generator.randint(
        minimum_integer,
        maximum_integer,
    )

    value = (
        Decimal(selected_integer)
        / Decimal(multiplier)
    )

    quantizer = Decimal("1").scaleb(-decimal_places)

    return value.quantize(quantizer)


def boolean_text(value: bool) -> str:
    """Convert a Boolean into consistent CSV text."""

    return "true" if value else "false"


def slugify(value: str) -> str:
    """Convert a supplier name into an email-safe value."""

    slug = re.sub(
        r"[^a-z0-9]+",
        ".",
        value.lower(),
    ).strip(".")

    return slug or "supplier"


def generate_suppliers(
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate the complete supplier master dataset."""

    validate_config(config)

    project_config = config["project"]
    commercial_rules = config["commercial_rules"]
    performance_targets = config[
        "performance_targets"
    ]

    expected_count = int(
        config["expected_counts"]["suppliers"]
    )
    seed = int(
        project_config.get(
            "master_seed",
            DEFAULT_SEED,
        )
    )
    namespace_uuid = UUID(
        project_config.get(
            "uuid_namespace",
            DEFAULT_NAMESPACE,
        )
    )
    generated_timestamp = project_config.get(
        "generated_timestamp",
        DEFAULT_GENERATED_TIMESTAMP,
    )

    random_generator = random.Random(seed)

    assignments = build_supplier_assignments(config)
    random_generator.shuffle(assignments)

    origin_groups = expand_distribution(
        config["origin_group_distribution"],
        expected_count,
    )
    risk_ratings = expand_distribution(
        config["risk_rating_distribution"],
        expected_count,
    )
    status_values = expand_distribution(
        config["supplier_status_distribution"],
        expected_count,
    )

    random_generator.shuffle(origin_groups)
    random_generator.shuffle(risk_ratings)

    supplier_statuses = assign_statuses_by_risk(
        risk_ratings,
        status_values,
    )

    otif_config = performance_targets["otif_rate"]
    quality_config = performance_targets[
        "quality_acceptance_rate"
    ]

    payment_terms = commercial_rules[
        "payment_terms_options_days"
    ]
    domestic_incoterms = commercial_rules[
        "domestic_incoterms"
    ]
    international_incoterms = commercial_rules[
        "international_incoterms"
    ]
    effective_from = commercial_rules[
        "effective_from"
    ]

    supplier_rows: list[dict[str, Any]] = []

    for index, assignment in enumerate(
        assignments,
        start=1,
    ):
        supplier_code = f"SUP-{index:04d}"
        supplier_name = assignment["supplier_name"]

        origin_group = origin_groups[index - 1]
        risk_rating = risk_ratings[index - 1]
        supplier_status = supplier_statuses[index - 1]

        country = choose_country(
            origin_group,
            config["countries"],
            random_generator,
        )

        lead_time_days = random_generator.randint(
            int(country["lead_time_minimum_days"]),
            int(country["lead_time_maximum_days"]),
        )

        order_range = assignment[
            "minimum_order_range"
        ]

        minimum_order_value = random_decimal(
            order_range["minimum"],
            order_range["maximum"],
            2,
            random_generator,
        )

        target_otif_rate = random_decimal(
            otif_config["minimum"],
            otif_config["maximum"],
            4,
            random_generator,
        )

        target_quality_rate = random_decimal(
            quality_config["minimum"],
            quality_config["maximum"],
            4,
            random_generator,
        )

        company_suffix = random_generator.choice(
            config["company_suffixes"]
        )

        legal_name = (
            f"{supplier_name} {company_suffix}"
        )

        if origin_group == "GB":
            incoterm = random_generator.choice(
                domestic_incoterms
            )
        else:
            incoterm = random_generator.choice(
                international_incoterms
            )

        supplier_id = uuid5(
            namespace_uuid,
            f"britmart:supplier:{supplier_code}",
        )

        supplier_rows.append(
            {
                "supplier_id": str(supplier_id),
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "legal_name": legal_name,
                "supplier_type": assignment[
                    "supplier_type"
                ],
                "category_codes": "|".join(
                    assignment["category_codes"]
                ),
                "country_code": country[
                    "country_code"
                ],
                "origin_group": origin_group,
                "default_currency_code": country[
                    "currency_code"
                ],
                "standard_lead_time_days": (
                    lead_time_days
                ),
                "minimum_order_value": format(
                    minimum_order_value,
                    ".2f",
                ),
                "supports_ambient": boolean_text(
                    assignment[
                        "supports_ambient"
                    ]
                ),
                "supports_chilled": boolean_text(
                    assignment[
                        "supports_chilled"
                    ]
                ),
                "supports_frozen": boolean_text(
                    assignment[
                        "supports_frozen"
                    ]
                ),
                "risk_rating": risk_rating,
                "supplier_status": supplier_status,
                "active_flag": boolean_text(
                    supplier_status != "INACTIVE"
                ),
                "payment_terms_days": (
                    random_generator.choice(
                        payment_terms
                    )
                ),
                "incoterm": incoterm,
                "target_otif_rate": format(
                    target_otif_rate,
                    ".4f",
                ),
                "target_quality_acceptance_rate": (
                    format(
                        target_quality_rate,
                        ".4f",
                    )
                ),
                "contact_email": (
                    "procurement."
                    f"{slugify(supplier_name)}"
                    "@supplier.britmart.example"
                ),
                "effective_from": effective_from,
                "effective_to": "",
                "created_at": generated_timestamp,
                "updated_at": generated_timestamp,
                "version_number": 1,
            }
        )

    return supplier_rows


def write_supplier_csv(
    supplier_rows: list[dict[str, Any]],
) -> None:
    """Write supplier data with a stable schema."""

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SUPPLIER_OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=SUPPLIER_FIELDS,
        )
        writer.writeheader()
        writer.writerows(supplier_rows)


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


def write_manifest(
    supplier_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    """Write supplier dataset metadata and integrity details."""

    status_counts = Counter(
        row["supplier_status"]
        for row in supplier_rows
    )
    risk_counts = Counter(
        row["risk_rating"]
        for row in supplier_rows
    )
    origin_counts = Counter(
        row["origin_group"]
        for row in supplier_rows
    )
    supplier_type_counts = Counter(
        row["supplier_type"]
        for row in supplier_rows
    )

    manifest = {
        "dataset_name": (
            "britmart_supplier_master"
        ),
        "dataset_version": config[
            "project"
        ].get(
            "dataset_version",
            "1.0.0",
        ),
        "schema_version": "1.0.0",
        "generated_at": config[
            "project"
        ].get(
            "generated_timestamp",
            DEFAULT_GENERATED_TIMESTAMP,
        ),
        "record_count": len(supplier_rows),
        "output_file": (
            SUPPLIER_OUTPUT_PATH.name
        ),
        "output_sha256": calculate_sha256(
            SUPPLIER_OUTPUT_PATH
        ),
        "status_counts": dict(
            sorted(status_counts.items())
        ),
        "risk_counts": dict(
            sorted(risk_counts.items())
        ),
        "origin_counts": dict(
            sorted(origin_counts.items())
        ),
        "supplier_type_counts": dict(
            sorted(supplier_type_counts.items())
        ),
        "business_key": "supplier_code",
        "technical_key": "supplier_id",
        "incremental_columns": [
            "updated_at",
            "supplier_id",
        ],
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
    """Execute supplier master-data generation."""

    config = load_config()
    supplier_rows = generate_suppliers(config)

    write_supplier_csv(supplier_rows)
    write_manifest(supplier_rows, config)

    print(
        "BritMart supplier master data "
        "generated successfully."
    )
    print(f"Suppliers: {len(supplier_rows)}")
    print(
        f"Output directory: {OUTPUT_DIRECTORY}"
    )


if __name__ == "__main__":
    main()