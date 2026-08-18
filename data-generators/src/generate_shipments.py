


"""Generate deterministic BritMart supplier shipment data."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "shipment_config.json"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"

PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
PURCHASE_ORDER_LINE_PATH = OUTPUT_DIRECTORY / "purchase_order_lines.csv"
PRODUCT_PATH = OUTPUT_DIRECTORY / "products.csv"
SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
DC_PATH = OUTPUT_DIRECTORY / "distribution_centres.csv"

SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
SHIPMENT_LINE_PATH = OUTPUT_DIRECTORY / "shipment_lines.csv"
STATUS_HISTORY_PATH = OUTPUT_DIRECTORY / "shipment_status_history.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "shipment_manifest.json"

SHIPMENT_FIELDS = [
    "shipment_id", "shipment_number", "supplier_shipment_reference",
    "purchase_order_id", "purchase_order_number", "supplier_id",
    "supplier_code", "distribution_centre_id", "distribution_centre_code",
    "carrier_code", "carrier_name", "vehicle_type", "shipment_status",
    "delivery_performance_status", "planned_dispatch_at", "actual_dispatch_at",
    "expected_delivery_at", "actual_delivery_at", "total_planned_quantity",
    "total_shipped_quantity", "total_received_quantity", "total_damaged_quantity",
    "total_rejected_quantity", "total_accepted_quantity", "temperature_controlled_flag",
    "minimum_recorded_temperature_celsius", "maximum_recorded_temperature_celsius",
    "temperature_breach_flag", "cancellation_reason", "created_at", "updated_at",
    "version_number",
]

SHIPMENT_LINE_FIELDS = [
    "shipment_line_id", "shipment_id", "shipment_number", "purchase_order_id",
    "purchase_order_number", "purchase_order_line_id", "line_number",
    "supplier_product_id", "product_id", "product_code", "sku", "storage_type",
    "unit_of_measure", "order_multiple", "ordered_quantity", "planned_quantity",
    "shipped_quantity", "received_quantity", "damaged_quantity", "rejected_quantity",
    "accepted_quantity", "created_at", "updated_at", "version_number",
]

HISTORY_FIELDS = [
    "shipment_status_history_id", "shipment_id", "shipment_number",
    "sequence_number", "previous_status", "new_status", "status_changed_at",
    "changed_by", "status_reason", "created_at",
]

STATUS_BY_PO_STATUS = {
    "CLOSED": "DELIVERED",
    "PARTIALLY_RECEIVED": "DELIVERED",
    "DISPATCHED": "IN_TRANSIT",
    "CONFIRMED": "PLANNED",
    "APPROVED": "PLANNED",
}

STATUS_PATHS = {
    "PLANNED": ["PLANNED"],
    "DISPATCHED": ["PLANNED", "DISPATCHED"],
    "IN_TRANSIT": ["PLANNED", "DISPATCHED", "IN_TRANSIT"],
    "DELIVERED": ["PLANNED", "DISPATCHED", "IN_TRANSIT", "DELIVERED"],
    "CANCELLED": ["PLANNED", "CANCELLED"],
}


def load_json(path: Path) -> dict[str, Any]:
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


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.001")), "f")


def quantise_to_multiple(quantity: Decimal, multiple: Decimal) -> Decimal:
    if multiple <= 0:
        raise ValueError("Order multiple must be greater than zero.")
    units = (quantity / multiple).to_integral_value(rounding=ROUND_DOWN)
    return units * multiple


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def choose_carrier(config: dict[str, Any], rng: random.Random, controlled: bool) -> dict[str, str]:
    carriers = config["carrier_configuration"]
    if controlled:
        suitable = [c for c in carriers if c["service_level"] == "TEMPERATURE_CONTROLLED"]
        if suitable:
            return rng.choice(suitable)
    return rng.choice(carriers)


def choose_vehicle(rng: random.Random, controlled: bool, storage_types: set[str]) -> str:
    if "FROZEN" in storage_types and "CHILLED" in storage_types:
        return "MIXED_TEMPERATURE_TRAILER"
    if "FROZEN" in storage_types:
        return "FROZEN_TRAILER"
    if "CHILLED" in storage_types:
        return "REFRIGERATED_LORRY"
    return rng.choice(["ARTICULATED_LORRY", "RIGID_LORRY"])


def temperature_values(
    config: dict[str, Any], rng: random.Random, storage_types: set[str]
) -> tuple[str, str, str]:
    controlled = bool(storage_types & {"CHILLED", "FROZEN"})
    if not controlled:
        return "", "", "false"
    storage = "FROZEN" if "FROZEN" in storage_types else "CHILLED"
    rules = config["temperature_rules"][storage]
    low = Decimal(str(rules["minimum_temperature_celsius"]))
    high = Decimal(str(rules["maximum_temperature_celsius"]))
    breach = rng.random() < float(rules["breach_probability"])
    if breach:
        recorded_low = low - Decimal("2.0")
        recorded_high = high + Decimal("2.0")
    else:
        span = high - low
        recorded_low = low + span * Decimal(str(rng.uniform(0.05, 0.30)))
        recorded_high = low + span * Decimal(str(rng.uniform(0.70, 0.95)))
    return f"{recorded_low:.2f}", f"{recorded_high:.2f}", str(breach).lower()


def allocate_quantity(
    total: Decimal,
    multiple: Decimal,
    shipment_count: int,
    anchor_index: int,
    split_line: bool,
    rng: random.Random,
) -> list[Decimal]:
    """Allocate a quantity without breaking the order multiple."""

    total_units = int((total / multiple).to_integral_value(rounding=ROUND_DOWN))
    allocations = [0] * shipment_count

    if total_units <= 0:
        return [Decimal("0")] * shipment_count

    if shipment_count == 1:
        allocations[0] = total_units
    elif split_line and total_units >= 2:
        active_count = min(shipment_count, total_units)
        active_indexes = list(range(active_count))
        rng.shuffle(active_indexes)

        for index in active_indexes:
            allocations[index] = 1

        for _ in range(total_units - active_count):
            allocations[rng.randrange(active_count)] += 1
    else:
        allocations[anchor_index % shipment_count] = total_units

    return [
        Decimal(units) * multiple
        for units in allocations
    ]


def target_quantity(
    po_status: str,
    ordered: Decimal,
    multiple: Decimal,
    config: dict[str, Any],
    rng: random.Random,
) -> Decimal:
    """Return the cumulative quantity represented by shipments."""

    if po_status != "PARTIALLY_RECEIVED":
        return ordered

    rules = config["quantity_rules"]
    rate = Decimal(
        str(
            rng.uniform(
                float(rules["partial_shipment_minimum_rate"]),
                float(rules["partial_shipment_maximum_rate"]),
            )
        )
    )
    target = quantise_to_multiple(
        ordered * rate,
        multiple,
    )

    if ordered <= multiple:
        return ordered

    return max(
        multiple,
        min(target, ordered - multiple),
    )


def receipt_quantities(
    shipped: Decimal,
    multiple: Decimal,
    config: dict[str, Any],
    rng: random.Random,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Calculate received, damaged, rejected and accepted quantities."""

    received = shipped
    damaged = Decimal("0")
    rejected = Decimal("0")
    qrules = config["quantity_rules"]
    if rng.random() < float(qrules["damaged_line_rate"]):
        damaged = quantise_to_multiple(
            received * Decimal(str(rng.uniform(0.01, float(qrules["maximum_damaged_quantity_rate"])))),
            multiple,
        )
        if damaged == 0 and received >= multiple:
            damaged = multiple
    remaining = received - damaged
    if remaining > 0 and rng.random() < float(qrules["rejected_line_rate"]):
        rejected = quantise_to_multiple(
            remaining * Decimal(str(rng.uniform(0.01, float(qrules["maximum_rejected_quantity_rate"])))),
            multiple,
        )
        if rejected == 0 and remaining >= multiple:
            rejected = multiple
    accepted = received - damaged - rejected
    return received, damaged, rejected, accepted


