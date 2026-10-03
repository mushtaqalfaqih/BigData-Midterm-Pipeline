"""
jobs.py — Scheduled and on-demand refresh jobs for Final Project.

Uses APScheduler (BackgroundScheduler) to periodically refresh materialized views.
Each job execution is logged to the job_runs collection via common.COL_JOB_RUNS.

Planned jobs:
  - refresh_all_views(): triggers views.materializer for all MVs.
  - refresh_daily_sales(): partial refresh for daily_sales_summary only.
  - refresh_top_products(): partial refresh for top_products_summary only.

Scheduler is enabled/disabled via the SCHEDULER_ENABLED env var.

This module will be fully implemented in a later step.
"""
