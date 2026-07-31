---
name: go-live
description: >-
  Open or share a deployed Heroku app. Use when the user says "open the app",
  "show me the app", "make it public", "go live", "share the URL", or similar.
  With the CLI deploy path, apps are publicly accessible immediately after deploy.
argument-hint: "[app-name]"
allowed-tools: Bash, Read
---

# Go Live

<!-- TODO: When MCP anonymous deploy is available, this skill will need to call
     update_app (authMode: 'user', post-claim) to set public_routing=true.
     For the CLI deploy path, apps are public by default — no routing toggle needed. -->

## Step 1 — Load context

Get `app_name` and `app_url` from:
1. Provided arguments
2. `.heroku-plugin-session.json` in the current directory

## Step 2 — Verify app is deployed

```bash
heroku ps --app <app-name>
```

If `web.1` is not `up`, suggest running `/heroku-plugin:check-deploy-status` first.

## Step 3 — Confirm the URL

```bash
heroku info --app <app-name>
```

Parse `Web URL:` from output.

## Step 4 — Open in browser

```bash
heroku open --app <app-name>
```

## Step 5 — Surface to user

```
✓ App is live at: <app_url>

  heroku open --app <app-name>     ← open in browser
  heroku logs --tail --app <app-name>  ← watch logs
  heroku ps --app <app-name>           ← check dyno status
  https://dashboard.heroku.com/apps/<app-name>  ← dashboard
```

Note: Apps deployed via the Heroku CLI are publicly accessible by default.
No additional routing toggle is required.
