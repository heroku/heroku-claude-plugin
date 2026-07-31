<!-- Source: https://devcenter.heroku.com/articles/how-heroku-works — verified 2026-07-30 -->

# Heroku Deploy Contract

Every app scaffolded by this plugin must satisfy all items in this contract.

## Required Files

| File | Required | Purpose |
|------|----------|---------|
| `Procfile` | Yes | Defines process types; `web:` must be present |
| `app.json` | Yes | Heroku manifest (addons, env, buildpacks, formation) |
| Buildpack marker | Yes | Language-specific (see below) |
| `.gitignore` | Yes | Excludes secrets, build artifacts, local env files |

## Buildpack Markers (Required per Stack)

| Stack | Required file(s) |
|-------|-----------------|
| Node.js | `package.json` + lockfile |
| Python | `requirements.txt` + `.python-version` |
| Ruby | `Gemfile` + `Gemfile.lock` |
| Go | `go.mod` + `go.sum` |

## $PORT Binding

The `web:` process **must** bind to the `$PORT` environment variable. Heroku assigns this dynamically — never hardcode a port.

```
# Correct
web: gunicorn app:app --bind 0.0.0.0:$PORT

# Wrong
web: gunicorn app:app --bind 0.0.0.0:5000
```

## Process Types

| Type | Required | Notes |
|------|----------|-------|
| `web` | Yes | Receives HTTP traffic; must bind to $PORT |
| `release` | If DB | Run migrations before dynos start |
| `worker` | No | Background jobs; scaled independently |

## Addon Wiring

When addons are declared in `app.json`, the app must be written to use their config vars:

| Addon | Config var the app must read |
|-------|------------------------------|
| `heroku-postgresql` | `DATABASE_URL` |
| `heroku-redis` | `REDIS_URL` (must use TLS — `rediss://`) |

## Secrets

- Never commit `.env`, `config/master.key`, or any file containing secrets
- Use `app.json` `env` with `"generator": "secret"` for generated secrets
- Manual config vars: `heroku config:set KEY=value`

## Stack

Default stack: `heroku-24` (Ubuntu 24.04). Specify in `app.json` as `"stack": "heroku-24"`.

## Anonymous Deploy Constraints

During anonymous deployment (pre-claim):
- Addons are provisioned (`heroku-postgresql`, `heroku-redis` supported)
- `public_routing` is set to `false` — app URL is not publicly accessible
- App is transferred to user account on claim
- After claim: `public_routing` can be set to `true`
