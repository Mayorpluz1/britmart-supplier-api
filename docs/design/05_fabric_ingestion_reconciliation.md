# BritMart Fabric Ingestion and Reconciliation Specification

## 5.1 Purpose

This document defines how Microsoft Fabric will extract, land, validate, reconcile and monitor data from the BritMart Supplier and Procurement API.

It covers:

- Full and incremental extraction
- Cursor-based pagination
- Watermark management
- Bronze ingestion
- Audit logging
- Retry and error handling
- Idempotent reruns
- Schema validation
- Data-quality quarantine
- Source-to-Bronze reconciliation
- Bronze-to-Silver reconciliation
- Silver-to-Gold reconciliation
- Cross-system business reconciliation


## 5.2 Ingestion Scope

Fabric will ingest the following FastAPI entities:

| Entity | Endpoint | Initial load | Continuing load |
|---|---|---|---|
| Suppliers | `/api/v1/suppliers` | Full | Incremental |
| Products | `/api/v1/products` | Full | Incremental |
| Distribution centres | `/api/v1/distribution-centres` | Full | Incremental |
| Supplier-product agreements | `/api/v1/supplier-product-agreements` | Full | Incremental |
| Purchase orders | `/api/v1/purchase-orders` | Full | Incremental |
| Purchase-order lines | `/api/v1/purchase-order-lines` | Full | Incremental |
| Shipments | `/api/v1/shipments` | Full | Incremental |
| Shipment lines | `/api/v1/shipment-lines` | Full | Incremental |
| Deliveries | `/api/v1/deliveries` | Full | Incremental |
| Supplier-performance events | `/api/v1/supplier-performance-events` | Full | Incremental |

Status-history entities will be append-only and extracted using `changed_at`.



## 5.3 Fabric Architecture

```text
FastAPI operational database
        ↓
FastAPI REST endpoints
        ↓
Fabric Data Factory pipeline
        ↓
Bronze raw API payload
        ↓
Silver validation and standardisation
        ↓
Cross-system reconciliation
        ↓
Gold dimensional model
        ↓
Semantic model and Power BI
````

FastAPI remains the operational system of record for procurement and supplier-shipment entities.

Fabric owns historical integration, quality controls, reconciliation and analytical publication.



# 5.4 Metadata-Driven Ingestion

The Supplier API pipeline must be controlled through ingestion metadata rather than separately hard-coded activities for every endpoint.

## 5.4.1 Ingestion Configuration

Recommended control table:

```text
ctl.ingestion_config
```

Required fields:

| Field                    | Purpose                                |
| ------------------------ | -------------------------------------- |
| `ingestion_config_id`    | Configuration identifier               |
| `source_system`          | `SUPPLIER_API`                         |
| `source_entity`          | Entity name                            |
| `endpoint_path`          | Relative API endpoint                  |
| `target_bronze_table`    | Bronze destination                     |
| `load_type`              | `FULL`, `INCREMENTAL` or `APPEND_ONLY` |
| `watermark_column`       | `updated_at` or `changed_at`           |
| `primary_key_column`     | Stable source identifier               |
| `default_page_size`      | Normal extraction page size            |
| `maximum_page_size`      | Permitted maximum                      |
| `overlap_minutes`        | Incremental overlap                    |
| `retry_count`            | Maximum transient retries              |
| `retry_interval_seconds` | Delay between retries                  |
| `timeout_seconds`        | Request timeout                        |
| `schema_version`         | Expected source schema                 |
| `criticality`            | Critical, high, medium or low          |
| `execution_order`        | Dependency order                       |
| `quality_rule_group`     | Applicable rule set                    |
| `active_flag`            | Whether the entity is enabled          |
| `expected_arrival_time`  | SLA expectation                        |
| `owner`                  | Responsible team or person             |
| `created_at`             | Metadata creation time                 |
| `updated_at`             | Metadata update time                   |



## 5.4.2 Watermark Tracker

Recommended table:

```text
ctl.watermark_tracker
```

Required fields:

| Field                         | Purpose                               |
| ----------------------------- | ------------------------------------- |
| `source_system`               | Supplier API                          |
| `source_entity`               | Entity name                           |
| `last_successful_watermark`   | Maximum committed source timestamp    |
| `last_successful_primary_key` | Tie-breaker identifier where required |
| `last_extraction_upper_bound` | Previous extraction boundary          |
| `last_successful_run_id`      | Successful pipeline execution         |
| `last_successful_at`          | Completion timestamp                  |
| `watermark_status`            | Current state                         |
| `updated_at`                  | Tracker update time                   |

The watermark must update only after:

1. Every API page has been retrieved.
2. Bronze persistence has succeeded.
3. Source-to-Bronze reconciliation has passed.
4. The entity run has been marked successful.



# 5.5 Initial Full Load

The first extraction for each entity will:

1. Read active entity metadata.
2. Set one fixed extraction upper boundary.
3. Request the first API page.
4. Capture the response and pagination metadata.
5. Follow the returned cursor until `has_next` is false.
6. Write every raw response page into Bronze.
7. Record request and response metadata.
8. Reconcile API counts with Bronze counts.
9. Record the maximum source watermark.
10. Update the watermark only after successful completion.

The initial full load must be repeatable without creating duplicate Silver or Gold records.



# 5.6 Incremental Extraction

## 5.6.1 Extraction Window

The lower boundary is calculated as:

```text
last_successful_watermark - configured overlap
```

The upper boundary is fixed at the beginning of the run:

```text
extraction_upper_bound = current source-safe UTC timestamp
```

The API request applies:

```text
updated_at > lower_boundary
AND updated_at <= upper_boundary
```

Example:

```http
GET /api/v1/shipments
    ?updated_since=2026-08-14T01:45:00Z
    &updated_before=2026-08-15T02:00:00Z
    &page_size=500
