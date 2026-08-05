#!/usr/bin/env python3
"""Run unit tests with coverage and report against the 90% target."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run unit tests with coverage and check against a target percentage."
    )
    parser.add_argument(
        "--target",
        type=int,
        default=90,
        metavar="N",
        help="Coverage percentage target (default: 90)",
    )
    return parser.parse_args()


def parse_coverage_percentage(output: str) -> int | None:
    """Extract the TOTAL coverage percentage from pytest-cov output."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("TOTAL"):
            parts = stripped.split()
            # pytest-cov TOTAL line: TOTAL  <stmts> <miss> <cover>%
            for part in reversed(parts):
                if part.endswith("%"):
                    try:
                        return int(part.rstrip("%"))
                    except ValueError:
                        pass
    return None


def main() -> int:
    args = parse_args()
    target = args.target

    tests_dir = Path(__file__).parent.parent / "tests" / "unit"
    if not tests_dir.exists():
        print(
            f"[coverage_report] SKIP: tests/unit/ not found — unit test infrastructure not yet installed.",
            file=sys.stderr,
        )
        return 0

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/",
            "--cov=scripts",
            "--cov-report=term-missing",
            "-q",
        ],
        capture_output=True,
        text=True,
    )

    combined = result.stdout + result.stderr
    print(combined, end="")

    coverage = parse_coverage_percentage(combined)

    if coverage is None:
        print(
            f"[coverage_report] ERROR: could not parse coverage percentage from output.",
            file=sys.stderr,
        )
        return 1

    print(f"\nCoverage: {coverage}% (target: {target}%)")

    if coverage >= target:
        return 0
    else:
        print(
            f"[coverage_report] FAIL: coverage {coverage}% is below target {target}%.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
