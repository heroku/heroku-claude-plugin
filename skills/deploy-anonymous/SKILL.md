---
name: deploy-anonymous
description: >-
  Deploy an app to Heroku. Use when the user says "deploy the app", "deploy it",
  "push to Heroku", "make it live", "ship it", or similar. Uses the mcp-portal
  MCP server to create a preview app, provision addons, and deploy via git push.
argument-hint: "[target-dir]"
allowed-tools: Bash, Read, Task, mcp__plugin_heroku-plugin_mcp-portal__create_anonymous_session, mcp__plugin_heroku-plugin_mcp-portal__check_anonymous_session_state, mcp__plugin_heroku-plugin_mcp-portal__create_preview_app, mcp__plugin_heroku-plugin_mcp-portal__create_addon, mcp__plugin_heroku-plugin_mcp-portal__get_addon_status, mcp__plugin_heroku-plugin_mcp-portal__get_deployment_status, mcp__plugin_heroku-plugin_mcp-portal__get_build_output, mcp__plugin_heroku-plugin_mcp-portal__check_claim_status
---

# Deploy to Heroku (Anonymous Preview)

## Step 1 — Verify prerequisites

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --quick --json
```

Gate on: `git: true`. Heroku CLI login is not required for the MCP deploy path.
If git check fails, surface the preflight error and stop.

## Step 2 — Verify scaffolded app

Check that the target directory exists and contains:
- `Procfile` with `web:` process
- `project.toml` (CNB buildpack specification — required)
- `.heroku-plugin-scaffold.json` (source of truth for addons and secret_env_vars)
- `.git/` directory (git repo initialized with at least one commit)

Read `.heroku-plugin-scaffold.json` now. You will need `addons` and `secret_env_vars` in later steps.

If any file is missing, suggest running `/heroku-plugin:scaffold-app` first.

## Step 3 — Create anonymous session

```
Tool: create_anonymous_session
Input: {}
Output: { conversation_id, tos_url, tos_status }
```

Surface the ToS URL to the user:

```
Before we deploy, you need to accept the Heroku Terms of Service:

  👉 [tos_url]

Open that link in your browser and accept. I'll wait.
```

Store `conversation_id` — thread it into every subsequent MCP call.

## Step 4 — Poll for ToS acceptance

```
Tool: check_anonymous_session_state
Input: { conversation_id }
Output: { tos_status: "pending" | "accepted" }
```

Poll every 5 seconds until `tos_status === "accepted"`. Show progress:
```
Waiting for Terms of Service acceptance... (checking every 5s)
```

Once accepted, confirm to the user and proceed.

## Step 5 — Create preview app

```
Tool: create_preview_app
Input: { conversation_id }
Output: { app_uuid, web_url, git_url, git_credentials: { token, expires_at }, mcp_credentials }
```

- Store `app_uuid` — required for all remaining MCP calls
- Store `git_url` and `git_credentials.token` — used in Step 8
- Do **not** surface `web_url` from this step — it is the raw `*.herokuapp.com` address, not the link to give the user
- `git_credentials` expire quickly — proceed through Steps 6 and 7 without delay

## Step 6 — Provision addons

Read the `addons` array from `.heroku-plugin-scaffold.json`. If empty, skip this step.

For each addon slug, provision and wait for readiness:

```
Tool: create_addon
Input: { app_uuid, service }
Output: { addon_id, name, plan, state, config_vars }
```

Then poll until ready:

```
Tool: get_addon_status
Input: { app_uuid, addon_id }
Output: { ready: boolean, config_vars }
```

Poll every 5 seconds until `ready: true`. Show progress to the user.

**Service slug mapping** (pass exactly these values as `service`):
| `.heroku-plugin-scaffold.json` slug | MCP `service` value |
|---|---|
| `heroku-postgresql` | `heroku-postgresql` |
| `heroku-redis` | `heroku-redis` |

If `create_addon` returns `isError: true`, surface the error and ask the user whether to
continue without the addon or stop.

## Step 7 — Set secrets [CLI — hybrid step]

Read `secret_env_vars` from `.heroku-plugin-scaffold.json`. If empty, skip this step.

For each name, generate and set a secret before pushing:

```bash
heroku config:set <NAME>=$(python3 -c 'import secrets; print(secrets.token_hex(32))') --app <app_uuid>
```

The `app_uuid` works as the `--app` identifier. This step requires the Heroku CLI and an
active `heroku login` session.

Common values: `DJANGO_SECRET_KEY` (Django), `RAILS_MASTER_KEY` (Rails).

## Step 8 — Push source

The git push triggers the Heroku CNB build. Use `git_credentials.token` for HTTP basic auth:

```bash
cd <target_dir>
git push https://heroku:<git_credentials.token>@<git_url_host_and_path> HEAD:main 2>&1
```

Reconstruct the authenticated URL from `git_url`:
- `git_url` example: `https://git.heroku.com/floating-plateau-8391.git`
- Authenticated form: `https://heroku:<token>@git.heroku.com/floating-plateau-8391.git`

Capture the full push output. Grep it for the build ID — Heroku emits it in the remote
output during the push. Look for patterns like:
- `remote: Build UUID: <uuid>`
- A line containing a UUID after `Build` or `build_id`

Store the `build_id` for Step 9.

If the push fails with a credential error, surface the full output and stop.

**Fallback for build_id:** If the push output does not contain a parseable build ID, run:
```bash
heroku builds --app <app_uuid> --json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])"
```

## Step 9 — Monitor build

```
Tool: get_deployment_status
Input: { app_uuid, build_id }
Output: { web_url, expires_at, build: { done, failed, log }, database }
```

Poll every 10 seconds until `build.done === true`. Show progress:
```
Building... (checking every 10s)
```

If `build.failed === true`:
- Surface the tail of `build.log` (last 30 lines) to the user
- Stop — do not proceed to Step 10
- Suggest checking the Procfile, requirements, or build errors shown

Store `web_url` and `expires_at` from the response — needed for Steps 10 and 11.

Note: `web_url` from `get_deployment_status` is the **claim portal URL**
(`https://claim-canary.heroku.com/preview/<app_uuid>`). This IS the link to give the user.

## Step 10 — Save session state

Write to `.heroku-plugin-session.json` in target_dir:
```json
{
  "app_uuid":    "<app_uuid>",
  "app_url":     "<web_url from get_deployment_status>",
  "expires_at":  <expires_at>,
  "stack":       "<stack from .heroku-plugin-scaffold.json>",
  "target_dir":  "<path>",
  "deployed_at": "<ISO8601 timestamp>"
}
```

## Step 11 — Surface result to user

```
✓ Your app is live!

  Preview URL: <web_url>

  Open that link to see your app and claim it as your own Heroku account.
  The claim window is open for 1 hour.
```

Do not surface the raw `*.herokuapp.com` URL — the claim portal URL is the correct link.

## Step 12 — Monitor claim (background)

```
Tool: check_claim_status
Input: { app_uuid, expires_at }
Output: { claimed: boolean, expired: boolean }
```

Poll every 30 seconds. When the state changes:

- `claimed: true` → "App claimed! It's now yours on Heroku."
- `expired: true` → "The claim window closed. The preview app has been removed. Run deploy again to create a new one."
