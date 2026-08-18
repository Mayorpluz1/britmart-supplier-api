# BritMart Supplier System Business Requirements

## 1.1 System Purpose

The BritMart Supplier and Procurement API will operate as an independent transactional source system used by BritMart’s procurement and supplier-management teams.

It will manage the following business process:

```text
Supplier
→ Supplier-product agreement
→ Purchase order
→ Purchase-order line
→ Supplier shipment
→ Shipment line
→ Distribution-centre delivery
→ Supplier performance event
```

The application will not be built merely to provide data to Microsoft Fabric. It will maintain its own operational database, business rules, API contracts, validation, authentication, logging and transaction history.

Microsoft Fabric will consume authorised data from the API for ingestion, analytics, reconciliation and operational monitoring.

---

## 1.2 Business Objectives

| ID      | Objective                                                            |
| ------- | -------------------------------------------------------------------- |
| OBJ-001 | Maintain a controlled register of BritMart suppliers.                |
| OBJ-002 | Identify the products each supplier is approved to supply.           |
| OBJ-003 | Create and manage purchase orders and purchase-order lines.          |
| OBJ-004 | Track partial and complete supplier shipments.                       |
| OBJ-005 | Track expected and actual delivery performance.                      |
| OBJ-006 | Reconcile ordered, shipped and warehouse-received quantities.        |
| OBJ-007 | Measure supplier timeliness, completeness and delivery quality.      |
| OBJ-008 | Provide reliable incremental data to Microsoft Fabric.               |
| OBJ-009 | Simulate realistic operational, technical and data-quality failures. |
| OBJ-010 | Maintain auditable business changes and application request logs.    |

---

## 1.3 Users and Responsibilities

| User or consumer                  | Responsibility                                                     |
| --------------------------------- | ------------------------------------------------------------------ |
| Procurement officer               | Creates and maintains purchase orders.                             |
| Procurement manager               | Approves, cancels or closes purchase orders.                       |
| Supplier manager                  | Maintains supplier status, agreements and performance information. |
| Supplier integration process      | Submits shipment and dispatch information.                         |
| Distribution-centre operation     | Records physical goods receipts in the SQL warehouse system.       |
| Microsoft Fabric                  | Extracts API data for processing, reconciliation and analytics.    |
| Platform administrator            | Manages configuration, API keys and controlled failure simulation. |
| Data engineer or support engineer | Investigates API, pipeline and data-quality incidents.             |

The first version will not require a complete graphical user interface. FastAPI Swagger documentation will provide the initial controlled interface for testing and demonstrating API operations.

---

## 1.4 Functional Requirements

### 1.4.1 Supplier Management

| ID         | Requirement                                                                     |
| ---------- | ------------------------------------------------------------------------------- |
| FR-SUP-001 | Create a supplier with a unique `SupplierID` and supplier code.                 |
| FR-SUP-002 | Retrieve an individual supplier or a paginated list of suppliers.               |
| FR-SUP-003 | Update permitted supplier attributes.                                           |
| FR-SUP-004 | Support `PENDING`, `ACTIVE`, `SUSPENDED` and `INACTIVE` statuses.               |
| FR-SUP-005 | Prevent purchase orders from being created for suspended or inactive suppliers. |
| FR-SUP-006 | Store supplier country, lead time, currency and delivery capabilities.          |
| FR-SUP-007 | Preserve `created_at` and `updated_at` timestamps.                              |
| FR-SUP-008 | Support logical deactivation rather than immediate physical deletion.           |
| FR-SUP-009 | Preserve supplier-status history for audit and analytical purposes.             |

### 1.4.2 Supplier-Product Agreements

| ID         | Requirement                                                                        |
| ---------- | ---------------------------------------------------------------------------------- |
| FR-SPA-001 | Identify the products a supplier is authorised to supply.                          |
| FR-SPA-002 | Store agreed cost, currency, lead time and minimum order quantity.                 |
| FR-SPA-003 | Support agreement start and end dates.                                             |
| FR-SPA-004 | Prevent ordering a product outside an active supplier agreement.                   |
| FR-SPA-005 | Support primary and alternative suppliers for products.                            |
| FR-SPA-006 | Retain historical supplier-product agreements.                                     |
| FR-SPA-007 | Prevent overlapping active agreements where the business rules do not permit them. |

