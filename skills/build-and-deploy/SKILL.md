---
name: build-and-deploy
description: >-
  Complete end-to-end workflow: scaffold a new app and deploy it to Heroku.
  Use when the user wants the full journey from description to live deploy in one step —
  phrases like "build and deploy", "create an app and deploy it to Heroku", "I want to
  build a SaaS app and host it on Heroku", or any prompt that implies both building
  and deploying. This orchestrates: preflight → scaffold-app → deploy → check-deploy-status.
argument-hint: "[description of the app]"
allowed-tools: Bash, Read, Task
---

# Build and Deploy

<!-- TODO: Step 4 below delegates to deploy-anonymous, which now uses the mcp-portal
     MCP path (deploy_mode: "mcp" is already set in plugin.json). Step 5 needs to be
     updated: surface the claim portal URL from session state rather than a raw
     *.herokuapp.com URL. The mcp-portal provisioning path is still stubbed on the
     canary — a live test is blocked until the server team ships real provisioning.
     See mcp/mcp-portal-readiness.md. -->

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

```
Task(
  subagent_type: "preflight",
  description: "Run preflight checks",
  prompt: "Run preflight checks. Return JSON result with git and docker status."
)
```

Gate on: `git: true`. Stop if it fails.
Note `docker` availability — pass to scaffold-app via `with_docker`.

## Step 3 — Scaffold the app

```
Task(
  subagent_type: "scaffold-app",
  description: "Scaffold Heroku app from user requirements",
  prompt: "Scaffold an app based on the user's description: '<user_description>'.
           docker_available: <true|false>.
           Return JSON with app_name, stack, variant, target_dir, addons, docker_available."
)
```

Parse result. Save to session state.

## Step 4 — Deploy to Heroku (MCP)

```
Task(
  subagent_type: "deploy-anonymous",
  description: "Deploy scaffolded app to Heroku via mcp-portal",
  prompt: "Deploy app '<app_name>' at '<target_dir>' to Heroku.
           Stack: <stack>. Addons: <addons>."
)
```

This task creates an anonymous session, creates the Heroku app via `create_preview_app`,
provisions addons, sets secrets (CLI hybrid if needed), pushes code via git, and monitors
the build via `get_deployment_status`.

## Step 5 — Surface next steps

After successful deployment, surface the claim portal URL from session state
(`web_url` returned by `get_deployment_status`):

```
✓ Your app is live!

  ─────────────────────────────────────────────────
  Preview:   https://claim-canary.heroku.com/preview/<app_uuid>
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
