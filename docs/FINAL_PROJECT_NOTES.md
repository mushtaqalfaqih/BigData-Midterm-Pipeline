# docs/FINAL_PROJECT_NOTES.md
# Final Project — Architecture & Design Decisions

## 1. Incremental Materialized View Design

### Why there is no true watermark
The midterm pipeline uses an **idempotent upsert** (`UpdateOne({order_id}, {$set: doc}, upsert=True)`).
Each re-run *overwrites* `metadata.processed_at` on already-existing documents, so this field
cannot be used as a monotonic watermark — it reflects the *last* run that touched the document,
not when it was first inserted.

### Chosen mechanism: `run_id` + per-run document counts via `mv_state`
The `mv_state` collection stores one entry per (materialized-view, run_id) pair:

```json
{
  "mv": "daily_sales_summary",
  "run_id": "a49919a5c7a847789615ec3194f4b9d7",
  "doc_count": 28329268,
  "refreshed_at": "2026-10-03T20:00:00Z"
}
```

A refresh job:
1. Queries `orders_validated` grouped by `run_id` to get current counts per run
   (uses the indexed `metadata.run_id` field — no full scan).
2. Compares against the stored counts in `mv_state`.
3. For **new or changed** run_ids (count differs from stored value), determines the
   affected **partitions** — days for `daily_sales_summary`, SKUs for `top_products_summary`.
4. **Replaces only those partitions** via `replace_one({partition_key}, new_doc, upsert=True)`.
5. Never uses `$inc` — always full partition replacement to stay idempotent.

### Rule: never use `$inc`
Incremental `$inc` operations on pre-aggregated totals are not idempotent; re-running a job
would double-count. All updates replace the entire partition document.

---

## 2. top_products_summary — Items Explosion Strategy

`items_json` is stored as a **JSON string** in `orders_validated`, not as a MongoDB array.
MongoDB's `$unwind` cannot operate on a string field directly.

**Tentative design (to be finalised in Step 5):**
- A Python job reads `orders_validated` in batches (using `metadata.run_id` index).
- For each document, `parse_items(items_json)` (from `src/final/common.py`) explodes the string
  into a list of `{sku, name, qty, unit_price, total}` dicts.
- The exploded items are written to `order_items_flat` (one MongoDB document per line-item).
- `top_products_summary` is then computed via a standard `$group` aggregation on `order_items_flat`.

This avoids the need for `$function` / `$accumulator` (which require JS) and is portable across
all MongoDB versions ≥ 4.4.

---

## 3. Validated Count vs. Valid + Corrected Count

The **orders_validated** collection contains fewer documents than the sum of
`valid_count + corrected_count` reported by the pipeline metrics.

**Root cause:** The source CSV contains duplicate `order_id` values.
The idempotent upsert (`unique index on order_id`) collapses duplicates — only the *last*
version of each `order_id` survives. Every re-run or duplicate in the source reduces the
final count below the raw classified count.

This is expected and correct behaviour. The validated collection is a deduplicated,
business-keyed view of the data.

---

## 4. API Routes (Final Assignment)

The REST API uses **FastAPI + Uvicorn** and exposes the following routes
(exact names from the assignment spec):

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/ingest` | Trigger pipeline — calls `run_elt_pipeline(reset=False)` |
| GET | `/analytics/daily-sales` | Query `daily_sales_summary` MV |
| GET | `/analytics/top-products` | Query `top_products_summary` MV |
| GET | `/analytics/orders` | Filtered find() on `orders_validated` |
| POST | `/views/refresh` | Trigger MV refresh job |
| GET | `/health` | Liveness check |

**Key decision:** `/ingest` uses `reset=False` so it never drops the production collections.
The CLI (`src/main.py`) retains `reset=True` as default (original midterm behaviour).

---

## 5. Safety Rules (enforced in all final code)

- **Never write to / drop / create indexes on `midterm_data_pipeline`** from final modules —
  only `orders_validated` reads (bounded by `$sample`/`limit`/indexed-field queries).
- All development and testing targets the `final_dev` database via `MONGO_DATABASE=final_dev`.
- No hardcoded file names, record counts, dates, or result values in any new module.
- All monetary amounts are stored as **strings** in `orders_validated`; always use
  `num_expr()` from `common.py` inside aggregation pipelines.
- `order_date` is an ISO 8601 **string**; always use `day_expr()` to extract the date part.
