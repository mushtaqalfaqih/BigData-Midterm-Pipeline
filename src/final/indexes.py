"""
indexes.py — Final Project Index Management for MongoDB.

Manages dedicated indexes for analytical query acceleration on orders_validated:
  1. idx_final_customer_date   {customer_id: 1, order_date: -1} (compound, ESR Equality-Sort)
  2. idx_final_status_date     {status: 1, order_date: -1}      (compound, ESR Equality-Sort)
  3. idx_final_order_date      {order_date: 1}                  (single-field, date range scans)
  4. idx_final_correction_rule {"corrections.rule_code": 1}     (multikey, nested array filter)

Safety guarantees:
  - All final project indexes are strictly prefixed with 'idx_final_'.
  - drop_final_indexes() will NEVER drop midterm indexes (e.g. idx_val_order_id_unique, idx_val_status, idx_quar_*).
  - Note on quarantine_by_reason: already served by midterm index 'idx_quar_reasons', no duplicate index needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo.database import Database

from src.final.common import COL_QUARANTINE, COL_VALIDATED, get_db


@dataclass
class FinalIndexSpec:
    name: str
    collection: str
    keys: list[tuple[str, int]]
    reason: str


FINAL_INDEXES: list[FinalIndexSpec] = [
    FinalIndexSpec(
        name="idx_final_customer_date",
        collection=COL_VALIDATED,
        keys=[("customer_id", 1), ("order_date", -1)],
        reason=(
            "Compound index serving 'customer_orders'. Follows ESR rule: customer_id (Equality) "
            "then order_date (Sort desc). Eliminates blocking in-memory SORT stage."
        ),
    ),
    FinalIndexSpec(
        name="idx_final_status_date",
        collection=COL_VALIDATED,
        keys=[("status", 1), ("order_date", -1)],
        reason=(
            "Compound index serving 'orders_by_status_period'. Follows ESR rule: status (Equality) "
            "then order_date (Sort desc / Range). Satisfies status filtering and avoids in-memory sort."
        ),
    ),
    FinalIndexSpec(
        name="idx_final_order_date",
        collection=COL_VALIDATED,
        keys=[("order_date", 1)],
        reason=(
            "Single-field index serving general date range queries and 'high_value_orders'. "
            "Allows efficient B-tree index bounds scan before applying $expr total_amount post-filter."
        ),
    ),
    FinalIndexSpec(
        name="idx_final_correction_rule",
        collection=COL_VALIDATED,
        keys=[("corrections.rule_code", 1)],
        reason=(
            "Multikey index on nested array corrections.rule_code serving 'corrected_orders_by_rule'. "
            "Avoids full collection scan by indexing each element of the corrections array."
        ),
    ),
]


def ensure_indexes(db: Database | None = None) -> dict[str, list[str]]:
    """
    Ensure all FINAL_INDEXES exist on the target database. Idempotent.

    Returns:
        dict: {"created": [index_names], "already_existed": [index_names]}
    """
    if db is None:
        db = get_db()

    created: list[str] = []
    already_existed: list[str] = []

    for spec in FINAL_INDEXES:
        col = db[spec.collection]
        existing_info = col.index_information()
        if spec.name in existing_info:
            already_existed.append(spec.name)
        else:
            col.create_index(spec.keys, name=spec.name, background=True)
            created.append(spec.name)

    return {"created": created, "already_existed": already_existed}


def drop_final_indexes(db: Database | None = None) -> dict[str, list[str]]:
    """
    Drop ONLY indexes prefixed with 'idx_final_'.
    Will NEVER drop midterm indexes (idx_val_order_id_unique, idx_val_status, etc.)
    or default primary key index (_id_).

    Returns:
        dict: {"dropped": [index_names]}
    """
    if db is None:
        db = get_db()

    dropped: list[str] = []

    for col_name in [COL_VALIDATED, COL_QUARANTINE]:
        col = db[col_name]
        existing_info = col.index_information()
        for idx_name in list(existing_info.keys()):
            if idx_name.startswith("idx_final_"):
                col.drop_index(idx_name)
                dropped.append(f"{col_name}.{idx_name}")

    return {"dropped": dropped}


def list_indexes(db: Database | None = None) -> list[dict[str, Any]]:
    """
    List all indexes on orders_validated and orders_quarantine, indicating
    whether each is a midterm index or a final project index.

    Returns:
        list of dicts with index details.
    """
    if db is None:
        db = get_db()

    results: list[dict[str, Any]] = []

    for col_name in [COL_VALIDATED, COL_QUARANTINE]:
        col = db[col_name]
        info = col.index_information()
        for name, meta in info.items():
            is_final = name.startswith("idx_final_")
            is_pk = name == "_id_"
            category = "primary" if is_pk else ("final" if is_final else "midterm")
            results.append(
                {
                    "collection": col_name,
                    "name": name,
                    "keys": meta.get("key", []),
                    "unique": meta.get("unique", False),
                    "category": category,
                }
            )

    return results
