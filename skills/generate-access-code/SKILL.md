---
name: generate-access-code
description: >-
  Generate a shareable access code for an anonymously deployed Heroku app preview.
  Use when the user says "share this app", "give me an access code", "share it
  with my colleague", or similar.
argument-hint: "[app-name]"
allowed-tools: Bash, Read
---

# Generate Access Code

<!-- TODO: This skill is MCP-only. Access codes are managed by the Heroku claim
     portal (W-23636832 nonce binding, W-23636833 ToU gate) — there is no MCP
     tool for this; it is browser-side claim portal UX. This skill cannot be
     implemented until the anonymous deploy path (connector-mcp) is available.
     Remove this notice and implement once MCP work is complete. -->

## Not Available in CLI Mode

Access codes are part of the anonymous Heroku deploy preview flow, which depends
on the connector-mcp server implementation. They are not available when using
the Heroku CLI deploy path.

Surface this message to the user:

```
Access codes are part of the anonymous Heroku preview flow, which is not
yet available.

To share your app deployed via CLI, share the URL directly:
  https://<app-name>.herokuapp.com

Your app is publicly accessible. Anyone with the URL can view it.
```

## MCP Implementation Notes (for when this is built)

Access code generation is browser-side claim portal UX — there is no MCP tool
for it. When anonymous deploy is available:

- The claim portal at `${CLAIM_PORTAL_URL}/preview/${app_uuid}` handles access
- Users share the direct app URL; access control is managed through the ToU/nonce binding
- Max 5 access codes per app is a claim portal constraint, not an MCP constraint

Reference: `mcp/references/connector-mcp-tools.md` — authentication model section
Reference: `mcp/references/gus-epic-summary.md` — W-23636832, W-23636833
