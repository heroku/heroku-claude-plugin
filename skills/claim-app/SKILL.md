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

<!-- TODO: This skill needs implementation. The MCP deploy path (deploy-anonymous)
     is in place. This skill should use mcp-portal's check_claim_status tool and
     the claim portal URL surfaced by deploy-anonymous. Remove this notice when
     implemented. See mcp/references/mcp-portal-tools.md for tool contracts. -->

## Not Yet Implemented

The MCP deploy path is live (`deploy-anonymous` uses mcp-portal), but this skill's
claim flow has not been implemented yet. Surface this message to the user:

```
The app claim workflow is not yet implemented.

Your app preview link was surfaced by the deploy step. Visit it to claim ownership:
  https://claim-canary.heroku.com/preview/<app_uuid>
```

## Implementation Notes

When this skill is implemented, it should:

1. Load `app_uuid`, `session_id`, and `expires_at` from session state
2. Check claim window — surface error if expired
3. Direct user to claim URL: `${CLAIM_PORTAL_URL}/preview/${app_uuid}`
4. Poll `check_claim_status` MCP tool every 15s until `claimed: true` or `expired: true`
5. On `claimed: true`: update session state, surface permanent URL
6. Note: reauthentication may be required after claim (tokens invalidated on transfer)

Reference: `mcp/references/mcp-portal-tools.md` — `check_claim_status` tool
