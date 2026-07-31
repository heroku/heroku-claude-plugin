#!/usr/bin/env bash
# PreCompact hook — serializes session state before context compaction.
# Writes .heroku-plugin-session.json to CWD so long-running scenarios survive compaction.

set -euo pipefail

SESSION_FILE="${PWD}/.heroku-plugin-session.json"

# Only checkpoint if a session is in progress (session file already exists or env vars set)
if [ ! -f "$SESSION_FILE" ] && [ -z "${HEROKU_APP_NAME:-}" ]; then
  echo '{}'
  exit 0
fi

# Build session state from env vars + existing file
EXISTING='{}'
if [ -f "$SESSION_FILE" ]; then
  EXISTING=$(cat "$SESSION_FILE")
fi

python3 - <<EOF
import json, os, datetime

existing = json.loads('''$EXISTING''')

state = {
    "app_name":    os.environ.get("HEROKU_APP_NAME",    existing.get("app_name", "")),
    "session_id":  os.environ.get("HEROKU_SESSION_ID",  existing.get("session_id", "")),
    "claim_url":   os.environ.get("HEROKU_CLAIM_URL",   existing.get("claim_url", "")),
    "timer_start": os.environ.get("HEROKU_TIMER_START", existing.get("timer_start", "")),
    "access_codes": existing.get("access_codes", []),
    "stack":       os.environ.get("HEROKU_STACK",       existing.get("stack", "")),
    "target_dir":  os.environ.get("HEROKU_TARGET_DIR",  existing.get("target_dir", "")),
    "checkpointed_at": datetime.datetime.utcnow().isoformat() + "Z",
}

with open("${SESSION_FILE}", "w") as f:
    json.dump(state, f, indent=2)
    f.write("\n")

print(json.dumps({"systemMessage": f"Heroku session state checkpointed to {os.path.basename('${SESSION_FILE}')}"}))
EOF

exit 0
