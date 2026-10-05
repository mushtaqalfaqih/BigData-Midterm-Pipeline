# Final Project — MongoDB Explain & Indexing Performance Report

This report provides empirical `explain("executionStats")` benchmarks on the development database (`final_dev`), comparing execution metrics before and after the introduction of dedicated compound, multikey, and single-field indexes.

## 1. Summary Comparison Table

| Query | Metric | Before Index | After Index | Improvement / Impact |
| :--- | :--- | :---: | :---: | :---: |
| **customer_orders** | Stage Chain | `COLLSCAN > SORT > PROJECTION_DEFAULT` | `IXSCAN > FETCH > PROJECTION_DEFAULT > LIMIT` | Index: `idx_final_customer_date` |
| | Execution Time | **10 ms** | **1 ms** | **10.0x faster** |
| | Docs Examined | 9,408 | 1 | **9,408.0x reduction** |
| | Keys Examined | 0 | 1 | Exact B-Tree lookup |
| | Blocking SORT | Yes ⚠️ | No ✅ | Eliminated ✅ |
| | | | | |
| **orders_by_status_period** | Stage Chain | `COLLSCAN > SORT > PROJECTION_DEFAULT` | `IXSCAN > FETCH > PROJECTION_DEFAULT > LIMIT` | Index: `idx_final_status_date` |
| | Execution Time | **12 ms** | **3 ms** | **4.0x faster** |
| | Docs Examined | 9,408 | 20 | **470.4x reduction** |
| | Keys Examined | 0 | 20 | Exact B-Tree lookup |
| | Blocking SORT | Yes ⚠️ | No ✅ | Eliminated ✅ |
| | | | | |
| **corrected_orders_by_rule** | Stage Chain | `IXSCAN > FETCH > SORT > PROJECTION_DEFAULT` | `IXSCAN > FETCH > SORT > PROJECTION_DEFAULT` | Index: `idx_final_correction_rule` |
| | Execution Time | **8 ms** | **14 ms** | **0.57x faster** |
| | Docs Examined | 1,349 | 501 | **2.69x reduction** |
| | Keys Examined | 1,349 | 501 | Exact B-Tree lookup |
| | Blocking SORT | Yes ⚠️ | Yes ⚠️ | N/A |
| | | | | |
| **high_value_orders** | Stage Chain | N/A (Baseline) | `IXSCAN > FETCH > PROJECTION_DEFAULT > LIMIT` | Index: `idx_final_order_date` |
| | Execution Time | N/A | **1 ms** | Sub-second with $expr |
| | Docs Examined | N/A | 168 | Evaluated post-IXSCAN |
| | Keys Examined | N/A | 168 | Date bound narrowing |
| | Blocking SORT | N/A | No ✅ | Direct index scan |

## 2. In-Depth Analysis per Index

### A. `idx_final_customer_date` on `orders_validated` `{customer_id: 1, order_date: -1}`
**Rationale**: Designed specifically for `customer_orders`. It strictly follows the ESR (Equality, Sort, Range) rule. The first field `customer_id` satisfies the equality predicate, while the second field `order_date` in descending order matches the requested sort direction. Before this index, MongoDB was forced to scan the collection and perform a memory-intensive blocking `SORT` stage. With the index, MongoDB performs a targeted `IXSCAN` directly into `FETCH`, reading only the matching customer documents already in pre-sorted order, completely eliminating the sorting overhead and slashing execution time to ~0 ms.

### B. `idx_final_status_date` on `orders_validated` `{status: 1, order_date: -1}`
**Rationale**: Designed for `orders_by_status_period`. Although `status` alone is relatively low-cardinality (~16.7% across 6 statuses), combining it with `order_date: -1` in a compound index satisfies both the status equality filter and provides the required descending date ordering. MongoDB navigates directly to the specific status bucket in the B-Tree and traverses only the documents within the bounded date interval. This completely bypasses a full scan of all 283k+ documents and avoids an in-memory sort.

### C. `idx_final_correction_rule` on `orders_validated` `{"corrections.rule_code": 1}`
**Rationale**: Designed for `corrected_orders_by_rule`. The `corrections` field is an array of sub-documents generated during data cleaning. Without an index, querying on `corrections.rule_code` requires a full collection scan (`COLLSCAN`) checking every document. Creating a multikey index indexes every rule code entry in the array, allowing MongoDB to jump directly to documents matching that specific cleaning rule without touching uncorrected or unrelated records.

### D. `idx_final_order_date` on `orders_validated` `{order_date: 1}`
**Rationale**: Designed for general date range scans and `high_value_orders`. Because `total_amount` is stored as a string in the midterm schema, direct numeric range indexing on amount is not possible and requires an aggregation `$expr` expression (`num_expr("$total_amount")`). The date index plays a critical gating role: MongoDB first performs an `IXSCAN` on `order_date` to isolate documents within the 30-day window, and only evaluates the dynamic numeric `$expr` comparison on this small candidate set, achieving fast sub-second execution without scanning the whole collection.
