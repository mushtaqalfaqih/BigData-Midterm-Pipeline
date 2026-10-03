"""
aggregations.py — $group-based aggregation pipeline reports for Final Project.

Aggregations differ from queries: they run multi-stage MongoDB aggregation pipelines
that group, sum, count, and reshape data.

Examples of aggregations to implement:
  - daily revenue summary (group by day_expr(order_date))
  - top products by revenue / quantity (after exploding items_json)
  - revenue by payment_method / delivery_type / city
  - quarantine reason distribution

All pipelines must use num_expr() from common.py for string→double coercion.
All pipelines must include a $limit stage to avoid unbounded scans.

This module will be fully implemented in a later step.
"""
