---
name: claim-app
description: >-
  Claim an anonymously deployed Heroku preview app so it belongs to the user's
  account. Use when the user says "claim this app", "I want to keep this app",
  "transfer my app to my account", or similar.
argument-hint: "[app-id]"
allowed-tools: Bash, Read
---

# Claim App

The claim itself happens in the browser, on the claim portal, signed in as the user. This skill
finds the claim link, gets the user there, and watches for the result.

Tool contract: `${CLAUDE_PLUGIN_ROOT}/references/mcp-core-contract.md`.

## Step 1 — Load context

Get `app_id`, `claim_url` and `expires_at` from the provided argument or the session file:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py show
```

If there is no `app_id`, tell the user there is no preview app to claim, suggest
`/heroku-plugin:deploy-anonymous`, and stop.

## Step 2 — Get the claim link

```
Tool: get_preview_app_details
Input: { app_id }
Output: { app_id, claim_url, expires_at, ... }
```

Use this response's `claim_url`, not the saved one. The saved link may predate a change, and
an error here (claimed, discarded, expired) tells you the app is gone:

- App already claimed → "This app is already claimed. It's in your Heroku account."
- App discarded or expired → say so and suggest a new deploy. Stop.

`expires_at` is epoch milliseconds. If it is in the past, the claim window has closed; say so
and stop.

## Step 3 — Send the user to the claim page

Show `claim_url` **verbatim** — copy it character for character, do not retype or rebuild it:

```
To keep this app, open this link and sign in to your Heroku account:

  <claim_url>

The claim window closes at <expires_at as a readable local time>.
```

Convert `expires_at` with `python3 -c 'import datetime,sys; print(datetime.datetime.fromtimestamp(int(sys.argv[1])/1000).astimezone().strftime("%Y-%m-%d %H:%M %Z"))' <expires_at>`.

## Step 4 — Watch for the result

```
Tool: check_claim_status
Input: { app_id }
Output: { monitoring: { owner, instruction }, app_id, claimed, expired }
```

If `monitoring.owner` is `"card"`, the Deployment card tracks the claim — do not poll. Otherwise
poll as `monitoring.instruction` says until `claimed` or `expired` is true.

- `claimed: true` → "App claimed! It's now yours on Heroku." It is no longer a preview app, so
  `/heroku-plugin:discard-preview-app` no longer applies to it. Leave the session file alone.
- `expired: true` → "The claim window closed and the preview app is gone. Run deploy again."
