# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin that scaffolds and deploys applications to Heroku from natural language prompts. It follows the Track 1 steel thread: user describes an app → plugin scaffolds it → deploys to Heroku → app is live.

The deploy path uses the mcp-portal MCP server (authenticated preview-app flow). `mcp/mcp-core-contract.md` is the source of truth for the tool surface; `mcp/mcp-deploy-plan*.md` and `mcp/mcp-portal-readiness.md` are historical and describe the retired session-based flow.

## Using the Plugin

Launch Claude Code with the plugin loaded:

```bash
claude --plugin-dir /path/to/heroku-plugin
```

The `UserPromptSubmit` hook fires automatically on any build or deploy prompt — no setup step needed. Just describe what you want to build and the plugin takes it from there. Preflight failures (missing git, etc.) are surfaced inline before any skill runs. The mcp-portal connector is added to Claude Code manually and authenticates as the user's verified Heroku identity; the plugin ships no `.mcp.json`.

## Skill Dispatch (Required)

**Never scaffold, build, or deploy by running bash commands directly.** Always invoke the appropriate skill via the `Skill` tool:

- Use `heroku-plugin:build-and-deploy` for a full build + deploy in one step
- Use individual atomic skills (`heroku-plugin:scaffold-app`, `heroku-plugin:deploy-anonymous`, etc.) when the user invokes them explicitly

Do not reproduce skill steps inline. Do not call `heroku create`, `git push heroku`, or `heroku buildpacks:add` directly — those are the skill's responsibility. Delegate via the `Skill` tool every time.

The deploy path is MCP-based. The `deploy-anonymous` skill calls mcp-portal tools; it does not use the Heroku CLI for app creation or git push.

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

**Layer 2 — Contract:** Writes deterministic Heroku glue files (`Procfile`, `project.toml`, `.heroku-plugin-scaffold.json`, `docker-compose.yml`, `Dockerfile`). Byte-identical across runs. This layer is what the generator evals assert.

`scripts/scaffold.py` is the orchestration spine. Stack modules live in `scripts/heroku_glue/`.

### Docker Model

Docker is for **local dev only** — never pushed to Heroku. When Docker is available:
- `Dockerfile` (local dev) and `docker-compose.yml` (app + Postgres + Redis sidecars) are generated
- `docker-compose.yml` mirrors Heroku addon config vars exactly (`DATABASE_URL`, `REDIS_URL`)
- Heroku deploy uses the mcp-portal git push path (not `heroku` remote — see `deploy-anonymous` skill)

Docker is optional. Preflight prompts the user with an explanation before offering to install it. `git` is the only hard requirement. The Heroku CLI is not used anywhere in the plugin — app creation, git credentials, secrets (`set_config_vars`, when `secret_env_vars` is non-empty in `.heroku-plugin-scaffold.json`) and discard are all mcp-portal tools.

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
| `discard-preview-app` | atomic | discard/cancel an unclaimed preview app |
| `teardown` | atomic | destroy app, clean up local session state |
| `build-and-deploy` | orchestrator | full build + deploy in one step |

### MCP Deploy Path

The deploy path calls the mcp-portal MCP server through a connector the user adds manually (the plugin has no `.mcp.json`). There are no sessions: the server identifies the caller by their verified Heroku login, each user has **one active preview app**, and every call after creation takes `app_id` (not `app_uuid`). Full contract: `mcp/mcp-core-contract.md`.

Tools used by the deploy flow:

| Tool | Purpose |
|------|---------|
| `create_preview_app` | Create the preview app; input `{}`; returns `app_id`, `git_url`, `git_credentials` (~5-min token) |
| `get_preview_app_git_credentials` | Mint fresh git credentials for an existing `app_id` (credential lapsed mid-deploy) |
| `set_config_vars` | Set secrets (`{ app_id, vars }`); returns masked values; the user is prompted to confirm |
| `create_addon` | Provision an addon (postgres, redis); input `{ app_id, service }` |
| `get_addon_status` | Poll addon until `ready: true`; input `{ app_id, addon_id }` |
| `get_deployment_status` | Build status; returns `claim_link`, claim-portal `web_url`, `expires_at` (epoch ms) |
| `get_build_output` | Build log, read when `build.failed` is true |
| `share_in_browser` | Fresh single-use preview link after the build succeeds |
| `check_claim_status` | Poll until the app is claimed or expired |
| `get_preview_app_details` | Claim URL and state for an existing app (used by `claim-app`) |
| `discard_preview_app` | Mark an unclaimed preview app discarded (`discard-preview-app` skill) |

Responses may carry a `monitoring` block (`owner: card | assistant`). Skills follow it instead of hardcoding poll intervals; see the contract.

The portal does not expose app deletion (`destroy_app` is filtered out of its allowlist), so there is no MCP path to delete a claimed app. `teardown` is paused until the portal team exposes it.

**Status:** The tool contract above was verified from `mcp-portal` and `mcp-core` 7.0.0 source on 2026-10-30. The new flow has not yet been run live against staging; the `discard-website` and `saas-*` scenarios in `evals/scenarios/` are the manual live check.

For local testing without the live server: set `HEROKU_MCP_STUB=1` — stubs in `mcp/stubs/` conform to the mcp-portal tool result spec.

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
- `effective_addons()` is the single source of truth — feeds `.heroku-plugin-scaffold.json` and the JSON summary

### Shared Helpers (`scripts/heroku_glue/common.py`)

- `write_file(path, content)` — UTF-8 + LF + trailing newline
- `write_json(path, data)` — sorted keys + 2-space indent
- `merge_gitignore(target_dir, lines)` — append-only, never clobbers
- `build_project_toml(buildpack_id)` — deterministic project.toml (no builder — Kodon selects it)
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
- No `.env` or secrets committed; Secrets are set through `set_config_vars`

### Supported Stacks + Addons (v1)

Stacks: `node`, `python` (fastapi/django/flask), `rails`, `go`, `website` (static HTML/CSS/JS)
Addons: `heroku-postgresql`, `heroku-redis` (Kafka: unsupported in v1)
Addons during anonymous deploy: available (provisioned with app)
Addons post-claim: billable to user's account

### plugin.json Policy

```json
"policy": {
  "reference_staleness_days": 30,
  "supported_stacks": ["node", "python", "rails", "go", "website"],
  "supported_addons": ["heroku-postgresql", "heroku-redis"],
  "unsupported_addons": ["kafka"]
}
```

The mcp-portal connection is configured in the user's Claude Code, not in this repo.

### Eval Strategy

- Generator evals: Layer 2 byte-identity, no LLM, CI on every push, output to `evals/.tmp/`
- Container evals: Docker boot tests (eval Dockerfiles, not CNBs), CI on PR + main
- Skill evals: trigger discrimination + E2E in stub mode, run manually or via `workflow_dispatch`
