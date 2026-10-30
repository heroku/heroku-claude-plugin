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

<!-- TODO: The app_id flow in this skill and its children has not yet had a live end-to-end
     run against the mcp-portal. Verify with the `discard-website` and `saas-*` scenarios
     (evals/scenarios) and remove this note once they pass. -->

You are running the complete Heroku build-and-deploy workflow. This orchestrates
atomic skills in sequence. Each step is independently resumable via session state.

## Step 1 — Load or resume session state

Check for `.heroku-plugin-session.json` in the current directory. If it contains
a partial session, ask:

```
I found a previous session for '<app_name>'. Resume from where we left off?
```

Read it with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py show`. If resuming: skip
completed steps based on the fields present (`deployed_at` means the deploy finished; an
`app_id` without `deployed_at` means a preview app exists but the deploy did not finish).

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

This skill creates the preview app via `create_preview_app`, sets secrets with
`set_config_vars` if the stack needs any, kicks off addon provisioning, pushes code via git
promptly (the git token is short-lived), then monitors the build and addon readiness as the
server's `monitoring` guidance directs.

If it stops because a preview app is **already active**, or because preview apps are
unavailable for this user, do not continue to Step 5. Relay what it reported. For an active
app, offer `/heroku-plugin:discard-preview-app` and resume Step 4 once the user has chosen.

## Step 5 — Surface next steps

`deploy-anonymous` has already shown the Preview and Claim links (or the Deployment card
has). Do not repeat or rebuild them here. Close with the next steps:

```
✓ Your app is deployed.

What would you like to do next?

  • Continue developing locally — your code is at <target_dir>
  • Claim this app:        /heroku-plugin:claim-app
  • Discard the preview:   /heroku-plugin:discard-preview-app
```

The claim window is about 1 hour; unclaimed apps are removed when it closes.

## Recovery

If any step fails, check `.heroku-plugin-session.json` to understand what completed.
Surface the last known good state and suggest which atomic skill to run next.
