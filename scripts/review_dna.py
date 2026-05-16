"""Generate a project-specific Review DNA profile.

Usage:
    python scripts/review_dna.py scan --json
    python scripts/review_dna.py init
    python scripts/review_dna.py instructions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.review_dna import (  # noqa: E402
    build_review_dna_profile,
    load_review_dna_profile,
    profile_to_json,
    render_review_dna_instructions,
    render_review_dna_summary,
    write_review_dna_profile,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            profile = build_review_dna_profile(args.repo)
            if args.json:
                print(profile_to_json(profile), end="")
            else:
                print(render_review_dna_summary(profile))
            return 0

        if args.command == "init":
            repo_path = Path(args.repo).expanduser().resolve()
            output_path = args.output or (repo_path / "review-dna.yml")
            profile = build_review_dna_profile(repo_path)
            written_path = write_review_dna_profile(
                profile,
                output_path,
                force=args.force,
            )
            print(f"Wrote {written_path}")
            return 0

        if args.command == "instructions":
            if args.profile is not None:
                profile = load_review_dna_profile(args.profile)
            else:
                profile = build_review_dna_profile(args.repo)
            print(render_review_dna_instructions(profile))
            return 0

    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Review DNA for deterministic project-specific review."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a repository and print its Review DNA profile.",
    )
    scan_parser.add_argument(
        "--repo",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository path to scan.",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )

    init_parser = subparsers.add_parser(
        "init",
        help="Write review-dna.yml for a repository.",
    )
    init_parser.add_argument(
        "--repo",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository path to scan.",
    )
    init_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path. Defaults to review-dna.yml inside the repo.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output file.",
    )

    instructions_parser = subparsers.add_parser(
        "instructions",
        help="Render reviewer-ready Markdown instructions.",
    )
    instructions_parser.add_argument(
        "--repo",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository path to scan when --profile is not provided.",
    )
    instructions_parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Existing Review DNA profile file to render.",
    )

    return parser


if __name__ == "__main__":
    raise SystemExit(main())

