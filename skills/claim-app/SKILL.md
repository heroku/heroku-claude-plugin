---
name: claim-app
description: >-
  Transfer an anonymously deployed Heroku app to a permanent user account.
  Use when the user says "claim this app", "I want to keep this app",
  "transfer my app to my account", or similar.
argument-hint: "[app-name]"
allowed-tools: Bash, Read
---

# Claim App

<!-- TODO: This skill is MCP-only and requires the connector-mcp anonymous deploy
     implementation (create_preview_app, check_claim_status, W-23636832 nonce
     binding, W-23636833 ToU gate). It is NOT available in CLI deploy mode.
     Remove this notice and implement once MCP work is complete. -->

## Not Available in CLI Mode

This skill requires the anonymous deploy path, which depends on the Heroku
connector-mcp server implementation. It is not available when using the
Heroku CLI deploy path.

Surface this message to the user:

```
The app claim workflow requires the Heroku MCP anonymous deploy path,
which is not yet available.

Your app '<app-name>' is already in your Heroku account (deployed via CLI).
You can manage it directly:

  heroku open --app <app-name>
  https://dashboard.heroku.com/apps/<app-name>
```

## MCP Implementation Notes (for when this is built)

When MCP anonymous deploy is available, this skill should:

1. Load `app_uuid`, `session_id`, and `expires_at` from session state
2. Check claim window — surface error if expired
3. Direct user to claim URL: `${CLAIM_PORTAL_URL}/preview/${app_uuid}`
4. Poll `check_claim_status` MCP tool every 15s until `claimed: true` or `expired: true`
5. On `claimed: true`: update session state, surface permanent URL
6. Note: reauthentication may be required after claim (tokens invalidated on transfer)

Reference: `mcp/references/connector-mcp-tools.md` — `check_claim_status` tool
