"""Automated tests for BritMart warehouse goods receipts."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORY = PROJECT_ROOT / "data-generators" / "src"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "goods_receipt_config.json"
GENERATOR_PATH = SOURCE_DIRECTORY / "generate_goods_receipts.py"
VALIDATOR_PATH = SOURCE_DIRECTORY / "validate_goods_receipts.py"

SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
SHIPMENT_LINE_PATH = OUTPUT_DIRECTORY / "shipment_lines.csv"
PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
DC_PATH = OUTPUT_DIRECTORY / "distribution_centres.csv"
RECEIPT_PATH = OUTPUT_DIRECTORY / "warehouse_goods_receipts.csv"
RECEIPT_LINE_PATH = OUTPUT_DIRECTORY / "warehouse_goods_receipt_lines.csv"
MOVEMENT_PATH = OUTPUT_DIRECTORY / "warehouse_inventory_movements.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "goods_receipt_manifest.json"

EXPECTED_RECEIPT_COUNT = 8576
EXPECTED_RECEIPT_LINE_COUNT = 45310
EXPECTED_MOVEMENT_COUNT = 47185


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
    required = [RECEIPT_PATH, RECEIPT_LINE_PATH, MOVEMENT_PATH, MANIFEST_PATH]
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


def test_goods_receipt_project_files_exist() -> None:
    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()


def test_goods_receipt_generator_runs_successfully() -> None:
    result = run_script(GENERATOR_PATH)
    assert result.returncode == 0, result.stderr
    assert "generated successfully" in result.stdout


def test_expected_goods_receipt_output_files_exist() -> None:
    ensure_outputs_exist()
    assert RECEIPT_PATH.exists()
    assert RECEIPT_LINE_PATH.exists()
    assert MOVEMENT_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_expected_goods_receipt_record_counts() -> None:
    ensure_outputs_exist()
    assert len(load_csv(RECEIPT_PATH)) == EXPECTED_RECEIPT_COUNT
    assert len(load_csv(RECEIPT_LINE_PATH)) == EXPECTED_RECEIPT_LINE_COUNT
    assert len(load_csv(MOVEMENT_PATH)) == EXPECTED_MOVEMENT_COUNT


def test_only_delivered_shipments_have_receipts() -> None:
    shipments = load_csv(SHIPMENT_PATH)
    receipts = load_csv(RECEIPT_PATH)
    delivered_ids = {
        row["shipment_id"] for row in shipments if row["shipment_status"] == "DELIVERED"
    }
    receipt_shipment_ids = {row["shipment_id"] for row in receipts}
    assert receipt_shipment_ids == delivered_ids


def test_each_delivered_shipment_has_exactly_one_receipt() -> None:
    counts = Counter(row["shipment_id"] for row in load_csv(RECEIPT_PATH))
    assert counts
    assert all(count == 1 for count in counts.values())


def test_goods_receipt_identifiers_are_unique_and_valid() -> None:
    receipts = load_csv(RECEIPT_PATH)
    for field in ["goods_receipt_id", "goods_receipt_number", "idempotency_key"]:
        values = [row[field] for row in receipts]
        assert all(values)
        assert len(values) == len(set(values))
    for row in receipts:
        UUID(row["goods_receipt_id"])
        UUID(row["idempotency_key"])


def test_receipt_line_and_movement_keys_are_unique() -> None:
    lines = load_csv(RECEIPT_LINE_PATH)
    movements = load_csv(MOVEMENT_PATH)
    for rows, fields in [
        (lines, ["goods_receipt_line_id", "goods_receipt_line_number", "idempotency_key"]),
        (movements, ["inventory_movement_id", "inventory_movement_reference", "idempotency_key"]),
    ]:
        for field in fields:
            values = [row[field] for row in rows]
            assert all(values)
            assert len(values) == len(set(values))


def test_source_system_ownership_is_correct() -> None:
    assert all(row["source_system"] == "WAREHOUSE_SQL" for row in load_csv(RECEIPT_PATH))
    assert all(row["source_system"] == "WAREHOUSE_SQL" for row in load_csv(MOVEMENT_PATH))


def test_receipt_headers_match_supplier_shipments() -> None:
    shipment_by_id = {row["shipment_id"]: row for row in load_csv(SHIPMENT_PATH)}
    for receipt in load_csv(RECEIPT_PATH):
        shipment = shipment_by_id[receipt["shipment_id"]]
        for field in [
            "shipment_number", "purchase_order_id", "purchase_order_number",
            "supplier_id", "supplier_code", "distribution_centre_id",
            "distribution_centre_code", "actual_delivery_at",
        ]:
            assert receipt[field] == shipment[field]


def test_receipt_headers_reference_valid_master_data() -> None:
    valid_orders = {row["purchase_order_id"] for row in load_csv(PURCHASE_ORDER_PATH)}
    valid_suppliers = {row["supplier_id"] for row in load_csv(SUPPLIER_PATH)}
    valid_dcs = {row["distribution_centre_id"] for row in load_csv(DC_PATH)}
    for receipt in load_csv(RECEIPT_PATH):
        assert receipt["purchase_order_id"] in valid_orders
        assert receipt["supplier_id"] in valid_suppliers
        assert receipt["distribution_centre_id"] in valid_dcs


def test_receipt_lines_match_supplier_shipment_lines() -> None:
    source_by_id = {row["shipment_line_id"]: row for row in load_csv(SHIPMENT_LINE_PATH)}
    products = {row["product_id"]: row for row in load_csv(PRODUCT_PATH)}
    lines = load_csv(RECEIPT_LINE_PATH)
    expected_ids = {
        row["shipment_line_id"]
        for row in source_by_id.values()
        if Decimal(row["received_quantity"]) > 0
    }
    assert {row["shipment_line_id"] for row in lines} == expected_ids
    for line in lines:
        source = source_by_id[line["shipment_line_id"]]
        for field in [
            "shipment_id", "purchase_order_id", "purchase_order_line_id",
            "product_id", "product_code", "sku", "storage_type", "unit_of_measure",
        ]:
            assert line[field] == source[field]
        assert line["storage_type"] == products[line["product_id"]]["storage_type"]


def test_supplier_api_to_warehouse_quantities_match() -> None:
    source_by_id = {row["shipment_line_id"]: row for row in load_csv(SHIPMENT_LINE_PATH)}
    for line in load_csv(RECEIPT_LINE_PATH):
        source = source_by_id[line["shipment_line_id"]]
        for field in [
            "received_quantity", "accepted_quantity", "damaged_quantity",
            "rejected_quantity",
        ]:
            assert Decimal(line[field]) == Decimal(source[field])


def test_receipt_line_quantities_reconcile() -> None:
    for line in load_csv(RECEIPT_LINE_PATH):
        received = Decimal(line["received_quantity"])
        accepted = Decimal(line["accepted_quantity"])
        damaged = Decimal(line["damaged_quantity"])
        rejected = Decimal(line["rejected_quantity"])
        assert received > 0
        assert min(accepted, damaged, rejected) >= 0
        assert received == accepted + damaged + rejected


def test_receipt_headers_reconcile_to_lines() -> None:
    lines_by_receipt = defaultdict(list)
    for line in load_csv(RECEIPT_LINE_PATH):
        lines_by_receipt[line["goods_receipt_id"]].append(line)
    mappings = {
        "total_received_quantity": "received_quantity",
        "total_accepted_quantity": "accepted_quantity",
        "total_damaged_quantity": "damaged_quantity",
        "total_rejected_quantity": "rejected_quantity",
    }
    for receipt in load_csv(RECEIPT_PATH):
        children = lines_by_receipt[receipt["goods_receipt_id"]]
        assert children
        for header_field, line_field in mappings.items():
            expected = sum((Decimal(row[line_field]) for row in children), Decimal("0"))
            assert Decimal(receipt[header_field]) == expected


def test_receipt_operational_timestamps_are_ordered() -> None:
    for receipt in load_csv(RECEIPT_PATH):
        delivered = parse_utc(receipt["actual_delivery_at"])
        started = parse_utc(receipt["receipt_started_at"])
        completed = parse_utc(receipt["receipt_completed_at"])
        posted = parse_utc(receipt["posted_at"])
        assert delivered < started < completed < posted
        assert parse_utc(receipt["created_at"]) == started
        assert parse_utc(receipt["updated_at"]) == posted


def test_best_before_dates_follow_delivery_dates() -> None:
    receipt_by_id = {row["goods_receipt_id"]: row for row in load_csv(RECEIPT_PATH)}
    for line in load_csv(RECEIPT_LINE_PATH):
        if line["best_before_date"]:
            delivery_date = parse_utc(receipt_by_id[line["goods_receipt_id"]]["actual_delivery_at"]).date()
            assert date.fromisoformat(line["best_before_date"]) > delivery_date


def test_inventory_movements_match_each_disposition() -> None:
    config = load_json(CONFIG_PATH)
    movement_types = config["inventory_movement_types"]
    movements_by_line = defaultdict(list)
    for movement in load_csv(MOVEMENT_PATH):
        movements_by_line[movement["goods_receipt_line_id"]].append(movement)
    for line in load_csv(RECEIPT_LINE_PATH):
        by_type = {row["movement_type"]: row for row in movements_by_line[line["goods_receipt_line_id"]]}
        assert len(by_type) == len(movements_by_line[line["goods_receipt_line_id"]])
        for disposition in ["accepted", "damaged", "rejected"]:
            quantity = Decimal(line[f"{disposition}_quantity"])
            movement = by_type.get(movement_types[disposition])
            if quantity == 0:
                assert movement is None
            else:
                assert movement is not None
                assert Decimal(movement["movement_quantity"]) == quantity


def test_available_and_quarantine_inventory_effects_reconcile() -> None:
    lines = load_csv(RECEIPT_LINE_PATH)
    movements = load_csv(MOVEMENT_PATH)
    accepted = sum((Decimal(row["accepted_quantity"]) for row in lines), Decimal("0"))
    damaged = sum((Decimal(row["damaged_quantity"]) for row in lines), Decimal("0"))
    available = sum((Decimal(row["available_quantity_effect"]) for row in movements), Decimal("0"))
    quarantine = sum((Decimal(row["quarantine_quantity_effect"]) for row in movements), Decimal("0"))
    assert available == accepted
    assert quarantine == damaged


def test_rejected_quantities_have_zero_stock_effect() -> None:
    config = load_json(CONFIG_PATH)
    rejected_type = config["inventory_movement_types"]["rejected"]
    rejected_movements = [
        row for row in load_csv(MOVEMENT_PATH) if row["movement_type"] == rejected_type
    ]
    assert rejected_movements
    for movement in rejected_movements:
        assert Decimal(movement["movement_quantity"]) > 0
        assert Decimal(movement["available_quantity_effect"]) == 0
        assert Decimal(movement["quarantine_quantity_effect"]) == 0
        assert Decimal(movement["physical_quantity_effect"]) == 0


def test_physical_inventory_excludes_rejected_quantity() -> None:
    lines = load_csv(RECEIPT_LINE_PATH)
    movements = load_csv(MOVEMENT_PATH)
    expected = sum(
        (
            Decimal(row["accepted_quantity"])
            + Decimal(row["damaged_quantity"])
            for row in lines
        ),
        Decimal("0"),
    )
    actual = sum((Decimal(row["physical_quantity_effect"]) for row in movements), Decimal("0"))
    assert actual == expected


def test_goods_receipt_manifest_matches_outputs() -> None:
    manifest = load_json(MANIFEST_PATH)
    expected = {
        RECEIPT_PATH.name: (EXPECTED_RECEIPT_COUNT, sha256(RECEIPT_PATH)),
        RECEIPT_LINE_PATH.name: (EXPECTED_RECEIPT_LINE_COUNT, sha256(RECEIPT_LINE_PATH)),
        MOVEMENT_PATH.name: (EXPECTED_MOVEMENT_COUNT, sha256(MOVEMENT_PATH)),
    }
    datasets = {row["file_name"]: row for row in manifest["datasets"]}
    assert set(datasets) == set(expected)
    for file_name, (record_count, digest) in expected.items():
        assert int(datasets[file_name]["record_count"]) == record_count
        assert datasets[file_name]["sha256"] == digest


def test_full_goods_receipt_validator_runs_successfully() -> None:
    result = run_script(VALIDATOR_PATH)
    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout
    assert "Supplier API-to-Warehouse SQL reconciliation: PASSED" in result.stdout


def test_goods_receipt_generation_is_reproducible() -> None:
    ensure_outputs_exist()
    paths = [RECEIPT_PATH, RECEIPT_LINE_PATH, MOVEMENT_PATH, MANIFEST_PATH]
    first = {path.name: path.read_bytes() for path in paths}
    result = run_script(GENERATOR_PATH)
    assert result.returncode == 0, result.stderr
    second = {path.name: path.read_bytes() for path in paths}
    assert first == second