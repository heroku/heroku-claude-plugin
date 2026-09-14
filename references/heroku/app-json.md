<!-- Source: https://devcenter.heroku.com/articles/app-json-schema — verified 2026-09-10 -->

# app.json Schema

Heroku app manifest. Used by Review Apps, Deploy Button, and the plugin to declare infrastructure.

## Minimal Example

```json
{
  "name": "my-app",
  "description": "A Heroku app",
  "stack": "heroku-24",
  "addons": ["heroku-postgresql"],
  "env": {
    "SECRET_KEY": { "generator": "secret" }
  },
  "formation": {
    "web": { "quantity": 1, "size": "basic" }
  }
}
```

Note: no `buildpacks` key — buildpack specification is handled by `project.toml` (CNB on Cedar).

## Fields

### `name` (string)

App name. Max 30 characters.

### `description` (string)

Brief summary shown in dashboard.

### `buildpacks` (array)

**Do not use in this plugin.** Buildpack specification is handled by `project.toml` (CNB on Cedar).
The `buildpacks` key is omitted from all scaffolded `app.json` files. Including it is a bug, not a fix.

### `addons` (array)

```json
"addons": [
  "heroku-postgresql",
  { "plan": "heroku-redis:mini", "as": "CACHE" }
]
```

- String form uses default plan for the addon
- Object form allows specifying `plan`, `as` (custom attachment/var name), `options`

### `env` (object)

```json
"env": {
  "SECRET_TOKEN": { "description": "...", "generator": "secret" },
  "WEB_CONCURRENCY": { "value": "5" },
  "FEATURE_FLAG": { "value": "false", "required": false }
}
```

Properties: `description`, `value`, `required` (bool), `generator` ("secret")

### `formation` (object)

```json
"formation": {
  "web": { "quantity": 1, "size": "basic" },
  "worker": { "quantity": 1, "size": "basic" }
}
```

### `scripts` (object)

```json
"scripts": {
  "postdeploy": "python manage.py migrate"
}
```

### `stack` (string)

```json
"stack": "heroku-24"
```

Default is `heroku-24`. Also available: `heroku-26`.

## Addon Slugs (Plugin Supported)

| Addon | Slug | Config Var |
|-------|------|------------|
| Postgres | `heroku-postgresql` | `DATABASE_URL` |
| Redis / Key-Value | `heroku-redis` | `REDIS_URL` |

## Determinism Rules (Layer 2)

- `sort_keys=True` when writing JSON
- Addon list: sorted and deduplicated
- `indent=2`, UTF-8, LF newlines, one trailing newline
