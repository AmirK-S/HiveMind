# Changelog

All notable changes to this repository are recorded here. The format follows
Keep a Changelog. Dates are ISO 8601.

## Unreleased

### Added
- First test suite: startup contract (configuration prefix, migrations on an
  empty database, /health, MCP endpoint path), one contract file per MCP tool
  through the HTTP transport with a bearer token, and the 2026-07-28 protocol
  revision contract. CI on GitHub Actions with a pgvector service.
- `docker/entrypoint.sh`: Alembic migrations run before uvicorn.
- Migration 007: `casbin_rule`, the RBAC policy table the server reads at startup.
- `.env.example`, `LICENSE` (MIT), this changelog.
- `conformance/`: reports of the official MCP conformance suite before and
  after the upgrade, and the `expected-failures` files that justify every
  remaining failure. 2026-07-28: 5 of 37 scored scenarios before, 13 after,
  zero wire schema violation on every run.

### Changed
- README rewritten: what the server does and does not do, quick start on a
  fresh clone, the seven tools, conformance before and after, end of life note.
- Upgrade to fastmcp 4.0.3 and the mcp 2.1.1 SDK: MCP revision 2026-07-28 is
  served without sessions, handshake revisions stay served on the same URL.
  `get_http_headers()` call sites ask for the Authorization header explicitly;
  the DNS rebinding guard is armed through `HIVEMIND_ALLOWED_HOSTS`.
- MCP endpoint served at exactly `/mcp`. It used to answer on `/mcp/mcp` while
  `/mcp` returned 307 then 404.
- Tool refusals are MCP errors (`isError: true`) instead of `CallToolResult`
  objects serialised as ordinary values.
- Server card advertises the transport path and bearer authentication.
- Distribution name is `hivemind-mcp`; `hivemind` on PyPI belongs to another project.

### Fixed
- `docker-compose.yml` passed `DATABASE_URL` and `REDIS_URL` without the
  `HIVEMIND_` prefix; the container connected to itself.
- `alembic/env.py` imported a name that does not exist; no migration had ever
  applied. Migrations 001 and 004 failed on an empty database.
- `rbac.py` stripped the async driver from the URL of an async adapter, and
  awaited the synchronous `enforce()`; `manage_roles` had never completed.
- Health checks called `curl`, absent from the runtime image.

### Removed
- `npx/`: the launcher installed a third party's package of the same name and
  sent `X-API-Key` where the tools read `Authorization: Bearer`.
- `SITREP.md` and `glama.json`: internal planning and directory listing files.
