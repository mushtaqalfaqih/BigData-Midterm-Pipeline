"""
api.py — FastAPI REST API entry point for Final Project.

Planned routes (exact names from assignment):
  POST /ingest                → calls run_elt_pipeline(reset=False)
  GET  /analytics/daily-sales → queries daily_sales_summary MV
  GET  /analytics/top-products→ queries top_products_summary MV
  GET  /analytics/orders      → filtered find() on orders_validated
  POST /views/refresh         → triggers materialized view refresh
  GET  /health                → liveness check

See src/final/api/ sub-package for route modules (to be created in a later step).

This module will be fully implemented in a later step.
"""
