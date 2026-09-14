# MCP Anonymous Deploy Integration Plan

**Status:** In progress — canary validated, awaiting live provisioning  
**Branch:** `feature/mcp-deploy` (off `feature/project-toml-cnb` → rebase to `main` after PR #20 merges)  
**Canary endpoint:** `https://mcp-portal-canary.herokai.com/mcp?herokai=$HEROKAI_SECRET`  
**Canary server:** `mcp-portal` v1.0.0 — 8 tools confirmed, provisioning path still stubbed

---

## Background

This plan replaces the CLI-based anonymous deploy path (`heroku create` + `git push heroku`) with
calls to the mcp-portal MCP server. The canary is live and available for testing.

Key motivation: `create_preview_app` calls `POST /teams/apps` with `{ stack: "cnb" }` server-side,
which activates CNB on Cedar automatically — the platform flag we couldn't set from the CLI path.

**References:**
- mcp-portal source: `~/src/mcp-portal`
- Tool contracts: `mcp/references/connector-mcp-tools.md` (to be updated)
- GUS epic: W-23636826 (deploy-flow tools)

---

## Decision: Hybrid for Secrets

The anonymous MCP tool surface has no `set_config_vars` tool. Config var setting requires user
auth (`authMode: 'user'`), which the anonymous session doesn't have.

**Decision:** Keep `heroku config:set` for the secrets step only. Everything else — app creation,
addon provisioning, git push, build monitoring, claim polling — moves to MCP tools.

This is a clean conceptual split: MCP owns infrastructure (server-team resources), CLI owns
the user's secret values (which belong to the user anyway, post-claim).

---

## New Deploy Flow

### Step 1 — Verify scaffold artifacts
Check that the target directory contains:
- `.heroku-plugin-scaffold.json` (source of truth for addons + secret_env_vars)
- `project.toml` (CNB buildpack spec)
- `Procfile`
- `.git/` directory

If missing: suggest running `heroku-plugin:scaffold-app` first.

### Step 2 — Create anonymous session
```
Tool: create_anonymous_session
Input: {}
Output: { conversation_id, tos_url }
```
Surface `tos_url` to the user: _"Visit [URL] to accept the Terms of Service before we continue."_
Wait for explicit user confirmation before proceeding to step 3.

### Step 3 — Poll for ToS acceptance
```
Tool: check_anonymous_session_state
Input: { conversation_id }
Output: { tos_status: "pending" | "accepted" }
```
Poll every 5 seconds until `tos_status === "accepted"`. Surface progress to user.

### Step 4 — Create preview app
```
Tool: create_preview_app
Input: { conversation_id }
       (optional: stack — defaults to "cnb", do not pass unless overriding)
Output: { app_uuid, git_url, git_credentials: { token, ... }, web_url }
```
- `app_uuid` is the Heroku app id — thread into all subsequent calls
- `git_credentials` are short-lived — proceed to push promptly
- `web_url` at this step is the raw `*.herokuapp.com` URL — **do not surface to user yet**
- CNB is the server default — omitting `stack` gets us CNB on Cedar automatically

### Step 5 — Provision addons
Read `addons` array from `.heroku-plugin-scaffold.json`. For each addon slug:
```
Tool: create_addon
Input: { app_uuid, service }   e.g. service: "heroku-postgresql"
Output: { addon_id, state, config_vars: string[] }

Tool: get_addon_status
Input: { app_uuid, addon_id }
Output: { ready: boolean, config_vars: string[] }
```
Poll `get_addon_status` every 5 seconds until `ready: true`.

**Allowlisted services and plans (server-enforced):**
| Plugin addon slug | MCP service slug |
|---|---|
| `heroku-postgresql` | `heroku-postgresql` |
| `heroku-redis` | `heroku-redis` |

Note: `heroku-redis` maps to `heroku-key-value-store:mini` on the server side — pass
`"heroku-redis"` and the server resolves the plan.

### Step 6 — Set secrets [CLI hybrid]
Read `secret_env_vars` from `.heroku-plugin-scaffold.json`. For each name:
```bash
heroku config:set NAME=$(python3 -c 'import secrets; print(secrets.token_hex(32))') --app <app_uuid>
```
The `app_uuid` works as the `--app` identifier; the app is server-team owned at this point
but the Heroku CLI can still set config vars on it with appropriate credentials.

Common values: `DJANGO_SECRET_KEY`, `RAILS_MASTER_KEY`.
If `secret_env_vars` is empty, skip this step entirely.

### Step 7 — Push source
```bash
git push https://<token>@<git_url_host><git_url_path>
```
Use HTTP basic auth with `git_credentials.token`. The push triggers the Heroku build.
`git_credentials` expire quickly — complete the push without delay after step 4.

### Step 8 — Monitor build
```
Tool: get_deployment_status
Input: { app_uuid, build_id }
Output: { web_url, expires_at, build: { done, failed, log }, database }
```
Poll every 10 seconds until `build.done === true`.
If `build.failed === true`: surface the tail of `build.log` to the user and stop.

**build_id:** Both `get_deployment_status` and `get_build_output` require `build_id` (schema
describes it as "returned by `update_deployment`" — stale docs from the old server; that tool
no longer exists). No MCP tool returns it after a git push. Two options to test in order:

**Option 1 — Parse from git push stdout (preferred)**
Heroku's remote output during a push includes the build ID. Capture stderr/stdout from the
push and grep for it. Exact format unknown until live provisioning ships — needs a real push
to observe. Expected pattern: something like `remote: Build UUID: <uuid>` or embedded in a
build URL line.

**Option 2 — CLI fallback**
If the grep approach fails or the format is unreliable:
```bash
heroku builds --app <app_uuid> --json | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])"
```
Run immediately after the push completes. Requires the Heroku CLI, which is already a
dependency. Less fragile than string parsing.

Validate which works once live provisioning is available on the canary.

Note: the older `connector-mcp-tools.md` reference shows `get_deployment_status` taking only
`{ app_uuid }` — that server diverged from mcp-portal. The canary requires `build_id`.
The reference doc needs updating as part of this PR.

### Step 9 — Surface result
`web_url` from `get_deployment_status` is the **claim portal URL**
(`https://claim-canary.heroku.com/preview/<app_uuid>`) — this is the correct URL to give
the user. Never surface the raw `*.herokuapp.com` URL.

### Step 10 — Monitor claim (optional, background)
```
Tool: check_claim_status
Input: { app_uuid, expires_at }
Output: { claimed: boolean, expired: boolean }
```
Poll until `claimed: true` (user took ownership) or `expired: true` (claim window closed,
app destroyed — normal terminal state).

---

## Files to Change

| File | Change |
|---|---|
| `skills/deploy-anonymous/SKILL.md` | Full rewrite — MCP flow above |
| `mcp/stubs/*.json` | Replace all 6 stubs with correct 8 tool shapes |
| `mcp/references/connector-mcp-tools.md` | Replace with mcp-portal canary contracts — the two servers have diverged (connector-mcp had `get_deployment_status { app_uuid }` only; canary requires `build_id`) |
| `plugin.json` | Add `mcp_endpoint` config block |
| `skills/check-deploy-status/SKILL.md` | Update tool names |

`teardown` skill stays CLI — no MCP tool for anonymous app destruction.

---

## MCP Endpoint Configuration

Add to `plugin.json` under `policy`:
```json
"mcp_endpoint": "https://mcp-portal-canary.herokai.com/mcp",
"mcp_auth_env_var": "HEROKAI_SECRET"
```

Auth is passed as a query parameter: `?herokai=$HEROKAI_SECRET`. The secret is read from the
environment variable at runtime — never committed.

---

## Stub Tool Name Mapping

Current stubs → correct mcp-portal tool names:

| Existing stub file | Correct tool name |
|---|---|
| `create_app.json` | `create_anonymous_session` + `create_preview_app` |
| `push_git.json` | _(git push — not an MCP tool)_ |
| `get_build_status.json` | `get_deployment_status` |
| `generate_access_code.json` | _(no MCP tool — claim portal handles this)_ |
| `transfer_app.json` | `check_claim_status` |
| `set_public_routing.json` | _(post-claim user tool — out of scope)_ |

New stubs needed:
- `create_anonymous_session.json`
- `check_anonymous_session_state.json`
- `create_preview_app.json`
- `create_addon.json`
- `get_addon_status.json`
- `get_deployment_status.json`
- `check_claim_status.json`
- `get_build_output.json` (optional, for log streaming fallback)

---

## Validation Plan

### Completed (2026-08-25)

- ✅ `HEROKAI_SECRET` set in `~/.zshrc` — available in all terminal sessions
- ✅ MCP handshake — server `mcp-portal` v1.0.0, protocol `2025-06-18`
- ✅ 8 tools confirmed: `create_anonymous_session`, `check_anonymous_session_state`,
  `create_preview_app`, `get_build_output`, `get_deployment_status`, `check_claim_status`,
  `create_addon`, `get_addon_status`
- ✅ `create_anonymous_session` response shape confirmed — `{ conversation_id, tos_url, tos_status }`
- ✅ `create_preview_app` input schema confirmed — `stack` optional, defaults to `"cnb"`
- ✅ `get_deployment_status` + `get_build_output` both require `{ app_uuid, build_id }`
- ⚠️ Canary provisioning is fully stubbed — `git_url` is `git.invalid`, credentials fake.
  ToS gate is in-memory only. All three session/provision tools return stub responses.

### Pending (requires live provisioning on canary)

- [ ] Accept ToS in browser — confirm `check_anonymous_session_state` → `"accepted"`
- [ ] `create_preview_app` returns real `app_uuid`, `git_url`, live `git_credentials`
- [ ] Push minimal Node app — observe full git push stdout, identify `build_id` format
- [ ] Validate Option 1 (grep push stdout) vs Option 2 (CLI fallback) for `build_id`
- [ ] Provision `heroku-postgresql` addon — confirm `"heroku-redis"` slug mapping works
- [ ] Confirm `get_deployment_status.web_url` is claim portal URL, not raw app URL
- [ ] Full end-to-end: session → app → push → build → claim portal URL surfaced

---

## Out of Scope (this PR)

- `claim-app` skill — requires `authMode: 'user'` tools (post-claim, user-owned)
- `generate-access-code` skill — handled by claim portal browser UX
- Kafka addon — not in anonymous allowlist
- Token exchange / JWT auth (W-23636843, W-23654160) — when those ship, `git_credentials`
  shape changes; update then
