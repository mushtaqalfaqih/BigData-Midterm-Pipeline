# Pipeline Execution Summary Report

- **Run ID**: `a49919a5c7a847789615ec3194f4b9d7`
- **Timestamp**: `2026-09-05T23:30:44Z`
- **Input File**: `orders_huge_mixed_quality.csv` (12650.32 MB)
- **Engine Used**: `pyspark`

---

## ⚡ Performance Metrics
- **Elapsed Time**: `8451.256 s`
- **Throughput**: `3549.77 rows/s`

---

## 📊 Classification Statistics
| Category | Count | Percentage |
| :--- | :--- | :--- |
| **Raw Loaded (`run_raw_count`)** | `30,000,000` | 100.0% |
| **Valid (`run_valid_count`)** | `24,312,892` | `81.04%` |
| **Corrected (`run_corrected_count`)** | `4,217,450` | `14.06%` |
| **Quarantine (`run_quarantine_count`)** | `1,469,658` | `4.90%` |

---

## 🔒 Consistency Check
- **Formula**: `run_raw_count == run_valid_count + run_corrected_count + run_quarantine_count`
- **Status**: `PASSED ✅`
- **Raw Count**: `30,000,000`
- **Classified Sum**: `30,000,000`
