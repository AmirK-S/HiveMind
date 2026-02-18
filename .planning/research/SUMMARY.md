# Project Research Summary

**Project:** HiveMind
**Domain:** Shared AI agent memory / collective knowledge commons platform (MCP server + web dashboard + B2B knowledge packs + crypto trading layer)
**Researched:** 2026-02-18
**Confidence:** HIGH (core memory/ingestion stack and pitfalls), MEDIUM (crypto trading layer)

## Executive Summary

HiveMind occupies a genuine white space: no existing product combines cross-organisational agent knowledge sharing, B2B vertical knowledge packs, and agent-to-agent knowledge trading in a single platform. The February 2026 research surveyed 50+ projects and found incumbents entirely siloed — private per-user memory systems (Mem0, Graphiti, Letta), skill marketplaces (GPT Store, PulseMCP), intra-org shared memory (AWS AgentCore, Microsoft Work IQ), and crypto knowledge infrastructure (OriginTrail, Shinkai) each occupy exactly one axis. HiveMind's core architecture must be built on Graphiti as the collective memory substrate (the only framework with native multi-agent shared graph semantics via `group_id` and bi-temporal conflict resolution), combined with a mandatory PII stripping pipeline (Presidio + GLiNER) and a trust-gated approval flow before any knowledge enters the commons.

The recommended approach is a phased build that treats trust infrastructure as foundational rather than a later addition. Phase 1 must deliver: a working MCP server, a PII stripping pipeline running locally (no external API calls), a user approval gate, namespace isolation per organisation, and a pre-seeded commons — all before any external agent connects. The "noisy commons" risk identified in academic literature (arXiv:2505.18279) is existential: a commons that accepts unvalidated knowledge from agents will degrade quickly and cannot be retroactively cleaned. The quality gate, provenance tracking, and origin-type metadata must be in the schema from the first database insert.

The two largest risks are legal, not technical. First, automated PII stripping does not constitute legal anonymisation under GDPR/EDPB standards — the business model must be built on knowledge that users voluntarily and explicitly contribute for public sharing, not on knowledge extracted from private agent sessions. Second, the crypto trading layer triggers securities regulation and money transmission licensing; it must be operated by a legally separate entity and must not launch until jurisdiction-specific legal opinions classify the tokens. The correct sequencing is: establish the free commons with critical mass (12-18 months), then layer B2B packs, then add crypto trading as an optional payment rail.

---

## Key Findings

### Recommended Stack

The memory engine decision is the most consequential architectural choice. Graphiti (`graphiti-core>=0.27.1`) is the correct backbone for the shared commons: it natively supports multiple agents writing to and reading from a shared `group_id`, bi-temporal conflict resolution is automatic and deterministic (no LLM call at retrieval time), and retrieval achieves sub-200ms p99 via BM25 + vector + graph traversal fused with RRF. Neither Mem0 (single-user assumption baked in) nor Letta (archival memory is per-agent, not shareable) can serve as the collective memory layer. FalkorDB is the recommended graph backend for MVP — Redis-native, no JVM, lighter operational footprint than Neo4j — with Neo4j as the scale-out path beyond ~10M edges.

The PII pipeline is safety-critical infrastructure. Presidio alone (`presidio-analyzer>=2.2.361`) is insufficient — Microsoft's own documentation warns results "aren't very accurate" at F1 ~0.60. GLiNER (`gliner>=0.2.24`, model: `knowledgator/gliner-pii-base-v1.0`) must be added as a fallback recognizer to handle domain-specific PII types (crypto wallet addresses, internal project codenames, French identifiers SIRET/SIREN/NIR) that Presidio's NER misses. The PII pipeline must run locally, in-process — sending raw agent sessions to any external API before stripping is a GDPR violation.

