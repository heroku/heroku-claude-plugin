#!/usr/bin/env python3
"""Build references/preferred-tools.json from references/preferred-tools.md.

The Markdown file is the only one engineers edit. The JSON is generated and read-only:
the agent's lookup reads it, so it must always be a pure function of the Markdown.

Markdown format: every `##` heading is a need, and its heading text is the need id. Text
before the first `##` is ignored. A need has a `Description:` line, an `Aliases:` line
(comma-separated) and a table with one row per stack.

  python3 scripts/build_tools_index.py            # regenerate the JSON
  python3 scripts/build_tools_index.py --check    # exit 1 if the JSON is out of date

Exit codes: 0 ok, 1 JSON out of date (--check), 2 invalid source. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REFERENCES_DIR = Path(__file__).parent.parent / "references"
DEFAULT_SOURCE = REFERENCES_DIR / "preferred-tools.md"
DEFAULT_OUTPUT = REFERENCES_DIR / "preferred-tools.json"

GENERATED_NOTE = (
    "Generated from preferred-tools.md by scripts/build_tools_index.py. Do not edit."
)

# stack -> the registry its packages must come from
STACK_REGISTRIES: dict[str, str] = {
    "go": "go",
    "node": "npm",
    "python": "pypi",
    "rails": "rubygems",
    "website": "npm",
}

COLUMNS = [
    "stack",
    "package",
    "registry",
    "version",
    "license",
    "link",
    "vetted_on",
    "approved_by",
]
HEADER_CELLS = [
    "Stack",
    "Package",
    "Registry",
    "Version",
    "License",
    "Link",
    "Vetted on",
    "Approved by",
]

NEED_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ToolsIndexError(ValueError):
    """The Markdown source is malformed."""


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_aliases(text: str) -> list[str]:
    return sorted({a.strip().lower() for a in text.split(",") if a.strip()})


def _parse_row(lineno: int, line: str) -> tuple[str, dict[str, str]]:
    cells = _cells(line)
    if len(cells) != len(COLUMNS):
        raise ToolsIndexError(
            f"line {lineno}: expected {len(COLUMNS)} columns, got {len(cells)}"
        )
    row = dict(zip(COLUMNS, cells, strict=True))
    for name, value in row.items():
        if not value:
            raise ToolsIndexError(f"line {lineno}: empty {name}")
    stack = row.pop("stack")
    if stack not in STACK_REGISTRIES:
        raise ToolsIndexError(f"line {lineno}: unknown stack {stack!r}")
    if row["registry"] != STACK_REGISTRIES[stack]:
        raise ToolsIndexError(
            f"line {lineno}: registry {row['registry']!r} does not match "
            f"stack {stack!r} "
            f"(expected {STACK_REGISTRIES[stack]!r})"
        )
    if not row["link"].startswith("https://"):
        raise ToolsIndexError(f"line {lineno}: link must be an https URL")
    try:
        if not DATE.match(row["vetted_on"]):
            raise ValueError
        datetime.strptime(row["vetted_on"], "%Y-%m-%d")
    except ValueError:
        raise ToolsIndexError(
            f"line {lineno}: invalid date {row['vetted_on']!r}, expected YYYY-MM-DD"
        ) from None
    return stack, row


def _parse_need(need_id: str, lineno: int, body: list[tuple[int, str]]) -> dict:
    if not NEED_ID.match(need_id):
        raise ToolsIndexError(
            f"line {lineno}: invalid need id {need_id!r} (use lowercase-hyphenated)"
        )
    description = aliases = None
    table: list[tuple[int, str]] = []
    for n, line in body:
        if line.startswith("Description:"):
            description = line.removeprefix("Description:").strip()
        elif line.startswith("Aliases:"):
            aliases = _parse_aliases(line.removeprefix("Aliases:"))
        elif line.startswith("|"):
            table.append((n, line))
    if not description:
        raise ToolsIndexError(f"line {lineno}: need {need_id!r} is missing Description")
    if aliases is None:
        raise ToolsIndexError(f"line {lineno}: need {need_id!r} is missing Aliases")
    if len(table) < 2:
        raise ToolsIndexError(f"line {lineno}: need {need_id!r} has no table")
    if _cells(table[0][1]) != HEADER_CELLS:
        raise ToolsIndexError(
            f"line {table[0][0]}: table header must be: | {' | '.join(HEADER_CELLS)} |"
        )
    tools: dict[str, dict[str, str]] = {}
    for n, line in table[2:]:  # table[1] is the |---| separator
        stack, row = _parse_row(n, line)
        if stack in tools:
            raise ToolsIndexError(
                f"line {n}: duplicate stack {stack!r} in need {need_id!r}"
            )
        tools[stack] = row
    return {"description": description, "aliases": aliases, "tools": tools}


def build_index(text: str) -> dict:
    """Parse the Markdown source into the index structure. Raises ToolsIndexError."""
    sections: list[tuple[str, int, list[tuple[int, str]]]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            sections.append((line[3:].strip(), n, []))
        elif sections:
            sections[-1][2].append((n, line.rstrip()))
    if not sections:
        raise ToolsIndexError("no needs found (expected '## <need-id>' headings)")

    needs: dict[str, dict] = {}
    alias_owner: dict[str, str] = {}
    for need_id, lineno, body in sections:
        if need_id in needs:
            raise ToolsIndexError(f"line {lineno}: duplicate need {need_id!r}")
        needs[need_id] = _parse_need(need_id, lineno, body)
        for alias in needs[need_id]["aliases"]:
            if alias in alias_owner:
                raise ToolsIndexError(
                    f"line {lineno}: alias {alias!r} is used by both "
                    f"{alias_owner[alias]!r} and {need_id!r}"
                )
            alias_owner[alias] = need_id
    return {"_generated": GENERATED_NOTE, "needs": needs}


def render(index: dict) -> str:
    return json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the preferred-tools JSON index."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="fail if the JSON is out of date"
    )
    args = parser.parse_args(argv)

    try:
        expected = render(build_index(args.source.read_text(encoding="utf-8")))
    except (OSError, ToolsIndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != expected:
            print(
                f"error: {args.output.name} is out of date; "
                "run scripts/build_tools_index.py",
                file=sys.stderr,
            )
            return 1
        return 0

    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(expected)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
