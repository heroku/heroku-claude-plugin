---
name: go-live
description: >-
  Open or share a deployed Heroku app. Use when the user says "open the app",
  "show me the app", "make it public", "go live", "share the URL", or similar.
argument-hint: "[app-name]"
allowed-tools: Read
---

# Go Live

## Step 1 — Load context

Read `.heroku-plugin-session.json` in the current directory. You need:
- `claim_url`
- `expires_at`

If the file is missing or `claim_url` is absent, tell the user:
```
No active session found. Run /heroku-plugin:deploy-anonymous first to deploy an app.
```
And stop.

## Step 2 — Surface to user

```
✓ Your app is ready.

  Open:   <claim_url>

  That link lets you view the running app and claim it to your Heroku account.
  The claim window closes at <expires_at>.
```
