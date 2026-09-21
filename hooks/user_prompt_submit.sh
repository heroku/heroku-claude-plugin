#!/usr/bin/env bash
# UserPromptSubmit hook — detects build/deploy intent and runs a quick preflight check.
# Fast path only: checks git + docker presence, skips reference staleness.
# Must complete in < 5 seconds.

set -euo pipefail

PAYLOAD=$(cat)
PROMPT=$(printf '%s' "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user_prompt',''))" 2>/dev/null || true)

# Keyword detection — match build/deploy intent
if ! printf '%s' "$PROMPT" | grep -qiE '(build|scaffold|deploy|create app|heroku|new app)'; then
  echo '{}'
  exit 0
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

# Quick preflight: git + docker existence only
MISSING=()

if ! command -v git &>/dev/null; then
  MISSING+=("git")
fi

if ! command -v docker &>/dev/null; then
  MISSING+=("docker (optional — enables local dev environment)")
fi

DISPATCH_RULE="IMPORTANT: You must use the Skill tool to handle this request. Invoke heroku-plugin:build-and-deploy for a full build and deploy, or heroku-plugin:scaffold-app / heroku-plugin:deploy-anonymous individually. Do NOT write app files manually, do NOT call heroku create or git push heroku directly, and do NOT call heroku buildpacks:add. Delegate everything through the skill."

if [ ${#MISSING[@]} -eq 0 ]; then
  printf '{"systemMessage": "%s"}\n' "$DISPATCH_RULE"
  exit 0
fi

MSG="Heroku plugin preflight:"
for item in "${MISSING[@]}"; do
  MSG="$MSG $item not found."
done

printf '{"systemMessage": "%s — %s"}\n' "$MSG" "$DISPATCH_RULE"
exit 0