def delivery_times(
    order: dict[str, str], shipment_status: str, config: dict[str, Any], rng: random.Random
) -> tuple[datetime, datetime | None, datetime, datetime | None, str]:
    timing = config["shipment_timing"]
    order_date = parse_date(order["order_date"])
    required_date = parse_date(order["required_delivery_date"])
    dispatch_date = order_date + timedelta(days=rng.randint(
        int(timing["minimum_dispatch_delay_days"]), int(timing["maximum_dispatch_delay_days"])
    ))
    dispatch_date = min(dispatch_date, required_date)
    planned_dispatch = datetime.combine(dispatch_date, time(6, 0), tzinfo=timezone.utc)
    actual_dispatch = None if shipment_status == "PLANNED" else planned_dispatch + timedelta(hours=rng.randint(0, 8))
    expected_delivery = datetime.combine(required_date, time(12, 0), tzinfo=timezone.utc)
    actual_delivery: datetime | None = None
    performance = "NOT_APPLICABLE"
    if shipment_status == "DELIVERED":
        draw = rng.random()
        distribution = config["delivery_performance_distribution"]
        if draw < float(distribution["EARLY"]):
            days = -rng.randint(int(timing["early_delivery_minimum_days"]), int(timing["early_delivery_maximum_days"]))
            performance = "EARLY"
        elif draw < float(distribution["EARLY"]) + float(distribution["ON_TIME"]):
            days = 0
            performance = "ON_TIME"
        else:
            days = rng.randint(int(timing["late_delivery_minimum_days"]), int(timing["late_delivery_maximum_days"]))
            performance = "LATE"
        actual_delivery = expected_delivery + timedelta(days=days, hours=rng.randint(-2, 4))
        if actual_dispatch and actual_delivery <= actual_dispatch:
            actual_delivery = actual_dispatch + timedelta(days=1)
    return planned_dispatch, actual_dispatch, expected_delivery, actual_delivery, performance


