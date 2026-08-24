"""Python stack module — supports FastAPI, Django, and Flask variants."""

from pathlib import Path

from . import common

STACK = "python"
DISPLAY_NAME = "Python"
REQUIRED_TOOLS = [
    ("python3", "https://www.python.org/downloads/"),
]
DEFAULT_ADDONS: list[str] = []

VARIANTS = ("fastapi", "django", "flask")
DEFAULT_VARIANT = "fastapi"

PYTHON_VERSION = "3.12"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_FASTAPI_MAIN = """\
import os

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def index():
    return {"status": "ok", "message": "Hello from FastAPI on Heroku!"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
"""

_FASTAPI_REQUIREMENTS = """\
fastapi
uvicorn[standard]
gunicorn
"""

_FLASK_APP = """\
import os

from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return {"status": "ok", "message": "Hello from Flask on Heroku!"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
"""

_FLASK_REQUIREMENTS = """\
flask
gunicorn
"""

_DOCKERIGNORE = """\
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.env.*
dist/
build/
.pytest_cache/
"""

_PRECOMMIT_CONFIG = """\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: end-of-file-fixer
      - id: trailing-whitespace
"""

_PYPROJECT_TOML = """\
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "S", "UP"]
ignore = ["S101"]
"""


# ---------------------------------------------------------------------------
# Module protocol
# ---------------------------------------------------------------------------

def effective_addons(options: dict) -> list[str]:
    variant = options.get("variant", DEFAULT_VARIANT)
    defaults = ["postgres"] if variant == "django" else []
    module_defaults = DEFAULT_ADDONS + defaults
    all_addons = module_defaults + list(options.get("addons", []))
    return common.resolve_addons(all_addons) if all_addons else []


