# mcp-portal Readiness — Plugin Integration Requirements

**Purpose:** Ordered list of MCP server features needed to complete the anonymous deploy
integration in the plugin. Pass to the mcp-portal team; implement in order so each item
can be tested independently as it lands on staging.

**Active endpoint:** `https://mcp-portal.staging.herokudev.com/mcp?herokai=${HEROKAI_SECRET}` (per `.mcp.json`)  
**Last validated:** 2026-08-28 — live staging probe; see below

---

## 2026-08-28 live staging probe

The plugin now points at **staging** (not canary), and staging provisions for real — items 1–4
below are effectively **done**. Per-tool results from a real end-to-end run (session → ToS →
`create_preview_app` → git push → CNB build succeeded, app deployed):

| Tool | Result |
|---|---|
| `create_anonymous_session` | ✅ real session + ToS URL |
| `check_anonymous_session_state` | ✅ pending → accepted (browser callback works) |
| `create_preview_app` | ✅ real `app_uuid`, `git_url` (`git.staging.herokudev.com`), real RS256 JWT creds (~5-min git, ~1-hr mcp) |
| git push → CNB build | ✅ real build ran and deployed |
| `check_claim_status` | ✅ works — but returned `claimed: true` with no claim ever performed (**staging auto-claims? confirm semantics**) |
| `get_deployment_status` | ❌ "Could not read the deployment status … try again shortly" — persistent (~65s, with and without `build_id`) |
| `get_build_output` | ❌ "Could not read the build status … try again shortly" — persistent |
| `get_preview_app_git_credentials` | ❌ "could not reach the deploy service … needs operator attention" (not retryable) |
| `create_addon`, `get_addon_status` | ⏭️ not exercised (no-addon happy path) |

**Open items for the mcp-portal team:**
1. `get_deployment_status` + `get_build_output` are **down on staging** — this is the highest-priority blocker: `get_deployment_status` is the only source of the claim-portal URL handed to the user.
2. `get_preview_app_git_credentials` fails at the service layer (down on staging). Its purpose (confirmed with the team) is minting fresh push creds for an **already-provisioned** preview app — i.e. the edit → redeploy loop, since the `create_preview_app` creds expire ~5 min after issuance. It is **not** needed for the first deploy and has no caller in the plugin yet (a redeploy skill would own it). Its `app_id` arg shape stays unverified until the service is back up.
3. `check_claim_status` returned `claimed: true` for an unclaimed app — confirm what "claimed" means on staging.

**`build_id` format — now confirmed (answers the item 4 question below):** the id is **not** emitted
as `remote: Build UUID: <uuid>`. It appears in the `*** Images (...)` block as
`builds.heroku.com/<app_uuid>/builds:<uuid>` — parse the UUID after `builds:`.

---

## Implementation Order

### 1. Persistent session store

**What it is:** Sessions from `create_anonymous_session` are currently in-memory on a single
dyno. They need to survive across requests so that `check_anonymous_session_state` can read
the session state in a separate HTTP request.

**What it unblocks:** Everything. Without this, ToS state can never transition from `pending`
to `accepted` across two separate HTTP requests.

**Staging status (2026-08-28):** ✅ Done — state survives across requests.

---

### 2. ToS browser callback

**What it is:** When a user visits `tos_url` in their browser and accepts, that acceptance
needs to write `tos_status: "accepted"` back to the session store.

**What it unblocks:** `check_anonymous_session_state` returning `"accepted"`, which is the
gate before `create_preview_app`.

**Staging status (2026-08-28):** ✅ Done — browser callback fires and flips status to `"accepted"`.

---

### 3. Real app provisioning (`create_preview_app`)

**What it is:** The tool needs to call `POST /teams/apps` with `{ stack: "cnb" }` and return
a real `app_uuid`, `git_url`, and short-lived `git_credentials`.

**What it unblocks:** Everything downstream — git push, build polling, addon provisioning,
claim status. This is the critical path item.

