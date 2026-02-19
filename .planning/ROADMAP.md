# Roadmap: HiveMind

## Overview

HiveMind ships in four phases optimized for speed-to-first-agent-connection. Phase 1 is deliberately light: get agents connecting, contributing, and retrieving knowledge through a working MCP server with basic PII stripping and user approval. Phase 2 hardens trust and security so the commons can open broadly without risk of poisoning or data leakage. Phase 3 makes the commons intelligent with quality scoring, advanced retrieval, conflict resolution, and developer SDKs. Phase 4 delivers the human interface (web dashboard) and all distribution channels that make HiveMind discoverable and installable everywhere.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Agent Connection Loop** - Working MCP server with core tools, PII stripping, user approval gate, org namespaces, and knowledge schema — the minimum to get agents connecting and contributing
- [x] **Phase 2: Trust & Security Hardening** - Advanced PII pipeline, prompt injection scanning, rate limiting, role-based access control, cross-namespace search, and API key auth — making the commons safe to open broadly (completed 2026-02-19)
- [x] **Phase 3: Quality Intelligence & SDKs** - Quality scoring from behavioral signals, bi-temporal tracking, conflict resolution, near-duplicate detection, sleep-time distillation, and REST/Python/TypeScript SDKs (completed 2026-02-19)
- [ ] **Phase 4: Dashboard & Distribution** - Web dashboard for humans to observe and manage the commons, plus all distribution channels (npx, Docker, Smithery, MCP directories, framework wrappers)

## Phase Details

### Phase 1: Agent Connection Loop
**Goal**: An agent can connect to HiveMind via MCP, contribute PII-stripped knowledge through a user approval gate, search and retrieve from the shared commons, and operate within an isolated org namespace — the core contribute/retrieve loop works end-to-end
**Depends on**: Nothing (first phase)
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, TRUST-01, TRUST-02, TRUST-03, ACL-01, KM-01, KM-04, KM-08, INFRA-01, INFRA-05
**Success Criteria** (what must be TRUE):
  1. An agent connects via MCP (Streamable HTTP) and calls `add_knowledge` — the contribution enters a quarantine queue, not the commons, until the user approves it
  2. A user receives a notification when their agent proposes a contribution, sees PII already stripped, and approves or rejects it — approved knowledge enters the commons
  3. An agent calling `search_knowledge` receives ranked results with tiered response (summary tier first, full content on request) from the commons
  4. An agent can list their own contributions via `list_knowledge` and delete them via `delete_knowledge` with cascade to derived artifacts
  5. Two organizations' agents operate in completely isolated namespaces — neither sees the other's contributions
**Plans:** 5/5 plans complete

Plans:
- [x] 01-01-PLAN.md — Project scaffolding, config, DB models (PendingContribution, KnowledgeItem, DeploymentConfig), Alembic migrations with pgvector
- [x] 01-02-PLAN.md — PII stripping pipeline (Presidio + GLiNER + API key patterns) and embedding provider abstraction
- [x] 01-03-PLAN.md — MCP server (Streamable HTTP) + auth + add_knowledge tool + search_knowledge tool with tiered response
- [x] 01-04-PLAN.md — list_knowledge + delete_knowledge tools + CLI approval workflow (Typer + Rich + questionary)
- [x] 01-05-PLAN.md — TRUST-02 gap closure: similar knowledge cosine lookup + QI pre-screening badge in review panel

### Phase 2: Trust & Security Hardening
**Goal**: The commons is protected against prompt injection, knowledge poisoning, PII leakage edge cases, and unauthorized access — safe enough to open to external agents at scale with API key authentication and granular role-based access control
**Depends on**: Phase 1
**Requirements**: TRUST-04, TRUST-05, TRUST-06, SEC-01, SEC-02, SEC-03, ACL-02, ACL-03, ACL-04, ACL-05, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. A user can configure auto-approve rules per knowledge category — trusted categories flow into the commons without manual review
  2. Knowledge containing prompt injection or malicious instructions is detected and blocked before entering the commons
  3. A content hash (SHA-256) is attached to every knowledge item and verified on retrieval — tampering is detectable
  4. An organization admin can manage agents and roles, with access enforced at namespace, category, and item levels
  5. An agent can search across both private namespace and public commons in a single query, with results deduplicated
**Plans:** 6/6 plans complete

