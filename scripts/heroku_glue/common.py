"""Shared helpers for deterministic Heroku glue file generation.

Layer 2 output is byte-identical across runs:
  - UTF-8 encoding, LF newlines, exactly one trailing newline
  - JSON: indent=2, sort_keys=True
  - Addon lists: sorted and deduplicated
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


class ScaffoldError(Exception):
    """User-facing, actionable scaffold failure."""


def log(message: str) -> None:
    """Emit a progress line to stderr (stdout reserved for JSON summary)."""
    print(f"[heroku-scaffold] {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Addon registry
# ---------------------------------------------------------------------------

ADDON_SLUGS = {
    "postgres": "heroku-postgresql",
    "postgresql": "heroku-postgresql",
    "redis": "heroku-redis",
    # kafka is registered but not supported in v1
    "kafka": None,
}

ADDON_CONFIG_VARS = {
    "heroku-postgresql": "DATABASE_URL",
    "heroku-redis": "REDIS_URL",
}

UNSUPPORTED_ADDONS = {"kafka"}


def resolve_addons(requested: list[str]) -> list[str]:
    """Translate friendly addon names to canonical Heroku slugs.

    Raises ScaffoldError for unsupported addons.
    Returns sorted, deduplicated canonical slugs.
    """
    slugs = []
    for name in requested:
        key = name.lower().strip()
        if key in UNSUPPORTED_ADDONS:
            raise ScaffoldError(
                f"Addon '{name}' is not supported in v1. Supported: postgres, redis."
            )
        if key in ADDON_SLUGS:
            slug = ADDON_SLUGS[key]
            if slug is not None:
                slugs.append(slug)
        elif name in ADDON_CONFIG_VARS:
            # Already a canonical slug
            slugs.append(name)
        else:
            raise ScaffoldError(
                f"Unknown addon '{name}'. Supported: postgres, redis."
            )
    return sorted(set(slugs))


def effective_addons(module, options: dict) -> list[str]:
    """Single source of truth: canonical addon slugs this stack will declare.

    Merges module defaults + user-requested, resolves to canonical slugs,
    deduplicates and sorts. Called by both apply_glue() and the JSON summary
    so they can never drift.
    """
    defaults = list(getattr(module, "DEFAULT_ADDONS", []))
    requested = list(options.get("addons", []))
    combined = defaults + requested
    return resolve_addons(combined) if combined else []


# ---------------------------------------------------------------------------
# Deterministic file writers
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str, *, executable: bool = False) -> None:
    """Write text with UTF-8, LF newlines, exactly one trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    path.write_text(normalized, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | 0o111)
    log(f"wrote {path}")


def write_json(path: Path, data: dict) -> None:
    """Write JSON with sorted keys and 2-space indent (deterministic)."""
    write_file(path, json.dumps(data, indent=2, sort_keys=True))


def merge_gitignore(target_dir: Path, lines: list[str]) -> None:
    """Append-only .gitignore update — never clobbers existing entries."""
    gitignore = target_dir / ".gitignore"
    existing = set()
    current_content = ""
    if gitignore.exists():
        current_content = gitignore.read_text(encoding="utf-8")
        existing = {ln.strip() for ln in current_content.splitlines()}

    new_lines = [ln for ln in lines if ln.strip() and ln.strip() not in existing]
    if not new_lines:
        return

    header = "# --- Heroku deploy artifacts (added by heroku-plugin) ---"
    if header.strip() not in existing:
        new_lines = [header] + new_lines

    separator = "\n" if current_content and not current_content.endswith("\n") else ""
    write_file(gitignore, current_content + separator + "\n".join(new_lines))


# ---------------------------------------------------------------------------
# app.json + docker-compose builders
# ---------------------------------------------------------------------------

def build_app_json(
    app_name: str,
    *,
    buildpack: str,
    addons: list[str] | None = None,
    env: dict | None = None,
    formation: dict | None = None,
    description: str = "",
    stack: str = "heroku-24",
) -> dict:
    """Assemble a deterministic app.json manifest."""
    data: dict = {"name": app_name, "stack": stack}
    if description:
        data["description"] = description
    data["buildpacks"] = [{"url": buildpack}]
    if env:
        data["env"] = env
    if addons:
        data["addons"] = sorted(addons)
    if formation:
        data["formation"] = formation
    return data


def build_docker_compose(app_name: str, addons: list[str]) -> dict:
    """Build a deterministic docker-compose.yml mirroring Heroku addon config vars."""
    services: dict = {
        "app": {
            "build": ".",
            "ports": ["${PORT:-5000}:${PORT:-5000}"],
            "environment": {"PORT": "${PORT:-5000}"},
            "depends_on": [],
        }
    }

    if "heroku-postgresql" in addons:
        services["postgres"] = {
            "image": "postgres:16",
            "environment": {
                "POSTGRES_DB": app_name.replace("-", "_"),
                "POSTGRES_USER": "postgres",
                "POSTGRES_PASSWORD": "postgres",
            },
            "ports": ["5432:5432"],
        }
        services["app"]["environment"]["DATABASE_URL"] = (
            f"postgres://postgres:postgres@postgres:5432/{app_name.replace('-', '_')}?sslmode=disable"
        )
        services["app"]["depends_on"].append("postgres")

    if "heroku-redis" in addons:
        services["redis"] = {
            "image": "redis:7-alpine",
            "ports": ["6379:6379"],
        }
        services["app"]["environment"]["REDIS_URL"] = "redis://redis:6379"
        services["app"]["depends_on"].append("redis")

    if not services["app"]["depends_on"]:
        del services["app"]["depends_on"]

    return {"version": "3.8", "services": services}


def write_docker_compose(target_dir: Path, app_name: str, addons: list[str]) -> None:
    """Write docker-compose.yml for local development."""
    data = build_docker_compose(app_name, addons)
    write_json(target_dir / "docker-compose.yml", data)


# ---------------------------------------------------------------------------
# Subprocess + toolchain helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a subprocess, streaming output to stderr, raising ScaffoldError on failure."""
    log(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=sys.stderr,  # native scaffolder output goes to stderr for JSON purity
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        raise ScaffoldError(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")


def require_tools(required: list[tuple[str, str]]) -> None:
    """Fail loudly if required tools are missing from PATH.

    Args:
        required: list of (binary_name, install_url) tuples
    """
    missing = [(bin_, url) for bin_, url in required if not shutil.which(bin_)]
    if missing:
        lines = ["Required tool(s) not found on PATH:"]
        for bin_, url in missing:
            lines.append(f"  - {bin_}  (install: {url})")
        lines.append("Install the tool(s) above and re-run.")
        raise ScaffoldError("\n".join(lines))


# ---------------------------------------------------------------------------
# Shared .gitignore base
# ---------------------------------------------------------------------------

BASE_GITIGNORE = [
    ".env",
    ".env.*",
    "*.local",
    ".DS_Store",
    "*.swp",
    "*.swo",
]
