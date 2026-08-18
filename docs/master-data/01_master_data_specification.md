# BritMart Shared Master-Data Specification

## 1. Purpose

This document defines the shared master data required across the complete BritMart retail data platform.

The objective is to ensure that FastAPI, SQL, SharePoint files, AWS S3, Fabric Eventstream and Microsoft Fabric use the same logically consistent business identifiers and reference data.

Master data must be generated before transactional data such as purchase orders, shipments, inventory movements, store sales and online orders.


## 2. Master-Data Principles

The BritMart master-data design must follow these principles:

1. Every master entity has one authoritative owner.
2. Every record has a stable technical identifier.
3. Every record has a readable business code.
4. Identifiers remain consistent across all source systems.
5. Synthetic generation must be deterministic and repeatable.
6. Relationships must satisfy referential integrity.
7. Important reference changes must retain history.
8. Generated data must reflect plausible UK retail operations.
9. No real customer or supplier personal data will be used.
10. Data must support both operational processing and analytics.


## 3. Authoritative Ownership

| Master entity | Authoritative owner | Consumers |
|---|---|---|
| UK region | SQL operational system | All sources and Fabric |
| Distribution centre | SQL operational system | FastAPI, SQL, S3 and Fabric |
| Store | SQL operational system | SharePoint POS, SQL, S3 and Fabric |
| Category | SQL product master | All sources and Fabric |
| Subcategory | SQL product master | All sources and Fabric |
| Product | SQL product master | FastAPI, SQL, SharePoint, S3 and Fabric |
| Supplier | FastAPI | FastAPI, SQL receipts and Fabric |
| Supplier-product agreement | FastAPI | FastAPI, procurement and Fabric |
| Calendar | Shared generator/Fabric | All generated events and Fabric |
| Seasonal event | Shared generator | Sales, promotions, inventory and Fabric |
| Promotion | Pricing simulation | POS, online commerce and Fabric |

A consuming system may retain a synchronised reference copy, but it must not silently change authoritative attributes.


## 4. Dataset Time Period

The project will use:

| Period | Date range | Purpose |
|---|---|---|
| Seed period | 1 July 2025–31 July 2025 | Opening inventory and operational history |
| Main reporting period | 1 August 2025–31 July 2026 | Twelve complete reporting months |
| Future test period | 1 August 2026 onwards | Incremental loading and operational simulation |

All generated business events must fall within an explicitly configured period.


## 5. Deterministic Generation

The generator will use a fixed random seed:

```text
BRITMART_MASTER_SEED = 20260816
````

The same seed and configuration must reproduce the same master records.

Technical UUID identifiers should be generated deterministically using UUID version 5 from:

```text
BritMart namespace + entity type + business code
```

Example conceptual input:

```text
britmart:product:PRD-000001
```

This provides:

* Stable identifiers
* Repeatable datasets
* Safe regeneration
* Consistency across source systems
* Easier automated testing

Random UUID version 4 values must not be regenerated independently by different source generators.


## 6. Identifier Standards

| Entity              | Business-code format    | Example                    |
| ------------------- | ----------------------- | -------------------------- |
| Region              | `REG-###`               | `REG-001`                  |
| Distribution centre | `DC-###`                | `DC-001`                   |
| Store               | `STR-####`              | `STR-0001`                 |
| Category            | `CAT-##`                | `CAT-01`                   |
| Subcategory         | `SUB-###`               | `SUB-001`                  |
| Product             | `PRD-######`            | `PRD-000001`               |
| SKU                 | `BM-########`           | `BM-00000001`              |
| Supplier            | `SUP-####`              | `SUP-0001`                 |
| Supplier agreement  | `AGR-######`            | `AGR-000001`               |
| Purchase order      | `PO-YYYY-######`        | `PO-2026-000001`           |
| Shipment            | `SHP-YYYY-######`       | `SHP-2026-000001`          |
| Delivery            | `DEL-YYYY-######`       | `DEL-2026-000001`          |
| Goods receipt       | `GRN-YYYY-######`       | `GRN-2026-000001`          |
| Transfer            | `TRF-YYYY-######`       | `TRF-2026-000001`          |
| POS receipt         | `POS-STORE-DATE-######` | `POS-0001-20260815-000001` |
| Online order        | `ONL-YYYY-########`     | `ONL-2026-00000001`        |
| Promotion           | `PROMO-YYYY-####`       | `PROMO-2026-0001`          |

Business codes must be unique within their entity.

