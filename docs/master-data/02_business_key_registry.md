 **Phase 2.2: Shared Business-Key Registry and Data Contracts**

# BritMart Shared Business-Key Registry

## 1. Purpose

This document defines the identifiers shared across BritMart’s operational source systems and Microsoft Fabric.

It ensures that FastAPI, SQL, SharePoint POS files, AWS S3, Eventstream and Fabric refer to the same business objects using stable and consistent identifiers.

The registry distinguishes between:

- Technical primary identifiers
- Human-readable business codes
- Source transaction identifiers
- Parent-child identifiers
- Idempotency keys
- Analytical surrogate keys


## 2. Identifier Principles

1. Every master and transaction record has one stable technical identifier.
2. Important records also have a readable business code.
3. Technical identifiers must not contain business meaning.
4. Business codes must not be reused.
5. Identifiers must not change when descriptions or attributes change.
6. Shared identifiers must be generated centrally or deterministically.
7. Different systems must not independently generate identifiers for the same object.
8. Fabric must preserve original source identifiers.
9. Gold dimensions may use surrogate keys without replacing source identifiers.
10. Deleted or inactive records must retain their historical identifiers.


## 3. Technical Identifier Standard

Master-data technical identifiers will use deterministic UUID version 5 values.

Conceptual generation input:

```text
BritMart namespace + entity type + business code
````

Example:

```text
britmart:product:PRD-000001
```

The same input must always generate the same UUID.

Transaction identifiers may use:

* Centrally generated UUIDs
* Source-controlled UUIDs
* Deterministic identifiers where regeneration is required

The authoritative source determines the transaction identifier.


## 4. Master Business-Key Registry

| Entity              | Technical key                   | Business key               | Format            | Owner                  |
| ------------------- | ------------------------------- | -------------------------- | ----------------- | ---------------------- |
| Region              | `region_id`                     | `region_code`              | `REG-###`         | SQL operational system |
| Distribution centre | `distribution_centre_id`        | `distribution_centre_code` | `DC-###`          | SQL operational system |
| Store               | `store_id`                      | `store_code`               | `STR-####`        | SQL operational system |
| Category            | `category_id`                   | `category_code`            | `CAT-##`          | SQL product master     |
| Subcategory         | `subcategory_id`                | `subcategory_code`         | `SUB-###`         | SQL product master     |
| Product             | `product_id`                    | `product_code`             | `PRD-######`      | SQL product master     |
| Product             | `product_id`                    | `sku`                      | `BM-########`     | SQL product master     |
| Supplier            | `supplier_id`                   | `supplier_code`            | `SUP-####`        | FastAPI                |
| Supplier agreement  | `supplier_product_agreement_id` | `agreement_code`           | `AGR-######`      | FastAPI                |
| Promotion           | `promotion_id`                  | `promotion_code`           | `PROMO-YYYY-####` | Pricing simulation     |
| Calendar date       | `calendar_date`                 | `date_key`                 | `YYYYMMDD`        | Shared generator       |

Rules:

* Technical keys are globally unique.
* Business keys are unique within their entity.
* Product code and SKU must both remain stable.
* No business key can be reassigned to a different record.
* Description changes must not generate new identifiers.


## 5. Transaction Business-Key Registry

| Entity              | Technical key            | Business identifier           | Format                    | Owner                |
| ------------------- | ------------------------ | ----------------------------- | ------------------------- | -------------------- |
| Purchase order      | `purchase_order_id`      | `purchase_order_number`       | `PO-YYYY-######`          | FastAPI              |
| Purchase-order line | `purchase_order_line_id` | Header plus line number       | `PO number + line number` | FastAPI              |
| Shipment            | `shipment_id`            | `shipment_number`             | `SHP-YYYY-######`         | FastAPI              |
| Shipment line       | `shipment_line_id`       | Shipment plus line identifier | Source controlled         | FastAPI              |
| Delivery attempt    | `delivery_attempt_id`    | `delivery_reference`          | `DEL-YYYY-######`         | FastAPI              |
| Goods receipt       | `goods_receipt_id`       | `goods_receipt_number`        | `GRN-YYYY-######`         | SQL warehouse system |
| Goods-receipt line  | `goods_receipt_line_id`  | Receipt plus line number      | Source controlled         | SQL warehouse        |
| Transfer            | `transfer_id`            | `transfer_number`             | `TRF-YYYY-######`         | SQL warehouse        |
| POS receipt         | `pos_receipt_id`         | `receipt_number`              | `POS-STORE-DATE-######`   | Store POS            |
| POS line            | `pos_line_id`            | Receipt plus line number      | Source controlled         | Store POS            |
| Online order        | `online_order_id`        | `online_order_number`         | `ONL-YYYY-########`       | E-commerce           |
| Online-order line   | `online_order_line_id`   | Order plus line number        | Source controlled         | E-commerce           |
| Inventory movement  | `inventory_movement_id`  | `movement_reference`          | `MOV-YYYY-########`       | SQL warehouse        |
| Inventory snapshot  | Composite source key     | Location, product and date    | Composite                 | SQL warehouse        |


