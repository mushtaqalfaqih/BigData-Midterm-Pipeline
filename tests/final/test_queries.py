"""
test_queries.py — Unit and integration tests for final project queries and indexes.

Tests:
  - Each query returns JSON-serializable output (no _id, no ObjectIds/datetimes)
  - Parameter defaults resolve dynamically from data
  - get_latest_iso_day() strictly ignores slash-formatted and DD-MM-YYYY dates
  - ensure_indexes() is idempotent
  - drop_final_indexes() never removes non-final (midterm / primary) indexes
  - Unknown query raises QueryNotFound
  - Empty collection returns empty data structure gracefully
"""

import json
import uuid
import pytest
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from config.settings import MONGO_URI
from src.final.common import COL_QUARANTINE, COL_VALIDATED
from src.final.indexes import drop_final_indexes, ensure_indexes, list_indexes
from src.final.queries import (
    QUERIES,
    QueryNotFound,
    get_latest_iso_day,
    run_query,
)


@pytest.fixture(scope="module")
def mongo_client():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except (ConnectionFailure, Exception):
        pytest.skip("MongoDB server is not reachable")
    yield client
    client.close()


@pytest.fixture(scope="module")
def test_db(mongo_client):
    db_name = f"test_final_{uuid.uuid4().hex[:8]}"
    db = mongo_client[db_name]

    # Pre-populate midterm indexes
    val_col = db[COL_VALIDATED]
    quar_col = db[COL_QUARANTINE]

    val_col.create_index([("order_id", 1)], unique=True, name="idx_val_order_id_unique")
    val_col.create_index([("status", 1)], name="idx_val_status")
    quar_col.create_index([("quarantine_reasons", 1)], name="idx_quar_reasons")

    # Seed ~30 synthetic documents in orders_validated
    # Notice: Include odd dates (slash format and DD-MM) to ensure ISO regex filtering works
    synthetic_docs = []
    statuses = ["مؤكد", "قيد الشحن", "تم التسليم", "ملغي", "مرتجع", "قيد الانتظار"]
    customers = [f"CUST-00{i}" for i in range(1, 6)]

    # Standard ISO docs (2025-01 to 2025-05-01)
    for i in range(1, 25):
        day = f"2025-04-{i:02d}" if i <= 20 else f"2025-05-{i-20:02d}"
        iso_date = f"{day}T10:00:00"
        is_corrected = (i % 3 == 0)
        doc = {
            "order_id": f"TEST-ORD-{i:03d}",
            "customer_id": customers[i % len(customers)],
            "status": statuses[i % len(statuses)],
            "order_date": iso_date,
            "total_amount": str(100000.0 + (i * 25000.0)),
            "quality_status": "CORRECTED" if is_corrected else "VALID",
            "corrections": (
                [{"rule_code": "RULE_1_ARABIC_DIGITS", "field": "customer_phone"}]
                if is_corrected else []
            ),
            "items_json": json.dumps([{"sku": f"SKU-{i}", "name": "Item", "qty": 1, "unit_price": 50000.0, "total": 50000.0}]),
        }
        synthetic_docs.append(doc)

    # Add odd dates that would SORT HIGHER than 2025-05-01 if not strictly filtered:
    # 1. Slash format (ASCII '/' > '-'): '2025/06/15'
    synthetic_docs.append({
        "order_id": "TEST-ODD-SLASH-1",
        "customer_id": "CUST-001",
        "status": "مؤكد",
        "order_date": "2025/06/15 14:00:00",
        "total_amount": "999999.0",
        "quality_status": "VALID",
    })
    synthetic_docs.append({
        "order_id": "TEST-ODD-SLASH-2",
        "customer_id": "CUST-002",
        "status": "مؤكد",
        "order_date": "2025/08/20 09:30:00",
        "total_amount": "800000.0",
        "quality_status": "VALID",
    })
    # 2. DD-MM format ('31-12-2025' > '2025-..')
    synthetic_docs.append({
        "order_id": "TEST-ODD-DDMM-1",
        "customer_id": "CUST-003",
        "status": "مؤكد",
        "order_date": "31-12-2025 23:59:00",
        "total_amount": "750000.0",
        "quality_status": "VALID",
    })
    # 3. Garbage date
    synthetic_docs.append({
        "order_id": "TEST-ODD-GARBAGE",
        "customer_id": "CUST-004",
        "status": "مؤكد",
        "order_date": "2025-99-99 99:99:99",
        "total_amount": "500000.0",
        "quality_status": "VALID",
    })

    val_col.insert_many(synthetic_docs)

    # Seed orders_quarantine
    quar_docs = [
        {
            "raw_record": {"order_id": "Q-001"},
            "quarantine_reasons": ["CORRUPTED_JSON"],
            "metadata": {"run_id": "test-run-1", "source_file": "test.csv"},
        },
        {
            "raw_record": {"order_id": "Q-002"},
            "quarantine_reasons": ["MISSING_ORDER_ID"],
            "metadata": {"run_id": "test-run-1", "source_file": "test.csv"},
        },
    ]
    quar_col.insert_many(quar_docs)

    yield db

    # Teardown: drop test database
    mongo_client.drop_database(db_name)