The SQL operational system remains the authoritative owner of the product master. FastAPI stores the approved `ProductID` reference and the supplier-specific commercial agreement.

### 1.4.3 Purchase Orders

| ID        | Requirement                                                                       |
| --------- | --------------------------------------------------------------------------------- |
| FR-PO-001 | Create a purchase order for one supplier and one destination distribution centre. |
| FR-PO-002 | Allow multiple product lines on each purchase order.                              |
| FR-PO-003 | Store order date, expected delivery date, currency and commercial totals.         |
| FR-PO-004 | Validate the supplier and relevant supplier-product agreements.                   |
| FR-PO-005 | Support draft, approval, fulfilment, completion and cancellation statuses.        |
| FR-PO-006 | Prevent shipments against an unapproved purchase order.                           |
| FR-PO-007 | Allow controlled amendments before shipment.                                      |
| FR-PO-008 | Prevent ordered quantities from being negative or zero.                           |
| FR-PO-009 | Calculate line and purchase-order totals using fixed-precision decimal values.    |
| FR-PO-010 | Preserve purchase-order status and amendment history.                             |
| FR-PO-011 | Support partial shipment and partial receipt.                                     |
| FR-PO-012 | Identify ordered, cancelled, shipped, received and outstanding quantities.        |
| FR-PO-013 | Prevent duplicate purchase-order numbers.                                         |
| FR-PO-014 | Prevent unauthorised changes after the purchase order reaches a terminal status.  |

### 1.4.4 Supplier Shipments

| ID         | Requirement                                                                        |
| ---------- | ---------------------------------------------------------------------------------- |
| FR-SHP-001 | Create one or more shipments against an approved purchase order.                   |
| FR-SHP-002 | Prevent shipment of products not included on the purchase order.                   |
| FR-SHP-003 | Prevent shipped quantities from exceeding the permitted outstanding quantity.      |
| FR-SHP-004 | Store dispatch, expected-delivery and actual-delivery timestamps.                  |
| FR-SHP-005 | Store carrier and tracking information.                                            |
| FR-SHP-006 | Support ambient, chilled and frozen shipment types.                                |
| FR-SHP-007 | Store batch or lot number and expiry date where applicable.                        |
| FR-SHP-008 | Support created, dispatched, in-transit, delayed, delivered and rejected statuses. |
| FR-SHP-009 | Support late-arriving shipment updates.                                            |
| FR-SHP-010 | Preserve shipment-status history.                                                  |
| FR-SHP-011 | Use an idempotency key to prevent accidental duplicate shipment creation.          |
| FR-SHP-012 | Validate that expiry dates follow dispatch dates where applicable.                 |
| FR-SHP-013 | Allow partial shipment of an individual purchase-order line.                       |

### 1.4.5 Delivery and Receipt Reconciliation

FastAPI records the supplier’s shipment and delivery declaration. The SQL warehouse system records the physical goods received by BritMart.

| ID         | Requirement                                                                            |
| ---------- | -------------------------------------------------------------------------------------- |
| FR-REC-001 | Expose shipment identifiers required by the warehouse receipt process.                 |
| FR-REC-002 | Allow Fabric to match shipment lines to SQL goods-receipt lines.                       |
| FR-REC-003 | Compare ordered, shipped, received, accepted, damaged and rejected quantities.         |
| FR-REC-004 | Identify unmatched shipments and goods receipts.                                       |
| FR-REC-005 | Identify over-delivery, short-delivery, late-delivery and damaged-delivery conditions. |
| FR-REC-006 | Preserve discrepancies rather than silently correcting them.                           |
| FR-REC-007 | Assign reconciliation status and severity within Fabric.                               |
| FR-REC-008 | Support line-level and purchase-order-level reconciliation.                            |
| FR-REC-009 | Support configurable reconciliation tolerances.                                        |

The operational API supplies source facts. Microsoft Fabric performs the cross-system analytical reconciliation.

### 1.4.6 Supplier Performance

| ID          | Requirement                                                                                |
| ----------- | ------------------------------------------------------------------------------------------ |
| FR-PERF-001 | Provide the fields required to calculate on-time delivery.                                 |
| FR-PERF-002 | Provide the fields required to calculate in-full delivery.                                 |
| FR-PERF-003 | Support OTIF calculations after joining warehouse receipts.                                |
| FR-PERF-004 | Support damage and rejection-rate calculations.                                            |
| FR-PERF-005 | Support analysis by supplier, product, category, distribution centre and reporting period. |
| FR-PERF-006 | Record supplier performance events such as delays and quality incidents.                   |
| FR-PERF-007 | Preserve the KPI-definition version used for performance calculations.                     |

