"""Generate deterministic BritMart purchase orders and lines."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5


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

PURCHASE_ORDER_FIELDS = [
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
]

PURCHASE_ORDER_LINE_FIELDS = [
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
]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    if not path.exists():
        raise FileNotFoundError(
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
        raise FileNotFoundError(
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


def decimal_value(value: Any) -> Decimal:
    """Convert a value into a Decimal."""

    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    """Round a value to two monetary decimal places."""

    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def unit_price(value: Decimal) -> Decimal:
    """Round a unit price to four decimal places."""

    return value.quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )


def quantity(value: Decimal) -> Decimal:
    """Round a quantity to three decimal places."""

    return value.quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )


def random_decimal(
    minimum: Any,
    maximum: Any,
    decimal_places: int,
    random_generator: random.Random,
) -> Decimal:
    """Generate a deterministic decimal in a range."""

    multiplier = 10**decimal_places

    minimum_integer = int(
        decimal_value(minimum) * multiplier
    )

    maximum_integer = int(
        decimal_value(maximum) * multiplier
    )

    selected_integer = random_generator.randint(
        minimum_integer,
        maximum_integer,
    )

    quantizer = Decimal("1").scaleb(
        -decimal_places
    )

    return (
        Decimal(selected_integer)
        / Decimal(multiplier)
    ).quantize(quantizer)


def parse_date(value: str) -> date:
    """Parse an ISO-formatted date."""

    return date.fromisoformat(value)


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp."""

    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def timestamp_text(value: datetime) -> str:
    """Return a UTC ISO timestamp ending in Z."""

    utc_value = value.astimezone(
        timezone.utc
    )

    return utc_value.isoformat(
        timespec="seconds"
    ).replace(
        "+00:00",
        "Z",
    )


def random_datetime_on_date(
    date_value: date,
    random_generator: random.Random,
) -> datetime:
    """Create a deterministic business-hours UTC timestamp."""

    hour = random_generator.randint(7, 17)
    minute = random_generator.randint(0, 59)
    second = random_generator.randint(0, 59)

    return datetime.combine(
        date_value,
        time(
            hour=hour,
            minute=minute,
            second=second,
        ),
        tzinfo=timezone.utc,
    )


def add_business_days(
    start_date: date,
    number_of_days: int,
) -> date:
    """Add weekdays while excluding Saturday and Sunday."""

    current_date = start_date
    added_days = 0

    while added_days < number_of_days:
        current_date += timedelta(days=1)

        if current_date.weekday() < 5:
            added_days += 1

    return current_date


