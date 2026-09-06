# 🏛️ Technical Architecture & Pipeline Design Document

## 1. Executive Architecture Overview

This document specifies the technical design, architectural patterns, and hardware-software optimization strategies applied in the **Big Data Hybrid ELT Data Pipeline** for processing 30,000,000+ e-commerce records.

The pipeline processes massive raw transaction files characterized by mixed quality, corrupted records, non-standard character encodings, and Arabic/Persian numeric and textual inputs.

---

## 2. Architectural Principles

### 2.1 Pure ELT (Extract - Load - Transform) Strategy
Unlike traditional ETL architectures where unparseable or dirty records are dropped at the extraction stage, this pipeline employs a strict **Pure ELT pattern**:
1. **100% Raw Ingestion**: Every single byte from the source CSV is ingested into MongoDB `orders_raw` with associated audit metadata (`run_id`, `source_file`, `source_row_number`, `ingested_at`, `engine_used`).
2. **Immutable Raw Storage**: `orders_raw` acts as an append-only historical data lake, preserving original dirty records for retrospective analysis or algorithm improvements.
3. **Decoupled Transformations**: Cleaning, business validation, and classification are performed downstream using the raw collection as a reliable source of truth.

---

## 3. Hybrid Engine Routing & Execution Mechanics

The system features an automated **File Router** ([src/file_router.py](file:///m:/H.W.BigData0v.0.1%20-%20Copy/src/file_router.py)) that inspects file metadata to choose the optimal compute engine:

```mermaid
graph TD
    A[Input File Discovery] --> B{Size <= 200 MB?}
    B -->|Yes| C[Python Streaming Loader]
    B -->|No| D[PySpark Distributed Loader]
    C --> E[Sequential Generator Stream]
    E --> F[MongoDB Bulk Write (Batch Size: 1000)]
    D --> G[Spark Distributed DataFrame Reader]
    G --> H[Partition Distribution foreachPartition]
    H --> F
```

### 3.1 Python Streaming Engine ($\le 200\text{ MB}$)
* **Design**: Uses Python's native `csv` streaming reader with constant $O(1)$ memory consumption.
* **Mechanism**: Bounded generator that yields records in chunks of `BATCH_SIZE = 1000`.
* **Throughput**: $\sim 3,417\text{ rows/sec}$.

### 3.2 PySpark Distributed Engine ($> 200\text{ MB}$)
* **Engine Architecture**: Configured with local multi-threading, custom garbage collection tuning, and off-heap memory management to reliably process a 12.65 GB CSV file:
  * **Driver / Executor Memory**: 8 GB each.
  * **Off-Heap Storage**: 2 GB (`spark.memory.offHeap.enabled = true`).
  * **Network Timeout**: 800 seconds (`spark.network.timeout`).
  * **CSV Escaping**: RFC-4180 strict quotes (`escape="\""`).
  * **Parallel Sinks**: Parallel writes across Spark partitions into MongoDB via `foreachPartition`.
* **Throughput**: $\sim 3,549.77\text{ rows/sec}$.

---

## 4. Database Schema & Indexing Architecture

The MongoDB instance (`midterm_data_pipeline`) is partitioned into three functional tiers:

### 4.1 `orders_raw` (Tier 1: Bronze / Raw Layer)
* Contains original uncleaned records.
* Indexed by `metadata.run_id` for efficient downstream batch processing.

```json
{
  "_id": ObjectId("..."),
  "metadata": {
    "run_id": "a49919a5c7a847789615ec3194f4b9d7",
    "source_file": "orders_huge_mixed_quality.csv",
    "source_row_number": null,
    "ingested_at": "2026-09-05T23:30:44Z",
    "engine_used": "pyspark"
  },
  "source_data": {
    "order_id": "ORD-0001",
    "delivery_cost": "ألفان",
    "payment_amount": "54000.00 ريال",
    "status": "مدفوع",
    "customer_email": "user@@example..com"
  }
}
```

### 4.2 `orders_validated` (Tier 2: Silver / Curated Layer)
* Contains all verified clean records (`VALID`) and auto-repaired records (`CORRECTED`).
* **Unique Compound Index**: Enforced on `order_id` to guarantee idempotency:
  ```javascript
  db.orders_validated.createIndex({ "order_id": 1 }, { unique: true, name: "idx_val_order_id_unique" })
  ```

### 4.3 `orders_quarantine` (Tier 3: Defect & Quarantine Layer)
* Stores corrupted, incomplete, or unrepairable records.
* Records the specific diagnostic reasons: `MISSING_ORDER_ID`, `CORRUPTED_ITEMS_JSON`, `EMPTY_ITEMS`, etc.

---

## 5. Mathematical Invariance & Idempotency Guarantee

### 5.1 The Mathematical Consistency Rule
Every pipeline execution must satisfy the conservation theorem:
$$\text{Raw Count} = \text{Valid Count} + \text{Corrected Count} + \text{Quarantine Count}$$

For the 30 Million records run:
$$30,000,000 = 24,312,892 + 4,217,450 + 1,469,658$$
$$\text{Difference} = 0 \quad (\text{Consistency: PASSED})$$

### 5.2 Idempotent Upsert Mathematical Model
When processing an order $O_i$, the database operation $f(O_i)$ satisfies:
$$f(f(O_i)) = f(O_i)$$
Re-executing the pipeline multiple times will modify existing documents rather than inserting duplicate records, maintaining a stable count of unique validated business entities.
