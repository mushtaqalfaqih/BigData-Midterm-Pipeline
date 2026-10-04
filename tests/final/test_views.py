"""
test_views.py — Tests for Materialized Views and Incremental Refresh.
"""

from src.final.common import (
    COL_DAILY_SALES,
    COL_MV_STATE,
    COL_ORDER_ITEMS_FLAT,
    COL_TOP_PRODUCTS,
    get_db,
)
from src.final.views import (
    get_daily_sales_view,
    get_top_products_view,
    refresh_materialized_views,
)


def test_materialized_views_full_refresh():
    db = get_db()
    res = refresh_materialized_views(db=db, full=True)

    assert res["status"] == "SUCCESS"
    assert res["mode"] == "full"
    assert "daily_sales_summary" in res["views_refreshed"]
    assert "top_products_summary" in res["views_refreshed"]

    # Verify collections exist and have data
    assert db[COL_DAILY_SALES].count_documents({}) > 0
    assert db[COL_TOP_PRODUCTS].count_documents({}) > 0
    assert db[COL_ORDER_ITEMS_FLAT].count_documents({}) > 0

    state = db[COL_MV_STATE].find_one({"_id": "state"})
    assert state is not None
    assert "runs_processed" in state


def test_materialized_views_incremental_noop():
    db = get_db()
    # Running incremental immediately should be UP_TO_DATE
    res = refresh_materialized_views(db=db, full=False)
    assert res["status"] in ["UP_TO_DATE", "SUCCESS"]
    if res["status"] == "UP_TO_DATE":
        assert res["mode"] == "incremental"
        assert res["affected_days"] == []


def test_get_daily_sales_view():
    records = get_daily_sales_view(limit=10)
    assert isinstance(records, list)
    assert len(records) > 0
    first = records[0]
    assert "date" in first
    assert "total_sales" in first
    assert "order_count" in first
    assert "_id" not in first


def test_get_top_products_view():
    products = get_top_products_view(limit=5)
    assert isinstance(products, list)
    assert len(products) > 0
    first = products[0]
    assert "sku" in first
    assert "total_revenue" in first
    assert "product_name" in first
    assert "_id" not in first