## 6. Cross-System Identifier Requirements

### 6.1 Supplier Shipment to Warehouse Receipt

The SQL warehouse goods receipt must retain:

* `supplier_id`
* `purchase_order_id`
* `purchase_order_line_id`
* `shipment_id`
* `shipment_line_id`
* `product_id`
* `distribution_centre_id`
* `batch_number` where applicable

This allows Fabric to reconcile ordered, shipped and received quantities.

### 6.2 Warehouse Transfer to Store Inventory

Warehouse transfers must retain:

* `transfer_id`
* `distribution_centre_id`
* `store_id`
* `product_id`
* `dispatch_at`
* `received_at`

### 6.3 Store Sales

POS files must retain:

* `pos_receipt_id`
* `pos_line_id`
* `store_id`
* `product_id`
* `promotion_id` where applicable
* `transaction_at`
* `trading_date`

### 6.4 Online Orders

Online data must retain:

* `online_order_id`
* `online_order_line_id`
* `product_id`
* `fulfilment_location_id`
* `promotion_id` where applicable
* `customer_id` as a synthetic pseudonymous identifier
* `created_at`
* `updated_at`

### 6.5 Eventstream Events

Streaming events must retain:

* `event_id`
* `event_type`
* Relevant operational entity identifier
* `event_occurred_at`
* `event_published_at`
* `event_version`
* `correlation_id`

An event must not rely only on a description to identify the affected order or shipment.

---

## 7. Parent-Child Key Rules

| Parent              | Child                      | Required parent identifier       |
| ------------------- | -------------------------- | -------------------------------- |
| Region              | Distribution centre        | `region_id`                      |
| Region              | Store                      | `region_id`                      |
| Distribution centre | Store                      | `primary_distribution_centre_id` |
| Category            | Subcategory                | `category_id`                    |
| Subcategory         | Product                    | `subcategory_id`                 |
| Supplier            | Supplier-product agreement | `supplier_id`                    |
| Product             | Supplier-product agreement | `product_id`                     |
| Supplier            | Purchase order             | `supplier_id`                    |
| Distribution centre | Purchase order             | `distribution_centre_id`         |
| Purchase order      | Purchase-order line        | `purchase_order_id`              |
| Purchase order      | Shipment                   | `purchase_order_id`              |
| Purchase-order line | Shipment line              | `purchase_order_line_id`         |
| Shipment            | Shipment line              | `shipment_id`                    |
| Shipment            | Delivery attempt           | `shipment_id`                    |
| Shipment            | Goods receipt              | `shipment_id`                    |
| Goods receipt       | Goods-receipt line         | `goods_receipt_id`               |
| Store               | POS receipt                | `store_id`                       |
| POS receipt         | POS line                   | `pos_receipt_id`                 |
| Online order        | Online-order line          | `online_order_id`                |

A child record must not be generated before its required parent exists.


## 8. Composite-Key Rules

Composite keys may support source uniqueness but must not replace stable technical identifiers where individual record identity is required.

Approved composite uniqueness examples:

```text
purchase_order_id + line_number
shipment_id + shipment_line_number
goods_receipt_id + line_number
pos_receipt_id + line_number
online_order_id + line_number
store_id + product_id + effective_from
location_id + product_id + snapshot_date
supplier_id + product_id + effective_from
```

Fabric must preserve every component of a composite source key.


## 9. Identifier Immutability

The following must never change after creation:

* Technical UUID
* Business code
* Purchase-order number
* Shipment number
* Goods-receipt number
* POS receipt number
* Online-order number
* Original source-system identifier

If an identifier was created incorrectly:

1. Do not overwrite historical records silently.
2. Record a controlled correction.
3. Cancel or deactivate the incorrect record where appropriate.
4. Create a correct replacement identifier if required.
5. Preserve the relationship between the incorrect and replacement records.


## 10. Analytical Surrogate Keys

Fabric Gold dimensions may use integer surrogate keys such as:

* `product_key`
* `supplier_key`
* `store_key`
* `distribution_centre_key`
* `promotion_key`
* `date_key`

Surrogate-key rules:

1. They are created in the analytical platform.
2. They do not replace source identifiers.
3. Facts retain or can trace back to source business keys.
4. Type 2 dimension versions receive separate surrogate keys.
5. Unknown members use controlled default keys.
6. Surrogate keys must not be written back to operational systems.

Recommended unknown-member values:

|  Key | Meaning                                |
| ---: | -------------------------------------- |
| `-1` | Unknown or unresolved                  |
| `-2` | Not applicable                         |
| `-3` | Data-quality error under investigation |


