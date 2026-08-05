#!/usr/bin/env python3
"""Skill trigger discrimination eval.

Validates that each skill triggers on the right prompts and NOT on control prompts.
Keyword-match validation: positive prompts must contain at least one skill keyword;
negative prompts must contain none of the skill's keywords.

Usage:
  python3 evals/skills/trigger_eval.py
  python3 evals/skills/trigger_eval.py --skill scaffold-app
  python3 evals/skills/trigger_eval.py --skill scaffold-app --samples 3
  python3 evals/skills/trigger_eval.py --dry-run   # prints only, no assertions
"""

from __future__ import annotations

import argparse
import sys

# TODO(token-budget-eval): Add a token budget eval entry for check-deploy-status
# (and for the diagnose-and-fix sub-agent Task call in Step 4b) once the token
# budget eval infrastructure from W-23664929 lands in evals/skills/token_budget_eval.py.
# The diagnose-and-fix prompt template carries ~200 tokens of system context
# (deploy-contract.md reference + stack reference) plus a variable log excerpt;
# budget should reflect worst-case 100-line log tail.

SKILL_TRIGGERS: dict[str, dict] = {
    "preflight": {
        "positive": [
            "Check my environment before building",
            "Run preflight checks",
            "Is my system ready for Heroku?",
            "Verify my setup",
        ],
        "negative": [
            "What is the capital of France?",
            "Review my pull request",
            "What does this function do?",
        ],
    },
    "scaffold-app": {
        # W-23667947: covers git init + gitignore angle of scaffolding AC
        "positive": [
            "Build me a Python FastAPI app",
            "Create a new Node.js Express app",
            "Scaffold a Rails application with Postgres",
            "I want to build a SaaS app that allows restaurants to order supplies",
            "Make me a Go web server",
            "Initialize a git repo and scaffold a Python app",
            "Create a new Go app with a gitignore",
        ],
        "negative": [
            "Deploy my existing app",
            "Check the build status",
            "Make my app public",
            "What is Docker?",
        ],
    },
    "deploy-anonymous": {
        # W-23667947: covers explicit deploy-via-git intent AC
        "positive": [
            "Deploy the application so I can share it",
            "Deploy it to Heroku",
            "Push to Heroku",
            "Make it live so I can preview it",
            "Push my app to Heroku using git",
            "I want to deploy this app so someone can use it",
        ],
        "negative": [
            "Build me an app",
            "Make it public",
            "What is my app URL?",
        ],
    },
    "check-deploy-status": {
        "positive": [
            "Is my app deployed?",
            "Check the build",
            "What happened to my deploy?",
            "How is the deployment going?",
            # diagnose/fix loop angle — exercises Step 4b Task delegation path
            "My Heroku build failed, can you fix it?",
            "The deploy crashed, diagnose what went wrong",
        ],
        "negative": [
            "Deploy my app",
            "Build a new app",
            "Make it public",
        ],
    },
    "generate-access-code": {
        "positive": [
            "Share this app with my colleague",
            "Give me an access code",
            "I want to share the app with Martin",
            "Generate a sharing code",
        ],
        "negative": [
            "Deploy my app",
            "Make it public",
            "Claim this app",
        ],
    },
    "claim-app": {
        "positive": [
            "I want to keep this app",
            "Claim the app",
            "Register for Heroku and transfer my app",
            "I signed up, transfer my app now",
        ],
        "negative": [
            "Deploy my app",
            "Share this app",
            "Make it public",
        ],
    },
    "go-live": {
        "positive": [
            "Make this app go live",
            "Make it public",
            "Enable public access",
            "Go live",
            "Share it with the world",
        ],
        "negative": [
            "Deploy my app",
            "Claim this app",
            "Build a new app",
        ],
    },
    "build-and-deploy": {
        "positive": [
            "Build me a SaaS app and deploy it to Heroku",
            "Create a FastAPI app and host it on Heroku",
            "I want to build and deploy a restaurant ordering app",
        ],
        "negative": [
            "Deploy my existing app",
            "Just build the app, don't deploy",
            "Check my deployment status",
        ],
    },
}