def expand_proportional_distribution(
    distribution: dict[str, Any],
    expected_count: int,
) -> list[str]:
    """Expand proportions into an exact list."""

    items = list(distribution.items())
    expanded: list[str] = []
    allocated_count = 0

    for label, proportion in items[:-1]:
        count = int(
            (
                decimal_value(proportion)
                * Decimal(expected_count)
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        expanded.extend(
            [label] * count
        )

        allocated_count += count

    final_label = items[-1][0]

    expanded.extend(
        [final_label]
        * (
            expected_count
            - allocated_count
        )
    )

    if len(expanded) != expected_count:
        raise ValueError(
            "Proportional distribution could not "
            "produce the expected count."
        )

    return expanded


def expand_exact_counts(
    counts: dict[str, Any],
    expected_count: int,
) -> list[str]:
    """Expand configured integer counts."""

    expanded = [
        label
        for label, count in counts.items()
        for _ in range(int(count))
    ]

    if len(expanded) != expected_count:
        raise ValueError(
            f"Configured counts produce {len(expanded)} "
            f"records instead of {expected_count}."
        )

    return expanded


def allocate_line_counts(
    order_count: int,
    target_line_count: int,
    minimum_lines: int,
    maximum_lines: int,
    random_generator: random.Random,
) -> list[int]:
    """Allocate varying lines while preserving the exact total."""

    minimum_total = (
        order_count * minimum_lines
    )

    maximum_total = (
        order_count * maximum_lines
    )

    if not (
        minimum_total
        <= target_line_count
        <= maximum_total
    ):
        raise ValueError(
            "Target line count cannot be achieved "
            "within configured line limits."
        )

    line_counts = [
        minimum_lines
        for _ in range(order_count)
    ]

    remaining_lines = (
        target_line_count
        - minimum_total
    )

    eligible_indexes = list(
        range(order_count)
    )

    while remaining_lines > 0:
        random_generator.shuffle(
            eligible_indexes
        )

        progress_made = False

        for index in eligible_indexes:
            if remaining_lines == 0:
                break

            if (
                line_counts[index]
                < maximum_lines
            ):
                line_counts[index] += 1
                remaining_lines -= 1
                progress_made = True

        if not progress_made:
            raise ValueError(
                "Unable to allocate the target "
                "purchase-order line count."
            )

    random_generator.shuffle(line_counts)

    if sum(line_counts) != target_line_count:
        raise ValueError(
            "Allocated line counts do not match "
            "the configured total."
        )

    return line_counts


def choose_weighted_distribution_centre(
    distribution_centres: list[
        dict[str, str]
    ],
    random_generator: random.Random,
) -> dict[str, str]:
    """Choose a distribution centre by receiving capacity."""

    weights = [
        max(
            1,
            int(
                centre[
                    "daily_receiving_capacity_cases"
                ]
            ),
        )
        for centre in distribution_centres
    ]

    return random_generator.choices(
        distribution_centres,
        weights=weights,
        k=1,
    )[0]


def build_agreements_by_supplier(
    agreements: list[dict[str, str]],
) -> dict[
    str,
    dict[str, list[dict[str, str]]],
]:
    """Group active agreements by supplier and role."""

    grouped: dict[
        str,
        dict[
            str,
            list[dict[str, str]],
        ],
    ] = defaultdict(
        lambda: {
            "PRIMARY": [],
            "SECONDARY": [],
            "ALL": [],
        }
    )

    for agreement in agreements:
        if (
            agreement["agreement_status"]
            != "ACTIVE"
        ):
            continue

        supplier_id = agreement[
            "supplier_id"
        ]

        role = agreement[
            "agreement_role"
        ]

        grouped[supplier_id][role].append(
            agreement
        )

        grouped[supplier_id]["ALL"].append(
            agreement
        )

    return dict(grouped)


def select_unique_agreements(
    supplier_agreements: dict[
        str,
        list[dict[str, str]],
    ],
    line_count: int,
    primary_probability: float,
    random_generator: random.Random,
) -> list[dict[str, str]]:
    """Choose unique products for one purchase order."""

    selected: list[
        dict[str, str]
    ] = []

    selected_product_ids: set[str] = set()

    primary_pool = list(
        supplier_agreements["PRIMARY"]
    )

    secondary_pool = list(
        supplier_agreements["SECONDARY"]
    )

    all_pool = list(
        supplier_agreements["ALL"]
    )

    random_generator.shuffle(
        primary_pool
    )
    random_generator.shuffle(
        secondary_pool
    )
    random_generator.shuffle(
        all_pool
    )

    while len(selected) < line_count:
        prefer_primary = (
            random_generator.random()
            < primary_probability
        )

        preferred_pool = (
            primary_pool
            if prefer_primary
            else secondary_pool
        )

        candidate = next(
            (
                agreement
                for agreement in preferred_pool
                if agreement["product_id"]
                not in selected_product_ids
            ),
            None,
        )

        if candidate is None:
            candidate = next(
                (
                    agreement
                    for agreement in all_pool
                    if agreement["product_id"]
                    not in selected_product_ids
                ),
                None,
            )

        if candidate is None:
            raise ValueError(
                "Supplier does not have enough unique "
                "product agreements for this order."
            )

        selected.append(candidate)

        selected_product_ids.add(
            candidate["product_id"]
        )

    return selected


def assign_statuses(
    order_dates: list[date],
    status_counts: dict[str, Any],
    random_generator: random.Random,
) -> list[str]:
    """Assign statuses with older orders further through lifecycle."""

    order_count = len(order_dates)

    expected_count = sum(
        int(value)
        for value in status_counts.values()
    )

    if expected_count != order_count:
        raise ValueError(
            "Purchase-order status counts do not "
            "match the order count."
        )

    statuses = [""] * order_count

    all_indexes = list(
        range(order_count)
    )

    cancelled_count = int(
        status_counts.get(
            "CANCELLED",
            0,
        )
    )

    cancelled_indexes = set(
        random_generator.sample(
            all_indexes,
            cancelled_count,
        )
    )

    for index in cancelled_indexes:
        statuses[index] = "CANCELLED"

    remaining_indexes = [
        index
        for index in all_indexes
        if index not in cancelled_indexes
    ]

    remaining_indexes.sort(
        key=lambda index: (
            order_dates[index],
            index,
        )
    )

    lifecycle_order = [
        "CLOSED",
        "PARTIALLY_RECEIVED",
        "DISPATCHED",
        "CONFIRMED",
        "APPROVED",
        "DRAFT",
    ]

    position = 0

    for status in lifecycle_order:
        count = int(
            status_counts.get(
                status,
                0,
            )
        )

        selected_indexes = (
            remaining_indexes[
                position:position + count
            ]
        )

        for index in selected_indexes:
            statuses[index] = status

        position += count

    if any(
        not status
        for status in statuses
    ):
        raise ValueError(
            "Not every purchase order received a status."
        )

    return statuses


def resolve_updated_at(
    created_at: datetime,
    required_delivery_date: date,
    purchase_order_status: str,
    snapshot_timestamp: datetime,
    random_generator: random.Random,
) -> datetime:
    """Create a logical status update timestamp."""

    if purchase_order_status == "DRAFT":
        updated_at = created_at

    elif purchase_order_status == "APPROVED":
        updated_at = (
            created_at
            + timedelta(
                hours=random_generator.randint(
                    1,
                    24,
                )
            )
        )

    elif purchase_order_status == "CONFIRMED":
        updated_at = (
            created_at
            + timedelta(
                hours=random_generator.randint(
                    6,
                    48,
                )
            )
        )

    elif purchase_order_status == "DISPATCHED":
        dispatch_date = (
            required_delivery_date
            - timedelta(
                days=random_generator.randint(
                    1,
                    5,
                )
            )
        )

        updated_at = random_datetime_on_date(
            max(
                created_at.date(),
                dispatch_date,
            ),
            random_generator,
        )

    elif (
        purchase_order_status
        == "PARTIALLY_RECEIVED"
    ):
        updated_at = random_datetime_on_date(
            max(
                created_at.date(),
                required_delivery_date,
            ),
            random_generator,
        )

    elif purchase_order_status == "CLOSED":
        closure_date = (
            required_delivery_date
            + timedelta(
                days=random_generator.randint(
                    0,
                    7,
                )
            )
        )

        updated_at = random_datetime_on_date(
            max(
                created_at.date(),
                closure_date,
            ),
            random_generator,
        )

    elif purchase_order_status == "CANCELLED":
        updated_at = (
            created_at
            + timedelta(
                hours=random_generator.randint(
                    1,
                    72,
                )
            )
        )

    else:
        updated_at = created_at

    return min(
        updated_at,
        snapshot_timestamp,
    )


def approval_role(
    total_value_gbp: Decimal,
    config: dict[str, Any],
) -> str:
    """Resolve purchase-order approval authority."""

    rules = config[
        "approval_rules"
    ]

    if total_value_gbp <= decimal_value(
        rules["auto_approval_limit_gbp"]
    ):
        return "AUTO_APPROVED"

    if total_value_gbp <= decimal_value(
        rules[
            "procurement_manager_limit_gbp"
        ]
    ):
        return "PROCUREMENT_MANAGER"

    if total_value_gbp <= decimal_value(
        rules[
            "procurement_director_limit_gbp"
        ]
    ):
        return "PROCUREMENT_DIRECTOR"

    return "EXECUTIVE_APPROVAL"


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    """Write a stable CSV file."""

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def generate_purchase_orders(
    config: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Generate purchase orders and purchase-order lines."""

    validation_report = load_json(
        MASTER_VALIDATION_REPORT_PATH
    )

    if (
        validation_report[
            "validation_status"
        ]
        != "PASSED"
        or validation_report[
            "approved_for_downstream_generation"
        ]
        is not True
    ):
        raise ValueError(
            "Master data is not approved for "
            "transaction generation."
        )

    products = load_csv(PRODUCT_PATH)
    suppliers = load_csv(SUPPLIER_PATH)

    agreements = load_csv(
        SUPPLIER_PRODUCT_PATH
    )

    distribution_centres = load_csv(
        DISTRIBUTION_CENTRE_PATH
    )

    products_by_id = {
        row["product_id"]: row
        for row in products
    }

    suppliers_by_id = {
        row["supplier_id"]: row
        for row in suppliers
    }

    agreements_by_supplier = (
        build_agreements_by_supplier(
            agreements
        )
    )

    eligible_supplier_ids = [
        supplier_id
        for supplier_id, agreement_groups
        in agreements_by_supplier.items()
        if (
            supplier_id in suppliers_by_id
            and suppliers_by_id[
                supplier_id
            ]["supplier_status"]
            == "ACTIVE"
            and len(
                agreement_groups["ALL"]
            )
            >= int(
                config["expected_counts"][
                    "maximum_lines_per_order"
                ]
            )
        )
    ]

    if not eligible_supplier_ids:
        raise ValueError(
            "No suppliers are eligible for "
            "purchase-order generation."
        )

    project_config = config["project"]

    random_generator = random.Random(
        int(project_config["master_seed"])
    )

    namespace_uuid = UUID(
        project_config["uuid_namespace"]
    )

    expected_counts = config[
        "expected_counts"
    ]

    order_count = int(
        expected_counts["purchase_orders"]
    )

    target_line_count = int(
        expected_counts[
            "purchase_order_lines"
        ]
    )

    line_counts = allocate_line_counts(
        order_count,
        target_line_count,
        int(
            expected_counts[
                "minimum_lines_per_order"
            ]
        ),
        int(
            expected_counts[
                "maximum_lines_per_order"
            ]
        ),
        random_generator,
    )

    operating_period = config[
        "operating_period"
    ]

    start_date = parse_date(
        operating_period["order_date_from"]
    )

    end_date = parse_date(
        operating_period["order_date_to"]
    )

    number_of_days = (
        end_date - start_date
    ).days

    order_dates = [
        (
            start_date
            + timedelta(
                days=random_generator.randint(
                    0,
                    number_of_days,
                )
            )
        )
        for _ in range(order_count)
    ]

    statuses = assign_statuses(
        order_dates,
        config[
            "purchase_order_status_counts"
        ],
        random_generator,
    )

    order_types = (
        expand_proportional_distribution(
            config[
                "order_type_distribution"
            ],
            order_count,
        )
    )

    random_generator.shuffle(
        order_types
    )

    cancellation_reasons = list(
        config["cancellation_rules"][
            "cancellation_reason_distribution"
        ].keys()
    )

    cancellation_weights = list(
        config["cancellation_rules"][
            "cancellation_reason_distribution"
        ].values()
    )

    snapshot_timestamp = parse_timestamp(
        project_config[
            "snapshot_timestamp"
        ]
    )

    audit_rules = config[
        "audit_rules"
    ]

    primary_probability = float(
        config["supplier_selection"][
            "primary_supplier_probability"
        ]
    )

    purchase_orders: list[
        dict[str, Any]
    ] = []

    purchase_order_lines: list[
        dict[str, Any]
    ] = []

    line_sequence = 1

    for order_index in range(
        order_count
    ):
        sequence_number = order_index + 1

        order_date = order_dates[
            order_index
        ]

        order_type = order_types[
            order_index
        ]

        purchase_order_status = statuses[
            order_index
        ]

        supplier_id = (
            random_generator.choice(
                eligible_supplier_ids
            )
        )

        supplier = suppliers_by_id[
            supplier_id
        ]

        selected_agreements = (
            select_unique_agreements(
                agreements_by_supplier[
                    supplier_id
                ],
                line_counts[order_index],
                primary_probability,
                random_generator,
            )
        )

        distribution_centre = (
            choose_weighted_distribution_centre(
                distribution_centres,
                random_generator,
            )
        )

        supplier_lead_time = int(
            supplier[
                "standard_lead_time_days"
            ]
        )

        delivery_offset_config = config[
            "delivery_rules"
        ][
            "required_date_offset_by_order_type"
        ][order_type]

        configured_offset = (
            random_generator.randint(
                int(
                    delivery_offset_config[
                        "minimum_days"
                    ]
                ),
                int(
                    delivery_offset_config[
                        "maximum_days"
                    ]
                ),
            )
        )

        required_offset = max(
            supplier_lead_time,
            configured_offset,
        )

        required_delivery_date = (
            add_business_days(
                order_date,
                required_offset,
            )
        )

        created_at = (
            random_datetime_on_date(
                order_date,
                random_generator,
            )
        )

        updated_at = resolve_updated_at(
            created_at,
            required_delivery_date,
            purchase_order_status,
            snapshot_timestamp,
            random_generator,
        )

        purchase_order_number = (
            f"PO-{order_date:%Y%m}-"
            f"{sequence_number:06d}"
        )

        purchase_order_id = uuid5(
            namespace_uuid,
            (
                "britmart:purchase-order:"
                f"{purchase_order_number}"
            ),
        )

        total_net_amount = Decimal("0")
        total_vat_amount = Decimal("0")
        total_gross_amount = Decimal("0")

        order_line_rows: list[
            dict[str, Any]
        ] = []

        quantity_multiplier_config = (
            config["line_allocation"][
                "quantity_multiplier_by_order_type"
            ][order_type]
        )

        price_variance_config = (
            config["line_allocation"][
                "price_variance_rate"
            ]
        )

        for line_number, agreement in enumerate(
            selected_agreements,
            start=1,
        ):
            product = products_by_id[
                agreement["product_id"]
            ]

            minimum_order_quantity = (
                decimal_value(
                    agreement[
                        "minimum_order_quantity"
                    ]
                )
            )

            order_multiple = decimal_value(
                agreement["order_multiple"]
            )

            quantity_multiplier = (
                random_generator.randint(
                    int(
                        quantity_multiplier_config[
                            "minimum"
                        ]
                    ),
                    int(
                        quantity_multiplier_config[
                            "maximum"
                        ]
                    ),
                )
            )

            ordered_quantity = quantity(
                minimum_order_quantity
                * Decimal(
                    quantity_multiplier
                )
            )

            if (
                ordered_quantity
                % order_multiple
                != 0
            ):
                raise ValueError(
                    "Generated quantity is not an "
                    "order-multiple value."
                )

            variance_rate = random_decimal(
                price_variance_config[
                    "minimum"
                ],
                price_variance_config[
                    "maximum"
                ],
                4,
                random_generator,
            )

            agreed_unit_price = (
                decimal_value(
                    agreement[
                        "agreed_unit_cost"
                    ]
                )
            )

            line_unit_price = unit_price(
                agreed_unit_price
                * (
                    Decimal("1")
                    + variance_rate
                )
            )

            net_amount = money(
                ordered_quantity
                * line_unit_price
            )

            vat_rate = decimal_value(
                product["vat_rate"]
            )

            vat_amount = money(
                net_amount * vat_rate
            )

            gross_amount = money(
                net_amount + vat_amount
            )

            total_net_amount += net_amount
            total_vat_amount += vat_amount
            total_gross_amount += gross_amount

            purchase_order_line_id = uuid5(
                namespace_uuid,
                (
                    "britmart:purchase-order-line:"
                    f"{purchase_order_number}:"
                    f"{line_number}"
                ),
            )

            order_line_rows.append(
                {
                    "purchase_order_line_id": str(
                        purchase_order_line_id
                    ),
                    "purchase_order_id": str(
                        purchase_order_id
                    ),
                    "purchase_order_number": (
                        purchase_order_number
                    ),
                    "line_number": line_number,
                    "supplier_product_id": (
                        agreement[
                            "supplier_product_id"
                        ]
                    ),
                    "product_id": product[
                        "product_id"
                    ],
                    "product_code": product[
                        "product_code"
                    ],
                    "sku": product["sku"],
                    "ordered_quantity": format(
                        ordered_quantity,
                        ".3f",
                    ),
                    "unit_of_measure": product[
                        "unit_of_measure"
                    ],
                    "order_multiple": format(
                        order_multiple,
                        ".3f",
                    ),
                    "unit_price": format(
                        line_unit_price,
                        ".4f",
                    ),
                    "currency_code": supplier[
                        "default_currency_code"
                    ],
                    "net_amount": format(
                        net_amount,
                        ".2f",
                    ),
                    "vat_rate": format(
                        vat_rate,
                        ".6f",
                    ),
                    "vat_amount": format(
                        vat_amount,
                        ".2f",
                    ),
                    "gross_amount": format(
                        gross_amount,
                        ".2f",
                    ),
                    "created_at": timestamp_text(
                        created_at
                    ),
                    "updated_at": timestamp_text(
                        updated_at
                    ),
                    "version_number": int(
                        audit_rules[
                            "initial_version_number"
                        ]
                    ),
                }
            )

            line_sequence += 1

        total_net_amount = money(
            total_net_amount
        )

        total_vat_amount = money(
            total_vat_amount
        )

        total_gross_amount = money(
            total_gross_amount
        )

        agreement_rate = decimal_value(
            selected_agreements[0][
                "gbp_value_per_currency_unit"
            ]
        )

        total_value_gbp = money(
            total_gross_amount
            * agreement_rate
        )

        resolved_approval_role = (
            approval_role(
                total_value_gbp,
                config,
            )
        )

        if purchase_order_status == "DRAFT":
            approved_at = ""
        else:
            approved_datetime = min(
                created_at
                + timedelta(
                    hours=random_generator.randint(
                        1,
                        24,
                    )
                ),
                updated_at,
            )

            approved_at = timestamp_text(
                approved_datetime
            )

        if (
            purchase_order_status
            == "CANCELLED"
        ):
            cancellation_reason = (
                random_generator.choices(
                    cancellation_reasons,
                    weights=cancellation_weights,
                    k=1,
                )[0]
            )
        else:
            cancellation_reason = ""

        buyer_code = (
            f"{config['approval_rules']['buyer_code_prefix']}-"
            f"{random_generator.randint(1, int(config['approval_rules']['buyer_count'])):03d}"
        )

        purchase_orders.append(
            {
                "purchase_order_id": str(
                    purchase_order_id
                ),
                "purchase_order_number": (
                    purchase_order_number
                ),
                "supplier_id": supplier_id,
                "supplier_code": supplier[
                    "supplier_code"
                ],
                "distribution_centre_id": (
                    distribution_centre[
                        "distribution_centre_id"
                    ]
                ),
                "distribution_centre_code": (
                    distribution_centre[
                        "distribution_centre_code"
                    ]
                ),
                "order_date": order_date.isoformat(),
                "required_delivery_date": (
                    required_delivery_date.isoformat()
                ),
                "order_type": order_type,
                "purchase_order_status": (
                    purchase_order_status
                ),
                "currency_code": supplier[
                    "default_currency_code"
                ],
                "total_net_amount": format(
                    total_net_amount,
                    ".2f",
                ),
                "total_vat_amount": format(
                    total_vat_amount,
                    ".2f",
                ),
                "total_gross_amount": format(
                    total_gross_amount,
                    ".2f",
                ),
                "total_value_gbp": format(
                    total_value_gbp,
                    ".2f",
                ),
                "buyer_code": buyer_code,
                "approval_role": (
                    resolved_approval_role
                ),
                "approved_at": approved_at,
                "cancellation_reason": (
                    cancellation_reason
                ),
                "created_by": audit_rules[
                    "created_by_system"
                ],
                "updated_by": audit_rules[
                    "updated_by_system"
                ],
                "created_at": timestamp_text(
                    created_at
                ),
                "updated_at": timestamp_text(
                    updated_at
                ),
                "version_number": int(
                    audit_rules[
                        "initial_version_number"
                    ]
                ),
            }
        )

        purchase_order_lines.extend(
            order_line_rows
        )

    if len(purchase_orders) != order_count:
        raise ValueError(
            "Generated purchase-order count is incorrect."
        )

    if (
        len(purchase_order_lines)
        != target_line_count
    ):
        raise ValueError(
            "Generated purchase-order line count is incorrect."
        )

    return (
        purchase_orders,
        purchase_order_lines,
    )


def write_manifest(
    purchase_orders: list[
        dict[str, Any]
    ],
    purchase_order_lines: list[
        dict[str, Any]
    ],
    config: dict[str, Any],
) -> None:
    """Write purchase-order dataset metadata."""

    status_counts = Counter(
        row["purchase_order_status"]
        for row in purchase_orders
    )

    order_type_counts = Counter(
        row["order_type"]
        for row in purchase_orders
    )

    currency_counts = Counter(
        row["currency_code"]
        for row in purchase_orders
    )

    manifest = {
        "dataset_name": (
            "britmart_purchase_orders"
        ),
        "dataset_version": config[
            "project"
        ]["dataset_version"],
        "schema_version": "1.0.0",
        "generated_at": config[
            "project"
        ]["generated_timestamp"],
        "snapshot_timestamp": config[
            "project"
        ]["snapshot_timestamp"],
        "purchase_order_count": len(
            purchase_orders
        ),
        "purchase_order_line_count": len(
            purchase_order_lines
        ),
        "status_counts": dict(
            sorted(status_counts.items())
        ),
        "order_type_counts": dict(
            sorted(order_type_counts.items())
        ),
        "currency_counts": dict(
            sorted(currency_counts.items())
        ),
        "output_files": {
            PURCHASE_ORDER_PATH.name: {
                "record_count": len(
                    purchase_orders
                ),
                "sha256": calculate_sha256(
                    PURCHASE_ORDER_PATH
                ),
            },
            PURCHASE_ORDER_LINE_PATH.name: {
                "record_count": len(
                    purchase_order_lines
                ),
                "sha256": calculate_sha256(
                    PURCHASE_ORDER_LINE_PATH
                ),
            },
        },
        "source_files": {
            PRODUCT_PATH.name: (
                calculate_sha256(
                    PRODUCT_PATH
                )
            ),
            SUPPLIER_PATH.name: (
                calculate_sha256(
                    SUPPLIER_PATH
                )
            ),
            SUPPLIER_PRODUCT_PATH.name: (
                calculate_sha256(
                    SUPPLIER_PRODUCT_PATH
                )
            ),
            DISTRIBUTION_CENTRE_PATH.name: (
                calculate_sha256(
                    DISTRIBUTION_CENTRE_PATH
                )
            ),
            MASTER_VALIDATION_REPORT_PATH.name: (
                calculate_sha256(
                    MASTER_VALIDATION_REPORT_PATH
                )
            ),
        },
        "business_keys": {
            "purchase_order": (
                "purchase_order_number"
            ),
            "purchase_order_line": [
                "purchase_order_id",
                "line_number",
            ],
        },
        "technical_keys": {
            "purchase_order": (
                "purchase_order_id"
            ),
            "purchase_order_line": (
                "purchase_order_line_id"
            ),
        },
        "incremental_columns": {
            "purchase_orders": [
                "updated_at",
                "purchase_order_id",
            ],
            "purchase_order_lines": [
                "updated_at",
                "purchase_order_line_id",
            ],
        },
    }

    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            manifest,
            output_file,
            indent=2,
            sort_keys=True,
        )
        output_file.write("\n")


def main() -> None:
    """Execute purchase-order generation."""

    config = load_json(CONFIG_PATH)

    purchase_orders, purchase_order_lines = (
        generate_purchase_orders(
            config
        )
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_csv(
        PURCHASE_ORDER_PATH,
        PURCHASE_ORDER_FIELDS,
        purchase_orders,
    )

    write_csv(
        PURCHASE_ORDER_LINE_PATH,
        PURCHASE_ORDER_LINE_FIELDS,
        purchase_order_lines,
    )

    write_manifest(
        purchase_orders,
        purchase_order_lines,
        config,
    )

    print(
        "BritMart purchase-order data "
        "generated successfully."
    )
    print(
        "Purchase orders: "
        f"{len(purchase_orders)}"
    )
    print(
        "Purchase-order lines: "
        f"{len(purchase_order_lines)}"
    )
    print(
        f"Output directory: {OUTPUT_DIRECTORY}"
    )


if __name__ == "__main__":
    main()