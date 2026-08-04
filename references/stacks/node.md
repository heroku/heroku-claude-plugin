<!-- Source: https://devcenter.heroku.com/articles/nodejs-support — verified 2026-07-30 -->

# Node.js on Heroku

## Supported Versions

| Version | Status |
|---------|--------|
| 26.x | Current |
| 24.x | Active LTS (recommended for production) |
| 22.x | Maintenance LTS |

Specify version in `package.json`:
```json
{
  "engines": {
    "node": "24.x"
  }
}
```

Default: 24.x if not specified.

## Required Files

| File | Purpose |
|------|---------|
| `package.json` | Dependencies + scripts + engines |
| `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` | Lockfile (one required) |
| `Procfile` | Process types (or use `npm start`) |

## Procfile

```
web: npm start
```

Or if you have a custom start command:
```
web: node server.js
```

App must bind to `process.env.PORT`.

## package.json start script

```json
{
  "scripts": {
    "start": "node server.js"
  }
}
```

## Package Managers

| Manager | Lockfile | Notes |
|---------|----------|-------|
| npm | `package-lock.json` | Default |
| pnpm | `pnpm-lock.yaml` | Requires `"packageManager"` field in package.json |
| Yarn | `yarn.lock` | Yarn 1.22.x default |

## Buildpack

Auto-detected from `package.json`. Explicit: `heroku/nodejs`

## Frontend (Vue.js / React / etc.)

Heroku has no Vue buildpack. Options:
1. **Python/Node serves built Vue static files** — single app, build step in `package.json`
2. **Separate apps** — Node.js app for frontend, Python app for API

For this plugin, the recommended pattern is a separate `package.json` build script with the frontend built during the Heroku release phase or committed as static assets.

## Heroku-Specific Gotchas

- Always pin Node version in `engines` — never let it float
- `npm start` is the default Procfile command; if not defined, build fails
- Postgres TLS: `pg` module defaults to `ssl: false` on Heroku Postgres; set `ssl: { rejectUnauthorized: false }` or use `DATABASE_URL` with `?ssl=true`
- Use `process.env.PORT` for the HTTP listener — never hardcode
- **`devDependencies` are pruned by default**: Heroku sets `NODE_ENV=production`, which causes `npm install` to skip devDependencies. Build tools like Vite, Vue CLI, and TypeScript compiler will not be installed. Fix: `heroku config:set NPM_CONFIG_PRODUCTION=false` before the first push. This only affects the build container, not runtime.

## Best Practices

### Formatting & Linting

Use ESLint + Prettier. Scaffolded config:

```bash
npm install --save-dev eslint prettier eslint-config-prettier
```

`eslint.config.js` (flat config):

```js
import js from "@eslint/js";
import prettier from "eslint-config-prettier";

export default [js.configs.recommended, prettier];
```

`.prettierrc`:

```json
{ "singleQuote": true, "trailingComma": "es5" }
```

### Testing

Use Jest (or Vitest for ESM-first projects):

```bash
npm install --save-dev jest
```

`package.json`:

```json
{ "scripts": { "test": "jest" } }
```

Place tests in `__tests__/` or colocated as `*.test.js`.

### Security

- Use `helmet` middleware — sets secure HTTP headers:
  ```js
  const helmet = require('helmet');
  app.use(helmet());
  ```
- Never commit `.env` files — use `heroku config:set`
- All secrets via `process.env` only — never hardcoded
- Postgres: read `DATABASE_URL` from env; set `ssl: { rejectUnauthorized: false }` for Heroku Postgres
- `npm audit` before every deploy — fix high/critical before shipping

### Code Quality

- Keep route handlers thin — business logic in separate modules
- Async/await over raw Promise chains
- Explicit error handling — no silent `catch(() => {})`
- No `console.log` in production — use a logger (`pino`, `winston`) or remove before commit

### Pre-commit

`husky` + `lint-staged` are scaffolded into every app:

```bash
npm install --save-dev husky lint-staged
npx husky install
```

On `git commit`: ESLint (auto-fix), Prettier (auto-fix), secret detection run against staged files only.
