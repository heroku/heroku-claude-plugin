---
name: check-deploy-status
description: >-
  Check Heroku deployment status and verify the app is running. Use after
  deploying to Heroku, or when the user asks "is my app deployed?", "check
  the build", "what happened to my deploy?", "are there any errors?", or similar.
argument-hint: "[app-uuid]"
allowed-tools: Bash, Read
---

# Check Deploy Status

## Step 1 — Load context

Get `conversation_id`, `app_uuid`, `build_id`, and `target_dir` from:
1. Provided arguments
2. `.heroku-plugin-session.json` in the current directory

## Step 2 — Check deployment status via MCP

```
Tool: get_deployment_status
Input: { conversation_id, app_uuid, build_id }   (build_id optional)
Output: { web_url, expires_at, build: { done, failed, log }, database }
```

If `build.done === false`, poll every 10 seconds until done.

## Step 3 — Analyze build log

Use `build.log` from the `get_deployment_status` response.
(`get_build_output` is no longer available — `get_deployment_status` carries the log.)

Analyze `build.log` from the MCP response for:

| Pattern | Diagnosis |
|---------|-----------|
| `Build succeeded` / `Launching` | Deployment succeeded |
| `Build failed` / ` ! ` lines | Build error — check log for root cause |
| `ModuleNotFoundError` / `ImportError` | Missing dependency |
| `no such file or directory` | Missing file/binary |
| `Error R10` | App didn't bind to $PORT in time |

Read `${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md` for the full
error reference. Read `${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md` for
stack-specific gotchas.

## Step 4a — Deployment succeeded

Probe the app URL to confirm it is responding:

```bash
curl -s -o /dev/null -w "%{http_code}" <web_url from session>
```

Surface result to user:

```
✓ App is live!

  Preview URL: <web_url>

  Open that link to view your app and claim it as your own Heroku account.
```

## Step 4b — Deployment failed

Surface the build log and a diagnosis to the user:

```
✗ Deployment failed.

Build log (last 30 lines):
  <tail of build.log>

Diagnosis: <root cause from log — e.g. missing dependency, bad Procfile, release-phase error>

Suggested fix: <one specific action — e.g. "Add 'gunicorn' to requirements.txt and redeploy">
```

Do not attempt an automatic fix or retry. Surface the information and let the user decide next steps.

## Step 4c — App deployed but not responding

If HTTP probe returns non-2xx on the preview URL:
- Surface the URL and status code
- Show the last 20 lines of `build.log`
- Do not attempt auto-fix for runtime errors — surface to user

## Step 5 — Update session state

If deployment succeeded, update `.heroku-plugin-session.json`:
```json
{
  "deployed": true,
  "app_url": "<web_url from get_deployment_status>"
}
```
