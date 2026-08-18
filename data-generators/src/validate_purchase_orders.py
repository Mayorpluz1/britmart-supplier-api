"""Validate BritMart purchase orders and purchase-order lines."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = (
    PROJECT_ROOT
    / "data-generators"
    / "config"
    / "purchase_order_config.json"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "output"
)

PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"

SUPPLIER_PRODUCT_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_products.csv"
)

DISTRIBUTION_CENTRE_PATH = (
    OUTPUT_DIRECTORY
    / "distribution_centres.csv"
)

MASTER_VALIDATION_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "master_data_validation_report.json"
)

PURCHASE_ORDER_PATH = (
    OUTPUT_DIRECTORY
    / "purchase_orders.csv"
)

PURCHASE_ORDER_LINE_PATH = (
    OUTPUT_DIRECTORY
    / "purchase_order_lines.csv"
)

MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "purchase_order_manifest.json"
)

PURCHASE_ORDER_REQUIRED_COLUMNS = {
    "purchase_order_id",
    "purchase_order_number",
    "supplier_id",
    "supplier_code",
    "distribution_centre_id",
    "distribution_centre_code",
    "order_date",
    "required_delivery_date",
    "order_type",
    "purchase_order_status",
    "currency_code",
    "total_net_amount",
    "total_vat_amount",
    "total_gross_amount",
    "total_value_gbp",
    "buyer_code",
    "approval_role",
    "approved_at",
    "cancellation_reason",
    "created_by",
    "updated_by",
    "created_at",
    "updated_at",
    "version_number",
}

PURCHASE_ORDER_LINE_REQUIRED_COLUMNS = {
    "purchase_order_line_id",
    "purchase_order_id",
    "purchase_order_number",
    "line_number",
    "supplier_product_id",
    "product_id",
    "product_code",
    "sku",
    "ordered_quantity",
    "unit_of_measure",
    "order_multiple",
    "unit_price",
    "currency_code",
    "net_amount",
    "vat_rate",
    "vat_amount",
    "gross_amount",
    "created_at",
    "updated_at",
    "version_number",
}


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
    """Calculate a SHA-256 file digest."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp."""

    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def validate_required_columns(
    purchase_orders: list[dict[str, str]],
    purchase_order_lines: list[
        dict[str, str]
    ],
) -> None:
    """Confirm both output schemas."""

    if not purchase_orders:
        raise AssertionError(
            "purchase_orders.csv is empty."
        )

    if not purchase_order_lines:
        raise AssertionError(
            "purchase_order_lines.csv is empty."
        )

    missing_order_columns = (
        PURCHASE_ORDER_REQUIRED_COLUMNS
        - set(purchase_orders[0])
    )

    missing_line_columns = (
        PURCHASE_ORDER_LINE_REQUIRED_COLUMNS
        - set(purchase_order_lines[0])
    )

    if missing_order_columns:
        raise AssertionError(
            "Purchase-order columns are missing: "
            f"{sorted(missing_order_columns)}"
        )

    if missing_line_columns:
        raise AssertionError(
            "Purchase-order-line columns are missing: "
            f"{sorted(missing_line_columns)}"
        )


def validate_record_counts(
    purchase_orders: list[dict[str, str]],
    purchase_order_lines: list[
        dict[str, str]
    ],
    config: dict[str, Any],
) -> None:
    """Confirm configured transaction counts."""

    expected = config["expected_counts"]

    if len(purchase_orders) != int(
        expected["purchase_orders"]
    ):
        raise AssertionError(
            "Purchase-order count is incorrect."
        )

    if len(purchase_order_lines) != int(
        expected["purchase_order_lines"]
    ):
        raise AssertionError(
            "Purchase-order-line count is incorrect."
        )

    actual_average = (
        Decimal(
            len(purchase_order_lines)
        )
        / Decimal(
            len(purchase_orders)
        )
    )

    if actual_average != Decimal(
        str(
            expected[
                "average_lines_per_order"
            ]
        )
    ):
        raise AssertionError(
            "Average lines per purchase order "
            "is incorrect."
        )


