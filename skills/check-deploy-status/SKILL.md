---
name: check-deploy-status
description: >-
  Check Heroku deployment status and verify the app is running. Use after
  deploying to Heroku, or when the user asks "is my app deployed?", "check
  the build", "what happened to my deploy?", "are there any errors?", or similar.
argument-hint: "[app-name]"
allowed-tools: Bash, Read, Task
---

# Check Deploy Status

<!-- TODO: Replace CLI polling with MCP tool calls (get_deployment_status,
     get_build_output) once the connector-mcp implementation is available. -->

## Step 1 — Load context

Get `app_name` and `target_dir` from:
1. Provided arguments
2. `.heroku-plugin-session.json` in the current directory

## Step 2 — Check latest release

```bash
heroku releases --app <app-name> --num 5
```

Parse output for the most recent release. Look for:
- `v<N>  Deploy <sha>  <user>  <timestamp>` → successful deploy
- `v<N>  ... failed` → failed release

## Step 3 — Stream recent build logs

```bash
heroku logs --app <app-name> --num 100 --source app,heroku
```

Analyze the output for:

| Pattern | Diagnosis |
|---------|-----------|
| `State changed from starting to up` | Deployment succeeded |
| `State changed from starting to crashed` | App crashed on boot |
| `Error R10 (Boot timeout)` | App didn't bind to $PORT in time |
| `Error H10 (App crashed)` | Runtime crash |
| ` ! ` lines | Heroku platform errors |
| `ModuleNotFoundError` / `ImportError` | Missing dependency |
| `no such file or directory` | Missing file/binary |

Read `${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md` for the full
error reference. Read `${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md` for
stack-specific gotchas.

## Step 4a — Deployment succeeded

```bash
heroku ps --app <app-name>
```

Confirm `web.1` is in `up` state.

```bash
curl -s -o /dev/null -w "%{http_code}" https://<app-name>.herokuapp.com/
```

Surface result to user:

```
✓ App is live!

  URL:    https://<app-name>.herokuapp.com
  Status: web.1 up

Open in browser: heroku open --app <app-name>
```

## Step 4b — Deployment failed (self-heal loop, max 3 attempts)

### Diagnose
Map the log pattern to a fix using the error table above.

### Fix
Apply the fix, show the user what you changed:
```bash
cd <target_dir>
# ... edit file(s) ...
git commit -am "fix: resolve deploy failure — <diagnosis>"
git push heroku main
```

Re-run from Step 2. Increment attempt counter. After 3 failed attempts:

```
✗ Deployment failed after 3 attempts.

Last error: <diagnosis>
Relevant logs:
  <log lines>

Suggested next step: <specific fix>
```

## Step 4c — App running but unhealthy

If `heroku ps` shows `web.1` up but HTTP probe returns non-2xx:
- Surface the URL and status code
- Suggest `heroku logs --tail --app <app-name>` for live debugging
- Do not attempt auto-fix for runtime errors — surface to user

## Step 5 — Update session state

If deployment succeeded, update `.heroku-plugin-session.json`:
```json
{
  "deployed": true,
  "app_url": "https://<app-name>.herokuapp.com"
}
```