**Core technologies:**
- `graphiti-core>=0.27.1` + FalkorDB: collective memory backbone with native multi-agent graph semantics and bi-temporal conflict resolution
- `mcp>=1.25,<2` + `fastmcp>=2.0`: MCP server runtime; pin below v2 (breaking changes expected Q1 2026); FastMCP reduces boilerplate ~70%
- `presidio-analyzer/anonymizer>=2.2.361` + `gliner>=0.2.24` + spaCy `en_core_web_lg`: PII stripping pipeline; must run in-process with no external API calls
- `BAAI/bge-m3` (self-hosted) / `text-embedding-3-small` (managed): embedding models; pin at graph creation time — changing requires full re-embedding
- `fastapi>=0.129.0` + `uvicorn>=0.34` + `pydantic>=2.10`: async REST API for dashboard and integrations
- `celery[redis]>=5.4` + `redis>=5.2`: async task queue for ingestion pipeline (LLM calls per contribution are inherently slow — must be decoupled from agent response path)
- PostgreSQL 16+ + pgvector>=0.8: relational metadata, access control, audit trail, Phase 1 vector search
- Qdrant (`qdrant-client>=1.16.1`): pure vector search for high-frequency agent memory queries (add in Phase 2 when pgvector latency becomes limiting)
- Next.js 15 + TypeScript 5.7 + Drizzle ORM>=0.39 + shadcn/ui: web dashboard
- x402 protocol (Coinbase SDK) + Solana web3.js v2: agent-to-agent micropayments (Phase 4 only; Solana $0.00025/tx, 400ms finality covers 77% of x402 volume)

### Expected Features

The feature research found zero direct competitors. Table stakes are borrowed from adjacent markets users already know (private memory systems, data marketplaces, B2B SaaS tools), not from direct competitors.

**Must have (table stakes — MVP is non-functional without these):**
- MCP server with `add_knowledge`, `search_knowledge`, `get_knowledge`, `delete_knowledge` tool surface — agents cannot connect without it
- Automatic PII stripping pipeline — runs before any knowledge enters the commons; mandatory trust gate
- User approval / consent flow — GDPR/CCPA compliance; users review what their agent will contribute before it is committed
- Namespace isolation per organisation — no cross-org leakage without explicit publication; foundational multi-tenancy
- Knowledge provenance and attribution — `source_agent_id`, `contributed_at`, `category`, `org_id`, `origin_type` on every item; immutable
- Hybrid semantic search (vector + BM25 + RRF) — P95 <500ms; agents expect ranked relevant results, not keyword grep
- Conflict detection and deduplication — vector similarity threshold before write; prevents immediate commons pollution
- Web dashboard with live knowledge feed — makes the invisible commons observable and credible
- REST API + Python SDK — non-MCP integrations and developer evaluation
- Basic knowledge category taxonomy (6-8 types: bug_fix, config, domain_expertise, workaround, pricing_data, regulatory_rule)

**Should have (differentiators — add after validating core contribution/retrieval loop):**
- Cross-organisational knowledge commons ("Waze model") — the core white space; no competitor currently offers this
- Quality scoring from behavioural signals (retrieval frequency, outcome reporting) — feeds pack curation and crypto pricing
- Bi-temporal knowledge tracking (`valid_at`, `invalid_at`, `created_at`, `expired_at`) — required for live vertical packs where knowledge expires
- First vertical knowledge pack (real estate recommended: mature willingness-to-pay, structured data)
- Sleep-time distillation — background job that consolidates related knowledge and generates pack summaries
- Category-level consent controls — allow per-category auto-approve rules; triggered when blanket approval is too coarse
- Open-source core with hosted premium — maximises adoption (commons needs contributors) while creating monetisation path

**Defer (v2+ — requires established product-market fit and knowledge critical mass):**
- Crypto trading layer / agent-to-agent micropayments — defer 12-18 months minimum; hard dependency on quality scoring, established user base, and jurisdiction-specific legal opinions
- Vertical knowledge pack creator marketplace — premature creator marketplace = low-quality pack proliferation (GPT Store failure pattern)
- Agent wallets / dynamic pricing — defer with crypto layer
- Cross-namespace knowledge federation — complex access control surface, low demand at early stage

