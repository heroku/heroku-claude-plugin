# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin that scaffolds and deploys applications to Heroku from natural language prompts. It follows the Track 1 steel thread: user describes an app → plugin scaffolds it → deploys to Heroku → app is live.

The reference implementation is `~/src/heroku-mcp-plugin`.

## Using the Plugin

Launch Claude Code with the plugin loaded:

```bash
claude --plugin-dir /path/to/heroku-plugin
```

The `UserPromptSubmit` hook fires automatically on any build or deploy prompt — no setup step needed. Just describe what you want to build and the plugin takes it from there. Preflight failures (missing git, not logged in to Heroku, etc.) are surfaced inline before any skill runs.

## Commands

### Tests

Generator evals are pure Python, CI-friendly, and cover Layer 2 determinism:

```bash
python3 -m unittest discover -s evals/generator -v           # all stacks
python3 -m unittest evals.generator.test_stacks.GoStackEval -v  # one stack
KEEP_EVAL_ARTIFACTS=1 python3 -m unittest discover -s evals/generator
```

Container evals require Docker and verify apps actually boot:

```bash
python3 -m unittest discover -s evals/container -v
```

Skill evals are run manually:

```bash
python3 evals/skills/trigger_eval.py                          # trigger discrimination
python3 evals/skills/trigger_eval.py --skill scaffold-app
HEROKU_MCP_STUB=1 python3 evals/skills/e2e_build_and_deploy.py --stack python
HEROKU_MCP_STUB=1 python3 evals/skills/e2e_build_and_deploy.py --stack go --keep
```

Scaffold dry-run (no files written):

```bash
python3 scripts/scaffold.py --name my-app --stack python --variant fastapi --dry-run
```

Preflight check:

```bash
python3 scripts/preflight.py --dry-run
```

No build step — pure Python (stdlib only) + Markdown.

## Architecture

### Two-Layer Scaffold Model

**Layer 1 — Idiom:** Runs the ecosystem's native generator. Output varies by tool version. Not tested for byte-identity.

**Layer 2 — Contract:** Writes deterministic Heroku glue files (`Procfile`, `app.json`, `docker-compose.yml`, `Dockerfile`). Byte-identical across runs. This layer is what the generator evals assert.

`scripts/scaffold.py` is the orchestration spine. Stack modules live in `scripts/heroku_glue/`.

### Docker Model

Docker is for **local dev only** — never pushed to Heroku. When Docker is available:
- `Dockerfile` (local dev) and `docker-compose.yml` (app + Postgres + Redis sidecars) are generated
- `docker-compose.yml` mirrors Heroku addon config vars exactly (`DATABASE_URL`, `REDIS_URL`)
- Heroku deploy stays on the buildpack path (`git push heroku main`)

Docker is optional. Preflight prompts the user with an explanation before offering to install it. `git` is the only hard requirement.

### Skills (Atomic + Orchestrator)

All skills live in `skills/*/SKILL.md`. Atomic skills are independently triggerable; the orchestrator chains them.

| Skill | Type | Triggers on |
|-------|------|------------|
| `preflight` | atomic | environment checks, setup |
| `scaffold-app` | atomic | build/create/scaffold prompts |
| `deploy-anonymous` | atomic | deploy/push prompts |
| `check-deploy-status` | atomic | build status, deployment polling |
| `generate-access-code` | atomic | share prompts |
| `claim-app` | atomic | claim/register/transfer prompts |
| `go-live` | atomic | make public/live prompts |
| `teardown` | atomic | destroy app, clean up local session state |
| `build-and-deploy` | orchestrator | full build + deploy in one step |

### MCP Stubs

All Heroku MCP calls are stubbed via `HEROKU_MCP_STUB=1`. Stubs in `mcp/stubs/` conform to MCP tool result spec. The anonymous deploy path depends on Heroku identity team work (in progress); stub mode is the default.

### Hooks

- **`UserPromptSubmit`** — detects build/deploy intent keywords; runs quick preflight (git + docker check only)
- **`PreCompact`** — serializes session state to `.heroku-plugin-session.json` before context compaction

### Reference Files

Local Heroku docs and coding standards in `references/`. Each file is stamped with source URL + verification date. Preflight checks for files older than `policy.reference_staleness_days` (default: 30) and triggers a targeted refetch.

## Key Conventions

### Layer 2 Determinism (enforced by evals)

- Encoding: UTF-8, LF only, exactly one trailing newline
- JSON: 2-space indent, `sort_keys=True`
- Addon lists: sorted and deduplicated
- `effective_addons()` is the single source of truth — feeds both `app.json` and the JSON summary

### Shared Helpers (`scripts/heroku_glue/common.py`)

- `write_file(path, content)` — UTF-8 + LF + trailing newline
- `write_json(path, data)` — sorted keys + 2-space indent
- `merge_gitignore(target_dir, lines)` — append-only, never clobbers
- `build_docker_compose(app_name, addons)` — deterministic docker-compose.yml
- `require_tools([(binary, url)])` — fails loudly before touching the filesystem
- `effective_addons(module, options)` — single source of truth for addon slugs

### Stack Module Protocol

Every stack module (`scripts/heroku_glue/<stack>.py`) implements:

```python
STACK: str
DISPLAY_NAME: str
REQUIRED_TOOLS: list[tuple[str, str]]
DEFAULT_ADDONS: list[str]

def effective_addons(options) -> list[str]
def scaffold(app_name, target_dir, options) -> None    # Layer 1
def apply_glue(app_name, target_dir, options) -> None  # Layer 2
def gitignore_lines(options) -> list[str]
```

Python module supports `variant` option: `fastapi` (default), `django`, `flask`.

### Safety

- Toolchain checks run **before** any writes
- Rollback only removes `target_dir` if **this run** created it
- Skills show diffs before applying edits
- No `.env` or secrets committed; Heroku config vars set manually

### Supported Stacks + Addons (v1)

Stacks: `node`, `python` (fastapi/django/flask), `rails`, `go`
Addons: `heroku-postgresql`, `heroku-redis` (Kafka: unsupported in v1)
Addons during anonymous deploy: available (provisioned with app)
Addons post-claim: billable to user's account

### plugin.json Policy

```json
"policy": {
  "reference_staleness_days": 30,
  "mcp_stub": false,
  "supported_stacks": ["node", "python", "rails", "go"],
  "supported_addons": ["heroku-postgresql", "heroku-redis"],
  "unsupported_addons": ["kafka"]
}
```

### Eval Strategy

- Generator evals: Layer 2 byte-identity, no LLM, CI on every push, output to `evals/.tmp/`
- Container evals: Docker boot tests (eval Dockerfiles, not CNBs), CI on PR + main
- Skill evals: trigger discrimination + E2E in stub mode, run manually or via `workflow_dispatch`