def generate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate headers, lines and lifecycle history with split fulfilment."""

    config = load_json(CONFIG_PATH)
    rng = random.Random(int(config["random_seed"]))
    orders = load_csv(PURCHASE_ORDER_PATH)
    order_lines = load_csv(PURCHASE_ORDER_LINE_PATH)
    products = {
        row["product_id"]: row
        for row in load_csv(PRODUCT_PATH)
    }
    suppliers = {
        row["supplier_id"]: row
        for row in load_csv(SUPPLIER_PATH)
    }
    dcs = {
        row["distribution_centre_id"]: row
        for row in load_csv(DC_PATH)
    }

    lines_by_order: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for line in order_lines:
        lines_by_order[
            line["purchase_order_id"]
        ].append(line)

    shipments: list[dict[str, Any]] = []
    shipment_lines: list[dict[str, Any]] = []
    histories: list[dict[str, Any]] = []
    shipment_sequence = 0

    split_config = config["split_shipment"]
    split_rate = float(
        split_config["eligible_order_rate"]
    )
    minimum_split = int(
        split_config[
            "minimum_shipments_per_order"
        ]
    )
    maximum_split = int(
        split_config[
            "maximum_shipments_per_order"
        ]
    )

    for order in sorted(
        orders,
        key=lambda row: row[
            "purchase_order_number"
        ],
    ):
        po_status = order[
            "purchase_order_status"
        ]

        if po_status in {"DRAFT", "CANCELLED"}:
            continue

        shipment_status = (
            STATUS_BY_PO_STATUS.get(po_status)
        )

        if shipment_status is None:
            raise ValueError(
                "Unsupported purchase-order status: "
                f"{po_status}"
            )

        source_lines = sorted(
            lines_by_order[
                order["purchase_order_id"]
            ],
            key=lambda row: int(
                row["line_number"]
            ),
        )

        if not source_lines:
            raise AssertionError(
                "Eligible purchase order has no lines."
            )

        is_split = (
            bool(split_config["enabled"])
            and rng.random() < split_rate
        )

        shipment_count = (
            rng.randint(
                minimum_split,
                maximum_split,
            )
            if is_split
            else 1
        )

        allocation_by_line: dict[
            str,
            list[Decimal],
        ] = {}

        for line_index, line in enumerate(
            source_lines
        ):
            ordered = Decimal(
                line["ordered_quantity"]
            )
            multiple = Decimal(
                line["order_multiple"]
            )
            target = target_quantity(
                po_status,
                ordered,
                multiple,
                config,
                rng,
            )

            # At least one product line is divided between
            # shipments where its quantity permits it.
            split_line = (
                is_split
                and (
                    line_index == 0
                    or rng.random() < 0.30
                )
            )

            allocation_by_line[
                line["purchase_order_line_id"]
            ] = allocate_quantity(
                target,
                multiple,
                shipment_count,
                line_index,
                split_line,
                rng,
            )

        shipment_contexts: list[
            dict[str, Any]
        ] = []

        for shipment_index in range(
            shipment_count
        ):
            shipment_sequence += 1
            shipment_number = (
                f"{config['shipment_reference_prefix']}"
                f"-{shipment_sequence:07d}"
            )
            shipment_id = stable_uuid(
                "shipment",
                shipment_number,
            )

            allocated_source_lines = [
                line
                for line in source_lines
                if allocation_by_line[
                    line["purchase_order_line_id"]
                ][shipment_index] > 0
            ]

            if not allocated_source_lines:
                raise AssertionError(
                    "Split-shipment allocation produced "
                    "an empty shipment."
                )

            storage_types = {
                products[
                    line["product_id"]
                ]["storage_type"]
                for line in allocated_source_lines
            }
            controlled = bool(
                storage_types
                & {"CHILLED", "FROZEN"}
            )
            carrier = choose_carrier(
                config,
                rng,
                controlled,
            )
            vehicle_type = choose_vehicle(
                rng,
                controlled,
                storage_types,
            )

            (
                planned_dispatch,
                actual_dispatch,
                expected_delivery,
                actual_delivery,
                performance,
            ) = delivery_times(
                order,
                shipment_status,
                config,
                rng,
            )

            # Split shipments occur sequentially rather
            # than sharing identical operational times.
            offset = timedelta(
                days=shipment_index
            )
            planned_dispatch += offset
            expected_delivery += offset

            if actual_dispatch:
                actual_dispatch += offset

            if actual_delivery:
                actual_delivery += offset

            created_at = (
                planned_dispatch
                - timedelta(days=1)
            )
            updated_at = (
                actual_delivery
                or actual_dispatch
                or planned_dispatch
            )
            totals = {
                key: Decimal("0")
                for key in [
                    "planned",
                    "shipped",
                    "received",
                    "damaged",
                    "rejected",
                    "accepted",
                ]
            }

            shipment_contexts.append(
                {
                    "shipment_index": (
                        shipment_index
                    ),
                    "shipment_id": shipment_id,
                    "shipment_number": (
                        shipment_number
                    ),
                    "storage_types": storage_types,
                    "controlled": controlled,
                    "carrier": carrier,
                    "vehicle_type": vehicle_type,
                    "planned_dispatch": (
                        planned_dispatch
                    ),
                    "actual_dispatch": (
                        actual_dispatch
                    ),
                    "expected_delivery": (
                        expected_delivery
                    ),
                    "actual_delivery": (
                        actual_delivery
                    ),
                    "performance": performance,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "totals": totals,
                }
            )

        for line in source_lines:
            ordered = Decimal(
                line["ordered_quantity"]
            )
            multiple = Decimal(
                line["order_multiple"]
            )
            allocations = allocation_by_line[
                line["purchase_order_line_id"]
            ]

            for shipment_index, allocated in enumerate(
                allocations
            ):
                if allocated <= 0:
                    continue

                context = shipment_contexts[
                    shipment_index
                ]

                if po_status in {
                    "APPROVED",
                    "CONFIRMED",
                }:
                    planned = allocated
                    shipped = Decimal("0")
                    received = Decimal("0")
                    damaged = Decimal("0")
                    rejected = Decimal("0")
                    accepted = Decimal("0")
                elif po_status == "DISPATCHED":
                    planned = allocated
                    shipped = allocated
                    received = Decimal("0")
                    damaged = Decimal("0")
                    rejected = Decimal("0")
                    accepted = Decimal("0")
                else:
                    planned = allocated
                    shipped = allocated
                    (
                        received,
                        damaged,
                        rejected,
                        accepted,
                    ) = receipt_quantities(
                        shipped,
                        multiple,
                        config,
                        rng,
                    )

                for name, value in zip(
                    context["totals"],
                    [
                        planned,
                        shipped,
                        received,
                        damaged,
                        rejected,
                        accepted,
                    ],
                ):
                    context["totals"][name] += value

                shipment_lines.append(
                    {
                        "shipment_line_id": stable_uuid(
                            "shipment-line",
                            (
                                f"{context['shipment_number']}:"
                                f"{line['purchase_order_line_id']}"
                            ),
                        ),
                        "shipment_id": (
                            context["shipment_id"]
                        ),
                        "shipment_number": (
                            context["shipment_number"]
                        ),
                        "purchase_order_id": (
                            order["purchase_order_id"]
                        ),
                        "purchase_order_number": (
                            order[
                                "purchase_order_number"
                            ]
                        ),
                        "purchase_order_line_id": (
                            line[
                                "purchase_order_line_id"
                            ]
                        ),
                        "line_number": (
                            line["line_number"]
                        ),
                        "supplier_product_id": (
                            line["supplier_product_id"]
                        ),
                        "product_id": (
                            line["product_id"]
                        ),
                        "product_code": (
                            line["product_code"]
                        ),
                        "sku": line["sku"],
                        "storage_type": products[
                            line["product_id"]
                        ]["storage_type"],
                        "unit_of_measure": (
                            line["unit_of_measure"]
                        ),
                        "order_multiple": (
                            decimal_text(multiple)
                        ),
                        "ordered_quantity": (
                            decimal_text(ordered)
                        ),
                        "planned_quantity": (
                            decimal_text(planned)
                        ),
                        "shipped_quantity": (
                            decimal_text(shipped)
                        ),
                        "received_quantity": (
                            decimal_text(received)
                        ),
                        "damaged_quantity": (
                            decimal_text(damaged)
                        ),
                        "rejected_quantity": (
                            decimal_text(rejected)
                        ),
                        "accepted_quantity": (
                            decimal_text(accepted)
                        ),
                        "created_at": utc_text(
                            context["created_at"]
                        ),
                        "updated_at": utc_text(
                            context["updated_at"]
                        ),
                        "version_number": 1,
                    }
                )

        for context in shipment_contexts:
            (
                min_temp,
                max_temp,
                breach,
            ) = temperature_values(
                config,
                rng,
                context["storage_types"],
            )

            totals = context["totals"]

            shipments.append(
                {
                    "shipment_id": (
                        context["shipment_id"]
                    ),
                    "shipment_number": (
                        context["shipment_number"]
                    ),
                    "supplier_shipment_reference": (
                        f"{config['supplier_shipment_reference_prefix']}"
                        f"-{order['supplier_code']}"
                        f"-{shipment_sequence:07d}"
                        f"-{context['shipment_index'] + 1}"
                    ),
                    "purchase_order_id": (
                        order["purchase_order_id"]
                    ),
                    "purchase_order_number": (
                        order[
                            "purchase_order_number"
                        ]
                    ),
                    "supplier_id": (
                        order["supplier_id"]
                    ),
                    "supplier_code": (
                        order["supplier_code"]
                    ),
                    "distribution_centre_id": (
                        order[
                            "distribution_centre_id"
                        ]
                    ),
                    "distribution_centre_code": (
                        order[
                            "distribution_centre_code"
                        ]
                    ),
                    "carrier_code": context[
                        "carrier"
                    ]["carrier_code"],
                    "carrier_name": context[
                        "carrier"
                    ]["carrier_name"],
                    "vehicle_type": context[
                        "vehicle_type"
                    ],
                    "shipment_status": (
                        shipment_status
                    ),
                    "delivery_performance_status": (
                        context["performance"]
                    ),
                    "planned_dispatch_at": utc_text(
                        context["planned_dispatch"]
                    ),
                    "actual_dispatch_at": (
                        utc_text(
                            context[
                                "actual_dispatch"
                            ]
                        )
                        if context["actual_dispatch"]
                        else ""
                    ),
                    "expected_delivery_at": utc_text(
                        context["expected_delivery"]
                    ),
                    "actual_delivery_at": (
                        utc_text(
                            context[
                                "actual_delivery"
                            ]
                        )
                        if context["actual_delivery"]
                        else ""
                    ),
                    "total_planned_quantity": (
                        decimal_text(
                            totals["planned"]
                        )
                    ),
                    "total_shipped_quantity": (
                        decimal_text(
                            totals["shipped"]
                        )
                    ),
                    "total_received_quantity": (
                        decimal_text(
                            totals["received"]
                        )
                    ),
                    "total_damaged_quantity": (
                        decimal_text(
                            totals["damaged"]
                        )
                    ),
                    "total_rejected_quantity": (
                        decimal_text(
                            totals["rejected"]
                        )
                    ),
                    "total_accepted_quantity": (
                        decimal_text(
                            totals["accepted"]
                        )
                    ),
                    "temperature_controlled_flag": (
                        str(
                            context["controlled"]
                        ).lower()
                    ),
                    "minimum_recorded_temperature_celsius": (
                        min_temp
                    ),
                    "maximum_recorded_temperature_celsius": (
                        max_temp
                    ),
                    "temperature_breach_flag": breach,
                    "cancellation_reason": "",
                    "created_at": utc_text(
                        context["created_at"]
                    ),
                    "updated_at": utc_text(
                        context["updated_at"]
                    ),
                    "version_number": 1,
                }
            )

            previous = ""

            for sequence_number, status in enumerate(
                STATUS_PATHS[shipment_status],
                start=1,
            ):
                changed_at = (
                    context["planned_dispatch"]
                    + timedelta(
                        hours=(
                            sequence_number - 1
                        )
                        * 8
                    )
                )

                if (
                    status == "DELIVERED"
                    and context["actual_delivery"]
                ):
                    changed_at = context[
                        "actual_delivery"
                    ]

                histories.append(
                    {
                        "shipment_status_history_id": stable_uuid(
                            "shipment-status-history",
                            (
                                f"{context['shipment_number']}:"
                                f"{sequence_number}"
                            ),
                        ),
                        "shipment_id": (
                            context["shipment_id"]
                        ),
                        "shipment_number": (
                            context["shipment_number"]
                        ),
                        "sequence_number": (
                            sequence_number
                        ),
                        "previous_status": previous,
                        "new_status": status,
                        "status_changed_at": (
                            utc_text(changed_at)
                        ),
                        "changed_by": (
                            "supplier-api-generator"
                        ),
                        "status_reason": (
                            "Deterministic operational "
                            "lifecycle event"
                        ),
                        "created_at": (
                            utc_text(changed_at)
                        ),
                    }
                )
                previous = status

    if any(
        row["supplier_id"] not in suppliers
        for row in shipments
    ):
        raise AssertionError(
            "A shipment references an unknown supplier."
        )

    if any(
        row["distribution_centre_id"] not in dcs
        for row in shipments
    ):
        raise AssertionError(
            "A shipment references an unknown "
            "distribution centre."
        )

    return shipments, shipment_lines, histories


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    shipments, shipment_lines, histories = generate()
    write_csv(SHIPMENT_PATH, shipments, SHIPMENT_FIELDS)
    write_csv(SHIPMENT_LINE_PATH, shipment_lines, SHIPMENT_LINE_FIELDS)
    write_csv(STATUS_HISTORY_PATH, histories, HISTORY_FIELDS)

    config = load_json(CONFIG_PATH)
    manifest = {
        "schema_version": config["schema_version"],
        "generator_name": config["generator_name"],
        "random_seed": config["random_seed"],
        "generated_at": config["generation_timestamp_utc"],
        "datasets": [
            {"file_name": SHIPMENT_PATH.name, "record_count": len(shipments), "sha256": file_sha256(SHIPMENT_PATH)},
            {"file_name": SHIPMENT_LINE_PATH.name, "record_count": len(shipment_lines), "sha256": file_sha256(SHIPMENT_LINE_PATH)},
            {"file_name": STATUS_HISTORY_PATH.name, "record_count": len(histories), "sha256": file_sha256(STATUS_HISTORY_PATH)},
        ],
        "source_record_counts": {
            "purchase_orders": len(load_csv(PURCHASE_ORDER_PATH)),
            "purchase_order_lines": len(load_csv(PURCHASE_ORDER_LINE_PATH)),
        },
        "watermark": config["fabric_incremental_extraction"],
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("BritMart supplier shipment data generated successfully.")
    print(f"Shipments: {len(shipments)}")
    print(f"Shipment lines: {len(shipment_lines)}")
    print(f"Status-history events: {len(histories)}")
    print(f"Output directory: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()