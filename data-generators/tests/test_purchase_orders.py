"""Automated tests for BritMart purchase orders."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "src"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data-generators"
    / "output"
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "data-generators"
    / "config"
    / "purchase_order_config.json"
)

GENERATOR_PATH = (
    SOURCE_DIRECTORY
    / "generate_purchase_orders.py"
)

VALIDATOR_PATH = (
    SOURCE_DIRECTORY
    / "validate_purchase_orders.py"
)

PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"

AGREEMENT_PATH = (
    OUTPUT_DIRECTORY
    / "supplier_products.csv"
)

DISTRIBUTION_CENTRE_PATH = (
    OUTPUT_DIRECTORY
    / "distribution_centres.csv"
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

EXPECTED_ORDER_COUNT = 8000
EXPECTED_LINE_COUNT = 48000

EXPECTED_STATUS_COUNTS = {
    "CLOSED": 6240,
    "PARTIALLY_RECEIVED": 560,
    "DISPATCHED": 480,
    "CONFIRMED": 320,
    "APPROVED": 240,
    "DRAFT": 80,
    "CANCELLED": 80,
}


def run_python_script(
    script_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Run a project Python script."""

    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def load_csv(
    path: Path,
) -> list[dict[str, str]]:
    """Load a CSV file."""

    if not path.exists():
        raise AssertionError(
            f"Expected CSV does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:
        return list(csv.DictReader(source_file))


def load_json(path: Path) -> dict:
    """Load a JSON file."""

    if not path.exists():
        raise AssertionError(
            f"Expected JSON does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as source_file:
        return json.load(source_file)


def calculate_sha256(path: Path) -> str:
    """Calculate a SHA-256 digest."""

    digest = hashlib.sha256()

    with path.open("rb") as source_file:
        for chunk in iter(
            lambda: source_file.read(65_536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def ensure_outputs_exist() -> None:
    """Generate outputs when required."""

    if (
        PURCHASE_ORDER_PATH.exists()
        and PURCHASE_ORDER_LINE_PATH.exists()
        and MANIFEST_PATH.exists()
    ):
        return

    result = run_python_script(
        GENERATOR_PATH
    )

    assert result.returncode == 0, (
        "Purchase-order generation failed.\n"
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )


def test_purchase_order_project_files_exist() -> None:
    """Confirm all purchase-order project files exist."""

    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()
    assert PRODUCT_PATH.exists()
    assert SUPPLIER_PATH.exists()
    assert AGREEMENT_PATH.exists()
    assert DISTRIBUTION_CENTRE_PATH.exists()


def test_purchase_order_generator_runs_successfully() -> None:
    """Confirm purchase-order generation succeeds."""

    result = run_python_script(
        GENERATOR_PATH
    )

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "generated successfully"
        in result.stdout.lower()
    )


def test_purchase_order_output_files_exist() -> None:
    """Confirm all expected output files exist."""

    ensure_outputs_exist()

    assert PURCHASE_ORDER_PATH.exists()
    assert PURCHASE_ORDER_LINE_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_expected_transaction_counts() -> None:
    """Confirm exact order and line counts."""

    ensure_outputs_exist()

    purchase_orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    purchase_order_lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    assert (
        len(purchase_orders)
        == EXPECTED_ORDER_COUNT
    )

    assert (
        len(purchase_order_lines)
        == EXPECTED_LINE_COUNT
    )

    assert (
        Decimal(len(purchase_order_lines))
        / Decimal(len(purchase_orders))
        == Decimal("6")
    )


def test_purchase_order_status_counts_are_exact() -> None:
    """Confirm the lifecycle status scenario."""

    ensure_outputs_exist()

    purchase_orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    actual_counts = Counter(
        row["purchase_order_status"]
        for row in purchase_orders
    )

    assert actual_counts == Counter(
        EXPECTED_STATUS_COUNTS
    )


def test_purchase_order_identifiers_are_unique() -> None:
    """Confirm purchase-order keys are valid and unique."""

    ensure_outputs_exist()

    purchase_orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    order_ids = [
        row["purchase_order_id"]
        for row in purchase_orders
    ]

    order_numbers = [
        row["purchase_order_number"]
        for row in purchase_orders
    ]

    assert len(order_ids) == len(
        set(order_ids)
    )

    assert len(order_numbers) == len(
        set(order_numbers)
    )

    for order_id in order_ids:
        assert str(UUID(order_id)) == order_id


def test_purchase_order_line_identifiers_are_unique() -> None:
    """Confirm purchase-order-line keys are valid and unique."""

    ensure_outputs_exist()

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    line_ids = [
        row["purchase_order_line_id"]
        for row in lines
    ]

    business_keys = [
        (
            row["purchase_order_id"],
            row["line_number"],
        )
        for row in lines
    ]

    assert len(line_ids) == len(
        set(line_ids)
    )

    assert len(business_keys) == len(
        set(business_keys)
    )

    for line_id in line_ids:
        assert str(UUID(line_id)) == line_id


def test_orders_reference_valid_active_suppliers() -> None:
    """Confirm order supplier references."""

    ensure_outputs_exist()

    suppliers = load_csv(
        SUPPLIER_PATH
    )

    purchase_orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    for order in purchase_orders:
        assert (
            order["supplier_id"]
            in suppliers_by_id
        )

        supplier = suppliers_by_id[
            order["supplier_id"]
        ]

        assert (
            supplier["supplier_status"]
            == "ACTIVE"
        )

        assert (
            order["supplier_code"]
            == supplier["supplier_code"]
        )

        assert (
            order["currency_code"]
            == supplier[
                "default_currency_code"
            ]
        )


def test_orders_reference_valid_distribution_centres() -> None:
    """Confirm destination references."""

    ensure_outputs_exist()

    centres = load_csv(
        DISTRIBUTION_CENTRE_PATH
    )

    purchase_orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    centres_by_id = {
        row["distribution_centre_id"]: row
        for row in centres
    }

    for order in purchase_orders:
        assert (
            order["distribution_centre_id"]
            in centres_by_id
        )

        centre = centres_by_id[
            order["distribution_centre_id"]
        ]

        assert (
            order[
                "distribution_centre_code"
            ]
            == centre[
                "distribution_centre_code"
            ]
        )


def test_lines_reference_valid_orders_products_and_agreements() -> None:
    """Confirm all line references."""

    ensure_outputs_exist()

    orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    products = load_csv(
        PRODUCT_PATH
    )

    agreements = load_csv(
        AGREEMENT_PATH
    )

    orders_by_id = {
        row["purchase_order_id"]: row
        for row in orders
    }

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    agreements_by_id = {
        row["supplier_product_id"]: row
        for row in agreements
    }

    for line in lines:
        assert (
            line["purchase_order_id"]
            in orders_by_id
        )

        assert (
            line["product_id"]
            in products_by_id
        )

        assert (
            line["supplier_product_id"]
            in agreements_by_id
        )

        order = orders_by_id[
            line["purchase_order_id"]
        ]

        product = products_by_id[
            line["product_id"]
        ]

        agreement = agreements_by_id[
            line["supplier_product_id"]
        ]

        assert (
            line["purchase_order_number"]
            == order["purchase_order_number"]
        )

        assert (
            line["product_code"]
            == product["product_code"]
        )

        assert line["sku"] == product["sku"]

        assert (
            agreement["supplier_id"]
            == order["supplier_id"]
        )

        assert (
            agreement["product_id"]
            == line["product_id"]
        )


def test_line_counts_are_within_configured_range() -> None:
    """Confirm each order has 2 to 12 lines."""

    ensure_outputs_exist()

    orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    line_counts = Counter(
        row["purchase_order_id"]
        for row in lines
    )

    assert len(line_counts) == len(orders)

    assert all(
        2 <= count <= 12
        for count in line_counts.values()
    )


def test_products_are_unique_within_each_order() -> None:
    """Confirm no duplicate product in one order."""

    ensure_outputs_exist()

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    products_by_order: dict[
        str,
        list[str],
    ] = defaultdict(list)

    for line in lines:
        products_by_order[
            line["purchase_order_id"]
        ].append(
            line["product_id"]
        )

    for product_ids in (
        products_by_order.values()
    ):
        assert len(product_ids) == len(
            set(product_ids)
        )


def test_quantities_respect_supplier_agreements() -> None:
    """Confirm minimum quantities and multiples."""

    ensure_outputs_exist()

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    agreements = load_csv(
        AGREEMENT_PATH
    )

    agreements_by_id = {
        row["supplier_product_id"]: row
        for row in agreements
    }

    for line in lines:
        agreement = agreements_by_id[
            line["supplier_product_id"]
        ]

        ordered_quantity = Decimal(
            line["ordered_quantity"]
        )

        minimum_quantity = Decimal(
            agreement[
                "minimum_order_quantity"
            ]
        )

        order_multiple = Decimal(
            line["order_multiple"]
        )

        assert (
            ordered_quantity
            >= minimum_quantity
        )

        assert (
            order_multiple
            == Decimal(
                agreement["order_multiple"]
            )
        )

        assert (
            ordered_quantity
            % order_multiple
            == 0
        )


def test_line_amount_calculations_are_correct() -> None:
    """Confirm net, VAT and gross calculations."""

    ensure_outputs_exist()

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    for line in lines:
        ordered_quantity = Decimal(
            line["ordered_quantity"]
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

        expected_net = (
            ordered_quantity
            * unit_price
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        expected_vat = (
            net_amount * vat_rate
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        assert net_amount == expected_net
        assert vat_amount == expected_vat

        assert (
            gross_amount
            == net_amount + vat_amount
        )


def test_header_totals_reconcile_to_lines() -> None:
    """Confirm header-to-line reconciliation."""

    ensure_outputs_exist()

    orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    lines_by_order: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for line in lines:
        lines_by_order[
            line["purchase_order_id"]
        ].append(line)

    for order in orders:
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

        assert (
            Decimal(
                order["total_net_amount"]
            )
            == expected_net
        )

        assert (
            Decimal(
                order["total_vat_amount"]
            )
            == expected_vat
        )

        assert (
            Decimal(
                order["total_gross_amount"]
            )
            == expected_gross
        )


def test_order_dates_and_delivery_dates_are_valid() -> None:
    """Confirm operating-period and delivery-date rules."""

    ensure_outputs_exist()

    orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    minimum_date = date(
        2025,
        8,
        1,
    )

    maximum_date = date(
        2026,
        7,
        31,
    )

    for order in orders:
        order_date = date.fromisoformat(
            order["order_date"]
        )

        required_date = date.fromisoformat(
            order[
                "required_delivery_date"
            ]
        )

        assert (
            minimum_date
            <= order_date
            <= maximum_date
        )

        assert required_date > order_date

        assert required_date.weekday() < 5


def test_draft_and_cancelled_order_rules_are_correct() -> None:
    """Confirm approval and cancellation behaviour."""

    ensure_outputs_exist()

    config = load_json(CONFIG_PATH)

    orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    valid_reasons = set(
        config["cancellation_rules"][
            "cancellation_reason_distribution"
        ]
    )

    for order in orders:
        status = order[
            "purchase_order_status"
        ]

        if status == "DRAFT":
            assert order["approved_at"] == ""
        else:
            assert order["approved_at"] != ""

        if status == "CANCELLED":
            assert (
                order["cancellation_reason"]
                in valid_reasons
            )
        else:
            assert (
                order["cancellation_reason"]
                == ""
            )


def test_purchase_order_manifest_matches_outputs() -> None:
    """Confirm manifest counts and hashes."""

    ensure_outputs_exist()

    orders = load_csv(
        PURCHASE_ORDER_PATH
    )

    lines = load_csv(
        PURCHASE_ORDER_LINE_PATH
    )

    manifest = load_json(
        MANIFEST_PATH
    )

    assert (
        manifest["purchase_order_count"]
        == len(orders)
    )

    assert (
        manifest[
            "purchase_order_line_count"
        ]
        == len(lines)
    )

    assert (
        manifest["output_files"][
            PURCHASE_ORDER_PATH.name
        ]["sha256"]
        == calculate_sha256(
            PURCHASE_ORDER_PATH
        )
    )

    assert (
        manifest["output_files"][
            PURCHASE_ORDER_LINE_PATH.name
        ]["sha256"]
        == calculate_sha256(
            PURCHASE_ORDER_LINE_PATH
        )
    )

    assert manifest[
        "incremental_columns"
    ]["purchase_orders"] == [
        "updated_at",
        "purchase_order_id",
    ]

    assert manifest[
        "incremental_columns"
    ]["purchase_order_lines"] == [
        "updated_at",
        "purchase_order_line_id",
    ]


def test_purchase_order_validator_runs_successfully() -> None:
    """Confirm the independent validator succeeds."""

    ensure_outputs_exist()

    result = run_python_script(
        VALIDATOR_PATH
    )

    assert result.returncode == 0, (
        f"Standard output:\n{result.stdout}\n"
        f"Error output:\n{result.stderr}"
    )

    assert (
        "validation passed"
        in result.stdout.lower()
    )


def test_purchase_order_generation_is_reproducible() -> None:
    """Confirm repeated generation produces identical files."""

    first_result = run_python_script(
        GENERATOR_PATH
    )

    assert first_result.returncode == 0, (
        first_result.stderr
    )

    first_order_hash = calculate_sha256(
        PURCHASE_ORDER_PATH
    )

    first_line_hash = calculate_sha256(
        PURCHASE_ORDER_LINE_PATH
    )

    first_manifest_bytes = (
        MANIFEST_PATH.read_bytes()
    )

    second_result = run_python_script(
        GENERATOR_PATH
    )

    assert second_result.returncode == 0, (
        second_result.stderr
    )

    second_order_hash = calculate_sha256(
        PURCHASE_ORDER_PATH
    )

    second_line_hash = calculate_sha256(
        PURCHASE_ORDER_LINE_PATH
    )

    second_manifest_bytes = (
        MANIFEST_PATH.read_bytes()
    )

    assert (
        first_order_hash
        == second_order_hash
    )

    assert (
        first_line_hash
        == second_line_hash
    )

    assert (
        first_manifest_bytes
        == second_manifest_bytes
    )