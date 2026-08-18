"""Generate deterministic BritMart warehouse goods-receipt data."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "goods_receipt_config.json"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"

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

RECEIPT_FIELDS = [
    "goods_receipt_id", "goods_receipt_number", "source_system", "shipment_id",
    "shipment_number", "purchase_order_id", "purchase_order_number", "supplier_id",
    "supplier_code", "distribution_centre_id", "distribution_centre_code",
    "receipt_status", "quality_status", "actual_delivery_at", "receipt_started_at",
    "receipt_completed_at", "posted_at", "dock_door_code", "receiver_code",
    "total_received_quantity", "total_accepted_quantity", "total_damaged_quantity",
    "total_rejected_quantity", "idempotency_key", "created_at", "updated_at",
    "version_number",
]

RECEIPT_LINE_FIELDS = [
    "goods_receipt_line_id", "goods_receipt_line_number", "goods_receipt_id",
    "goods_receipt_number", "shipment_id", "shipment_number", "shipment_line_id",
    "purchase_order_id", "purchase_order_number", "purchase_order_line_id",
    "product_id", "product_code", "sku", "storage_type", "unit_of_measure",
    "received_quantity", "accepted_quantity", "damaged_quantity", "rejected_quantity",
    "quality_status", "quality_inspector_code", "supplier_batch_number",
    "best_before_date", "idempotency_key", "created_at", "updated_at",
    "version_number",
]

MOVEMENT_FIELDS = [
    "inventory_movement_id", "inventory_movement_reference", "source_system",
    "goods_receipt_id", "goods_receipt_number", "goods_receipt_line_id",
    "shipment_id", "shipment_line_id", "purchase_order_id", "purchase_order_line_id",
    "distribution_centre_id", "distribution_centre_code", "product_id", "product_code",
    "sku", "movement_type", "inventory_bucket", "movement_quantity",
    "available_quantity_effect", "quarantine_quantity_effect",
    "physical_quantity_effect", "movement_at", "idempotency_key", "created_at",
    "updated_at", "version_number",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required JSON file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def stable_uuid(entity: str, business_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"britmart:{entity}:{business_key}"))


def parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError(f"Timestamp must use UTC Z notation: {value}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.001")), "f")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt_quality_status(damaged: Decimal, rejected: Decimal) -> str:
    if damaged > 0 and rejected > 0:
        return "PARTIAL_HOLD_AND_REJECTION"
    if damaged > 0:
        return "PARTIAL_QUALITY_HOLD"
    if rejected > 0:
        return "PARTIAL_REJECTION"
    return "PASSED"


def line_quality_status(damaged: Decimal, rejected: Decimal) -> str:
    if damaged > 0 and rejected > 0:
        return "PARTIALLY_DAMAGED_AND_REJECTED"
    if damaged > 0:
        return "PARTIALLY_DAMAGED"
    if rejected > 0:
        return "PARTIALLY_REJECTED"
    return "ACCEPTED"


def best_before_date(product: dict[str, str], delivered_at: datetime) -> str:
    shelf_life = product.get("shelf_life_days", "").strip()
    if not shelf_life:
        return ""
    days = int(Decimal(shelf_life))
    if days <= 0:
        return ""
    return (delivered_at.date() + timedelta(days=days)).isoformat()


def add_movement(
    movements: list[dict[str, Any]],
    config: dict[str, Any],
    receipt: dict[str, Any],
    receipt_line: dict[str, Any],
    quantity: Decimal,
    disposition: str,
    sequence: int,
    movement_at: datetime,
) -> None:
    if quantity <= 0:
        return

    movement_type = config["inventory_movement_types"][disposition]
    stock_rule = config["stock_effect_rules"][movement_type]
    bucket_key = f"{disposition}_inventory_bucket"
    bucket = config["quality_rules"][bucket_key]
    movement_reference = (
        f"{config['business_key_prefixes']['inventory_movement_reference']}"
        f"-{sequence:09d}"
    )
    business_key = f"{receipt_line['goods_receipt_line_id']}:{movement_type}"

    movements.append(
        {
            "inventory_movement_id": stable_uuid("inventory-movement", business_key),
            "inventory_movement_reference": movement_reference,
            "source_system": "WAREHOUSE_SQL",
            "goods_receipt_id": receipt["goods_receipt_id"],
            "goods_receipt_number": receipt["goods_receipt_number"],
            "goods_receipt_line_id": receipt_line["goods_receipt_line_id"],
            "shipment_id": receipt["shipment_id"],
            "shipment_line_id": receipt_line["shipment_line_id"],
            "purchase_order_id": receipt["purchase_order_id"],
            "purchase_order_line_id": receipt_line["purchase_order_line_id"],
            "distribution_centre_id": receipt["distribution_centre_id"],
            "distribution_centre_code": receipt["distribution_centre_code"],
            "product_id": receipt_line["product_id"],
            "product_code": receipt_line["product_code"],
            "sku": receipt_line["sku"],
            "movement_type": movement_type,
            "inventory_bucket": bucket,
            "movement_quantity": decimal_text(quantity),
            "available_quantity_effect": decimal_text(
                quantity * Decimal(str(stock_rule["available_quantity_multiplier"]))
            ),
            "quarantine_quantity_effect": decimal_text(
                quantity * Decimal(str(stock_rule["quarantine_quantity_multiplier"]))
            ),
            "physical_quantity_effect": decimal_text(
                quantity * Decimal(str(stock_rule["physical_quantity_multiplier"]))
            ),
            "movement_at": utc_text(movement_at),
            "idempotency_key": stable_uuid("inventory-movement-idempotency", business_key),
            "created_at": utc_text(movement_at),
            "updated_at": utc_text(movement_at),
            "version_number": 1,
        }
    )


def generate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    config = load_json(CONFIG_PATH)
    rng = random.Random(int(config["random_seed"]))
    shipments = load_csv(SHIPMENT_PATH)
    shipment_lines = load_csv(SHIPMENT_LINE_PATH)
    orders = {row["purchase_order_id"]: row for row in load_csv(PURCHASE_ORDER_PATH)}
    products = {row["product_id"]: row for row in load_csv(PRODUCT_PATH)}
    suppliers = {row["supplier_id"]: row for row in load_csv(SUPPLIER_PATH)}
    dcs = {row["distribution_centre_id"]: row for row in load_csv(DC_PATH)}

    lines_by_shipment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in shipment_lines:
        lines_by_shipment[line["shipment_id"]].append(line)

    receipts: list[dict[str, Any]] = []
    receipt_lines: list[dict[str, Any]] = []
    movements: list[dict[str, Any]] = []
    receipt_sequence = 0
    receipt_line_sequence = 0
    movement_sequence = 0

    timing = config["receipt_timing"]
    operations = config["warehouse_operating_configuration"]

    for shipment in sorted(shipments, key=lambda row: row["shipment_number"]):
        if shipment["shipment_status"] != "DELIVERED":
            continue

        if not shipment["actual_delivery_at"]:
            raise AssertionError("Delivered shipment is missing actual_delivery_at.")
        if shipment["supplier_id"] not in suppliers:
            raise AssertionError("Delivered shipment references an unknown supplier.")
        if shipment["distribution_centre_id"] not in dcs:
            raise AssertionError("Delivered shipment references an unknown distribution centre.")
        if shipment["purchase_order_id"] not in orders:
            raise AssertionError("Delivered shipment references an unknown purchase order.")

        source_lines = sorted(
            lines_by_shipment[shipment["shipment_id"]],
            key=lambda row: (int(row["line_number"]), row["shipment_line_id"]),
        )
        if not source_lines:
            raise AssertionError("Delivered shipment has no shipment lines.")

        receipt_sequence += 1
        receipt_number = (
            f"{config['business_key_prefixes']['goods_receipt_number']}"
            f"-{receipt_sequence:08d}"
        )
        receipt_id = stable_uuid("warehouse-goods-receipt", receipt_number)
        delivered_at = parse_utc(shipment["actual_delivery_at"])
        started_at = delivered_at + timedelta(
            minutes=rng.randint(
                int(timing["minimum_minutes_after_delivery"]),
                int(timing["maximum_minutes_after_delivery"]),
            )
        )
        completed_at = started_at + timedelta(minutes=rng.randint(20, 180))
        posted_at = completed_at + timedelta(
            minutes=rng.randint(1, int(timing["maximum_posting_delay_minutes"]))
        )
        dock = rng.choice(operations["dock_door_codes"])
        receiver = rng.choice(operations["receiver_codes"])

        totals = {
            "received": Decimal("0"),
            "accepted": Decimal("0"),
            "damaged": Decimal("0"),
            "rejected": Decimal("0"),
        }
        pending_receipt_lines: list[dict[str, Any]] = []

        for source_line in source_lines:
            received = Decimal(source_line["received_quantity"])
            accepted = Decimal(source_line["accepted_quantity"])
            damaged = Decimal(source_line["damaged_quantity"])
            rejected = Decimal(source_line["rejected_quantity"])
            if received <= 0:
                raise AssertionError("Delivered shipment line must have received quantity.")
            if received != accepted + damaged + rejected:
                raise AssertionError("Supplier shipment quantities do not reconcile.")

            product = products[source_line["product_id"]]
            receipt_line_sequence += 1
            line_number = (
                f"{config['business_key_prefixes']['goods_receipt_line_number']}"
                f"-{receipt_line_sequence:09d}"
            )
            line_business_key = f"{receipt_id}:{source_line['shipment_line_id']}"
            inspector = rng.choice(operations["quality_inspector_codes"])
            receipt_line = {
                "goods_receipt_line_id": stable_uuid("warehouse-goods-receipt-line", line_business_key),
                "goods_receipt_line_number": line_number,
                "goods_receipt_id": receipt_id,
                "goods_receipt_number": receipt_number,
                "shipment_id": shipment["shipment_id"],
                "shipment_number": shipment["shipment_number"],
                "shipment_line_id": source_line["shipment_line_id"],
                "purchase_order_id": shipment["purchase_order_id"],
                "purchase_order_number": shipment["purchase_order_number"],
                "purchase_order_line_id": source_line["purchase_order_line_id"],
                "product_id": source_line["product_id"],
                "product_code": source_line["product_code"],
                "sku": source_line["sku"],
                "storage_type": source_line["storage_type"],
                "unit_of_measure": source_line["unit_of_measure"],
                "received_quantity": decimal_text(received),
                "accepted_quantity": decimal_text(accepted),
                "damaged_quantity": decimal_text(damaged),
                "rejected_quantity": decimal_text(rejected),
                "quality_status": line_quality_status(damaged, rejected),
                "quality_inspector_code": inspector,
                "supplier_batch_number": (
                    f"BATCH-{shipment['supplier_code']}-{receipt_line_sequence:09d}"
                ),
                "best_before_date": best_before_date(product, delivered_at),
                "idempotency_key": stable_uuid("goods-receipt-line-idempotency", line_business_key),
                "created_at": utc_text(started_at),
                "updated_at": utc_text(posted_at),
                "version_number": 1,
            }
            pending_receipt_lines.append(receipt_line)
            totals["received"] += received
            totals["accepted"] += accepted
            totals["damaged"] += damaged
            totals["rejected"] += rejected

        receipt_business_key = f"WAREHOUSE_SQL:{shipment['shipment_id']}"
        receipt = {
            "goods_receipt_id": receipt_id,
            "goods_receipt_number": receipt_number,
            "source_system": "WAREHOUSE_SQL",
            "shipment_id": shipment["shipment_id"],
            "shipment_number": shipment["shipment_number"],
            "purchase_order_id": shipment["purchase_order_id"],
            "purchase_order_number": shipment["purchase_order_number"],
            "supplier_id": shipment["supplier_id"],
            "supplier_code": shipment["supplier_code"],
            "distribution_centre_id": shipment["distribution_centre_id"],
            "distribution_centre_code": shipment["distribution_centre_code"],
            "receipt_status": config["receipt_status"],
            "quality_status": receipt_quality_status(totals["damaged"], totals["rejected"]),
            "actual_delivery_at": shipment["actual_delivery_at"],
            "receipt_started_at": utc_text(started_at),
            "receipt_completed_at": utc_text(completed_at),
            "posted_at": utc_text(posted_at),
            "dock_door_code": dock,
            "receiver_code": receiver,
            "total_received_quantity": decimal_text(totals["received"]),
            "total_accepted_quantity": decimal_text(totals["accepted"]),
            "total_damaged_quantity": decimal_text(totals["damaged"]),
            "total_rejected_quantity": decimal_text(totals["rejected"]),
            "idempotency_key": stable_uuid("goods-receipt-idempotency", receipt_business_key),
            "created_at": utc_text(started_at),
            "updated_at": utc_text(posted_at),
            "version_number": 1,
        }
        receipts.append(receipt)
        receipt_lines.extend(pending_receipt_lines)

        for receipt_line in pending_receipt_lines:
            movement_at = posted_at
            quantities = {
                "accepted": Decimal(receipt_line["accepted_quantity"]),
                "damaged": Decimal(receipt_line["damaged_quantity"]),
                "rejected": Decimal(receipt_line["rejected_quantity"]),
            }
            for disposition in ["accepted", "damaged", "rejected"]:
                if quantities[disposition] <= 0:
                    continue
                movement_sequence += 1
                add_movement(
                    movements,
                    config,
                    receipt,
                    receipt_line,
                    quantities[disposition],
                    disposition,
                    movement_sequence,
                    movement_at,
                )

    return receipts, receipt_lines, movements


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    receipts, receipt_lines, movements = generate()
    write_csv(RECEIPT_PATH, receipts, RECEIPT_FIELDS)
    write_csv(RECEIPT_LINE_PATH, receipt_lines, RECEIPT_LINE_FIELDS)
    write_csv(MOVEMENT_PATH, movements, MOVEMENT_FIELDS)

    config = load_json(CONFIG_PATH)
    manifest = {
        "schema_version": config["schema_version"],
        "generator_name": config["generator_name"],
        "random_seed": config["random_seed"],
        "generated_at": config["generation_timestamp_utc"],
        "source_ownership": config["source_ownership"],
        "datasets": [
            {
                "file_name": RECEIPT_PATH.name,
                "record_count": len(receipts),
                "sha256": file_sha256(RECEIPT_PATH),
            },
            {
                "file_name": RECEIPT_LINE_PATH.name,
                "record_count": len(receipt_lines),
                "sha256": file_sha256(RECEIPT_LINE_PATH),
            },
            {
                "file_name": MOVEMENT_PATH.name,
                "record_count": len(movements),
                "sha256": file_sha256(MOVEMENT_PATH),
            },
        ],
        "source_record_counts": {
            "shipments": len(load_csv(SHIPMENT_PATH)),
            "shipment_lines": len(load_csv(SHIPMENT_LINE_PATH)),
            "delivered_shipments": sum(
                1 for row in load_csv(SHIPMENT_PATH) if row["shipment_status"] == "DELIVERED"
            ),
        },
        "watermark": config["fabric_incremental_extraction"],
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("BritMart warehouse goods-receipt data generated successfully.")
    print(f"Goods receipts: {len(receipts)}")
    print(f"Goods-receipt lines: {len(receipt_lines)}")
    print(f"Inventory movements: {len(movements)}")
    print(f"Output directory: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()