def validate_unique_keys(
    purchase_orders: list[dict[str, str]],
    purchase_order_lines: list[
        dict[str, str]
    ],
) -> None:
    """Confirm technical and business key uniqueness."""

    order_ids = [
        row["purchase_order_id"]
        for row in purchase_orders
    ]

    order_numbers = [
        row["purchase_order_number"]
        for row in purchase_orders
    ]

    line_ids = [
        row["purchase_order_line_id"]
        for row in purchase_order_lines
    ]

    line_business_keys = [
        (
            row["purchase_order_id"],
            row["line_number"],
        )
        for row in purchase_order_lines
    ]

    if len(order_ids) != len(
        set(order_ids)
    ):
        raise AssertionError(
            "Duplicate purchase_order_id detected."
        )

    if len(order_numbers) != len(
        set(order_numbers)
    ):
        raise AssertionError(
            "Duplicate purchase_order_number detected."
        )

    if len(line_ids) != len(
        set(line_ids)
    ):
        raise AssertionError(
            "Duplicate purchase_order_line_id detected."
        )

    if len(line_business_keys) != len(
        set(line_business_keys)
    ):
        raise AssertionError(
            "Duplicate purchase-order line number detected."
        )

    for identifier in (
        order_ids + line_ids
    ):
        UUID(identifier)


def validate_master_data_approval() -> None:
    """Confirm master data was approved before generation."""

    report = load_json(
        MASTER_VALIDATION_REPORT_PATH
    )

    if report["validation_status"] != "PASSED":
        raise AssertionError(
            "Master-data validation did not pass."
        )

    if (
        report[
            "approved_for_downstream_generation"
        ]
        is not True
    ):
        raise AssertionError(
            "Master data is not approved for "
            "downstream generation."
        )


def validate_header_references(
    purchase_orders: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    distribution_centres: list[
        dict[str, str]
    ],
) -> None:
    """Validate supplier and destination references."""

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    centres_by_id = {
        row["distribution_centre_id"]: row
        for row in distribution_centres
    }

    for order in purchase_orders:
        supplier_id = order["supplier_id"]
        centre_id = order[
            "distribution_centre_id"
        ]

        if supplier_id not in suppliers_by_id:
            raise AssertionError(
                "Purchase order references an "
                "unknown supplier."
            )

        if centre_id not in centres_by_id:
            raise AssertionError(
                "Purchase order references an unknown "
                "distribution centre."
            )

        supplier = suppliers_by_id[
            supplier_id
        ]

        centre = centres_by_id[
            centre_id
        ]

        if (
            order["supplier_code"]
            != supplier["supplier_code"]
        ):
            raise AssertionError(
                "Purchase-order supplier identifiers "
                "do not match."
            )

        if (
            supplier["supplier_status"]
            != "ACTIVE"
        ):
            raise AssertionError(
                "A purchase order references a "
                "non-active supplier."
            )

        if (
            order["currency_code"]
            != supplier[
                "default_currency_code"
            ]
        ):
            raise AssertionError(
                "Purchase-order currency does not "
                "match supplier currency."
            )

        if (
            order[
                "distribution_centre_code"
            ]
            != centre[
                "distribution_centre_code"
            ]
        ):
            raise AssertionError(
                "Distribution-centre identifiers "
                "do not match."
            )


def validate_line_references(
    purchase_orders: list[dict[str, str]],
    purchase_order_lines: list[
        dict[str, str]
    ],
    products: list[dict[str, str]],
    agreements: list[dict[str, str]],
) -> None:
    """Validate line references and parent consistency."""

    orders_by_id = {
        row["purchase_order_id"]: row
        for row in purchase_orders
    }

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    agreements_by_id = {
        row["supplier_product_id"]: row
        for row in agreements
    }

    for line in purchase_order_lines:
        order_id = line[
            "purchase_order_id"
        ]
        product_id = line["product_id"]
        agreement_id = line[
            "supplier_product_id"
        ]

        if order_id not in orders_by_id:
            raise AssertionError(
                "Purchase-order line references "
                "an unknown purchase order."
            )

        if product_id not in products_by_id:
            raise AssertionError(
                "Purchase-order line references "
                "an unknown product."
            )

        if agreement_id not in agreements_by_id:
            raise AssertionError(
                "Purchase-order line references "
                "an unknown supplier agreement."
            )

        order = orders_by_id[order_id]
        product = products_by_id[
            product_id
        ]
        agreement = agreements_by_id[
            agreement_id
        ]

        if (
            line["purchase_order_number"]
            != order["purchase_order_number"]
        ):
            raise AssertionError(
                "Line purchase-order number does "
                "not match its parent."
            )

        if (
            line["product_code"]
            != product["product_code"]
        ):
            raise AssertionError(
                "Line product code does not match "
                "its product identifier."
            )

        if line["sku"] != product["sku"]:
            raise AssertionError(
                "Line SKU does not match product."
            )

        if (
            agreement["product_id"]
            != product_id
        ):
            raise AssertionError(
                "Supplier agreement references a "
                "different product."
            )

        if (
            agreement["supplier_id"]
            != order["supplier_id"]
        ):
            raise AssertionError(
                "Supplier agreement does not belong "
                "to the order supplier."
            )

        if (
            line["currency_code"]
            != order["currency_code"]
        ):
            raise AssertionError(
                "Line currency differs from "
                "purchase-order currency."
            )


