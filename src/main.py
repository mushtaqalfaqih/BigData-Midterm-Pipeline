import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import SAMPLE_INPUT_FILE
from src.elt_pipeline import run_elt_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Big Data Midterm ELT Data Pipeline"
    )
    parser.add_argument(
        "--file-path",
        type=str,
        default=str(SAMPLE_INPUT_FILE),
        help="Path to the input CSV file (default: data/samples/orders_sample_10k.csv)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        default=False,
        help=(
            "Skip dropping collections before the run (incremental mode). "
            "Default behaviour (reset=True) is preserved when this flag is absent."
        ),
    )

    args = parser.parse_args()

    input_path = Path(args.file_path)

    if not input_path.exists():
        print(f"Error: Specified input file does not exist: {input_path}")
        sys.exit(1)

    run_elt_pipeline(str(input_path), reset=not args.no_reset)


if __name__ == "__main__":
    main()