**Anti-features to explicitly avoid:**
- Fully autonomous knowledge sharing without approval gate — "noisy commons" failure mode
- LLM-generated quality scores — expensive, non-deterministic, gameable; use behavioural signals instead
- Visible crypto complexity in user-facing UI — B2B adoption blocker; abstract to euros
- Unlimited free tier — removes conversion pressure; use generous-but-bounded (100 queries/month, 50 contributions/month)

### Architecture Approach

The system has six major layers separated into a monorepo of packages: MCP Server Gateway (protocol entry point), Ingestion Pipeline (extract, PII strip, deduplicate, quality score, approval gate), Knowledge Store (tri-layer: vector, graph, relational), Distribution Engine (real-time push to subscribed agents), B2B Pack System (curated domain-specific subsets), and Web Dashboard. The MCP Gateway must be thin — tool handlers validate input, delegate to service packages, format response. All business logic lives in ingestion, knowledge-store, and distribution packages. Mixing domain logic into MCP handler code creates hard-to-test code that breaks with each MCP spec update.

The most architecturally critical decision is to start with pgvector-only storage in Phase 1, with the knowledge-store package designed from day one to add the graph layer (Neo4j/FalkorDB) in Phase 2 without rewriting callers. This avoids premature operational complexity while preserving the upgrade path. The approval gate must be on by default — knowledge quarantined until user approves, with configurable auto-approve thresholds that users expand as trust is established; not opt-in.

**Major components:**
1. MCP Server Gateway — protocol entry point; auth, rate limiting, session management; thin tool handlers only
2. Ingestion Pipeline — four sequential stages: LLM extraction, local PII strip, dedup, quality score; async via Celery; approval gate decouples ingestion throughput from user review latency
3. Knowledge Store — tri-layer abstraction: pgvector (Phase 1), add Qdrant + FalkorDB/Neo4j (Phase 2); unified interface so storage technology swaps don't rewrite callers
4. Distribution Engine — real-time push (SSE/WebSocket) to subscribed agents after approval; Redis pub/sub in Phase 2+; EventEmitter acceptable in Phase 1
5. B2B Pack System — curation and versioning layer over the commons; Waze flywheel (pack subscribers contribute back); SaaS billing before crypto
6. Web Dashboard — live contribution feed, approval workflow UI, search interface, provenance detail; Next.js 15 + WebSocket subscriptions

**Key patterns:**
- Bi-temporal knowledge graph: `valid_at`, `invalid_at`, `created_at`, `expired_at` on every edge; never delete, only invalidate; audit trail is always complete
- Hybrid retrieval with RRF: parallel vector (Qdrant) + graph traversal (FalkorDB/Neo4j) + BM25, fused via Reciprocal Rank Fusion; no LLM call at retrieval time
- Namespace-scoped access control: three tiers — `private:<org_id>`, `pack:<pack_id>`, `global`; agent queries carry namespace list; metadata join on every read
- Knowledge origin tagging: every item carries `origin_type` (human-validated, AI-generated, community-corroborated); required to detect model collapse

### Critical Pitfalls

1. **PII stripping treated as legal anonymisation** — Run vanilla Presidio and declare inputs "anonymised": EDPB Opinion 28/2024 and CNIL July 2025 confirm this is legally insufficient. Re-identification remains possible via model inversion attacks. Prevention: design contribution flows around knowledge users explicitly and voluntarily submit for public sharing (opt-in, not extracted from private sessions). Add GLiNER to Presidio, handle French identifiers, code block metadata, and git author fields. Complete a DPIA before ingesting real user data.

2. **No viable legal basis for commercialising private conversation content** — GDPR Article 6 provides no robust legal basis for extracting and selling knowledge from private agent sessions; ePrivacy Directive Article 5 prohibits it without consent; Italian Garante rejected contract performance as an AI training basis; CNIL fined Google EUR 325M in Sept 2025 for analogous behaviour. Prevention: this is a Phase 0 business model constraint, not an engineering fix. Knowledge must come from explicit user contribution, not session extraction.

3. **Cold start kills network effects before they form** — An empty commons is useless, so agents don't contribute, keeping it empty. Enterprise buyers will not tolerate an empty system. Prevention: pre-seed with curated content from public sources (Stack Overflow CC BY-SA, GitHub public repos, official docs) before external access opens. At least one vertical must have 1000+ curated items at launch. Vertical knowledge packs must exist at v0, not v2.

