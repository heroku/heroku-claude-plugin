#!/usr/bin/env bash
# PreCompact hook — serializes session state before context compaction.
# Writes .heroku-plugin-session.json to CWD so long-running scenarios survive compaction.

set -euo pipefail

SESSION_FILE="${PWD}/.heroku-plugin-session.json"

# Only checkpoint if a session is in progress (session file already exists or env vars set)
if [ ! -f "$SESSION_FILE" ] && [ -z "${HEROKU_APP_NAME:-}" ] && [ -z "${HEROKU_APP_ID:-}" ]; then
  echo '{}'
  exit 0
fi

# Delegate to the session helper. The session file lives in the working directory and may
# come from an untrusted repo, so it is only ever parsed as JSON data by the helper.
# -I isolates the interpreter from PYTHON* env vars and the cwd.
exec python3 -I "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/scripts/session.py" checkpoint --dir "$PWD"
