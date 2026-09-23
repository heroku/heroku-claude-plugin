#!/usr/bin/env bash
# Build a canary distribution zip from the current branch HEAD.
# Usage: ./scripts/build_canary_zip.sh [output_path]
#
# Example:
#   ./scripts/build_canary_zip.sh ~/Desktop/heroku-plugin-canary-v0.1.4.zip
#
# Testers add the MCP connector manually via Claude Desktop Settings > Connectors
# or: claude mcp add --transport http heroku-canary <url>

set -euo pipefail

VERSION=$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])")
OUTPUT="${1:-$HOME/Desktop/heroku-plugin-canary-v${VERSION}.zip}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# 1. Extract all tracked files
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$TMPDIR"

# 2. Remove files that must not be distributed
rm -rf "$TMPDIR/mcp"
rm -f  "$TMPDIR/.mcp.json"

# 3. Zip from inside the clean directory
rm -f "$OUTPUT"
(cd "$TMPDIR" && zip -r "$OUTPUT" . -x "*.pyc" -x "__pycache__/*" -q)

echo "Built: $OUTPUT"
echo ""
echo "Contents check (mcp-related):"
unzip -l "$OUTPUT" | grep -i mcp || echo "  (none — good)"
