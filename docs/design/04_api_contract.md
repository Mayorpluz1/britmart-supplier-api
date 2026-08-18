# BritMart Supplier System API Contract

## 4.1 Purpose

This document defines the version-one REST API contract for the BritMart Supplier and Procurement system.

It specifies:

- Endpoint paths
- HTTP methods
- Authentication
- Request and response structures
- Pagination
- Filtering and sorting
- Incremental extraction
- Idempotency
- Error responses
- HTTP status codes
- API versioning
- Controlled failure simulation

The base version-one path is:

```text
/api/v1
````


## 4.2 API Design Principles

The API must:

* Use nouns for resources.
* Use standard HTTP methods.
* Return JSON.
* Use plural resource names.
* Return consistent response envelopes.
* Use stable business identifiers.
* Support pagination for collection endpoints.
* Support incremental extraction for Fabric.
* Reject invalid requests clearly.
* Avoid exposing database implementation details.
* Preserve backward compatibility within version 1.
* Use idempotency protection for important creation requests.


## 4.3 Authentication

Protected endpoints require:

```http
X-API-Key: <api-key>
```

The application must:

* Validate the API key securely.
* Store only a secure hash of the key.
* Reject missing or invalid keys.
* Mask keys in logs.
* Associate each request with an API client.
* Support key expiration and deactivation.

Missing or invalid authentication returns:

```http
401 Unauthorized
```

Authenticated clients without permission return:

```http
403 Forbidden
```


## 4.4 Standard Request Headers

| Header            |                              Required | Purpose                                |
| ----------------- | ------------------------------------: | -------------------------------------- |
| `X-API-Key`       |                                   Yes | Client authentication                  |
| `X-Request-ID`    |                                    No | Client-supplied correlation identifier |
| `Idempotency-Key` | Required for selected POST operations | Duplicate-request prevention           |
| `Content-Type`    |           Required for request bodies | `application/json`                     |
| `Accept`          |                           Recommended | `application/json`                     |

If `X-Request-ID` is absent, the API generates one.

The response must return:

```http
X-Request-ID: <request-id>
```


## 4.5 Standard Single-Resource Response

```json
{
  "data": {
    "resource_id": "uuid"
  },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "response_timestamp": "2026-08-15T22:00:00Z"
  }
}
```


## 4.6 Standard Page-Based Collection Response

Page-based pagination supports interactive use and ordinary API exploration.

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total_records": 10000,
    "total_pages": 100,
    "has_next": true,
    "has_previous": false
  },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "response_timestamp": "2026-08-15T22:00:00Z"
  }
}
```

Rules:

* Default `page` is `1`.
* Default `page_size` is `100`.
* Maximum `page_size` is `1000`.
* Invalid page values return `422`.
* Stable sorting is mandatory.


## 4.7 Cursor-Based Incremental Response

Microsoft Fabric should use cursor-based pagination for incremental extraction because it is safer than page-number pagination when records change during extraction.

Example:

```json
{
  "data": [],
  "pagination": {
    "page_size": 500,
    "next_cursor": "opaque-cursor-value",
    "has_next": true
  },
  "extraction": {
    "updated_since": "2026-08-01T00:00:00Z",
    "updated_before": "2026-08-15T02:00:00Z",
    "minimum_updated_at": "2026-08-01T00:10:00Z",
    "maximum_updated_at": "2026-08-14T23:59:40Z",
    "records_returned": 500
  },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "schema_version": "1.0",
    "response_timestamp": "2026-08-15T02:00:01Z"
  }
}
```

The cursor must be:

* Opaque to clients.
* Bound to the extraction filters.
* Based on `updated_at` and the primary identifier.
* Rejected if altered or used with incompatible filters.


# 4.8 Health and Service Endpoints

## 4.8.1 Liveness Check

```http
GET /health
```

Purpose:

Confirms that the FastAPI process is running.

Authentication:

Not required.

Response:

```json
{
  "status": "healthy",
  "service": "britmart-supplier-api",
  "version": "1.0.0",
  "timestamp": "2026-08-15T22:00:00Z"
}
```

Expected status:

```http
200 OK
```


## 4.8.2 Readiness Check

```http
GET /ready
```

Purpose:

