"""Automated tests for BritMart supplier shipments."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORY = PROJECT_ROOT / "data-generators" / "src"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "shipment_config.json"
GENERATOR_PATH = SOURCE_DIRECTORY / "generate_shipments.py"
VALIDATOR_PATH = SOURCE_DIRECTORY / "validate_shipments.py"

PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
PURCHASE_ORDER_LINE_PATH = OUTPUT_DIRECTORY / "purchase_order_lines.csv"
PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
DC_PATH = OUTPUT_DIRECTORY / "distribution_centres.csv"
SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
SHIPMENT_LINE_PATH = OUTPUT_DIRECTORY / "shipment_lines.csv"
HISTORY_PATH = OUTPUT_DIRECTORY / "shipment_status_history.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "shipment_manifest.json"

EXPECTED_ELIGIBLE_ORDER_COUNT = 7840

STATUS_BY_PO_STATUS = {
    "CLOSED": "DELIVERED",
    "PARTIALLY_RECEIVED": "DELIVERED",
    "DISPATCHED": "IN_TRANSIT",
    "CONFIRMED": "PLANNED",
    "APPROVED": "PLANNED",
}

EXPECTED_STATUS_PATHS = {
    "PLANNED": ["PLANNED"],
    "IN_TRANSIT": ["PLANNED", "DISPATCHED", "IN_TRANSIT"],
    "DELIVERED": ["PLANNED", "DISPATCHED", "IN_TRANSIT", "DELIVERED"],
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_script(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_outputs_exist() -> None:
    required = [SHIPMENT_PATH, SHIPMENT_LINE_PATH, HISTORY_PATH, MANIFEST_PATH]
    if any(not path.exists() for path in required):
        result = run_script(GENERATOR_PATH)
        assert result.returncode == 0, result.stderr


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    assert value.endswith("Z")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_shipment_project_files_exist() -> None:
    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()


def test_shipment_generator_runs_successfully() -> None:
    result = run_script(GENERATOR_PATH)
    assert result.returncode == 0, result.stderr
    assert "generated successfully" in result.stdout


def test_expected_shipment_output_files_exist() -> None:
    ensure_outputs_exist()
    assert SHIPMENT_PATH.exists()
    assert SHIPMENT_LINE_PATH.exists()
    assert HISTORY_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_expected_shipment_record_counts() -> None:
    ensure_outputs_exist()
    config = load_json(CONFIG_PATH)
    shipments = load_csv(SHIPMENT_PATH)
    lines = load_csv(SHIPMENT_LINE_PATH)
    history = load_csv(HISTORY_PATH)
    maximum = int(
        config["split_shipment"][
            "maximum_shipments_per_order"
        ]
    )
    assert (
        EXPECTED_ELIGIBLE_ORDER_COUNT
        < len(shipments)
        <= EXPECTED_ELIGIBLE_ORDER_COUNT
        * maximum
    )
    assert len(lines) >= 47040
    assert len(history) >= len(shipments)


def test_shipment_status_counts_reconcile_to_orders() -> None:
    ensure_outputs_exist()
    order_by_id = {
        row["purchase_order_id"]: row
        for row in load_csv(PURCHASE_ORDER_PATH)
    }
    actual = Counter(
        row["shipment_status"]
        for row in load_csv(SHIPMENT_PATH)
    )
    expected = Counter()
    for shipment in load_csv(SHIPMENT_PATH):
        status = order_by_id[
            shipment["purchase_order_id"]
        ]["purchase_order_status"]
        expected[STATUS_BY_PO_STATUS[status]] += 1
    assert actual == expected


def test_shipment_identifiers_are_unique_and_valid() -> None:
    shipments = load_csv(SHIPMENT_PATH)
    for field in ["shipment_id", "shipment_number", "supplier_shipment_reference"]:
        values = [row[field] for row in shipments]
        assert len(values) == len(set(values))
        assert all(values)
    for row in shipments:
        UUID(row["shipment_id"])


def test_shipment_line_and_history_identifiers_are_unique() -> None:
    lines = load_csv(SHIPMENT_LINE_PATH)
    history = load_csv(HISTORY_PATH)
    line_ids = [row["shipment_line_id"] for row in lines]
    history_ids = [row["shipment_status_history_id"] for row in history]
    assert len(line_ids) == len(set(line_ids))
    assert len(history_ids) == len(set(history_ids))
    for value in line_ids + history_ids:
        UUID(value)


def test_draft_and_cancelled_orders_have_no_shipments() -> None:
    orders = load_csv(PURCHASE_ORDER_PATH)
    shipment_order_ids = {row["purchase_order_id"] for row in load_csv(SHIPMENT_PATH)}
    for order in orders:
        if order["purchase_order_status"] in {"DRAFT", "CANCELLED"}:
            assert order["purchase_order_id"] not in shipment_order_ids


def test_every_eligible_order_has_one_to_three_shipments() -> None:
    orders = load_csv(PURCHASE_ORDER_PATH)
    counts = Counter(row["purchase_order_id"] for row in load_csv(SHIPMENT_PATH))
    maximum = int(
        load_json(CONFIG_PATH)[
            "split_shipment"
        ]["maximum_shipments_per_order"]
    )
    split_orders = 0
    for order in orders:
        count = counts[order["purchase_order_id"]]
        if order["purchase_order_status"] in {"DRAFT", "CANCELLED"}:
            assert count == 0
        else:
            assert 1 <= count <= maximum
            if count > 1:
                split_orders += 1
    assert split_orders > 0


def test_shipment_status_matches_purchase_order_status() -> None:
    order_by_id = {row["purchase_order_id"]: row for row in load_csv(PURCHASE_ORDER_PATH)}
    for shipment in load_csv(SHIPMENT_PATH):
        order = order_by_id[shipment["purchase_order_id"]]
        assert shipment["shipment_status"] == STATUS_BY_PO_STATUS[order["purchase_order_status"]]


def test_shipment_supplier_and_destination_match_purchase_order() -> None:
    order_by_id = {row["purchase_order_id"]: row for row in load_csv(PURCHASE_ORDER_PATH)}
    valid_suppliers = {row["supplier_id"] for row in load_csv(SUPPLIER_PATH)}
    valid_dcs = {row["distribution_centre_id"] for row in load_csv(DC_PATH)}
    for shipment in load_csv(SHIPMENT_PATH):
        order = order_by_id[shipment["purchase_order_id"]]
        assert shipment["supplier_id"] in valid_suppliers
        assert shipment["distribution_centre_id"] in valid_dcs
        assert shipment["supplier_id"] == order["supplier_id"]
        assert shipment["supplier_code"] == order["supplier_code"]
        assert shipment["distribution_centre_id"] == order["distribution_centre_id"]
        assert shipment["distribution_centre_code"] == order["distribution_centre_code"]


def test_shipment_lines_reference_valid_parents_and_products() -> None:
    shipment_by_id = {row["shipment_id"]: row for row in load_csv(SHIPMENT_PATH)}
    po_line_by_id = {row["purchase_order_line_id"]: row for row in load_csv(PURCHASE_ORDER_LINE_PATH)}
    product_by_id = {row["product_id"]: row for row in load_csv(PRODUCT_PATH)}
    for line in load_csv(SHIPMENT_LINE_PATH):
        shipment = shipment_by_id[line["shipment_id"]]
        po_line = po_line_by_id[line["purchase_order_line_id"]]
        product = product_by_id[line["product_id"]]
        assert line["purchase_order_id"] == shipment["purchase_order_id"]
        assert line["purchase_order_id"] == po_line["purchase_order_id"]
        assert line["product_id"] == po_line["product_id"]
        assert line["sku"] == po_line["sku"]
        assert line["storage_type"] == product["storage_type"]


def test_shipment_line_quantities_are_valid() -> None:
    po_line_by_id = {row["purchase_order_line_id"]: row for row in load_csv(PURCHASE_ORDER_LINE_PATH)}
    for line in load_csv(SHIPMENT_LINE_PATH):
        ordered = Decimal(line["ordered_quantity"])
        planned = Decimal(line["planned_quantity"])
        shipped = Decimal(line["shipped_quantity"])
        received = Decimal(line["received_quantity"])
        damaged = Decimal(line["damaged_quantity"])
        rejected = Decimal(line["rejected_quantity"])
        accepted = Decimal(line["accepted_quantity"])
        source_ordered = Decimal(po_line_by_id[line["purchase_order_line_id"]]["ordered_quantity"])
        assert ordered == source_ordered
        assert Decimal("0") < planned <= ordered
        assert Decimal("0") <= shipped <= planned
        assert Decimal("0") <= received <= shipped
        assert damaged >= 0 and rejected >= 0
        assert damaged + rejected <= received
        assert accepted == received - damaged - rejected


def test_shipment_quantities_respect_order_multiples() -> None:
    for line in load_csv(SHIPMENT_LINE_PATH):
        multiple = Decimal(line["order_multiple"])
        assert multiple > 0
        for field in [
            "planned_quantity", "shipped_quantity", "received_quantity",
            "damaged_quantity", "rejected_quantity", "accepted_quantity",
        ]:
            value = Decimal(line[field])
            assert value == 0 or value % multiple == 0


def test_shipment_headers_reconcile_to_lines() -> None:
    lines_by_shipment = defaultdict(list)
    for line in load_csv(SHIPMENT_LINE_PATH):
        lines_by_shipment[line["shipment_id"]].append(line)
    mappings = {
        "total_planned_quantity": "planned_quantity",
        "total_shipped_quantity": "shipped_quantity",
        "total_received_quantity": "received_quantity",
        "total_damaged_quantity": "damaged_quantity",
        "total_rejected_quantity": "rejected_quantity",
        "total_accepted_quantity": "accepted_quantity",
    }
    for shipment in load_csv(SHIPMENT_PATH):
        children = lines_by_shipment[shipment["shipment_id"]]
        assert children
        for header_field, line_field in mappings.items():
            expected = sum((Decimal(row[line_field]) for row in children), Decimal("0"))
            assert Decimal(shipment[header_field]) == expected


def test_cumulative_shipped_quantity_never_exceeds_ordered() -> None:
    po_line_by_id = {row["purchase_order_line_id"]: row for row in load_csv(PURCHASE_ORDER_LINE_PATH)}
    cumulative = defaultdict(lambda: Decimal("0"))
    for line in load_csv(SHIPMENT_LINE_PATH):
        cumulative[line["purchase_order_line_id"]] += Decimal(line["shipped_quantity"])
    for po_line_id, shipped in cumulative.items():
        assert shipped <= Decimal(po_line_by_id[po_line_id]["ordered_quantity"])


def test_some_purchase_order_lines_span_multiple_shipments() -> None:
    occurrences = Counter(
        row["purchase_order_line_id"]
        for row in load_csv(SHIPMENT_LINE_PATH)
    )
    assert any(
        count > 1
        for count in occurrences.values()
    )


def test_shipment_dates_and_delivery_performance_are_valid() -> None:
    for shipment in load_csv(SHIPMENT_PATH):
        created = parse_utc(shipment["created_at"])
        planned = parse_utc(shipment["planned_dispatch_at"])
        expected = parse_utc(shipment["expected_delivery_at"])
        updated = parse_utc(shipment["updated_at"])
        assert created <= planned <= expected
        assert updated >= created
        status = shipment["shipment_status"]
        if status == "PLANNED":
            assert not shipment["actual_dispatch_at"]
            assert not shipment["actual_delivery_at"]
            assert shipment["delivery_performance_status"] == "NOT_APPLICABLE"
        elif status == "IN_TRANSIT":
            assert shipment["actual_dispatch_at"]
            assert not shipment["actual_delivery_at"]
            assert shipment["delivery_performance_status"] == "NOT_APPLICABLE"
        elif status == "DELIVERED":
            dispatch = parse_utc(shipment["actual_dispatch_at"])
            delivered = parse_utc(shipment["actual_delivery_at"])
            assert delivered > dispatch
            assert shipment["delivery_performance_status"] in {"EARLY", "ON_TIME", "LATE"}


def test_status_history_paths_are_complete_and_contiguous() -> None:
    history_by_shipment = defaultdict(list)
    for event in load_csv(HISTORY_PATH):
        history_by_shipment[event["shipment_id"]].append(event)
    for shipment in load_csv(SHIPMENT_PATH):
        events = sorted(history_by_shipment[shipment["shipment_id"]], key=lambda row: int(row["sequence_number"]))
        assert [event["new_status"] for event in events] == EXPECTED_STATUS_PATHS[shipment["shipment_status"]]
        assert [int(event["sequence_number"]) for event in events] == list(range(1, len(events) + 1))
        previous = ""
        for event in events:
            assert event["previous_status"] == previous
            parse_utc(event["status_changed_at"])
            previous = event["new_status"]


def test_temperature_control_is_logically_consistent() -> None:
    controlled_vehicles = {
        "REFRIGERATED_LORRY", "FROZEN_TRAILER", "MIXED_TEMPERATURE_TRAILER"
    }
    for shipment in load_csv(SHIPMENT_PATH):
        if shipment["temperature_controlled_flag"] == "true":
            assert shipment["vehicle_type"] in controlled_vehicles
            minimum = Decimal(shipment["minimum_recorded_temperature_celsius"])
            maximum = Decimal(shipment["maximum_recorded_temperature_celsius"])
            assert minimum <= maximum
        else:
            assert not shipment["minimum_recorded_temperature_celsius"]
            assert not shipment["maximum_recorded_temperature_celsius"]


def test_shipment_manifest_matches_outputs() -> None:
    manifest = load_json(MANIFEST_PATH)
    shipment_count = len(
        load_csv(SHIPMENT_PATH)
    )
    line_count = len(
        load_csv(SHIPMENT_LINE_PATH)
    )
    history_count = len(
        load_csv(HISTORY_PATH)
    )
    expected = {
        SHIPMENT_PATH.name: (
            shipment_count,
            sha256(SHIPMENT_PATH),
        ),
        SHIPMENT_LINE_PATH.name: (
            line_count,
            sha256(SHIPMENT_LINE_PATH),
        ),
        HISTORY_PATH.name: (
            history_count,
            sha256(HISTORY_PATH),
        ),
    }
    datasets = {row["file_name"]: row for row in manifest["datasets"]}
    assert set(datasets) == set(expected)
    for file_name, (record_count, digest) in expected.items():
        assert int(datasets[file_name]["record_count"]) == record_count
        assert datasets[file_name]["sha256"] == digest


def test_full_shipment_validator_runs_successfully() -> None:
    result = run_script(VALIDATOR_PATH)
    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout
    assert "Purchase-order-to-shipment reconciliation: PASSED" in result.stdout


def test_shipment_generation_is_reproducible() -> None:
    ensure_outputs_exist()
    paths = [SHIPMENT_PATH, SHIPMENT_LINE_PATH, HISTORY_PATH, MANIFEST_PATH]
    first = {path.name: path.read_bytes() for path in paths}
    result = run_script(GENERATOR_PATH)
    assert result.returncode == 0, result.stderr
    second = {path.name: path.read_bytes() for path in paths}
    assert first == second