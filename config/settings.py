import os
from pathlib import Path

# ============================================================
# Load .env file if python-dotenv is installed (silent if not)
# ============================================================
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass


# ============================================================
# Project Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SAMPLES_DIR = DATA_DIR / "samples"

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(PROJECT_ROOT / "reports")))


# ============================================================
# Input Files
# ============================================================

LARGE_INPUT_FILE = RAW_DATA_DIR / "orders_huge_mixed_quality.csv"

SAMPLE_INPUT_FILE = SAMPLES_DIR / "orders_sample_10k.csv"


# ============================================================
# File Router
# ============================================================

# Files <= this size will use Python Batch.
# Files > this size will use PySpark.
SMALL_FILE_THRESHOLD_MB = 200


# ============================================================
# Python Batch
# ============================================================

BATCH_SIZE = 1000


# ============================================================
# MongoDB  (override via env vars or .env file)
# ============================================================

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

MONGO_DATABASE = os.getenv("MONGO_DATABASE", "midterm_data_pipeline")

RAW_COLLECTION = "orders_raw"
VALIDATED_COLLECTION = "orders_validated"
QUARANTINE_COLLECTION = "orders_quarantine"