Microsoft Fabric will calculate the official supplier-performance indicators. The operational system may provide provisional information but will not own Gold-layer analytical calculations.

---

## 1.5 Status-Transition Requirements

### 1.5.1 Supplier Status

```text
PENDING → ACTIVE
ACTIVE → SUSPENDED
SUSPENDED → ACTIVE
ACTIVE → INACTIVE
SUSPENDED → INACTIVE
```

An inactive supplier cannot return directly to active status without an approved reactivation process.

### 1.5.2 Purchase-Order Status

```text
DRAFT
→ APPROVED
→ PARTIALLY_SHIPPED
→ FULLY_SHIPPED
→ PARTIALLY_RECEIVED
→ COMPLETED
```

Alternative terminal states are:

```text
CANCELLED
CLOSED_WITH_SHORTFALL
```

### 1.5.3 Shipment Status

```text
CREATED
→ DISPATCHED
→ IN_TRANSIT
→ DELIVERED
```

Permitted alternative statuses include:

```text
DELAYED
PARTIALLY_DELIVERED
REJECTED
CANCELLED
```

The application must reject impossible transitions such as:

```text
CREATED → DELIVERED
DELIVERED → DISPATCHED
CANCELLED → IN_TRANSIT
```

Administrative corrections must use a separately logged correction process.

---

## 1.6 Core Business Rules

### 1.6.1 Purchase-Order Quantity

```text
Ordered quantity
= Cancelled quantity
+ Received quantity
+ Outstanding quantity
```

Received quantities originate from the SQL warehouse system and are reconciled in Microsoft Fabric.

### 1.6.2 Shipment Quantity

```text
Total shipped quantity for a purchase-order line
≤ Ordered quantity - Cancelled quantity
```

### 1.6.3 Receipt-Quality Quantity

```text
Received quantity
= Accepted quantity
+ Damaged quantity
+ Rejected quantity
```

### 1.6.4 Delivery Performance

A shipment is considered on time when:

```text
actual_delivery_at ≤ expected_delivery_at
```

A configurable grace period may be applied during analytical reporting, but the original timestamps must not be modified.

### 1.6.5 In-Full Performance

A shipment line is considered delivered in full when:

```text
accepted quantity ≥ expected shipment quantity
```

The precise OTIF definition must be versioned because different organisations may calculate it differently.

### 1.6.6 Currency and Monetary Values

* Use three-character currency codes.
* Store monetary fields using fixed-precision decimal values.
* Do not use floating-point values for money.
* Each purchase order must use one transaction currency.
* Currency conversion will be performed in Fabric using a controlled exchange-rate dataset.

### 1.6.7 Date and Time

* Store application timestamps in Coordinated Universal Time.
* Retain the original source timezone where it has business value.
* Use UK local trading dates for business reporting.
* Account for British Summer Time.
* Do not rely implicitly on server-local time.



## 1.7 API Requirements

The first API version must support:

* API versioning through `/api/v1`.
* JSON request and response bodies.
* Swagger/OpenAPI documentation.
* API-key authentication.
* Pagination.
* Filtering.
* Stable sorting.
* Incremental extraction.
* Appropriate HTTP status codes.
* Structured error responses.
* Correlation and request identifiers.
* Health and readiness endpoints.
* Controlled failure simulation.
* Rate-limit simulation.
* Idempotent creation operations.
* Request and response logging without exposing secrets.

Paginated list endpoints must return records and pagination metadata.

Example:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total_records": 10000,
    "total_pages": 100,
    "has_next": true
  }
}


## 1.8 Microsoft Fabric Extraction Requirements

Microsoft Fabric must be able to:

* Extract each entity independently.
* Request a stable page size.
* Filter records using `updated_since`.
* Supply an upper extraction boundary.
* Sort records by `updated_at` and business identifier.
* Resume pagination safely.
* Identify the API schema version.
* Capture source record counts.
* Capture minimum and maximum update timestamps.
* Reprocess an earlier extraction window.
* Detect logically deleted records.
* Retry transient failures.
* Avoid retrying permanent authentication or validation failures.

The recommended incremental condition is:

