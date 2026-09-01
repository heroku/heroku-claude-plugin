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

<!-- TODO: Access codes are managed by the Heroku claim portal — there is no MCP
     tool for this; it is browser-side UX. The deploy path (MCP) is in place.
     This skill surfaces a message pointing users to the claim portal URL.
     Remove this notice when the claim portal UX is confirmed. -->

## Not Available via MCP

Access codes are browser-side claim portal UX — there is no MCP tool for them.
Surface this message to the user:

```
Access code generation is handled by the Heroku claim portal, not via MCP.

To share your deployed app, share the claim portal URL from your deploy step.
The `web_url` returned by `get_deployment_status` is the claim portal URL.

From the claim portal, the recipient can accept the Terms of Service and
take ownership of the app.
```

## Notes

- The claim portal URL is the `web_url` from `get_deployment_status`
- Access control is managed through the ToU/nonce binding on the portal side
- The `app_uuid` is saved in `.heroku-plugin-session.json` after a successful deploy
