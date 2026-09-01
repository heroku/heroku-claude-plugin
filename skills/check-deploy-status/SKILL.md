---
name: check-deploy-status
description: >-
  Check Heroku deployment status and verify the app is running. Use after
  deploying to Heroku, or when the user asks "is my app deployed?", "check
  the build", "what happened to my deploy?", "are there any errors?", or similar.
  On failure, delegates diagnosis and repair to the `diagnose-and-fix` sub-agent
  (explicit Task delegation — LLM role is interpreting novel log text).
argument-hint: "[app-uuid]"
allowed-tools: Bash, Read, Task, mcp__plugin_heroku-plugin_mcp-portal__get_deployment_status, mcp__plugin_heroku-plugin_mcp-portal__get_build_output
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

## Step 4b — Deployment failed (self-heal loop, max 3 attempts)

<!-- Why a sub-agent call here: the LLM's irreducible role is interpreting novel
     log text to determine root cause and apply a targeted fix. Making the
     delegation explicit (rather than embedding it in prose) improves
     testability — the Task boundary can be exercised in isolation — and
     reliability, because the sub-agent receives focused context with a
     structured return contract. -->

Initialize `attempt = 1`. While `attempt <= 3`:

1. Collect the log excerpt from `build.log` (last 50–100 lines).

2. Call the `diagnose-and-fix` sub-agent:

   ```
   Task(
     subagent_type: "diagnose-and-fix",
     description: "Diagnose and fix Heroku deploy failure",
     prompt: "Diagnose the following Heroku deploy failure and apply a fix.
              App UUID: '<app_uuid>' at '<target_dir>'. Stack: '<stack>'.
              Log excerpt:
              <log lines>

              Reference ${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md
              for known error patterns.
              Reference ${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md
              for stack-specific gotchas.

              Apply the fix, commit with message 'fix: <diagnosis>', and return:
              { \"fixed\": true|false, \"diagnosis\": \"...\", \"fix_applied\": \"...\" }"
   )
   ```

3. If `result.fixed == true`: re-run `deploy-anonymous` from Step 8 (git push).
   Increment `attempt`.

4. If `result.fixed == false`: increment `attempt` and loop.

After 3 failed attempts (or if the sub-agent cannot fix):

```
✗ Deployment failed after 3 attempts.

Last error: <diagnosis>
Relevant logs:
  <log lines>

Suggested next step: <specific fix>
```

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
