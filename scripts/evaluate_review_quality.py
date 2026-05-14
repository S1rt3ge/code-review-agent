"""Run deterministic review quality evals.

Usage:
    python scripts/evaluate_review_quality.py
    python scripts/evaluate_review_quality.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.review_eval import (  # noqa: E402
    format_review_eval_report,
    load_eval_cases,
    run_review_quality_eval,
)

DEFAULT_CASES_PATH = PROJECT_ROOT / "evals" / "review_quality_cases.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic quality evals for the local review analyzer."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Path to review quality eval cases JSON.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report.",
    )
    args = parser.parse_args(argv)

    try:
        cases = load_eval_cases(args.cases)
        report = run_review_quality_eval(cases)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_review_eval_report(report))

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
