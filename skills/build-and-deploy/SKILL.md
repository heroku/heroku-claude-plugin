---
name: build-and-deploy
description: >-
  Complete end-to-end workflow: scaffold a new app and deploy it to Heroku.
  Use when the user wants the full journey from description to live deploy in one step —
  phrases like "build and deploy", "create an app and deploy it to Heroku", "I want to
  build a SaaS app and host it on Heroku", or any prompt that implies both building
  and deploying. This orchestrates: preflight → scaffold-app → deploy → check-deploy-status.
argument-hint: "[description of the app]"
allowed-tools: Bash, Read
---

# Build and Deploy

<!-- TODO: Step 5 needs a live end-to-end test to confirm the claim portal URL is
     surfaced correctly. Blocked on get_deployment_status returning "try again shortly"
     on staging as of 2026-08-28. Track status in mcp/mcp-portal-readiness.md. -->

You are running the complete Heroku build-and-deploy workflow. This orchestrates
atomic skills in sequence. Each step is independently resumable via session state.

## Step 1 — Load or resume session state

Check for `.heroku-plugin-session.json` in the current directory. If it contains
a partial session, ask:

```
I found a previous session for '<app_name>'. Resume from where we left off?
```

If resuming: skip completed steps based on session state fields present
(`deployed: true` means deploy already happened).

## Step 2 — Run preflight

Invoke the preflight skill using the `Skill` tool:

```
Skill: heroku-plugin:preflight
```

Gate on: `git: true`. Stop if it fails.
Note `docker` availability — pass to scaffold-app via `with_docker`.

## Step 3 — Scaffold the app

Invoke the scaffold-app skill using the `Skill` tool:

```
Skill: heroku-plugin:scaffold-app
Args: <user_description>
```

Parse result. Save to session state.

## Step 4 — Deploy to Heroku (MCP)

Invoke the deploy-anonymous skill using the `Skill` tool:

```
Skill: heroku-plugin:deploy-anonymous
```

This skill creates an anonymous session, creates the Heroku app via `create_preview_app`,
sets secrets (CLI hybrid if needed) and kicks off addon provisioning, pushes code via git
promptly (the git token is short-lived), then monitors the build and addon readiness
concurrently via `get_deployment_status` / `get_addon_status`.

## Step 5 — Surface next steps

After successful deployment, surface the claim portal URL from session state
(`web_url` returned by `get_deployment_status`):

```
✓ Your app is live!

  ─────────────────────────────────────────────────
  Preview:   <web_url from get_deployment_status>
  ─────────────────────────────────────────────────

Visit the preview URL to claim ownership of this app before the window closes.

What would you like to do next?

  • Continue developing locally — your code is at <target_dir>
  • Claim this app:  /heroku-plugin:claim-app
  • Clean up:        /heroku-plugin:teardown
```

## Recovery

If any step fails, check `.heroku-plugin-session.json` to understand what completed.
Surface the last known good state and suggest which atomic skill to run next.