4. **Knowledge poisoning and model collapse** — A single malicious agent can inject subtly incorrect knowledge that fans out to thousands of agents before detection. Recursive AI-to-AI contribution without human signal causes model collapse (Shumailov et al., Nature 2024: "irreversible defects" at 1/1000 synthetic contamination). Prevention: no knowledge distributed without a confidence gate; origin-type field in schema from first insert; circular contribution detection (agent retrieves from commons, re-contributes the same knowledge); new agent rate limits and probationary tier.

5. **Crypto layer regulatory exposure** — x402 micropayments and knowledge tokens trigger MiCA (EU, from December 2024), securities regulation (US SEC), and money transmission licensing in every jurisdiction. An enforcement action against the crypto layer damages the core product. Prevention: legally separate entity for crypto operations from day one; no crypto feature launched without jurisdiction-specific token classification opinion; MiCA CASP registration before EU operation. Never in the same codebase/entity as the core platform.

---

## Implications for Roadmap

Based on combined research, the dependency chain from ARCHITECTURE.md defines the only viable build order. The approval gate and PII pipeline are load-bearing for the trust model — underbuilding them creates a failure mode that cannot be recovered from retroactively. The crypto layer has no value until the commons has critical mass.

### Phase 0: Legal and Content Foundation (Pre-Build)

**Rationale:** Three pitfalls require decisions before any code is written: legal basis for data processing (determines what data flows are even permissible), legal entity structure (crypto layer must be separated now or never), and knowledge IP strategy (affects fundraising narrative and monetisation design). These cannot be retrofitted.

**Delivers:** Legal opinion on data flows and token classification, DPIA for PII processing, separate legal entity for crypto layer, minimum viable commons threshold defined, pre-seeding content strategy for at least one target vertical, business model narrative that does not claim unenforceable knowledge IP.

**Avoids:** Pitfall 2 (no viable legal basis), Pitfall 6 (crypto regulatory exposure), Pitfall 8 (knowledge IP non-defensibility).

**Research flag:** Needs legal research, not technical research. This phase involves outside counsel, not engineering.

### Phase 1: Core Commons Infrastructure

**Rationale:** Everything else depends on this. The MCP gateway, PII pipeline, approval gate, knowledge store, and web dashboard must all be functional and trustworthy before any external agent contributes. The commons must be pre-seeded before access opens. The ingestion pipeline's approval gate must be on by default — architecture decisions made here (schema shape, namespace model, origin-type field, abstraction interfaces) cannot be changed after real data is in the system.

**Delivers:** Working MCP server with core tool surface (`add_knowledge`, `search_knowledge`, `list_knowledge`, `delete_knowledge`), local PII pipeline (Presidio + GLiNER, no external API calls), user approval flow with webhook/email notification, namespace isolation (private org + global commons), knowledge provenance schema (agent ID, timestamp, category, origin_type — immutable), pgvector-only knowledge store with abstraction interface for graph layer addition, conflict detection via similarity threshold, basic web dashboard (approval UI + live knowledge feed), REST API + Python SDK, pre-seeded content for target vertical, basic knowledge category taxonomy.

**Stack used:** `mcp>=1.25,<2` + `fastmcp`, `graphiti-core[falkordb]>=0.27.1` + FalkorDB, `presidio-analyzer/anonymizer>=2.2.361` + `gliner>=0.2.24` + spaCy, `fastapi>=0.129.0` + `uvicorn` + `pydantic>=2.10`, `celery[redis]>=5.4`, PostgreSQL 16 + pgvector, Next.js 15 + Drizzle ORM.

**Avoids:** Pitfall 1 (PII legal shield), Pitfall 3 (knowledge poisoning), Pitfall 4 (cold start), Pitfall 5 (MCP protocol instability — abstraction layer), Pitfall 7 (trust paradox — per-domain exclusions), Pitfall 9 (model collapse — origin-type in schema from first insert).

