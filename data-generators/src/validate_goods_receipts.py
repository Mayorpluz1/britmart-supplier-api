"""Validate BritMart warehouse goods receipts and inventory movements."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "goods_receipt_config.json"

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

RECEIPT_COLUMNS = {
    "goods_receipt_id", "goods_receipt_number", "source_system", "shipment_id",
    "shipment_number", "purchase_order_id", "purchase_order_number", "supplier_id",
    "supplier_code", "distribution_centre_id", "distribution_centre_code",
    "receipt_status", "quality_status", "actual_delivery_at", "receipt_started_at",
    "receipt_completed_at", "posted_at", "dock_door_code", "receiver_code",
    "total_received_quantity", "total_accepted_quantity", "total_damaged_quantity",
    "total_rejected_quantity", "idempotency_key", "created_at", "updated_at",
    "version_number",
}

LINE_COLUMNS = {
    "goods_receipt_line_id", "goods_receipt_line_number", "goods_receipt_id",
    "goods_receipt_number", "shipment_id", "shipment_number", "shipment_line_id",
    "purchase_order_id", "purchase_order_number", "purchase_order_line_id",
    "product_id", "product_code", "sku", "storage_type", "unit_of_measure",
    "received_quantity", "accepted_quantity", "damaged_quantity", "rejected_quantity",
    "quality_status", "quality_inspector_code", "supplier_batch_number",
    "best_before_date", "idempotency_key", "created_at", "updated_at",
    "version_number",
}

MOVEMENT_COLUMNS = {
    "inventory_movement_id", "inventory_movement_reference", "source_system",
    "goods_receipt_id", "goods_receipt_number", "goods_receipt_line_id",
    "shipment_id", "shipment_line_id", "purchase_order_id", "purchase_order_line_id",
    "distribution_centre_id", "distribution_centre_code", "product_id", "product_code",
    "sku", "movement_type", "inventory_bucket", "movement_quantity",
    "available_quantity_effect", "quarantine_quantity_effect",
    "physical_quantity_effect", "movement_at", "idempotency_key", "created_at",
    "updated_at", "version_number",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise AssertionError(f"Required file does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"Required JSON file does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    if not value or not value.endswith("Z"):
        raise AssertionError(f"Timestamp is not a populated UTC value: {value}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_unique(rows: list[dict[str, str]], field: str) -> None:
    values = [row[field] for row in rows]
    if not all(values) or len(values) != len(set(values)):
        raise AssertionError(f"Field must be populated and unique: {field}")


def assert_valid_uuid(rows: list[dict[str, str]], field: str) -> None:
    for row in rows:
        try:
            UUID(row[field])
        except ValueError as exc:
            raise AssertionError(f"Invalid UUID in {field}: {row[field]}") from exc


def validate_schema(
    receipts: list[dict[str, str]],
    lines: list[dict[str, str]],
    movements: list[dict[str, str]],
) -> None:
    if not receipts or not lines or not movements:
        raise AssertionError("Goods-receipt outputs cannot be empty.")
    if not RECEIPT_COLUMNS.issubset(receipts[0]):
        raise AssertionError(f"Missing receipt columns: {RECEIPT_COLUMNS - set(receipts[0])}")
    if not LINE_COLUMNS.issubset(lines[0]):
        raise AssertionError(f"Missing receipt-line columns: {LINE_COLUMNS - set(lines[0])}")
    if not MOVEMENT_COLUMNS.issubset(movements[0]):
        raise AssertionError(f"Missing movement columns: {MOVEMENT_COLUMNS - set(movements[0])}")


def validate_keys(
    receipts: list[dict[str, str]],
    lines: list[dict[str, str]],
    movements: list[dict[str, str]],
) -> None:
    for rows, field in [
        (receipts, "goods_receipt_id"),
        (receipts, "goods_receipt_number"),
        (receipts, "idempotency_key"),
        (lines, "goods_receipt_line_id"),
        (lines, "goods_receipt_line_number"),
        (lines, "idempotency_key"),
        (movements, "inventory_movement_id"),
        (movements, "inventory_movement_reference"),
        (movements, "idempotency_key"),
    ]:
        assert_unique(rows, field)
    assert_valid_uuid(receipts, "goods_receipt_id")
    assert_valid_uuid(lines, "goods_receipt_line_id")
    assert_valid_uuid(movements, "inventory_movement_id")


def validate_receipt_eligibility(
    receipts: list[dict[str, str]],
    shipments: list[dict[str, str]],
) -> None:
    delivered = {
        row["shipment_id"]: row
        for row in shipments
        if row["shipment_status"] == "DELIVERED"
    }
    receipt_counts = Counter(row["shipment_id"] for row in receipts)
    if set(receipt_counts) != set(delivered):
        raise AssertionError("Receipt coverage does not equal delivered-shipment coverage.")
    if any(count != 1 for count in receipt_counts.values()):
        raise AssertionError("Each delivered shipment must have exactly one goods receipt.")
    if len(receipts) != len(delivered):
        raise AssertionError("Goods-receipt count does not match delivered shipments.")


def validate_header_references(
    receipts: list[dict[str, str]],
    shipments: list[dict[str, str]],
    orders: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    dcs: list[dict[str, str]],
) -> None:
    shipment_by_id = {row["shipment_id"]: row for row in shipments}
    order_ids = {row["purchase_order_id"] for row in orders}
    supplier_ids = {row["supplier_id"] for row in suppliers}
    dc_ids = {row["distribution_centre_id"] for row in dcs}

    for receipt in receipts:
        shipment = shipment_by_id[receipt["shipment_id"]]
        if receipt["source_system"] != "WAREHOUSE_SQL":
            raise AssertionError("Goods receipts must be owned by WAREHOUSE_SQL.")
        if receipt["receipt_status"] != "POSTED":
            raise AssertionError("Generated goods receipts must be POSTED.")
        if receipt["purchase_order_id"] not in order_ids:
            raise AssertionError("Goods receipt references an unknown purchase order.")
        if receipt["supplier_id"] not in supplier_ids:
            raise AssertionError("Goods receipt references an unknown supplier.")
        if receipt["distribution_centre_id"] not in dc_ids:
            raise AssertionError("Goods receipt references an unknown distribution centre.")
        for field in [
            "shipment_number", "purchase_order_id", "purchase_order_number",
            "supplier_id", "supplier_code", "distribution_centre_id",
            "distribution_centre_code", "actual_delivery_at",
        ]:
            if receipt[field] != shipment[field]:
                raise AssertionError(f"Receipt header differs from shipment: {field}")


def validate_receipt_lines(
    receipts: list[dict[str, str]],
    lines: list[dict[str, str]],
    shipment_lines: list[dict[str, str]],
    products: list[dict[str, str]],
) -> None:
    receipt_by_id = {row["goods_receipt_id"]: row for row in receipts}
    shipment_line_by_id = {row["shipment_line_id"]: row for row in shipment_lines}
    product_by_id = {row["product_id"]: row for row in products}
    delivered_line_ids = {
        row["shipment_line_id"]
        for row in shipment_lines
        if Decimal(row["received_quantity"]) > 0
    }
    actual_line_ids = {row["shipment_line_id"] for row in lines}
    if actual_line_ids != delivered_line_ids:
        raise AssertionError("Receipt-line coverage differs from received shipment lines.")

    for line in lines:
        receipt = receipt_by_id.get(line["goods_receipt_id"])
        source = shipment_line_by_id.get(line["shipment_line_id"])
        product = product_by_id.get(line["product_id"])
        if receipt is None or source is None or product is None:
            raise AssertionError("Goods-receipt line has an invalid parent reference.")
        if line["goods_receipt_number"] != receipt["goods_receipt_number"]:
            raise AssertionError("Receipt-line number does not match receipt header.")
        for field in [
            "shipment_id", "shipment_number", "purchase_order_id",
            "purchase_order_number", "purchase_order_line_id", "product_id",
            "product_code", "sku", "storage_type", "unit_of_measure",
        ]:
            if line[field] != source[field]:
                raise AssertionError(f"Receipt line differs from shipment line: {field}")
        received = Decimal(line["received_quantity"])
        accepted = Decimal(line["accepted_quantity"])
        damaged = Decimal(line["damaged_quantity"])
        rejected = Decimal(line["rejected_quantity"])
        if received <= 0 or min(accepted, damaged, rejected) < 0:
            raise AssertionError("Receipt-line quantities are invalid.")
        if received != accepted + damaged + rejected:
            raise AssertionError("Receipt-line quantities do not reconcile.")
        for field in [
            "received_quantity", "accepted_quantity", "damaged_quantity",
            "rejected_quantity",
        ]:
            if Decimal(line[field]) != Decimal(source[field]):
                raise AssertionError(f"Warehouse and Supplier API quantities differ: {field}")
        if line["best_before_date"]:
            if date.fromisoformat(line["best_before_date"]) <= parse_utc(receipt["actual_delivery_at"]).date():
                raise AssertionError("Best-before date must follow delivery date.")


def validate_header_line_totals(
    receipts: list[dict[str, str]],
    lines: list[dict[str, str]],
) -> None:
    lines_by_receipt: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in lines:
        lines_by_receipt[line["goods_receipt_id"]].append(line)
    mappings = {
        "total_received_quantity": "received_quantity",
        "total_accepted_quantity": "accepted_quantity",
        "total_damaged_quantity": "damaged_quantity",
        "total_rejected_quantity": "rejected_quantity",
    }
    for receipt in receipts:
        children = lines_by_receipt[receipt["goods_receipt_id"]]
        if not children:
            raise AssertionError("Goods-receipt header has no lines.")
        for header_field, line_field in mappings.items():
            expected = sum((Decimal(row[line_field]) for row in children), Decimal("0"))
            if Decimal(receipt[header_field]) != expected:
                raise AssertionError(f"Receipt header does not reconcile: {header_field}")
        if Decimal(receipt["total_received_quantity"]) != (
            Decimal(receipt["total_accepted_quantity"])
            + Decimal(receipt["total_damaged_quantity"])
            + Decimal(receipt["total_rejected_quantity"])
        ):
            raise AssertionError("Goods-receipt header quantities do not reconcile.")


def validate_timestamps(receipts: list[dict[str, str]]) -> None:
    for receipt in receipts:
        delivered = parse_utc(receipt["actual_delivery_at"])
        started = parse_utc(receipt["receipt_started_at"])
        completed = parse_utc(receipt["receipt_completed_at"])
        posted = parse_utc(receipt["posted_at"])
        created = parse_utc(receipt["created_at"])
        updated = parse_utc(receipt["updated_at"])
        if not delivered < started < completed < posted:
            raise AssertionError("Goods-receipt operational timestamps are out of order.")
        if created != started or updated != posted:
            raise AssertionError("Goods-receipt audit timestamps are inconsistent.")


def validate_inventory_movements(
    lines: list[dict[str, str]],
    movements: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    movements_by_line: dict[str, list[dict[str, str]]] = defaultdict(list)
    for movement in movements:
        movements_by_line[movement["goods_receipt_line_id"]].append(movement)
        if movement["source_system"] != "WAREHOUSE_SQL":
            raise AssertionError("Inventory movements must be owned by WAREHOUSE_SQL.")
        parse_utc(movement["movement_at"])

    movement_types = config["inventory_movement_types"]
    expected_by_disposition = {
        "accepted": movement_types["accepted"],
        "damaged": movement_types["damaged"],
        "rejected": movement_types["rejected"],
    }

    for line in lines:
        child_movements = movements_by_line[line["goods_receipt_line_id"]]
        by_type = {row["movement_type"]: row for row in child_movements}
        if len(by_type) != len(child_movements):
            raise AssertionError("Duplicate movement type for a goods-receipt line.")
        for disposition, movement_type in expected_by_disposition.items():
            quantity = Decimal(line[f"{disposition}_quantity"])
            movement = by_type.get(movement_type)
            if quantity == 0:
                if movement is not None:
                    raise AssertionError("Zero quantity unexpectedly produced a movement.")
                continue
            if movement is None:
                raise AssertionError(f"Missing inventory movement: {movement_type}")
            if Decimal(movement["movement_quantity"]) != quantity:
                raise AssertionError("Inventory movement quantity differs from receipt line.")
            rule = config["stock_effect_rules"][movement_type]
            expected_available = quantity * Decimal(str(rule["available_quantity_multiplier"]))
            expected_quarantine = quantity * Decimal(str(rule["quarantine_quantity_multiplier"]))
            expected_physical = quantity * Decimal(str(rule["physical_quantity_multiplier"]))
            if Decimal(movement["available_quantity_effect"]) != expected_available:
                raise AssertionError("Available inventory effect is incorrect.")
            if Decimal(movement["quarantine_quantity_effect"]) != expected_quarantine:
                raise AssertionError("Quarantine inventory effect is incorrect.")
            if Decimal(movement["physical_quantity_effect"]) != expected_physical:
                raise AssertionError("Physical inventory effect is incorrect.")


def validate_global_inventory_reconciliation(
    lines: list[dict[str, str]],
    movements: list[dict[str, str]],
) -> None:
    accepted = sum((Decimal(row["accepted_quantity"]) for row in lines), Decimal("0"))
    damaged = sum((Decimal(row["damaged_quantity"]) for row in lines), Decimal("0"))
    rejected = sum((Decimal(row["rejected_quantity"]) for row in lines), Decimal("0"))
    received = sum((Decimal(row["received_quantity"]) for row in lines), Decimal("0"))
    available_effect = sum((Decimal(row["available_quantity_effect"]) for row in movements), Decimal("0"))
    quarantine_effect = sum((Decimal(row["quarantine_quantity_effect"]) for row in movements), Decimal("0"))
    physical_effect = sum((Decimal(row["physical_quantity_effect"]) for row in movements), Decimal("0"))
    if received != accepted + damaged + rejected:
        raise AssertionError("Global receipt quantities do not reconcile.")
    if available_effect != accepted:
        raise AssertionError("Available inventory does not equal accepted quantity.")
    if quarantine_effect != damaged:
        raise AssertionError("Quarantine inventory does not equal damaged quantity.")
    if physical_effect != accepted + damaged:
        raise AssertionError("Physical inventory excludes/contains incorrect dispositions.")


def validate_manifest(
    receipts: list[dict[str, str]],
    lines: list[dict[str, str]],
    movements: list[dict[str, str]],
    manifest: dict[str, Any],
) -> None:
    expected = {
        RECEIPT_PATH.name: (len(receipts), file_sha256(RECEIPT_PATH)),
        RECEIPT_LINE_PATH.name: (len(lines), file_sha256(RECEIPT_LINE_PATH)),
        MOVEMENT_PATH.name: (len(movements), file_sha256(MOVEMENT_PATH)),
    }
    datasets = {row["file_name"]: row for row in manifest.get("datasets", [])}
    if set(datasets) != set(expected):
        raise AssertionError("Goods-receipt manifest dataset list is incorrect.")
    for file_name, (count, digest) in expected.items():
        if int(datasets[file_name]["record_count"]) != count:
            raise AssertionError("Goods-receipt manifest count is incorrect.")
        if datasets[file_name]["sha256"] != digest:
            raise AssertionError("Goods-receipt manifest hash is incorrect.")


def run_all_validations() -> tuple[int, int, int]:
    config = load_json(CONFIG_PATH)
    shipments = load_csv(SHIPMENT_PATH)
    shipment_lines = load_csv(SHIPMENT_LINE_PATH)
    orders = load_csv(PURCHASE_ORDER_PATH)
    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)
    dcs = load_csv(DC_PATH)
    receipts = load_csv(RECEIPT_PATH)
    lines = load_csv(RECEIPT_LINE_PATH)
    movements = load_csv(MOVEMENT_PATH)
    manifest = load_json(MANIFEST_PATH)

    validate_schema(receipts, lines, movements)
    validate_keys(receipts, lines, movements)
    validate_receipt_eligibility(receipts, shipments)
    validate_header_references(receipts, shipments, orders, suppliers, dcs)
    validate_receipt_lines(receipts, lines, shipment_lines, products)
    validate_header_line_totals(receipts, lines)
    validate_timestamps(receipts)
    validate_inventory_movements(lines, movements, config)
    validate_global_inventory_reconciliation(lines, movements)
    validate_manifest(receipts, lines, movements, manifest)
    return len(receipts), len(lines), len(movements)


def main() -> None:
    receipt_count, line_count, movement_count = run_all_validations()
    print("BritMart warehouse goods-receipt validation passed.")
    print(f"Goods receipts validated: {receipt_count}")
    print(f"Goods-receipt lines validated: {line_count}")
    print(f"Inventory movements validated: {movement_count}")
    print("Supplier API-to-Warehouse SQL reconciliation: PASSED")
    print("Available and quarantine inventory reconciliation: PASSED")
    print("Rejected-quantity zero-stock-effect reconciliation: PASSED")


if __name__ == "__main__":
    main()