Confirms that the application can serve operational requests and connect to its database.

Possible responses:

```http
200 OK
503 Service Unavailable
```

Example unavailable response:

```json
{
  "status": "not_ready",
  "checks": {
    "database": "unavailable"
  }
}
```


# 4.9 Supplier Endpoints

## 4.9.1 List Suppliers

```http
GET /api/v1/suppliers
```

Supported parameters:

| Parameter        | Type      | Required | Purpose                    |
| ---------------- | --------- | -------: | -------------------------- |
| `page`           | Integer   |       No | Page number                |
| `page_size`      | Integer   |       No | Records per page           |
| `status`         | String    |       No | Filter by supplier status  |
| `country_code`   | String    |       No | Filter by country          |
| `active_flag`    | Boolean   |       No | Filter active records      |
| `updated_since`  | Timestamp |       No | Lower incremental boundary |
| `updated_before` | Timestamp |       No | Upper incremental boundary |
| `cursor`         | String    |       No | Continue cursor extraction |
| `sort_by`        | String    |       No | Approved sortable field    |
| `sort_order`     | String    |       No | `asc` or `desc`            |

Default incremental order:

```text
updated_at ASC, supplier_id ASC
```

Response:

```http
200 OK
```


## 4.9.2 Retrieve Supplier

```http
GET /api/v1/suppliers/{supplier_id}
```

Responses:

```http
200 OK
404 Not Found
```


## 4.9.3 Create Supplier

```http
POST /api/v1/suppliers
```

Required header:

```http
Idempotency-Key: <unique-key>
```

Example request:

```json
{
  "supplier_code": "SUP-0001",
  "supplier_name": "Northern Fresh Produce",
  "legal_name": "Northern Fresh Produce Limited",
  "country_code": "GB",
  "default_currency_code": "GBP",
  "standard_lead_time_days": 3,
  "supports_ambient": true,
  "supports_chilled": true,
  "supports_frozen": false
}
```

Successful response:

```http
201 Created
```

Other responses:

```http
400 Bad Request
401 Unauthorized
409 Conflict
422 Unprocessable Entity
```


## 4.9.4 Update Supplier

```http
PATCH /api/v1/suppliers/{supplier_id}
```

Only permitted attributes may be changed.

The request should include the expected `version_number` to prevent lost updates.

Responses:

```http
200 OK
404 Not Found
409 Conflict
422 Unprocessable Entity
```


## 4.9.5 Change Supplier Status

```http
POST /api/v1/suppliers/{supplier_id}/status-transitions
```

Example request:

```json
{
  "new_status": "SUSPENDED",
  "change_reason": "Repeated quality failures",
  "expected_version_number": 4
}
```

Responses:

```http
200 OK
404 Not Found
409 Conflict
422 Unprocessable Entity
```


## 4.9.6 Retrieve Supplier Status History

```http
GET /api/v1/suppliers/{supplier_id}/status-history
```

Response:

```http
200 OK
```


# 4.10 Product and Distribution-Centre Reference Endpoints

These endpoints are read-only to ordinary API clients.

## 4.10.1 List Products

```http
GET /api/v1/products
```

Filters:

* `category_id`
* `subcategory_id`
* `storage_type`
* `active_flag`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


## 4.10.2 Retrieve Product

```http
GET /api/v1/products/{product_id}
```


## 4.10.3 List Distribution Centres

```http
GET /api/v1/distribution-centres
```

Filters:

* `region`
* `active_flag`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


## 4.10.4 Retrieve Distribution Centre

```http
GET /api/v1/distribution-centres/{distribution_centre_id}
```

Product and distribution-centre reference updates are performed through controlled synchronisation processes, not public endpoints.


# 4.11 Supplier-Product Agreement Endpoints

## 4.11.1 List Agreements

```http
GET /api/v1/supplier-product-agreements
```

Filters:

* `supplier_id`
* `product_id`
* `agreement_status`
* `effective_on`
* `primary_supplier_flag`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


## 4.11.2 Retrieve Agreement

```http
GET /api/v1/supplier-product-agreements/{agreement_id}
```


## 4.11.3 Create Agreement

```http
POST /api/v1/supplier-product-agreements
```

Required:

```http
Idempotency-Key
```

