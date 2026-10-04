# Pipeline Execution Summary Report

- **Run ID**: `2a02f9cfcdc94753ada1fb2484e15cd2`
- **Timestamp**: `2026-10-04T23:11:52Z`
- **Input File**: `orders_sample_10k.csv` (4.17 MB)
- **Engine Used**: `python_batch`

---

## ⚡ Performance Metrics
- **Elapsed Time**: `2.853 s`
- **Throughput**: `3505.36 rows/s`

---

## 📊 Classification Statistics
| Category | Count | Percentage |
| :--- | :--- | :--- |
| **Raw Loaded (`run_raw_count`)** | `10,000` | 100.0% |
| **Valid (`run_valid_count`)** | `8,133` | `81.33%` |
| **Corrected (`run_corrected_count`)** | `1,359` | `13.59%` |
| **Quarantine (`run_quarantine_count`)** | `508` | `5.08%` |

---

## 🔒 Consistency Check
- **Formula**: `run_raw_count == run_valid_count + run_corrected_count + run_quarantine_count`
- **Status**: `PASSED ✅`
- **Raw Count**: `10,000`
- **Classified Sum**: `10,000`
