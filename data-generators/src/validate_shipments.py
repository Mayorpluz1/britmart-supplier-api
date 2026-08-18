"""Validate BritMart supplier shipment data and reconciliations."""

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
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "shipment_config.json"

PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
PURCHASE_ORDER_LINE_PATH = OUTPUT_DIRECTORY / "purchase_order_lines.csv"
PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
DC_PATH = OUTPUT_DIRECTORY / "distribution_centres.csv"
SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
SHIPMENT_LINE_PATH = OUTPUT_DIRECTORY / "shipment_lines.csv"
HISTORY_PATH = OUTPUT_DIRECTORY / "shipment_status_history.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "shipment_manifest.json"

SHIPMENT_COLUMNS = {
    "shipment_id", "shipment_number", "supplier_shipment_reference",
    "purchase_order_id", "purchase_order_number", "supplier_id", "supplier_code",
    "distribution_centre_id", "distribution_centre_code", "carrier_code",
    "carrier_name", "vehicle_type", "shipment_status",
    "delivery_performance_status", "planned_dispatch_at", "actual_dispatch_at",
    "expected_delivery_at", "actual_delivery_at", "total_planned_quantity",
    "total_shipped_quantity", "total_received_quantity", "total_damaged_quantity",
    "total_rejected_quantity", "total_accepted_quantity",
    "temperature_controlled_flag", "minimum_recorded_temperature_celsius",
    "maximum_recorded_temperature_celsius", "temperature_breach_flag",
    "cancellation_reason", "created_at", "updated_at", "version_number",
}

LINE_COLUMNS = {
    "shipment_line_id", "shipment_id", "shipment_number", "purchase_order_id",
    "purchase_order_number", "purchase_order_line_id", "line_number",
    "supplier_product_id", "product_id", "product_code", "sku", "storage_type",
    "unit_of_measure", "order_multiple", "ordered_quantity", "planned_quantity",
    "shipped_quantity", "received_quantity", "damaged_quantity",
    "rejected_quantity", "accepted_quantity", "created_at", "updated_at",
    "version_number",
}

HISTORY_COLUMNS = {
    "shipment_status_history_id", "shipment_id", "shipment_number",
    "sequence_number", "previous_status", "new_status", "status_changed_at",
    "changed_by", "status_reason", "created_at",
}

STATUS_BY_PO_STATUS = {
    "CLOSED": "DELIVERED",
    "PARTIALLY_RECEIVED": "DELIVERED",
    "DISPATCHED": "IN_TRANSIT",
    "CONFIRMED": "PLANNED",
    "APPROVED": "PLANNED",
}