Successful response:

```http
201 Created
```


## 4.11.4 Update Agreement

```http
PATCH /api/v1/supplier-product-agreements/{agreement_id}
```


## 4.11.5 Change Agreement Status

```http
POST /api/v1/supplier-product-agreements/{agreement_id}/status-transitions
```


# 4.12 Purchase-Order Endpoints

## 4.12.1 List Purchase Orders

```http
GET /api/v1/purchase-orders
```

Filters:

* `supplier_id`
* `distribution_centre_id`
* `purchase_order_status`
* `order_date_from`
* `order_date_to`
* `expected_delivery_from`
* `expected_delivery_to`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`

Default incremental order:

```text
updated_at ASC, purchase_order_id ASC
```


## 4.12.2 Retrieve Purchase Order

```http
GET /api/v1/purchase-orders/{purchase_order_id}
```

Optional parameter:

```text
include_lines=true
```


## 4.12.3 Create Purchase Order

```http
POST /api/v1/purchase-orders
```

Required header:

```http
Idempotency-Key
```

Example request:

```json
{
  "supplier_id": "uuid",
  "distribution_centre_id": "uuid",
  "order_date": "2026-08-15",
  "requested_delivery_date": "2026-08-20",
  "expected_delivery_date": "2026-08-20",
  "currency_code": "GBP",
  "lines": [
    {
      "line_number": 1,
      "product_id": "uuid",
      "supplier_product_agreement_id": "uuid",
      "ordered_quantity": "500.000",
      "unit_cost": "2.4500",
      "tax_rate": "0.200000"
    }
  ]
}
```

The purchase-order header and all lines must be created within one database transaction.

Successful response:

```http
201 Created
```


## 4.12.4 Update Draft Purchase Order

```http
PATCH /api/v1/purchase-orders/{purchase_order_id}
```

Only permitted while the order is in an amendable state.


## 4.12.5 Add Purchase-Order Line

```http
POST /api/v1/purchase-orders/{purchase_order_id}/lines
```

Only permitted before approval unless an approved amendment process is used.


## 4.12.6 Update Purchase-Order Line

```http
PATCH /api/v1/purchase-orders/{purchase_order_id}/lines/{line_id}
```


## 4.12.7 Approve Purchase Order

```http
POST /api/v1/purchase-orders/{purchase_order_id}/approval
```

Example request:

```json
{
  "approved_by": "procurement.manager@britmart.example",
  "expected_version_number": 2
}
```


## 4.12.8 Cancel Purchase Order

```http
POST /api/v1/purchase-orders/{purchase_order_id}/cancellation
```

Example request:

```json
{
  "cancellation_reason": "Supplier unable to fulfil order",
  "expected_version_number": 3
}
```


## 4.12.9 Retrieve Purchase-Order Status History

```http
GET /api/v1/purchase-orders/{purchase_order_id}/status-history
```


## 4.12.10 List Purchase-Order Lines for Fabric

```http
GET /api/v1/purchase-order-lines
```

This top-level endpoint allows Fabric to extract purchase-order lines independently.

Filters:

* `purchase_order_id`
* `product_id`
* `line_status`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


# 4.13 Shipment Endpoints

## 4.13.1 List Shipments

```http
GET /api/v1/shipments
```

Filters:

* `purchase_order_id`
* `supplier_id`
* `distribution_centre_id`
* `shipment_status`
* `shipment_type`
* `expected_delivery_from`
* `expected_delivery_to`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`

Example Fabric extraction:

```http
GET /api/v1/shipments?updated_since=2026-08-01T00:00:00Z&updated_before=2026-08-15T02:00:00Z&page_size=500
```


## 4.13.2 Retrieve Shipment

```http
GET /api/v1/shipments/{shipment_id}
```

Optional:

```text
include_lines=true
```


## 4.13.3 Create Shipment

```http
POST /api/v1/shipments
```

Required header:

```http
Idempotency-Key
```

Example request:

```json
{
  "shipment_number": "SHP-2026-000001",
  "purchase_order_id": "uuid",
  "shipment_type": "CHILLED",
  "carrier_name": "BritLogistics",
  "tracking_number": "BL-984001",
  "expected_delivery_at": "2026-08-20T08:00:00Z",
  "lines": [
    {
      "purchase_order_line_id": "uuid",
      "product_id": "uuid",
      "shipped_quantity": "450.000",
      "batch_number": "BAT-20260815-01",
      "expiry_date": "2026-08-29"
    }
  ]
}
```

