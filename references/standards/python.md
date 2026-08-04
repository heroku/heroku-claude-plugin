# Python Coding Standards

*Idiomatic Python: readable, explicit, and simple*

---

## Core Philosophy

- **Readability counts**: Code is read more than it is written — optimize for the reader
- **Explicit over implicit**: Never rely on hidden behavior or magic
- **Simple over complex**: If you can't explain it simply, the design needs work
- **Standard library first**: Reach for stdlib before adding a dependency

---

## Code Style

### Formatting
- Use `ruff format` — line length 88, enforced
- Use `ruff check` with rules: `E`, `F`, `I`, `N`, `S`, `UP`
- Run both before every commit — never commit with lint errors

### Naming
- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- `SCREAMING_SNAKE_CASE` for module-level constants
- Prefix private helpers with `_`; avoid double-underscore unless you need name mangling

### Type hints
- Always annotate function signatures (parameters + return type)
- Use `from __future__ import annotations` for forward references
- Prefer `X | None` over `Optional[X]` (Python 3.10+)
- Use `list[str]` not `List[str]`, `dict[str, int]` not `Dict[str, int]`

---

## Testing (TDD)

- **Write the failing test first**, then implement
- Use `pytest` — place tests in `tests/` named `test_*.py`
- **Minimum 90% coverage** — `pytest --cov=. --cov-fail-under=90`
- Test behavior, not implementation — test what the function does, not how
- One assertion concept per test; use descriptive test names
- FastAPI: use `TestClient` from `fastapi.testclient` (requires `httpx`)
- Django: use Django's `TestCase` or `pytest-django`
- Flask: use `app.test_client()`

```python
# Good — tests behavior
def test_catalog_returns_only_active_items(client):
    response = client.get("/api/catalog/")
    assert response.status_code == 200
    assert all(item["active"] for item in response.json())

# Bad — tests implementation detail
def test_catalog_calls_query_filter(mock_db):
    ...
```

---

## Code Quality

### Functions
- One responsibility per function — if you need "and" to describe it, split it
- Keep functions short — if it doesn't fit on a screen, reconsider the design
- No side effects in functions that return values

### Error handling
- Never silence exceptions with bare `except:` or `except Exception: pass`
- Use specific exception types
- Fail loudly at system boundaries; log with context

### Security
- Never hardcode secrets — read from `os.environ` only
- Validate all external input at the boundary
- Use `ruff S` rules — they catch common security anti-patterns
- Database: always use parameterized queries, never string interpolation

### Dependencies
- Pin versions in `requirements.txt`
- Separate dev dependencies (testing, linting) from runtime dependencies
- Prefer packages with active maintenance and small dependency trees

---

## Database (SQLAlchemy + Alembic)

- Always wire `DATABASE_URL` from `os.environ` — never hardcode
- Generate migrations against an **empty database** — never against one that already has the schema
- Inspect every generated migration before committing — an empty `upgrade()` is always wrong
- `release:` process in Procfile must run `alembic upgrade head` before app starts

---

## FastAPI Route Ordering

**`app.mount()` must always be the last call in `main.py`.** StaticFiles mounts shadow any routes registered after them — all unmatched paths are served as 404 from the static directory instead of reaching your API handlers.

```python
# Correct — mount static files LAST
app = FastAPI()

@app.get("/api/items")        # registered first
def get_items(): ...

app.mount("/", StaticFiles(...))  # LAST — must be after all API routes
```

```python
# Wrong — mount before API routes, /api/* will be shadowed
app = FastAPI()
app.mount("/", StaticFiles(...))  # TOO EARLY

@app.get("/api/items")        # never reached
def get_items(): ...
```

---

## Heroku-Specific

- See `references/stacks/python.md` for Procfile patterns, buildpack config, and gotchas
- `DEBUG=False` in production — set via Heroku config var
- All secrets via `heroku config:set` — never in code or committed files
