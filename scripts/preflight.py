#!/usr/bin/env python3
"""Heroku plugin preflight checker.

Checks:
  1. git    (required — deploy fails without it)
  2. heroku (required — CLI deploy path; TODO: remove hard requirement once MCP implementation is available)
  3. docker (optional — enables local dev environment)
  4. Reference file staleness (if not --quick)

Outputs JSON on stdout:
  { "git": true, "heroku": true, "heroku_logged_in": true,
    "docker": true|false, "docker_skipped": false, "references_updated": [...] }

Exits 0 on success or when optional checks are skipped.
Exits 1 if git or heroku CLI is missing, or if heroku login check fails.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent

GIT_INSTALL = {
    "Darwin": "brew install git  (or https://git-scm.com/download/mac)",
    "Linux": "apt-get install git  (or https://git-scm.com/download/linux)",
    "Windows": "winget install Git.Git  (or https://git-scm.com/download/win)",
}

# TODO: remove HEROKU_INSTALL and heroku hard requirement once MCP implementation is available
HEROKU_INSTALL = {
    "Darwin": "brew tap heroku/brew && brew install heroku  (or https://devcenter.heroku.com/articles/heroku-cli)",
    "Linux": "curl https://cli-assets.heroku.com/install.sh | sh  (or https://devcenter.heroku.com/articles/heroku-cli)",
    "Windows": "winget install Heroku.HerokuCLI  (or https://devcenter.heroku.com/articles/heroku-cli)",
}

DOCKER_INSTALL = {
    "Darwin": "brew install --cask docker",
    "Linux": "https://docs.docker.com/engine/install/",
    "Windows": "winget install Docker.DockerDesktop",
}

DOCKER_EXPLANATION = (
    "Docker gives you a local development environment without installing "
    "language runtimes (Python, Node.js, Ruby, Go) on your machine. "
    "It also lets you run local copies of Postgres and Redis that mirror "
    "your Heroku addons exactly, so what works locally works on Heroku."
)


def _os_key() -> str:
    return platform.system()  # "Darwin", "Linux", "Windows"


def _check_git() -> tuple[bool, str]:
    if shutil.which("git"):
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        return True, result.stdout.strip()
    return False, ""


# TODO: remove _check_heroku and heroku hard requirement once MCP implementation is available
def _check_heroku() -> tuple[bool, str]:
    """Check heroku CLI is installed and user is logged in."""
    if not shutil.which("heroku"):
        return False, ""
    result = subprocess.run(["heroku", "--version"], capture_output=True, text=True)
    return True, result.stdout.strip().splitlines()[0] if result.stdout else ""


def _check_heroku_login() -> tuple[bool, str]:
    """Return (logged_in, email). Runs heroku whoami."""
    try:
        result = subprocess.run(
            ["heroku", "whoami"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False, ""


def _check_docker() -> bool:
    return shutil.which("docker") is not None and _docker_running()


def _docker_running() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _install_docker() -> bool:
    os_key = _os_key()
    if os_key == "Darwin":
        cmd = ["brew", "install", "--cask", "docker"]
    elif os_key == "Linux":
        print("  Please install Docker manually: https://docs.docker.com/engine/install/", file=sys.stderr)
        return False
    elif os_key == "Windows":
        cmd = ["winget", "install", "Docker.DockerDesktop"]
    else:
        print(f"  Unsupported OS for automatic install: {os_key}", file=sys.stderr)
        return False

    print(f"  Installing Docker...", file=sys.stderr)
    try:
        result = subprocess.run(cmd, timeout=300)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_references(quick: bool = False) -> list[str]:
    if quick:
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "scripts" / "check_references.py"), "--auto"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout).get("updated", [])
    except Exception:
        pass
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Heroku plugin preflight checker.")
    parser.add_argument("--quick", action="store_true", help="Skip reference staleness check")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no installs")
    parser.add_argument("--json", action="store_true", help="Output JSON result to stdout")
    args = parser.parse_args()

    result = {
        "git": False,
        "git_version": "",
        "heroku": False,
        "heroku_version": "",
        "heroku_logged_in": False,
        "heroku_email": "",
        "docker": False,
        "docker_skipped": False,
        "references_updated": [],
    }

    # --- git (required) ---
    git_ok, git_version = _check_git()
    result["git"] = git_ok
    result["git_version"] = git_version

    if not git_ok:
        install_hint = GIT_INSTALL.get(_os_key(), "https://git-scm.com/downloads")
        print(f"\n✗ git is required but not found.", file=sys.stderr)
        print(f"  Install: {install_hint}", file=sys.stderr)
        if args.json:
            print(json.dumps(result))
        return 1

    print(f"✓ git  ({git_version})", file=sys.stderr)

    # TODO: remove heroku CLI hard requirement once MCP implementation is available.
    # --- heroku CLI (required until MCP deploy path is available) ---
    heroku_ok, heroku_version = _check_heroku()
    result["heroku"] = heroku_ok
    result["heroku_version"] = heroku_version

    if not heroku_ok:
        install_hint = HEROKU_INSTALL.get(_os_key(), "https://devcenter.heroku.com/articles/heroku-cli")
        print(f"\n✗ Heroku CLI is required but not found.", file=sys.stderr)
        print(f"  Install: {install_hint}", file=sys.stderr)
        if args.json:
            print(json.dumps(result))
        return 1

    print(f"✓ heroku  ({heroku_version})", file=sys.stderr)

    # --- heroku login check ---
    if not args.dry_run:
        logged_in, email = _check_heroku_login()
        result["heroku_logged_in"] = logged_in
        result["heroku_email"] = email

        if not logged_in:
            print(f"\n✗ Not logged in to Heroku.", file=sys.stderr)
            print(f"  Run: heroku login", file=sys.stderr)
            if args.json:
                print(json.dumps(result))
            return 1

        print(f"✓ heroku logged in  ({email})", file=sys.stderr)
    else:
        print(f"  (dry-run: skipping heroku login check)", file=sys.stderr)

    # --- docker (optional) ---
    docker_ok = _check_docker()

    if docker_ok:
        print("✓ docker", file=sys.stderr)
        result["docker"] = True
    else:
        print(f"\n  Docker not found.", file=sys.stderr)
        print(f"\n  {DOCKER_EXPLANATION}\n", file=sys.stderr)

        if args.dry_run:
            print("  (dry-run: skipping Docker install prompt)", file=sys.stderr)
            result["docker_skipped"] = True
        else:
            try:
                answer = input("  Would you like me to install Docker Desktop? [yes/no]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "no"

            if answer in ("yes", "y"):
                if _install_docker():
                    docker_ok = _check_docker()
                    result["docker"] = docker_ok
                    if docker_ok:
                        print("✓ docker (installed)", file=sys.stderr)
                    else:
                        print("  Docker installed but not yet running — start Docker Desktop and re-run.", file=sys.stderr)
                        result["docker_skipped"] = True
                else:
                    print("  Docker install failed — proceeding without local dev environment.", file=sys.stderr)
                    result["docker_skipped"] = True
            else:
                print("  Proceeding without Docker — local run/test unavailable.", file=sys.stderr)
                result["docker_skipped"] = True

    # --- reference staleness ---
    if not args.quick and not args.dry_run:
        updated = _check_references()
        result["references_updated"] = updated
        if updated:
            print(f"  References updated: {', '.join(updated)}", file=sys.stderr)

    if args.json:
        print(json.dumps(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
