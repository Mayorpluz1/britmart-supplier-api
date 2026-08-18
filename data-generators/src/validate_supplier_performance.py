"""Validate BritMart supplier performance events and monthly scorecards."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "supplier_performance_config.json"

SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
PURCHASE_ORDER_LINE_PATH = OUTPUT_DIRECTORY / "purchase_order_lines.csv"
SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
SHIPMENT_LINE_PATH = OUTPUT_DIRECTORY / "shipment_lines.csv"
RECEIPT_PATH = OUTPUT_DIRECTORY / "warehouse_goods_receipts.csv"
EVENT_PATH = OUTPUT_DIRECTORY / "supplier_performance_events.csv"
MONTHLY_PATH = OUTPUT_DIRECTORY / "supplier_performance_monthly.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "supplier_performance_manifest.json"

EVENT_COLUMNS = {
    "supplier_performance_event_id", "event_number", "supplier_id", "supplier_code",
    "event_type", "event_category", "severity", "source_system", "shipment_id",
    "shipment_number", "purchase_order_id", "purchase_order_number",
    "goods_receipt_id", "goods_receipt_number", "event_occurred_at",
    "performance_month", "metric_name", "metric_actual_value",
    "metric_target_value", "passed_flag", "score_impact", "event_description",
    "idempotency_key", "created_at", "updated_at", "version_number",
}

MONTHLY_COLUMNS = {
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


def parse_utc(value: str) -> datetime:
    if not value or not value.endswith("Z"):
        raise AssertionError(f"Timestamp is not UTC: {value}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def rate(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("1.000000")
    return (numerator / denominator).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def rating_for_score(score: Decimal, config: dict[str, Any]) -> str:
    thresholds = config["rating_thresholds"]
    for rating in ["EXCELLENT", "GOOD", "WATCH", "HIGH_RISK"]:
        if score >= Decimal(str(thresholds[rating])):
            return rating
    return "HIGH_RISK"


def validate_schema(events: list[dict[str, str]], monthly: list[dict[str, str]]) -> None:
    if not events or not monthly:
        raise AssertionError("Supplier performance outputs cannot be empty.")
    if not EVENT_COLUMNS.issubset(events[0]):
        raise AssertionError(f"Missing event columns: {EVENT_COLUMNS - set(events[0])}")
    if not MONTHLY_COLUMNS.issubset(monthly[0]):
        raise AssertionError(f"Missing monthly columns: {MONTHLY_COLUMNS - set(monthly[0])}")


def validate_keys(events: list[dict[str, str]], monthly: list[dict[str, str]]) -> None:
    for rows, fields in [
        (events, ["supplier_performance_event_id", "event_number", "idempotency_key"]),
        (monthly, ["supplier_performance_monthly_id", "idempotency_key"]),
    ]:
        for field in fields:
            values = [row[field] for row in rows]
            if not all(values) or len(values) != len(set(values)):
                raise AssertionError(f"Performance key is not populated and unique: {field}")
    monthly_business_keys = [(row["supplier_id"], row["performance_month"]) for row in monthly]
    if len(monthly_business_keys) != len(set(monthly_business_keys)):
        raise AssertionError("Duplicate supplier-month scorecard.")
    for row in events:
        UUID(row["supplier_performance_event_id"])
        UUID(row["idempotency_key"])
    for row in monthly:
        UUID(row["supplier_performance_monthly_id"])
        UUID(row["idempotency_key"])


def validate_event_metadata(
    events: list[dict[str, str]], suppliers: list[dict[str, str]], config: dict[str, Any]
) -> None:
    supplier_by_id = {row["supplier_id"]: row for row in suppliers}
    definitions = config["event_definitions"]
    for event in events:
        supplier = supplier_by_id.get(event["supplier_id"])
        if supplier is None or event["supplier_code"] != supplier["supplier_code"]:
            raise AssertionError("Performance event references an invalid supplier.")
        definition = definitions.get(event["event_type"])
        if definition is None:
            raise AssertionError(f"Unsupported performance event: {event['event_type']}")
        if event["event_category"] != definition["event_category"]:
            raise AssertionError("Event category differs from configuration.")
        if event["severity"] != definition["severity"]:
            raise AssertionError("Event severity differs from configuration.")
        if Decimal(event["score_impact"]) != Decimal(str(definition["score_impact"])):
            raise AssertionError("Event score impact differs from configuration.")
        occurred = parse_utc(event["event_occurred_at"])
        if event["performance_month"] != occurred.strftime("%Y-%m"):
            raise AssertionError("Event performance month differs from occurrence month.")
        if parse_utc(event["created_at"]) != occurred or parse_utc(event["updated_at"]) != occurred:
            raise AssertionError("Event audit timestamps differ from occurrence timestamp.")


def validate_delivery_events(
    events: list[dict[str, str]], shipments: list[dict[str, str]]
) -> None:
    delivery_types = {"DELIVERY_EARLY", "DELIVERY_ON_TIME", "DELIVERY_LATE"}
    delivery_events = [row for row in events if row["event_type"] in delivery_types]
    event_by_shipment = {row["shipment_id"]: row for row in delivery_events}
    delivered = [row for row in shipments if row["shipment_status"] == "DELIVERED"]
    if len(event_by_shipment) != len(delivery_events):
        raise AssertionError("A delivered shipment has duplicate delivery events.")
    if set(event_by_shipment) != {row["shipment_id"] for row in delivered}:
        raise AssertionError("Delivery-event coverage differs from delivered shipments.")
    expected_types = {
        "EARLY": "DELIVERY_EARLY",
        "ON_TIME": "DELIVERY_ON_TIME",
        "LATE": "DELIVERY_LATE",
    }
    for shipment in delivered:
        event = event_by_shipment[shipment["shipment_id"]]
        if event["event_type"] != expected_types[shipment["delivery_performance_status"]]:
            raise AssertionError("Delivery event classification is incorrect.")
        if event["shipment_number"] != shipment["shipment_number"]:
            raise AssertionError("Delivery event shipment number mismatch.")
        if event["source_system"] != "SUPPLIER_API":
            raise AssertionError("Delivery event source system is incorrect.")


def validate_temperature_events(
    events: list[dict[str, str]], shipments: list[dict[str, str]]
) -> None:
    actual = {row["shipment_id"] for row in events if row["event_type"] == "TEMPERATURE_BREACH"}
    expected = {
        row["shipment_id"]
        for row in shipments
        if row["shipment_status"] == "DELIVERED"
        and row["temperature_controlled_flag"] == "true"
        and row["temperature_breach_flag"] == "true"
    }
    if actual != expected:
        raise AssertionError("Temperature-breach event coverage is incorrect.")


def validate_quality_events(
    events: list[dict[str, str]], receipts: list[dict[str, str]]
) -> None:
    damaged_events = {row["goods_receipt_id"]: row for row in events if row["event_type"] == "DAMAGED_GOODS"}
    rejected_events = {row["goods_receipt_id"]: row for row in events if row["event_type"] == "REJECTED_GOODS"}
    expected_damaged = {
        row["goods_receipt_id"]: row
        for row in receipts
        if Decimal(row["total_damaged_quantity"]) > 0
    }
    expected_rejected = {
        row["goods_receipt_id"]: row
        for row in receipts
        if Decimal(row["total_rejected_quantity"]) > 0
    }
    if set(damaged_events) != set(expected_damaged):
        raise AssertionError("Damaged-goods event coverage is incorrect.")
    if set(rejected_events) != set(expected_rejected):
        raise AssertionError("Rejected-goods event coverage is incorrect.")
    for receipt_id, event in damaged_events.items():
        if Decimal(event["metric_actual_value"]) != Decimal(expected_damaged[receipt_id]["total_damaged_quantity"]):
            raise AssertionError("Damaged-goods event quantity is incorrect.")
        if event["source_system"] != "WAREHOUSE_SQL":
            raise AssertionError("Quality event source system is incorrect.")
    for receipt_id, event in rejected_events.items():
        if Decimal(event["metric_actual_value"]) != Decimal(expected_rejected[receipt_id]["total_rejected_quantity"]):
            raise AssertionError("Rejected-goods event quantity is incorrect.")


def expected_otif(
    order: dict[str, str],
    order_shipments: list[dict[str, str]],
    po_lines: list[dict[str, str]],
    shipment_lines: list[dict[str, str]],
    config: dict[str, Any],
) -> tuple[str, bool, bool]:
    delivered = [row for row in order_shipments if row["shipment_status"] == "DELIVERED"]
    ordered = sum((Decimal(row["ordered_quantity"]) for row in po_lines), Decimal("0"))
    received = sum((Decimal(row["received_quantity"]) for row in shipment_lines), Decimal("0"))
    fulfilment = rate(received, ordered)
    in_full = fulfilment >= Decimal(str(config["evaluation_rules"]["in_full_tolerance_rate"]))
    on_time = all(
        row["delivery_performance_status"] in config["evaluation_rules"]["on_time_delivery_statuses"]
        for row in delivered
    )
    if in_full and on_time:
        return "OTIF_PASS", in_full, on_time
    if not in_full and not on_time:
        return "OTIF_FAIL_LATE_AND_INCOMPLETE", in_full, on_time
    if not on_time:
        return "OTIF_FAIL_LATE", in_full, on_time
    return "OTIF_FAIL_INCOMPLETE", in_full, on_time


def validate_otif_events(
    events: list[dict[str, str]],
    orders: list[dict[str, str]],
    po_lines: list[dict[str, str]],
    shipments: list[dict[str, str]],
    shipment_lines: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    otif_types = {name for name in config["event_definitions"] if name.startswith("OTIF_")}
    actual = {row["purchase_order_id"]: row for row in events if row["event_type"] in otif_types}
    eligible = set(config["evaluation_rules"]["purchase_order_statuses_eligible_for_otif"])
    eligible_orders = [row for row in orders if row["purchase_order_status"] in eligible]
    if set(actual) != {row["purchase_order_id"] for row in eligible_orders}:
        raise AssertionError("OTIF event coverage differs from eligible purchase orders.")
    shipments_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    po_lines_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    shipment_lines_by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in shipments:
        shipments_by_order[row["purchase_order_id"]].append(row)
    for row in po_lines:
        po_lines_by_order[row["purchase_order_id"]].append(row)
    for row in shipment_lines:
        shipment_lines_by_order[row["purchase_order_id"]].append(row)
    for order in eligible_orders:
        expected_type, in_full, on_time = expected_otif(
            order,
            shipments_by_order[order["purchase_order_id"]],
            po_lines_by_order[order["purchase_order_id"]],
            shipment_lines_by_order[order["purchase_order_id"]],
            config,
        )
        event = actual[order["purchase_order_id"]]
        if event["event_type"] != expected_type:
            raise AssertionError("OTIF event type is incorrect.")
        if (event["passed_flag"] == "true") != (in_full and on_time):
            raise AssertionError("OTIF event pass flag is incorrect.")


def build_expected_monthly(
    shipments: list[dict[str, str]],
    receipts: list[dict[str, str]],
    events: list[dict[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    expected: dict[tuple[str, str], dict[str, Any]] = {}

    def bucket(supplier_id: str, supplier_code: str, month: str) -> dict[str, Any]:
        key = (supplier_id, month)
        if key not in expected:
            expected[key] = {
                "supplier_code": supplier_code,
                "delivery_count": 0,
                "early_delivery_count": 0,
                "on_time_delivery_count": 0,
                "late_delivery_count": 0,
                "evaluated_purchase_order_count": 0,
                "otif_pass_count": 0,
                "otif_fail_count": 0,
                "in_full_pass_count": 0,
                "in_full_fail_count": 0,
                "received": Decimal("0"),
                "accepted": Decimal("0"),
                "damaged": Decimal("0"),
                "rejected": Decimal("0"),
                "controlled": 0,
                "breaches": 0,
            }
        return expected[key]

    for shipment in shipments:
        if shipment["shipment_status"] != "DELIVERED":
            continue
        month = parse_utc(shipment["actual_delivery_at"]).strftime("%Y-%m")
        values = bucket(shipment["supplier_id"], shipment["supplier_code"], month)
        values["delivery_count"] += 1
        performance = shipment["delivery_performance_status"]
        values[
            "early_delivery_count" if performance == "EARLY"
            else "on_time_delivery_count" if performance == "ON_TIME"
            else "late_delivery_count"
        ] += 1
        if shipment["temperature_controlled_flag"] == "true":
            values["controlled"] += 1
            if shipment["temperature_breach_flag"] == "true":
                values["breaches"] += 1

    for receipt in receipts:
        month = parse_utc(receipt["posted_at"]).strftime("%Y-%m")
        values = bucket(receipt["supplier_id"], receipt["supplier_code"], month)
        values["received"] += Decimal(receipt["total_received_quantity"])
        values["accepted"] += Decimal(receipt["total_accepted_quantity"])
        values["damaged"] += Decimal(receipt["total_damaged_quantity"])
        values["rejected"] += Decimal(receipt["total_rejected_quantity"])

    otif_types = {
        "OTIF_PASS", "OTIF_FAIL_LATE", "OTIF_FAIL_INCOMPLETE",
        "OTIF_FAIL_LATE_AND_INCOMPLETE",
    }
    for event in events:
        if event["event_type"] not in otif_types:
            continue
        values = bucket(event["supplier_id"], event["supplier_code"], event["performance_month"])
        values["evaluated_purchase_order_count"] += 1
        passed = event["event_type"] == "OTIF_PASS"
        incomplete = event["event_type"] in {"OTIF_FAIL_INCOMPLETE", "OTIF_FAIL_LATE_AND_INCOMPLETE"}
        values["otif_pass_count" if passed else "otif_fail_count"] += 1
        values["in_full_fail_count" if incomplete else "in_full_pass_count"] += 1
    return expected


def validate_monthly(
    monthly: list[dict[str, str]],
    shipments: list[dict[str, str]],
    receipts: list[dict[str, str]],
    events: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    expected = build_expected_monthly(shipments, receipts, events)
    actual = {(row["supplier_id"], row["performance_month"]): row for row in monthly}
    if set(actual) != set(expected):
        raise AssertionError("Supplier-month scorecard coverage is incorrect.")
    weights = config["score_weights"]
    for key, values in expected.items():
        row = actual[key]
        integer_fields = [
            "delivery_count", "early_delivery_count", "on_time_delivery_count",
            "late_delivery_count", "evaluated_purchase_order_count", "otif_pass_count",
            "otif_fail_count", "in_full_pass_count", "in_full_fail_count",
        ]
        for field in integer_fields:
            if int(row[field]) != int(values[field]):
                raise AssertionError(f"Monthly count is incorrect: {field}")
        if int(row["temperature_controlled_delivery_count"]) != values["controlled"]:
            raise AssertionError("Monthly controlled-delivery count is incorrect.")
        if int(row["temperature_breach_count"]) != values["breaches"]:
            raise AssertionError("Monthly temperature-breach count is incorrect.")
        quantity_map = {
            "total_received_quantity": "received",
            "total_accepted_quantity": "accepted",
            "total_damaged_quantity": "damaged",
            "total_rejected_quantity": "rejected",
        }
        for field, expected_field in quantity_map.items():
            if Decimal(row[field]) != values[expected_field]:
                raise AssertionError(f"Monthly quantity is incorrect: {field}")

        delivery_count = Decimal(values["delivery_count"])
        on_time_count = Decimal(values["early_delivery_count"] + values["on_time_delivery_count"])
        evaluated = Decimal(values["evaluated_purchase_order_count"])
        controlled = Decimal(values["controlled"])
        on_time_rate = rate(on_time_count, delivery_count)
        in_full_rate = rate(Decimal(values["in_full_pass_count"]), evaluated)
        otif_rate = rate(Decimal(values["otif_pass_count"]), evaluated)
        quality_rate = rate(values["accepted"], values["received"])
        damage_rate = rate(values["damaged"], values["received"]) if values["received"] else Decimal("0.000000")
        rejection_rate = rate(values["rejected"], values["received"]) if values["received"] else Decimal("0.000000")
        temperature_rate = Decimal("1.000000") - (
            rate(Decimal(values["breaches"]), controlled) if controlled else Decimal("0.000000")
        )
        expected_rates = {
            "on_time_delivery_rate": on_time_rate,
            "in_full_rate": in_full_rate,
            "otif_rate": otif_rate,
            "accepted_quality_rate": quality_rate,
            "damage_rate": damage_rate,
            "rejection_rate": rejection_rate,
            "temperature_compliance_rate": temperature_rate,
        }
        for field, expected_value in expected_rates.items():
            if Decimal(row[field]) != expected_value:
                raise AssertionError(f"Monthly rate is incorrect: {field}")
        score = (
            otif_rate * Decimal(str(weights["otif_rate"]))
            + on_time_rate * Decimal(str(weights["on_time_delivery_rate"]))
            + in_full_rate * Decimal(str(weights["in_full_rate"]))
            + quality_rate * Decimal(str(weights["accepted_quality_rate"]))
            + temperature_rate * Decimal(str(weights["temperature_compliance_rate"]))
        ) * Decimal("100")
        score = score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if Decimal(row["performance_score"]) != score:
            raise AssertionError("Monthly performance score is incorrect.")
        if row["performance_rating"] != rating_for_score(score, config):
            raise AssertionError("Monthly performance rating is incorrect.")
        rating = rating_for_score(score, config)
        expected_risk = (
            "CRITICAL"
            if values["breaches"]
            >= int(
                config["risk_rules"][
                    "temperature_breach_critical_count"
                ]
            )
            else "HIGH"
            if rating == "HIGH_RISK"
            else "WATCH"
            if (
                rating == "WATCH"
                or values["late_delivery_count"]
                >= int(
                    config["risk_rules"][
                        "late_delivery_warning_count"
                    ]
                )
            )
            else "NORMAL"
        )
        if row["risk_indicator"] != expected_risk:
            raise AssertionError(
                "Monthly supplier risk indicator is incorrect."
            )


def validate_manifest(
    events: list[dict[str, str]], monthly: list[dict[str, str]], manifest: dict[str, Any]
) -> None:
    expected = {
        EVENT_PATH.name: (len(events), file_sha256(EVENT_PATH)),
        MONTHLY_PATH.name: (len(monthly), file_sha256(MONTHLY_PATH)),
    }
    datasets = {row["file_name"]: row for row in manifest.get("datasets", [])}
    if set(datasets) != set(expected):
        raise AssertionError("Performance manifest dataset list is incorrect.")
    for file_name, (count, digest) in expected.items():
        if int(datasets[file_name]["record_count"]) != count:
            raise AssertionError("Performance manifest count is incorrect.")
        if datasets[file_name]["sha256"] != digest:
            raise AssertionError("Performance manifest hash is incorrect.")


def run_all_validations() -> tuple[int, int]:
    config = load_json(CONFIG_PATH)
    suppliers = load_csv(SUPPLIER_PATH)
    orders = load_csv(PURCHASE_ORDER_PATH)
    po_lines = load_csv(PURCHASE_ORDER_LINE_PATH)
    shipments = load_csv(SHIPMENT_PATH)
    shipment_lines = load_csv(SHIPMENT_LINE_PATH)
    receipts = load_csv(RECEIPT_PATH)
    events = load_csv(EVENT_PATH)
    monthly = load_csv(MONTHLY_PATH)
    manifest = load_json(MANIFEST_PATH)

    validate_schema(events, monthly)
    validate_keys(events, monthly)
    validate_event_metadata(events, suppliers, config)
    validate_delivery_events(events, shipments)
    validate_temperature_events(events, shipments)
    validate_quality_events(events, receipts)
    validate_otif_events(events, orders, po_lines, shipments, shipment_lines, config)
    validate_monthly(monthly, shipments, receipts, events, config)
    validate_manifest(events, monthly, manifest)
    return len(events), len(monthly)


def main() -> None:
    event_count, monthly_count = run_all_validations()
    print("BritMart supplier performance validation passed.")
    print(f"Performance events validated: {event_count}")
    print(f"Supplier-month scorecards validated: {monthly_count}")
    print("Delivery and OTIF reconciliation: PASSED")
    print("Warehouse quality reconciliation: PASSED")
    print("Monthly score and rating recalculation: PASSED")


if __name__ == "__main__":
    main()