Technical UUIDs and readable business codes must both be retained.


# 7. UK Region Master

BritMart will operate across 12 reporting regions.

| Region code | Region name              | Number of stores |
| ----------- | ------------------------ | ---------------: |
| `REG-001`   | London                   |               20 |
| `REG-002`   | South East England       |               15 |
| `REG-003`   | North West England       |               13 |
| `REG-004`   | West Midlands            |               11 |
| `REG-005`   | Yorkshire and the Humber |               11 |
| `REG-006`   | East of England          |               10 |
| `REG-007`   | South West England       |               10 |
| `REG-008`   | East Midlands            |                9 |
| `REG-009`   | North East England       |                6 |
| `REG-010`   | Wales                    |                6 |
| `REG-011`   | Scotland                 |                7 |
| `REG-012`   | Northern Ireland         |                2 |
|             | **Total**                |          **120** |

Required region fields:

* `region_id`
* `region_code`
* `region_name`
* `country_name`
* `active_flag`
* `created_at`
* `updated_at`

The regional allocation is a BritMart portfolio assumption and not a representation of a real retailer’s store estate.


# 8. Distribution-Centre Master

BritMart will operate six fictional regional distribution centres in plausible UK logistics areas.

| Code     | Operating area | Fictional location | Primary coverage                        |
| -------- | -------------- | ------------------ | --------------------------------------- |
| `DC-001` | North West     | Warrington area    | North West and Northern Ireland         |
| `DC-002` | Midlands       | Rugby area         | West Midlands and East Midlands         |
| `DC-003` | Yorkshire      | Doncaster area     | Yorkshire and North East                |
| `DC-004` | South East     | Thurrock area      | London and South East                   |
| `DC-005` | South West     | Bristol area       | South West and Wales                    |
| `DC-006` | Scotland       | Livingston area    | Scotland and overflow northern coverage |

These are fictional BritMart facilities. Only broad location areas will be used; no real business address is required.

Required fields:

* `distribution_centre_id`
* `distribution_centre_code`
* `distribution_centre_name`
* `region_id`
* `location_area`
* `postcode_area`
* `latitude`
* `longitude`
* `supports_ambient`
* `supports_chilled`
* `supports_frozen`
* `daily_receiving_capacity_cases`
* `daily_dispatch_capacity_cases`
* `active_flag`
* `opened_date`
* `created_at`
* `updated_at`

Rules:

* All six centres support ambient products.
* At least five support chilled products.
* At least four support frozen products.
* Capacity must be positive.
* Every centre must cover at least one store region.
* Every store must have one primary distribution centre.
* Coordinates should be approximate area coordinates, not private addresses.


# 9. Store Master

BritMart will have 120 stores.

## 9.1 Store Formats

| Format      |   Count | Relative sales weighting | Typical characteristics               |
| ----------- | ------: | -----------------------: | ------------------------------------- |
| Superstore  |      30 |                      2.5 | Large product range and higher volume |
| Supermarket |      60 |                      1.5 | Standard full grocery offering        |
| Convenience |      30 |                      0.6 | Smaller range and lower basket size   |
| **Total**   | **120** |                          |                                       |

Required fields:

* `store_id`
* `store_code`
* `store_name`
* `region_id`
* `primary_distribution_centre_id`
* `store_format`
* `city`
* `postcode_area`
* `latitude`
* `longitude`
* `floor_area_square_metres`
* `opening_date`
* `online_collection_flag`
* `home_delivery_support_flag`
* `active_flag`
* `created_at`
* `updated_at`

Rules:

* Store codes must be unique.
* Store names must be fictional.
* Every store belongs to one region.
* Every store has one primary distribution centre.
* Store format controls product assortment and sales weighting.
* Floor area must fall within the configured range for the store format.
* Not every convenience store supports home delivery.
* Larger stores are more likely to support online collection.
* No exact real-store address will be used.

Suggested floor-area ranges:

| Format      |  Minimum |  Maximum |
| ----------- | -------: | -------: |
| Superstore  | 4,000 m² | 9,000 m² |
| Supermarket | 1,500 m² | 4,500 m² |
| Convenience |   150 m² |   600 m² |


# 10. Product Hierarchy

BritMart will have five categories and forty subcategories.

## 10.1 Fresh Food

Category code:

```text
CAT-01
```

Subcategories:

1. Fruit
2. Vegetables
3. Meat
4. Poultry
5. Fish
6. Bakery
7. Dairy
8. Prepared Meals

