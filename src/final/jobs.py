"""
jobs.py — Scheduled Jobs and Audit Logging for Final Project.

Provides:
  - BackgroundScheduler using APScheduler.
  - Job 1: refresh_materialized_views_job (Periodic partition-based refresh of MVs).
  - Job 2: pipeline_consistency_audit_job (Data quality and collection alignment audit).
  - On-demand execution capability (run_job_now) callable via FastAPI or CLI.
  - Audit logging to job_runs collection (started_at, finished_at, duration_seconds, status, details).
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pymongo.database import Database

from src.final.common import (
    COL_JOB_RUNS,
    COL_QUARANTINE,
    COL_RAW,
    COL_VALIDATED,
    get_db,
    utc_now_iso,
)
from src.final.views import refresh_materialized_views

logger = logging.getLogger("pipeline.jobs")

_scheduler: BackgroundScheduler | None = None


# ============================================================
# Core Job Implementations
# ============================================================

def job_refresh_materialized_views(db: Database) -> dict[str, Any]:
    """Execute incremental refresh of materialized views."""
    return refresh_materialized_views(db=db, full=False)


def job_pipeline_consistency_audit(db: Database) -> dict[str, Any]:
    """Audit mathematical consistency and data health between raw, validated, and quarantine."""
    raw_col = db[COL_RAW]
    val_col = db[COL_VALIDATED]
    quar_col = db[COL_QUARANTINE]

    total_raw = raw_col.count_documents({})
    total_val = val_col.count_documents({})
    total_quar = quar_col.count_documents({})

    # Check distinct runs
    runs_in_val = set(val_col.distinct("metadata.run_id"))
    runs_in_quar = set(quar_col.distinct("metadata.run_id"))
    all_runs = sorted(list(runs_in_val | runs_in_quar))

    # Distinct order_ids in raw
    distinct_raw_orders = len(raw_col.distinct("source_data.order_id"))
    duplicate_raw_orders = max(0, total_raw - distinct_raw_orders)

    # In an ELT pipeline with idempotent upserts, the collection counts satisfy:
    # unique_validated + quarantine <= total_raw (with equality holding on raw rows processed)
    # The pipeline log also tracks exact valid + corrected + quarantine == raw
    is_consistent = (total_val + total_quar <= total_raw) and (total_raw > 0)

    return {
        "is_consistent": is_consistent,
        "total_raw": total_raw,
        "total_validated": total_val,
        "total_quarantine": total_quar,
        "duplicate_raw_orders": duplicate_raw_orders,
        "effective_unique_raw": distinct_raw_orders,
        "classified_sum": total_val + total_quar,
        "active_runs_count": len(all_runs),
        "audit_passed": is_consistent,
        "note": "Validated collection holds deduplicated unique order entities via idempotent upsert."
    }


# ============================================================
# Job Registry
# ============================================================

JOB_REGISTRY: dict[str, dict[str, Any]] = {
    "refresh_materialized_views": {
        "name": "refresh_materialized_views",
        "title": "Materialized Views Incremental Refresh",
        "description": "Periodically inspects orders_validated and updates daily_sales_summary & top_products_summary partitions.",
        "interval_minutes": 15,
        "handler": job_refresh_materialized_views,
    },
    "pipeline_consistency_audit": {
        "name": "pipeline_consistency_audit",
        "title": "Pipeline Mathematical Consistency Audit",
        "description": "Verifies data integrity and consistency between raw, validated, and quarantine collections.",
        "interval_minutes": 30,
        "handler": job_pipeline_consistency_audit,
    },
}


# ============================================================
# Execution & Audit Logging Engine
# ============================================================

def run_job_now(
    job_name: str,
    trigger_type: str = "manual",
    db: Database | None = None,
) -> dict[str, Any]:
    """
    Execute a registered job immediately and record its audit log in job_runs.

    Args:
        job_name: Name of job in JOB_REGISTRY.
        trigger_type: 'manual' or 'scheduled'.
        db: Optional database instance.

    Returns:
        dict: The audit record stored in job_runs collection.
    """
    if job_name not in JOB_REGISTRY:
        raise KeyError(
            f"Job '{job_name}' not found. Available jobs: {list(JOB_REGISTRY.keys())}"
        )

    if db is None:
        db = get_db()

    job_info = JOB_REGISTRY[job_name]
    run_uuid = uuid.uuid4().hex
    started_at = utc_now_iso()
    t0 = time.perf_counter()

    status = "SUCCESS"
    details: Any = None
    error_message: str | None = None

    try:
        details = job_info["handler"](db)
    except Exception as exc:
        status = "FAILED"
        error_message = str(exc)
        details = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        logger.error(f"Job {job_name} failed: {exc}", exc_info=True)

    finished_at = utc_now_iso()
    duration_seconds = round(time.perf_counter() - t0, 3)

    log_entry: dict[str, Any] = {
        "_id": run_uuid,
        "run_id": run_uuid,
        "job_name": job_name,
        "title": job_info["title"],
        "trigger": trigger_type,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "details": details,
        "error": error_message,
    }

    # Store audit in job_runs collection
    db[COL_JOB_RUNS].insert_one(dict(log_entry))

    # Return clean json-friendly copy
    clean_entry = dict(log_entry)
    clean_entry.pop("_id", None)
    return clean_entry


# ============================================================
# Scheduler Control
# ============================================================

def get_scheduler() -> BackgroundScheduler:
    """Return the global BackgroundScheduler instance, initializing if needed."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
        # Register jobs
        for job_name, spec in JOB_REGISTRY.items():
            _scheduler.add_job(
                func=_scheduled_job_wrapper,
                trigger=IntervalTrigger(minutes=spec["interval_minutes"]),
                args=[job_name],
                id=job_name,
                name=spec["title"],
                replace_existing=True,
            )
    return _scheduler


def _scheduled_job_wrapper(job_name: str) -> None:
    """Internal wrapper invoked by APScheduler trigger."""
    try:
        run_job_now(job_name=job_name, trigger_type="scheduled")
    except Exception as exc:
        logger.error(f"Scheduled job wrapper error for {job_name}: {exc}")


def start_scheduler() -> None:
    """Start APScheduler in background if not already running."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler background service started successfully.")


def stop_scheduler() -> None:
    """Gracefully shutdown APScheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler background service stopped.")


def list_registered_jobs() -> list[dict[str, Any]]:
    """Return catalog of registered jobs and their schedule configuration."""
    scheduler = get_scheduler()
    results = []

    for name, spec in JOB_REGISTRY.items():
        job_obj = scheduler.get_job(name) if scheduler.running else None
        next_run = job_obj.next_run_time.isoformat() if job_obj and job_obj.next_run_time else None

        results.append(
            {
                "name": name,
                "title": spec["title"],
                "description": spec["description"],
                "interval_minutes": spec["interval_minutes"],
                "next_run_time": next_run,
                "status": "RUNNING" if (scheduler.running and job_obj) else "SCHEDULED",
            }
        )
    return results


def get_job_runs(
    db: Database | None = None,
    limit: int = 20,
    job_name: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch recent execution audit logs from job_runs collection."""
    if db is None:
        db = get_db()

    query_filter: dict[str, Any] = {}
    if job_name:
        query_filter["job_name"] = job_name

    cursor = db[COL_JOB_RUNS].find(query_filter, {"_id": 0}).sort("started_at", -1).limit(limit)
    return list(cursor)
