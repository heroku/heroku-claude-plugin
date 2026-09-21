---
name: teardown
description: >-
  Destroy a Heroku app and clean up local session state. Use when the user says
  "clean up", "tear down", "destroy the app", "delete the app", "reset", or similar.
  Safe to run after a test or when starting fresh.
argument-hint: "[app-name]"
allowed-tools: Bash, Read
---

# Teardown

## Step 1 — Identify the app

Get `app_name` from:
1. Provided argument
2. `.heroku-plugin-session.json` in the current directory

If neither is available, ask the user: "Which app should I destroy?"

## Step 2 — Confirm with the user

Before destroying anything, surface a clear confirmation prompt:

```
⚠ This will permanently destroy the Heroku app '<app-name>' and all its addons.

  App:    <app-name>
  URL:    https://<app-name>.herokuapp.com
  Addons: <addon list from session state, or "unknown">

  This cannot be undone.

Type the app name to confirm, or press Ctrl-C to cancel:
```

Read the user's response. Only proceed if they type the exact app name.
If they type anything else or cancel, surface:

```
Teardown cancelled — no changes made.
```

And stop.

## Step 3 — Destroy the Heroku app

The mcp-portal does not expose an app destroy tool. Direct the user to the Heroku dashboard:

```
To permanently destroy the app, visit:

  https://dashboard.heroku.com/apps/<app-name>/settings

Scroll to the bottom and click "Delete app". Once done, let me know and I'll clean up local state.
```

Wait for the user to confirm they've deleted the app (or that they want to skip), then continue to Step 4.

## Step 4 — Clean up local session state

Remove `.heroku-plugin-session.json` from the current directory if it exists:

```bash
rm -f .heroku-plugin-session.json
```

## Step 5 — Save session record to moot

Before surfacing the final result, save two memories using `moot memory create`:

**Memory 1 — Run steps** (`--kind context --scope user`)
- Title: `heroku-plugin build-and-deploy: session run steps (<date>)`
- Content: date, app name, stack, result (SUCCESS/FAILED), each numbered step with what was called and what happened, any deviations from the expected skill chain, notable issues with memory IDs if applicable, approximate timing
- **Required fields — scan ALL subagent and skill responses before writing:**
  - `token_usage`: output from `token_usage.py record` if `HEROKU_TOKEN_BUDGET_TRACKING=1` was set
  - `subagent_tokens`: total tokens used by any Task() sub-agents
  - `tool_uses`: total tool calls across the session
  - `duration_ms`: total wall-clock time if reported by any subagent
- Keywords: `heroku build-and-deploy <stack> <addons>`

**Memory 2 — Issues/fixes** (`--kind learning --scope user`) — one per distinct issue
- Title: `heroku-plugin <skill>: <short description of issue>`
- Content: what failed, root cause, workaround used, recommended permanent fix with file path, cross-reference to run steps memory by ID
- Keywords: `heroku build-and-deploy <stack> <issue-keywords>`

If moot is not running or unavailable, note it in the final output and skip silently — do not block teardown.

These records are searchable with: `moot search "heroku build-and-deploy"`

## Step 6 — Surface result

```
✓ Teardown complete.

  Heroku app '<app-name>' has been destroyed.
  Local session state cleared.
  Session record saved to moot.

To start fresh:
  Create a new directory and run: claude --plugin-dir /path/to/heroku-plugin
```
