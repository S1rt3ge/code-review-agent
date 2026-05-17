"""Generate a project-specific Review DNA profile.

Usage:
    python scripts/review_dna.py scan --json
    python scripts/review_dna.py init
    python scripts/review_dna.py instructions
    python scripts/review_dna.py check --json
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
    detect_changed_files,
    load_review_dna_profile,
    profile_to_json,
    render_review_dna_instructions,
    render_review_dna_check_report,
    render_review_dna_summary,
    review_dna_check_to_json,
    run_review_dna_check,
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

        if args.command == "check":
            repo_path = Path(args.repo).expanduser().resolve()
            profile = _load_or_build_profile(repo_path, args.profile)
            changed_files = (
                args.changed_file
                if args.changed_file
                else detect_changed_files(repo_path)
            )
            result = run_review_dna_check(profile, changed_files=changed_files)
            if args.json:
                print(review_dna_check_to_json(result), end="")
            else:
                print(render_review_dna_check_report(result))
            return 0 if result.status == "PASS" else 1

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

    check_parser = subparsers.add_parser(
        "check",
        help="Check changed files against Review DNA project-fit rules.",
    )
    check_parser.add_argument(
        "--repo",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository path to check.",
    )
    check_parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Existing Review DNA profile file to use.",
    )
    check_parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path. Can be passed multiple times.",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )

    return parser


def _load_or_build_profile(repo_path: Path, profile_path: Path | None):
    if profile_path is not None:
        return load_review_dna_profile(profile_path)

    default_profile_path = repo_path / "review-dna.yml"
    if default_profile_path.is_file():
        return load_review_dna_profile(default_profile_path)

    return build_review_dna_profile(repo_path)


if __name__ == "__main__":
    raise SystemExit(main())
