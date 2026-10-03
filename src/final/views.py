"""
views.py — Materialized View management for Final Project.

Responsible for computing and persisting aggregated results into:
  - daily_sales_summary
  - top_products_summary
  - order_items_flat

Incremental MV design (as documented in docs/FINAL_PROJECT_NOTES.md):
  - No true watermark exists: upsert overwrites metadata.processed_at.
  - Tracking mechanism: mv_state collection stores run_id → doc_count per MV.
  - A refresh detects runs whose current count differs from the stored snapshot,
    then RECOMPUTES ONLY THE AFFECTED PARTITIONS (days / skus) and replaces them.
  - Never use $inc for incremental updates — always full partition replacement.

This module will be fully implemented in a later step.
"""
