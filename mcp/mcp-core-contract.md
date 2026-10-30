# mcp-portal / mcp-core tool contract

Source of truth for the tool surface the plugin calls. Verified by reading
`mcp-portal` (`src/tools/register.ts`) and `mcp-core` 7.0.0 (`src/tools/`) on 2026-10-30.
Stubs in `mcp/stubs/`, the e2e eval, and the skills must agree with this file. When the
server changes, update this file first.

## Identity model

- The caller is a verified Heroku user (bearer auth). There are **no sessions** and **no
  `conversation_id`**. `create_anonymous_session` no longer exists.
- A user has **one active preview app** at a time. The identifier is `app_id` (not `app_uuid`).
- Claim state machine: `pending` → `claimed` | `discarded`. Both are terminal. `expired` is
  derived (claim window is ~60 minutes). Only `pending` apps with a future expiry are active.
- Preview apps are gated by the `preview-apps-mcp-tools` lab (modes: disabled, enabled, gated).
  When the user is denied, the tool returns an error with a user-facing message. Show it and stop.

## Tools the portal exposes (16)

`create_preview_app`, `discard_preview_app`, `get_preview_app_git_credentials`,
`get_preview_app_details`, `check_claim_status`, `share_in_browser`, `give_agent_access`,
`create_addon`, `get_addon_status`, `get_build_output`, `get_deployment_status`,
`get_app_info`, `get_config_vars`, `set_config_vars`, `get_app_logs`, `update_app`.

`create_preview_app`, `get_preview_app_git_credentials`, `share_in_browser` and
`give_agent_access` are dropped from this list when the portal's admin API is off.

**Not exposed:** `destroy_app` (exists in mcp-core, filtered out by the portal allowlist),
`destroy_addon`, `unset_config_var`. There is no MCP path to delete a claimed app.

## Inputs and outputs

Preview-app tools take `app_id`. Tools that share the credential selector (`create_addon`,
`get_addon_status`, `get_deployment_status`, `set_config_vars`) accept `app` or `app_id`; the
plugin always passes `app_id`.

| Tool | Input | Output |
|------|-------|--------|
| `create_preview_app` | `{}` | `{ app_id, git_url, git_credentials: { token, expires_at } }` |
| `get_preview_app_git_credentials` | `{ app_id }` | `{ git_credentials: { token, expires_at } }` |
| `create_addon` | `{ app_id, service }` | `{ id, name, addon_service?, plan?, state, config_vars[], web_url?, app }` |
| `get_addon_status` | `{ app_id, addon_id }` | `{ monitoring?, addon_id, name, plan, state, ready, config_vars[] }` |
| `set_config_vars` | `{ app_id, vars: { NAME: value } }` | `{ config_vars (masked), updated[] }` |
| `get_deployment_status` | `{ app_id, build_id? }` | `{ monitoring?, claim_link?, app_id?, web_url?, expires_at?, build: { status, done, failed }, addons[] }` |
| `get_preview_app_details` | `{ app_id }` | `{ app_id, claim_url, expires_at, build?, addons[], … }` |
| `check_claim_status` | `{ app_id }` | `{ monitoring?, app_id, claimed, expired }` |
| `share_in_browser` | `{ app_id }` | `{ authorization_url, expires_in, preview_link?, instruction? }` |
| `discard_preview_app` | `{ app_id }` | `{ app_id }` |

Notes:

- `git_credentials` last ~5 minutes. Refresh with `get_preview_app_git_credentials`.
- `get_deployment_status.web_url` is the **claim-portal URL**, not the running app. Claim URL
  shape is `${claimPortalUrl}/start/${app_id}`. Copy `claim_link` / `preview_link` verbatim.
- `get_deployment_status` no longer carries the build log. Use `get_build_output` for it.
- `create_addon` `service` values the server accepts for preview apps: `heroku-postgresql`,
  `heroku-key-value-store`, `heroku-redis`, `heroku-connect`, `heroku-kafka` (the server picks
  the plan). The plugin supports `heroku-postgresql` and `heroku-redis` only; Kafka stays
  unsupported per `plugin.json` policy.
- `set_config_vars` returns masked values. It requires user confirmation (elicitation); the
  user may be prompted.

## Monitoring policy

Responses may carry `monitoring: { owner, support, instruction }`.

- `owner: "card"` — the Deployment card polls build, add-on and claim state and owns the
  Preview/Claim actions. Do not poll and do not repeat the links.
- `owner: "assistant"` — the assistant polls, following `instruction` (it names the cadence).
  Do not hardcode an interval in a skill.
- `support: "unknown"` defaults to `assistant`. Never ask the user whether a card is visible.

## Errors the plugin must handle

| Condition | Tool | Plugin behavior |
|-----------|------|-----------------|
| Active preview app already exists | `create_preview_app` | Error names the existing app. Offer `discard-preview-app`; do not create a second app. |
| Feature gate denied (lab disabled / not enabled for user) | `create_preview_app` | Show the server message verbatim and stop. Do not retry. |
| App not pending (claimed, discarded, expired) | `discard_preview_app` | "The preview app is not available to be discarded." Report it; nothing to do. |
| Git credential expired | git push | Call `get_preview_app_git_credentials`, push again. |
| No identity | any | "Requires the user to sign in with a verified Heroku identity." Stop. |

## Discard semantics

`discard_preview_app` only sets the claim status to `discarded`. The server relies on the
Platform API to destroy the Heroku app afterward; there is no immediate destroy. It confirms
with the user before running (`destructiveHint`, `confirmIrreversible`). It is not applicable
to claimed apps.

## Known open items

- `teardown` for claimed apps: the portal team is preparing to expose app deletion. Until it
  lands, `teardown` behavior for claimed apps is unchanged.
- Passages in `CLAUDE.md`, `README.md` and `mcp/mcp-deploy-plan*.md` that describe
  `.mcp.json`, `HEROKAI_SECRET`, sessions, `conversation_id` or `app_uuid` are stale.
