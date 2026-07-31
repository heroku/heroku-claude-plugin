---
name: preflight
description: >-
  Run Heroku plugin preflight checks. Verifies that git is installed (required)
  and optionally installs Docker for local development. Also checks whether local
  Heroku reference docs are up to date. Use before building or deploying any app,
  or when the user asks about prerequisites, setup, or environment checks.
argument-hint: "[--quick]"
allowed-tools: Bash, Read
---

# Preflight Checks

You are running the Heroku plugin preflight checker. Follow these steps in order.

## Step 1 — Run preflight.py

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py --json
```

Capture the JSON output. Parse it to determine:
- `git`: true/false
- `docker`: true/false
- `docker_skipped`: true/false
- `references_updated`: array of updated files

## Step 2 — Handle git missing (hard stop)

If `git` is false, surface this message and stop:

```
✗ git is required to deploy to Heroku.

Install git:
  macOS:   brew install git
  Linux:   apt-get install git
  Windows: winget install Git.Git

Re-run preflight once git is installed.
```

Do not proceed with any scaffold or deploy workflow.

## Step 3 — Handle Docker prompt

If `docker` is false and `docker_skipped` is false, the preflight script already
prompted the user interactively. If running in a non-interactive context (e.g.
called from another skill), surface this message:

```
⚠ Docker not found.

Docker enables a local development environment without installing language
runtimes on your machine. It also runs local Postgres and Redis that mirror
your Heroku addons exactly.

To install: run /heroku-plugin:preflight and respond to the prompt.

Proceeding without Docker — local run and test will be unavailable.
```

## Step 4 — Report results

Surface a clean summary:

```
Heroku plugin preflight:

  ✓ git (<version>)
  ✓ docker              (or: ⚠ docker — skipped, local dev unavailable)
  ✓ references current  (or: ↻ references updated: <files>)

Ready to build.  (or: git missing — cannot proceed.)
```

## Step 5 — Return status

Return a structured result so calling skills can gate on it:
```json
{
  "ready": true,
  "git": true,
  "docker": true
}
```