def scaffold(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 1: create minimal Python project structure."""
    variant = options.get("variant", DEFAULT_VARIANT)
    target_dir.mkdir(parents=True, exist_ok=True)

    if variant == "django":
        common.require_tools([("django-admin", "https://www.djangoproject.com/download/")])
        common.run(["django-admin", "startproject", "config", str(target_dir)])
    # fastapi and flask: no native scaffolder — we write files directly in apply_glue


def apply_glue(app_name: str, target_dir: Path, options: dict) -> None:
    """Layer 2: write deterministic Heroku glue files."""
    variant = options.get("variant", DEFAULT_VARIANT)
    addons = effective_addons(options)

    # Python version pin
    common.write_file(target_dir / ".python-version", PYTHON_VERSION)

    if variant == "fastapi":
        _apply_fastapi(app_name, target_dir, addons)
    elif variant == "flask":
        _apply_flask(app_name, target_dir, addons)
    elif variant == "django":
        _apply_django(app_name, target_dir, addons)
    else:
        raise common.ScaffoldError(f"Unknown Python variant '{variant}'. Choose: fastapi, django, flask.")

    common.write_file(target_dir / "project.toml", common.build_project_toml("heroku/python"))

    # Shared .gitignore
    common.merge_gitignore(target_dir, common.BASE_GITIGNORE + gitignore_lines(options))

    # Pre-commit config
    common.write_file(target_dir / ".pre-commit-config.yaml", _PRECOMMIT_CONFIG)
    common.write_file(target_dir / "pyproject.toml", _PYPROJECT_TOML)

    # docker-compose if Docker available
    if options.get("with_docker"):
        _write_dockerfile(target_dir, variant)
        common.write_docker_compose(target_dir, app_name, addons)


def gitignore_lines(options: dict) -> list[str]:
    return [
        "__pycache__/",
        "*.py[cod]",
        ".venv/",
        "venv/",
        "*.egg-info/",
        ".pytest_cache/",
        "dist/",
    ]


# ---------------------------------------------------------------------------
# Variant helpers
# ---------------------------------------------------------------------------

def _apply_fastapi(app_name: str, target_dir: Path, addons: list[str]) -> None:
    common.write_file(target_dir / "main.py", _FASTAPI_MAIN)

    reqs = list(_FASTAPI_REQUIREMENTS.strip().splitlines())
    if "heroku-postgresql" in addons:
        reqs += ["sqlalchemy", "psycopg2-binary", "alembic"]
    if "heroku-redis" in addons:
        reqs += ["redis"]
    common.write_file(target_dir / "requirements.txt", "\n".join(sorted(reqs)))

    common.write_file(
        target_dir / "Procfile",
        f"web: gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT",
    )

    env = {}
    if "heroku-postgresql" in addons:
        env["DATABASE_URL"] = {"description": "Heroku Postgres connection string", "required": True}
    if "heroku-redis" in addons:
        env["REDIS_URL"] = {"description": "Heroku Redis connection string", "required": True}

    app_json = common.build_app_json(
        app_name,
        buildpack="heroku/python",
        addons=addons,
        env=env if env else None,
        formation={"web": {"quantity": 1, "size": "basic"}},
    )
    common.write_json(target_dir / "app.json", app_json)


def _apply_flask(app_name: str, target_dir: Path, addons: list[str]) -> None:
    common.write_file(target_dir / "app.py", _FLASK_APP)

    reqs = list(_FLASK_REQUIREMENTS.strip().splitlines())
    if "heroku-postgresql" in addons:
        reqs += ["flask-sqlalchemy", "psycopg2-binary"]
    if "heroku-redis" in addons:
        reqs += ["redis"]
    common.write_file(target_dir / "requirements.txt", "\n".join(sorted(reqs)))

    common.write_file(target_dir / "Procfile", f"web: gunicorn app:app --bind 0.0.0.0:$PORT")

    env = {}
    if "heroku-postgresql" in addons:
        env["DATABASE_URL"] = {"description": "Heroku Postgres connection string", "required": True}
    if "heroku-redis" in addons:
        env["REDIS_URL"] = {"description": "Heroku Redis connection string", "required": True}

    app_json = common.build_app_json(
        app_name,
        buildpack="heroku/python",
        addons=addons,
        env=env if env else None,
        formation={"web": {"quantity": 1, "size": "basic"}},
    )
    common.write_json(target_dir / "app.json", app_json)


def _apply_django(app_name: str, target_dir: Path, addons: list[str]) -> None:
    # Patch settings.py for Heroku: ALLOWED_HOSTS, DATABASES, STATIC
    settings_path = target_dir / "config" / "settings.py"
    if settings_path.exists():
        settings = settings_path.read_text(encoding="utf-8")
        patches = [
            ("ALLOWED_HOSTS = []", "ALLOWED_HOSTS = ['.herokuapp.com', 'localhost']"),
            (
                "DATABASES = {",
                "import os\nimport dj_database_url\n\nDATABASES = {\n    'default': dj_database_url.config(conn_max_age=600)\n}\n\n_ORIGINAL_DATABASES = {",
            ),
        ]
        for old, new in patches:
            if old in settings and new.split("\n")[-1] not in settings:
                settings = settings.replace(old, new, 1)
        common.write_file(settings_path, settings)

    reqs = ["django", "gunicorn", "whitenoise", "dj-database-url"]
    if "heroku-postgresql" in addons:
        reqs.append("psycopg2-binary")
    if "heroku-redis" in addons:
        reqs.append("redis")
    common.write_file(target_dir / "requirements.txt", "\n".join(sorted(reqs)))

    common.write_file(
        target_dir / "Procfile",
        "web: gunicorn config.wsgi --bind 0.0.0.0:$PORT\nrelease: python manage.py migrate",
    )

    env = {
        "DJANGO_SECRET_KEY": {"generator": "secret"},
        "DJANGO_DEBUG": {"value": "False"},
    }
    if "heroku-postgresql" in addons:
        env["DATABASE_URL"] = {"description": "Heroku Postgres connection string", "required": True}
    if "heroku-redis" in addons:
        env["REDIS_URL"] = {"description": "Heroku Redis connection string", "required": True}

    app_json = common.build_app_json(
        app_name,
        buildpack="heroku/python",
        addons=addons,
        env=env,
        formation={"web": {"quantity": 1, "size": "basic"}},
    )
    common.write_json(target_dir / "app.json", app_json)


def _write_dockerfile(target_dir: Path, variant: str) -> None:
    if variant == "fastapi":
        entry = "gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}"
    elif variant == "flask":
        entry = "gunicorn app:app --bind 0.0.0.0:${PORT:-5000}"
    else:
        entry = "gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000}"

    dockerfile = f"""\
FROM python:{PYTHON_VERSION}-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
EXPOSE $PORT
CMD {entry}
"""
    common.write_file(target_dir / "Dockerfile", dockerfile)
    common.write_file(target_dir / ".dockerignore", _DOCKERIGNORE)
