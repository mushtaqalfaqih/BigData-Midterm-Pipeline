#!/usr/bin/env python3
"""
create_small_sample.py — Root-level entry point for creating reproducible samples.
Delegates to src.create_small_sample.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.create_small_sample import main

if __name__ == "__main__":
    main()
