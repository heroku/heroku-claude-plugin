#!/usr/bin/env python3
"""Heroku plugin preflight checker.

Checks:
  1. git    (required — deploy fails without it)
  2. docker (optional — enables local dev environment)
  3. Reference file staleness (if not --quick)

Outputs JSON on stdout:
  { "git": true, "docker": true|false, "docker_skipped": false,
    "references_updated": [...] }

Exits 0 on success or when optional checks are skipped.
Exits 1 only if git is missing.
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