def validate_line_counts_and_products(
    purchase_orders: list[dict[str, str]],
    purchase_order_lines: list[
        dict[str, str]
    ],
    config: dict[str, Any],
) -> None:
    """Validate line ranges, numbering and unique products."""

    lines_by_order: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for line in purchase_order_lines:
        lines_by_order[
            line["purchase_order_id"]
        ].append(line)

    minimum_lines = int(
        config["expected_counts"][
            "minimum_lines_per_order"
        ]
    )

    maximum_lines = int(
        config["expected_counts"][
            "maximum_lines_per_order"
        ]
    )

    for order in purchase_orders:
        order_lines = lines_by_order[
            order["purchase_order_id"]
        ]

        if not (
            minimum_lines
            <= len(order_lines)
            <= maximum_lines
        ):
            raise AssertionError(
                "Purchase-order line count is outside "
                "the configured range."
            )

        actual_line_numbers = {
            int(line["line_number"])
            for line in order_lines
        }

        expected_line_numbers = set(
            range(
                1,
                len(order_lines) + 1,
            )
        )

        if (
            actual_line_numbers
            != expected_line_numbers
        ):
            raise AssertionError(
                "Purchase-order line numbers are "
                "not sequential."
            )

        product_ids = [
            line["product_id"]
            for line in order_lines
        ]

        if len(product_ids) != len(
            set(product_ids)
        ):
            raise AssertionError(
                "A purchase order contains a "
                "duplicate product."
            )


