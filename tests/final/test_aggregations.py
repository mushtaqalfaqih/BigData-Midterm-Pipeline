"""
test_aggregations.py — Tests for MongoDB Aggregation Pipeline Reports.
"""

import pytest
from src.final.aggregations import (
    AggregationNotFound,
    execute_aggregation,
    list_aggregations,
)
from src.final.common import get_db


def test_list_aggregations():
    aggs = list_aggregations()
    assert len(aggs) >= 5
    names = [a["name"] for a in aggs]
    assert "sales_by_city" in names
    assert "top_products" in names
    assert "top_customers" in names
    assert "sales_by_period" in names
    assert "orders_by_status" in names


def test_sales_by_city_aggregation():
    res = execute_aggregation("sales_by_city", {"limit": 5})
    assert res["aggregation"] == "sales_by_city"
    assert "results" in res
    assert isinstance(res["results"], list)
    if res["results"]:
        first = res["results"][0]
        assert "city" in first
        assert "total_revenue" in first
        assert "order_count" in first
        assert first["total_revenue"] >= 0


def test_top_products_aggregation():
    res = execute_aggregation("top_products", {"limit": 5})
    assert res["aggregation"] == "top_products"
    assert "results" in res
    assert isinstance(res["results"], list)
    if res["results"]:
        first = res["results"][0]
        assert "sku" in first
        assert "total_revenue" in first


def test_top_customers_aggregation():
    res = execute_aggregation("top_customers", {"limit": 5})
    assert res["aggregation"] == "top_customers"
    assert "results" in res
    assert isinstance(res["results"], list)
    if res["results"]:
        first = res["results"][0]
        assert "customer_id" in first
        assert "total_spend" in first


def test_sales_by_period_aggregation():
    res = execute_aggregation("sales_by_period", {"limit": 10})
    assert res["aggregation"] == "sales_by_period"
    assert "results" in res
    assert isinstance(res["results"], list)
    if res["results"]:
        first = res["results"][0]
        assert "date" in first or "period" in first
        assert "total_revenue" in first


def test_orders_by_status_aggregation():
    res = execute_aggregation("orders_by_status")
    assert res["aggregation"] == "orders_by_status"
    assert "results" in res
    assert isinstance(res["results"], list)


def test_invalid_aggregation_raises():
    with pytest.raises(AggregationNotFound):
        execute_aggregation("non_existent_aggregation")
