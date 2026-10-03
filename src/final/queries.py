"""
queries.py — Standard Analytical Query Registry for Final Project.

Provides 5 find()-style queries over orders_validated and orders_quarantine:
  1. customer_orders
  2. orders_by_status_period
  3. high_value_orders
  4. corrected_orders_by_rule
  5. quarantine_by_reason

Features:
  - Query registry with QuerySpec
  - Runtime resolution of parameter defaults from database data (no hardcoded literals)
  - ISO date detection with strict regex (rejects DD-MM-YYYY and slash formats)
  - String-to-number comparison using $expr and num_expr()
  - JSON-serializable output (drops _id, handles ObjectIds/datetimes)
  - Graceful handling of empty collections
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from bson import ObjectId
from pymongo.cursor import Cursor
from pymongo.database import Database

from src.final.common import (
    COL_QUARANTINE,
    COL_VALIDATED,
    get_db,
    num_expr,
)

# Strict regex matching ISO 8601 timestamps: YYYY-MM-DDTHH:MM:SS
ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T")


class QueryNotFound(KeyError):
    """Raised when a requested query name is not in the registry."""
    pass


@dataclass
class QuerySpec:
    name: str
    description: str
    params: dict[str, str]
    build_cursor: Callable[[Database, dict[str, Any]], tuple[Cursor, dict[str, Any]]]


def _clean_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Ensure document is JSON-serializable and omit _id."""
    clean = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, ObjectId):
            clean[k] = str(v)
        elif isinstance(v, (datetime, time.struct_time)):
            clean[k] = v.isoformat() if hasattr(v, "isoformat") else str(v)
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


def get_latest_iso_day(db: Database, col_name: str = COL_VALIDATED) -> str | None:
    """
    Safely find the latest valid ISO day (YYYY-MM-DD) in the collection.
    Uses strict regex filter to ensure slash-formatted (2025/..) or
    day-first (DD-MM-..) strings are ignored even if they sort higher alphabetically.
    """
    col = db[col_name]
    doc = col.find_one(
        {"order_date": ISO_DATE_REGEX},
        sort=[("order_date", -1)],
        projection={"order_date": 1},
    )
    if doc and doc.get("order_date"):
        return str(doc["order_date"])[:10]
    return None


# ============================================================
# Query Implementations (build_cursor)
# ============================================================

def _build_customer_orders(
    db: Database, params: dict[str, Any]
) -> tuple[Cursor, dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})

    customer_id = resolved.get("customer_id")
    if not customer_id:
        doc = col.find_one(
            {"customer_id": {"$exists": True, "$ne": None, "$ne": ""}},
            projection={"customer_id": 1},
        )
        customer_id = doc["customer_id"] if doc else ""
        resolved["customer_id"] = customer_id

    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    if not customer_id:
        cursor = col.find({"_id": {"$exists": False}}).limit(0)
        return cursor, resolved

    cursor = (
        col.find({"customer_id": customer_id}, projection={"_id": 0})
        .sort([("order_date", -1)])
        .limit(limit)
    )
    return cursor, resolved


