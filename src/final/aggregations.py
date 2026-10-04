"""
aggregations.py — Analytical Aggregation Pipeline Reports for Final Project.

Provides 5 standard Aggregation Reports satisfying Course Specification (Phase 2):
  1. sales_by_city       — Total revenue, order count, and average order value grouped by city.
  2. top_products        — Top selling products by revenue and quantity.
  3. top_customers       — Top spending customers by total spend and order count.
  4. sales_by_period     — Daily sales summary across time grouped by YYYY-MM-DD.
  5. orders_by_status    — Distribution of orders and revenue across status and payment methods.
  Bonus 6:
  6. quarantine_summary  — Distribution of quarantine errors across error codes.

Guarantees:
  - Dynamic execution: zero hardcoded file names, counts, dates, or results.
  - Type-safe monetary coercion using num_expr() from common.py.
  - Safe date extraction using day_expr() from common.py.
  - Unbounded scan protection with configurable limits.
  - JSON-serializable outputs (no raw ObjectIds or bson types).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from bson import ObjectId
from pymongo.database import Database

from src.final.common import (
    COL_ORDER_ITEMS_FLAT,
    COL_QUARANTINE,
    COL_VALIDATED,
    day_expr,
    get_db,
    num_expr,
    parse_items,
)


class AggregationNotFound(KeyError):
    """Raised when a requested aggregation name is not found in the registry."""
    pass


@dataclass
class AggregationSpec:
    name: str
    title: str
    description: str
    params: dict[str, str] = field(default_factory=dict)
    run: Callable[[Database, dict[str, Any]], tuple[list[dict[str, Any]], dict[str, Any]]] = None


def _clean_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Ensure document is clean and JSON-serializable."""
    clean = {}
    for k, v in doc.items():
        if k == "_id" and isinstance(v, ObjectId):
            continue
        if isinstance(v, ObjectId):
            clean[k] = str(v)
        elif isinstance(v, datetime):
            clean[k] = v.isoformat()
        elif isinstance(v, dict):
            clean[k] = _clean_doc(v)
        elif isinstance(v, list):
            clean[k] = [
                _clean_doc(item) if isinstance(item, dict)
                else (str(item) if isinstance(item, ObjectId) else item)
                for item in v
            ]
        else:
            clean[k] = v
    return clean


# ============================================================
# 1. Sales by City
# ============================================================

def _run_sales_by_city(
    db: Database, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})
    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    pipeline = [
        {"$match": {"city": {"$exists": True, "$ne": None, "$ne": ""}}},
        {
            "$group": {
                "_id": "$city",
                "order_count": {"$sum": 1},
                "total_revenue": {"$sum": num_expr("$total_amount")},
                "avg_order_value": {"$avg": num_expr("$total_amount")},
                "total_delivery_cost": {"$sum": num_expr("$delivery_cost")},
            }
        },
        {"$sort": {"total_revenue": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "city": "$_id",
                "order_count": 1,
                "total_revenue": {"$round": ["$total_revenue", 2]},
                "avg_order_value": {"$round": ["$avg_order_value", 2]},
                "total_delivery_cost": {"$round": ["$total_delivery_cost", 2]},
            }
        },
    ]

    results = [_clean_doc(d) for d in col.aggregate(pipeline)]
    return results, resolved


# ============================================================
# 2. Top Products
# ============================================================