The shipment and its lines must be created within one transaction.


## 4.13.4 Update Shipment

```http
PATCH /api/v1/shipments/{shipment_id}
```

Only permitted fields may be updated according to current shipment status.


## 4.13.5 Change Shipment Status

```http
POST /api/v1/shipments/{shipment_id}/status-transitions
```

Example request:

```json
{
  "new_status": "DISPATCHED",
  "event_timestamp": "2026-08-19T17:15:00Z",
  "status_location": "Supplier dispatch centre",
  "status_message": "Shipment departed supplier",
  "expected_version_number": 1
}
```


## 4.13.6 Retrieve Shipment Status History

```http
GET /api/v1/shipments/{shipment_id}/status-history
```


## 4.13.7 List Shipment Lines for Fabric

```http
GET /api/v1/shipment-lines
```

Filters:

* `shipment_id`
* `purchase_order_line_id`
* `product_id`
* `batch_number`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


# 4.14 Delivery Endpoints

## 4.14.1 List Delivery Attempts

```http
GET /api/v1/deliveries
```

Filters:

* `shipment_id`
* `distribution_centre_id`
* `delivery_status`
* `arrival_from`
* `arrival_to`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


## 4.14.2 Retrieve Delivery Attempt

```http
GET /api/v1/deliveries/{delivery_attempt_id}
```


## 4.14.3 Record Delivery Attempt

```http
POST /api/v1/shipments/{shipment_id}/deliveries
```

Required header:

```http
Idempotency-Key
```

Example request:

```json
{
  "attempt_number": 1,
  "arrival_at": "2026-08-20T07:50:00Z",
  "delivery_status": "ARRIVED",
  "temperature_celsius": "3.80",
  "seal_intact_flag": true,
  "delivery_reference": "DEL-2026-000001"
}
```


## 4.14.4 Update Delivery Attempt

```http
PATCH /api/v1/deliveries/{delivery_attempt_id}
```

Examples include:

* Start unloading
* Complete unloading
* Reject delivery
* Record departure


# 4.15 Supplier Performance Event Endpoints

## 4.15.1 List Performance Events

```http
GET /api/v1/supplier-performance-events
```

Filters:

* `supplier_id`
* `purchase_order_id`
* `shipment_id`
* `event_type`
* `event_severity`
* `resolution_status`
* `occurred_from`
* `occurred_to`
* `updated_since`
* `updated_before`
* `cursor`
* `page`
* `page_size`


## 4.15.2 Retrieve Performance Event

```http
GET /api/v1/supplier-performance-events/{event_id}
```


## 4.15.3 Create Performance Event

```http
POST /api/v1/supplier-performance-events
```


## 4.15.4 Resolve Performance Event

```http
POST /api/v1/supplier-performance-events/{event_id}/resolution
```


# 4.16 Incremental Extraction Rules

Incremental collection endpoints must support:

```text
updated_since
updated_before
cursor
page_size
```

The extraction window is:

```text
updated_at > updated_since
AND updated_at <= updated_before
```

Stable ordering is:

```text
updated_at ASC, primary_identifier ASC
```

Fabric must:

1. Set `updated_before` at the beginning of the extraction.
2. Keep the same boundaries for every page.
3. Follow `next_cursor` until `has_next` is false.
4. Record the maximum source timestamp received.
5. Update the watermark only after successful Bronze persistence.
6. Apply a configurable overlap during the next extraction.

Append-only history endpoints use `changed_at` instead of `updated_at`.


# 4.17 Sorting Rules

Clients may only sort by approved fields.

Unsupported sort fields return:

```http
422 Unprocessable Entity
```

All sort orders must include the primary identifier as the final tie-breaker.

Example:

```text
updated_at ASC, shipment_id ASC
```

This prevents non-deterministic ordering when several records have the same timestamp.


# 4.18 Standard Error Response

