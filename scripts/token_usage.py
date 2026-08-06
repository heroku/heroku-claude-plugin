#!/usr/bin/env python3
"""Token usage recording and reporting.

Feature-flagged via the HEROKU_TOKEN_BUDGET_TRACKING environment variable.
When unset or empty, all operations are silent no-ops.

Usage:
  # Record usage at the end of a skill (Claude provides its estimated output token count):
  python3 scripts/token_usage.py record --skill scaffold-app --tokens 312

  # Print a utilization report vs configured budgets:
  python3 scripts/token_usage.py report

Exit codes:
  0 — always (fire-and-forget; never blocks a skill)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
USAGE_LOG = Path.cwd() / ".heroku-plugin-token-usage.jsonl"


def _tracking_enabled() -> bool:
    return os.environ.get("HEROKU_TOKEN_BUDGET_TRACKING", "").strip() == "1"


def _load_budgets() -> dict[str, int]:
    try:
        raw = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        budgets = raw.get("policy", {}).get("token_budgets", {})
        return {k: v for k, v in budgets.items() if not k.startswith("_")}
    except Exception:
        return {}


def cmd_record(skill: str, tokens: int) -> int:
    """Append one usage record to the JSONL log and print utilization to stdout."""
    if not _tracking_enabled():
        return 0

    budgets = _load_budgets()
    budget = budgets.get(skill)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": skill,
        "tokens": tokens,
        "budget": budget,
        "over_budget": (tokens > budget) if budget is not None else None,
    }

    try:
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(f"[token_usage] warn: could not write log: {exc}", file=sys.stderr)

    if budget is not None:
        pct = round(tokens / budget * 100)
        status = "over budget" if tokens > budget else "within budget"
        print(f"[token usage] {skill}: {tokens} / {budget} tokens ({pct}%) — {status}")
    else:
        print(f"[token usage] {skill}: {tokens} tokens (no budget configured)")

    return 0


def cmd_report() -> int:
    """Print a utilization table comparing logged usage against configured budgets."""
    if not _tracking_enabled():
        return 0

    if not USAGE_LOG.exists():
        print("[token usage] No usage recorded yet. Set HEROKU_TOKEN_BUDGET_TRACKING=1 and run some skills.")
        return 0

    budgets = _load_budgets()
    records: list[dict] = []
    try:
        for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    except Exception as exc:
        print(f"[token_usage] error reading log: {exc}", file=sys.stderr)
        return 0

    if not records:
        print("[token usage] Log is empty.")
        return 0

    # Aggregate: per-skill average, max, count
    from collections import defaultdict
    stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0, "max": 0})
    for r in records:
        s = r["skill"]
        t = r["tokens"]
        stats[s]["count"] += 1
        stats[s]["total"] += t
        stats[s]["max"] = max(stats[s]["max"], t)

    print(f"\n{'Skill':<25} {'Budget':>8} {'Avg':>8} {'Max':>8} {'Runs':>6}  Utilization")
    print("─" * 70)
    for skill in sorted(stats):
        st = stats[skill]
        avg = round(st["total"] / st["count"])
        mx = st["max"]
        budget = budgets.get(skill)
        if budget:
            avg_pct = round(avg / budget * 100)
            max_pct = round(mx / budget * 100)
            bar = "█" * min(round(max_pct / 5), 20)
            util = f"{avg_pct}% avg / {max_pct}% max  {bar}"
        else:
            util = "(no budget)"
        bstr = str(budget) if budget else "—"
        print(f"  {skill:<23} {bstr:>8} {avg:>8} {mx:>8} {st['count']:>6}  {util}")
    print()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Token usage recording and reporting (no-op unless HEROKU_TOKEN_BUDGET_TRACKING=1)."
    )
    sub = parser.add_subparsers(dest="cmd")

    rec = sub.add_parser("record", help="Record token usage for a skill")
    rec.add_argument("--skill", required=True, help="Skill name (e.g. scaffold-app)")
    rec.add_argument("--tokens", required=True, type=int, help="Estimated output token count")

    sub.add_parser("report", help="Print utilization report vs configured budgets")

    args = parser.parse_args()

    if args.cmd == "record":
        return cmd_record(args.skill, args.tokens)
    if args.cmd == "report":
        return cmd_report()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
