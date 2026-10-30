---
name: discard-preview-app
description: >-
  Discard an unclaimed Heroku preview app. Use when the user says "discard the
  preview app", "throw away the preview", "cancel the preview", "abandon this
  deploy", "start over with a new preview", or when create_preview_app reports
  that a preview app is already active. Only works before the app is claimed.
argument-hint: "[app-id]"
allowed-tools: Bash, Read
---

# Discard Preview App

Discards a preview app that has not been claimed. A user has one active preview app at a
time, so this is also how to free the slot for a new deploy. It does **not** delete a
claimed app — a claimed app belongs to the user's account and is out of scope here.

## Step 1 — Identify the app

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py show
```

Take `session.app_id` from the JSON. If the user passed an `app-id` argument, or an
"already active" error from `create_preview_app` named an app, use that instead.

If there is no `app_id` from any source, stop and tell the user there is no preview app to
discard. Do not guess an ID.

## Step 2 — Confirm with the user

Discarding cannot be undone. Name the app and ask before calling the tool:

```
Discard preview app <app_id>? The app and its data are removed and the preview link stops
working. This cannot be undone.
```

Wait for a clear yes. The server asks for its own confirmation too; both are expected.

## Step 3 — Discard

```
Tool: discard_preview_app
Input: { app_id }
Output: { app_id }
```

Success means the returned `app_id` equals the one you sent. Anything else is a failure.

- `The preview app is not available to be discarded.` — the app is already claimed,
  discarded or expired. Tell the user exactly that. Do not retry and do not call it a
  success. A claimed app is now the user's to manage in their Heroku account.
- Identity or feature-gate errors — show the server's message and stop.

## Step 4 — Clear local session state

Only after a successful discard, clear the session file for that app:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py clear --if-app-id <app_id>
```

Read the JSON it prints. `"cleared": true` means the file is gone. `"cleared": false`
carries a `reason` (`no session file`, or `session app_id does not match` when the file
belongs to a different app). Both are fine to report as-is; neither is an error. Never
remove the file with `rm`.

## Step 5 — Report

State only what the outputs showed:

```
✓ Preview app <app_id> discarded.
  Session state: <cleared | left in place — <reason>>

Run a new deploy whenever you're ready.
```

Do not say the Heroku app was "destroyed". The server marks the preview app discarded and
the platform removes it afterwards.
