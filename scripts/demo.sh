#!/usr/bin/env bash
# HiveMind demo: two agents, one shared memory, MCP revision 2026-07-28.
#
# Replayable from the repository alone:
#   cp .env.example .env && docker compose up -d --build && ./scripts/demo.sh
#
# What it shows, in order:
#   1. server/discover answers without a handshake or a session
#   2. alice contributes a piece of knowledge and receives a server-minted handle
#   3. bob, another agent of the same organisation, finds it by meaning, then by handle
#   4. bob reports that the knowledge solved his problem
#   5. each agent only lists what it contributed itself
#
# Needs: bash, curl, python3, docker compose (for the token and the approval rule).
set -euo pipefail

URL="${HIVEMIND_URL:-http://localhost:8000}"
ORG="demo-org"
VERSION="2026-07-28"
META='"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}'

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }

# JSON-RPC POST on the 2026-07-28 wire. $1 method, $2 params JSON, $3 token or empty, $4 tool name or empty.
mcp() {
  local method="$1" params="$2" token="${3:-}" name="${4:-}"
  local -a headers=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream'
                    -H "MCP-Protocol-Version: $VERSION" -H "Mcp-Method: $method")
  [ -n "$name" ]  && headers+=(-H "Mcp-Name: $name")
  [ -n "$token" ] && headers+=(-H "Authorization: Bearer $token")
  curl -s -X POST "$URL/mcp" "${headers[@]}" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$method\",\"params\":{${params:+$params,}$META}}"
}

# Call a tool and print the payload. $1 tool, $2 arguments JSON, $3 token.
call() {
  local tool="$1" args="$2" token="$3"
  mcp tools/call "\"name\":\"$tool\",\"arguments\":$args" "$token" "$tool" | python3 -c '
import json, sys
r = json.load(sys.stdin)
if "error" in r:
    print("JSON-RPC error:", r["error"]); sys.exit(1)
res = r["result"]
if res.get("isError"):
    print("refused:", res["content"][0]["text"]); sys.exit(0)
payload = res.get("structuredContent") or json.loads(res["content"][0]["text"])
if isinstance(payload, dict) and list(payload) == ["result"]:
    payload = payload["result"]
print(json.dumps(payload, indent=2))
'
}

field() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

say "0. Waiting for $URL/health"
for _ in $(seq 1 60); do
  curl -sf "$URL/health" >/dev/null 2>&1 && break
  sleep 3
done
curl -sf "$URL/health" >/dev/null || { echo "server not reachable at $URL"; exit 1; }
note "up"

say "1. server/discover on the $VERSION wire (no initialize, no session)"
DISCOVER="$(mcp server/discover '')"
note "supportedVersions: $(printf '%s' "$DISCOVER" | field '["result"]["supportedVersions"]')"
note "serverInfo:        $(printf '%s' "$DISCOVER" | field '["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]')"
note "tools:             $(mcp tools/list '' | python3 -c 'import json,sys; r=json.load(sys.stdin)["result"]; print(len(r["tools"]), "tools, ttlMs", r["ttlMs"], "cacheScope", r["cacheScope"])')"

say "2. Two agents of organisation $ORG get a bearer token each (signed with HIVEMIND_SECRET_KEY)"
mint() { docker compose exec -T hivemind python -c "from hivemind.server.auth import create_token; print(create_token('$ORG', '$1'))" | tr -d '\r'; }
ALICE="$(mint alice)"; BOB="$(mint bob)"
note "alice: ${ALICE:0:24}...   bob: ${BOB:0:24}..."

say "   An auto-approval rule for $ORG, so alice's contribution lands in the commons at once"
note "(without it the contribution is queued for human review; there is no MCP tool to approve)"
docker compose exec -T postgres psql -q -U hivemind -d hivemind -c \
  "INSERT INTO auto_approve_rules (id, org_id, category, is_auto_approve, created_at, updated_at)
   SELECT gen_random_uuid(), '$ORG', 'general', true, now(), now()
   WHERE NOT EXISTS (SELECT 1 FROM auto_approve_rules WHERE org_id = '$ORG' AND category = 'general');" >/dev/null

say "3. alice contributes"
CONTENT="With asyncpg behind SQLAlchemy 2, a pool_size above the PostgreSQL max_connections divided by the number of workers gives 'too many clients already' under load; size the pool per worker, not per service."
ADDED="$(call add_knowledge "{\"content\":\"$CONTENT\",\"category\":\"general\",\"confidence\":0.9,\"tags\":[\"asyncpg\",\"sqlalchemy\"]}" "$ALICE")"
printf '%s\n' "$ADDED" | sed 's/^/   /'
HANDLE="$(printf '%s' "$ADDED" | field '["contribution_id"]')"

say "4. bob searches by meaning, with other words than alice used"
call search_knowledge '{"query":"postgres connection pool too many clients with several uvicorn workers","limit":3}' "$BOB" | sed 's/^/   /'

say "5. bob fetches the item by the handle alice received (the server-minted identifier, passed as an ordinary argument)"
call search_knowledge "{\"id\":\"$HANDLE\"}" "$BOB" | sed 's/^/   /'

say "6. bob reports that it solved his problem"
call report_outcome "{\"item_id\":\"$HANDLE\",\"outcome\":\"solved\",\"run_id\":\"demo-run-1\"}" "$BOB" | sed 's/^/   /'

say "7. Each agent lists only its own contributions"
note "alice:"; call list_knowledge '{}' "$ALICE" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("     total_count:", d["total_count"])'
note "bob:";   call list_knowledge '{}' "$BOB"   | python3 -c 'import json,sys; d=json.load(sys.stdin); print("     total_count:", d["total_count"])'

say "8. Without a token, the same call is refused as an MCP error"
call list_knowledge '{}' "" | sed 's/^/   /'

say "Done. The item alice contributed is now shared memory: bob found it, used it, rated it."
