# Architecture & Pipeline Design Documentation

## Overview

This project implements a production-ready **ELT Data Pipeline** for Big Data processing (Lecture 5 Homework & Midterm Project).
The pipeline ingests raw, dirty e-commerce order records from CSV files into **MongoDB**, cleans and transforms the data using deterministic rules, logs audit trails for all modifications, and classifies records into validated vs quarantine collections.


---

##  Data Quality Rules & Audit Trail

| Rule Code | Description | Example Transformation |
| :--- | :--- | :--- |
| `R1_NORMALIZE_DIGITS` | Normalize Eastern Arabic / Persian digits | `'٧٠٦٠٠٠٫٠'` $\rightarrow$ `'706000.0'` |
| `R2_REMOVE_THOUSANDS_SEPARATOR` | Remove commas in numbers | `'135,000.00'` $\rightarrow$ `'135000.00'` |
| `R3_STRIP_CURRENCY_TEXT` | Strip currency suffixes / symbols | `'54000.00 ريال'` $\rightarrow$ `'54000.00'` |
| `R4_ARABIC_WORDS_CONVERSION` | Convert Arabic number words | `'ألفان'` $\rightarrow$ `'2000.0'` |
| `R5_ABS_NEGATIVE_VALUE` | Convert negative monetary amounts | `'-21500.0'` $\rightarrow$ `'21500.0'` |
| `R6_CURRENCY_NORMALIZATION` | Standardize currency codes | `'ريال يمني'` $\rightarrow$ `'YER'` |
| `R7_STATUS_NORMALIZATION` | Standardize status strings | `'مدفوع'` $\rightarrow$ `'تم الدفع'` |
| `R8_CONTACT_FORMAT_CLEANING` | Clean double `@` / double dots | `'user@@example..com'` $\rightarrow$ `'user@example.com'` |

---

## Mandatory Mathematical Consistency Rule

Every pipeline run verifies the following formula:

$$\text{run\_raw\_count} = \text{run\_valid\_count} + \text{run\_corrected\_count} + \text{run\_quarantine\_count}$$

The result of this check is exported to `reports/results.json` and `reports/results.md`.
