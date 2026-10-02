"""Command-line evaluation of the tissue-niche agent comparison."""

import argparse
from pathlib import Path

from .evaluation import evaluate_study


def main() -> None:
    """Evaluate the saved study without model calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", required=True, type=Path)
    args = parser.parse_args()
    print(evaluate_study(args.study_dir).to_string(index=False))


if __name__ == "__main__":
    main()
