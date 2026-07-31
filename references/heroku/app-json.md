<!-- Source: https://devcenter.heroku.com/articles/app-json-schema — verified 2026-07-30 -->

# app.json Schema

Heroku app manifest. Used by Review Apps, Deploy Button, and the plugin to declare infrastructure.

## Minimal Example

```json
{
  "name": "my-app",
  "description": "A Heroku app",
  "buildpacks": [{ "url": "heroku/python" }],
  "addons": ["heroku-postgresql"],
  "env": {
    "SECRET_KEY": { "generator": "secret" }
  },
  "formation": {
    "web": { "quantity": 1, "size": "basic" }
  }
}
```

## Fields

### `name` (string)

App name. Max 30 characters.

### `description` (string)

Brief summary shown in dashboard.

### `buildpacks` (array)

```json
"buildpacks": [{ "url": "heroku/python" }]
```

For Cedar (classic) apps only. Use `project.toml` for Fir (CNB) apps.

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
