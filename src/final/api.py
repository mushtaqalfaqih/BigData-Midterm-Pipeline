"""
api.py — Unified FastAPI REST API for Final Big Data Project.

Provides complete OpenAPI/Swagger documentation at /docs covering all 10 required routes:
  1. GET  /health              — System health check and collection metrics.
  2. POST /ingest              — Trigger data ingestion ELT pipeline.
  3. POST /indexes             — Build and verify MongoDB indexes.
  4. GET  /queries             — List available analytical queries.
  5. GET  /queries/{name}      — Run a specific analytical query with query params.
  6. GET  /aggregations        — List available aggregation pipeline reports.
  7. GET  /aggregations/{name} — Run a specific aggregation report with query params.
  8. POST /refresh-mv          — Incremental or full refresh of materialized views.
  9. GET  /jobs                — List scheduled background jobs and recent execution audit logs.
 10. POST /jobs/{name}/run     — On-demand immediate execution of a job.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from config.settings import (
    MONGO_DATABASE,
    MONGO_URI,
    PROJECT_ROOT,
    RAW_COLLECTION,
    VALIDATED_COLLECTION,
    QUARANTINE_COLLECTION,
)
from src.elt_pipeline import run_elt_pipeline
from src.final.aggregations import (
    AggregationNotFound,
    execute_aggregation,
    list_aggregations,
)
from src.final.common import (
    COL_DAILY_SALES,
    COL_JOB_RUNS,
    COL_ORDER_ITEMS_FLAT,
    COL_TOP_PRODUCTS,
    get_db,
    utc_now_iso,
)
from src.final.indexes import ensure_indexes
from src.final.jobs import (
    get_job_runs,
    get_scheduler,
    list_registered_jobs,
    run_job_now,
    start_scheduler,
    stop_scheduler,
)
from src.final.queries import QUERIES, QueryNotFound, run_query
from src.final.views import (
    ensure_mv_indexes,
    get_daily_sales_view,
    get_top_products_view,
    refresh_materialized_views,
)


# ============================================================
# Lifespan Management
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Optional auto-start scheduler if SCHEDULER_AUTOSTART is set (default true)
    autostart = os.environ.get("SCHEDULER_AUTOSTART", "true").lower() in ("true", "1", "yes")
    if autostart:
        start_scheduler()
    yield
    stop_scheduler()


# ============================================================
# FastAPI App Initialization
# ============================================================

app = FastAPI(
    title="Big Data Hybrid Pipeline Unified API",
    description=(
        "**Al-Razi University | Big Data Practical Course — Final Project**\n\n"
        "Unified REST API providing automated ingestion, indexed analytical queries, "
        "live aggregation reports, incrementally refreshed Materialized Views, and background scheduled jobs."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request / Response Schemas
# ============================================================

class IngestRequest(BaseModel):
    file_path: Optional[str] = Field(
        None,
        description="Path to CSV dataset. If omitted, uses default sample in data/samples/.",
        json_schema_extra={"example": "data/samples/orders_sample_10k.csv"},
    )
    reset: bool = Field(
        False,
        description="If True, clears collections before loading. Default False preserves history.",
        json_schema_extra={"example": False},
    )


# ============================================================
# Root Redirect to Swagger Documentation
# ============================================================

@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    """Redirects base URL to interactive Swagger UI documentation."""
    return RedirectResponse(url="/docs")


# ============================================================
# 1. Health Check
# ============================================================

@app.get(
    "/health",
    tags=["1. System & Health"],
    summary="System Health and Status Check",
    description="Checks MongoDB connection, collection document counts, and scheduler status.",
)
def get_health() -> dict[str, Any]:
    try:
        db = get_db()
        db.command("ping")
        mongo_status = "CONNECTED"
    except Exception as exc:
        mongo_status = f"ERROR: {exc}"

    scheduler = get_scheduler()
    scheduler_status = "RUNNING" if scheduler.running else "STOPPED"

    counts: dict[str, int] = {}
    if mongo_status == "CONNECTED":
        counts = {
            "orders_raw": db[RAW_COLLECTION].count_documents({}),
            "orders_validated": db[VALIDATED_COLLECTION].count_documents({}),
            "orders_quarantine": db[QUARANTINE_COLLECTION].count_documents({}),
            "order_items_flat": db[COL_ORDER_ITEMS_FLAT].count_documents({}),
            "daily_sales_summary": db[COL_DAILY_SALES].count_documents({}),
            "top_products_summary": db[COL_TOP_PRODUCTS].count_documents({}),
            "job_runs": db[COL_JOB_RUNS].count_documents({}),
        }

    return {
        "status": "UP",
        "timestamp": utc_now_iso(),
        "database": {
            "name": MONGO_DATABASE,
            "status": mongo_status,
            "counts": counts,
        },
        "scheduler": {
            "status": scheduler_status,
        },
    }


# ============================================================
# 2. Ingestion Trigger
# ============================================================

@app.post(
    "/ingest",
    tags=["2. Data Ingestion"],
    summary="Trigger Data Ingestion ELT Pipeline",
    description="Executes the hybrid ELT pipeline (Python batch or PySpark), cleaning, classification, and upsert.",
)
def post_ingest(payload: Optional[IngestRequest] = None) -> dict[str, Any]:
    req = payload or IngestRequest()
    file_path = req.file_path

    # Dynamically resolve default file path if not provided
    if not file_path:
        sample_10k = PROJECT_ROOT / "data" / "samples" / "orders_sample_10k.csv"
        sample_5k = PROJECT_ROOT / "data" / "samples" / "orders_sample_5k.csv"
        raw_csv = PROJECT_ROOT / "data" / "raw" / "orders_messy.csv"

        if sample_10k.exists():
            file_path = str(sample_10k)
        elif sample_5k.exists():
            file_path = str(sample_5k)
        elif raw_csv.exists():
            file_path = str(raw_csv)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No CSV dataset found. Please specify file_path in request body.",
            )

    try:
        metrics = run_elt_pipeline(file_path=file_path, reset=req.reset)
        return {
            "status": "SUCCESS",
            "message": "ELT pipeline execution completed successfully.",
            "metrics": metrics,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(exc)}",
        )


# ============================================================
# 3. Index Management
# ============================================================

@app.post(
    "/indexes",
    tags=["3. Indexes & Optimization"],
    summary="Build and Ensure MongoDB Indexes",
    description="Creates dedicated compound and multikey indexes for query acceleration and materialized views.",
)
def post_indexes() -> dict[str, Any]:
    db = get_db()
    idx_results = ensure_indexes(db)
    ensure_mv_indexes(db)
    return {
        "status": "SUCCESS",
        "message": "Indexes verified and created successfully.",
        "indexes": idx_results,
    }


# ============================================================
# 4. List Analytical Queries
# ============================================================

@app.get(
    "/queries",
    tags=["4. Analytical Queries"],
    summary="List Available Analytical Queries",
    description="Returns registry of the 5 standard analytical queries with parameter specifications.",
)
def get_queries() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.params,
        }
        for spec in QUERIES.values()
    ]


# ============================================================
# 5. Run Analytical Query
# ============================================================

@app.get(
    "/queries/{name}",
    tags=["4. Analytical Queries"],
    summary="Execute Specific Analytical Query",
    description="Runs analytical query by name with optional query string filters (e.g. limit, customer_id, status).",
)
def get_query_by_name(name: str, request: Request) -> dict[str, Any]:
    try:
        params = dict(request.query_params)
        return run_query(name=name, params=params)
    except QueryNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{str(exc)}. Available: {list(QUERIES.keys())}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution error: {str(exc)}",
        )


# ============================================================
# 6. List Aggregation Reports
# ============================================================

@app.get(
    "/aggregations",
    tags=["5. Aggregations & Analytics"],
    summary="List Available Aggregation Reports",
    description="Returns catalog of pre-configured MongoDB Aggregation Pipeline reports.",
)
def get_aggregations() -> list[dict[str, Any]]:
    return list_aggregations()


# ============================================================
# 7. Run Aggregation Report
# ============================================================

@app.get(
    "/aggregations/{name}",
    tags=["5. Aggregations & Analytics"],
    summary="Execute Specific Aggregation Report",
    description="Executes aggregation report by name (e.g. sales_by_city, top_products, top_customers, sales_by_period).",
)
def get_aggregation_by_name(name: str, request: Request) -> dict[str, Any]:
    try:
        params = dict(request.query_params)
        return execute_aggregation(name=name, params=params)
    except AggregationNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{str(exc)}. Available: {[a['name'] for a in list_aggregations()]}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Aggregation execution error: {str(exc)}",
        )


# ============================================================
# 8. Refresh Materialized Views
# ============================================================

@app.post(
    "/refresh-mv",
    tags=["6. Materialized Views"],
    summary="Refresh Materialized Views",
    description="Performs incremental partition refresh of daily_sales_summary and top_products_summary (or full refresh if ?full=true).",
)
def post_refresh_mv(
    full: bool = Query(
        False,
        description="If True, forces full rebuild of all materialized views instead of incremental partition refresh.",
    )
) -> dict[str, Any]:
    try:
        report = refresh_materialized_views(full=full)
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Materialized view refresh failed: {str(exc)}",
        )


# ============================================================
# 9. List Jobs & History
# ============================================================

@app.get(
    "/jobs",
    tags=["7. Background Scheduled Jobs"],
    summary="List Scheduled Jobs and Execution History",
    description="Returns list of registered background jobs, their schedule, and recent audit logs from job_runs.",
)
def get_jobs(
    limit: int = Query(20, description="Max audit log entries to return", ge=1, le=100)
) -> dict[str, Any]:
    return {
        "registered_jobs": list_registered_jobs(),
        "recent_runs": get_job_runs(limit=limit),
    }


# ============================================================
# 10. Run Job On-Demand
# ============================================================

@app.post(
    "/jobs/{name}/run",
    tags=["7. Background Scheduled Jobs"],
    summary="Trigger Specific Job Immediately",
    description="Triggers on-demand execution of a background job (e.g. refresh_materialized_views or pipeline_consistency_audit) and logs to job_runs.",
)
def post_job_run(name: str) -> dict[str, Any]:
    try:
        log_entry = run_job_now(job_name=name, trigger_type="manual")
        return {
            "status": "SUCCESS",
            "message": f"Job '{name}' executed successfully.",
            "execution": log_entry,
        }
    except KeyError as exc:
        registered = [j["name"] for j in list_registered_jobs()]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{name}' not found. Available jobs: {registered}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job execution failed: {str(exc)}",
        )