```

The upper boundary must not change between pages.


## 5.6.2 Stable Incremental Ordering

The API must order records using:

```text
updated_at ASC, primary_key ASC
```

This prevents records with the same timestamp from being returned unpredictably.

Fabric must preserve:

* Lower boundary
* Upper boundary
* Cursor
* Page number or request sequence
* Minimum timestamp received
* Maximum timestamp received
* Final primary identifier



## 5.6.3 Overlap Window

A configurable overlap protects against:

* Late database commits
* Timestamp precision differences
* Boundary conditions
* Delayed updates
* Temporary source inconsistency

Recommended initial overlap:

```text
15 minutes
```

Overlapping records are expected. Silver processing must deduplicate and merge them safely.



# 5.7 Pagination

Microsoft Fabric should use cursor-based pagination for scheduled incremental extraction.

The pipeline process is:

```text
Request first page
→ Write raw page
→ Read next_cursor
→ Request next page
→ Continue until has_next = false
```

For every page, Fabric must record:

* `run_id`
* `request_id`
* `source_entity`
* `page_sequence`
* `cursor_received`
* `next_cursor`
* `records_returned`
* `request_started_at`
* `request_completed_at`
* `http_status_code`
* `response_time_ms`

A cursor must not be reused with different extraction boundaries or filters.



# 5.8 Bronze-Layer Design

Bronze preserves the source payload as faithfully as possible.

Each Bronze record must include source fields and ingestion metadata.

Required ingestion metadata:

| Field                     | Purpose                         |
| ------------------------- | ------------------------------- |
| `_run_id`                 | Fabric pipeline execution       |
| `_source_system`          | `SUPPLIER_API`                  |
| `_source_entity`          | Extracted entity                |
| `_source_endpoint`        | Endpoint used                   |
| `_source_request_id`      | FastAPI correlation identifier  |
| `_extraction_lower_bound` | Incremental lower boundary      |
| `_extraction_upper_bound` | Incremental upper boundary      |
| `_page_sequence`          | API page order                  |
| `_source_schema_version`  | API schema version              |
| `_ingested_at`            | Fabric landing timestamp        |
| `_raw_payload_hash`       | Duplicate and integrity support |
| `_bronze_record_status`   | Technical ingestion status      |

Bronze principles:

* Do not apply business transformations.
* Preserve technically readable invalid business records.
* Do not silently rename or discard unexpected fields.
* Retain enough information to replay processing.
* Separate source business timestamps from Fabric ingestion timestamps.
* Append new raw extraction records.
* Protect sensitive headers and secrets from storage.



# 5.9 Bronze Storage Structure

Recommended logical structure:

```text
bronze/supplier_api/suppliers/
bronze/supplier_api/products/
bronze/supplier_api/distribution_centres/
bronze/supplier_api/supplier_product_agreements/
bronze/supplier_api/purchase_orders/
bronze/supplier_api/purchase_order_lines/
bronze/supplier_api/shipments/
bronze/supplier_api/shipment_lines/
bronze/supplier_api/deliveries/
bronze/supplier_api/supplier_performance_events/
```

Recommended partitioning:

```text
ingestion_date
```

Avoid excessive high-cardinality partitioning.



# 5.10 Audit Framework

## 5.10.1 Pipeline Run Audit

Recommended table:

```text
audit.pipeline_run
```

Fields:

| Field              | Purpose                                           |
| ------------------ | ------------------------------------------------- |
| `run_id`           | Unique run identifier                             |
| `pipeline_name`    | Pipeline                                          |
| `source_system`    | Supplier API                                      |
| `trigger_type`     | Manual, scheduled or rerun                        |
| `started_at`       | Start timestamp                                   |
| `completed_at`     | Completion timestamp                              |
| `run_status`       | Running, succeeded, failed or partially succeeded |
| `records_read`     | Total source records                              |
| `records_written`  | Bronze records                                    |
| `records_rejected` | Technical rejection count                         |
| `retry_count`      | Total retries                                     |
| `error_code`       | Final error code                                  |
| `error_message`    | Sanitised error                                   |
| `environment`      | Development, test or production simulation        |



## 5.10.2 Entity Run Audit

Recommended table:

```text
audit.entity_run
```

Fields:

| Field                      | Purpose                          |
| -------------------------- | -------------------------------- |
| `entity_run_id`            | Entity execution identifier      |
| `run_id`                   | Parent pipeline run              |
| `source_entity`            | Extracted entity                 |
| `load_type`                | Full, incremental or append-only |
| `lower_watermark`          | Lower boundary                   |
| `upper_watermark`          | Upper boundary                   |
| `source_record_count`      | API records returned             |
| `bronze_record_count`      | Bronze records persisted         |
| `page_count`               | API pages                        |
| `minimum_source_timestamp` | Minimum update timestamp         |
| `maximum_source_timestamp` | Maximum update timestamp         |
| `status`                   | Entity result                    |
| `started_at`               | Start time                       |
| `completed_at`             | End time                         |
| `retry_count`              | Entity retry count               |
| `error_code`               | Error code                       |
| `error_message`            | Sanitised message                |



## 5.10.3 API Request Audit

Recommended table:

```text
audit.api_request
```

Fields include:

* `run_id`
* `entity_run_id`
* `request_id`
* `endpoint`
* `page_sequence`
* `http_method`
* `http_status_code`
* `response_time_ms`
* `records_returned`
* `retry_attempt`
* `requested_at`
* `completed_at`
* `error_code`
* `error_message`

API keys must never appear in audit tables.



# 5.11 Retry and Failure Handling

## 5.11.1 Retryable Failures

Retry:

* HTTP `429`
* HTTP `500`
* HTTP `503`
* Network timeout
* Temporary connection failure

Recommended initial policy:

```text
Maximum attempts: 3
Delay: exponential backoff
Base delay: 10 seconds
Maximum delay: 60 seconds
```

Where provided, respect:

```http
Retry-After
```



## 5.11.2 Non-Retryable Failures

Do not repeatedly retry:

* HTTP `400`
* HTTP `401`
* HTTP `403`
* HTTP `404` caused by incorrect configuration
* HTTP `422`
* Schema incompatibility
* Invalid extraction configuration

These require configuration correction, data treatment or operational investigation.



## 5.11.3 Failure Outcome

When retries are exhausted:

1. Mark the entity run as failed.
2. Record the affected endpoint and page.
3. Record the final retry count.
4. Store the sanitised error code and message.
5. Do not update the watermark.
6. Prevent dependent transformations where critical.
7. Raise a monitoring alert.
8. Permit a controlled rerun using the same extraction window.



# 5.12 Idempotent Reruns

A rerun must not duplicate trusted Silver or Gold records.

Required controls:

* Stable business primary keys
* Raw payload hash
* Extraction run identifier
* Silver deduplication
* Delta `MERGE`
* Controlled overlap
* Watermark update after success only
* Duplicate API-page detection

Silver matching should use the business primary key.

When multiple copies exist, prefer the record with:

1. Latest valid `updated_at`
2. Highest `version_number`
3. Latest `_ingested_at` as the final technical tie-breaker

A rerun must preserve audit history rather than overwriting the original failed run.



# 5.13 Schema Validation

The API response must be validated against the expected data contract.

Validate:

* Required fields
* Field data types
* Primary identifier
* Timestamp format
* Schema version
* Response envelope
* Pagination structure
* Permitted controlled values

Schema outcomes:

| Outcome                   | Treatment                         |
| ------------------------- | --------------------------------- |
| Expected schema           | Continue                          |
| Optional field added      | Record and continue if compatible |
| Safe type widening        | Continue only when approved       |
| Required field missing    | Controlled failure or quarantine  |
| Field renamed             | Breaking change                   |
| Incompatible type         | Breaking change                   |
| Unexpected schema version | Stop affected entity publication  |

Bronze retains the raw payload even when Silver rejects the schema, provided the response is technically readable and safe to store.


# 5.14 Silver-Layer Processing

Silver processing will:

1. Read the relevant Bronze records.
2. Validate the expected schema.
3. Standardise timestamps to UTC.
4. Standardise identifiers and codes.
5. Apply decimal precision.
6. Validate controlled statuses.
7. Deduplicate overlapping records.
8. Apply referential-integrity checks.
9. Apply business-quality rules.
10. Quarantine invalid records.
11. Merge valid records by business key.
12. Record processing and quality metrics.

Silver must maintain the source business key and Bronze lineage metadata.



# 5.15 Data-Quality Rules

## 5.15.1 Supplier Rules

* `supplier_id` must be present.
* `supplier_code` must be unique.
* Supplier status must be valid.
* Country code must be valid.
* Currency code must be valid.
* Lead time cannot be negative.
* Inactive suppliers cannot accept new purchase orders.

## 5.15.2 Agreement Rules

* Supplier must exist.
* Product must exist.
* Agreed cost cannot be negative.
* Minimum order quantity must be greater than zero.
* End date cannot precede start date.
* Active agreements must reference active suppliers and products.

## 5.15.3 Purchase-Order Rules

* Purchase-order identifier must be unique.
* Supplier must exist.
* Distribution centre must exist.
* Order must contain at least one line.
* Ordered quantity must be greater than zero.
* Requested delivery date cannot precede order date.
* Header total must equal the sum of valid lines.
* Purchase-order currency must match line commercial terms.

## 5.15.4 Shipment Rules

* Shipment identifier must be unique.
* Purchase order must exist.
* Supplier must match the purchase order.
* Destination must match the purchase order.
* Shipment line must reference a valid purchase-order line.
* Shipment product must match the ordered product.
* Shipped quantity must be greater than zero.
* Cumulative shipped quantity must not exceed the permitted order quantity.
* Expiry date cannot precede manufacture or dispatch date.
* Status transition must be valid.

## 5.15.5 Delivery Rules

* Delivery attempt must reference a shipment.
* Destination must match the shipment.
* Attempt number must be sequential and positive.
* Arrival cannot precede dispatch.
* Unloading completion cannot precede unloading start.
* Rejected delivery must include a rejection reason.



# 5.16 Quarantine Framework

Invalid Silver records must be written to controlled quarantine tables.

Recommended table pattern:

```text
quarantine.<entity_name>
```

Required quarantine metadata:

| Field                   | Purpose                               |
| ----------------------- | ------------------------------------- |
| `quarantine_id`         | Unique quarantine record              |
| `run_id`                | Fabric execution                      |
| `source_entity`         | Entity                                |
| `source_primary_key`    | Original identifier                   |
| `rule_id`               | Failed rule                           |
| `rule_severity`         | Criticality                           |
| `failure_reason`        | Explanation                           |
| `raw_payload_reference` | Bronze lineage                        |
| `quarantined_at`        | Quarantine time                       |
| `resolution_status`     | Open, corrected, accepted or rejected |
| `resolved_at`           | Resolution time                       |
| `resolved_by`           | Responsible user or process           |

Quarantine records must not be silently deleted.


# 5.17 Source-to-Bronze Reconciliation

For every entity extraction, compare:

* API record count
* Bronze record count
* Number of API pages
* Minimum source timestamp
* Maximum source timestamp
* Quantity or monetary control totals where applicable
* Payload hash anomalies
* Technical rejection count

Required equation:

```text
API records returned
= Bronze records successfully persisted
+ Technical records explicitly rejected
```

Example:

```text
Source entity: shipment_lines
API records returned: 4,250
Bronze records written: 4,250
Technical records rejected: 0
Difference: 0
Result: Passed
```

A critical count difference prevents watermark advancement.



# 5.18 Bronze-to-Silver Reconciliation

Required equation:

```text
Distinct Bronze input
= Silver accepted
+ Quarantined
+ Valid duplicates removed
+ Superseded versions
```

Record separately:

* Bronze rows read
* Duplicate rows
* Latest valid records
* Silver inserts
* Silver updates
* Quarantined rows
* Superseded versions
* Unexplained difference

Any unexplained difference is a reconciliation failure.



# 5.19 Silver-to-Gold Reconciliation

Compare:

* Silver valid business events
* Gold fact records
* Quantity totals
* Monetary totals
* Unknown dimension members
* Unmatched business keys
* Excluded records with documented reasons

Gold publication must not produce unexplained loss or duplication.



# 5.20 Cross-System Business Reconciliation

## 5.20.1 Purchase-Order Reconciliation

```text
Ordered quantity
= Cancelled quantity
+ Received quantity
+ Outstanding quantity
```

Reconcile at:

* Purchase-order line
* Purchase order
* Supplier
* Product
* Distribution centre
* Reporting date



## 5.20.2 Shipment-to-Receipt Reconciliation

```text
Shipped quantity
= Received quantity
+ Confirmed in-transit quantity
+ Confirmed shortfall quantity
```

Possible statuses:

```text
MATCHED
PARTIALLY_RECEIVED
OVER_RECEIVED
SHORT_RECEIVED
AWAITING_RECEIPT
UNMATCHED_SHIPMENT
UNMATCHED_RECEIPT
```



## 5.20.3 Receipt-Quality Reconciliation

```text
Quantity received
= Quantity accepted
+ Quantity damaged
+ Quantity rejected
```

A difference is a critical warehouse data-quality failure.



## 5.20.4 Identifier Reconciliation

Validate that FastAPI and SQL warehouse records agree on:

* `supplier_id`
* `purchase_order_id`
* `purchase_order_line_id`
* `shipment_id`
* `shipment_line_id`
* `product_id`
* `distribution_centre_id`
* `batch_number` where applicable

Conflicting identifiers must be quarantined or flagged for investigation.



## 5.20.5 Inventory Reconciliation

The SQL warehouse and sales sources must eventually satisfy:

```text
Closing stock
= Opening stock
+ Supplier receipts
+ Transfers in
+ Customer returns
- Transfers out
- Store sales
- Online fulfilment
- Waste
+ Positive adjustments
- Negative adjustments
```

This reconciliation is outside the FastAPI database but depends on trusted supplier receipts and shared identifiers.



# 5.21 Reconciliation Severity

| Severity      | Example                                     | Required action                          |
| ------------- | ------------------------------------------- | ---------------------------------------- |
| Critical      | Source and Bronze counts do not match       | Stop entity and downstream publication   |
| Critical      | Receipt components do not balance           | Quarantine and stop affected publication |
| High          | Warehouse receipt has no shipment           | Quarantine and investigate               |
| High          | Shipment product differs from order product | Quarantine                               |
| Medium        | Shipment partially received                 | Load with business warning               |
| Medium        | Delivery later than expected                | Load and report                          |
| Low           | Optional description missing                | Load and record warning                  |
| Informational | Valid late-arriving update                  | Process normally                         |



# 5.22 Reconciliation Tolerances

Tolerances must be explicitly configured and versioned.

Examples:

| Measure                                  |                         Initial tolerance |
| ---------------------------------------- | ----------------------------------------: |
| Record-count difference                  |                                      Zero |
| Purchase-order monetary difference       |                                     £0.01 |
| Receipt quantity equation                |                                      Zero |
| Shipment versus receipt difference       | Business exception permitted but reported |
| Timestamp delay                          |                   Based on SLA and source |
| Duplicate primary keys in trusted Silver |                                      Zero |

Tolerances must not be hidden inside notebook code.



# 5.23 Supplier-Performance Measures

## On-Time Delivery

```text
On-time deliveries
÷ Completed deliveries
```

A delivery is on time when:

```text
actual_delivery_at <= expected_delivery_at
```

## In-Full Delivery

```text
Fully accepted shipment lines
÷ Completed shipment lines
```

## OTIF

```text
Deliveries both on time and in full
÷ Completed deliveries
```

## Damage Rate

```text
Damaged quantity
÷ Received quantity
```

## Rejection Rate

```text
Rejected quantity
÷ Received quantity
```

Every KPI must include:

* Definition version
* Effective date
* Numerator
* Denominator
* Exclusions
* Calculation timestamp



# 5.24 Late-Arriving Data

Late-arriving records must:

* Retain their original business timestamp.
* Receive the actual Fabric ingestion timestamp.
* Be processed through the configured overlap.
* Update the correct Silver record.
* Recalculate affected Gold aggregates.
* Trigger reconciliation for affected dates or partitions.
* Be counted in late-arrival monitoring.

Late records must not be assigned a false current business date.



# 5.25 Logical Deletions

Fabric must detect and preserve logical changes such as:

* Supplier deactivation
* Agreement termination
* Purchase-order cancellation
* Shipment cancellation
* Reference-record deactivation

Silver and Gold treatment depends on entity design:

* Current-state tables update the active status.
* Historical dimensions preserve prior versions where Type 2 applies.
* Transaction facts are not physically deleted without controlled correction.



# 5.26 Pipeline Dependency Rules

Recommended processing order:

```text
Products and distribution centres
→ Suppliers
→ Supplier-product agreements
→ Purchase orders
→ Purchase-order lines
→ Shipments
→ Shipment lines
→ Deliveries
→ Supplier-performance events
→ SQL goods receipts
→ Cross-system reconciliation
→ Gold publication
```

Reference and parent entities must be available before dependent validation.



# 5.27 Publication Gates

Gold and semantic-model refresh may proceed only when:

* All critical entities succeed.
* Critical schema checks pass.
* Source-to-Bronze reconciliation passes.
* Critical Bronze-to-Silver reconciliation passes.
* Critical data-quality thresholds pass.
* Cross-system reconciliation is within approved tolerance.
* Required source freshness SLAs are met.

A medium or low business exception may permit publication while producing a warning.


# 5.28 Monitoring Requirements

The monitoring dashboard must show:

* Pipeline name
* Run identifier
* Source system
* Entity
* Start and completion time
* Status
* Duration
* Records read
* Records written
* Records quarantined
* Pages processed
* Retry count
* HTTP status
* Failed endpoint
* Failed activity
* Watermark boundaries
* Freshness status
* Schema version
* Reconciliation status
* Error code
* Error message
* SLA breach flag

The dashboard must allow investigation from master pipeline to entity, API request and quality-rule failure.



# 5.29 Security Requirements

* Store API secrets in a secure connection or Azure Key Vault.
* Never store plain API keys in notebooks or GitHub.
* Use HTTPS for deployed extraction.
* Mask secrets in audit logs.
* Apply least-privilege access.
* Restrict quarantine data appropriately.
* Protect failure-simulation endpoints.
* Retain configuration-change audit history.
* Separate development, test and production-simulation configuration.



# 5.30 Recovery and Backfill

The platform must support:

* Rerunning a failed entity.
* Rerunning one extraction window.
* Replaying Bronze records.
* Backfilling a specified date range.
* Resetting a watermark through an audited process.
* Reprocessing quarantined records after correction.
* Rebuilding affected Silver or Gold partitions.
* Preserving original and recovery run identifiers.

Watermarks must never be manually changed without an audit record.


# 5.31 Testing Requirements

Required tests include:

* Successful full extraction
* Successful incremental extraction
* Multiple API pages
* Records sharing the same timestamp
* Empty incremental window
* HTTP 401
* HTTP 429
* HTTP 500
* HTTP 503
* Timeout
* Retry exhaustion
* Duplicate API response
* Late-arriving update
* Schema change
* Invalid JSON
* Missing supplier
* Missing product
* Shipment quantity exceeding order
* Unmatched goods receipt
* Receipt-quality imbalance
* Idempotent rerun
* Watermark not advanced after failure
* Gold publication blocked after critical failure


# 5.32 Phase 1 Acceptance Criteria

Phase 1 is complete when:

* Business requirements are documented.
* Entity relationships are approved.
* The logical database schema is defined.
* The version-one API contract is defined.
* Fabric extraction fields are defined.
* Full and incremental processing are defined.
* Pagination and watermarks are defined.
* Retry behaviour is defined.
* Audit requirements are defined.
* Data-quality and quarantine treatment are defined.
* All four reconciliation levels are defined.
* Cross-system business equations are documented.
* Security and recovery expectations are documented.
* Build scope and system ownership are unambiguous.


## 5.33 Deliverable Status

**Deliverable:** Phase 1.5 — Fabric Incremental-Ingestion and Reconciliation Specification
**Status:** Approved design baseline
**Phase status:** Phase 1 design complete
**Next phase:** Phase 2 — Shared Master-Data Design and Generation
