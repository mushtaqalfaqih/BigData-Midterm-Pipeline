"""
views.py — Materialized View Management and Incremental Refresh for Final Project.

Implements:
  1. Materialized Views:
     - daily_sales_summary: Daily aggregated revenue, order count, and AOV.
     - top_products_summary: Product rankings by revenue, quantity, and order count.
     - order_items_flat: Exploded line items table enabling high-speed indexed analytics.
  2. Incremental Partition Refresh:
     - Tracks ingestion runs using mv_state collection.
     - Detects newly added or modified runs without needing a global monotonic watermark.
     - Recomputes ONLY the affected daily partitions and touched product SKUs.
     - Performs idempotent upsert (replace_one with upsert=True) on affected partitions.
     - Supports full refresh on-demand (full=True).
"""

from __future__ import annotations

import time
from typing import Any
from pymongo import ReplaceOne, UpdateOne
from pymongo.database import Database

from src.final.common import (
    COL_DAILY_SALES,
    COL_MV_STATE,
    COL_ORDER_ITEMS_FLAT,
    COL_TOP_PRODUCTS,
    COL_VALIDATED,
    day_expr,
    get_db,
    num_expr,
    parse_items,
    utc_now_iso,
)


def ensure_mv_indexes(db: Database) -> None:
    """Ensure supporting indexes exist on materialized view collections."""
    # order_items_flat indexes
    db[COL_ORDER_ITEMS_FLAT].create_index([("order_id", 1)], background=True)
    db[COL_ORDER_ITEMS_FLAT].create_index(
        [("sku", 1), ("order_date", -1)], background=True
    )
    db[COL_ORDER_ITEMS_FLAT].create_index([("run_id", 1)], background=True)

    # daily_sales_summary index
    db[COL_DAILY_SALES].create_index([("date", 1)], unique=True, background=True)

    # top_products_summary index
    db[COL_TOP_PRODUCTS].create_index([("sku", 1)], unique=True, background=True)
    db[COL_TOP_PRODUCTS].create_index([("total_revenue", -1)], background=True)


