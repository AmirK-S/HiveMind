# Requirements: HiveMind

**Defined:** 2026-02-18
**Core Value:** Agents stop learning alone — when one agent solves a problem, every connected agent benefits.
**Updated:** 2026-02-18 after deep PDF research ingestion (10 PDFs)
**Updated:** 2026-02-18 — moved legal/compliance to v2, simplified trust to product-focused
**Updated:** 2026-02-18 — roadmap v2: 4-phase structure, Phase 1 lightened for speed

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### MCP Server

- [x] **MCP-01**: Agent can connect to HiveMind via MCP protocol (Streamable HTTP transport per MCP spec 2025-11-25)
- [x] **MCP-02**: Agent can contribute knowledge via `add_knowledge` tool — knowledge is explicitly contributed, not silently extracted from conversations
- [x] **MCP-03**: Agent can search the commons via `search_knowledge` tool with tiered response (summary tier: title+category+confidence ~30-50 tokens; full tier: complete content on request) to minimize token cost at scale
- [x] **MCP-04**: Agent can list their contributed knowledge via `list_knowledge` tool
- [x] **MCP-05**: Agent can delete their own contributed knowledge via `delete_knowledge` tool — deletion cascades to derived distillations and summaries
- [ ] **MCP-06**: Agent can report outcome after retrieving knowledge ("solved my problem" / "did not help") as an explicit active confirmation signal for quality scoring

### API & SDKs

- [x] **SDK-01**: Developer can interact with HiveMind via REST API (CRUD operations, API key auth with usage metering per billing period)
- [ ] **SDK-02**: Developer can integrate via Python SDK
- [ ] **SDK-03**: Developer can integrate via TypeScript SDK

### Trust & Privacy

- [x] **TRUST-01**: All inbound knowledge is PII-stripped before storage using: Presidio as orchestrator + GLiNER (`knowledgator/gliner-pii-base-v1.0`) for zero-shot coverage + API secret patterns (AWS, GitHub, Google, Stripe, Slack, JWT, RSA keys) + private URL detection
- [x] **TRUST-02**: User receives notification when agent proposes sharing knowledge — notification surfaces quality pre-screening signals and similar existing knowledge
- [x] **TRUST-03**: User can approve or reject each knowledge contribution before it enters the commons
- [x] **TRUST-04**: User can configure auto-approve rules per knowledge category
- [x] **TRUST-05**: PII stripping runs two-pass validation: Pass 1 re-runs analyzer on anonymized text for residual leaks; Pass 2 checks output against original PII values verbatim
- [x] **TRUST-06**: Pipeline is markdown-aware — extracts and protects fenced/inline code blocks before anonymization, processes only narrative text, then reinjects code blocks intact

### Security

- [x] **SEC-01**: Contributed knowledge scanned for prompt injection and malicious instructions before entering commons — knowledge items injected into agent context windows are a potential attack vector (ClawHavoc precedent: 824 malicious skills in agent ecosystem)
- [x] **SEC-02**: Content hash (SHA-256) on every knowledge item for integrity verification — knowledge items cannot be mutated in transit without detection
- [x] **SEC-03**: Rate limiting on contributions per agent + coordinated contribution campaign detection (anti-sybil) to prevent knowledge poisoning attacks

### Access Control

- [x] **ACL-01**: Each organization has a private namespace isolated from other organizations
- [x] **ACL-02**: User can explicitly publish knowledge from private namespace to public commons — publication is reversible
- [x] **ACL-03**: Agent roles enforced at three levels: namespace (org), category (knowledge type), and individual item
- [x] **ACL-04**: Organization admin can manage agents and roles within their namespace
- [x] **ACL-05**: Cross-namespace search supported — queries can span both private and public commons with deduplication of results appearing in both

### Knowledge Management

