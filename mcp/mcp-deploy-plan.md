# MCP Anonymous Deploy Integration Plan

**Status:** Active — staging provisions for real; build polling still down  
**Active endpoint:** `https://mcp-portal.staging.herokudev.com/mcp?herokai=${HEROKAI_SECRET}` (per `.mcp.json`)  
**Last validated:** 2026-08-28 (live staging probe) + 2026-10-08 (mcp-portal rebase)

> For historical context on the canary-era plan (8 tools, ToS flow) see `mcp/mcp-deploy-plan-v1.md`.

---

## Deploy Flow Overview

The anonymous deploy uses 7 mcp-portal tools across 11 steps. There is no ToS gate — the flow
goes directly from session creation to app provisioning.

**Credential clock:** `create_preview_app` returns short-lived git credentials (~5 min). Steps 5
and 6 (set secrets, kick off addons) are fast, fire-and-don't-wait operations. The git push (Step
7) must complete before those credentials expire. Addon readiness and build monitoring run
concurrently *after* the push — never before.

---

## Tool Inventory (active deploy flow)

| Tool | Input | Purpose |
|------|-------|---------|
| `create_anonymous_session` | `{}` | Start session; returns `conversation_id` |
| `create_preview_app` | `{ conversation_id }` | Create Heroku app (CNB stack); returns `app_uuid`, `git_url`, `git_credentials` |
| `create_addon` | `{ app_uuid, service }` | Kick off addon provisioning (fire-and-continue) |
| `get_addon_status` | `{ app_uuid, addon_id }` | Poll until `ready: true` |
| `get_deployment_status` | `{ conversation_id, app_uuid, build_id? }` | Poll build; returns claim portal `web_url` |
| `share_in_browser` | `{ conversation_id, app_uuid }` | Get single-use preview URL after build succeeds |
| `check_claim_status` | `{ conversation_id, app_uuid }` | Poll until claimed or expired |

`get_build_output` — removed from active flow; `get_deployment_status` carries the build log.  
`get_preview_app_git_credentials` — future redeploy skill only (not first-deploy).

---

## Step-by-Step Flow

### Step 1 — Verify prerequisites
Preflight: `git` required; Heroku CLI not required for the MCP path.

### Step 2 — Verify scaffold artifacts
Read `.heroku-plugin-scaffold.json` — source of truth for `stack`, `addons`, `secret_env_vars`.
Confirm `project.toml`, `.git/`, and `Procfile` are present (except `website` stack — no Procfile).

### Step 3 — Create anonymous session
```
Tool: create_anonymous_session
Input: {}
Output: { conversation_id }
```
Store `conversation_id` — thread into all subsequent MCP calls.

### Step 4 — Create preview app
```
Tool: create_preview_app
Input: { conversation_id }
Output: { app_uuid, git_url, git_credentials: { token, expires_at }, mcp_credentials, web_url }
```
- Store `app_uuid`, `git_url`, `git_credentials.token`
- Do **not** surface `web_url` here — it is the raw `*.herokuapp.com` URL, not the claim link
- The credential clock starts now (~5 min) — Steps 5–6 must be fast

### Step 5 — Set secrets [CLI hybrid — skip if empty]
For apps with `secret_env_vars` (Django, Rails only):
```bash
heroku config:set NAME=$(python3 -c 'import secrets; print(secrets.token_hex(32))') --app <app_uuid>
```
The mcp-portal has no `set_config_vars` tool. CLI is required for this step only.

### Step 6 — Kick off addon provisioning (fire-and-continue)
For each addon in `.heroku-plugin-scaffold.json`:
```
Tool: create_addon
Input: { app_uuid, service }
Output: { id, state, config_vars }
```
Store each `id` as `addon_id` for Step 8. Do **not** poll readiness here — proceed immediately to the push.

**Service slugs** (pass exactly):
| Scaffold slug | MCP `service` value |
|---|---|
| `heroku-postgresql` | `heroku-postgresql` |
| `heroku-redis` | `heroku-redis` |

### Step 7 — Push source
Push immediately — this is the race against the credential clock from Step 4.

Use the git push command from the `create_preview_app` tool description exactly (including any
push options such as `-o heroku.action=async`). Parse `build_id` from push stdout:
```
builds:([0-9a-f-]{36})
```
`build_id` is optional — `get_deployment_status` defaults to the latest build when omitted.

### Step 8 — Monitor build and finish addons (concurrent)

**Apps-capable host (MCP App UI card):** Call `get_deployment_status` exactly once; the card
takes over. Wait for it to signal completion, then skip to Step 9.

**Without the card:** Two tracks run concurrently after the push:

**Track A — build:**
```
Tool: get_deployment_status
Input: { conversation_id, app_uuid, build_id }   # build_id optional
Output: { web_url, expires_at, build: { done, failed, log } }
```
Poll every 30s until `build.done === true`. Store `web_url` (claim portal URL) and `expires_at`.

**Track B — addons** (only if Step 6 fired any):
```
Tool: get_addon_status
Input: { app_uuid, addon_id }
Output: { ready: boolean, config_vars }
```
Poll every 30s until `ready: true`. Runs concurrently with Track A.

Join: do not proceed to Step 9 until both tracks complete.

### Step 9 — Save session state
Write `.heroku-plugin-session.json` with `conversation_id`, `app_uuid`, `claim_url`, `expires_at`,
`stack`, `target_dir`, `deployed_at`.

### Step 10 — Surface result
**Apps-capable host:** Card already showed Preview and Claim — confirm success, do not repeat URLs.

**Without the card:**
```
Tool: share_in_browser
Input: { conversation_id, app_uuid }
Output: { url }   # single-use preview URL
```
Surface Preview (`share_in_browser.url`) and Claim (`get_deployment_status.web_url`) to user.

### Step 11 — Monitor claim (background)
```
Tool: check_claim_status
Input: { conversation_id, app_uuid }
Output: { claimed: boolean, expired: boolean }
```
Poll every 30s until `claimed: true` or `expired: true`.

---

## Hybrid: Secrets via Heroku CLI

The anonymous MCP surface has no `set_config_vars` tool. Config var setting requires user auth
(`authMode: 'user'`), which the anonymous session doesn't support.

**Decision:** Keep `heroku config:set` for secrets only. Everything else — app creation, addon
provisioning, git push, build monitoring, claim polling — uses MCP tools. The CLI is only invoked
when `secret_env_vars` is non-empty in `.heroku-plugin-scaffold.json` (Django, Rails).

---

## Current Staging Status (as of 2026-08-28 + 2026-10-08 rebase)

| Tool | Status |
|------|--------|
| `create_anonymous_session` | ✅ confirmed — returns real `conversation_id` |
| `create_preview_app` | ✅ confirmed — real `app_uuid`, real `git_url`, real RS256 JWT creds (~5-min git, ~1-hr mcp) |
| `get_deployment_status` | ❌ down — "try again shortly" (highest-priority blocker — blocks claim URL) |
| `check_claim_status` | ✅ works — staging may auto-claim; semantics under investigation |
| `create_addon`, `get_addon_status` | ⏭️ not yet exercised live (no-addon path only tested) |
| `share_in_browser` | ⏭️ not yet exercised live |
| `get_preview_app_git_credentials` | ❌ down — deploy service unreachable; purpose = fresh push creds for edit→redeploy (future skill, not first-deploy) |

See `mcp/mcp-portal-readiness.md` for the full ordered status list and open items.
