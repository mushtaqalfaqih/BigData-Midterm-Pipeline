"""
test_jobs.py — Tests for Scheduled Jobs and Job Runs Audit Logging.
"""

import pytest
from src.final.common import COL_JOB_RUNS, get_db
from src.final.jobs import (
    get_job_runs,
    list_registered_jobs,
    run_job_now,
)


def test_list_registered_jobs():
    jobs = list_registered_jobs()
    assert len(jobs) >= 2
    names = [j["name"] for j in jobs]
    assert "refresh_materialized_views" in names
    assert "pipeline_consistency_audit" in names


def test_run_refresh_materialized_views_job():
    log = run_job_now("refresh_materialized_views")
    assert log["job_name"] == "refresh_materialized_views"
    assert log["status"] == "SUCCESS"
    assert "duration_seconds" in log
    assert log["duration_seconds"] >= 0
    assert log["trigger"] == "manual"
    assert "run_id" in log


def test_run_pipeline_consistency_audit_job():
    log = run_job_now("pipeline_consistency_audit")
    assert log["job_name"] == "pipeline_consistency_audit"
    assert log["status"] == "SUCCESS"
    assert "details" in log
    assert "total_raw" in log["details"]
    assert "total_validated" in log["details"]


def test_job_runs_audit_persisted():
    db = get_db()
    runs = get_job_runs(limit=5)
    assert len(runs) > 0
    first = runs[0]
    assert "job_name" in first
    assert "status" in first
    assert "started_at" in first
    assert "finished_at" in first


def test_invalid_job_raises():
    with pytest.raises(KeyError):
        run_job_now("non_existent_job_1234")
