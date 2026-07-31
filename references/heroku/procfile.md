<!-- Source: https://devcenter.heroku.com/articles/procfile — verified 2026-07-30 -->

# Procfile

## Location and Naming

- Root directory of the repo
- Filename: `Procfile` (exact, no extension, case-sensitive)

## Syntax

```
<process-type>: <command>
```

## Standard Process Types

### `web` (required for HTTP traffic)

Must bind to `$PORT` — Heroku assigns the port dynamically.

```
web: bundle exec puma -p $PORT
web: gunicorn app:app
web: npm start
web: ./bin/myapp
```

### `release` (runs once during release phase)

Executes before new dynos are started. Use for migrations and one-time setup.

```
release: python manage.py migrate
release: bundle exec rails db:migrate
```

### `worker` (background processes)

Scaled independently from web.

```
worker: bundle exec sidekiq
worker: celery -A app worker
```

## Key Rules

- `$PORT` is dynamically assigned — never hardcode a port
- `web` process is required to receive HTTP traffic
- `release` process failure blocks the deploy
- Multiple process types are separated by newlines, one per line
- No tabs — use a single space after the colon
