# heroku-plugin

A Claude Code plugin that scaffolds and deploys applications to Heroku from natural language prompts. Describe what you want to build — the plugin generates the code, creates the Heroku app, provisions addons, and deploys it.

## Getting Started

The only thing you need before launching is [Claude Code](https://claude.ai/code). Everything else is handled by the plugin.

Launch Claude Code with the plugin loaded:

```bash
claude --plugin-dir /path/to/heroku-plugin
```

Then describe what you want to build:

```
Build me a Python REST API and deploy it to Heroku
```

Before any work starts, the plugin checks your environment and walks you through anything that's missing:

- **git** — required. Install instructions surfaced if not found.
- **Docker Desktop** — optional. The plugin explains what it enables and offers to install it. You can skip it and still deploy to Heroku.

The deploy path uses the Heroku mcp-portal MCP server — no Heroku CLI login required for app creation or deployment. The CLI is only used when the scaffolded app needs generated secrets (e.g. `DJANGO_SECRET_KEY`).

Once the environment is ready, the plugin scaffolds the code, creates the Heroku app, provisions any addons, and deploys — all from that one prompt.

## Supported Stacks

| Stack | Variants |
|-------|---------|
| Python | FastAPI (default), Django, Flask |
| Node.js | Express |
| Ruby on Rails | PostgreSQL-backed |
| Go | net/http |

## Supported Addons

- `heroku-postgresql`
- `heroku-redis`

## Skills

| Skill | How to trigger |
|-------|---------------|
| `build-and-deploy` | "Build me an app and deploy it to Heroku" |
| `scaffold-app` | "Scaffold a Node.js app" |
| `deploy-anonymous` | "Deploy the app to Heroku" |
| `check-deploy-status` | "Is my app deployed?" / "Check the build" |
| `go-live` | "Open the app" / "Show me the URL" |
| `teardown` | "Clean up the app" / "Destroy the app" |
| `preflight` | "Check my environment" |

---

## Live Testing Guide

This section covers how to exercise the plugin against a real Heroku account.

### Setup

1. Clone this repo and navigate to it
2. Ensure `HEROKAI_SECRET` is set in your environment (contact the mcp-portal team for access)
3. Create a fresh directory for each test run:
   ```bash
   mkdir ~/heroku-plugin-tests/run-01
   cd ~/heroku-plugin-tests/run-01
   ```
4. Launch Claude with the plugin:
   ```bash
   claude --plugin-dir /path/to/heroku-plugin
   ```

> **Note:** Live end-to-end testing requires a working mcp-portal staging server. Session creation and app provisioning are confirmed working (2026-08-28). Currently blocked on `get_deployment_status` returning errors on staging. Check `mcp/mcp-portal-readiness.md` for current status.

### Test Scenarios

Submit each prompt in a fresh session. After each run, use the teardown prompt to reset.

#### Happy Path — One per Stack

| # | Prompt | Expected outcome |
|---|--------|-----------------|
| 1 | "Build me a simple REST API in Python and deploy it to Heroku" | FastAPI app, no addons, live on Heroku |
| 2 | "Create a Node.js web app and deploy it" | Express app, no addons, live on Heroku |
| 3 | "I want a Go API deployed to Heroku" | Go app, no addons, live on Heroku |
| 4 | "Build a Rails app with a database and deploy it" | Rails + Postgres, live on Heroku |

#### Addon Coverage

| # | Prompt | Expected outcome |
|---|--------|-----------------|
| 5 | "Build a Python app with a database and a cache layer" | FastAPI + Postgres + Redis |
| 6 | "Create a Django app" | Django, auto-picks Postgres |

#### Variant Coverage

| # | Prompt | Expected outcome |
|---|--------|-----------------|
| 7 | "Build a Flask app and deploy it to Heroku" | Python/Flask variant |

#### Edge Cases

| # | Prompt | Expected outcome |
|---|--------|-----------------|
| 8 | "Deploy my app to Heroku" _(no scaffold first)_ | Prompts to scaffold first |
| 9 | "Check my environment" | Preflight report — git, Heroku login, Docker |
| 10 | "Share my app with a colleague" | Surfaces MCP-not-available message, suggests sharing URL directly |

### Resetting Between Runs

At the end of each session, ask Claude to clean up:

```
Please clean up the app
```

The `teardown` skill will:
1. Confirm the app name before destroying anything
2. Destroy the Heroku app and all its addons
3. Clear local session state (`.heroku-plugin-session.json`)
4. Save a session record to moot — a run steps memory and one memory per issue encountered, both tagged `heroku build-and-deploy` for easy retrieval

Previous runs are searchable with: `moot search "heroku build-and-deploy"`

Then start the next run in a fresh directory:

```bash
mkdir ~/heroku-plugin-tests/run-02
cd ~/heroku-plugin-tests/run-02
claude --plugin-dir /path/to/heroku-plugin
```

### What to Evaluate

For each scenario, assess:

- **Scaffold quality** — does the generated code follow the language's best practices? Are linting configs present?
- **Deploy success** — did the MCP session, addon provisioning, and git push complete without manual intervention?
- **Error handling** — if something failed, did the plugin diagnose it and self-heal (up to 3 attempts)?
- **Output clarity** — were the URLs, next steps, and status messages easy to understand?
- **Teardown** — did cleanup remove the app and clear session state correctly?

---

## Development

### Running Tests

Generator evals (fast, no Docker, CI on every push):

```bash
python3 -m unittest discover -s evals/generator -v
```

Container evals (requires Docker, CI on PR + main):

```bash
python3 -m unittest discover -s evals/container -v
```

Scaffold dry-run:

```bash
python3 scripts/scaffold.py --name my-app --stack python --variant fastapi --dry-run
```

Preflight dry-run:

```bash
python3 scripts/preflight.py --dry-run
```

### Project Structure

```
skills/          Atomic skills + build-and-deploy orchestrator
scripts/         scaffold.py, preflight.py, heroku_glue/ stack modules
references/      Local Heroku docs (seeded, staleness-checked)
hooks/           UserPromptSubmit + PreCompact hook scripts
evals/           Generator, container, and skill evals
.claude-plugin/  plugin.json manifest + hooks.json registration
```
