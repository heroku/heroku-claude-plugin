---
name: scaffold-app
description: >-
  Scaffold a new application ready for Heroku deployment. Use when the user wants
  to create, build, or generate a new app — phrases like "build me an app",
  "create a new app", "scaffold a project", "make a SaaS app", or similar.
  Supports Node.js (Express), Python (FastAPI, Django, Flask), Ruby on Rails, and Go.
argument-hint: "[app-name] [stack] [--variant fastapi|django|flask] [--addons postgres,redis]"
allowed-tools: Bash, Read, Write, Edit, Task
---

# Scaffold App

You are scaffolding a Heroku-ready application. Follow these steps in order.

## Step 1 — Gather inputs

Ask the user for any missing details:

1. **App name** — kebab-case (e.g. `supply-chef`). If not provided, suggest one based on their description.
2. **Stack** — one of: `node`, `python`, `rails`, `go`. If the user mentioned a language, map it:
   - Python → `python` (ask: FastAPI, Django, or Flask? Default: FastAPI)
   - Node / JavaScript / Express → `node`
   - Ruby / Rails → `rails`
   - Go / Golang → `go`
3. **Addons** — infer from the user's description:
   - Mentions database, store, retrieve, persist → suggest `postgres`
   - Mentions cache, queue, jobs, Redis → suggest `redis`
   - Confirm with user before adding
4. **Target directory** — default: current directory / app-name

Consult `${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md` for stack-specific requirements
and `${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md` for the Heroku contract.

## Step 2 — Run preflight

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --quick --json
```

If git is missing, stop and surface the preflight failure. If docker is missing,
note that local run/test will be unavailable but continue.

## Step 3 — Run scaffolder

Build the scaffold command from gathered inputs:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py \
  --name <app-name> \
  --stack <stack> \
  [--variant <variant>] \
  [--addons <postgres,redis>] \
  [--dir <target-dir>] \
  [--with-docker]   # include if docker is available
```

Parse the JSON summary from stdout. On non-zero exit, relay the stderr error message
verbatim and stop.

## Step 4 — Git init and first commit

```bash
cd <target_dir>
git init
git add -A
git commit -m "Initial Heroku scaffold — <stack> app"
```

## Step 5 — Invoke deploy-readiness-reviewer

Run a deploy readiness review on the scaffolded app:

```
Task(
  subagent_type: "deploy-readiness-reviewer",
  description: "Review deploy readiness of scaffolded app",
  prompt: "Review the scaffolded app at <target_dir> for Heroku deploy readiness.
           Stack: <stack> (variant: <variant>). Addons: <addons>.
           Docker: <with_docker>. Report any blockers and recommendations."
)
```

Relay the agent's report verbatim.

## Step 6 — Report results

Surface a summary:

```
✓ Scaffolded <display_name> app '<app-name>' at <target_dir>

  Addons:  <addon slugs or "none">
  Docker:  <yes/no>

Next: deploy with /heroku-plugin:deploy-anonymous or run locally with:
  docker-compose up   (if Docker available)
```

Return JSON for use by orchestrator skills:
```json
{
  "app_name": "...",
  "stack": "...",
  "variant": "...",
  "target_dir": "...",
  "addons": [],
  "docker_available": true
}
```