def _build_orders_by_status_period(
    db: Database, params: dict[str, Any]
) -> tuple[Cursor, dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})

    # Status
    status = resolved.get("status")
    if not status:
        doc = col.find_one(
            {"status": {"$exists": True, "$ne": None, "$ne": ""}},
            projection={"status": 1},
        )
        status = doc["status"] if doc else "مؤكد"
        resolved["status"] = status

    # Date bounds
    to_day = resolved.get("to_day")
    if not to_day:
        latest = get_latest_iso_day(db)
        to_day = latest if latest else datetime.utcnow().strftime("%Y-%m-%d")
        resolved["to_day"] = to_day

    from_day = resolved.get("from_day")
    if not from_day:
        try:
            to_dt = datetime.strptime(to_day, "%Y-%m-%d")
            from_dt = to_dt - timedelta(days=30)
            from_day = from_dt.strftime("%Y-%m-%d")
        except ValueError:
            from_day = to_day
        resolved["from_day"] = from_day

    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    # Compute next_day for strict < bound
    try:
        next_day = (datetime.strptime(to_day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        next_day = to_day + "Z"

    query_filter: dict[str, Any] = {
        "status": status,
        "order_date": {"$gte": from_day, "$lt": next_day},
    }

    cursor = (
        col.find(query_filter, projection={"_id": 0})
        .sort([("order_date", -1)])
        .limit(limit)
    )
    return cursor, resolved


def _build_high_value_orders(
    db: Database, params: dict[str, Any]
) -> tuple[Cursor, dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})

    to_day = resolved.get("to_day")
    if not to_day:
        latest = get_latest_iso_day(db)
        to_day = latest if latest else datetime.utcnow().strftime("%Y-%m-%d")
        resolved["to_day"] = to_day

    from_day = resolved.get("from_day")
    if not from_day:
        try:
            to_dt = datetime.strptime(to_day, "%Y-%m-%d")
            from_dt = to_dt - timedelta(days=30)
            from_day = from_dt.strftime("%Y-%m-%d")
        except ValueError:
            from_day = to_day
        resolved["from_day"] = from_day

    min_amount = resolved.get("min_amount")
    if min_amount is None:
        # Resolve 90th percentile over bounded $sample of 500
        pipeline = [
            {"$sample": {"size": 500}},
            {"$project": {"total": num_expr("$total_amount")}},
        ]
        try:
            samples = [
                float(d["total"])
                for d in col.aggregate(pipeline)
                if d.get("total") is not None and float(d.get("total", 0)) > 0
            ]
            samples.sort()
            if samples:
                idx = int(0.90 * len(samples))
                min_amount = round(samples[min(idx, len(samples) - 1)], 2)
            else:
                min_amount = 500000.0
        except Exception:
            min_amount = 500000.0
        resolved["min_amount"] = min_amount
    else:
        resolved["min_amount"] = float(min_amount)

    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    try:
        next_day = (datetime.strptime(to_day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        next_day = to_day + "Z"

    # Numeric range cannot use standard string index; use $expr with num_expr()
    query_filter: dict[str, Any] = {
        "order_date": {"$gte": from_day, "$lt": next_day},
        "$expr": {"$gte": [num_expr("$total_amount"), float(min_amount)]},
    }

    cursor = (
        col.find(query_filter, projection={"_id": 0})
        .sort([("order_date", -1)])
        .limit(limit)
    )
    return cursor, resolved


def _build_corrected_orders_by_rule(
    db: Database, params: dict[str, Any]
) -> tuple[Cursor, dict[str, Any]]:
    col = db[COL_VALIDATED]
    resolved = dict(params or {})

    rule_code = resolved.get("rule_code")
    if not rule_code:
        doc = col.find_one(
            {"quality_status": "CORRECTED", "corrections.rule_code": {"$exists": True}},
            projection={"corrections": 1},
        )
        if doc and doc.get("corrections"):
            rule_code = doc["corrections"][0].get("rule_code", "RULE_7_STATUS_NORMALIZATION")
        else:
            rule_code = "RULE_7_STATUS_NORMALIZATION"
        resolved["rule_code"] = rule_code

    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    query_filter: dict[str, Any] = {
        "quality_status": "CORRECTED",
        "corrections.rule_code": rule_code,
    }

    cursor = (
        col.find(query_filter, projection={"_id": 0})
        .sort([("order_date", -1)])
        .limit(limit)
    )
    return cursor, resolved


def _build_quarantine_by_reason(
    db: Database, params: dict[str, Any]
) -> tuple[Cursor, dict[str, Any]]:
    col = db[COL_QUARANTINE]
    resolved = dict(params or {})

    reason = resolved.get("reason")
    if not reason:
        doc = col.find_one(
            {"quarantine_reasons": {"$exists": True, "$ne": []}},
            projection={"quarantine_reasons": 1},
        )
        if doc and doc.get("quarantine_reasons"):
            reason = doc["quarantine_reasons"][0]
        else:
            reason = "CORRUPTED_JSON"
        resolved["reason"] = reason

    limit = min(max(int(resolved.get("limit", 20)), 1), 200)
    resolved["limit"] = limit

    projection = {
        "_id": 0,
        "raw_record.order_id": 1,
        "quarantine_reasons": 1,
        "metadata.run_id": 1,
        "metadata.source_file": 1,
    }

    cursor = (
        col.find({"quarantine_reasons": reason}, projection=projection)
        .sort([("_id", -1)])
        .limit(limit)
    )
    return cursor, resolved


# ============================================================
# Query Registry
# ============================================================

QUERIES: dict[str, QuerySpec] = {
    "customer_orders": QuerySpec(
        name="customer_orders",
        description="Fetch orders for a specific customer sorted by order_date descending.",
        params={"customer_id": "string", "limit": "int (default 20, max 200)"},
        build_cursor=_build_customer_orders,
    ),
    "orders_by_status_period": QuerySpec(
        name="orders_by_status_period",
        description="Filter orders by status and date range [from_day, to_day] sorted by order_date descending.",
        params={"status": "string", "from_day": "YYYY-MM-DD", "to_day": "YYYY-MM-DD", "limit": "int"},
        build_cursor=_build_orders_by_status_period,
    ),
    "high_value_orders": QuerySpec(
        name="high_value_orders",
        description="Orders within date range having total_amount >= min_amount (via $expr conversion).",
        params={"min_amount": "float", "from_day": "YYYY-MM-DD", "to_day": "YYYY-MM-DD", "limit": "int"},
        build_cursor=_build_high_value_orders,
    ),
    "corrected_orders_by_rule": QuerySpec(
        name="corrected_orders_by_rule",
        description="Orders classified as CORRECTED that underwent a specific cleaning rule.",
        params={"rule_code": "string", "limit": "int"},
        build_cursor=_build_corrected_orders_by_rule,
    ),
    "quarantine_by_reason": QuerySpec(
        name="quarantine_by_reason",
        description="Quarantine records tagged with a specific validation failure reason.",
        params={"reason": "string", "limit": "int"},
        build_cursor=_build_quarantine_by_reason,
    ),
}


def run_query(
    name: str,
    params: dict[str, Any] | None = None,
    db: Database | None = None,
) -> dict[str, Any]:
    """
    Execute a registered analytical query with resolved defaults.

    Args:
        name: Name of query in QUERIES registry.
        params: Optional dict of query parameters.
        db: Optional PyMongo database instance.

    Returns:
        JSON-serializable dict:
        {"name", "description", "params_used", "count", "data", "elapsed_ms"}
    """
    if name not in QUERIES:
        raise QueryNotFound(f"Query '{name}' not found in registry. Available: {list(QUERIES.keys())}")

    if db is None:
        db = get_db()

    spec = QUERIES[name]
    t0 = time.perf_counter()
    cursor, resolved_params = spec.build_cursor(db, params or {})
    raw_docs = list(cursor)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    data = [_clean_doc(d) for d in raw_docs]

    result: dict[str, Any] = {
        "name": spec.name,
        "description": spec.description,
        "params_used": resolved_params,
        "count": len(data),
        "data": data,
        "elapsed_ms": elapsed_ms,
    }
    if len(data) == 0:
        result["message"] = "No matching documents found or collection is empty."

    return result