def _run_top_products(
    db: Database, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resolved = dict(params or {})
    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    flat_col = db[COL_ORDER_ITEMS_FLAT]
    
    # Check if order_items_flat is already populated
    if flat_col.estimated_document_count() > 0:
        pipeline = [
            {"$match": {"sku": {"$exists": True, "$ne": None, "$ne": ""}}},
            {
                "$group": {
                    "_id": "$sku",
                    "product_name": {"$first": "$name"},
                    "total_quantity": {"$sum": "$qty"},
                    "total_revenue": {"$sum": "$total"},
                    "orders_count": {"$sum": 1},
                }
            },
            {"$sort": {"total_revenue": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "_id": 0,
                    "sku": "$_id",
                    "product_name": 1,
                    "total_quantity": 1,
                    "total_revenue": {"$round": ["$total_revenue", 2]},
                    "orders_count": 1,
                }
            },
        ]
        results = [_clean_doc(d) for d in flat_col.aggregate(pipeline)]
        return results, resolved

    # Fallback / Direct execution over orders_validated with parse_items
    val_col = db[COL_VALIDATED]
    cursor = val_col.find(
        {"items_json": {"$exists": True, "$ne": None, "$ne": ""}},
        projection={"items_json": 1},
    ).limit(5000)

    product_stats: dict[str, dict[str, Any]] = {}
    for doc in cursor:
        items = parse_items(doc.get("items_json"))
        for item in items:
            sku = item.get("sku")
            if not sku:
                continue
            if sku not in product_stats:
                product_stats[sku] = {
                    "sku": sku,
                    "product_name": item.get("name") or sku,
                    "total_quantity": 0,
                    "total_revenue": 0.0,
                    "orders_count": 0,
                }
            product_stats[sku]["total_quantity"] += int(item.get("qty", 1))
            product_stats[sku]["total_revenue"] += float(item.get("total", 0.0))
            product_stats[sku]["orders_count"] += 1

    sorted_products = sorted(
        product_stats.values(), key=lambda p: p["total_revenue"], reverse=True
    )[:limit]

    for p in sorted_products:
        p["total_revenue"] = round(p["total_revenue"], 2)

    return sorted_products, resolved


# ============================================================
# 3. Top Customers
# ============================================================

def _run_top_customers(
    db: Database, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})
    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    pipeline = [
        {"$match": {"customer_id": {"$exists": True, "$ne": None, "$ne": ""}}},
        {
            "$group": {
                "_id": "$customer_id",
                "customer_name": {"$first": "$customer_name"},
                "order_count": {"$sum": 1},
                "total_spend": {"$sum": num_expr("$total_amount")},
                "avg_order_value": {"$avg": num_expr("$total_amount")},
                "last_order_date": {"$max": "$order_date"},
            }
        },
        {"$sort": {"total_spend": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "customer_id": "$_id",
                "customer_name": 1,
                "order_count": 1,
                "total_spend": {"$round": ["$total_spend", 2]},
                "avg_order_value": {"$round": ["$avg_order_value", 2]},
                "last_order_date": 1,
            }
        },
    ]

    results = [_clean_doc(d) for d in col.aggregate(pipeline)]
    return results, resolved


# ============================================================
# 4. Sales by Period (Daily Sales)
# ============================================================

def _run_sales_by_period(
    db: Database, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})
    limit = min(max(int(resolved.get("limit", 30)), 1), 365)
    resolved["limit"] = limit

    match_stage: dict[str, Any] = {"order_date": {"$exists": True, "$ne": None, "$ne": ""}}

    from_day = resolved.get("from_day")
    to_day = resolved.get("to_day")
    if from_day and to_day:
        match_stage["order_date"] = {"$gte": from_day, "$lte": to_day + "T23:59:59"}
    elif from_day:
        match_stage["order_date"] = {"$gte": from_day}
    elif to_day:
        match_stage["order_date"] = {"$lte": to_day + "T23:59:59"}

    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": day_expr("$order_date"),
                "order_count": {"$sum": 1},
                "total_revenue": {"$sum": num_expr("$total_amount")},
                "avg_order_value": {"$avg": num_expr("$total_amount")},
                "paid_orders": {
                    "$sum": {
                        "$cond": [{"$eq": ["$payment_status", "تم الدفع"]}, 1, 0]
                    }
                },
            }
        },
        {"$match": {"_id": {"$regex": r"^\d{4}-\d{2}-\d{2}$"}}},
        {"$sort": {"_id": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "order_count": 1,
                "total_revenue": {"$round": ["$total_revenue", 2]},
                "avg_order_value": {"$round": ["$avg_order_value", 2]},
                "paid_orders": 1,
            }
        },
    ]

    results = [_clean_doc(d) for d in col.aggregate(pipeline)]
    return results, resolved


# ============================================================
# 5. Orders by Status & Payment Method
# ============================================================

