---
name: deploy-anonymous
description: >-
  Deploy an app to Heroku. Use when the user says "deploy the app", "deploy it",
  "push to Heroku", "make it live", "ship it", or similar. Uses the mcp-portal
  MCP server to create a preview app, provision addons, and deploy via git push.
argument-hint: "[target-dir]"
allowed-tools: Bash, Read
---

# Deploy to Heroku (Anonymous Preview)

## Step 1 — Verify prerequisites

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --quick --json
```

Gate on: `git: true`. Heroku CLI login is not required for the MCP deploy path.
If git check fails, surface the preflight error and stop.

## Step 2 — Verify scaffolded app

**Read `.heroku-plugin-scaffold.json` first.** You need `stack`, `addons`, and `secret_env_vars` in later steps, and `stack` determines which other files are required.

Then verify the target directory contains:
- `project.toml` (CNB buildpack specification — required for all stacks)
- `.git/` directory (git repo initialized with at least one commit)
- `Procfile` with `web:` process — **required for all stacks except `website`**. The `heroku/static-web-server` buildpack provides the web process — **do not create a Procfile** for a website stack app.

If any required file is missing, suggest running `/heroku-plugin:scaffold-app` first.

## Step 3 — Create anonymous session

```
Tool: create_anonymous_session
Input: {}
Output: { conversation_id }
```

Store `conversation_id` — thread it into every subsequent MCP call.

## Step 4 — Create preview app

```
Tool: create_preview_app
Input: { conversation_id }
Output: { app_uuid, web_url, git_url, git_credentials: { token, expires_at }, mcp_credentials }
```

- Store `app_uuid` — required for all remaining MCP calls
- Store `git_url` and `git_credentials.token` — used in Step 7
- Do **not** surface `web_url` from this step — it is the raw `*.herokuapp.com` address, not the link to give the user
- `git_credentials` expire quickly (~5 min) — the push (Step 7) must land inside that window. Everything between here and the push is kept to *fast* calls only (Steps 5–6); the *slow* work (addon readiness, build) is deferred to Step 8, after the push, so it never eats the credential window

> **Steps 5–8 ordering — the credential clock.** The push (Step 7) is the critical path: it
> must happen before the Step 4 token lapses (~5 min). So Steps 5 and 6 are *fast* calls only —
> set secrets, then fire addon creation without waiting. The *slow* work (addon readiness + the
> build) is deferred to Step 8 and polled concurrently, **after** the push. Never let addon
> readiness polling block the push.

## Step 5 — Set secrets [CLI — known gap]

Read `secret_env_vars` from `.heroku-plugin-scaffold.json`. **If empty, skip this step entirely** — most stacks (node, python/fastapi, go, website) have no secrets and never reach here.

If non-empty (Django, Rails): the mcp-portal has no `set_config_vars` tool. The Heroku CLI is required for this step. If the user does not have the CLI installed or is not logged in, surface:

```
⚠ This app needs secret config vars set before the build, but the mcp-portal does not
  support setting config vars. The Heroku CLI is required for this step.

  Install: https://devcenter.heroku.com/articles/heroku-cli
  Then run: heroku login

  Let me know when you're ready and I'll continue.
