---
name: go-live
description: >-
  Open or share a deployed Heroku app. Use when the user says "open the app",
  "show me the app", "make it public", "go live", "share the URL", or similar.
argument-hint: "[app-name]"
allowed-tools: Bash, Read, mcp__plugin_heroku-plugin_mcp-portal__get_deployment_status, mcp__plugin_heroku-plugin_mcp-portal__share_in_browser
---

# Go Live

## Step 1 — Load context

Read `.heroku-plugin-session.json` in the current directory. You need:
- `conversation_id`
- `app_uuid`
- `claim_url` (the claim portal URL from the deploy)

If the file is missing or `app_uuid` is absent, tell the user:
```
No active session found. Run /heroku-plugin:deploy-anonymous first to deploy an app.
```
And stop.

## Step 2 — Check deployment status

```
Tool: get_deployment_status
Input: { conversation_id, app_uuid }
Output: { web_url, expires_at, build: { done, failed } }
```

If `build.done` is false, tell the user the build is still in progress and suggest
running `/heroku-plugin:check-deploy-status` to monitor it.

If `build.failed` is true, tell the user the build failed and suggest re-deploying.

## Step 3 — Get a fresh preview URL

```
Tool: share_in_browser
Input: { conversation_id, app_uuid }
Output: { url }
```

## Step 4 — Surface to user

```
✓ Your app is live!

  Preview:  <url from share_in_browser>     ← view the running app
  Claim:    <web_url from get_deployment_status>  ← transfer to your Heroku account

  The claim link lets you permanently add this app to your Heroku account.
```