def _run_orders_by_status(
    db: Database, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})
    limit = min(max(int(resolved.get("limit", 50)), 1), 200)
    resolved["limit"] = limit

    pipeline = [
        {"$match": {"status": {"$exists": True, "$ne": None, "$ne": ""}}},
        {
            "$group": {
                "_id": {
                    "status": "$status",
                    "payment_method": {"$ifNull": ["$payment_method", "غير محدد"]},
                },
                "order_count": {"$sum": 1},
                "total_revenue": {"$sum": num_expr("$total_amount")},
                "avg_amount": {"$avg": num_expr("$total_amount")},
            }
        },
        {"$sort": {"order_count": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "status": "$_id.status",
                "payment_method": "$_id.payment_method",
                "order_count": 1,
                "total_revenue": {"$round": ["$total_revenue", 2]},
                "avg_amount": {"$round": ["$avg_amount", 2]},
            }
        },
    ]

    results = [_clean_doc(d) for d in col.aggregate(pipeline)]
    return results, resolved


# ============================================================
# 6. Quarantine Summary
# ============================================================

def _run_quarantine_summary(
    db: Database, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    col = db[COL_QUARANTINE]
    resolved = dict(params or {})
    limit = min(max(int(resolved.get("limit", 20)), 1), 100)
    resolved["limit"] = limit

    pipeline = [
        {"$unwind": "$quarantine_reasons"},
        {
            "$group": {
                "_id": "$quarantine_reasons",
                "count": {"$sum": 1},
                "latest_incident": {"$max": "$metadata.quarantined_at"},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "error_code": "$_id",
                "count": 1,
                "latest_incident": 1,
            }
        },
    ]

    results = [_clean_doc(d) for d in col.aggregate(pipeline)]
    return results, resolved


# ============================================================
# Aggregations Registry
# ============================================================

AGGREGATIONS: dict[str, AggregationSpec] = {
    "sales_by_city": AggregationSpec(
        name="sales_by_city",
        title="Sales by City",
        description="Total revenue, order count, and average order value grouped by city.",
        params={"limit": "Maximum number of cities to return (default: 20)"},
        run=_run_sales_by_city,
    ),
    "top_products": AggregationSpec(
        name="top_products",
        title="Top Products by Revenue & Quantity",
        description="Best performing products ranked by total revenue and items sold.",
        params={"limit": "Maximum number of products to return (default: 20)"},
        run=_run_top_products,
    ),
    "top_customers": AggregationSpec(
        name="top_customers",
        title="Top Customers by Spending",
        description="Highest spending customers ranked by cumulative order amounts.",
        params={"limit": "Maximum number of customers to return (default: 20)"},
        run=_run_top_customers,
    ),
    "sales_by_period": AggregationSpec(
        name="sales_by_period",
        title="Sales by Time Period (Daily)",
        description="Daily sales trends with order volumes and revenue breakdown.",
        params={
            "from_day": "Start date YYYY-MM-DD (optional)",
            "to_day": "End date YYYY-MM-DD (optional)",
            "limit": "Max days to return (default: 30)",
        },
        run=_run_sales_by_period,
    ),
    "orders_by_status": AggregationSpec(
        name="orders_by_status",
        title="Orders by Status & Payment Method",
        description="Distribution of order counts and amounts across lifecycle states.",
        params={"limit": "Maximum groups to return (default: 50)"},
        run=_run_orders_by_status,
    ),
    "quarantine_summary": AggregationSpec(
        name="quarantine_summary",
        title="Quarantine Diagnostic Distribution",
        description="Frequency breakdown of records isolated in orders_quarantine by reason.",
        params={"limit": "Max reasons to return (default: 20)"},
        run=_run_quarantine_summary,
    ),
}


def list_aggregations() -> list[dict[str, Any]]:
    """Return catalog of available aggregation reports."""
    return [
        {
            "name": spec.name,
            "title": spec.title,
            "description": spec.description,
            "params": spec.params,
        }
        for spec in AGGREGATIONS.values()
    ]


def execute_aggregation(
    name: str,
    params: dict[str, Any] | None = None,
    db: Database | None = None,
) -> dict[str, Any]:
    """
    Execute a registered aggregation report by name.

    Returns:
        dict: {
            "aggregation": name,
            "params_used": resolved_params,
            "count": len(results),
            "results": results
        }
    """
    if name not in AGGREGATIONS:
        raise AggregationNotFound(
            f"Aggregation '{name}' not found. Available: {list(AGGREGATIONS.keys())}"
        )

    if db is None:
        db = get_db()

    spec = AGGREGATIONS[name]
    results, resolved_params = spec.run(db, params or {})

    return {
        "aggregation": name,
        "title": spec.title,
        "params_used": resolved_params,
        "count": len(results),
        "results": results,
    }