**Research flag:** MCP abstraction layer design (protocol is still evolving — needs research into current spec state and planned breaking changes). PII pipeline customisation for French-specific identifiers (SIRET, SIREN, NIR) needs dedicated research sprint.

### Phase 2: Quality and Graph Layer

**Rationale:** Once the contribution/retrieval loop has real users (target: first 100 active contributors or 10,000 knowledge items), the limitations of pgvector-only retrieval and heuristic quality scoring become the binding constraints. The graph layer enables multi-hop relational queries that pure vector search misses. Quality scoring from real behavioural signals (retrieval frequency, outcome reporting) becomes possible once the system has usage data from Phase 1.

**Delivers:** Graph store layer added to knowledge-store abstraction (FalkorDB for MVP, Neo4j path for scale), hybrid retrieval with RRF (vector + graph traversal + BM25, no LLM at retrieval time, target P95 <300ms), real-time push distribution (Redis pub/sub, SSE fan-out to subscribed agents), quality scoring from behavioural signals (retrieval frequency, agent outcome reporting), bi-temporal knowledge tracking (`valid_at`, `invalid_at`), category-level consent controls, LLM-assisted conflict resolution layer (on top of similarity threshold from Phase 1), TypeScript SDK.

**Stack added:** Qdrant (`qdrant-client>=1.16.1`) for pure vector path, `neo4j>=6.1` or FalkorDB cluster, Redis Streams for reliable distribution fan-out, `BAAI/bge-m3` or `text-embedding-3-small`.

**Implements:** Hybrid Vector + Graph Retrieval pattern, Bi-Temporal Knowledge Graph pattern, Real-Time Distribution Engine.

**Research flag:** Graph query performance benchmarks for FalkorDB vs Neo4j at target scale — needs dedicated research to confirm switching point. RRF tuning parameters (k constant) need empirical validation against real queries.

### Phase 3: B2B Vertical Knowledge Packs

**Rationale:** The first monetised layer. Requires namespace support (Phase 1) and quality scoring (Phase 2) before packs can be curated and sold — selling unscored, potentially PII-contaminated packs is a legal and reputational risk. Real estate is the recommended first vertical: mature willingness-to-pay (EUR 50-200/month per agent per research benchmarks), structured data, clear knowledge expiry (bi-temporal tracking from Phase 2 is now available). Sleep-time distillation generates pack summaries. SaaS billing (not crypto) at this stage.

**Delivers:** Pack registry with versioning and changelog, curator tools for building domain-specific knowledge subsets, Waze flywheel (pack subscribers contribute back to pack namespace), sleep-time distillation (background consolidation job, cron/event-triggered), first curated real estate pack, SaaS billing for pack subscriptions, pack marketplace UI in dashboard.

**Avoids:** Pitfall 4 (cold start — packs provide initial value even with sparse user contribution), anti-feature of premature creator marketplace (internal curation first, creator marketplace after quality is demonstrated).

**Research flag:** Real estate knowledge licensing — sourcing structured real estate data for initial pack seeding requires research into data provider agreements and licensing terms. Sleep-time distillation LLM prompt design needs a dedicated research spike.

### Phase 4: Crypto Trading Layer

**Rationale:** Only viable after the commons has established critical mass (12-18 months post-Phase 1 open access per pricing research), quality scoring is operational (required to price knowledge), and the separate legal entity is registered and compliant. The crypto layer enhances monetisation; it must not gate adoption. Build the SaaS pack business first, add crypto as an optional premium payment rail.

**Delivers:** Agent wallets (Privy for custodial, Crossmint for non-custodial), x402 micropayment integration (Coinbase CDP facilitator, Solana primary settlement at $0.00025/tx), dynamic pricing engine (quality score-weighted), knowledge trading marketplace, `trade_knowledge` MCP tool, stake-to-earn quality validation (Numerai model).

**Stack added:** x402 Coinbase SDK, `@solana/web3.js>=2`, Privy or Crossmint SDK.

**Critical dependency:** Legally separate crypto entity must be in place from Phase 0. MiCA CASP registration must be obtained before EU operation.

