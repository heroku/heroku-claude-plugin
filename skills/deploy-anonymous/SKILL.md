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

Tool contract: `${CLAUDE_PLUGIN_ROOT}/references/mcp-core-contract.md`. There is no session step — the
server identifies the user by their verified Heroku login — and every call takes `app_id`.

## Step 1 — Verify prerequisites

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --quick --json
```

Gate on: `git: true`. The Heroku CLI is not used anywhere in this skill.
If git check fails, surface the preflight error and stop.

## Step 2 — Verify scaffolded app

**Read `.heroku-plugin-scaffold.json` first.** You need `stack`, `addons`, and `secret_env_vars` in later steps, and `stack` determines which other files are required.

Then verify the target directory contains:
- `project.toml` (CNB buildpack specification — required for all stacks)
- `.git/` directory (git repo initialized with at least one commit)
- `Procfile` with `web:` process — **required for all stacks except `website`**. The `heroku/static-web-server` buildpack provides the web process — **do not create a Procfile** for a website stack app.

If any required file is missing, suggest running `/heroku-plugin:scaffold-app` first.

## Step 3 — Create the preview app

```
Tool: create_preview_app
Input: {}
Output: { app_id, git_url, git_credentials: { token, expires_at } }
```

Record the app right away, before anything else can fail, so it can be found and discarded:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py set app_id=<app_id> stack=<stack> target_dir=<target_dir> --dir <target_dir>
```

- `app_id` is required for every remaining MCP call.
- Use `git_url` and `git_credentials.token` in Step 6. Never print the token.
- This call returns no URL — the app is not deployed yet. Do not invent one.
- `git_credentials` expire within minutes. Everything between here and the push (Steps 4–5) is
  *fast* calls only; the *slow* work (addon readiness, the build) happens in Step 7, after the push.

**If the call fails:**

- *"Preview app `<id>` is already active"* — the user already has a preview app. Do **not**
  create a second one. Tell them which app it is and offer `/heroku-plugin:discard-preview-app`
  to free the slot, or to deploy into the existing app. Stop until they choose.
- *"Preview apps are currently unavailable for this user."* or *"Could not verify Preview Apps
  availability."* — the feature is not enabled for this user. Show the server's message
  verbatim and stop. Do not retry in a loop; if the message ends "Try again shortly.", one
  later re-run is fine.
- *"requires the user to sign in with a verified Heroku identity"* — tell the user to
  authenticate the mcp-portal connector, then stop.

## Step 4 — Set secrets

Read `secret_env_vars` from `.heroku-plugin-scaffold.json`. **If empty, skip this step** — most
stacks (node, python/fastapi, go, website) have no secrets.

If non-empty (Django `DJANGO_SECRET_KEY`, Rails `RAILS_MASTER_KEY`), generate each value and set
them in one call. The Heroku CLI is not needed.

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

```
Tool: set_config_vars
Input: { app_id, vars: { "<NAME>": "<generated value>" } }
Output: { config_vars (masked), updated: [names] }
```

- The server asks the user to confirm. That prompt is expected — tell the user why before
  calling ("setting the app's secret keys").
- Success means every name in `secret_env_vars` appears in `updated`. If any is missing,
  surface the error and ask whether to continue; the build will likely fail without it.
- Never print a generated value. The tool returns them masked; show only the names.

## Step 5 — Kick off addon provisioning (do not wait)

Read the `addons` array from `.heroku-plugin-scaffold.json`. If empty, skip this step.

For each addon slug, **fire** the provision — call `create_addon` and move straight on. Do
**not** poll here; readiness is polled in Step 7, concurrently with the build. Firing it
before the push lets provisioning overlap the build.

```
Tool: create_addon
Input: { app_id, service }
Output: { id, name, plan, state, config_vars, app }
```

Store each `id` — Step 7 polls it as `addon_id`.

**Service slug mapping** (pass exactly these values as `service`):
| `.heroku-plugin-scaffold.json` slug | MCP `service` value |
|---|---|
| `heroku-postgresql` | `heroku-postgresql` |
| `heroku-redis` | `heroku-redis` |

