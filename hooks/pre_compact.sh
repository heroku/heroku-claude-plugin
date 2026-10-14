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

# Build session state from env vars + existing file. The session file lives in the
# working directory and may come from an untrusted repo, so it is only ever parsed as
# JSON data — never interpolated into shell or Python source.
export SESSION_FILE

python3 -I - <<'PY'
import datetime
import json
import os
import tempfile

path = os.environ["SESSION_FILE"]

existing = {}
try:
    with open(path) as f:
        loaded = json.load(f)
    if isinstance(loaded, dict):
        existing = loaded
except (OSError, ValueError):
    pass


def text(env_name, key):
    value = os.environ.get(env_name)
    if value is not None:
        return value
    value = existing.get(key, "")
    return value if isinstance(value, str) else ""


codes = existing.get("access_codes", [])

state = {
    "app_name":    text("HEROKU_APP_NAME", "app_name"),
    "session_id":  text("HEROKU_SESSION_ID", "session_id"),
    "claim_url":   text("HEROKU_CLAIM_URL", "claim_url"),
    "timer_start": text("HEROKU_TIMER_START", "timer_start"),
    "access_codes": [c for c in codes if isinstance(c, str)] if isinstance(codes, list) else [],
    "stack":       text("HEROKU_STACK", "stack"),
    "target_dir":  text("HEROKU_TARGET_DIR", "target_dir"),
    "token_budget_tracking": os.environ.get("HEROKU_TOKEN_BUDGET_TRACKING", "").strip() == "1",
    "checkpointed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
}

# Write atomically so a crash mid-write can't leave a truncated session file
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".heroku-plugin-session.", suffix=".tmp")
try:
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
except BaseException:
    os.unlink(tmp)
    raise

print(json.dumps({"systemMessage": f"Heroku session state checkpointed to {os.path.basename(path)}"}))
PY

exit 0
