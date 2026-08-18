"""Automated tests for BritMart supplier performance data."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORY = PROJECT_ROOT / "data-generators" / "src"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"
CONFIG_PATH = PROJECT_ROOT / "data-generators" / "config" / "supplier_performance_config.json"
GENERATOR_PATH = SOURCE_DIRECTORY / "generate_supplier_performance.py"
VALIDATOR_PATH = SOURCE_DIRECTORY / "validate_supplier_performance.py"

SUPPLIER_PATH = OUTPUT_DIRECTORY / "suppliers.csv"
PURCHASE_ORDER_PATH = OUTPUT_DIRECTORY / "purchase_orders.csv"
SHIPMENT_PATH = OUTPUT_DIRECTORY / "shipments.csv"
RECEIPT_PATH = OUTPUT_DIRECTORY / "warehouse_goods_receipts.csv"
EVENT_PATH = OUTPUT_DIRECTORY / "supplier_performance_events.csv"
MONTHLY_PATH = OUTPUT_DIRECTORY / "supplier_performance_monthly.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "supplier_performance_manifest.json"

EXPECTED_EVENT_COUNT = 17235
EXPECTED_MONTHLY_COUNT = 577


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
    if any(not path.exists() for path in [EVENT_PATH, MONTHLY_PATH, MANIFEST_PATH]):
        result = run_script(GENERATOR_PATH)
        assert result.returncode == 0, result.stderr


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def test_supplier_performance_project_files_exist() -> None:
    assert CONFIG_PATH.exists()
    assert GENERATOR_PATH.exists()
    assert VALIDATOR_PATH.exists()


def test_supplier_performance_generator_runs_successfully() -> None:
    result = run_script(GENERATOR_PATH)
    assert result.returncode == 0, result.stderr
    assert "generated successfully" in result.stdout


def test_expected_supplier_performance_outputs_exist() -> None:
    ensure_outputs_exist()
    assert EVENT_PATH.exists()
    assert MONTHLY_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_expected_supplier_performance_record_counts() -> None:
    ensure_outputs_exist()
    assert len(load_csv(EVENT_PATH)) == EXPECTED_EVENT_COUNT
    assert len(load_csv(MONTHLY_PATH)) == EXPECTED_MONTHLY_COUNT


def test_performance_event_keys_are_unique_and_valid() -> None:
    events = load_csv(EVENT_PATH)
    for field in ["supplier_performance_event_id", "event_number", "idempotency_key"]:
        values = [row[field] for row in events]
        assert all(values)
        assert len(values) == len(set(values))
    for event in events:
        UUID(event["supplier_performance_event_id"])
        UUID(event["idempotency_key"])


def test_monthly_scorecard_keys_are_unique_and_valid() -> None:
    monthly = load_csv(MONTHLY_PATH)
    for field in ["supplier_performance_monthly_id", "idempotency_key"]:
        values = [row[field] for row in monthly]
        assert all(values)
        assert len(values) == len(set(values))
    business_keys = [(row["supplier_id"], row["performance_month"]) for row in monthly]
    assert len(business_keys) == len(set(business_keys))


def test_all_performance_records_reference_valid_suppliers() -> None:
    suppliers = {row["supplier_id"]: row for row in load_csv(SUPPLIER_PATH)}
    for row in load_csv(EVENT_PATH) + load_csv(MONTHLY_PATH):
        assert row["supplier_id"] in suppliers
        assert row["supplier_code"] == suppliers[row["supplier_id"]]["supplier_code"]


def test_event_metadata_matches_configuration() -> None:
    definitions = load_json(CONFIG_PATH)["event_definitions"]
    for event in load_csv(EVENT_PATH):
        definition = definitions[event["event_type"]]
        assert event["event_category"] == definition["event_category"]
        assert event["severity"] == definition["severity"]
        assert Decimal(event["score_impact"]) == Decimal(str(definition["score_impact"]))


def test_every_delivered_shipment_has_one_delivery_event() -> None:
    shipments = [row for row in load_csv(SHIPMENT_PATH) if row["shipment_status"] == "DELIVERED"]
    delivery_types = {"DELIVERY_EARLY", "DELIVERY_ON_TIME", "DELIVERY_LATE"}
    delivery_events = [row for row in load_csv(EVENT_PATH) if row["event_type"] in delivery_types]
    counts = Counter(row["shipment_id"] for row in delivery_events)
    assert set(counts) == {row["shipment_id"] for row in shipments}
    assert all(value == 1 for value in counts.values())


def test_delivery_event_types_match_delivery_performance() -> None:
    expected_type = {
        "EARLY": "DELIVERY_EARLY",
        "ON_TIME": "DELIVERY_ON_TIME",
        "LATE": "DELIVERY_LATE",
    }
    shipment_by_id = {row["shipment_id"]: row for row in load_csv(SHIPMENT_PATH)}
    for event in load_csv(EVENT_PATH):
        if event["event_type"] not in set(expected_type.values()):
            continue
        shipment = shipment_by_id[event["shipment_id"]]
        assert event["event_type"] == expected_type[shipment["delivery_performance_status"]]
        assert event["source_system"] == "SUPPLIER_API"


def test_temperature_breach_events_match_delivered_shipments() -> None:
    expected = {
        row["shipment_id"]
        for row in load_csv(SHIPMENT_PATH)
        if row["shipment_status"] == "DELIVERED"
        and row["temperature_controlled_flag"] == "true"
        and row["temperature_breach_flag"] == "true"
    }
    actual = {
        row["shipment_id"]
        for row in load_csv(EVENT_PATH)
        if row["event_type"] == "TEMPERATURE_BREACH"
    }
    assert actual == expected


def test_quality_events_match_warehouse_receipts() -> None:
    receipts = load_csv(RECEIPT_PATH)
    events = load_csv(EVENT_PATH)
    expected_damaged = {
        row["goods_receipt_id"]
        for row in receipts
        if Decimal(row["total_damaged_quantity"]) > 0
    }
    expected_rejected = {
        row["goods_receipt_id"]
        for row in receipts
        if Decimal(row["total_rejected_quantity"]) > 0
    }
    actual_damaged = {
        row["goods_receipt_id"] for row in events if row["event_type"] == "DAMAGED_GOODS"
    }
    actual_rejected = {
        row["goods_receipt_id"] for row in events if row["event_type"] == "REJECTED_GOODS"
    }
    assert actual_damaged == expected_damaged
    assert actual_rejected == expected_rejected


def test_quality_event_quantities_match_receipts() -> None:
    receipts = {row["goods_receipt_id"]: row for row in load_csv(RECEIPT_PATH)}
    for event in load_csv(EVENT_PATH):
        if event["event_type"] == "DAMAGED_GOODS":
            assert Decimal(event["metric_actual_value"]) == Decimal(
                receipts[event["goods_receipt_id"]]["total_damaged_quantity"]
            )
            assert event["source_system"] == "WAREHOUSE_SQL"
        elif event["event_type"] == "REJECTED_GOODS":
            assert Decimal(event["metric_actual_value"]) == Decimal(
                receipts[event["goods_receipt_id"]]["total_rejected_quantity"]
            )
            assert event["source_system"] == "WAREHOUSE_SQL"


def test_otif_event_coverage_matches_eligible_orders() -> None:
    config = load_json(CONFIG_PATH)
    eligible_statuses = set(config["evaluation_rules"]["purchase_order_statuses_eligible_for_otif"])
    eligible_ids = {
        row["purchase_order_id"]
        for row in load_csv(PURCHASE_ORDER_PATH)
        if row["purchase_order_status"] in eligible_statuses
    }
    otif_types = {name for name in config["event_definitions"] if name.startswith("OTIF_")}
    events = [row for row in load_csv(EVENT_PATH) if row["event_type"] in otif_types]
    counts = Counter(row["purchase_order_id"] for row in events)
    assert set(counts) == eligible_ids
    assert all(value == 1 for value in counts.values())


def test_otif_pass_flags_match_event_types() -> None:
    for event in load_csv(EVENT_PATH):
        if not event["event_type"].startswith("OTIF_"):
            continue
        assert (event["passed_flag"] == "true") == (event["event_type"] == "OTIF_PASS")
        assert event["source_system"] == "CROSS_SYSTEM_RECONCILIATION"


def test_monthly_delivery_counts_reconcile() -> None:
    monthly = load_csv(MONTHLY_PATH)
    for row in monthly:
        delivery_count = int(row["delivery_count"])
        classified = (
            int(row["early_delivery_count"])
            + int(row["on_time_delivery_count"])
            + int(row["late_delivery_count"])
        )
        assert delivery_count == classified


def test_monthly_otif_and_in_full_counts_reconcile() -> None:
    for row in load_csv(MONTHLY_PATH):
        evaluated = int(row["evaluated_purchase_order_count"])
        assert evaluated == int(row["otif_pass_count"]) + int(row["otif_fail_count"])
        assert evaluated == int(row["in_full_pass_count"]) + int(row["in_full_fail_count"])


def test_monthly_quality_quantities_reconcile() -> None:
    for row in load_csv(MONTHLY_PATH):
        received = Decimal(row["total_received_quantity"])
        accepted = Decimal(row["total_accepted_quantity"])
        damaged = Decimal(row["total_damaged_quantity"])
        rejected = Decimal(row["total_rejected_quantity"])
        assert received == accepted + damaged + rejected


def test_monthly_rates_and_scores_are_bounded() -> None:
    rate_fields = [
        "on_time_delivery_rate", "in_full_rate", "otif_rate",
        "accepted_quality_rate", "damage_rate", "rejection_rate",
        "temperature_compliance_rate",
    ]
    for row in load_csv(MONTHLY_PATH):
        for field in rate_fields:
            assert Decimal("0") <= Decimal(row[field]) <= Decimal("1")
        assert Decimal("0") <= Decimal(row["performance_score"]) <= Decimal("100")


def test_monthly_ratings_and_risk_values_are_controlled() -> None:
    valid_ratings = {"EXCELLENT", "GOOD", "WATCH", "HIGH_RISK"}
    valid_risks = {"NORMAL", "WATCH", "HIGH", "CRITICAL"}
    for row in load_csv(MONTHLY_PATH):
        assert row["performance_rating"] in valid_ratings
        assert row["risk_indicator"] in valid_risks


def test_performance_manifest_matches_outputs() -> None:
    manifest = load_json(MANIFEST_PATH)
    expected = {
        EVENT_PATH.name: (EXPECTED_EVENT_COUNT, sha256(EVENT_PATH)),
        MONTHLY_PATH.name: (EXPECTED_MONTHLY_COUNT, sha256(MONTHLY_PATH)),
    }
    datasets = {row["file_name"]: row for row in manifest["datasets"]}
    assert set(datasets) == set(expected)
    for file_name, (count, digest) in expected.items():
        assert int(datasets[file_name]["record_count"]) == count
        assert datasets[file_name]["sha256"] == digest


def test_full_supplier_performance_validator_runs_successfully() -> None:
    result = run_script(VALIDATOR_PATH)
    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout
    assert "Monthly score and rating recalculation: PASSED" in result.stdout


def test_supplier_performance_generation_is_reproducible() -> None:
    ensure_outputs_exist()
    paths = [EVENT_PATH, MONTHLY_PATH, MANIFEST_PATH]
    first = {path.name: path.read_bytes() for path in paths}
    result = run_script(GENERATOR_PATH)
    assert result.returncode == 0, result.stderr
    second = {path.name: path.read_bytes() for path in paths}
    assert first == second