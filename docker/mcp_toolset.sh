#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000}"
TOOLSET_NAME="${MCP_TOOLSET_NAME:-monitoring}"

# Admin key precedence: exported env var, then docker/.env LITELLM_ADMIN_KEY
# (a dedicated proxy_admin user, litellmadm), finally the demo master key.
# The raw master key only resolves as proxy_admin after the config-key fix in
# litellm_config.yaml; the scoped admin key is preferred for toolset work.
if [ -z "${LITELLM_ADMIN_KEY:-}" ] && [ -f "$ENV_FILE" ]; then
  LITELLM_ADMIN_KEY="$(grep '^LITELLM_ADMIN_KEY=' "$ENV_FILE" | head -n1 | cut -d= -f2-)"
fi
if [ -z "${LITELLM_ADMIN_KEY:-}" ]; then
  LITELLM_ADMIN_KEY="${LITELLM_MASTER_KEY:-sk-1234-master-key-4321}"
  echo "WARNING: LITELLM_ADMIN_KEY not found in $ENV_FILE, falling back to the master key / demo default" >&2
fi

AUTH_HEADER="Authorization: Bearer $LITELLM_ADMIN_KEY"

# Curated tool subset per server (same order as the toolset table in docker/README.md)
read -r -d '' TOOLSET_TOOLS <<'EOF' || true
{
  "phoenix": ["search", "list_tools"],
  "victoriametrics": ["query", "query_range", "metrics", "alerts"],
  "litellm_admin": ["list_spend_logs", "list_keys", "check_health", "get_global_spend_report"]
}
EOF

# Exit cleanly if the toolset already exists (no silent overwrite)
EXISTING="$(curl -sf -H "$AUTH_HEADER" "$BASE_URL/v1/mcp/toolset" || echo '[]')"
TOOLSET_ID="$(printf '%s' "$EXISTING" | TOOLSET_NAME="$TOOLSET_NAME" python3 -c '
import json, os, sys
toolsets = json.load(sys.stdin)
name = os.environ["TOOLSET_NAME"]
match = next((t for t in toolsets if t.get("toolset_name") == name), None)
print(match.get("toolset_id", "") if match else "")
')"
if [ -n "$TOOLSET_ID" ]; then
  echo "Toolset '$TOOLSET_NAME' already exists (id $TOOLSET_ID), skipping creation"
  echo "Full info:"
  curl -sf -H "$AUTH_HEADER" "$BASE_URL/v1/mcp/toolset/$TOOLSET_ID" | python3 -m json.tool
  exit 0
fi

# Resolve each server_name to its DB-stored server_id (UUIDs change per DB)
SERVERS="$(curl -sf -H "$AUTH_HEADER" "$BASE_URL/v1/mcp/server")"
TOOLS="$(printf '%s' "$SERVERS" | TOOLSET_TOOLS="$TOOLSET_TOOLS" python3 -c '
import json, os, sys
servers = json.load(sys.stdin)
by_name = {s["server_name"]: s["server_id"] for s in servers}
tools_by_server = json.loads(os.environ["TOOLSET_TOOLS"])
tools = []
for server, names in tools_by_server.items():
    if server not in by_name:
        print(f"ERROR: mcp server {server!r} not found in /v1/mcp/server", file=sys.stderr)
        sys.exit(1)
    for name in names:
        tools.append({"server_id": by_name[server], "tool_name": name})
print(json.dumps(tools))
')"

PAYLOAD="$(TOOLSET_NAME="$TOOLSET_NAME" TOOLS="$TOOLS" python3 -c '
import json, os
payload = {
    "toolset_name": os.environ["TOOLSET_NAME"],
    "description": "Curated monitoring subset across phoenix, victoriametrics and litellm_admin",
    "tools": json.loads(os.environ["TOOLS"]),
}
print(json.dumps(payload))
')"

echo "Creating toolset '$TOOLSET_NAME' on $BASE_URL ..."
curl -sf -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" -d "$PAYLOAD" "$BASE_URL/v1/mcp/toolset" >/dev/null

echo "Toolset created. Verifying ..."
curl -sf -H "$AUTH_HEADER" "$BASE_URL/v1/mcp/toolset" | python3 -m json.tool

TOOLSET_ID="$(curl -sf -H "$AUTH_HEADER" "$BASE_URL/v1/mcp/toolset" | TOOLSET_NAME="$TOOLSET_NAME" python3 -c '
import json, os, sys
toolsets = json.load(sys.stdin)
name = os.environ["TOOLSET_NAME"]
match = next(t for t in toolsets if t.get("toolset_name") == name)
print(match["toolset_id"])
')"
echo "Toolset '$TOOLSET_NAME' id: $TOOLSET_ID"
curl -sf -H "$AUTH_HEADER" "$BASE_URL/v1/mcp/toolset/$TOOLSET_ID" | python3 -m json.tool