**Research flag:** High. x402 protocol is still evolving (35M+ transactions, $10M+ volume but launched recently). MiCA CASP registration process needs dedicated legal/regulatory research. Dynamic pricing model for knowledge units has no established benchmark — needs market research.

### Phase Ordering Rationale

- **Legal first:** Pitfalls 2 and 6 are business model constraints, not engineering problems. Addressing them in Phase 0 avoids building systems that must be dismantled later.
- **Trust infrastructure before contributors:** The approval gate and PII pipeline must be in place before any real agent data is accepted. A poisoned or legally non-compliant commons cannot be retroactively cleaned.
- **Commons before packs, packs before crypto:** Each layer depends on the previous. B2B packs require quality scoring (Phase 2). Crypto trading requires established knowledge volume and pack infrastructure (Phase 3). The Crypto layer with no knowledge to trade has no value.
- **Pre-seeding before open access:** Cold start is existential. The commons must demonstrate value in the first agent session. Seeding runs in Phase 1 before external access opens — not on demand after launch.
- **Graph layer as Phase 2 upgrade, not Phase 1 requirement:** pgvector is sufficient for Phase 1 retrieval. Deferring the graph layer reduces Phase 1 complexity while the knowledge-store abstraction interface preserves the upgrade path.

### Research Flags

**Needs `/gsd:research-phase` during planning:**
- **Phase 1:** MCP protocol abstraction layer — MCP spec has evolved rapidly (Tasks, MCP Apps, Streamable HTTP all added in 2025-11-25); protocol abstraction design needs research into current spec state and planned v2 breaking changes
- **Phase 1:** French-specific PII recognisers — SIRET, SIREN, NIR, French phone formats have zero native Presidio support; implementation approach needs a dedicated research spike
- **Phase 3:** Real estate knowledge data sourcing — licensing terms, provider agreements, and data quality for initial pack seeding require research
- **Phase 4:** MiCA CASP registration — regulatory process and timeline need jurisdiction-specific legal research
- **Phase 4:** x402 protocol maturity — protocol is young; needs research into current SDK stability, settlement reliability, and edge cases

**Standard patterns (skip research-phase):**
- **Phase 1:** FastAPI + Celery + Redis task queue architecture — well-documented, standard Python async infrastructure pattern
- **Phase 1:** Presidio + spaCy integration — official documentation is comprehensive; GLiNER integration path is documented
- **Phase 1:** Next.js 15 + Drizzle ORM dashboard — standard developer dashboard stack with mature documentation
- **Phase 2:** Qdrant Docker deployment — official documentation comprehensive; straightforward integration
- **Phase 2:** Redis pub/sub for distribution fan-out — standard pattern with well-understood scaling properties

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core memory layer (Graphiti, Presidio, FastAPI) sourced from three deep-research PDFs with live PyPI version verification as of Feb 2026. Crypto stack (x402, Solana web3.js) is MEDIUM — protocol is young and evolving. |
| Features | HIGH | Sourced from 50+ project market survey, three academic papers (arXiv:2505.18279, arXiv:2407.06485, TechRxiv 2025), and live market data. White space conclusion is well-supported. Pricing benchmarks from dedicated pricing strategy PDF. |
| Architecture | HIGH | Sourced from three deep technical PDFs covering Mem0, Graphiti, and Letta architectures, plus MCP spec 2025-11-25. Anti-pattern identification is grounded in documented failure modes. Build order dependency chain is internally consistent with feature research. |
| Pitfalls | HIGH | Legal pitfalls sourced from dedicated legal research PDF with specific regulatory actions (CNIL EUR 325M fine Sept 2025, EDPB Opinion 28/2024, Italian Garante vs. OpenAI). Technical pitfalls grounded in academic literature (Shumailov et al., Nature 2024; ICLR 2025 Spotlight). |

**Overall confidence:** HIGH for core platform decisions. MEDIUM for crypto trading layer (protocol maturity, regulatory path).

### Gaps to Address

