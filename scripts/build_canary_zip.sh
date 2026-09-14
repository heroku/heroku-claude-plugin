#!/usr/bin/env bash
# Build a canary distribution zip from the current branch HEAD.
# Usage: ./scripts/build_canary_zip.sh <mcp_url> <herokai_secret> [output_path]
#
# Example:
#   ./scripts/build_canary_zip.sh \
#     https://mcp-portal-canary-e80b708566b2.herokuapp.com \
#     GjunECLVqvMUCeAHljxL07DWdCsl6hcH \
#     ~/Desktop/heroku-plugin-canary-v0.1.3.zip

set -euo pipefail

MCP_URL="${1:?Usage: $0 <mcp_url> <herokai_secret> [output_path]}"
HEROKAI_SECRET="${2:?Usage: $0 <mcp_url> <herokai_secret> [output_path]}"
VERSION=$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])")
OUTPUT="${3:-$HOME/Desktop/heroku-plugin-canary-v${VERSION}.zip}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# 1. Extract all tracked files
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$TMPDIR"

# 2. Remove files that must not be distributed
rm -rf "$TMPDIR/mcp"
rm -f  "$TMPDIR/.mcp.json"

# 3. Write the hardcoded canary .mcp.json
cat > "$TMPDIR/.mcp.json" << EOF
{
  "mcpServers": {
    "mcp-portal": {
      "type": "http",
      "url": "${MCP_URL}/mcp?herokai=${HEROKAI_SECRET}"
    }
  }
}
EOF

# 4. Zip from inside the clean directory
rm -f "$OUTPUT"
(cd "$TMPDIR" && zip -r "$OUTPUT" . -x "*.pyc" -x "__pycache__/*" -q)

echo "Built: $OUTPUT"
echo ""
echo "Contents check (mcp-related):"
unzip -l "$OUTPUT" | grep -i mcp || echo "  (none — good)"