```

Wait for confirmation, then set each secret before the push:

```bash
heroku config:set <NAME>=$(python3 -c 'import secrets; print(secrets.token_hex(32))') --app <app_uuid>
```

The `app_uuid` works as the `--app` identifier. Common values: `DJANGO_SECRET_KEY` (Django), `RAILS_MASTER_KEY` (Rails).

## Step 6 — Kick off addon provisioning (do not wait)

Read the `addons` array from `.heroku-plugin-scaffold.json`. If empty, skip this step.

For each addon slug, **fire** the provision — call `create_addon` and move straight on. Do
**not** poll `get_addon_status` here; readiness is polled in Step 8, concurrently with the
build. `create_addon` returns quickly and only *starts* provisioning, so firing it before the
push lets provisioning overlap the build — maximizing the chance the addon is ready before any
release phase runs.

```
Tool: create_addon
Input: { app_uuid, service }
Output: { id, app, plan, state, config_vars }
```

Store each `id` — Step 8 polls it for readiness as `addon_id`.

**Service slug mapping** (pass exactly these values as `service`):
| `.heroku-plugin-scaffold.json` slug | MCP `service` value |
|---|---|
| `heroku-postgresql` | `heroku-postgresql` |
| `heroku-redis` | `heroku-redis` |

If `create_addon` returns `isError: true`, surface the error and ask the user whether to
continue without the addon or stop.

## Step 7 — Push source

Push **immediately** after Step 6 — this is the critical path against the credential clock; do
not wait on addon readiness (that is Step 8).

**Use the git push command from the `create_preview_app` tool description exactly — including
any push options it specifies (e.g. `-o heroku.action=async`).** Do not substitute or simplify
the command. The tool description is the authoritative source; this skill does not override it.

The push output is unstructured text from `git push` — there is no structured `build_id` field.
Capture the full stdout and parse it: the build id appears in the `*** Images (...)` block near
the end of the output as `builds:<uuid>` — regex `builds:([0-9a-f-]{36})`. `build_id` is
optional — `get_deployment_status` defaults to the latest build for the app when omitted.

If the push fails with a credential error, the token from Step 4 has likely lapsed (~5 min
after `create_preview_app`). Surface the full output and stop — re-running the deploy mints a
fresh session and app.

## Step 8 — Monitor build and finish addons

> **Read this branch decision first before doing anything else in this step.**

**Apps-capable host (Claude Desktop with MCP App UI card present):**
Call `get_deployment_status` **exactly once**. The card appears and takes over — it polls build status, addon readiness, and claim status automatically. **Do not call `get_deployment_status` again. Do not poll.** Wait for the card to signal completion, then read `web_url` and `expires_at` from that single response and go directly to Step 9.

---

**Without the card:** Two tracks run concurrently after the push — join both before Step 9.

**Track A — build:**

```
Tool: get_deployment_status
Input: { conversation_id, app_uuid, build_id }   # build_id optional (omit = latest build)
Output: { web_url, expires_at, build: { done, failed, log }, database }
```

Poll every 30 seconds until `build.done === true`. Show progress:
```
Building... (checking every 30s)
```

If `build.failed === true`:
- Surface the tail of `build.log` (last 30 lines) to the user
- Stop — do not proceed to Step 9
- Suggest checking the Procfile, requirements, or build errors shown
- If the failure is a **release-phase** error referencing a missing `DATABASE_URL` or addon, the
  addon simply was not ready when the release command ran — wait for Track B to report `ready`,
  then re-push (re-running the deploy if the git token has lapsed)

**Track B — addons** (only if Step 6 fired any): for each `id` stored from `create_addon`, poll until ready:

```
Tool: get_addon_status
Input: { app_uuid, addon_id }
Output: { ready: boolean, config_vars }
```

Poll every 30 seconds until `ready: true`. Runs concurrently with Track A.

**Join:** do not proceed to Step 9 until `build.done === true` **and** every addon reports `ready: true`.

Store `web_url` and `expires_at` from `get_deployment_status` — `web_url` is the **claim portal URL**, needed for Steps 10 and 11.

## Step 9 — Save session state

Write to `.heroku-plugin-session.json` in target_dir:
```json
{
  "conversation_id": "<conversation_id>",
  "app_uuid":        "<app_uuid>",
  "claim_url":       "<web_url from get_deployment_status>",
  "expires_at":      <expires_at>,
  "stack":           "<stack from .heroku-plugin-scaffold.json>",
  "target_dir":      "<path>",
  "deployed_at":     "<ISO8601 timestamp>"
}
```

## Step 10 — Surface result to user

**Apps-capable host:** The live card already surfaced Preview and Claim actions — **do not**
repeat the raw URLs. Confirm to the user that the deploy succeeded and the card has the links.

**Without the card:** Call `share_in_browser` to get a fresh single-use preview URL:

```
Tool: share_in_browser
Input: { conversation_id, app_uuid }
Output: { url }
```

Then surface both links:

```
✓ Your app is live!

  Preview:  <url from share_in_browser>   ← view the running app
  Claim:    <web_url from get_deployment_status>   ← transfer to your Heroku account

  The claim window is open for 1 hour.
```

Do not surface the raw `*.herokuapp.com` URL for either link.

## Step 11 — Monitor claim (background)

**Apps-capable host:** The live card handles claim monitoring — **do not** poll
`check_claim_status` while the card is present.

**Without the card:**

```
Tool: check_claim_status
Input: { conversation_id, app_uuid }
Output: { app_uuid, claimed: boolean, expired: boolean }
```

Do not pass `expires_at` — the server tracks the deadline internally.

Poll every 30 seconds. When the state changes:

- `claimed: true` → "App claimed! It's now yours on Heroku."
- `expired: true` → "The claim window closed. The preview app has been removed. Run deploy again to create a new one."
