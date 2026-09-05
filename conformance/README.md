# MCP conformance reports

Reports produced by the official suite, `@modelcontextprotocol/conformance`,
against this server. Each directory is one run; the `.log` next to it is the
console output, and every scenario folder holds the `checks.json` the tool wrote.

The suite is a reference-server validator: most scenarios require tools,
prompts and resources with imposed names (`test_simple_text`,
`test_input_required_result_elicitation`, ...) or capabilities this server does
not expose. For a business server that only exposes tools, the scenarios that
judge the protocol itself are `server-stateless`, `tools-list`,
`server-sse-multiple-streams`, `dns-rebinding-protection`, the `tools/list`
check of `caching`, and the synthetic `wire-schema-valid` check applied to
every message sent.

## baseline-fastmcp-2.14.5 (2026-09-05)

Server as of commit `844e5eb`, fastmcp 2.14.5, mcp 1.26.0. Tool version
`0.2.0-alpha.11`, the only line that carries `--requirements`.

| Requirements | Scored | Passed | Failed | Not scored | Skipped | Wire schema |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2025-11-25` | 30 | 8 | 22 | 3 | 0 | 143 messages, 0 violation |
| `2026-07-28` | 36 | 5 | 31 | 13 | 1 | 45 checks, 0 violation |

Protocol scenarios on this baseline:

- `tools-list`: passes on `2025-11-25` (seven tools, valid names); fails on
  `2026-07-28` only because the server rejects the protocol version.
- `server-sse-multiple-streams`: passes with a warning on `2025-11-25`; fails on
  `2026-07-28` (three HTTP 400).
- `server-stateless` and `caching`: not part of `2025-11-25`; fail on
  `2026-07-28`. No `ttlMs` or `cacheScope` is emitted yet.
- `dns-rebinding-protection`: fails on both. The server answers 200 to
  `Host: evil.example.com`. This is the one defect that does not come from the
  protocol revision.

The dominant failure on `2026-07-28` is a single message:
`Unsupported protocol version: 2026-07-28. Supported versions: 2024-11-05,
2025-03-26, 2025-06-18, 2025-11-25`. The number measures the gap to the new
revision, not the quality of the server. During both runs the server logged
zero HTTP 500 and zero traceback.