- **Machine unlearning capability:** Research confirms it is legally required for GDPR consent revocation (Art. 17 right to erasure). No implementation approach is specified in the research. Needs a dedicated technical research spike before Phase 1 data model is finalised.
- **x402 protocol edge cases and reliability:** The protocol has $10M+ volume but is young. Failure modes (settlement failures, double-spend protection, dispute resolution) are not covered in the research. Needs Phase 4 research.
- **Multi-language PII beyond French:** The research covers French-specific identifiers explicitly but only mentions GLiNER as a zero-shot multilingual option. If B2B packs target non-French European markets, additional recogniser research is needed.
- **Graph query performance at 10M+ edges:** The FalkorDB-to-Neo4j switching point (~10M edges) is from Graphiti documentation. Empirical validation under HiveMind's specific query patterns (bi-temporal edge traversal + namespace filtering) is needed before committing to FalkorDB as the long-term graph backend.
- **Minimum viable commons threshold:** The pitfalls research identifies pre-seeding as critical but does not quantify the threshold for "useful enough." This needs to be defined as a testable metric (e.g. P50 retrieval precision on a benchmark query set) before Phase 1 development begins.

---

## Sources

### Primary (HIGH confidence)
- "AI Agent Memory Frameworks: A Deep Technical Comparison of Mem0, Graphiti, and Letta" (deep research PDF, 2025-2026) — memory architecture decisions, storage backends, retrieval latencies, shared memory primitives
- "Cartographie du Knowledge Sharing Inter-Agents IA — Février 2026" (deep research PDF) — 50+ project market survey, white space identification, MCP ecosystem state, crypto knowledge trading landscape
- "Stratégie de Pricing pour une Plateforme de Knowledge IA à Trois Couches — 2025" (deep research PDF) — pricing benchmarks, freemium conversion rates, vertical SaaS economics, crypto protocol revenue reality, sequencing recommendation
- "Risques juridiques majeurs d'une plateforme de revente de connaissances IA" (deep research PDF, 2025) — GDPR, ePrivacy, AI Act, copyright, trade secrets, provider ToS analysis
- "Anonymisation automatique des données LLM : état de l'art technique 2025" (deep research PDF) — Presidio architecture, NER benchmarks, PII edge cases
- "La grande extinction silencieuse du savoir technique collectif" and "L'effondrement de Stack Overflow" (deep research PDFs, 2025/2026) — commons failure modes, model collapse research, MCP ecosystem data
- arXiv:2505.18279 "Collaborative Memory" — private + shared selective memory architecture, noisy commons warning
- arXiv:2407.06485 "CrowdTransfer" — crowdsourced knowledge transfer, provenance requirements
- Shumailov et al., Nature 2024 — model collapse from recursive AI training
- ICLR 2025 Spotlight — 1/1000 synthetic data contamination threshold

### Secondary (MEDIUM confidence)
- graphiti-core PyPI (verified Feb 2026): https://pypi.org/project/graphiti-core/ — v0.27.1
- FastAPI PyPI (verified Feb 2026): https://pypi.org/project/fastapi/ — v0.129.0
- x402 protocol: https://www.x402.org/ — Coinbase CDP; 35M+ transactions, $10M+ volume since launch
- Solana x402: https://solana.com/x402/what-is-x402 — 77% of x402 volume, $0.00025/tx
- MCP Specification 2025-11-25 — Tasks, MCP Apps, Streamable HTTP transport, .well-known federation registry
- EDPB Opinion 28/2024; CNIL guidance June/July 2025; Italian Garante vs. OpenAI (Nov 2024, EUR 15M); CNIL vs. Google (Sept 2025, EUR 325M)

### Tertiary (LOW confidence — validate during implementation)
- FalkorDB-to-Neo4j switching point at ~10M edges — from Graphiti documentation; not independently benchmarked for HiveMind's query patterns
- Real estate pack pricing benchmark (EUR 50-200/month per agent) — from pricing research PDF; needs market validation with actual prospects
- 12-18 month delay recommendation for crypto layer — from pricing strategy research; qualitative recommendation, not empirical

---

*Research completed: 2026-02-18*
*Ready for roadmap: yes*
