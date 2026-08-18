"""Generate deterministic BritMart supplier performance events and monthly scores."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "supplier_performance_config.json"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"

SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
PURCHASE_ORDER_LINE_PATH = OUTPUT_DIRECTORY / "purchase_order_lines.csv"
SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
SHIPMENT_LINE_PATH = OUTPUT_DIRECTORY / "shipment_lines.csv"
RECEIPT_PATH = OUTPUT_DIRECTORY / "warehouse_goods_receipts.csv"
RECEIPT_LINE_PATH = OUTPUT_DIRECTORY / "warehouse_goods_receipt_lines.csv"

EVENT_PATH = OUTPUT_DIRECTORY / "supplier_performance_events.csv"
MONTHLY_PATH = OUTPUT_DIRECTORY / "supplier_performance_monthly.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "supplier_performance_manifest.json"

EVENT_FIELDS = [
    "supplier_performance_event_id", "event_number", "supplier_id", "supplier_code",
    "event_type", "event_category", "severity", "source_system", "shipment_id",
    "shipment_number", "purchase_order_id", "purchase_order_number",
    "goods_receipt_id", "goods_receipt_number", "event_occurred_at",
    "performance_month", "metric_name", "metric_actual_value",
    "metric_target_value", "passed_flag", "score_impact", "event_description",
    "idempotency_key", "created_at", "updated_at", "version_number",
]

MONTHLY_FIELDS = [
    "supplier_performance_monthly_id", "supplier_id", "supplier_code",
    "performance_month", "delivery_count", "early_delivery_count",
    "on_time_delivery_count", "late_delivery_count", "evaluated_purchase_order_count",
    "otif_pass_count", "otif_fail_count", "in_full_pass_count", "in_full_fail_count",
    "total_received_quantity", "total_accepted_quantity", "total_damaged_quantity",
    "total_rejected_quantity", "temperature_controlled_delivery_count",
    "temperature_breach_count", "on_time_delivery_rate", "in_full_rate", "otif_rate",
    "accepted_quality_rate", "damage_rate", "rejection_rate",
    "temperature_compliance_rate", "performance_score", "performance_rating",
    "risk_indicator", "idempotency_key", "created_at", "updated_at",
    "version_number",
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
        raise ValueError(f"Timestamp must be UTC: {value}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rate(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("1.000000")
    return (numerator / denominator).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def decimal_text(value: Decimal, places: str = "0.000001") -> str:
    return format(value.quantize(Decimal(places), rounding=ROUND_HALF_UP), "f")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def rating_for_score(score: Decimal, config: dict[str, Any]) -> str:
    thresholds = config["rating_thresholds"]
    for rating in ["EXCELLENT", "GOOD", "WATCH", "HIGH_RISK"]:
        if score >= Decimal(str(thresholds[rating])):
            return rating
    return "HIGH_RISK"


def add_event(
    events: list[dict[str, Any]],
    config: dict[str, Any],
    supplier_id: str,
    supplier_code: str,
    event_type: str,
    occurred_at: datetime,
    source_system: str,
    metric_name: str,
    metric_actual: Decimal,
    metric_target: Decimal,
    passed: bool,
    description: str,
    shipment: dict[str, str] | None = None,
    order: dict[str, str] | None = None,
    receipt: dict[str, str] | None = None,
) -> None:
    definition = config["event_definitions"][event_type]
    shipment = shipment or {}
    order = order or {}
    receipt = receipt or {}
    business_parts = [
        supplier_id,
        shipment.get("shipment_id", ""),
        order.get("purchase_order_id", ""),
        receipt.get("goods_receipt_id", ""),
        event_type,
    ]
    business_key = ":".join(business_parts)
    event_sequence = len(events) + 1
    events.append(
        {
            "supplier_performance_event_id": stable_uuid("supplier-performance-event", business_key),
            "event_number": f"SPE-{event_sequence:09d}",
            "supplier_id": supplier_id,
            "supplier_code": supplier_code,
            "event_type": event_type,
            "event_category": definition["event_category"],
            "severity": definition["severity"],
            "source_system": source_system,
            "shipment_id": shipment.get("shipment_id", ""),
            "shipment_number": shipment.get("shipment_number", ""),
            "purchase_order_id": order.get(
                "purchase_order_id", shipment.get("purchase_order_id", "")
            ),
            "purchase_order_number": order.get(
                "purchase_order_number", shipment.get("purchase_order_number", "")
            ),
            "goods_receipt_id": receipt.get("goods_receipt_id", ""),
            "goods_receipt_number": receipt.get("goods_receipt_number", ""),
            "event_occurred_at": utc_text(occurred_at),
            "performance_month": occurred_at.strftime("%Y-%m"),
            "metric_name": metric_name,
            "metric_actual_value": decimal_text(metric_actual),
            "metric_target_value": decimal_text(metric_target),
            "passed_flag": str(passed).lower(),
            "score_impact": definition["score_impact"],
            "event_description": description,
            "idempotency_key": stable_uuid("supplier-performance-event-idempotency", business_key),
            "created_at": utc_text(occurred_at),
            "updated_at": utc_text(occurred_at),
            "version_number": 1,
        }
    )


def generate() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config = load_json(CONFIG_PATH)
    rules = config["evaluation_rules"]
    weights = config["score_weights"]
    suppliers = {row["supplier_id"]: row for row in load_csv(SUPPLIER_PATH)}
    orders = load_csv(PURCHASE_ORDER_PATH)
    po_lines = load_csv(PURCHASE_ORDER_LINE_PATH)
    shipments = load_csv(SHIPMENT_PATH)
    shipment_lines = load_csv(SHIPMENT_LINE_PATH)
    receipts = load_csv(RECEIPT_PATH)
    receipt_lines = load_csv(RECEIPT_LINE_PATH)

    shipments_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    lines_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    receipt_lines_by_receipt: dict[str, list[dict[str, str]]] = defaultdict(list)
    receipt_by_shipment = {row["shipment_id"]: row for row in receipts}

    for shipment in shipments:
        shipments_by_order[shipment["purchase_order_id"]].append(shipment)
    for line in po_lines:
        lines_by_order[line["purchase_order_id"]].append(line)
    for line in receipt_lines:
        receipt_lines_by_receipt[line["goods_receipt_id"]].append(line)

    events: list[dict[str, Any]] = []
    monthly: dict[tuple[str, str], dict[str, Any]] = {}

    def bucket(supplier_id: str, supplier_code: str, month: str) -> dict[str, Any]:
        key = (supplier_id, month)
        if key not in monthly:
            monthly[key] = {
                "supplier_id": supplier_id,
                "supplier_code": supplier_code,
                "performance_month": month,
                "delivery_count": 0,
                "early_delivery_count": 0,
                "on_time_delivery_count": 0,
                "late_delivery_count": 0,
                "evaluated_purchase_order_count": 0,
                "otif_pass_count": 0,
                "otif_fail_count": 0,
                "in_full_pass_count": 0,
                "in_full_fail_count": 0,
                "total_received_quantity": Decimal("0"),
                "total_accepted_quantity": Decimal("0"),
                "total_damaged_quantity": Decimal("0"),
                "total_rejected_quantity": Decimal("0"),
                "temperature_controlled_delivery_count": 0,
                "temperature_breach_count": 0,
            }
        return monthly[key]

    # Delivery, temperature and warehouse quality events.
    for shipment in sorted(shipments, key=lambda row: row["shipment_number"]):
        if shipment["shipment_status"] != "DELIVERED":
            continue
        occurred_at = parse_utc(shipment["actual_delivery_at"])
        month = occurred_at.strftime("%Y-%m")
        supplier_id = shipment["supplier_id"]
        supplier_code = shipment["supplier_code"]
        if supplier_id not in suppliers:
            raise AssertionError("Shipment references an unknown supplier.")
        summary = bucket(supplier_id, supplier_code, month)
        summary["delivery_count"] += 1

        performance = shipment["delivery_performance_status"]
        event_type = {
            "EARLY": "DELIVERY_EARLY",
            "ON_TIME": "DELIVERY_ON_TIME",
            "LATE": "DELIVERY_LATE",
        }[performance]
        if performance == "EARLY":
            summary["early_delivery_count"] += 1
        elif performance == "ON_TIME":
            summary["on_time_delivery_count"] += 1
        else:
            summary["late_delivery_count"] += 1
        add_event(
            events, config, supplier_id, supplier_code, event_type, occurred_at,
            "SUPPLIER_API", "delivery_on_time_flag",
            Decimal("1") if performance in rules["on_time_delivery_statuses"] else Decimal("0"),
            Decimal("1"), performance in rules["on_time_delivery_statuses"],
            f"Shipment delivery performance classified as {performance}.", shipment=shipment,
        )

        if shipment["temperature_controlled_flag"] == "true":
            summary["temperature_controlled_delivery_count"] += 1
            if shipment["temperature_breach_flag"] == "true":
                summary["temperature_breach_count"] += 1
                add_event(
                    events, config, supplier_id, supplier_code, "TEMPERATURE_BREACH",
                    occurred_at, "SUPPLIER_API", "temperature_compliance_flag",
                    Decimal("0"), Decimal("1"), False,
                    "Recorded shipment temperature exceeded the permitted range.",
                    shipment=shipment,
                )

        receipt = receipt_by_shipment.get(shipment["shipment_id"])
        if receipt is None:
            raise AssertionError("Delivered shipment has no warehouse goods receipt.")
        received = Decimal(receipt["total_received_quantity"])
        accepted = Decimal(receipt["total_accepted_quantity"])
        damaged = Decimal(receipt["total_damaged_quantity"])
        rejected = Decimal(receipt["total_rejected_quantity"])
        posted_at = parse_utc(receipt["posted_at"])
        quality_summary = bucket(
            supplier_id,
            supplier_code,
            posted_at.strftime("%Y-%m"),
        )
        quality_summary[
            "total_received_quantity"
        ] += received
        quality_summary[
            "total_accepted_quantity"
        ] += accepted
        quality_summary[
            "total_damaged_quantity"
        ] += damaged
        quality_summary[
            "total_rejected_quantity"
        ] += rejected
        if damaged > 0:
            add_event(
                events, config, supplier_id, supplier_code, "DAMAGED_GOODS", posted_at,
                "WAREHOUSE_SQL", "damaged_quantity", damaged, Decimal("0"), False,
                "Warehouse inspection identified damaged supplier goods.",
                shipment=shipment, receipt=receipt,
            )
        if rejected > 0:
            add_event(
                events, config, supplier_id, supplier_code, "REJECTED_GOODS", posted_at,
                "WAREHOUSE_SQL", "rejected_quantity", rejected, Decimal("0"), False,
                "Warehouse inspection rejected supplier goods.",
                shipment=shipment, receipt=receipt,
            )

    # PO-level in-full and OTIF evaluation.
    eligible_statuses = set(rules["purchase_order_statuses_eligible_for_otif"])
    shipment_lines_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in shipment_lines:
        shipment_lines_by_order[line["purchase_order_id"]].append(line)

    for order in sorted(orders, key=lambda row: row["purchase_order_number"]):
        if order["purchase_order_status"] not in eligible_statuses:
            continue
        order_shipments = shipments_by_order[order["purchase_order_id"]]
        delivered_shipments = [
            row for row in order_shipments if row["shipment_status"] == "DELIVERED"
        ]
        if not delivered_shipments:
            continue
        occurred_at = max(parse_utc(row["actual_delivery_at"]) for row in delivered_shipments)
        month = occurred_at.strftime("%Y-%m")
        summary = bucket(order["supplier_id"], order["supplier_code"], month)
        summary["evaluated_purchase_order_count"] += 1
        ordered_quantity = sum(
            (Decimal(row["ordered_quantity"]) for row in lines_by_order[order["purchase_order_id"]]),
            Decimal("0"),
        )
        received_quantity = sum(
            (Decimal(row["received_quantity"]) for row in shipment_lines_by_order[order["purchase_order_id"]]),
            Decimal("0"),
        )
        fulfilment_rate = rate(received_quantity, ordered_quantity)
        in_full = fulfilment_rate >= Decimal(str(rules["in_full_tolerance_rate"]))
        on_time = all(
            row["delivery_performance_status"] in rules["on_time_delivery_statuses"]
            for row in delivered_shipments
        )
        otif = in_full and on_time
        summary["in_full_pass_count" if in_full else "in_full_fail_count"] += 1
        summary["otif_pass_count" if otif else "otif_fail_count"] += 1
        if otif:
            event_type = "OTIF_PASS"
        elif not on_time and not in_full:
            event_type = "OTIF_FAIL_LATE_AND_INCOMPLETE"
        elif not on_time:
            event_type = "OTIF_FAIL_LATE"
        else:
            event_type = "OTIF_FAIL_INCOMPLETE"
        add_event(
            events, config, order["supplier_id"], order["supplier_code"], event_type,
            occurred_at, "CROSS_SYSTEM_RECONCILIATION", "otif_flag",
            Decimal("1") if otif else Decimal("0"), Decimal("1"), otif,
            f"PO fulfilment rate {fulfilment_rate}; on-time result {on_time}.",
            order=order,
        )

    generated_at = parse_utc(config["generation_timestamp_utc"])
    monthly_rows: list[dict[str, Any]] = []
    for (supplier_id, month), values in sorted(monthly.items()):
        delivery_count = Decimal(values["delivery_count"])
        on_time_count = Decimal(
            values["early_delivery_count"] + values["on_time_delivery_count"]
        )
        evaluated = Decimal(values["evaluated_purchase_order_count"])
        received = values["total_received_quantity"]
        accepted = values["total_accepted_quantity"]
        damaged = values["total_damaged_quantity"]
        rejected = values["total_rejected_quantity"]
        controlled = Decimal(values["temperature_controlled_delivery_count"])
        breaches = Decimal(values["temperature_breach_count"])
        on_time_rate = rate(on_time_count, delivery_count)
        in_full_rate = rate(Decimal(values["in_full_pass_count"]), evaluated)
        otif_rate = rate(Decimal(values["otif_pass_count"]), evaluated)
        accepted_rate = rate(accepted, received)
        damage_rate = rate(damaged, received) if received else Decimal("0.000000")
        rejection_rate = rate(rejected, received) if received else Decimal("0.000000")
        temperature_rate = Decimal("1.000000") - (
            rate(breaches, controlled) if controlled else Decimal("0.000000")
        )
        score = (
            otif_rate * Decimal(str(weights["otif_rate"]))
            + on_time_rate * Decimal(str(weights["on_time_delivery_rate"]))
            + in_full_rate * Decimal(str(weights["in_full_rate"]))
            + accepted_rate * Decimal(str(weights["accepted_quality_rate"]))
            + temperature_rate * Decimal(str(weights["temperature_compliance_rate"]))
        ) * Decimal("100")
        score = score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rating = rating_for_score(score, config)
        risk_indicator = (
            "CRITICAL" if values["temperature_breach_count"] >= int(config["risk_rules"]["temperature_breach_critical_count"])
            else "HIGH" if rating == "HIGH_RISK"
            else "WATCH" if (
                rating == "WATCH"
                or values["late_delivery_count"] >= int(config["risk_rules"]["late_delivery_warning_count"])
            )
            else "NORMAL"
        )
        business_key = f"{supplier_id}:{month}"
        monthly_rows.append(
            {
                "supplier_performance_monthly_id": stable_uuid("supplier-performance-monthly", business_key),
                "supplier_id": supplier_id,
                "supplier_code": values["supplier_code"],
                "performance_month": month,
                "delivery_count": values["delivery_count"],
                "early_delivery_count": values["early_delivery_count"],
                "on_time_delivery_count": values["on_time_delivery_count"],
                "late_delivery_count": values["late_delivery_count"],
                "evaluated_purchase_order_count": values["evaluated_purchase_order_count"],
                "otif_pass_count": values["otif_pass_count"],
                "otif_fail_count": values["otif_fail_count"],
                "in_full_pass_count": values["in_full_pass_count"],
                "in_full_fail_count": values["in_full_fail_count"],
                "total_received_quantity": decimal_text(received, "0.001"),
                "total_accepted_quantity": decimal_text(accepted, "0.001"),
                "total_damaged_quantity": decimal_text(damaged, "0.001"),
                "total_rejected_quantity": decimal_text(rejected, "0.001"),
                "temperature_controlled_delivery_count": values["temperature_controlled_delivery_count"],
                "temperature_breach_count": values["temperature_breach_count"],
                "on_time_delivery_rate": decimal_text(on_time_rate),
                "in_full_rate": decimal_text(in_full_rate),
                "otif_rate": decimal_text(otif_rate),
                "accepted_quality_rate": decimal_text(accepted_rate),
                "damage_rate": decimal_text(damage_rate),
                "rejection_rate": decimal_text(rejection_rate),
                "temperature_compliance_rate": decimal_text(temperature_rate),
                "performance_score": decimal_text(score, "0.01"),
                "performance_rating": rating,
                "risk_indicator": risk_indicator,
                "idempotency_key": stable_uuid("supplier-performance-monthly-idempotency", business_key),
                "created_at": utc_text(generated_at),
                "updated_at": utc_text(generated_at),
                "version_number": 1,
            }
        )

    return events, monthly_rows


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    events, monthly_rows = generate()
    write_csv(EVENT_PATH, events, EVENT_FIELDS)
    write_csv(MONTHLY_PATH, monthly_rows, MONTHLY_FIELDS)
    config = load_json(CONFIG_PATH)
    manifest = {
        "schema_version": config["schema_version"],
        "generator_name": config["generator_name"],
        "generated_at": config["generation_timestamp_utc"],
        "datasets": [
            {"file_name": EVENT_PATH.name, "record_count": len(events), "sha256": file_sha256(EVENT_PATH)},
            {"file_name": MONTHLY_PATH.name, "record_count": len(monthly_rows), "sha256": file_sha256(MONTHLY_PATH)},
        ],
        "source_record_counts": {
            "suppliers": len(load_csv(SUPPLIER_PATH)),
            "purchase_orders": len(load_csv(PURCHASE_ORDER_PATH)),
            "shipments": len(load_csv(SHIPMENT_PATH)),
            "goods_receipts": len(load_csv(RECEIPT_PATH)),
        },
        "watermark": config["fabric_incremental_extraction"],
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("BritMart supplier performance data generated successfully.")
    print(f"Performance events: {len(events)}")
    print(f"Supplier-month scorecards: {len(monthly_rows)}")
    print(f"Output directory: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()