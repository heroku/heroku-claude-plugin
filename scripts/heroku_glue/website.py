"""Static website stack module (heroku/static-web-server buildpack)."""

from pathlib import Path

from . import common

STACK = "website"
DISPLAY_NAME = "Static Website"
REQUIRED_TOOLS: list[tuple[str, str]] = []
DEFAULT_ADDONS: list[str] = []

# Intentionally not using common.build_project_toml() — that helper always appends
# heroku/procfile, which must not appear for static sites (the buildpack owns the
# web process). The website project.toml is structurally different from all other
# stacks and is kept separate to avoid conditional logic in the shared helper.
_PROJECT_TOML = """\
[_]
schema-version = "0.2"

[[io.buildpacks.group]]
id = "heroku/static-web-server"
"""

_INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My App</title>
</head>
<body>
  <h1>Hello from Heroku!</h1>
  <p>Edit <code>public/index.html</code> to get started.</p>
</body>
</html>
"""


def effective_addons(options: dict) -> list[str]:
    requested = list(options.get("addons", []))
    if requested:
        raise common.ScaffoldError(
            "Static website stack does not support addons. "
            "Deploy a backend API as a separate app."
        )
    return []


def scaffold(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 1: create public/ directory with a starter index.html."""
    target_dir.mkdir(parents=True, exist_ok=True)
    public = target_dir / "public"
    public.mkdir(exist_ok=True)
    if not (public / "index.html").exists():
        common.write_file(public / "index.html", _INDEX_HTML)


def apply_glue(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 2: write deterministic Heroku glue files."""
    common.write_file(target_dir / "project.toml", _PROJECT_TOML)
    common.merge_gitignore(target_dir, common.BASE_GITIGNORE + gitignore_lines(options))


def secret_env_vars(options: dict) -> list[str]:
    return []


def gitignore_lines(options: dict) -> list[str]:
    return [".DS_Store"]