```json
{
  "error": {
    "code": "SUPPLIER_NOT_FOUND",
    "message": "The requested supplier does not exist.",
    "details": [],
    "retryable": false
  },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "response_timestamp": "2026-08-15T22:00:00Z"
  }
}
```

Validation-error example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request failed validation.",
    "details": [
      {
        "field": "ordered_quantity",
        "message": "Value must be greater than zero."
      }
    ],
    "retryable": false
  },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "response_timestamp": "2026-08-15T22:00:00Z"
  }
}
```

Internal exception details and database errors must not be exposed to clients.


# 4.19 HTTP Status Codes

| Status | Meaning                                 | Fabric treatment                       |
| -----: | --------------------------------------- | -------------------------------------- |
|  `200` | Successful retrieval or update          | Continue                               |
|  `201` | Resource created                        | Continue                               |
|  `204` | Successful operation with no body       | Continue                               |
|  `400` | Malformed business request              | Fail or quarantine                     |
|  `401` | Missing or invalid authentication       | Fail without repeated retry            |
|  `403` | Authenticated but not authorised        | Fail without repeated retry            |
|  `404` | Resource not found                      | Handle according to operation          |
|  `409` | Duplicate, version or business conflict | Investigate or apply idempotency logic |
|  `422` | Validation failure                      | Quarantine or correct request          |
|  `429` | Rate limit exceeded                     | Retry after instructed delay           |
|  `500` | Unexpected server error                 | Retry according to policy              |
|  `503` | Service or dependency unavailable       | Retry according to policy              |


# 4.20 Retry Headers

For `429` or temporary unavailability, the API may return:

```http
Retry-After: 30
```

Fabric should respect this value where technically supported.

Responses may also include:

```http
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
```


# 4.21 Idempotency Rules

The following operations require `Idempotency-Key`:

* Create supplier
* Create supplier-product agreement
* Create purchase order
* Create shipment
* Record delivery attempt
* Create supplier-performance event

If the same client repeats the same request with the same key, the API returns the original result.

If the same key is used with a different request body, return:

```http
409 Conflict
```


# 4.22 Optimistic Concurrency

Important update operations require:

```text
expected_version_number
```

If the stored version no longer matches, return:

```http
409 Conflict
```

Example error code:

```text
VERSION_CONFLICT
```

This prevents one user or process from silently overwriting another update.


# 4.23 Controlled Failure Simulation

Failure simulation is restricted to development and test environments.

Administrative endpoints should use a separate protected path:

```http
POST /api/v1/admin/failure-scenarios/{scenario_code}/activate
POST /api/v1/admin/failure-scenarios/{scenario_code}/deactivate
GET  /api/v1/admin/failure-scenarios
```

Supported scenarios may include:

* HTTP 401
* HTTP 429
* HTTP 500
* HTTP 503
* Delayed response
* Database unavailable
* Malformed response in an isolated test route
* Pagination inconsistency
* Schema-version change

These endpoints must require administrator authorisation and must not be exposed as normal operational functionality.


# 4.24 API Versioning and Schema Evolution

Version 1 uses:

```text
/api/v1
```

Backward-compatible version-one changes include:

* Adding an optional response field
* Adding an optional query parameter
* Adding a new endpoint
* Expanding documented enum values only through controlled review

Breaking changes require:

```text
/api/v2
```

Breaking changes include:

* Removing a field
* Renaming a field
* Changing a field to an incompatible type
* Changing identifier meaning
* Changing pagination behaviour incompatibly

Responses should expose:

```text
api_version
schema_version
```


# 4.25 API Contract Acceptance Criteria

The API contract is accepted when:

* All required business entities have endpoints.
* Collection endpoints support pagination.
* Fabric entities support incremental extraction.
* Stable sorting is defined.
* Authentication is required appropriately.
* Important create operations are idempotent.
* Updates support optimistic concurrency.
* Errors follow one structured format.
* Retryable and non-retryable failures are distinguishable.
* Failure simulation is protected.
* API and schema versioning are defined.
* External SQL warehouse receipts remain outside FastAPI ownership.
-

## 4.26 Deliverable Status

**Deliverable:** Phase 1.4 — API Endpoint Contract
**Status:** Approved design baseline
**Next deliverable:** Phase 1.5 — Fabric Incremental-Ingestion and Reconciliation Specification
