# mcp-portal Readiness — Plugin Integration Requirements

**Purpose:** Ordered list of MCP server features needed to complete the anonymous deploy
integration in the plugin. Pass to the mcp-portal team; implement in order so each item
can be tested independently as it lands on canary.

**Canary endpoint:** `https://mcp-portal-canary.herokai.com/mcp?herokai=$HEROKAI_SECRET`  
**Last validated:** 2026-08-25 — all session/provisioning tools still stubbed

---

## Implementation Order

### 1. Persistent session store

**What it is:** Sessions from `create_anonymous_session` are currently in-memory on a single
dyno. They need to survive across requests so that `check_anonymous_session_state` can read
the session state in a separate HTTP request.

**What it unblocks:** Everything. Without this, ToS state can never transition from `pending`
to `accepted` across two separate HTTP requests.

**Current canary behavior:** Response text says "opened IN MEMORY ONLY — nothing was persisted"

---

### 2. ToS browser callback

**What it is:** When a user visits `tos_url` in their browser and accepts, that acceptance
needs to write `tos_status: "accepted"` back to the session store.

**What it unblocks:** `check_anonymous_session_state` returning `"accepted"`, which is the
gate before `create_preview_app`.

**Current canary behavior:** `check_anonymous_session_state` always returns `"pending"` — no
browser callback is wired.

---

### 3. Real app provisioning (`create_preview_app`)

**What it is:** The tool needs to call `POST /teams/apps` with `{ stack: "cnb" }` and return
a real `app_uuid`, `git_url`, and short-lived `git_credentials`.

**What it unblocks:** Everything downstream — git push, build polling, addon provisioning,
claim status. This is the critical path item.

**Current canary behavior:** Returns `git_url: "https://git.invalid/..."` and
`git_credentials.token: "STUB-git-jwt-not-real"`

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
The plugin also needs to know the exact format of the `build_id` in the git push remote
output — Heroku embeds it in the push stdout and the plugin parses it from there to pass
to `get_deployment_status`. Please confirm the exact line format once a real push is
possible, e.g.:
```
remote: Build UUID: <uuid>
```

---

### 5. Build polling (`get_build_output`, `get_deployment_status`)

**What it is:** Both tools are already implemented and hit the real Heroku API. What's needed
is a real `app_uuid` and `build_id` flowing from items 3 and 4, plus confirmation of the
`build_id` format in git push stdout (see item 4 note).

**What it unblocks:** Build monitoring and the `web_url` (claim portal URL) returned by
`get_deployment_status`.

**Current canary behavior:** Implemented and live — blocked only on receiving real inputs.

---

### 6. Addon provisioning (`create_addon`, `get_addon_status`)

**What it is:** Both tools are already implemented locally. They need a real `app_uuid` from
item 3 to provision against. Required for any scaffolded app that includes
`heroku-postgresql` or `heroku-redis`.

**What it unblocks:** Postgres and Redis on anonymous preview apps (Django, Rails, any stack
requesting addons).

**Current canary behavior:** Implemented and live — blocked only on real `app_uuid`.

---

### 7. Claim polling (`check_claim_status`)

**What it is:** Already hits the real Heroku API. Needs a real `app_uuid` from a live
deployed app and the claim portal wired to canary.

**What it unblocks:** Full end-to-end flow including the user claiming the app as their own.

**Current canary behavior:** Implemented and live — blocked only on real `app_uuid`.

---

## Summary

| # | Feature | Blocks | Completed | Current status |
|---|---|---|---|---|
| 1 | Persistent session store | Everything | ☐ | In-memory only |
| 2 | ToS browser callback | Items 3–7 | ☐ | Not wired |
| 3 | Real app provisioning (`create_preview_app`) | Items 4–7 | ☐ | Stubbed (`git.invalid`) |
| 4 | Git credentials (real JWT) + `build_id` format | Items 5–7 | ☐ | Stubbed |
| 5 | Build polling (`get_build_output`, `get_deployment_status`) | Item 7 | ☐ | Implemented, needs real data |
| 6 | Addon provisioning (`create_addon`, `get_addon_status`) | — | ☐ | Implemented, needs real `app_uuid` |
| 7 | Claim polling (`check_claim_status`) | — | ☐ | Implemented, needs real `app_uuid` |
