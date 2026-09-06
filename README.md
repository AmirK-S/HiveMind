# HiveMind

Shared memory for AI agents, served over the Model Context Protocol. One agent
contributes what it learned, another one finds it. The server speaks MCP
revision 2026-07-28 (no sessions, `server/discover`) and the earlier handshake
revisions on the same URL, through fastmcp 4.0.3.

This is a dated demonstration, not a product. It has no hosted instance, no
users and no daily maintenance. The [end of life](#end-of-life) section says
what will break next. Everything stated here can be checked from the repository
alone.

## What it does

- Seven MCP tools over Streamable HTTP at `/mcp`: contribute, search, list,
  delete, publish, report an outcome, manage roles.
- Server-minted handles: `add_knowledge` returns a `contribution_id` that the
  client passes back as an ordinary tool argument. No protocol session is
  needed, which is what the 2026-07-28 revision made mandatory.
- Before storage: prompt injection scan (DeBERTa), personal data removal
  (Presidio with GLiNER), three-stage deduplication (MinHash, cosine, LLM),
  quality scoring, conflict resolution.
- Isolation by organisation and by agent, carried in the bearer token, never in
  tool arguments. RBAC with Casbin.
- A REST API under `/api/v1`, with the same organisation isolation, keyed by `X-API-Key`.

## What it does not do

- It does not run anywhere. You run it.
- It does not ship a hosted knowledge commons; the "public" flag only shares an
  item between organisations of the same instance.
- The third deduplication stage and conflict resolution call an LLM and are not
  reachable from the MCP tools: the MinHash index they depend on is never
  populated by the write path. They are kept as code, documented as unwired.
- `docker-compose.yml` starts the server, PostgreSQL and Redis. It starts no
  Celery worker, so webhooks and quality signal aggregation never run in the
  shipped stack.
- The startup downloads the embedding model from Hugging Face on first run. A
  machine without network access does not start.
- The PII pass still redacts a few product names as if they were people or
  places: `Prometheus` and `Grafana` are the two measured cases (spaCy
  recognizer). Known, documented, not corrected in this release.
- A2A facade: not planned in this release.

## Quick start

Requirements: Docker with Compose. Ports 8000, 5432 and 6379 free.

```bash
git clone https://github.com/AmirK-S/HiveMind.git
cd HiveMind
cp .env.example .env
docker compose up -d --build
curl -s localhost:8000/health
```

The first start takes one to three minutes: migrations run, then three models
load. `docker compose logs -f hivemind` shows the progress. Measured on a fresh
clone on 2026-09-06: build 5 min 33 s, first `/health` 200 after 182 s, zero
container restart (`conformance/` holds the session reports).

Mint a bearer token for an organisation and an agent. There is no CLI command
for it; the signing key is `HIVEMIND_SECRET_KEY` from your `.env`:

```bash
docker compose exec hivemind python -c \
  "from hivemind.server.auth import create_token; print(create_token('org-a', 'agent-1'))"
```

Connect an MCP client that speaks Streamable HTTP. The generic shape, to adapt
to your client's configuration file:

```json
{
  "mcpServers": {
    "hivemind": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Clients that only speak stdio can go through `mcp-remote` with a `--header`
argument. There is no `npx` launcher in this repository, and the server is not
published on PyPI: it needs PostgreSQL with pgvector and Redis, so it is
distributed as this repository and its Docker image. The distribution name in
`pyproject.toml` is `hivemind-mcp`; `hivemind` on PyPI is an unrelated project.

Talk to the server by hand, on the 2026-07-28 wire:

```bash
curl -s -X POST localhost:8000/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' -H 'Mcp-Method: server/discover' \
  -d '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'
```

## Demo

`scripts/demo.sh` replays the whole story against a running compose stack:
`server/discover` on the 2026-07-28 wire, two agents of one organisation, alice
contributes, bob finds the item by meaning and then by handle, rates it, each
agent lists only its own contributions, and a call without a token is refused.
`scripts/demo-transcript.txt` is its output on a fresh clone on 2026-09-06.

```bash
cp .env.example .env && docker compose up -d --build && ./scripts/demo.sh
```

## The seven tools

| Tool | What it does | Refuses when |
| --- | --- | --- |
| `add_knowledge` | Contributes a text with a category; returns `contribution_id` and `status` (`queued`, or `auto_approved` if a rule exists for the organisation) | content shorter than 10 characters, unknown category, injection detected, too much redacted |
| `search_knowledge` | Fetches by `id`, or searches by `query` (BM25 plus vectors) | neither `id` nor `query`, unknown or foreign private item |
| `list_knowledge` | Lists the caller's own contributions, pending and approved | unknown status filter |
| `delete_knowledge` | Soft-deletes an item of the caller's organisation and agent | item of another agent or organisation, unknown id |
| `publish_knowledge` | Makes an item visible to other organisations, or hides it again | item of another organisation, unknown id |
| `report_outcome` | Records `solved` or `did_not_help` for an item, once per `run_id` | unknown item, unknown outcome |
| `manage_roles` | Reads or assigns Casbin roles and permissions | caller is not an admin of the organisation |

Every refusal is an MCP error (`isError: true`) with a one-line message. Every
tool reads `Authorization: Bearer <jwt>`; the JWT carries `org_id` and
`agent_id`. The REST API under `/api/v1` uses `X-API-Key` instead.

The RBAC policy table starts empty. Nobody is an admin until a policy and a
role link exist in `casbin_rule` for the organisation; `tests/test_tool_manage_roles.py`
shows the two rows to insert.

## Protocol revision and conformance

The official suite, `@modelcontextprotocol/conformance`, was run before and
after the upgrade from fastmcp 2.14.5 to 4.0.3. Reports, logs and the
`expected-failures` files are in [`conformance/`](conformance/README.md).

| Requirements | Before (2.14.5) | After (4.0.3) |
| --- | --- | --- |
| `2025-11-25`, scored scenarios passed | 8 of 30 | 10 of 30 |
| `2026-07-28`, scored scenarios passed | 5 of 37 | 13 of 37 |
| `2026-07-28`, checks passed / failed | 55 / 102 | 111 / 56 |
| Wire schema violations | 0 | 0 |

Most of the suite drives reference tools with imposed names (`test_simple_text`,
`test_input_required_result_*`) or capabilities this server does not expose
(resources, prompts, completion, the tasks extension). The scenarios that judge
the protocol of a tools-only server (`server-stateless`, `tools-list`,
`server-sse-multiple-streams`, `dns-rebinding-protection`, `caching`) pass
after the upgrade, except two checks of `server-stateless` that need a
reference tool. Each remaining failure is listed with its reason in
`conformance/expected-failures-2026-07-28.yaml`, and the tool exits 0 with it.

Almost none of the upgrade happened in this repository's code. The revision is
absorbed by the framework. Two things had to change: `get_http_headers()` drops
the `Authorization` header by default in fastmcp 4.x, so the eight call sites
ask for it explicitly; and the DNS rebinding guard is off by default, so the
server arms it with `HIVEMIND_ALLOWED_HOSTS`.

## Tests

```bash
uv sync --extra dev
docker run -d --name hivemind-test-pg -e POSTGRES_USER=hm -e POSTGRES_PASSWORD=hm \
  -e POSTGRES_DB=postgres -p 55432:5432 pgvector/pgvector:pg16
HIVEMIND_TEST_ADMIN_URL=postgresql://hm:hm@localhost:55432/postgres uv run pytest -q
```

59 tests. The three models are replaced by doubles, so no test downloads
anything or calls an LLM. One file per MCP tool, each going through
`POST /mcp` with a bearer token against a database migrated to head, with the
nominal path and at least three refusals. Without `HIVEMIND_TEST_ADMIN_URL`
the tests that need PostgreSQL skip. CI runs the same suite on every push
(`.github/workflows/ci.yml`).

Les tests marques `models` sont exclus de la suite par defaut et de CI, car ils
chargent le vrai pipeline PII, donc GLiNER (environ 400 Mo dans
`~/.cache/huggingface`) et le modele spacy du groupe `models` ; ils se lancent a
part :

```bash
uv run pytest -m models
```

What is not tested: the REST API, the CLI, the pipelines beyond the doubles
(except the PII contract), Celery tasks. The tests cover the contract of the seven tools and
the protocol surface, not the rest of the code.

## Configuration

All variables carry the `HIVEMIND_` prefix and have a default in
`hivemind/config.py`; `.env.example` lists the useful ones.

| Variable | Default | Role |
| --- | --- | --- |
| `HIVEMIND_SECRET_KEY` | `dev-secret-change-me` | HS256 key of the bearer tokens. Change it. |
| `HIVEMIND_DATABASE_URL` | local PostgreSQL | set by the compose file to its own service |
| `HIVEMIND_REDIS_URL` | local Redis | idem |
| `HIVEMIND_ALLOWED_HOSTS` | `localhost,127.0.0.1` | hostnames accepted in `Host`; others get 421 |
| `HIVEMIND_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | must not change for the life of a database |
| `HIVEMIND_ANTHROPIC_API_KEY` | empty | LLM stages; empty means skipped |

## Repository layout

- `hivemind/`: the server. `server/main.py` builds the app (`create_app()`),
  `server/tools/` holds the seven tools, `pipeline/` the PII, injection and
  embedding stages, `security/` RBAC and rate limiting, `api/` the REST routes.
- `alembic/`: seven migrations. `docker/entrypoint.sh` applies them before uvicorn.
- `tests/`: the suite described above.
- `conformance/`: MCP conformance reports before and after the upgrade.
- `wrappers/`: `hivemind-langchain` and `hivemind-crewai`, thin clients of the
  REST API, published on PyPI in February 2026.
- `scripts/`: the demo, its transcript, and an OpenAPI export of the REST API.

Removed in September 2026, still in the git history: a Next.js dashboard, two
generated SDKs that had drifted from the API, a FalkorDB driver nothing
imported, and a skill file with a wrong category list.

## End of life

This repository serves MCP revision `2026-07-28` with `fastmcp>=4.0.3,<5` and
the `mcp` 2.1.1 SDK, pinned in `uv.lock`. It is not maintained on a daily basis.

What will break next: the next protocol revision will do to the session-less
era what `2026-07-28` did to sessions, and the conformance suite will have to
be run again with new `--requirements`. The tests in `tests/` are the safety
net for that day: they exercise the wire, not the framework's internals. The
official TypeScript SDK did not speak `2026-07-28` as of 2026-09-05 (1.30.0
tops out at `2025-11-25`), so editor clients will keep using the handshake
era for a while; the server serves both.

## Issues

Issues are read and answered within seven days. No feature is promised: this
is a dated demonstration. A reproducible defect in what the README claims gets
fixed; a request for a new capability gets a written answer and stays open or
is closed as out of scope.

## License

MIT, see `LICENSE`.
