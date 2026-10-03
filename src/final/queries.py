"""
queries.py — find()-style filtered and sorted lookups on Final Project collections.

Queries differ from aggregations: they use find() / find_one() with filters,
projections, and sort — NOT $group pipelines.

Examples of queries to implement:
  - orders by customer_id
  - orders in a date range
  - orders by status / payment_status
  - top-N from daily_sales_summary materialized view
  - lookup order_items_flat by sku

This module will be fully implemented in a later step.
"""
