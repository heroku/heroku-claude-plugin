<!-- Source: https://devcenter.heroku.com/articles/how-heroku-works — verified 2026-07-30 -->

# Heroku Deploy Contract

Every app scaffolded by this plugin must satisfy all items in this contract.

## Required Files

| File | Required | Purpose |
|------|----------|---------|
| `Procfile` | Yes | Defines process types; `web:` must be present |
| `project.toml` | Yes | CNB on Cedar: declares buildpack + `heroku/procfile`; omits builder (Kodon selects it) |
| `.heroku-plugin-scaffold.json` | Yes | Scaffold summary: addons + secret env vars for deploy skill |
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

When addons are declared in `.heroku-plugin-scaffold.json`, the app must be written to use their config vars:

| Addon | Config var the app must read |
|-------|------------------------------|
| `heroku-postgresql` | `DATABASE_URL` |
| `heroku-redis` | `REDIS_URL` (must use TLS — `rediss://`) |

## Secrets

- Never commit `.env`, `config/master.key`, or any file containing secrets
- Generated secrets: declare names in `.heroku-plugin-scaffold.json` `secret_env_vars` array;
  the `deploy-anonymous` skill generates values with `python3 -c 'import secrets; ...'` and
  sets them via `heroku config:set --app <app_uuid>`
- Manual config vars: `heroku config:set KEY=value --app <app_uuid>`

## Stack

Default stack: CNB on Cedar. The mcp-portal `create_preview_app` tool sets `stack: "cnb"` at
app creation time. `project.toml` declares the buildpack group — no `builder` field (Kodon
selects the builder automatically).

## Anonymous Deploy Constraints

During anonymous deployment (pre-claim):
- App is created by the mcp-portal server using its platform token — not the user's Heroku account
- Addons are provisioned via `create_addon` MCP tool (`heroku-postgresql`, `heroku-redis` supported)
- App URL visible to the user is the claim portal URL returned as `web_url` from `get_deployment_status`
- Claim window: 60 minutes from app creation (default)
- App is transferred to user account when they claim it via the portal
- After claim: app moves to user's Heroku account; addons become billable