def _flatten_order_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Explode items_json of a single validated order into flat item documents."""
    order_id = str(doc.get("order_id", ""))
    order_date = str(doc.get("order_date", ""))
    status = str(doc.get("status", ""))
    customer_id = str(doc.get("customer_id", ""))
    city = str(doc.get("city", "") or "")
    run_id = str(doc.get("metadata", {}).get("run_id", "") or "")

    raw_items = doc.get("items_json")
    parsed = parse_items(raw_items)

    flat_records = []
    for item in parsed:
        sku = item.get("sku")
        if not sku:
            continue
        flat_records.append(
            {
                "order_id": order_id,
                "order_date": order_date,
                "status": status,
                "customer_id": customer_id,
                "city": city,
                "sku": sku,
                "name": item.get("name") or sku,
                "qty": float(item.get("qty", 1.0)),
                "unit_price": float(item.get("unit_price", 0.0)),
                "total": float(item.get("total", 0.0)),
                "run_id": run_id,
            }
        )
    return flat_records


def refresh_order_items_flat(
    db: Database,
    target_order_ids: list[str] | None = None,
    full: bool = False,
) -> int:
    """
    Synchronize order_items_flat from orders_validated.

    Args:
        db: MongoDB database instance.
        target_order_ids: Specific order IDs to synchronize (for incremental mode).
        full: If True, completely rebuilds order_items_flat.

    Returns:
        int: Number of flattened item records written.
    """
    flat_col = db[COL_ORDER_ITEMS_FLAT]
    val_col = db[COL_VALIDATED]

    if full or target_order_ids is None:
        flat_col.delete_many({})
        cursor = val_col.find(
            {"items_json": {"$exists": True, "$ne": None, "$ne": ""}},
            projection={
                "order_id": 1,
                "order_date": 1,
                "status": 1,
                "customer_id": 1,
                "city": 1,
                "items_json": 1,
                "metadata.run_id": 1,
            },
        )
    else:
        if not target_order_ids:
            return 0
        flat_col.delete_many({"order_id": {"$in": target_order_ids}})
        cursor = val_col.find(
            {"order_id": {"$in": target_order_ids}},
            projection={
                "order_id": 1,
                "order_date": 1,
                "status": 1,
                "customer_id": 1,
                "city": 1,
                "items_json": 1,
                "metadata.run_id": 1,
            },
        )

    batch: list[dict[str, Any]] = []
    total_written = 0

    for doc in cursor:
        items = _flatten_order_items(doc)
        batch.extend(items)
        if len(batch) >= 2000:
            flat_col.insert_many(batch, ordered=False)
            total_written += len(batch)
            batch = []

    if batch:
        flat_col.insert_many(batch, ordered=False)
        total_written += len(batch)

    return total_written


def refresh_daily_sales_summary(
    db: Database,
    target_days: list[str] | None = None,
    full: bool = False,
) -> int:
    """
    Recompute daily sales aggregates for specified days or all days.

    Args:
        db: MongoDB database instance.
        target_days: List of YYYY-MM-DD date strings to recompute.
        full: If True, rebuilds all days.

    Returns:
        int: Count of daily summary documents updated.
    """
    val_col = db[COL_VALIDATED]
    daily_col = db[COL_DAILY_SALES]
    now_iso = utc_now_iso()

    match_filter: dict[str, Any] = {
        "order_date": {"$exists": True, "$ne": None, "$ne": ""}
    }

    if not full and target_days is not None:
        if not target_days:
            return 0
        # Build regex or prefix match for target days
        day_regex = "^(" + "|".join(target_days) + ")"
        match_filter["order_date"]["$regex"] = day_regex

    pipeline = [
        {"$match": match_filter},
        {
            "$group": {
                "_id": day_expr("$order_date"),
                "total_sales": {"$sum": num_expr("$total_amount")},
                "order_count": {"$sum": 1},
                "avg_order_value": {"$avg": num_expr("$total_amount")},
                "total_delivery_cost": {"$sum": num_expr("$delivery_cost")},
                "status_breakdown": {
                    "$push": "$status"
                },
            }
        },
    ]

    aggregates = list(val_col.aggregate(pipeline))
    if full:
        daily_col.delete_many({})

    operations = []
    for agg in aggregates:
        day_str = agg["_id"]
        if not day_str or len(day_str) < 10:
            continue

        # Count status distribution in memory
        statuses = agg.get("status_breakdown", [])
        status_counts: dict[str, int] = {}
        for s in statuses:
            if s:
                status_counts[s] = status_counts.get(s, 0) + 1

        total_sales = round(float(agg.get("total_sales", 0.0)), 2)
        order_count = int(agg.get("order_count", 0))
        avg_aov = round(float(agg.get("avg_order_value", 0.0)), 2)
        total_delivery = round(float(agg.get("total_delivery_cost", 0.0)), 2)

        doc = {
            "date": day_str,
            "total_sales": total_sales,
            "order_count": order_count,
            "avg_order_value": avg_aov,
            "total_delivery_cost": total_delivery,
            "status_distribution": status_counts,
            "last_refreshed_at": now_iso,
        }

        operations.append(
            ReplaceOne({"date": day_str}, doc, upsert=True)
        )

    if operations:
        daily_col.bulk_write(operations, ordered=False)

    return len(operations)


def refresh_top_products_summary(
    db: Database,
    target_skus: list[str] | None = None,
    full: bool = False,
) -> int:
    """
    Recompute product-level summaries for specified SKUs or all SKUs.

    Args:
        db: MongoDB database instance.
        target_skus: List of SKUs to recompute.
        full: If True, rebuilds all products.

    Returns:
        int: Count of product summary documents updated.
    """
    flat_col = db[COL_ORDER_ITEMS_FLAT]
    prod_col = db[COL_TOP_PRODUCTS]
    now_iso = utc_now_iso()

    match_filter: dict[str, Any] = {
        "sku": {"$exists": True, "$ne": None, "$ne": ""}
    }

    if not full and target_skus is not None:
        if not target_skus:
            return 0
        match_filter["sku"]["$in"] = target_skus

    pipeline = [
        {"$match": match_filter},
        {
            "$group": {
                "_id": "$sku",
                "product_name": {"$first": "$name"},
                "total_quantity": {"$sum": "$qty"},
                "total_revenue": {"$sum": "$total"},
                "order_count": {"$sum": 1},
            }
        },
    ]

    aggregates = list(flat_col.aggregate(pipeline))
    if full:
        prod_col.delete_many({})

    operations = []
    for agg in aggregates:
        sku = agg["_id"]
        if not sku:
            continue

        doc = {
            "sku": sku,
            "product_name": agg.get("product_name") or sku,
            "total_quantity": float(agg.get("total_quantity", 0.0)),
            "total_revenue": round(float(agg.get("total_revenue", 0.0)), 2),
            "order_count": int(agg.get("order_count", 0)),
            "last_refreshed_at": now_iso,
        }

        operations.append(
            ReplaceOne({"sku": sku}, doc, upsert=True)
        )

    if operations:
        prod_col.bulk_write(operations, ordered=False)

    return len(operations)


def refresh_materialized_views(
    db: Database | None = None,
    full: bool = False,
) -> dict[str, Any]:
    """
    Master refresh function implementing the incremental partition refresh mechanism.

    Detects modified/new runs in orders_validated compared to mv_state,
    determines affected order IDs, dates, and SKUs, and updates only those partitions.

    Args:
        db: MongoDB database instance.
        full: If True, forces a full rebuild regardless of state.

    Returns:
        dict: Execution report with timing, mode, and affected partitions.
    """
    t0 = time.perf_counter()
    if db is None:
        db = get_db()

    ensure_mv_indexes(db)

    val_col = db[COL_VALIDATED]
    state_col = db[COL_MV_STATE]

    # Inspect current runs in orders_validated
    run_groups = list(
        val_col.aggregate([
            {"$group": {"_id": "$metadata.run_id", "count": {"$sum": 1}}}
        ])
    )
    current_runs = {
        str(r["_id"]): r["count"] for r in run_groups if r["_id"] is not None
    }

    state_doc = state_col.find_one({"_id": "state"}) or {}
    prev_runs = state_doc.get("runs_processed", {})

    # Detect dirty (new or modified) runs
    dirty_runs = [
        run_id
        for run_id, count in current_runs.items()
        if prev_runs.get(run_id) != count
    ]

    is_initial_build = not state_doc or full or len(prev_runs) == 0

    if not is_initial_build and not dirty_runs:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "UP_TO_DATE",
            "mode": "incremental",
            "message": "All materialized views are already synchronized.",
            "affected_days": [],
            "affected_skus_count": 0,
            "views_refreshed": [],
            "elapsed_ms": elapsed_ms,
            "last_refreshed_at": state_doc.get("last_refreshed_at"),
        }

    if is_initial_build:
        mode = "full"
        items_written = refresh_order_items_flat(db, full=True)
        days_updated = refresh_daily_sales_summary(db, full=True)
        skus_updated = refresh_top_products_summary(db, full=True)
        affected_days = ["*all*"]
        affected_skus_count = skus_updated
    else:
        mode = "incremental"
        # Find orders touched by the dirty runs
        touched_orders = list(
            val_col.find(
                {"metadata.run_id": {"$in": dirty_runs}},
                projection={"order_id": 1, "order_date": 1, "items_json": 1},
            )
        )

        affected_order_ids = [str(o["order_id"]) for o in touched_orders if "order_id" in o]
        affected_days_set = set()
        affected_skus_set = set()

        for o in touched_orders:
            od = str(o.get("order_date", ""))
            if len(od) >= 10:
                affected_days_set.add(od[:10])
            items = parse_items(o.get("items_json"))
            for it in items:
                sku = it.get("sku")
                if sku:
                    affected_skus_set.add(sku)

        # 1. Update order_items_flat for touched orders
        refresh_order_items_flat(db, target_order_ids=affected_order_ids, full=False)

        # 2. Update daily_sales_summary for affected dates only
        days_updated = refresh_daily_sales_summary(
            db, target_days=list(affected_days_set), full=False
        )

        # 3. Update top_products_summary for affected SKUs only
        skus_updated = refresh_top_products_summary(
            db, target_skus=list(affected_skus_set), full=False
        )

        affected_days = sorted(list(affected_days_set))
        affected_skus_count = len(affected_skus_set)

    now_iso = utc_now_iso()
    state_col.replace_one(
        {"_id": "state"},
        {
            "_id": "state",
            "last_refreshed_at": now_iso,
            "runs_processed": current_runs,
            "total_validated_orders": sum(current_runs.values()),
        },
        upsert=True,
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "status": "SUCCESS",
        "mode": mode,
        "affected_days": affected_days,
        "affected_skus_count": affected_skus_count,
        "views_refreshed": [COL_ORDER_ITEMS_FLAT, COL_DAILY_SALES, COL_TOP_PRODUCTS],
        "refreshed_at": now_iso,
        "elapsed_ms": elapsed_ms,
    }


def get_daily_sales_view(
    db: Database | None = None,
    limit: int = 30,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict[str, Any]]:
    """Query pre-computed daily_sales_summary view directly (high-speed read)."""
    if db is None:
        db = get_db()
    col = db[COL_DAILY_SALES]

    query_filter: dict[str, Any] = {}
    if from_date and to_date:
        query_filter["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        query_filter["date"] = {"$gte": from_date}
    elif to_date:
        query_filter["date"] = {"$lte": to_date}

    cursor = col.find(query_filter, {"_id": 0}).sort("date", -1).limit(limit)
    return list(cursor)


def get_top_products_view(
    db: Database | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Query pre-computed top_products_summary view directly (high-speed read)."""
    if db is None:
        db = get_db()
    col = db[COL_TOP_PRODUCTS]

    cursor = col.find({}, {"_id": 0}).sort("total_revenue", -1).limit(limit)
    return list(cursor)
