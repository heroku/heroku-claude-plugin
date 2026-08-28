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
- `git_credentials` expire quickly (~5 min) — the push (Step 8) must land inside that window. Everything between here and the push is kept to *fast* calls only (Steps 6–7); the *slow* work (addon readiness, build) is deferred to Step 9, after the push, so it never eats the credential window

> **Steps 6–9 ordering — the credential clock.** The push (Step 8) is the critical path: it
> must happen before the Step 5 token lapses (~5 min). So Steps 6 and 7 are *fast* calls only —
> set secrets, then fire addon creation without waiting. The *slow* work (addon readiness + the
> build) is deferred to Step 9 and polled concurrently, **after** the push. Never let addon
> readiness polling block the push.

## Step 6 — Set secrets [CLI — hybrid step]

Read `secret_env_vars` from `.heroku-plugin-scaffold.json`. If empty, skip this step.

Set these **before** the push — the build and release phases may consume them (e.g. Rails
`assets:precompile` needs `RAILS_MASTER_KEY`/`SECRET_KEY_BASE`; Django `collectstatic` needs
`DJANGO_SECRET_KEY`). Each is a fast call, so it costs only seconds against the credential window.

For each name, generate and set a secret:

```bash
heroku config:set <NAME>=$(python3 -c 'import secrets; print(secrets.token_hex(32))') --app <app_uuid>
```

The `app_uuid` works as the `--app` identifier. This step requires the Heroku CLI and an
active `heroku login` session.

Common values: `DJANGO_SECRET_KEY` (Django), `RAILS_MASTER_KEY` (Rails).

## Step 7 — Kick off addon provisioning (do not wait)

Read the `addons` array from `.heroku-plugin-scaffold.json`. If empty, skip this step.

For each addon slug, **fire** the provision — call `create_addon` and move straight on. Do
**not** poll `get_addon_status` here; readiness is polled in Step 9, concurrently with the
build. `create_addon` returns quickly and only *starts* provisioning, so firing it before the
push lets provisioning overlap the build — maximizing the chance the addon is ready before any
release phase runs.

```
Tool: create_addon
Input: { conversation_id, app_uuid, service }
Output: { addon_id, name, plan, state, config_vars }
```

`conversation_id` selects the anonymous provisioning path — it is required here (along with
`app_uuid` and the allowlisted `service` slug). Store each `addon_id` — Step 9 polls it for
readiness.

**Service slug mapping** (pass exactly these values as `service`):
| `.heroku-plugin-scaffold.json` slug | MCP `service` value |
|---|---|
| `heroku-postgresql` | `heroku-postgresql` |
| `heroku-redis` | `heroku-redis` |

If `create_addon` returns `isError: true`, surface the error and ask the user whether to
continue without the addon or stop.

## Step 8 — Push source

Push **immediately** after Step 7 — this is the critical path against the credential clock; do
not wait on addon readiness (that is Step 9). The git push triggers the Heroku CNB build. Use
`git_credentials.token` for HTTP basic auth:

```bash
cd <target_dir>
git push https://heroku:<git_credentials.token>@<git_url_host_and_path> HEAD:main 2>&1
```

Reconstruct the authenticated URL from `git_url`:
- `git_url` example: `https://git.heroku.com/floating-plateau-8391.git`
- Authenticated form: `https://heroku:<token>@git.heroku.com/floating-plateau-8391.git`

Capture the full push output. The build id is **not** emitted as a `Build UUID:` line. It
appears embedded in the CNB image path in the `*** Images (...)` block near the end of the
push, in the form `builds:<uuid>` — e.g.:
- `remote:       builds.heroku.com/<app_uuid>/builds:e0828838-c667-4acd-8e3e-c15fd602333f`

Extract the 36-char UUID that follows `builds:` (regex `builds:([0-9a-f-]{36})`) and store it
as `build_id` for Step 9. `build_id` is **optional** — `get_deployment_status` and
`get_build_output` default to the latest build for the app when it is omitted, so if the
pattern does not match, proceed to Step 9 without it.

> Verified against a real staging push (2026-08-28). The build id's downstream acceptance by
> the status tools is unconfirmed — `get_deployment_status`/`get_build_output` were returning
> "try again shortly" errors on staging at probe time.

If the push fails with a credential error, the one-shot token from Step 5 has likely lapsed
(it expires ~5 min after `create_preview_app`). Surface the full output and stop; re-running
the deploy mints a fresh session and app. (Minting fresh push creds for an *existing* preview
app — the edit → redeploy loop — is `get_preview_app_git_credentials`' job, which belongs to a
future redeploy flow, not this first-deploy skill.)

**Fallback for build_id:** If the push output does not contain a parseable build ID, run:
```bash
heroku builds --app <app_uuid> --json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])"
```

## Step 9 — Monitor build and finish addons (concurrent)

Two things complete after the push and are independent — poll both, then **join** before Step 10.

**Track A — build:**

```
Tool: get_deployment_status
Input: { conversation_id, app_uuid, build_id }   # conversation_id + app_uuid required; build_id optional (omit = latest build)
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
- If the failure is a **release-phase** error referencing a missing `DATABASE_URL` or addon, the
  addon simply was not ready when the release command ran — wait for Track B to report `ready`,
  then re-push (re-running the deploy if the git token has lapsed)

**Track B — addons** (only if Step 7 fired any): for each stored `addon_id`, poll until ready:

```
Tool: get_addon_status
Input: { conversation_id, app_uuid, addon_id }   # all three required
Output: { ready: boolean, config_vars }
```

Poll every 5 seconds until `ready: true`. This runs concurrently with Track A — the two do not
depend on each other.

**Join:** do not proceed to Step 10 until `build.done === true` **and** every addon reports
`ready: true`.

Store `web_url` and `expires_at` from `get_deployment_status` — needed for Steps 10 and 11.

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
Input: { conversation_id, app_uuid }
Output: { app_uuid, claimed: boolean, expired: boolean }
```

Poll every 30 seconds. When the state changes:

- `claimed: true` → "App claimed! It's now yours on Heroku."
- `expired: true` → "The claim window closed. The preview app has been removed. Run deploy again to create a new one."