def test_latest_iso_day_ignores_odd_dates(test_db):
    """Confirm get_latest_iso_day ignores '2025/08/20' and '31-12-2025' and picks '2025-05-04'."""
    latest = get_latest_iso_day(test_db)
    assert latest == "2025-05-04"
    assert not latest.startswith("2025/")
    assert not latest.startswith("31-")


def test_each_query_returns_json_serializable_output(test_db):
    """Every query in the registry must produce JSON-serializable output with no _id."""
    for qname in QUERIES:
        res = run_query(qname, db=test_db)
        # Must serialize cleanly to JSON string
        json_str = json.dumps(res)
        assert json_str is not None
        assert res["name"] == qname
        assert "count" in res
        assert "data" in res
        assert "elapsed_ms" in res

        # Validate documents inside data have no _id
        for doc in res["data"]:
            assert "_id" not in doc


def test_defaults_resolve_from_data(test_db):
    """Ensure running queries without parameters resolves valid defaults from real docs."""
    # 1. customer_orders
    res = run_query("customer_orders", db=test_db)
    assert res["params_used"]["customer_id"].startswith("CUST-")
    assert res["count"] > 0

    # 2. orders_by_status_period
    res = run_query("orders_by_status_period", db=test_db)
    assert "status" in res["params_used"]
    assert res["params_used"]["to_day"] == "2025-05-04"
    assert res["count"] > 0

    # 3. high_value_orders
    res = run_query("high_value_orders", db=test_db)
    assert "min_amount" in res["params_used"]
    assert float(res["params_used"]["min_amount"]) > 0

    # 4. corrected_orders_by_rule
    res = run_query("corrected_orders_by_rule", db=test_db)
    assert res["params_used"]["rule_code"] == "RULE_1_ARABIC_DIGITS"
    assert res["count"] > 0

    # 5. quarantine_by_reason
    res = run_query("quarantine_by_reason", db=test_db)
    assert res["params_used"]["reason"] in ["CORRUPTED_JSON", "MISSING_ORDER_ID"]
    assert res["count"] > 0


def test_ensure_indexes_is_idempotent(test_db):
    """Calling ensure_indexes repeatedly must not duplicate or error."""
    res1 = ensure_indexes(test_db)
    assert len(res1["created"]) + len(res1["already_existed"]) == 4

    res2 = ensure_indexes(test_db)
    assert len(res2["created"]) == 0
    assert len(res2["already_existed"]) == 4


def test_drop_final_indexes_never_removes_non_final_index(test_db):
    """drop_final_indexes must drop idx_final_* but leave midterm and primary indexes."""
    ensure_indexes(test_db)

    # Drop final indexes
    drop_res = drop_final_indexes(test_db)
    assert len(drop_res["dropped"]) == 4

    # Verify existing indexes
    indexes = list_indexes(test_db)
    index_names = {idx["name"] for idx in indexes}

    # Midterm indexes MUST still exist
    assert "idx_val_order_id_unique" in index_names
    assert "idx_val_status" in index_names
    assert "idx_quar_reasons" in index_names
    assert "_id_" in index_names

    # Final indexes MUST NOT exist
    for idx_name in index_names:
        assert not idx_name.startswith("idx_final_")


def test_unknown_query_raises_query_not_found(test_db):
    """Requesting an unregistered query must raise QueryNotFound."""
    with pytest.raises(QueryNotFound):
        run_query("non_existent_analytical_query", db=test_db)


def test_empty_collection_returns_gracefully(mongo_client):
    """Querying an empty database must not raise unhandled exceptions."""
    empty_db_name = f"test_empty_{uuid.uuid4().hex[:8]}"
    empty_db = mongo_client[empty_db_name]

    try:
        res = run_query("customer_orders", db=empty_db)
        assert res["count"] == 0
        assert res["data"] == []
        assert "message" in res
    finally:
        mongo_client.drop_database(empty_db_name)