**Staging status (2026-08-28):** ✅ Done — returns real `app_uuid`, real `git_url` (`git.staging.herokudev.com`), and real RS256 JWT credentials.

---

### 4. Git credentials generation

**What it is:** `git_credentials.token` must be a real app-scoped JWT that authenticates a
`git push` to `git_url`. Likely the OAuth authorization path (`POST /oauth/authorizations`)
minting a short-lived token scoped to the app.

**What it unblocks:** The actual git push that triggers a real Heroku build.

**Note:** May ship as part of item 3 or as the W-23654160 git-push path. Either way the
token must work for:
```bash
git push https://heroku:<token>@git.heroku.com/<app>.git
```
**`build_id` format confirmed (2026-08-28):** Appears in the `*** Images (...)` block as
`builds.heroku.com/<app_uuid>/builds:<uuid>` — parse the UUID after `builds:` with
regex `builds:([0-9a-f-]{36})`. The downstream acceptance of this `build_id` by
`get_deployment_status` remains unconfirmed (tool currently down on staging).

---

### 5. Build polling (`get_build_output`, `get_deployment_status`)

**What it is:** Both tools are already implemented and hit the real Heroku API. What's needed
is a real `app_uuid` and `build_id` flowing from items 3 and 4, plus confirmation of the
`build_id` format in git push stdout (see item 4 note).

**What it unblocks:** Build monitoring and the `web_url` (claim portal URL) returned by
`get_deployment_status`.

**Staging status (2026-08-28):** ❌ **DOWN** — `get_deployment_status` and `get_build_output` both return "try again shortly" persistently. Highest-priority blocker.

---

### 6. Addon provisioning (`create_addon`, `get_addon_status`)

**What it is:** Both tools are already implemented locally. They need a real `app_uuid` from
item 3 to provision against. Required for any scaffolded app that includes
`heroku-postgresql` or `heroku-redis`.

**What it unblocks:** Postgres and Redis on anonymous preview apps (Django, Rails, any stack
requesting addons).

**Staging status (2026-08-28):** ⏭️ Not yet exercised live (no-addon happy path run).

---

### 7. Claim polling (`check_claim_status`)

**What it is:** Already hits the real Heroku API. Needs a real `app_uuid` from a live
deployed app and the claim portal wired to staging.

**What it unblocks:** Full end-to-end flow including the user claiming the app as their own.

**Staging status (2026-08-28):** ✅ Works — but returned `claimed: true` for an unclaimed app. Confirm whether staging auto-claims.

---

## Summary

Status as of the 2026-08-28 staging probe (was all-stubbed on 2026-08-25 canary):

| # | Feature | Blocks | Completed | Current status (staging) |
|---|---|---|---|---|
| 1 | Persistent session store | Everything | ☑ | Works — state survives across requests |
| 2 | ToS browser callback | Items 3–7 | ☑ | Works — acceptance flips to `accepted` |
| 3 | Real app provisioning (`create_preview_app`) | Items 4–7 | ☑ | Real app + `git_url` (no longer `git.invalid`) |
| 4 | Git credentials (real JWT) + `build_id` format | Items 5–7 | ☑ | Real JWT creds; `build_id` format confirmed (`builds:<uuid>`) |
| 5 | Build polling (`get_build_output`, `get_deployment_status`) | Item 7 | ☐ | **DOWN** — "try again shortly" (blocks claim URL) |
| 6 | Addon provisioning (`create_addon`, `get_addon_status`) | — | ☐ | Not yet exercised live |
| 7 | Claim polling (`check_claim_status`) | — | ☑ | Works — but `claimed:true` semantics need confirming |
| 8 | Redeploy git creds (`get_preview_app_git_credentials`) | future redeploy flow | ☐ | **DOWN** — deploy service unreachable; purpose = fresh creds for pushing revisions to a live preview app (not first-deploy) |
