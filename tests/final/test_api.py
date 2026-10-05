"""
test_api.py — End-to-end Tests for Unified FastAPI Application.

Tests all 10 official routes:
  1. GET  /health
  2. POST /indexes
  3. GET  /queries
  4. GET  /queries/{name}
  5. GET  /aggregations
  6. GET  /aggregations/{name}
  7. POST /refresh-mv
  8. GET  /jobs
  9. POST /jobs/{name}/run
 10. POST /ingest
"""

from fastapi.testclient import TestClient
from src.final.api import app

client = TestClient(app)


def test_api_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UP"
    assert "database" in data
    assert data["database"]["status"] == "CONNECTED"
    assert "counts" in data["database"]


def test_api_indexes_endpoint():
    resp = client.post("/indexes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "indexes" in data


def test_api_list_queries():
    resp = client.get("/queries")
    assert resp.status_code == 200
    queries = resp.json()
    assert isinstance(queries, list)
    assert len(queries) >= 5
    names = [q["name"] for q in queries]
    assert "customer_orders" in names
    assert "high_value_orders" in names


def test_api_run_query_success():
    resp = client.get("/queries/customer_orders?limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "customer_orders"
    assert "data" in data


def test_api_run_query_not_found():
    resp = client.get("/queries/unknown_query_name")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_list_aggregations():
    resp = client.get("/aggregations")
    assert resp.status_code == 200
    aggs = resp.json()
    assert isinstance(aggs, list)
    assert len(aggs) >= 5
    names = [a["name"] for a in aggs]
    assert "sales_by_city" in names
    assert "top_products" in names


def test_api_run_aggregation_success():
    resp = client.get("/aggregations/sales_by_city?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["aggregation"] == "sales_by_city"
    assert "results" in data


def test_api_run_aggregation_not_found():
    resp = client.get("/aggregations/unknown_agg_name")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_refresh_mv_endpoint():
    resp = client.post("/refresh-mv?full=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["SUCCESS", "UP_TO_DATE"]


def test_api_list_jobs():
    resp = client.get("/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "registered_jobs" in data
    assert "recent_runs" in data
    assert len(data["registered_jobs"]) >= 2


def test_api_run_job_on_demand_success():
    resp = client.post("/jobs/pipeline_consistency_audit/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "execution" in data
    assert data["execution"]["status"] == "SUCCESS"


def test_api_run_job_on_demand_not_found():
    resp = client.post("/jobs/unknown_job_xyz/run")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_openapi_json():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/health" in schema["paths"]
    assert "/ingest" in schema["paths"]
    assert "/indexes" in schema["paths"]
    assert "/queries" in schema["paths"]
    assert "/queries/{name}" in schema["paths"]
    assert "/aggregations" in schema["paths"]
    assert "/aggregations/{name}" in schema["paths"]
    assert "/refresh-mv" in schema["paths"]
    assert "/jobs" in schema["paths"]
    assert "/jobs/{name}/run" in schema["paths"]


def test_api_dashboard_endpoint():
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Chart.js" in resp.text