```text
updated_at > lower_watermark
AND updated_at <= extraction_upper_bound
```

For records sharing the same timestamp, stable ordering must use:

```text
updated_at, entity_id
```

A configurable overlap window will protect against late commits and timestamp-boundary problems.


## 1.9 Non-Functional Requirements

### 1.9.1 Availability and Reliability

* Health endpoints should respond independently from business endpoints where possible.
* Database readiness must be checked separately.
* Transient failures may be retried.
* Failed transactions must not leave partially written business data.
* Duplicate requests must not create duplicate purchase orders or shipments.
* The application must support controlled restart without data corruption.

### 1.9.2 Performance

| Operation                           |                         Initial target |
| ----------------------------------- | -------------------------------------: |
| Health endpoint                     |         Under 200 milliseconds locally |
| Single-record lookup                |         Under 500 milliseconds locally |
| Paginated list request              | Under one second for normal page sizes |
| Default page size                   |                            100 records |
| Maximum page size                   |                          1,000 records |
| Initial Fabric extraction page size |                            500 records |

These are BritMart project service targets and not claims about a real retailer.

### 1.9.3 Security

* API keys must not be stored in application source code.
* Secrets must be provided through environment configuration.
* Logs must mask authentication values.
* Database access must follow least-privilege principles.
* The deployed API must use HTTPS.
* Administrative failure endpoints must be disabled or protected outside development and test environments.
* Sensitive configuration must not be committed to GitHub.

### 1.9.4 Auditability

The application must record:

* Request identifier
* Request timestamp
* Endpoint
* HTTP method
* Response status
* Response duration
* Client identifier
* Relevant entity identifier
* Error code
* Error message
* Application version
* Environment

### 1.9.5 Maintainability

* Use modular routers, schemas, database models and service layers.
* Separate configuration from application logic.
* Use controlled database migrations.
* Provide automated tests.
* Document business rules and architecture decisions.
* Pin or lock production dependencies.
* Use consistent formatting, linting and naming conventions.


## 1.10 Controlled Failure Scenarios

The system must eventually support controlled simulation of:

* HTTP 401 authentication failure
* HTTP 429 rate limiting
* HTTP 500 internal server error
* HTTP 503 service unavailable
* Delayed response or timeout
* Duplicate shipment
* Missing supplier identifier
* Missing product identifier
* Invalid quantity
* Invalid date sequence
* Schema change
* Late-arriving update
* Pagination inconsistency
* Database unavailability

Failure simulation must be protected by environment configuration and must not be unintentionally enabled in the production simulation environment.


## 1.11 Out of Scope for Version 1

The following are excluded from the first version:

* Complete supplier portal user interface
* Supplier invoicing and payments
* Full three-way financial matching
* Direct-to-store supplier deliveries
* Workforce management
* Customer loyalty programme
* Machine-learning demand forecasting
* Complete product-recall workflow
* Kubernetes deployment
* Multiple FastAPI microservices
* Docker deployment before local development works

Batch number and expiry-date fields will still be retained so product recall can be introduced later.


## 1.12 Assumptions and Constraints

* BritMart is a fictional UK retailer.
* The initial implementation will contain approximately 50 suppliers.
* Products, stores and distribution centres are mastered outside FastAPI.
* Suppliers deliver to distribution centres in version 1.
* Microsoft Fabric performs enterprise reconciliation and analytical reporting.
* SQLite may be used during early development.
* PostgreSQL or Azure SQL should be used for the final deployed version.
* The dataset will be synthetic but logically consistent.
* All source systems must use the agreed shared business identifiers.
* Project scale will be appropriate for a portfolio while preserving realistic business relationships.



## 1.13 Acceptance Criteria

The business-requirements deliverable is complete when:

* Every entity has a defined business purpose.
* Each operational entity has one authoritative owner.
* Shared identifiers are defined.
* Status transitions are documented.
* Quantity and monetary rules are unambiguous.
* Fabric extraction requirements are documented.
* Reconciliation responsibilities between FastAPI, SQL and Fabric are clear.
* Version 1 scope is controlled.
* Failure simulation cannot accidentally operate in the production simulation.
* Requirements can be traced to database fields, API endpoints and automated tests.


## 1.14 Deliverable Status

**Deliverable:** Phase 1.1 — Business Requirements
**Status:** Approved design baseline
**Next deliverable:** Phase 1.2 — Entity and Relationship Model
