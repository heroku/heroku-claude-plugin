---
name: deploy-anonymous
description: >-
  Deploy an app to Heroku. Use when the user says "deploy the app", "deploy it",
  "push to Heroku", "make it live", "ship it", or similar. Uses the Heroku CLI
  to create the app, provision addons, and push code via git.
argument-hint: "[app-name] [target-dir]"
allowed-tools: Bash, Read, Task
---

# Deploy to Heroku

<!-- TODO: This skill uses the Heroku CLI. Replace with MCP tool calls
     (create_preview_app, prepare_deployment, update_deployment) once the
     connector-mcp anonymous deploy implementation is available. -->

## Step 1 — Verify prerequisites

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --quick --json
```

Gate on: `git: true`, `heroku: true`, `heroku_logged_in: true`.
If any fail, surface the preflight error and stop.

## Step 2 — Verify scaffolded app

Check that the target directory exists and contains:
- `Procfile` with `web:` process
- `app.json`
- `.git/` directory (git repo initialized)

If missing, suggest running `/heroku-plugin:scaffold-app` first.

## Step 3 — Determine app name

Use the `app_name` from session state (`.heroku-plugin-session.json`) if present,
otherwise derive from the directory name or ask the user.

## Step 4 — Create Heroku app

```bash
heroku create <app-name> --no-remote
```

If the name is taken, suggest `<app-name>-<random-suffix>` and confirm with user.

Parse the output for the app URL and Git URL:
```
Creating ⬢ <app-name>... done
https://<app-name>.herokuapp.com/ | https://git.heroku.com/<app-name>.git
```

## Step 5 — Apply app.json configuration

`heroku create --no-remote` does **not** process `app.json` — generators, buildpacks, and env
entries are only applied during Heroku Button / `heroku create --manifest` deploys. Apply them
manually in this order:

### 5a — Set env vars from generators

Read `app.json` and look for env entries with `"generator": "secret"`. For each one, generate
and set the value before pushing:

```bash
# For each env var with "generator": "secret" in app.json:
heroku config:set <KEY>=$(python3 -c 'import secrets; print(secrets.token_hex(32))') --app <app-name>
```

Common examples: `DJANGO_SECRET_KEY`, `SECRET_KEY_BASE` (Rails), `SECRET_KEY` (Flask).

### 5b — Apply buildpacks

Read `app.json` and look for the `buildpacks` array. Apply each in order:

```bash
# For each buildpack in app.json buildpacks array (in order):
heroku buildpacks:add --index <N> <url> --app <app-name>
```

Example — Node.js app:
```bash
heroku buildpacks:add --index 1 heroku/nodejs --app <app-name>
```

Example — Vue.js + Python (multi-buildpack):
```bash
heroku buildpacks:add --index 1 heroku/nodejs --app <app-name>
heroku buildpacks:add --index 2 heroku/python --app <app-name>
```

If `app.json` has no `buildpacks` array, Heroku will auto-detect. Skip this step.

**For any app that includes a Node.js build step** (Vue, React, or any frontend that runs `npm run build`):
set `NPM_CONFIG_PRODUCTION=false` before pushing. Heroku sets `NODE_ENV=production` by default,
which causes `npm install` to skip `devDependencies` — Vite, Vue CLI, and other build tools are
devDependencies and will not be installed, breaking the build.

```bash
heroku config:set NPM_CONFIG_PRODUCTION=false --app <app-name>
```

This is safe — it only affects the build phase, not the runtime.

### 5c — Provision addons

For each addon in the `addons` array, provision it:

```bash
# heroku-postgresql
heroku addons:create heroku-postgresql:essential-0 --app <app-name> --wait

# heroku-redis
heroku addons:create heroku-redis:mini --app <app-name> --wait
```

Use `--wait` to block until provisioning completes. Surface progress to the user.

If addon provisioning fails, surface the error and ask the user whether to proceed
without the addon or stop.

## Step 6 — Set git remote and push

```bash
cd <target_dir>
heroku git:remote --app <app-name>
```

`heroku git:remote` sets the remote to HTTPS (`https://git.heroku.com/<app>.git`). On some
machines the git credential helper is not configured to supply Heroku credentials, causing
`git push` to fail with "could not read Username". Avoid this by embedding the token in the
remote URL before pushing:

```bash
HEROKU_API_KEY=$(heroku auth:token 2>/dev/null | tail -1)
git remote set-url heroku "https://heroku:${HEROKU_API_KEY}@git.heroku.com/<app-name>.git"
git push heroku main
```

If `main` branch doesn't exist, try `master`:
```bash
git push heroku master:main
```

Surface the git push output so the user can see the build logs in real time.

## Step 7 — Save session state

Write to `.heroku-plugin-session.json` in target_dir:
```json
{
  "app_name":    "<app-name>",
  "app_url":     "https://<app-name>.herokuapp.com",
  "stack":       "<stack>",
  "target_dir":  "<path>",
  "deployed_at": "<ISO8601>"
}
```

Export env vars for PreCompact hook:
`HEROKU_APP_NAME`, `HEROKU_STACK`, `HEROKU_TARGET_DIR`

## Step 8 — Hand off to check-deploy-status

```
Task(
  subagent_type: "check-deploy-status",
  description: "Verify deployment succeeded",
  prompt: "Check deployment status for app '<app-name>' at '<target_dir>'."
)
```