def validate_line_commercial_values(
    purchase_order_lines: list[
        dict[str, str]
    ],
    products: list[dict[str, str]],
    agreements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Validate quantities, prices, VAT and amounts."""

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    agreements_by_id = {
        row["supplier_product_id"]: row
        for row in agreements
    }

    variance_config = config[
        "line_allocation"
    ]["price_variance_rate"]

    minimum_variance = Decimal(
        str(variance_config["minimum"])
    )

    maximum_variance = Decimal(
        str(variance_config["maximum"])
    )

    for line in purchase_order_lines:
        product = products_by_id[
            line["product_id"]
        ]

        agreement = agreements_by_id[
            line["supplier_product_id"]
        ]

        ordered_quantity = Decimal(
            line["ordered_quantity"]
        )

        order_multiple = Decimal(
            line["order_multiple"]
        )

        unit_price = Decimal(
            line["unit_price"]
        )

        net_amount = Decimal(
            line["net_amount"]
        )

        vat_rate = Decimal(
            line["vat_rate"]
        )

        vat_amount = Decimal(
            line["vat_amount"]
        )

        gross_amount = Decimal(
            line["gross_amount"]
        )

        minimum_order_quantity = Decimal(
            agreement[
                "minimum_order_quantity"
            ]
        )

        agreement_order_multiple = Decimal(
            agreement["order_multiple"]
        )

        agreement_price = Decimal(
            agreement["agreed_unit_cost"]
        )

        if ordered_quantity <= 0:
            raise AssertionError(
                "Ordered quantity must be positive."
            )

        if (
            ordered_quantity
            < minimum_order_quantity
        ):
            raise AssertionError(
                "Ordered quantity is below the "
                "supplier minimum."
            )

        if (
            order_multiple
            != agreement_order_multiple
        ):
            raise AssertionError(
                "Order multiple differs from agreement."
            )

        if (
            ordered_quantity
            % order_multiple
            != 0
        ):
            raise AssertionError(
                "Ordered quantity is not an "
                "order-multiple value."
            )

        minimum_price = (
            agreement_price
            * (
                Decimal("1")
                + minimum_variance
            )
        )

        maximum_price = (
            agreement_price
            * (
                Decimal("1")
                + maximum_variance
            )
        )

        tolerance = Decimal("0.0001")

        if not (
            minimum_price - tolerance
            <= unit_price
            <= maximum_price + tolerance
        ):
            raise AssertionError(
                "Line unit price is outside the "
                "configured variance."
            )

        expected_net = (
            ordered_quantity
            * unit_price
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if net_amount != expected_net:
            raise AssertionError(
                "Line net amount is incorrect."
            )

        expected_vat_rate = Decimal(
            product["vat_rate"]
        ).quantize(
            Decimal("0.000001")
        )

        if vat_rate != expected_vat_rate:
            raise AssertionError(
                "Line VAT rate differs from product."
            )

        expected_vat = (
            net_amount * vat_rate
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if vat_amount != expected_vat:
            raise AssertionError(
                "Line VAT amount is incorrect."
            )

        if (
            gross_amount
            != net_amount + vat_amount
        ):
            raise AssertionError(
                "Line gross amount is incorrect."
            )


def validate_header_totals(
    purchase_orders: list[dict[str, str]],
    purchase_order_lines: list[
        dict[str, str]
    ],
    agreements: list[dict[str, str]],
) -> None:
    """Reconcile line amounts to header totals."""

    lines_by_order: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    agreements_by_id = {
        row["supplier_product_id"]: row
        for row in agreements
    }

    for line in purchase_order_lines:
        lines_by_order[
            line["purchase_order_id"]
        ].append(line)

    for order in purchase_orders:
        order_lines = lines_by_order[
            order["purchase_order_id"]
        ]

        expected_net = sum(
            Decimal(line["net_amount"])
            for line in order_lines
        )

        expected_vat = sum(
            Decimal(line["vat_amount"])
            for line in order_lines
        )

        expected_gross = sum(
            Decimal(line["gross_amount"])
            for line in order_lines
        )

        if (
            Decimal(
                order["total_net_amount"]
            )
            != expected_net
        ):
            raise AssertionError(
                "Purchase-order net total does "
                "not reconcile to lines."
            )

        if (
            Decimal(
                order["total_vat_amount"]
            )
            != expected_vat
        ):
            raise AssertionError(
                "Purchase-order VAT total does "
                "not reconcile to lines."
            )

        if (
            Decimal(
                order["total_gross_amount"]
            )
            != expected_gross
        ):
            raise AssertionError(
                "Purchase-order gross total does "
                "not reconcile to lines."
            )

        first_agreement = agreements_by_id[
            order_lines[0][
                "supplier_product_id"
            ]
        ]

        rate = Decimal(
            first_agreement[
                "gbp_value_per_currency_unit"
            ]
        )

        expected_gbp = (
            expected_gross * rate
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if (
            Decimal(
                order["total_value_gbp"]
            )
            != expected_gbp
        ):
            raise AssertionError(
                "Purchase-order GBP value is incorrect."
            )


def validate_status_distribution(
    purchase_orders: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Confirm the exact status scenario."""

    actual_counts = Counter(
        row["purchase_order_status"]
        for row in purchase_orders
    )

    expected_counts = Counter(
        {
            status: int(count)
            for status, count
            in config[
                "purchase_order_status_counts"
            ].items()
        }
    )

    if actual_counts != expected_counts:
        raise AssertionError(
            f"Purchase-order status mismatch: "
            f"{dict(actual_counts)}"
        )


def expected_approval_role(
    total_value_gbp: Decimal,
    config: dict[str, Any],
) -> str:
    """Calculate expected approval authority."""

    rules = config["approval_rules"]

    if total_value_gbp <= Decimal(
        str(
            rules[
                "auto_approval_limit_gbp"
            ]
        )
    ):
        return "AUTO_APPROVED"

    if total_value_gbp <= Decimal(
        str(
            rules[
                "procurement_manager_limit_gbp"
            ]
        )
    ):
        return "PROCUREMENT_MANAGER"

    if total_value_gbp <= Decimal(
        str(
            rules[
                "procurement_director_limit_gbp"
            ]
        )
    ):
        return "PROCUREMENT_DIRECTOR"

    return "EXECUTIVE_APPROVAL"


def validate_dates_statuses_and_approvals(
    purchase_orders: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Validate lifecycle dates, approvals and cancellations."""

    operating_period = config[
        "operating_period"
    ]

    minimum_order_date = date.fromisoformat(
        operating_period[
            "order_date_from"
        ]
    )

    maximum_order_date = date.fromisoformat(
        operating_period[
            "order_date_to"
        ]
    )

    snapshot_timestamp = parse_timestamp(
        config["project"][
            "snapshot_timestamp"
        ]
    )

    valid_order_types = set(
        config[
            "order_type_distribution"
        ]
    )

    valid_cancellation_reasons = set(
        config["cancellation_rules"][
            "cancellation_reason_distribution"
        ]
    )

    for order in purchase_orders:
        order_date = date.fromisoformat(
            order["order_date"]
        )

        required_date = date.fromisoformat(
            order["required_delivery_date"]
        )

        created_at = parse_timestamp(
            order["created_at"]
        )

        updated_at = parse_timestamp(
            order["updated_at"]
        )

        if not (
            minimum_order_date
            <= order_date
            <= maximum_order_date
        ):
            raise AssertionError(
                "Order date is outside the "
                "operating period."
            )

        if required_date <= order_date:
            raise AssertionError(
                "Required delivery date must be "
                "after order date."
            )

        if required_date.weekday() >= 5:
            raise AssertionError(
                "Required delivery date falls "
                "on a weekend."
            )

        if (
            order["order_type"]
            not in valid_order_types
        ):
            raise AssertionError(
                "Unknown purchase-order type."
            )

        if created_at > updated_at:
            raise AssertionError(
                "created_at is after updated_at."
            )

        if updated_at > snapshot_timestamp:
            raise AssertionError(
                "updated_at is after the snapshot."
            )

        for timestamp in [
            created_at,
            updated_at,
        ]:
            if (
                timestamp.tzinfo is None
                or timestamp.utcoffset() is None
                or timestamp.utcoffset().total_seconds()
                != 0
            ):
                raise AssertionError(
                    "Audit timestamp is not UTC."
                )

        total_value_gbp = Decimal(
            order["total_value_gbp"]
        )

        if (
            order["approval_role"]
            != expected_approval_role(
                total_value_gbp,
                config,
            )
        ):
            raise AssertionError(
                "Approval role does not match "
                "purchase-order value."
            )

        if (
            order[
                "purchase_order_status"
            ]
            == "DRAFT"
        ):
            if order["approved_at"]:
                raise AssertionError(
                    "Draft purchase order must "
                    "not be approved."
                )
        else:
            if not order["approved_at"]:
                raise AssertionError(
                    "Non-draft purchase order must "
                    "have approved_at."
                )

            approved_at = parse_timestamp(
                order["approved_at"]
            )

            if approved_at < created_at:
                raise AssertionError(
                    "approved_at precedes created_at."
                )

            if approved_at > updated_at:
                raise AssertionError(
                    "approved_at is after updated_at."
                )

        if (
            order[
                "purchase_order_status"
            ]
            == "CANCELLED"
        ):
            if (
                order["cancellation_reason"]
                not in valid_cancellation_reasons
            ):
                raise AssertionError(
                    "Cancelled purchase order has "
                    "an invalid cancellation reason."
                )
        elif order["cancellation_reason"]:
            raise AssertionError(
                "Non-cancelled purchase order has "
                "a cancellation reason."
            )


def validate_line_audit_fields(
    purchase_order_lines: list[
        dict[str, str]
    ],
    purchase_orders: list[
        dict[str, str]
    ],
) -> None:
    """Confirm line audit fields match parent orders."""

    orders_by_id = {
        row["purchase_order_id"]: row
        for row in purchase_orders
    }

    for line in purchase_order_lines:
        order = orders_by_id[
            line["purchase_order_id"]
        ]

        if (
            line["created_at"]
            != order["created_at"]
        ):
            raise AssertionError(
                "Line created_at differs from parent."
            )

        if (
            line["updated_at"]
            != order["updated_at"]
        ):
            raise AssertionError(
                "Line updated_at differs from parent."
            )

        if int(
            line["version_number"]
        ) != 1:
            raise AssertionError(
                "Initial line version must equal 1."
            )

    for order in purchase_orders:
        if int(
            order["version_number"]
        ) != 1:
            raise AssertionError(
                "Initial order version must equal 1."
            )


def validate_manifest(
    purchase_orders: list[
        dict[str, str]
    ],
    purchase_order_lines: list[
        dict[str, str]
    ],
) -> None:
    """Validate manifest counts, hashes and keys."""

    manifest = load_json(MANIFEST_PATH)

    if (
        manifest["purchase_order_count"]
        != len(purchase_orders)
    ):
        raise AssertionError(
            "Manifest purchase-order count is incorrect."
        )

    if (
        manifest[
            "purchase_order_line_count"
        ]
        != len(purchase_order_lines)
    ):
        raise AssertionError(
            "Manifest line count is incorrect."
        )

    order_metadata = manifest[
        "output_files"
    ][PURCHASE_ORDER_PATH.name]

    line_metadata = manifest[
        "output_files"
    ][PURCHASE_ORDER_LINE_PATH.name]

    if (
        order_metadata["sha256"]
        != calculate_sha256(
            PURCHASE_ORDER_PATH
        )
    ):
        raise AssertionError(
            "Purchase-order output hash mismatch."
        )

    if (
        line_metadata["sha256"]
        != calculate_sha256(
            PURCHASE_ORDER_LINE_PATH
        )
    ):
        raise AssertionError(
            "Purchase-order-line output hash mismatch."
        )

    expected_source_paths = [
        PRODUCT_PATH,
        SUPPLIER_PATH,
        SUPPLIER_PRODUCT_PATH,
        DISTRIBUTION_CENTRE_PATH,
        MASTER_VALIDATION_REPORT_PATH,
    ]

    for source_path in expected_source_paths:
        if (
            manifest["source_files"][
                source_path.name
            ]
            != calculate_sha256(
                source_path
            )
        ):
            raise AssertionError(
                f"Source hash mismatch for "
                f"{source_path.name}."
            )

    if manifest[
        "incremental_columns"
    ]["purchase_orders"] != [
        "updated_at",
        "purchase_order_id",
    ]:
        raise AssertionError(
            "Purchase-order incremental order is incorrect."
        )

    if manifest[
        "incremental_columns"
    ]["purchase_order_lines"] != [
        "updated_at",
        "purchase_order_line_id",
    ]:
        raise AssertionError(
            "Purchase-order-line incremental "
            "order is incorrect."
        )


def run_all_validations() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Run the complete purchase-order validation suite."""

    config = load_json(CONFIG_PATH)

    purchase_orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    purchase_order_lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)

    agreements = load_csv(
        SUPPLIER_PRODUCT_PATH
    )

    distribution_centres = load_csv(
        DISTRIBUTION_CENTRE_PATH
    )

    validate_master_data_approval()

    validate_required_columns(
        purchase_orders,
        purchase_order_lines,
    )

    validate_record_counts(
        purchase_orders,
        purchase_order_lines,
        config,
    )

    validate_unique_keys(
        purchase_orders,
        purchase_order_lines,
    )

    validate_header_references(
        purchase_orders,
        suppliers,
        distribution_centres,
    )

    validate_line_references(
        purchase_orders,
        purchase_order_lines,
        products,
        agreements,
    )

    validate_line_counts_and_products(
        purchase_orders,
        purchase_order_lines,
        config,
    )

    validate_line_commercial_values(
        purchase_order_lines,
        products,
        agreements,
        config,
    )

    validate_header_totals(
        purchase_orders,
        purchase_order_lines,
        agreements,
    )

    validate_status_distribution(
        purchase_orders,
        config,
    )

    validate_dates_statuses_and_approvals(
        purchase_orders,
        config,
    )

    validate_line_audit_fields(
        purchase_order_lines,
        purchase_orders,
    )

    validate_manifest(
        purchase_orders,
        purchase_order_lines,
    )

    return (
        purchase_orders,
        purchase_order_lines,
    )


def main() -> None:
    """Execute purchase-order validation."""

    purchase_orders, purchase_order_lines = (
        run_all_validations()
    )

    print(
        "BritMart purchase-order validation passed."
    )
    print(
        "Purchase orders validated: "
        f"{len(purchase_orders)}"
    )
    print(
        "Purchase-order lines validated: "
        f"{len(purchase_order_lines)}"
    )
    print(
        "Header-to-line reconciliation: PASSED"
    )
    print(
        "Master-data referential integrity: PASSED"
    )


if __name__ == "__main__":
    main()
