---
name: go-live
description: >-
  Open or share a deployed Heroku app. Use when the user says "open the app",
  "show me the app", "make it public", "go live", "share the URL", or similar.
argument-hint: "[app-id]"
allowed-tools: Bash, Read
---

# Go Live

## Step 1 — Load context

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py show
```

You need `session.app_id`. If it is missing, tell the user:
```
No active session found. Run /heroku-plugin:deploy-anonymous first to deploy an app.
```
And stop.

## Step 2 — Get fresh links

```
Tool: share_in_browser
Input: { app_id }
Output: { authorization_url, expires_in, preview_link, instruction }
```

A preview link is single-use and short-lived, so always request a new one rather than reusing
an old link. An error saying the app was claimed, discarded or expired means it is gone; say
that and stop.

Use `session.claim_url` for the claim link, or call `get_preview_app_details { app_id }` if it
is absent.

## Step 3 — Surface to user

Copy `preview_link` and the claim link **verbatim**, and follow `instruction` for the preview
link. Do not fetch either link yourself.

```
✓ Your app is ready.

  <preview_link>   ← view the running app (single use)
  <claim_link>     ← claim it to your Heroku account

  The claim window closes at <expires_at as a readable local time>.
```

`session.expires_at` is epoch milliseconds. Convert it with
`python3 -c 'import datetime,sys; print(datetime.datetime.fromtimestamp(int(sys.argv[1])/1000).astimezone().strftime("%Y-%m-%d %H:%M %Z"))' <expires_at>`.