EXPECTED_STATUS_PATHS = {
    "PLANNED": ["PLANNED"],
    "DISPATCHED": ["PLANNED", "DISPATCHED"],
    "IN_TRANSIT": ["PLANNED", "DISPATCHED", "IN_TRANSIT"],
    "DELIVERED": ["PLANNED", "DISPATCHED", "IN_TRANSIT", "DELIVERED"],
    "CANCELLED": ["PLANNED", "CANCELLED"],
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


def parse_timestamp(value: str) -> datetime:
    if not value:
        raise AssertionError("A required timestamp is empty.")
    if not value.endswith("Z"):
        raise AssertionError(f"Timestamp is not UTC: {value}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_uuid(value: str, field_name: str) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise AssertionError(f"Invalid UUID in {field_name}: {value}") from exc


def assert_unique(rows: list[dict[str, str]], column: str) -> None:
    values = [row[column] for row in rows]
    if any(not value for value in values):
        raise AssertionError(f"Empty value found in unique column {column}.")
    if len(values) != len(set(values)):
        raise AssertionError(f"Duplicate values found in {column}.")


def validate_files_and_schema(
    shipments: list[dict[str, str]],
    lines: list[dict[str, str]],
    history: list[dict[str, str]],
) -> None:
    if not shipments or not lines or not history:
        raise AssertionError("Shipment output datasets must not be empty.")
    if not SHIPMENT_COLUMNS.issubset(shipments[0]):
        raise AssertionError(f"Shipment columns missing: {SHIPMENT_COLUMNS - set(shipments[0])}")
    if not LINE_COLUMNS.issubset(lines[0]):
        raise AssertionError(f"Shipment-line columns missing: {LINE_COLUMNS - set(lines[0])}")
    if not HISTORY_COLUMNS.issubset(history[0]):
        raise AssertionError(f"Status-history columns missing: {HISTORY_COLUMNS - set(history[0])}")


def validate_keys(
    shipments: list[dict[str, str]],
    lines: list[dict[str, str]],
    history: list[dict[str, str]],
) -> None:
    for rows, key in [
        (shipments, "shipment_id"),
        (shipments, "shipment_number"),
        (shipments, "supplier_shipment_reference"),
        (lines, "shipment_line_id"),
        (history, "shipment_status_history_id"),
    ]:
        assert_unique(rows, key)
    for row in shipments:
        validate_uuid(row["shipment_id"], "shipment_id")
    for row in lines:
        validate_uuid(row["shipment_line_id"], "shipment_line_id")
    for row in history:
        validate_uuid(row["shipment_status_history_id"], "shipment_status_history_id")


def validate_references(
    shipments: list[dict[str, str]],
    lines: list[dict[str, str]],
    history: list[dict[str, str]],
    orders: list[dict[str, str]],
    po_lines: list[dict[str, str]],
    products: list[dict[str, str]],
    suppliers: list[dict[str, str]],
    dcs: list[dict[str, str]],
) -> None:
    order_by_id = {row["purchase_order_id"]: row for row in orders}
    po_line_by_id = {row["purchase_order_line_id"]: row for row in po_lines}
    product_by_id = {row["product_id"]: row for row in products}
    supplier_by_id = {row["supplier_id"]: row for row in suppliers}
    dc_by_id = {row["distribution_centre_id"]: row for row in dcs}
    shipment_by_id = {row["shipment_id"]: row for row in shipments}

    for shipment in shipments:
        order = order_by_id.get(shipment["purchase_order_id"])
        if order is None:
            raise AssertionError("A shipment references an unknown purchase order.")
        if shipment["purchase_order_number"] != order["purchase_order_number"]:
            raise AssertionError("Shipment purchase-order number mismatch.")
        if shipment["supplier_id"] not in supplier_by_id:
            raise AssertionError("A shipment references an unknown supplier.")
        if shipment["supplier_id"] != order["supplier_id"] or shipment["supplier_code"] != order["supplier_code"]:
            raise AssertionError("Shipment supplier does not match its purchase order.")
        if shipment["distribution_centre_id"] not in dc_by_id:
            raise AssertionError("A shipment references an unknown distribution centre.")
        if shipment["distribution_centre_id"] != order["distribution_centre_id"]:
            raise AssertionError("Shipment destination does not match its purchase order.")
        if shipment["distribution_centre_code"] != order["distribution_centre_code"]:
            raise AssertionError("Shipment destination code mismatch.")

    for line in lines:
        shipment = shipment_by_id.get(line["shipment_id"])
        po_line = po_line_by_id.get(line["purchase_order_line_id"])
        if shipment is None or po_line is None:
            raise AssertionError("A shipment line has an invalid parent reference.")
        if line["shipment_number"] != shipment["shipment_number"]:
            raise AssertionError("Shipment-line shipment number mismatch.")
        if line["purchase_order_id"] != shipment["purchase_order_id"]:
            raise AssertionError("Shipment line and header reference different purchase orders.")
        if line["purchase_order_id"] != po_line["purchase_order_id"]:
            raise AssertionError("Shipment line references the wrong purchase-order line.")
        product = product_by_id.get(line["product_id"])
        if product is None:
            raise AssertionError("A shipment line references an unknown product.")
        if line["product_id"] != po_line["product_id"] or line["sku"] != po_line["sku"]:
            raise AssertionError("Shipment-line product does not match purchase-order line.")
        if line["storage_type"] != product["storage_type"]:
            raise AssertionError("Shipment-line storage type does not match product master.")

    for event in history:
        shipment = shipment_by_id.get(event["shipment_id"])
        if shipment is None or event["shipment_number"] != shipment["shipment_number"]:
            raise AssertionError("A status-history event has an invalid shipment reference.")


def validate_order_coverage(
    shipments: list[dict[str, str]],
    orders: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    """Validate zero-to-many PO-to-shipment relationships."""

    shipments_by_order = defaultdict(list)

    for shipment in shipments:
        shipments_by_order[
            shipment["purchase_order_id"]
        ].append(shipment)

    maximum_shipments = int(
        config["split_shipment"][
            "maximum_shipments_per_order"
        ]
    )
    split_order_count = 0

    expected_eligible = 0

    for order in orders:
        status = order["purchase_order_status"]
        linked = shipments_by_order[
            order["purchase_order_id"]
        ]

        if status in {"DRAFT", "CANCELLED"}:
            if linked:
                raise AssertionError(
                    f"{status} purchase orders "
                    "must not have shipments."
                )
            continue

        expected_status = STATUS_BY_PO_STATUS.get(status)

        if expected_status is None:
            raise AssertionError(
                "Unsupported purchase-order status: "
                f"{status}"
            )

        expected_eligible += 1

        if not (
            1
            <= len(linked)
            <= maximum_shipments
        ):
            raise AssertionError(
                "Eligible purchase orders must have "
                "between one and the configured maximum "
                "number of shipments."
            )

        if len(linked) > 1:
            split_order_count += 1

        if any(
            shipment["shipment_status"]
            != expected_status
            for shipment in linked
        ):
            raise AssertionError(
                "Shipment lifecycle status does not "
                "match purchase-order status."
            )

    if len(shipments) < expected_eligible:
        raise AssertionError(
            "Shipment count is below the eligible "
            "purchase-order count."
        )

    if (
        config["split_shipment"]["enabled"]
        and split_order_count == 0
    ):
        raise AssertionError(
            "Split shipments are enabled but no purchase "
            "order has multiple shipments."
        )


def validate_line_quantities(
    lines: list[dict[str, str]],
    po_lines: list[dict[str, str]],
    orders: list[dict[str, str]],
) -> None:
    """Validate line and cumulative PO quantities."""

    po_line_by_id = {row["purchase_order_line_id"]: row for row in po_lines}
    order_by_id = {
        row["purchase_order_id"]: row
        for row in orders
    }
    cumulative_planned: defaultdict[
        str,
        Decimal,
    ] = defaultdict(lambda: Decimal("0"))
    cumulative_shipped: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    cumulative_received: defaultdict[
        str,
        Decimal,
    ] = defaultdict(lambda: Decimal("0"))
    line_occurrences: Counter[str] = Counter()

    for line in lines:
        ordered = Decimal(line["ordered_quantity"])
        planned = Decimal(line["planned_quantity"])
        shipped = Decimal(line["shipped_quantity"])
        received = Decimal(line["received_quantity"])
        damaged = Decimal(line["damaged_quantity"])
        rejected = Decimal(line["rejected_quantity"])
        accepted = Decimal(line["accepted_quantity"])
        multiple = Decimal(line["order_multiple"])
        source_ordered = Decimal(po_line_by_id[line["purchase_order_line_id"]]["ordered_quantity"])

        if ordered != source_ordered:
            raise AssertionError(
                "Shipment-line ordered quantity does "
                "not match the purchase-order line."
            )

        if planned <= 0 or planned > ordered:
            raise AssertionError(
                "Shipment-line planned quantity must be "
                "positive and cannot exceed ordered "
                "quantity."
            )
        if any(value < 0 for value in [ordered, planned, shipped, received, damaged, rejected, accepted]):
            raise AssertionError("Shipment quantities cannot be negative.")
        if shipped > planned or received > shipped:
            raise AssertionError("Shipment quantity progression is invalid.")
        if damaged + rejected > received:
            raise AssertionError("Damaged and rejected quantities exceed received quantity.")
        if accepted != received - damaged - rejected:
            raise AssertionError("Accepted quantity does not reconcile.")
        if multiple <= 0:
            raise AssertionError("Order multiple must be greater than zero.")
        for value in [planned, shipped, received, damaged, rejected, accepted]:
            if value != 0 and value % multiple != 0:
                raise AssertionError("Shipment quantity is not a valid order-multiple quantity.")
        po_line_id = line["purchase_order_line_id"]
        cumulative_planned[po_line_id] += planned
        cumulative_shipped[po_line_id] += shipped
        cumulative_received[po_line_id] += received
        line_occurrences[po_line_id] += 1

    if not any(
        count > 1
        for count in line_occurrences.values()
    ):
        raise AssertionError(
            "No purchase-order line is represented "
            "across multiple shipments."
        )

    for po_line_id, source_line in po_line_by_id.items():
        order = order_by_id[
            source_line["purchase_order_id"]
        ]
        status = order["purchase_order_status"]
        ordered = Decimal(
            source_line["ordered_quantity"]
        )
        planned = cumulative_planned[po_line_id]
        shipped = cumulative_shipped[po_line_id]
        received = cumulative_received[po_line_id]

        if status in {"DRAFT", "CANCELLED"}:
            if planned or shipped or received:
                raise AssertionError(
                    "Ineligible purchase-order lines "
                    "must not have shipment quantities."
                )
            continue

        if planned > ordered or shipped > ordered:
            raise AssertionError(
                "Cumulative shipment quantity exceeds "
                "ordered quantity."
            )

        if status in {
            "CLOSED",
            "DISPATCHED",
            "CONFIRMED",
            "APPROVED",
        }:
            if planned != ordered:
                raise AssertionError(
                    "Cumulative planned quantity must "
                    "equal ordered quantity."
                )

        if status == "CLOSED":
            if shipped != ordered or received != ordered:
                raise AssertionError(
                    "Closed purchase-order lines must be "
                    "fully shipped and received."
                )
        elif status == "PARTIALLY_RECEIVED":
            if not (
                Decimal("0")
                < received
                == shipped
                <= planned
                <= ordered
            ):
                raise AssertionError(
                    "Partially received quantities do "
                    "not represent an outstanding balance."
                )
        elif status == "DISPATCHED":
            if shipped != ordered or received != 0:
                raise AssertionError(
                    "Dispatched purchase-order lines must "
                    "be fully shipped but not received."
                )
        elif status in {"CONFIRMED", "APPROVED"}:
            if shipped != 0 or received != 0:
                raise AssertionError(
                    "Planned purchase-order shipments "
                    "cannot have shipped or received "
                    "quantities."
                )

    partial_order_totals: defaultdict[
        str,
        dict[str, Decimal],
    ] = defaultdict(
        lambda: {
            "ordered": Decimal("0"),
            "shipped": Decimal("0"),
        }
    )

    for po_line_id, source_line in po_line_by_id.items():
        order_id = source_line["purchase_order_id"]
        order = order_by_id[order_id]

        if (
            order["purchase_order_status"]
            == "PARTIALLY_RECEIVED"
        ):
            partial_order_totals[order_id][
                "ordered"
            ] += Decimal(
                source_line["ordered_quantity"]
            )
            partial_order_totals[order_id][
                "shipped"
            ] += cumulative_shipped[po_line_id]

    for totals in partial_order_totals.values():
        if not (
            Decimal("0")
            < totals["shipped"]
            < totals["ordered"]
        ):
            raise AssertionError(
                "A partially received purchase order "
                "does not retain an outstanding quantity."
            )


def validate_header_line_reconciliation(
    shipments: list[dict[str, str]], lines: list[dict[str, str]]
) -> None:
    lines_by_shipment = defaultdict(list)
    for line in lines:
        lines_by_shipment[line["shipment_id"]].append(line)
    mappings = {
        "total_planned_quantity": "planned_quantity",
        "total_shipped_quantity": "shipped_quantity",
        "total_received_quantity": "received_quantity",
        "total_damaged_quantity": "damaged_quantity",
        "total_rejected_quantity": "rejected_quantity",
        "total_accepted_quantity": "accepted_quantity",
    }
    for shipment in shipments:
        child_lines = lines_by_shipment[shipment["shipment_id"]]
        if not child_lines:
            raise AssertionError("A shipment header has no shipment lines.")
        for header_column, line_column in mappings.items():
            expected = sum((Decimal(row[line_column]) for row in child_lines), Decimal("0"))
            if Decimal(shipment[header_column]) != expected:
                raise AssertionError(f"Shipment header total does not reconcile: {header_column}")


def validate_status_and_dates(
    shipments: list[dict[str, str]], lines: list[dict[str, str]]
) -> None:
    lines_by_shipment = defaultdict(list)
    for line in lines:
        lines_by_shipment[line["shipment_id"]].append(line)
    valid_statuses = set(EXPECTED_STATUS_PATHS)
    for shipment in shipments:
        status = shipment["shipment_status"]
        if status not in valid_statuses:
            raise AssertionError(f"Invalid shipment status: {status}")
        planned = parse_timestamp(shipment["planned_dispatch_at"])
        expected = parse_timestamp(shipment["expected_delivery_at"])
        created = parse_timestamp(shipment["created_at"])
        updated = parse_timestamp(shipment["updated_at"])
        actual_dispatch = parse_timestamp(shipment["actual_dispatch_at"]) if shipment["actual_dispatch_at"] else None
        actual_delivery = parse_timestamp(shipment["actual_delivery_at"]) if shipment["actual_delivery_at"] else None
        if created > planned or updated < created or expected < planned:
            raise AssertionError("Shipment timestamp ordering is invalid.")
        if status == "PLANNED":
            if actual_dispatch or actual_delivery:
                raise AssertionError("Planned shipments cannot have actual operational timestamps.")
        else:
            if actual_dispatch is None:
                raise AssertionError("Dispatched shipments require actual_dispatch_at.")
        if status == "DELIVERED":
            if actual_delivery is None or shipment["delivery_performance_status"] not in {"EARLY", "ON_TIME", "LATE"}:
                raise AssertionError("Delivered shipment date/performance fields are invalid.")
            if actual_dispatch and actual_delivery <= actual_dispatch:
                raise AssertionError("Delivery cannot occur before dispatch.")
        elif actual_delivery or shipment["delivery_performance_status"] != "NOT_APPLICABLE":
            raise AssertionError("Undelivered shipment contains delivery completion fields.")

        child_lines = lines_by_shipment[shipment["shipment_id"]]
        if status == "PLANNED" and any(Decimal(row["shipped_quantity"]) != 0 for row in child_lines):
            raise AssertionError("Planned shipment has shipped quantities.")
        if status == "IN_TRANSIT" and any(Decimal(row["received_quantity"]) != 0 for row in child_lines):
            raise AssertionError("In-transit shipment has received quantities.")


def validate_temperature(shipments: list[dict[str, str]]) -> None:
    for shipment in shipments:
        controlled = shipment["temperature_controlled_flag"] == "true"
        if controlled:
            if not shipment["minimum_recorded_temperature_celsius"] or not shipment["maximum_recorded_temperature_celsius"]:
                raise AssertionError("Temperature-controlled shipment lacks readings.")
            minimum = Decimal(shipment["minimum_recorded_temperature_celsius"])
            maximum = Decimal(shipment["maximum_recorded_temperature_celsius"])
            if minimum > maximum:
                raise AssertionError("Minimum temperature exceeds maximum temperature.")
            if shipment["vehicle_type"] not in {
                "REFRIGERATED_LORRY", "FROZEN_TRAILER", "MIXED_TEMPERATURE_TRAILER"
            }:
                raise AssertionError("Temperature-controlled shipment uses an invalid vehicle.")
        elif shipment["minimum_recorded_temperature_celsius"] or shipment["maximum_recorded_temperature_celsius"]:
            raise AssertionError("Ambient shipment unexpectedly contains temperature readings.")


def validate_history(
    shipments: list[dict[str, str]], history: list[dict[str, str]]
) -> None:
    history_by_shipment = defaultdict(list)
    for event in history:
        history_by_shipment[event["shipment_id"]].append(event)
        parse_timestamp(event["status_changed_at"])
        parse_timestamp(event["created_at"])
    for shipment in shipments:
        events = sorted(history_by_shipment[shipment["shipment_id"]], key=lambda row: int(row["sequence_number"]))
        expected_path = EXPECTED_STATUS_PATHS[shipment["shipment_status"]]
        actual_path = [event["new_status"] for event in events]
        if actual_path != expected_path:
            raise AssertionError("Shipment status-history path is invalid.")
        if [int(event["sequence_number"]) for event in events] != list(range(1, len(events) + 1)):
            raise AssertionError("Shipment history sequence numbers are not contiguous.")
        previous = ""
        for event in events:
            if event["previous_status"] != previous:
                raise AssertionError("Shipment history previous-status chain is invalid.")
            previous = event["new_status"]


def validate_manifest(
    shipments: list[dict[str, str]],
    lines: list[dict[str, str]],
    history: list[dict[str, str]],
    manifest: dict[str, Any],
) -> None:
    expected = {
        SHIPMENT_PATH.name: (len(shipments), file_sha256(SHIPMENT_PATH)),
        SHIPMENT_LINE_PATH.name: (len(lines), file_sha256(SHIPMENT_LINE_PATH)),
        HISTORY_PATH.name: (len(history), file_sha256(HISTORY_PATH)),
    }
    datasets = {row["file_name"]: row for row in manifest.get("datasets", [])}
    if set(datasets) != set(expected):
        raise AssertionError("Shipment manifest dataset list is incorrect.")
    for file_name, (count, digest) in expected.items():
        if int(datasets[file_name]["record_count"]) != count:
            raise AssertionError("Shipment manifest record count mismatch.")
        if datasets[file_name]["sha256"] != digest:
            raise AssertionError("Shipment manifest hash mismatch.")


def run_all_validations() -> tuple[int, int, int]:
    config = load_json(CONFIG_PATH)
    shipments = load_csv(SHIPMENT_PATH)
    lines = load_csv(SHIPMENT_LINE_PATH)
    history = load_csv(HISTORY_PATH)
    orders = load_csv(PURCHASE_ORDER_PATH)
    po_lines = load_csv(PURCHASE_ORDER_LINE_PATH)
    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)
    dcs = load_csv(DC_PATH)
    manifest = load_json(MANIFEST_PATH)

    validate_files_and_schema(shipments, lines, history)
    validate_keys(shipments, lines, history)
    validate_references(shipments, lines, history, orders, po_lines, products, suppliers, dcs)
    validate_order_coverage(
        shipments,
        orders,
        config,
    )
    validate_line_quantities(
        lines,
        po_lines,
        orders,
    )
    validate_header_line_reconciliation(shipments, lines)
    validate_status_and_dates(shipments, lines)
    validate_temperature(shipments)
    validate_history(shipments, history)
    validate_manifest(shipments, lines, history, manifest)
    return len(shipments), len(lines), len(history)


def main() -> None:
    shipment_count, line_count, history_count = run_all_validations()
    print("BritMart supplier shipment validation passed.")
    print(f"Shipments validated: {shipment_count}")
    print(f"Shipment lines validated: {line_count}")
    print(f"Status-history events validated: {history_count}")
    print("Purchase-order-to-shipment reconciliation: PASSED")
    print("Header-to-line quantity reconciliation: PASSED")
    print("Master-data referential integrity: PASSED")


if __name__ == "__main__":
    main()