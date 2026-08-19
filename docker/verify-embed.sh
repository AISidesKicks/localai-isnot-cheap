#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000}"

# Master key precedence: exported env var, then docker/.env LITELLM_MASTER_KEY,
# finally the demo default.
if [ -z "${LITELLM_MASTER_KEY:-}" ] && [ -f "$ENV_FILE" ]; then
  LITELLM_MASTER_KEY="$(grep '^LITELLM_MASTER_KEY=' "$ENV_FILE" | head -n1 | cut -d= -f2-)"
fi
if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
  LITELLM_MASTER_KEY="sk-1234-master-key-4321"
  echo "WARNING: LITELLM_MASTER_KEY not found in $ENV_FILE, falling back to the demo default" >&2
fi

AUTH_HEADER="Authorization: Bearer $LITELLM_MASTER_KEY"
INPUT='what is the answer to life?'

# Feed a JSON body through python3 and assert the returned embedding is dim 768.
assert_dim () {
  python3 -c 'import json,sys; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) else d["data"][0]; dim=len(d["embedding"]); print(f"  dim={dim}", file=sys.stderr); sys.exit(0 if dim==768 else 1)' >/dev/null
}

check_engine () {
  local payload
  payload="$(INPUT="$INPUT" python3 -c 'import json,os; print(json.dumps({"model":"nomic-embed-text-v1.5","input":os.environ["INPUT"]}))')"
  echo "Checking cheap-llamaembed directly on port 8081 ..."
  if curl -sf -H "Content-Type: application/json" -d "$payload" "http://localhost:8081/v1/embeddings" | assert_dim; then
    echo "  OK (dim 768)"
  else
    echo "  FAILED (expected dim 768)" >&2
    exit 1
  fi
}

check_alias () {
  local payload
  payload="$(INPUT="$INPUT" python3 -c 'import json,os; print(json.dumps({"model":"nomic-embed-llama","input":os.environ["INPUT"]}))')"
  echo "Checking LiteLLM alias 'nomic-embed-llama' ..."
  if curl -sf -H "$AUTH_HEADER" -H "Content-Type: application/json" -d "$payload" "$BASE_URL/v1/embeddings" | assert_dim; then
    echo "  OK (dim 768)"
  else
    echo "  FAILED (expected dim 768)" >&2
    exit 1
  fi
}

check_engine
check_alias

echo "Embedding endpoint verified (dim 768)."
