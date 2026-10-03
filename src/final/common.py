"""
common.py — Shared utilities for the Final Project.

Provides:
  - get_client() / get_db()  : MongoDB connection helpers using config.settings.
  - Collection name constants : existing midterm collections + new final-project ones.
  - num_expr(field_path)      : $convert-based Mongo expression for string→double coercion.
  - day_expr(field_path)      : $substrBytes expression extracting YYYY-MM-DD from ISO string.
  - parse_items(items_json)   : Python-side JSON parser for items_json strings; never raises.
  - utc_now_iso()             : Current UTC timestamp as ISO 8601 string.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from config.settings import MONGO_URI, MONGO_DATABASE


# ============================================================
# Collection Name Constants
# ============================================================

# --- Existing midterm collections (read-only from final code) ---
COL_RAW = "orders_raw"
COL_VALIDATED = "orders_validated"
COL_QUARANTINE = "orders_quarantine"

# --- New final-project collections ---
COL_DAILY_SALES = "daily_sales_summary"       # materialized view: daily revenue
COL_TOP_PRODUCTS = "top_products_summary"     # materialized view: product rankings
COL_ORDER_ITEMS_FLAT = "order_items_flat"     # exploded items (one doc per line-item)
COL_MV_STATE = "mv_state"                     # tracks run_id → doc_count per MV
COL_JOB_RUNS = "job_runs"                     # audit log for scheduled / API-triggered jobs


# ============================================================
# MongoDB Connection Helpers
# ============================================================

def get_client() -> MongoClient:
    """Return a new MongoClient using MONGO_URI from config.settings (env-overridable)."""
    return MongoClient(MONGO_URI)


def get_db(client: MongoClient | None = None) -> Database:
    """
    Return the active database using MONGO_DATABASE from config.settings.

    Args:
        client: Optional existing MongoClient. If None a new one is created —
                caller is responsible for closing it.
    """
    if client is None:
        client = get_client()
    return client[MONGO_DATABASE]


# ============================================================
# Mongo Expression Helpers
# ============================================================

def num_expr(field_path: str) -> dict:
    """
    Return a MongoDB aggregation expression that converts a field to double.

    Amounts in orders_validated are stored as STRINGS (e.g. "769000.0").
    $convert handles NaN / null / unparseable values gracefully.

    Args:
        field_path: Mongo field reference, e.g. "$total_amount".

    Returns:
        A dict usable inside a $project / $group expression:
        {
            "$convert": {
                "input": "<field_path>",
                "to": "double",
                "onError": 0,
                "onNull": 0
            }
        }

    Example:
        {"$sum": num_expr("$total_amount")}
    """
    return {
        "$convert": {
            "input": field_path,
            "to": "double",
            "onError": 0,
            "onNull": 0,
        }
    }


def day_expr(field_path: str = "$order_date") -> dict:
    """
    Return a MongoDB aggregation expression that extracts the date portion
    (YYYY-MM-DD) from an ISO 8601 string field.

    order_date is stored as a STRING such as "2025-02-24T21:29:00".
    $substrBytes safely extracts the first 10 characters.

    Args:
        field_path: Mongo field reference (default: "$order_date").

    Returns:
        {"$substrBytes": ["<field_path>", 0, 10]}

    Example:
        {"$group": {"_id": day_expr(), "total": {"$sum": num_expr("$total_amount")}}}
    """
    return {"$substrBytes": [field_path, 0, 10]}


# ============================================================
# Python-side Helpers
# ============================================================

def parse_items(items_json: Any) -> list[dict]:
    """
    Safely parse the items_json field from orders_validated into a list of dicts.

    Each item may have: sku, name, qty, unit_price, total.
    Values may be dirty (wrong types). Coercion is done here; the function never raises.

    Args:
        items_json: The raw value from the document (string, list, None, etc.).

    Returns:
        A list of normalised item dicts. Returns [] on any failure.
    """
    if items_json is None:
        return []

    # Already a list (shouldn't happen in current schema but be defensive)
    if isinstance(items_json, list):
        raw_list = items_json
    else:
        try:
            raw_list = json.loads(str(items_json))
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    if not isinstance(raw_list, list):
        return []

    result = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            result.append(
                {
                    "sku": str(item.get("sku", "") or ""),
                    "name": str(item.get("name", "") or ""),
                    "qty": _safe_float(item.get("qty")),
                    "unit_price": _safe_float(item.get("unit_price")),
                    "total": _safe_float(item.get("total")),
                }
            )
        except Exception:  # noqa: BLE001 — never propagate
            continue

    return result


def _safe_float(val: Any) -> float:
    """Convert val to float; return 0.0 on any failure."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string (e.g. '2026-10-03T20:00:00Z')."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
