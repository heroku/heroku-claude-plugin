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

<!-- TODO: Currently uses Heroku CLI deploy path. When connector-mcp anonymous deploy
     is available, update Step 4 to use deploy-anonymous (MCP path) and add Step 5
     claim/access-code flow. Switch deploy_mode in plugin.json from "cli" to "mcp". -->

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
  prompt: "Run preflight checks. Return JSON result with git, heroku, heroku_logged_in, and docker status."
)
```

Gate on: `git: true`, `heroku: true`, `heroku_logged_in: true`. Stop if any fail.
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

## Step 4 — Deploy to Heroku (CLI)

```
Task(
  subagent_type: "deploy-anonymous",
  description: "Deploy scaffolded app to Heroku via CLI",
  prompt: "Deploy app '<app_name>' at '<target_dir>' to Heroku.
           Stack: <stack>. Addons: <addons>."
)
```

This task creates the Heroku app, provisions addons, pushes code via git,
and calls check-deploy-status.

## Step 5 — Surface next steps

After successful deployment:

```
✓ Your app is live!

  ─────────────────────────────────────────────────
  URL:       https://<app_name>.herokuapp.com
  Dashboard: https://dashboard.heroku.com/apps/<app_name>
  ─────────────────────────────────────────────────

What would you like to do next?

  • Continue developing locally — your code is at <target_dir>
  • Watch logs:    heroku logs --tail --app <app_name>
  • Scale dynos:   heroku ps:scale web=1 --app <app_name>
  • Open app:      /heroku-plugin:go-live
```

## Recovery

If any step fails, check `.heroku-plugin-session.json` to understand what completed.
Surface the last known good state and suggest which atomic skill to run next.