# Keywords expected to appear in positive prompts for each skill.
# A positive prompt must match at least one keyword (case-insensitive).
# A negative prompt must match none of the skill's keywords.
#
# Keywords use specific phrases rather than single broad words to avoid
# false matches on shared vocabulary (e.g. "build" appears in many prompts).
SKILL_KEYWORD_MAP: dict[str, list[str]] = {
    "preflight": [
        "preflight", "check", "environment", "setup", "verify",
        "system", "ready",
    ],
    "scaffold-app": [
        "scaffold", "build me", "create a", "make me", "build a", "new app",
    ],
    "deploy-anonymous": [
        "deploy", "push", "live", "heroku",
    ],
    "check-deploy-status": [
        # Use phrases specific enough not to match "Deploy my app" or "Build a new app"
        "deployed", "what happened", "deployment going", "the build",
        "build status", "deploy status",
    ],
    "generate-access-code": [
        "share", "access code", "sharing code", "colleague", "generate a",
    ],
    "claim-app": [
        "claim", "keep this app", "register", "transfer", "signed up",
    ],
    "go-live": [
        "live", "public", "go-live", "world",
    ],
    "build-and-deploy": [
        # Multi-word phrases that appear in positives but not in the negatives
        # ("Deploy my existing app", "Just build the app, don't deploy", "Check my deployment status")
        "build and deploy", "host it on", "build me a",
    ],
}


def _matches(prompt: str, keywords: list[str]) -> bool:
    """Return True if the prompt contains at least one keyword (case-insensitive)."""
    lower = prompt.lower()
    return any(kw.lower() in lower for kw in keywords)


def run_eval(
    skill: str | None = None,
    samples: int | None = None,
    dry_run: bool = False,
) -> int:
    """Run trigger discrimination eval. Returns 0 if all pass, 1 if any fail."""
    skills_to_test = {skill: SKILL_TRIGGERS[skill]} if skill else SKILL_TRIGGERS
    failures: list[str] = []

    for skill_name, cases in skills_to_test.items():
        keywords = SKILL_KEYWORD_MAP[skill_name]
        positives = cases["positive"][:samples] if samples else cases["positive"]
        negatives = cases["negative"][:samples] if samples else cases["negative"]

        print(f"\n[{skill_name}]")

        for prompt in positives:
            matched = _matches(prompt, keywords)
            if dry_run or matched:
                print(f"  ✓ positive: {prompt[:60]}")
            else:
                print(f"  ✗ positive FAILED (no keyword match): {prompt[:60]}")
                if not dry_run:
                    failures.append(
                        f"{skill_name}/positive — no keyword match: {prompt!r}"
                    )

        for prompt in negatives:
            matched = _matches(prompt, keywords)
            if dry_run or not matched:
                print(f"  ✓ negative (control): {prompt[:60]}")
            else:
                print(f"  ✗ negative FAILED (keyword match): {prompt[:60]}")
                if not dry_run:
                    failures.append(
                        f"{skill_name}/negative — unexpected keyword match: {prompt!r}"
                    )

    print(f"\n{'─' * 50}")
    if dry_run:
        print("DRY RUN: assertions skipped")
        return 0

    if failures:
        print(f"FAILED: {len(failures)} trigger(s) misfired")
        for f in failures:
            print(f"  {f}")
        return 1

    print("PASSED: All trigger discriminations correct")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill trigger discrimination eval.")
    parser.add_argument("--skill", help="Test a single skill")
    parser.add_argument("--samples", type=int, help="Number of samples per skill")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompts without asserting (preserves old stub behavior)",
    )
    args = parser.parse_args()

    if args.skill and args.skill not in SKILL_TRIGGERS:
        print(f"Unknown skill '{args.skill}'. Available: {', '.join(SKILL_TRIGGERS)}")
        return 1

    return run_eval(skill=args.skill, samples=args.samples, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