## 11. Idempotency Keys

Important create operations require an idempotency key.

Protected operations include:

* Supplier creation
* Supplier-agreement creation
* Purchase-order creation
* Shipment creation
* Delivery-attempt creation
* Supplier-performance-event creation

The uniqueness scope is:

```text
api_client_id + operation_name + idempotency_key
```

Repeating the same request with the same key returns the original outcome.

Using the same key with a different payload returns a conflict.


## 12. Identifier Data Contract

Every shared identifier must define:

| Contract property | Requirement                   |
| ----------------- | ----------------------------- |
| Field name        | Exact agreed name             |
| Data type         | UUID, string, integer or date |
| Required status   | Required or optional          |
| Format            | Documented pattern            |
| Owner             | Authoritative system          |
| Uniqueness        | Entity or composite scope     |
| Mutability        | Normally immutable            |
| Nullable rule     | Explicit                      |
| Example           | Synthetic valid value         |
| Consumers         | Systems using the identifier  |
| Effective date    | Contract start                |
| Schema version    | Contract version              |


## 13. Naming Consistency

The same concept must use the same field name across systems wherever practical.

Use:

```text
supplier_id
product_id
store_id
distribution_centre_id
purchase_order_id
purchase_order_line_id
shipment_id
shipment_line_id
goods_receipt_id
online_order_id
promotion_id
```

Avoid unexplained variations such as:

```text
supplierID
supplier_number
vendor_key
supp_id
```

When a source cannot follow the canonical name, Fabric metadata must contain an explicit source-to-canonical mapping.


## 14. Source-to-Canonical Mapping

Required mapping fields:

* `source_system`
* `source_entity`
* `source_field_name`
* `canonical_entity`
* `canonical_field_name`
* `source_data_type`
* `canonical_data_type`
* `transformation_rule`
* `required_flag`
* `schema_version`
* `effective_from`
* `effective_to`

Mapping logic must not be hidden only inside notebook code.


## 15. Data-Contract Versioning

Initial contract version:

```text
1.0
```

Version changes:

| Change                     | Treatment                 |
| -------------------------- | ------------------------- |
| Optional field added       | Minor compatible change   |
| Description clarified      | Documentation change      |
| Safe validation expansion  | Reviewed minor change     |
| Required field added       | Potential breaking change |
| Field renamed              | Breaking change           |
| Identifier type changed    | Breaking change           |
| Identifier meaning changed | Breaking change           |
| Field removed              | Breaking change           |

Breaking API contract changes require a new major version.


## 16. Identifier Validation Rules

The generator and pipelines must validate:

* Technical key is present.
* Technical key has the correct UUID format.
* Business key follows the required pattern.
* Business key is unique.
* Parent key exists.
* Identifier has not been reused.
* Source-system owner is correct.
* Required cross-system identifiers are present.
* Composite keys are unique.
* Technical and business identifiers map one-to-one.
* No unexpected whitespace exists.
* Identifier comparison is case controlled.

Critical identifier failures must be quarantined.


## 17. Referential-Integrity Reconciliation

Required checks include:

```text
Every product → one valid subcategory
Every subcategory → one valid category
Every store → one valid region
Every store → one valid distribution centre
Every agreement → one valid supplier and product
Every purchase order → one valid supplier and distribution centre
Every purchase-order line → one valid purchase order and product
Every shipment → one valid purchase order
Every shipment line → one valid shipment and purchase-order line
Every receipt → one valid shipment where a reference is expected
Every POS line → one valid store and product
Every online-order line → one valid order and product
```

Unmatched external records must be preserved for investigation rather than discarded.


## 18. Contract Storage

The project will eventually store machine-readable contracts under:

```text
data-contracts/
```

Recommended future files:

```text
data-contracts/
├── region.schema.json
├── distribution_centre.schema.json
├── store.schema.json
├── category.schema.json
├── subcategory.schema.json
├── product.schema.json
├── supplier.schema.json
├── supplier_product_agreement.schema.json
└── shared_identifiers.yaml
```

The Markdown document explains the design. Machine-readable contracts will support automated validation.


## 19. Acceptance Criteria

The business-key registry is approved when:

* Every shared entity has an owner.
* Technical and business keys are defined.
* Identifier formats are defined.
* Parent-child relationships are documented.
* Cross-system reconciliation identifiers are present.
* Identifier immutability is defined.
* Composite-key rules are documented.
* Fabric surrogate-key treatment is defined.
* Idempotency-key scope is defined.
* Data-contract versioning is defined.
* Validation rules are defined.
* Future machine-readable contract locations are defined.


## 20. Deliverable Status

**Deliverable:** Phase 2.2 — Shared Business-Key Registry and Data Contracts
**Status:** Approved design baseline
**Next deliverable:** Phase 2.3 — UK Regions, Distribution Centres and Store Master Data