If `create_addon` returns `isError: true`, surface the error and ask the user whether to
continue without the addon or stop.

## Step 6 — Push source

Push **immediately** after Step 5 — this is the critical path against the credential clock.

**Use the git push command from the `create_preview_app` tool description exactly — including
any push options it specifies (e.g. `-o heroku.action=async`).** Do not substitute or simplify
it. The tool description is the authoritative source; this skill does not override it.

The push output is unstructured text — there is no structured `build_id`. Capture the full
stdout and parse the build id from the `*** Images (...)` block as `builds:<uuid>` — regex
`builds:([0-9a-f-]{36})`. `build_id` is optional; the status tools default to the latest build.

**If the push fails with a credential error**, the token has lapsed. Do not re-run the deploy
and do not create a new app. Mint a fresh credential for the same app and push again:

```
Tool: get_preview_app_git_credentials
Input: { app_id }
Output: { git_credentials: { token, expires_at } }
```

If that tool itself errors, surface the message and stop.

## Step 7 — Monitor build and finish addons

Call `get_deployment_status` **once** and read its `monitoring` block. The server decides who
watches the deploy, so follow it rather than a fixed interval.

```
Tool: get_deployment_status
Input: { app_id, build_id }   # build_id optional (omit = latest build)
Output: { monitoring: { owner, support, instruction }, claim_link, web_url, expires_at,
          build: { status, done, failed }, addons: [{ name, ready, ... }] }
```

**`monitoring.owner` is `"card"`** — the Deployment card polls build, add-on and claim state
and owns the Preview/Claim actions. Do not poll, do not call `get_deployment_status` again,
and do not repeat the links. Wait for the card to finish, then go to Step 8.

**`monitoring.owner` is `"assistant"`** — you poll, as `monitoring.instruction` says (it names
the cadence; do not hardcode one). Never ask the user whether a card is visible.

- *Build:* repeat `get_deployment_status` until `build.done` is true.
  If `build.failed` is true, call `get_build_output { app_id, build_id }` and show the last
  30 lines of its `log`, then stop — do not continue to Step 8. A release-phase error about a
  missing `DATABASE_URL` means the addon was not ready; wait for it, then re-push (refresh the
  git credential first if it lapsed).
- *Addons* (only if Step 5 fired any): for each stored `id`, call `get_addon_status`
  `{ app_id, addon_id }` and follow its `monitoring.instruction` until `ready` is true.
  This runs alongside the build.

**Join:** do not continue until `build.done` is true **and** every addon reports `ready: true`.

## Step 8 — Save session state

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py set claim_url=<web_url> expires_at=<expires_at> deployed_at=<ISO8601 now> --dir <target_dir>
```

`web_url` from `get_deployment_status` is the **claim-portal URL**, not the running app.
`expires_at` is epoch milliseconds. Read the JSON the command prints and confirm the values
you set are in `session`.

## Step 9 — Surface result to user

**Card owns monitoring:** the card already shows Preview and Claim actions — **do not**
repeat the raw URLs. Confirm the deploy succeeded and that the card has the links.

**Assistant owns monitoring:** call `share_in_browser` for a fresh single-use preview link:

```
Tool: share_in_browser
Input: { app_id }
Output: { authorization_url, expires_in, preview_link, instruction }
```

Then show both links, copying `preview_link` and `claim_link` **verbatim** (each is a complete
labeled Markdown link; do not retype or rebuild them). Follow `instruction` for the preview link.

```
✓ Your app is live!

  <preview_link>   ← view the running app
  <claim_link>     ← transfer it to your Heroku account

  The claim window closes in about 1 hour.
```

Never show a raw `*.herokuapp.com` address, and never fetch the preview link yourself.

## Step 10 — Monitor claim

**Card owns monitoring:** do not poll `check_claim_status`.

**Assistant owns monitoring:**

```
Tool: check_claim_status
Input: { app_id }
Output: { monitoring: { instruction }, app_id, claimed, expired }
```

Poll as `monitoring.instruction` says. When the state changes:

- `claimed: true` → "App claimed! It's now yours on Heroku."
- `expired: true` → "The claim window closed and the preview app is gone. Run deploy again to create a new one."
