#!/usr/bin/env python3
"""
scripts/make_dev_slice.py
Extracts a development slice from a large CSV dataset.
Reads the source using Python's standard csv module (utf-8, newline='')
and writes the header plus the first N data rows.
"""

import argparse
import csv
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Extract a slice of N rows from a CSV file preserving header and encoding."
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Path to the input CSV file",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Path to the output sliced CSV file",
    )
    parser.add_argument(
        "--rows",
        type=int,
        required=True,
        help="Number of data rows to extract (excluding header)",
    )

    args = parser.parse_args()

    source_path = Path(args.source)
    out_path = Path(args.out)
    rows_limit = args.rows

    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    if rows_limit <= 0:
        print(f"Error: --rows must be greater than 0, got {rows_limit}", file=sys.stderr)
        sys.exit(1)

    # Ensure parent output directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading from: {source_path}")
    print(f"Writing to:   {out_path}")
    print(f"Target rows:  {rows_limit:,}")

    rows_written = 0
    with open(source_path, mode="r", encoding="utf-8", newline="") as fin:
        reader = csv.reader(fin)
        header = next(reader, None)
        if header is None:
            print("Error: Source file is empty.", file=sys.stderr)
            sys.exit(1)

        with open(out_path, mode="w", encoding="utf-8", newline="") as fout:
            writer = csv.writer(fout)
            writer.writerow(header)

            for row in reader:
                writer.writerow(row)
                rows_written += 1
                if rows_written >= rows_limit:
                    break

    size_bytes = os.path.getsize(out_path)
    size_mb = size_bytes / (1024 * 1024)

    print(f"Extraction complete.")
    print(f"Rows written: {rows_written:,}")
    print(f"Output size:  {size_mb:.2f} MB ({size_bytes:,} bytes)")


if __name__ == "__main__":
    main()