- [x] **KM-01**: Every knowledge item has immutable provenance: source_agent_id, contributed_at, category, org_id, confidence_score, run_id (session), content_hash (SHA-256)
- [ ] **KM-02**: Retrieval latency split into two tiers: pure retrieval (vector+BM25+RRF, no LLM) target <200ms P95; full pipeline (with LLM reranking) target <1.5s P95
- [ ] **KM-03**: Near-duplicate detection compares against top-10 most similar existing items using three-stage dedup: cosine similarity → LSH/MinHash → LLM confirmation above configurable threshold (default 0.95)
- [x] **KM-04**: Knowledge items typed by category: bug_fix, config, domain_expertise, workaround, pricing_data, regulatory_rule, tooling, reasoning_trace, failed_approach, version_workaround, general — with framework/library version metadata on applicable items
- [x] **KM-05**: Bi-temporal tracking with two independent timelines: world-time (valid_at, invalid_at — when fact was true) and system-time (created_at, expired_at — when ingested). Invalidation marks facts as expired rather than deleting, enabling point-in-time queries.
- [ ] **KM-06**: Temporal queries supported ("what was known about X at time T") including version-scoped queries ("what was known about library X version Y")
- [ ] **KM-07**: LLM-assisted conflict resolution with four outcomes: UPDATE, ADD, NOOP, VERSION_FORK — where VERSION_FORK preserves both old and new knowledge as valid but version-scoped. Explicitly limited to single-hop direct conflicts; multi-hop conflicts flagged for human review.
- [x] **KM-08**: Embedding model pinned at deployment initialization and documented; re-embedding migration procedure documented for model changes. Abstraction layer decouples stored data from embedding model version.

### Quality & Intelligence

- [x] **QI-01**: Each knowledge item has a quality score (0-1) derived from behavioral signals
- [x] **QI-02**: Quality signals include: retrieval frequency, explicit agent outcome reporting ("solved" / "did not help" per MCP-06), contradiction rate, staleness, version freshness. Retrieval frequency and usefulness exposed as separate user-visible metrics on dashboard.
- [ ] **QI-03**: Search results ranked by quality score combined with relevance
- [ ] **QI-04**: Sleep-time distillation runs as background job — triggered by volume threshold or conflict count. Distillation re-runs PII pipeline on generated summaries and maintains provenance links for erasure propagation.
- [ ] **QI-05**: Distillation merges duplicates, flags contradictions, generates summaries. Quality pre-screening runs before human approval queue — users review a filtered shortlist, not raw agent output.

### Web Dashboard

