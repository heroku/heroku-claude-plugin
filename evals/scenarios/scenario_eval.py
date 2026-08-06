#!/usr/bin/env python3
"""Scenario eval launcher.

Validates the scenarios corpus and launches the scenario-eval workflow.
Must be run from a Claude Code session started with --dangerously-skip-permissions
since agents will write files, run Heroku CLI commands, and deploy real apps.

Usage:
  python3 evals/scenarios/scenario_eval.py --list
  python3 evals/scenarios/scenario_eval.py --run
  python3 evals/scenarios/scenario_eval.py --scenario saas-node-express-postgres
  python3 evals/scenarios/scenario_eval.py --validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCENARIOS_FILE = Path(__file__).parent / "scenarios.json"
REQUIRED_FIELDS = {"id", "prompt", "skill", "stack", "assertions"}


def load_scenarios() -> list[dict]:
    return json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))


def validate(scenarios: list[dict]) -> list[str]:
    errors = []
    seen_ids: set[str] = set()
    for i, s in enumerate(scenarios):
        missing = REQUIRED_FIELDS - set(s.keys())
        if missing:
            errors.append(f"scenario[{i}]: missing fields {missing}")
        sid = s.get("id", f"[{i}]")
        if sid in seen_ids:
            errors.append(f"duplicate id: {sid!r}")
        seen_ids.add(sid)
        if not isinstance(s.get("assertions", []), list) or not s.get("assertions"):
            errors.append(f"{sid}: assertions must be a non-empty list")
    return errors


def cmd_list(scenarios: list[dict]) -> int:
    print(f"{'ID':<45} {'Stack':<10} {'Addons'}")
    print("─" * 80)
    for s in scenarios:
        addons = ", ".join(s.get("addons", [])) or "none"
        variant = f" ({s['variant']})" if s.get("variant") else ""
        print(f"  {s['id']:<43} {s['stack'] + variant:<10} {addons}")
    print(f"\n{len(scenarios)} scenario(s) total. Max 5 run concurrently.")
    return 0


def cmd_validate(scenarios: list[dict]) -> int:
    errors = validate(scenarios)
    if errors:
        print("INVALID:")
        for e in errors:
            print(f"  {e}")
        return 1
    print(f"OK: {len(scenarios)} scenario(s) valid")
    return 0


def cmd_run(scenario_id: str | None) -> int:
    print("─" * 60)
    print("Scenario Eval")
    print("─" * 60)
    print()
    print("This launches the scenario-eval workflow which will:")
    print("  • Deploy real Heroku apps (one per scenario)")
    print("  • Require an authenticated Heroku account")
    print("  • Run teardown after each scenario")
    print()
    print("Prerequisites:")
    print("  1. Run from a session started with:")
    print("       HEROKU_TOKEN_BUDGET_TRACKING=1 claude --plugin-dir /path/to/heroku-plugin --dangerously-skip-permissions")
    print("  2. heroku whoami must succeed")
    print("  3. moot-server should be running for session records")
    print()
    if scenario_id:
        print(f"Launching workflow for scenario: {scenario_id}")
        print()
        print("In Claude Code, run:")
        print(f'  /workflow scenario-eval {{"scenario": "{scenario_id}"}}')
    else:
        print("Launching workflow for all scenarios (max 5 concurrent).")
        print()
        print("In Claude Code, run:")
        print("  /workflow scenario-eval")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scenario eval launcher.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List available scenarios")
    group.add_argument("--validate", action="store_true", help="Validate scenarios.json schema")
    group.add_argument("--run", action="store_true", help="Print instructions to launch the workflow")
    group.add_argument("--scenario", metavar="ID", help="Print instructions for a single scenario")
    args = parser.parse_args()

    try:
        scenarios = load_scenarios()
    except Exception as exc:
        print(f"Error loading scenarios.json: {exc}", file=sys.stderr)
        return 1

    errors = validate(scenarios)
    if errors and not args.validate:
        print("scenarios.json has validation errors — run --validate for details", file=sys.stderr)
        return 1

    if args.list:
        return cmd_list(scenarios)
    if args.validate:
        return cmd_validate(scenarios)
    if args.run:
        return cmd_run(None)
    if args.scenario:
        ids = [s["id"] for s in scenarios]
        if args.scenario not in ids:
            print(f"Unknown scenario: {args.scenario!r}. Available: {', '.join(ids)}", file=sys.stderr)
            return 1
        return cmd_run(args.scenario)

    return 0


if __name__ == "__main__":
    sys.exit(main())
