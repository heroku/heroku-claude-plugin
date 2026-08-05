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

Read `${CLAUDE_PLUGIN_ROOT}/references/heroku/build-standards.md` before starting.
The ALWAYS rules defined there apply to this entire skill without exception.

## Step 1 — Confirm requirements

Before writing a single line of code, confirm the following with the user:

1. **Stack** — one of: `node`, `python`, `rails`, `go`.
   - If no preference given, present the supported options and ask
   - If an unsupported stack is requested (e.g. Elixir, Java), surface the supported list and ask for a preference
   - If the user mentions a frontend framework (Vue, React, etc.), clarify: is this needed for MVP or is an API sufficient? Default to API-only unless explicitly confirmed otherwise
   - Map languages to stacks: Python → `python`, Node/JS → `node`, Ruby/Rails → `rails`, Go/Golang → `go`
   - Python: ask FastAPI, Django, or Flask? Default: FastAPI

2. **What is being built** — confirm the feature scope explicitly:
   - What does this app do?
   - What are the minimum features needed for a working app?
   - What is explicitly out of scope for this build?

3. **Addons** — infer from description, confirm before adding:
   - Database / store / persist → suggest `postgres`
   - Cache / queue / jobs → suggest `redis`

4. **App name** — kebab-case. Suggest one based on description if not provided.

5. **Target directory** — default: current directory / app-name

Present a summary and get explicit confirmation before proceeding:

```
Here's what I'm going to build:

  App:     <app-name>
  Stack:   <stack> (<variant if python>)
  Addons:  <addons or "none">
  Scope:   <bullet list of confirmed features>
  Out of scope: <bullet list>

Shall I proceed?
```

Do not proceed until the user confirms.

## Step 2 — Read references

Read these files before writing any code:

```
${CLAUDE_PLUGIN_ROOT}/references/stacks/<stack>.md
${CLAUDE_PLUGIN_ROOT}/references/heroku/deploy-contract.md
${CLAUDE_PLUGIN_ROOT}/references/standards/<language>.md
```

Where `<language>` maps to: python → `python.md`, node → `javascript.md`, rails → `ruby.md`, go → `go.md`

## Step 3 — Run preflight

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --quick --json
```

Gate on `git: true`. If docker is missing, note that local run/test will be unavailable but continue.

## Step 4 — Run scaffolder

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py \
  --name <app-name> \
  --stack <stack> \
  [--variant <variant>] \
  [--addons <postgres,redis>] \
  [--dir <target-dir>] \
  [--with-docker]
```

Parse the JSON summary from stdout. On non-zero exit, relay the stderr error message verbatim and stop.

## Step 5 — Build features using TDD

For each confirmed feature, follow the TDD cycle strictly:

1. **Write a failing test** that describes the expected behavior
2. **Run it** — confirm it fails for the right reason
3. **Implement** the minimum code to make it pass
4. **Run tests** — confirm it passes, no regressions
5. Move to the next feature

Reference `${CLAUDE_PLUGIN_ROOT}/references/standards/<language>.md` for testing patterns,
test structure, and framework-specific test clients.

Never write implementation code without a corresponding test.

## Step 6 — Run pre-commit checklist

Before committing, work through every item in:
`${CLAUDE_PLUGIN_ROOT}/references/heroku/pre-commit-checklist.md`

All items must pass:
- Tests pass at 90%+ coverage
- No lint errors
- Code formatted
- Security scan clean
- No unnecessary code (no dead code, no empty implementations, no debug statements)
- All tests are meaningful
- No secrets in staged files

Do not commit until every item passes.

## Step 7 — Git init and commit

```bash
cd <target_dir>
git init
git add -A
git commit -m "Initial Heroku scaffold — <stack> app"
```

## Step 8 — Invoke deploy-readiness-reviewer

```
Task(
  subagent_type: "deploy-readiness-reviewer",
  description: "Review deploy readiness of scaffolded app",
  prompt: "Review the scaffolded app at <target_dir> for Heroku deploy readiness.
           Stack: <stack> (variant: <variant>). Addons: <addons>.
           Docker: <with_docker>. Report any blockers and recommendations."
)
```

Fix any blockers before proceeding. Relay the full report to the user.

## Step 9 — Report results

```
✓ Scaffolded <display_name> app '<app-name>' at <target_dir>

  Addons:  <addon slugs or "none">
  Docker:  <yes/no>
  Tests:   <test count> passing, <coverage>% coverage

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
