# BritMart Supplier System Entity and Relationship Model

## 2.1 Purpose

This document defines the entities, relationships, ownership and cardinality required by the BritMart Supplier and Procurement API.

The model separates:

- Operational entities owned by FastAPI
- Reference entities mastered in the SQL operational system
- Warehouse-receipt entities owned outside FastAPI
- Analytical reconciliation performed in Microsoft Fabric
- Technical entities required for security, reliability and observability

---

## 2.2 System Ownership Boundaries

| Entity group | Authoritative system |
|---|---|
| Suppliers | FastAPI |
| Supplier-product agreements | FastAPI |
| Purchase orders | FastAPI |
| Supplier shipments | FastAPI |
| Deliveries and delivery events | FastAPI |
| Product master | SQL operational system |
| Distribution centres | SQL operational system |
| Goods receipts | SQL warehouse system |
| Warehouse inventory | SQL warehouse system |
| Cross-system reconciliation | Microsoft Fabric |
| Supplier-performance analytics | Microsoft Fabric |

FastAPI may retain synchronised reference copies of products and distribution centres for operational validation, but it is not their authoritative owner.

---

## 2.3 Core Operational Entities

### 2.3.1 Supplier

Represents an organisation approved or being assessed to supply products to BritMart.

Important attributes include:

- `supplier_id`
- `supplier_code`
- `supplier_name`
- `legal_name`
- `supplier_status`
- `country_code`
- `default_currency_code`
- `standard_lead_time_days`
- `supports_ambient`
- `supports_chilled`
- `supports_frozen`
- `active_flag`
- `created_at`
- `updated_at`

One supplier can have:

- Many supplier-product agreements
- Many purchase orders
- Many shipments
- Many status-history records
- Many supplier-performance events

---

### 2.3.2 Supplier Status History

Records every controlled change to a supplier’s operational status.

Important attributes include:

- `supplier_status_history_id`
- `supplier_id`
- `previous_status`
- `new_status`
- `change_reason`
- `changed_by`
- `changed_at`

Relationship:

```text
Supplier 1 → many Supplier Status History records