- [ ] **DASH-01**: User can view two feeds: private namespace feed (org's agent contributions) and public commons feed (shared pool) — public commons feed is the featured/prominent view demonstrating network effect
- [ ] **DASH-02**: User can search the knowledge commons from the dashboard
- [ ] **DASH-03**: User can view per-user and per-org contribution AND retrieval statistics — including how many times their contributed knowledge was retrieved by other agents (reciprocity ledger)
- [ ] **DASH-04**: User can view knowledge item detail with full provenance
- [ ] **DASH-05**: User can approve/reject pending knowledge contributions from the dashboard
- [ ] **DASH-06**: Public commons health metrics visible: total items, growth rate, retrieval volume, domains covered — demonstrating network effect to attract contributors

### Distribution & Onboarding

- [ ] **DIST-01**: npx one-liner install for the MCP server (zero-friction first connection)
- [ ] **DIST-02**: Docker image published and maintained on Docker Hub
- [ ] **DIST-03**: Install configs for all major MCP clients in README: Claude Desktop, Cursor, VS Code, ChatGPT Desktop, Windsurf, Gemini CLI
- [ ] **DIST-04**: Smithery.ai listing for one-click hosted install
- [ ] **DIST-05**: OpenClaw skill wrapper (SKILL.md format) so OpenClaw agents can use HiveMind natively
- [ ] **DIST-06**: Submit to MCP discovery directories: PulseMCP, Glama.ai, mcp.so, AwesomeClaude.ai, official MCP Registry, punkpeye/awesome-mcp-servers
- [ ] **DIST-07**: LangChain tool wrapper (`HiveMindRetriever`) published to PyPI
- [ ] **DIST-08**: CrewAI tool wrapper (`HiveMindTool`) compatible with CrewAI tool interface
- [ ] **DIST-09**: 30-second demo GIF in README showing two agents sharing knowledge via MCP in Claude Desktop or Cursor

### Infrastructure

- [x] **INFRA-01**: PostgreSQL + pgvector as primary persistent store (sufficient for v1; abstraction allows Qdrant migration beyond ~50M items at 4.5K QPS with native multitenancy)
- [x] **INFRA-02**: Knowledge store abstraction following Graphiti's `GraphDriver` pattern — first graph backend target: Graphiti-on-FalkorDB (sub-10ms queries, Redis-based, native multitenancy)
- [x] **INFRA-03**: Near-real-time knowledge availability (seconds, not milliseconds) via webhook push after quality gate
- [x] **INFRA-04**: API key authentication with associated tier, request counter, and billing period reset — prerequisite for monetization
- [x] **INFRA-05**: Concurrent multi-agent writes handled safely — event sourcing or CRDT approach for shared knowledge to prevent race conditions

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Legal & Compliance

- **LEGAL-01**: Architecture designed around explicitly contributed data — agents surface knowledge created by users with intent to share, not extracted from prior conversational context
- **LEGAL-02**: DPIA (Data Protection Impact Assessment) documented before launch per GDPR art. 35(3)(b)
- **LEGAL-03**: Granular consent mechanism covers separately: (a) extraction, (b) anonymization processing, (c) sharing in commons. Consent revocable.
- **LEGAL-04**: Right to erasure propagation — when user revokes consent, deletion cascades from source knowledge items through all derived distillations, summaries, and quality aggregations
- **LEGAL-05**: AI Act transparency — all knowledge items disclosed as AI-assisted content per art. 50
- **LEGAL-06**: Reliability disclaimers displayed on all shared knowledge
- **LEGAL-07**: Product liability documentation and verification processes maintained for EU directive compliance
- **LEGAL-08**: EU data residency — data stored in EU region (required for French enterprise procurement, GDPR compliance) *(was INFRA-06)*

### Monetization & Billing

- **MON-01**: Free tier (Discover): €0, 100 requests/month, no credit card required
- **MON-02**: Paid tiers: Starter €29/month (2,000 req), Pro €79/month (10,000 req + 3 verticals), Business €149/month (50,000 req + API)
- **MON-03**: Usage metering per API key per billing period with soft and hard limit enforcement
- **MON-04**: Overage billing: €0.005-0.02/additional request
- **MON-05**: Annual billing option (2 months free, ~17% discount)
- **MON-06**: SEPA payment default, prices displayed HT (standard French B2B)
- **MON-07**: Billing portal: view plan, usage, upgrade/downgrade, download invoices

### B2B Knowledge Packs

- **PACK-01**: Pack registry with versioning and metadata
- **PACK-02**: First curated vertical pack (real estate — €50-200/month, mature willingness-to-pay)
- **PACK-03**: Waze flywheel — agents using packs contribute back
- **PACK-04**: Pack access via MCP tools
- **PACK-05**: SaaS billing for pack subscriptions
- **PACK-06**: Creator marketplace with operator agreements

### Crypto Trading Layer

- **CRYPTO-01**: Agent wallets for knowledge transactions
- **CRYPTO-02**: x402 micropayments for knowledge access (chain-agnostic, Coinbase standard)
- **CRYPTO-03**: Dynamic pricing based on knowledge quality and rarity
- **CRYPTO-04**: Knowledge trading marketplace
- **CRYPTO-05**: All crypto abstracted from user — payments in euros, automatic conversion

### Additional

- **MISC-01**: Cross-namespace knowledge federation
- **MISC-02**: A2A integration — expose HiveMind knowledge retrieval as A2A-callable capability
- **MISC-03**: AGNTCY directory listing for agent discoverability
- **MISC-04**: LlamaIndex query engine integration
- **MISC-05**: Knowledge interchange format standard (canonical serialization for export/interop)
- **MISC-06**: Public knowledge URLs — each public commons item gets a shareable, indexable URL
- **MISC-07**: Contribution leaderboard (public, opt-in) — top contributors by retrieval count

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile app | Web-first platform |
| Model training / fine-tuning | HiveMind is retrieval-augmented, not training infrastructure |
| Building AI agents | HiveMind is infrastructure agents connect to |
| Fully autonomous sharing (no approval) | Noisy commons risk is existential + prompt injection vector via contributed knowledge (ClawHavoc precedent) |
| Real-time streaming to agents | Near-real-time sufficient; true streaming adds complexity without quality gating |
| General-purpose data marketplace | Horizontal marketplaces generate negligible revenue |
| Visible crypto in UI | Abstract all blockchain; users see euros, not tokens |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCP-01 | Phase 1 | Complete |
| MCP-02 | Phase 1 | Complete |
| MCP-03 | Phase 1 | Complete |
| MCP-04 | Phase 1 | Complete |
| MCP-05 | Phase 1 | Complete |
| MCP-06 | Phase 3 | Pending |
| SDK-01 | Phase 3 | Complete |
| SDK-02 | Phase 3 | Pending |
| SDK-03 | Phase 3 | Pending |
| TRUST-01 | Phase 1 | Complete |
| TRUST-02 | Phase 1 | Complete |
| TRUST-03 | Phase 1 | Complete |
| TRUST-04 | Phase 2 | Complete |
| TRUST-05 | Phase 2 | Complete |
| TRUST-06 | Phase 2 | Complete |
| SEC-01 | Phase 2 | Complete |
| SEC-02 | Phase 2 | Complete |
| SEC-03 | Phase 2 | Complete |
| ACL-01 | Phase 1 | Complete |
| ACL-02 | Phase 2 | Complete |
| ACL-03 | Phase 2 | Complete |
| ACL-04 | Phase 2 | Complete |
| ACL-05 | Phase 2 | Complete |
| KM-01 | Phase 1 | Complete |
| KM-02 | Phase 3 | Pending |
| KM-03 | Phase 3 | Pending |
| KM-04 | Phase 1 | Complete |
| KM-05 | Phase 3 | Complete |
| KM-06 | Phase 3 | Pending |
| KM-07 | Phase 3 | Pending |
| KM-08 | Phase 1 | Complete |
| QI-01 | Phase 3 | Complete |
| QI-02 | Phase 3 | Complete |
| QI-03 | Phase 3 | Pending |
| QI-04 | Phase 3 | Pending |
| QI-05 | Phase 3 | Pending |
| DASH-01 | Phase 4 | Pending |
| DASH-02 | Phase 4 | Pending |
| DASH-03 | Phase 4 | Pending |
| DASH-04 | Phase 4 | Pending |
| DASH-05 | Phase 4 | Pending |
| DASH-06 | Phase 4 | Pending |
| DIST-01 | Phase 4 | Pending |
| DIST-02 | Phase 4 | Pending |
| DIST-03 | Phase 4 | Pending |
| DIST-04 | Phase 4 | Pending |
| DIST-05 | Phase 4 | Pending |
| DIST-06 | Phase 4 | Pending |
| DIST-07 | Phase 4 | Pending |
| DIST-08 | Phase 4 | Pending |
| DIST-09 | Phase 4 | Pending |
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 2 | Complete |
| INFRA-03 | Phase 2 | Complete |
| INFRA-04 | Phase 2 | Complete |
| INFRA-05 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 56 total
- Mapped to phases: 56
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 — roadmap v2: 4-phase structure, Phase 1 lightened for speed*