Plans:
- [ ] 02-01-PLAN.md — Pipeline hardening: prompt injection scanner (SEC-01), two-pass PII validation (TRUST-05), markdown-aware code block preservation (TRUST-06), content integrity helpers (SEC-02)
- [ ] 02-02-PLAN.md — DB schema + config: ApiKey, AutoApproveRule, WebhookEndpoint models + Alembic migrations 003-005 + new settings
- [ ] 02-03-PLAN.md — Security infrastructure: Casbin RBAC with domain-aware model (ACL-03/04), rate limiting + anti-sybil (SEC-03), API key management (INFRA-04)
- [ ] 02-04-PLAN.md — Graph + webhook infrastructure: KnowledgeStoreDriver abstraction (INFRA-02), Celery webhook delivery (INFRA-03)
- [ ] 02-05-PLAN.md — Tool integration: wire injection scanner + auto-approve + hash verification + cross-namespace dedup into MCP tools
- [ ] 02-06-PLAN.md — Server + CLI integration: extended lifespan, publish_knowledge tool (ACL-02), manage_roles tool (ACL-04), webhook dispatch in approval flow

### Phase 3: Quality Intelligence & SDKs
**Goal**: The commons becomes self-improving — quality scores surface the best knowledge, behavioral signals feed back into rankings, temporal tracking handles knowledge evolution, and developers can integrate via REST API and Python/TypeScript SDKs without MCP
**Depends on**: Phase 2
**Requirements**: MCP-06, SDK-01, SDK-02, SDK-03, KM-02, KM-03, KM-05, KM-06, KM-07, QI-01, QI-02, QI-03, QI-04, QI-05
**Success Criteria** (what must be TRUE):
  1. An agent reports an outcome ("solved" / "did not help") after retrieving knowledge, and that signal visibly changes the item's quality score over time
  2. Search results are ranked by combined quality + relevance — the top result is measurably more useful than a random result from the same query
  3. Near-duplicate knowledge contributed by different agents is detected (three-stage dedup) and consolidated rather than duplicated
  4. A developer can query the commons via REST API with an API key, or via Python/TypeScript SDK, and get results equivalent to MCP search
  5. Temporal queries work — "what was known about X at time T" returns point-in-time accurate results
**Plans:** 7/7 plans complete

Plans:
- [ ] 03-01-PLAN.md — Schema migration (quality + temporal columns, quality_signals table) + quality scorer + config settings
- [ ] 03-02-PLAN.md — REST API layer with API key auth, metering middleware, knowledge + outcomes endpoints
- [ ] 03-03-PLAN.md — report_outcome MCP tool + REST wiring + bi-temporal query helpers + temporal search filter
- [ ] 03-04-PLAN.md — Three-stage dedup pipeline (cosine + MinHash + LLM) + conflict resolution (UPDATE/ADD/NOOP/VERSION_FORK) + add_knowledge integration
- [ ] 03-05-PLAN.md — Hybrid BM25+vector search with RRF + quality-boosted ranking + Celery signal aggregation task
- [ ] 03-06-PLAN.md — Sleep-time distillation (duplicate merging, contradiction flagging, summary generation, PII re-scan, quality pre-screening)
- [ ] 03-07-PLAN.md — Python + TypeScript SDK generation from OpenAPI spec + Makefile target + CI drift check

### Phase 4: Dashboard & Distribution
**Goal**: A human can open the web dashboard and see the commons growing live, manage approvals and contributions, view analytics — and any developer can discover HiveMind through standard channels and install it in under 5 minutes
**Depends on**: Phase 3
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DIST-01, DIST-02, DIST-03, DIST-04, DIST-05, DIST-06, DIST-07, DIST-08, DIST-09
**Success Criteria** (what must be TRUE):
  1. A user opens the dashboard and sees both their private namespace feed and the public commons feed updating in real time — the public commons is the prominent view demonstrating network effect
  2. A user can approve or reject pending knowledge contributions from the dashboard, view item detail with full provenance, and see per-user/per-org contribution and retrieval statistics (reciprocity ledger)
  3. A developer runs a single `npx` command, edits one config file, and makes a successful `search_knowledge` call from Claude Desktop or Cursor — all within 5 minutes
  4. HiveMind is listed in at least 4 MCP discovery directories and has framework wrappers (LangChain, CrewAI, OpenClaw) published to their respective registries
  5. A 30-second demo GIF in the README shows two agents sharing knowledge via MCP in a real client
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Agent Connection Loop | 3/4 | Complete    | 2026-02-18 |
| 2. Trust & Security Hardening | 6/6 | Complete   | 2026-02-19 |
| 3. Quality Intelligence & SDKs | 6/7 | Complete    | 2026-02-19 |
| 4. Dashboard & Distribution | 0/TBD | Not started | - |
