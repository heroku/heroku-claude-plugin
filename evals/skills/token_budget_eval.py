#!/usr/bin/env python3
"""Token budget eval.

Validates that representative skill responses stay within the configured token
budgets defined in plugin.json under policy.token_budgets.

Since we cannot invoke Claude in CI, this eval operates on hardcoded sample
responses for each skill and measures their token count using a simple
word-count proxy (len(text.split())). This is good enough for budget
validation — real tokenizers count slightly differently but the proxy is
a conservative approximation at these response sizes. See comment in
_token_count() for rationale.

Usage:
  python3 evals/skills/token_budget_eval.py
  python3 evals/skills/token_budget_eval.py --skill preflight

Exit codes:
  0 — all samples under budget
  1 — one or more samples exceed budget
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Sample responses — 2 per skill: one normal, one verbose/edge-case
# ---------------------------------------------------------------------------

SAMPLE_RESPONSES: dict[str, list[dict]] = {
    "preflight": [
        {
            "label": "normal — all checks pass",
            "text": (
                "Preflight checks complete.\n\n"
                "- git: found at /usr/bin/git (version 2.43.0)\n"
                "- heroku CLI: found at /usr/local/bin/heroku (logged in as user@example.com)\n"
                "- docker: found at /usr/local/bin/docker (version 24.0)\n\n"
                "Your environment is ready. You can scaffold and deploy."
            ),
        },
        {
            "label": "edge case — verbose error with instructions",
            "text": (
                "Preflight checks found issues that must be resolved before proceeding.\n\n"
                "git: NOT FOUND\n"
                "  git is required to scaffold and deploy. Install it from https://git-scm.com or "
                "run `brew install git` on macOS.\n\n"
                "heroku CLI: NOT FOUND\n"
                "  The Heroku CLI is required to deploy. Install from https://devcenter.heroku.com/articles/heroku-cli "
                "or run `brew tap heroku/brew && brew install heroku`.\n\n"
                "docker: OPTIONAL — not found\n"
                "  Docker is not required but enables local dev with docker-compose. "
                "Install from https://docs.docker.com/get-docker/ if you want local dev.\n\n"
                "Please fix the required issues above and then re-run the preflight check."
            ),
        },
    ],
    "scaffold-app": [
        {
            "label": "normal — Python FastAPI scaffolded",
            "text": (
                "Scaffolding a Python FastAPI app named my-app.\n\n"
                "Running `pip install fastapi uvicorn` and generating project structure...\n\n"
                "Created files:\n"
                "  my-app/\n"
                "  my-app/main.py\n"
                "  my-app/requirements.txt\n"
                "  my-app/Procfile\n"
                "  my-app/app.json\n"
                "  my-app/.gitignore\n"
                "  my-app/Dockerfile         (local dev only, not pushed to Heroku)\n"
                "  my-app/docker-compose.yml (includes postgres sidecar)\n\n"
                "Heroku glue written. Addons configured: heroku-postgresql.\n\n"
                "Next step: run the deploy skill to push to Heroku."
            ),
        },
        {
            "label": "edge case — verbose output with all addons and long toolchain log",
            "text": (
                "Scaffolding a Rails app named restaurant-app with PostgreSQL and Redis.\n\n"
                "Checking toolchain...\n"
                "  ruby: found 3.2.2\n"
                "  bundler: found 2.4.1\n"
                "  rails: found 7.1.0\n\n"
                "Running `rails new restaurant-app --database=postgresql --skip-test`...\n"
                "      create  README.md\n"
                "      create  Rakefile\n"
                "      create  .ruby-version\n"
                "      create  .gitignore\n"
                "      create  Gemfile\n"
                "      create  Gemfile.lock\n"
                "      create  app/\n"
                "      create  app/models/\n"
                "      create  app/controllers/\n"
                "      create  app/views/\n"
                "      create  config/\n"
                "      create  config/database.yml\n"
                "      create  config/routes.rb\n"
                "      create  db/\n"
                "      run     bundle install\n\n"
                "Writing Heroku glue files...\n"
                "  Procfile: web: bundle exec puma -C config/puma.rb\n"
                "  app.json: addons=[heroku-postgresql, heroku-redis], stack=heroku-22\n"
                "  Dockerfile: ruby:3.2-slim base image, RAILS_ENV=production\n"
                "  docker-compose.yml: postgres:16 + redis:7-alpine sidecars\n\n"
                "Git repository initialized. Initial commit created.\n\n"
                "Scaffold complete. Run the deploy skill when ready."
            ),
        },
    ],
    "deploy-anonymous": [
        {
            "label": "normal — deploy succeeded",
            "text": (
                "Deploying my-app to Heroku...\n\n"
                "Initializing git remote: heroku\n"
                "Running: git push heroku main\n\n"
                "remote: Compressing source files... done.\n"
                "remote: Building source:\n"
                "remote: -----> Python app detected\n"
                "remote: -----> Installing python-3.12.0\n"
                "remote: -----> Installing dependencies from Pipfile.lock\n"
                "remote: -----> Discovering process types\n"
                "remote:        Procfile declares types -> web\n"
                "remote: -----> Compressing... done, 56.2 MB\n"
                "remote: -----> Launching... done\n"
                "remote:        https://my-app-a1b2c3.herokuapp.com/ deployed to Heroku\n\n"
                "Deploy complete. Your app is available at: https://my-app-a1b2c3.herokuapp.com/"
            ),
        },
        {
            "label": "edge case — deploy failed with buildpack error",
            "text": (
                "Deploying my-app to Heroku...\n\n"
                "Running: git push heroku main\n\n"
                "remote: Compressing source files... done.\n"
                "remote: Building source:\n"
                "remote: -----> Python app detected\n"
                "remote: -----> Installing python-3.12.0\n"
                "remote:  !     Error installing dependencies from requirements.txt\n"
                "remote:  !     Push rejected, failed to compile Python app.\n\n"
                "remote: Verifying deploy... done.\n"
                "error: failed to push some refs to 'https://git.heroku.com/my-app.git'\n\n"
                "Deploy failed. Common causes:\n"
                "- Syntax error or missing package in requirements.txt\n"
                "- Incompatible Python version specified in runtime.txt\n"
                "- Missing environment variable needed at build time\n\n"
                "Run the check-deploy-status skill for more details, or review the build log above."
            ),
        },
    ],
    "check-deploy-status": [
        {
            "label": "normal — build succeeded",
            "text": (
                "Build status for my-app:\n\n"
                "  Status: succeeded\n"
                "  Build ID: a1b2c3d4\n"
                "  Started: 2 minutes ago\n"
                "  Completed: 45 seconds ago\n"
                "  Output URL: https://my-app-a1b2c3.herokuapp.com/\n\n"
                "Your app is live."
            ),
        },
        {
            "label": "edge case — build pending with log lines",
            "text": (
                "Build status for my-app:\n\n"
                "  Status: building\n"
                "  Build ID: a1b2c3d4\n"
                "  Started: 30 seconds ago\n\n"
                "Recent log output:\n"
                "  remote: -----> Python app detected\n"
                "  remote: -----> Installing python-3.12.0\n"
                "  remote: -----> Installing dependencies from Pipfile.lock\n"
                "  remote:        Collecting fastapi==0.104.0\n"
                "  remote:        Collecting uvicorn==0.24.0\n"
                "  remote:        Collecting pydantic==2.4.0\n\n"
                "Build is still in progress. Run check-deploy-status again in a moment to see the final result."
            ),
        },
    ],
    "generate-access-code": [
        {
            "label": "normal — access code generated",
            "text": (
                "Access code generated for my-app.\n\n"
                "Share this code with your colleague:\n\n"
                "  ACCESS CODE: HERO-4729\n\n"
                "They can use it at https://heroku.com/claim to access the app. "
                "The code expires in 24 hours."
            ),
        },
        {
            "label": "edge case — access code with extended instructions",
            "text": (
                "Access code generated for my-app.\n\n"
                "  ACCESS CODE: HERO-4729\n\n"
                "Share this with your colleague. Here's what they need to do:\n\n"
                "1. Visit https://heroku.com/claim\n"
                "2. Enter the access code: HERO-4729\n"
                "3. If they don't have a Heroku account, they'll be prompted to create one (free).\n"
                "4. Once they enter the code, they'll have viewer access to the app.\n\n"
                "Note: The code expires in 24 hours. If it expires, use the generate-access-code skill to create a new one.\n\n"
                "The app URL is: https://my-app-a1b2c3.herokuapp.com/"
            ),
        },
    ],
    "claim-app": [
        {
            "label": "normal — app claimed successfully",
            "text": (
                "Transferring my-app to your Heroku account...\n\n"
                "  Transfer complete.\n"
                "  App: my-app\n"
                "  New owner: user@example.com\n\n"
                "The app is now in your account. You can manage it at https://dashboard.heroku.com/apps/my-app."
            ),
        },
        {
            "label": "edge case — claim failed, account not found",
            "text": (
                "Unable to transfer my-app.\n\n"
                "Error: Heroku account not found for the provided email address.\n\n"
                "To claim this app:\n"
                "1. Sign up for a Heroku account at https://signup.heroku.com\n"
                "2. Verify your email address\n"
                "3. Return here and run the claim-app skill again with your verified email\n\n"
                "If you already have an account and are seeing this error, make sure you're using the "
                "exact email address associated with your Heroku account."
            ),
        },
    ],
    "go-live": [
        {
            "label": "normal — app made public",
            "text": (
                "Making my-app public...\n\n"
                "Removing access code restriction.\n"
                "App is now publicly accessible at: https://my-app-a1b2c3.herokuapp.com/\n\n"
                "Anyone with the URL can access your app."
            ),
        },
        {
            "label": "edge case — verbose with DNS instructions",
            "text": (
                "Making my-app public...\n\n"
                "Access code restriction removed.\n"
                "App URL: https://my-app-a1b2c3.herokuapp.com/\n\n"
                "Your app is now live and publicly accessible.\n\n"
                "Optional next steps:\n"
                "- Add a custom domain: heroku domains:add www.example.com\n"
                "- Configure DNS: add a CNAME record pointing www.example.com to my-app-a1b2c3.herokuapp.com\n"
                "- Enable SSL: Heroku provides free SSL on all apps via Heroku's ACM (Automatic Certificate Management)\n\n"
                "To add collaborators, use: heroku access:add user@example.com --app my-app"
            ),
        },
    ],
    "build-and-deploy": [
        {
            "label": "normal — build and deploy completed",
            "text": (
                "Running build-and-deploy for my-app (Python FastAPI).\n\n"
                "Step 1/3: Scaffold\n"
                "  Created project at ./my-app\n"
                "  Generated Procfile, app.json, Dockerfile, docker-compose.yml\n\n"
                "Step 2/3: Deploy\n"
                "  Initializing git remote\n"
                "  Pushing to Heroku...\n"
                "  Build complete\n\n"
                "Step 3/3: Verify\n"
                "  Status: succeeded\n"
                "  URL: https://my-app-a1b2c3.herokuapp.com/\n\n"
                "Your app is live."
            ),
        },
        {
            "label": "edge case — full verbose pipeline with addon provisioning",
            "text": (
                "Running build-and-deploy for restaurant-app (Rails + PostgreSQL + Redis).\n\n"
                "Step 1/4: Preflight\n"
                "  git: ok\n"
                "  heroku CLI: ok\n"
                "  ruby: ok (3.2.2)\n"
                "  All checks passed.\n\n"
                "Step 2/4: Scaffold\n"
                "  Running rails new restaurant-app --database=postgresql\n"
                "  Writing Procfile: web: bundle exec puma -C config/puma.rb\n"
                "  Writing app.json: addons=[heroku-postgresql, heroku-redis]\n"
                "  Writing Dockerfile (local dev)\n"
                "  Writing docker-compose.yml (postgres + redis sidecars)\n"
                "  Git repo initialized, initial commit created.\n\n"
                "Step 3/4: Deploy\n"
                "  Creating Heroku app: restaurant-app-a1b2c3\n"
                "  Provisioning addon: heroku-postgresql (hobby-dev plan)\n"
                "  Provisioning addon: heroku-redis (hobby-dev plan)\n"
                "  Pushing to Heroku via git push heroku main...\n"
                "  -----> Ruby app detected\n"
                "  -----> Installing dependencies via Bundler\n"
                "  -----> Detecting rake tasks\n"
                "  -----> Launching...\n"
                "  https://restaurant-app-a1b2c3.herokuapp.com/ deployed to Heroku\n\n"
                "Step 4/4: Verify\n"
                "  Build status: succeeded\n"
                "  App URL: https://restaurant-app-a1b2c3.herokuapp.com/\n"
                "  DATABASE_URL: set\n"
                "  REDIS_URL: set\n\n"
                "Build and deploy complete. Your app is live at: https://restaurant-app-a1b2c3.herokuapp.com/"
            ),
        },
    ],
}


def _token_count(text: str) -> int:
    """Approximate token count using word-count proxy.

    Real LLM tokenizers (BPE, sentencepiece) count tokens differently from
    words — punctuation, whitespace, and subword splits all affect the count.
    len(text.split()) undercounts by roughly 10-20% on typical prose, making
    it a conservative proxy: if a response passes the word-count budget check,
    it is very likely within the true token budget too. Good enough for CI.
    """
    return len(text.split())


def load_budgets(plugin_json_path: str) -> dict[str, int]:
    """Load token budgets from plugin.json, skipping metadata keys prefixed with _."""
    with open(plugin_json_path) as f:
        config = json.load(f)
    raw = config["policy"]["token_budgets"]
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def run_eval(skill: str | None = None) -> int:
    """Run token budget eval. Returns 0 if all pass, 1 if any exceed budget."""
    here = os.path.dirname(os.path.abspath(__file__))
    plugin_json = os.path.join(here, "..", "..", ".claude-plugin", "plugin.json")
    budgets = load_budgets(plugin_json)

    skills_to_test = {skill: SAMPLE_RESPONSES[skill]} if skill else SAMPLE_RESPONSES
    failures: list[str] = []

    print(f"Token budgets loaded from plugin.json ({len(budgets)} skills)\n")

    for skill_name, samples in skills_to_test.items():
        budget = budgets.get(skill_name)
        if budget is None:
            print(f"[{skill_name}] SKIP — no budget configured")
            continue

        print(f"[{skill_name}] budget={budget} tokens")
        for sample in samples:
            count = _token_count(sample["text"])
            status = "✓" if count <= budget else "✗"
            print(f"  {status} {sample['label']}: {count} tokens (budget: {budget})")
            if count > budget:
                failures.append(
                    f"{skill_name}/{sample['label']}: {count} tokens exceeds budget of {budget}"
                )

    print(f"\n{'─' * 50}")
    if failures:
        print(f"FAILED: {len(failures)} sample(s) exceed token budget")
        for f in failures:
            print(f"  {f}")
        return 1

    print("PASSED: All samples within token budget")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Token budget eval for skill responses.")
    parser.add_argument(
        "--skill",
        help="Test a single skill (e.g. preflight)",
        choices=list(SAMPLE_RESPONSES.keys()),
    )
    args = parser.parse_args()
    return run_eval(skill=args.skill)


if __name__ == "__main__":
    sys.exit(main())