## 10.2 Grocery

Category code:

```text
CAT-02
```

Subcategories:

1. Tinned Food
2. Pasta and Rice
3. Breakfast
4. Cooking Ingredients
5. Snacks
6. Confectionery
7. Condiments
8. World Foods

## 10.3 Beverages

Category code:

```text
CAT-03
```

Subcategories:

1. Water
2. Soft Drinks
3. Juice
4. Tea
5. Coffee
6. Energy Drinks
7. Beer and Cider
8. Wine

## 10.4 Frozen and Chilled

Category code:

```text
CAT-04
```

Subcategories:

1. Frozen Meals
2. Frozen Vegetables
3. Frozen Meat
4. Ice Cream
5. Pizza
6. Chilled Desserts
7. Yoghurts
8. Chilled Drinks

## 10.5 Household and Personal Care

Category code:

```text
CAT-05
```

Subcategories:

1. Cleaning
2. Laundry
3. Paper Products
4. Toiletries
5. Hair Care
6. Oral Care
7. Baby Care
8. Pet Care

Each category must have exactly eight active subcategories in the initial dataset.


# 11. Product Volume Distribution

BritMart will have 2,000 active products.

| Category                    | Product count |
| --------------------------- | ------------: |
| Fresh Food                  |           480 |
| Grocery                     |           520 |
| Beverages                   |           300 |
| Frozen and Chilled          |           360 |
| Household and Personal Care |           340 |
| **Total**                   |     **2,000** |

Every subcategory must contain at least 25 products.

Product counts may vary between subcategories to reflect different assortment sizes.


# 12. Product Master Attributes

Required fields:

* `product_id`
* `product_code`
* `sku`
* `product_name`
* `category_id`
* `subcategory_id`
* `brand_type`
* `brand_name`
* `unit_of_measure`
* `package_size`
* `case_pack_quantity`
* `storage_type`
* `shelf_life_days`
* `unit_cost`
* `standard_retail_price`
* `vat_rate`
* `reorder_level`
* `safety_stock_quantity`
* `country_of_origin`
* `perishable_flag`
* `age_restricted_flag`
* `active_flag`
* `effective_from`
* `effective_to`
* `created_at`
* `updated_at`

Brand types:

```text
BRITMART_OWN_BRAND
NATIONAL_BRAND
REGIONAL_BRAND
```

Storage types:

```text
AMBIENT
CHILLED
FROZEN
```

Units of measure may include:

```text
EACH
PACK
KILOGRAM
GRAM
LITRE
MILLILITRE
CASE
```


# 13. Product Business Rules

1. Product codes and SKUs must be unique.
2. Every product belongs to one subcategory.
3. Every subcategory belongs to one category.
4. Standard retail price must be greater than or equal to unit cost.
5. Case-pack quantity must be greater than zero.
6. Reorder level cannot be negative.
7. Safety stock cannot be negative.
8. Perishable products require a shelf-life value.
9. Frozen products must use frozen storage.
10. Chilled products must use chilled storage.
11. Alcohol products must be age restricted.
12. VAT rates must come from a controlled configuration.
13. Historical VAT treatment must not be hard-coded permanently into product-generation logic.
14. Inactive products cannot be included in new purchase orders or new sales.
15. Product names must be synthetic and must not intentionally copy a real retailer’s proprietary product range.


# 14. Product Popularity Tiers

Products will be assigned to demand tiers.

| Tier | Approximate product share |                    Relative demand |
| ---- | ------------------------: | ---------------------------------: |
| A    |                       20% |               High-volume products |
| B    |                       30% |                 Medium-high volume |
| C    |                       35% |                    Standard volume |
| D    |                       15% | Slow-moving or specialist products |

Sales and replenishment must not be uniformly distributed across all products.

Tier A products should account for a disproportionately high share of sales.


# 15. Supplier Master

BritMart will have 50 suppliers.

## 15.1 Country Distribution

| Supplier location   |  Count |
| ------------------- | -----: |
| United Kingdom      |     34 |
| European Union      |     10 |
| Other international |      6 |
| **Total**           | **50** |

The international mix supports realistic differences in lead time, currency and supply-chain risk.

## 15.2 Supplier Types

Supplier types should include:

* Fresh-produce supplier
* Meat and poultry supplier
* Dairy supplier
* Bakery supplier
* Grocery manufacturer
* Beverage manufacturer
* Frozen-food supplier
* Household-goods manufacturer
* Personal-care supplier
* Importer or distributor
* Regional specialist supplier

