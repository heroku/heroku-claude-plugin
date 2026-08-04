<!-- Source: https://devcenter.heroku.com/articles/python-support — verified 2026-07-30 -->

# Python on Heroku

## Supported Versions

| Version | Status |
|---------|--------|
| 3.14 | Default (Heroku) |
| 3.13 | Supported |
| 3.12 | Supported |
| 3.11 | Supported |
| 3.10 | Deprecated |

Specify version in `.python-version` (recommended) or legacy `runtime.txt`:
```
python-3.12.0
```

**Local venv gotcha — Python 3.14:** pydantic-core (used by FastAPI) requires Python ≤ 3.13 due
to pyo3 limitations. If `python3` on the user's machine resolves to 3.14 (e.g. homebrew default),
`pip install` will fail building pydantic-core wheels. Before creating the local venv, check:

```bash
python3 --version
```

If 3.14+, use the 3.13 binary explicitly:
```bash
brew install python@3.13   # if not already installed
/opt/homebrew/opt/python@3.13/bin/python3.13 -m venv .venv
```

The `.python-version` file scaffolded by this plugin pins 3.12 — correct for Heroku — but does
not affect which binary is used for local venv creation.

## Required Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `.python-version` | Python version pin |
| `Procfile` | Process types |

## Variants

### FastAPI

```
# requirements.txt (minimum)
fastapi
uvicorn[standard]
gunicorn

# Procfile
web: gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

### Django

```
# requirements.txt (minimum)
django
gunicorn
whitenoise
psycopg2-binary   # if using Postgres

# Procfile
web: gunicorn <project>.wsgi --bind 0.0.0.0:$PORT
release: python manage.py migrate
```

Static files: Use `whitenoise` middleware — do not rely on `collectstatic` to serve files in production without it.

### Flask

```
# requirements.txt (minimum)
flask
gunicorn

# Procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

## Buildpack

Auto-detected from `requirements.txt`. Explicit: `heroku/python`

## Heroku-Specific Gotchas

- Always specify Python version — never rely on the default changing under you
- `3.10` is deprecated; scaffold with `3.12` minimum
- Django: set `ALLOWED_HOSTS` to include `.herokuapp.com` or use `DJANGO_ALLOWED_HOSTS` env var
- Django: `DEBUG=False` in production; set via Heroku config var
- Postgres TLS: `psycopg2` connects via `DATABASE_URL`; Heroku Postgres uses self-signed certs — set `sslmode=require` in connection string or Django's `DATABASES` config

## Best Practices

### Formatting & Linting

Use `ruff` for both linting and formatting (replaces flake8, black, isort):

```bash
pip install ruff
ruff check .       # lint
ruff format .      # format
```

Configure in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "S", "UP"]  # errors, pyflakes, isort, naming, security, pyupgrade
ignore = ["S101"]  # allow assert in tests
```

### Testing

Use `pytest`. Place tests in `tests/` named `test_*.py`:

```bash
pip install pytest pytest-cov
pytest tests/
pytest --cov=. tests/   # with coverage
```

FastAPI apps use `fastapi.testclient.TestClient` (requires `httpx`).
Flask apps use `app.test_client()`.
Django apps use Django's built-in test runner.

### Security

- Never commit `.env` files or secrets — use `heroku config:set`
- All secrets read from `os.environ` only — never hardcoded
- `DEBUG=False` in production — enforced via Heroku config var
- Postgres: always use `DATABASE_URL` from env; `sslmode=require` is set by Heroku automatically
- Ruff `S` rules catch common security anti-patterns (hardcoded passwords, insecure random, shell injection)

### Code Quality

- Functions do one thing; if you need to describe what a function does, it should be split
- No commented-out code committed
- Prefer explicit imports over `import *`
- Keep endpoints thin — business logic in service/helper modules, not in route handlers

### Pre-commit

A `.pre-commit-config.yaml` is scaffolded into every app. Install once per clone:

```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on `git commit`: ruff lint + format, secret detection, large file check.
