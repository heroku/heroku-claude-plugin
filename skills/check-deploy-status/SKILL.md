---
name: check-deploy-status
description: >-
  Check Heroku deployment status and verify the app is running. Use after
  deploying to Heroku, or when the user asks "is my app deployed?", "check
  the build", "what happened to my deploy?", "are there any errors?", or similar.
argument-hint: "[app-id]"
allowed-tools: Bash, Read
---

# Check Deploy Status

Tool contract: `${CLAUDE_PLUGIN_ROOT}/mcp/mcp-core-contract.md`.

## Step 1 — Load context

Get `app_id`, `stack` and `target_dir` from:
1. Provided arguments
2. The session file:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py show
```

Read `session` from the JSON. If there is no `app_id` from either source, tell the user there is
no deployed preview app to check, suggest `/heroku-plugin:deploy-anonymous`, and stop.

## Step 2 — Check deployment status via MCP

```
Tool: get_deployment_status
Input: { app_id, build_id }   # build_id optional (omit = latest build)
Output: { monitoring: { owner, support, instruction }, claim_link, web_url, expires_at,
          build: { status, done, failed }, addons: [{ name, ready, state }] }
```

Read `monitoring` first and follow it:

- **`owner: "card"`** — the Deployment card owns monitoring. Report what this one response
  says and do not poll or call the tool again.
- **`owner: "assistant"`** — if `build.done` is false, call it again as `monitoring.instruction`
  says until `build.done` is true. Do not hardcode an interval.

An error that says the app has been claimed, discarded or has expired means the preview app is
gone. Say that, suggest a new deploy, and stop.

## Step 3 — Analyze the build log

Only when `build.failed` is true, or the user asked for the log:

```
Tool: get_build_output
Input: { app_id, build_id }   # build_id optional
Output: { log, status, done }
```

`get_deployment_status` carries the build state but not the log; the log comes from
`get_build_output`. Match the log against:

| Pattern | Diagnosis |
|---------|-----------|
| `Build succeeded` / `Launching` | Deployment succeeded |
| `Build failed` / ` ! ` lines | Build error — check log for root cause |
| `ModuleNotFoundError` / `ImportError` | Missing dependency |
| `no such file or directory` | Missing file/binary |
| `Error R10` | App didn't bind to $PORT in time |

Read `${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md` for the full error reference
and `${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md` for stack-specific gotchas.

## Step 4a — Deployment succeeded

Confirm the app is actually running by looking at its processes, not by fetching a URL
(the claim link is a sign-in page, and a preview app needs browser authorization):

```
Tool: get_app_info
Input: { app_id }
Output: { name, web_url, dynos: [{ type, state }], addons: [{ name, plan }] }
```

The web process is up when a `web` dyno has `state` `up`. Report the real state; if it is
`starting`, say so and offer to check again.

If the card does not own the links, call `share_in_browser { app_id }` and show `preview_link`
and `claim_link` verbatim (they are complete labeled links; do not rebuild them):

```
✓ App is live.

  <preview_link>   ← view the running app
  <claim_link>     ← transfer it to your Heroku account
```

If the card owns monitoring, it already shows these — confirm the status and do not repeat them.
Never show the raw `*.herokuapp.com` address and never fetch the preview link yourself.

## Step 4b — Deployment failed

Surface the build log and a diagnosis:

```
✗ Deployment failed.

Build log (last 30 lines):
  <tail of log>

Diagnosis: <root cause from log — e.g. missing dependency, bad Procfile, release-phase error>

Suggested fix: <one specific action — e.g. "Add 'gunicorn' to requirements.txt and redeploy">
```

Do not attempt an automatic fix or retry. Surface the information and let the user decide.

## Step 4c — Build succeeded but the web process is not up

If `get_app_info` shows no `web` dyno, or one that is `crashed`:
- Say which state it is in
- Show the last 20 lines from `get_app_logs { app_id, lines: 20 }`
- Do not attempt an auto-fix for runtime errors — surface it to the user

## Step 5 — Update session state

If the deployment succeeded:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py set claim_url=<web_url> expires_at=<expires_at> --dir <target_dir>
```

Read the JSON it prints and confirm both values are in `session`.