Required supplier fields:

* `supplier_id`
* `supplier_code`
* `supplier_name`
* `legal_name`
* `supplier_type`
* `country_code`
* `default_currency_code`
* `standard_lead_time_days`
* `minimum_order_value`
* `supports_ambient`
* `supports_chilled`
* `supports_frozen`
* `risk_rating`
* `supplier_status`
* `active_flag`
* `effective_from`
* `effective_to`
* `created_at`
* `updated_at`

Supplier names must be fictional.


# 16. Supplier Lead-Time Rules

Recommended lead-time ranges:

| Supplier type                | Lead-time range |
| ---------------------------- | --------------: |
| UK fresh supplier            |        1–4 days |
| UK ambient supplier          |        2–7 days |
| UK manufacturer              |       3–10 days |
| European supplier            |       5–15 days |
| Other international supplier |      14–45 days |

International lead times may include greater variation and disruption risk.

Lead time must influence:

* Purchase-order date
* Requested delivery date
* Shipment dispatch date
* Expected arrival date
* Safety-stock requirements
* Late-delivery probability


# 17. Supplier-Product Agreements

Every product must have at least one active supplier agreement.

Recommended distribution:

| Supplier coverage | Product share | Approximate products |
| ----------------- | ------------: | -------------------: |
| One supplier      |           70% |                1,400 |
| Two suppliers     |           25% |                  500 |
| Three suppliers   |            5% |                  100 |

This produces approximately:

```text
2,700 supplier-product agreements
```

Rules:

1. Every active product has at least one active agreement.
2. Every product has exactly one primary supplier at a time.
3. Alternative suppliers may have different costs and lead times.
4. Supplier storage capability must match product storage requirements.
5. Agreement currency normally follows supplier currency.
6. Minimum order quantity must be positive.
7. Order multiple must be positive.
8. Agreement dates must be valid.
9. Agreement costs must remain below normal retail prices.
10. Suspended or inactive suppliers cannot have newly used active agreements.
11. Agreement history must be retained.

Required agreement fields:

* `supplier_product_agreement_id`
* `agreement_code`
* `supplier_id`
* `product_id`
* `supplier_product_code`
* `agreed_unit_cost`
* `currency_code`
* `minimum_order_quantity`
* `order_multiple`
* `lead_time_days`
* `primary_supplier_flag`
* `agreement_status`
* `effective_from`
* `effective_to`
* `created_at`
* `updated_at`


# 18. Calendar Master

The calendar must cover at least:

```text
1 July 2025–31 December 2026
```

This includes the seed period, reporting period and future incremental testing.

Required calendar fields:

* `calendar_date`
* `date_key`
* `day_of_week_number`
* `day_name`
* `day_of_month`
* `week_of_year`
* `month_number`
* `month_name`
* `calendar_quarter`
* `calendar_year`
* `financial_period`
* `financial_quarter`
* `financial_year`
* `weekend_flag`
* `uk_bank_holiday_flag`
* `bank_holiday_name`
* `retail_event_flag`
* `retail_event_name`
* `season`
* `created_at`
* `updated_at`

The project must explicitly document the selected BritMart financial-calendar convention.


# 19. Seasonal and Retail Events

The generator must support:

* Summer demand
* Back-to-school period
* Halloween
* Black Friday
* Christmas
* New Year
* Valentine’s Day
* Mother’s Day
* Easter
* UK bank-holiday weekends
* Warm-weather events
* Winter-demand periods

Event effects must target relevant categories rather than increasing all product demand equally.

Examples:

| Event           | Most affected products                                 |
| --------------- | ------------------------------------------------------ |
| Summer          | Water, soft drinks, ice cream and barbecue products    |
| Back to school  | Snacks, drinks, toiletries and household products      |
| Halloween       | Confectionery, snacks and soft drinks                  |
| Black Friday    | Household and selected non-food products               |
| Christmas       | Meat, beverages, confectionery, bakery and frozen food |
| January         | Health-oriented products and household cleaning        |
| Valentine’s Day | Confectionery, beverages and prepared meals            |
| Easter          | Confectionery, bakery and family meals                 |

Retail-event factors must be configuration-driven.


# 20. Store Assortment Rules

Not every store carries every product.

Recommended active assortment:

| Store format | Approximate active products |
| ------------ | --------------------------: |
| Superstore   |                 1,700–2,000 |
| Supermarket  |                 1,200–1,700 |
| Convenience  |                     450–800 |

Rules:

1. High-demand products should appear in most stores.
2. Specialist and slow-moving products should have narrower distribution.
3. Frozen assortment depends on store capacity.
4. Alcohol assortment must respect store configuration.
5. New or inactive products must respect effective dates.
6. Store assortment changes must be reproducible.

A separate `store_product_assortment` bridge will eventually connect stores and products.


# 21. Shared Master-Data Output Files

Phase 2 generation will eventually produce:

```text
regions.csv
distribution_centres.csv
stores.csv
categories.csv
subcategories.csv
products.csv
suppliers.csv
supplier_product_agreements.csv
calendar.csv
seasonal_events.csv
store_product_assortment.csv
```

These files are controlled generation outputs, not manually edited operational sources.

They will seed or support the relevant simulated systems.


# 22. Validation Rules

The generator must validate:

* Expected row counts
* Unique technical identifiers
* Unique business codes
* Unique SKUs
* Valid parent-child relationships
* Valid category and subcategory mappings
* Valid store-region mappings
* Valid store-distribution-centre mappings
* Valid supplier-product agreements
* Exactly one primary supplier per product
* Positive costs and prices
* Retail price not below normal cost
* Valid effective dates
* Valid storage compatibility
* Required shelf life for perishable products
* Complete calendar dates
* No unintended real personal data

Generation must fail if critical master-data validation fails.


# 23. Master-Data Reconciliation

Required control totals:

| Entity                      |      Expected count |
| --------------------------- | ------------------: |
| Regions                     |                  12 |
| Distribution centres        |                   6 |
| Stores                      |                 120 |
| Categories                  |                   5 |
| Subcategories               |                  40 |
| Products                    |               2,000 |
| Suppliers                   |                  50 |
| Supplier-product agreements | Approximately 2,700 |

Required relationship checks:

```text
Every store → one valid region
Every store → one valid primary distribution centre
Every subcategory → one valid category
Every product → one valid subcategory
Every active product → at least one active supplier agreement
Every active product → exactly one primary supplier
Every agreement → one valid supplier and one valid product
```


# 24. Change and History Strategy

Master data must support changes such as:

* Supplier suspension
* Product deactivation
* Store closure
* New product introduction
* Agreement cost change
* Supplier change
* Distribution-centre reassignment
* Store assortment change

The source systems retain operational history where required.

Fabric Silver will apply:

* Type 1 treatment for corrections that do not require history
* Type 2 treatment for analytically important changes
* Effective dates and current-record indicators
* Unknown-member handling for unresolved references

The specific Type 1 and Type 2 treatment will be documented during Silver design.


# 25. Filesystem and Repository Structure

Recommended Phase 2 structure:

```text
britmart-supplier-api/
├── docs/
│   ├── design/
│   └── master-data/
├── data-generators/
│   ├── config/
│   ├── src/
│   ├── tests/
│   └── output/
└── data-contracts/
```

Generated output should not be placed inside `.venv`.

Large generated datasets may be excluded from Git and regenerated through documented commands.

Small sample datasets may be retained for demonstrations and automated tests.


# 26. Phase 2 Build Order

Master data will be created in this order:

```text
Regions
→ Distribution centres
→ Stores
→ Categories
→ Subcategories
→ Products
→ Suppliers
→ Supplier-product agreements
→ Calendar
→ Seasonal events
→ Store-product assortment
```

This order ensures every child record can reference an existing parent.


# 27. Acceptance Criteria

The master-data specification is approved when:

* Entity counts are agreed.
* UK regional distribution is defined.
* Distribution-centre coverage is defined.
* Store formats and counts are defined.
* Five categories and forty subcategories are defined.
* Product counts and attributes are defined.
* Supplier distribution and lead-time rules are defined.
* Supplier-product coverage is defined.
* Stable identifier generation is defined.
* Calendar and seasonal-event rules are defined.
* Output files are identified.
* Validation and reconciliation controls are documented.
* Data can be regenerated deterministically.


## 28. Deliverable Status

**Deliverable:** Phase 2.1 — Shared Master-Data Specification
**Status:** Approved design baseline
**Next deliverable:** Phase 2.2 — Shared Business-Key Registry and Data Contracts


After pasting, confirm that the last line says:

```text
Next deliverable: Phase 2.2 — Shared Business-Key Registry and Data Contracts
````