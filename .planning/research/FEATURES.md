# Feature Research

**Domain:** Shared AI agent memory / knowledge commons platform
**Researched:** 2026-02-18
**Confidence:** HIGH (primary sources: three deep-research PDFs from February 2026 covering 50+ projects, academic papers arXiv:2505.18279 and arXiv:2407.06485, and live market data)

---

## Context: What the Market Has (and Has Not) Built

The February 2026 research surveyed 50+ projects across 8 categories and reached a stark conclusion: **no existing product combines cross-organisational knowledge sharing, agent-to-agent knowledge trading, and vertical knowledge packs in a single platform.** Every incumbent operates in exactly one of those three axes.

- **Private per-user memory** (Mem0, Zep/Graphiti, Letta): mature, well-funded, entirely siloed
- **Skill/tool marketplaces** (GPT Store, PulseMCP, SkillsMP, ClawHub): distribute capabilities, never structured knowledge
- **Intra-org shared memory** (AWS AgentCore, MS Work IQ, Claude Team): shared within one organisation, never cross-org
- **Crypto infrastructure** (OriginTrail, Story Protocol, Shinkai): partial knowledge graph or trading protocol, never combined with vertical packs
- **Vertical AI SaaS** (Harvey, Abridge, EliseAI, ZBrain): massive knowledge moats locked inside proprietary workflows, never sold as MCP-accessible packs

HiveMind occupies the white space at the intersection of all three axes. This shapes the feature analysis below: the "table stakes" are not borrowed from direct competitors (there are none) — they are borrowed from the adjacent markets users already know (private memory systems, data marketplaces, B2B SaaS tools).

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels broken or untrustworthy, not just incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **MCP server with standard tool surface** (`add_knowledge`, `search_knowledge`, `list_knowledge`) | MCP is the de facto universal standard (Linux Foundation, adopted by every major IDE and LLM client). Agents expect to connect via MCP. Without it, agents cannot use the product at all. | MEDIUM | MCP spec (2025-11-25) with HTTP Streaming transport. Must expose `add_knowledge`, `search_knowledge`, `get_knowledge`, `delete_knowledge` at minimum. Two MCP implementations exist as reference: Mem0 OpenMemory MCP and Graphiti MCP server. |
| **Semantic search / hybrid retrieval** | Every memory system in the market (Mem0, Graphiti, Letta) ships hybrid search. Agents querying a knowledge base expect ranked, relevant results — not keyword grep. A system that returns noise is worse than no system. | MEDIUM | Minimum: vector similarity (embeddings) + BM25 keyword fusion via RRF. Graphiti achieves P95 retrieval in 300ms with zero LLM calls at retrieval time — that is the performance target. |
| **Automatic PII stripping before knowledge enters commons** | This is the trust gate that makes cross-org sharing possible at all. Without it, no enterprise connects. The "noisy commons" problem identified in arXiv:2505.18279 — unfiltered collective memory degrades value — makes sanitisation non-negotiable. | HIGH | Must run before any knowledge is written to the shared store. Regex + NER at minimum. Configurable sensitivity levels. Audit log of what was stripped. |
| **User approval / consent flow** | Agents sharing knowledge on behalf of a user without the user's explicit opt-in is a legal and trust problem. GDPR (EU), CCPA (US) require consent for data that may contain personal signals. Users must be able to review what will be shared before it is committed. | MEDIUM | Notification surface (email, webhook, or web dashboard). Approve / reject / edit per-item or per-category. Opt-out controls. Settings to pre-approve certain knowledge types. |
| **Knowledge provenance and attribution** | If agents trust contributed knowledge, they need to know where it came from, when, and by which agent/user — so they can weight it appropriately and trace errors. Academic literature (arXiv:2407.06485 "CrowdTransfer") makes provenance a first-class architectural requirement. | MEDIUM | Each knowledge item: `source_agent_id`, `contributed_at`, `category`, `confidence_score`, optional `version`. Immutable once written. |
| **Persistent storage with ACID guarantees** | Every production memory system (Mem0, Graphiti, Letta) uses a durable backend. Agents that contribute knowledge expect it to survive restarts, not live in-memory. | LOW | PostgreSQL + pgvector is the most pragmatic choice (co-locates relational metadata and vector embeddings, simplifies ops). Qdrant as standalone vector store if scale demands it. |
| **REST API + SDK** | Developers integrating into existing agent stacks (LangChain, CrewAI, custom) need a programmable interface beyond MCP. Mem0 ships Python + TypeScript SDKs; every serious dev tool does. | MEDIUM | REST API with standard CRUD. Python SDK (priority — most AI agent code is Python). TypeScript SDK (second). Auth via API key. |
| **Web dashboard — live view of the knowledge commons** | A live dashboard is what turns an invisible infrastructure layer into a product people can see working. Without observability, adoption stalls — users need to verify their agents are contributing and that the commons is growing. | MEDIUM | Real-time feed of incoming knowledge contributions. Search interface. Per-user contribution stats. Knowledge item detail view with provenance. |
| **Conflict detection / deduplication** | When many agents contribute knowledge, duplicates and contradictions accumulate rapidly. Every mature memory system (Mem0: A.U.D.N. cycle, Graphiti: bi-temporal model, Letta: block versioning) handles this. A commons without it degrades quickly. | HIGH | At minimum: vector similarity check before write (reject near-duplicates above threshold). Better: LLM-assisted UPDATE vs ADD vs NOOP decision on conflict. Temporal tracking (when was this valid). |
| **Access control / namespace isolation** | Agents from Company A must not see knowledge contributed by Company B unless explicitly shared. This is the foundational multi-tenancy requirement. Without it, the product is a data liability, not an asset. | HIGH | Namespace per organisation. RBAC: agent roles (contributor, reader, admin). Optional public namespace for the global commons. Graphiti's `group_id` pattern is the right primitive to copy and extend. |

---

### Differentiators (Competitive Advantage)

Features that set HiveMind apart. Zero competitors currently offer any of these in the context of shared cross-org knowledge.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Cross-organisational knowledge commons (the "Waze model")** | The core white space. Zero products currently allow an agent from Company X to benefit from knowledge contributed by an agent from Company Y. HiveMind is first. The network effect compounds: more agents contributing = better knowledge = more agents joining. | HIGH | Requires: namespace isolation (so orgs can control what leaks), a public/shared namespace, quality scoring to prevent "noisy commons" degradation. arXiv:2505.18279 proposes bipartite dynamic access graphs as the formal model — implement simplified version. |
| **B2B vertical knowledge packs (real estate, accounting, e-commerce)** | The research finding is sharp: Harvey ($1.2B+), Abridge ($550M+), EliseAI ($250M+) have massive vertical knowledge moats but sell workflows, not packs. ZBrain is closest with pre-built agents per vertical but it is a closed enterprise platform. A marketplace of MCP-accessible, curated, continuously-updated vertical knowledge packs does not exist. This is a standalone $10B+ market opportunity. | HIGH | Phase 1: curate first pack manually (real estate recommended — mature willingness-to-pay: €50-200/month per agent, data is structured). Phase 2: creator marketplace (operators contribute, earn revenue share). Packs must be agent-accessible via MCP, not locked in a UI workflow. |
| **Bi-temporal knowledge tracking** | Graphiti's bi-temporal model (ingestion time vs real-world validity time) is the only system that correctly handles "when did we know this" vs "when was this true." For domains like real estate pricing or tax rules, this is essential — knowledge expires. No competitor in the collective memory space has this. | HIGH | Track `valid_from`, `valid_until`, `ingested_at`, `expired_at` per knowledge item. Allow temporal queries ("what did agents know about X in Q3 2025?"). Enables knowledge deprecation and audit. |
| **Agent-to-agent knowledge trading with micropayments (crypto layer)** | The research identifies x402 (Coinbase's HTTP micropayment protocol) as the emerging standard for agent-to-agent economic transactions. Story Protocol (ATCP/IP) has the most advanced trading framework for IP but targets media, not operational knowledge. Shinkai Protocol is most conceptually aligned but early-stage. No one combines knowledge + pricing + micropayments in a working product. | VERY HIGH | Defer 12-18 months minimum per the pricing research recommendation. Build the free commons first, accumulate a critical mass of agents and knowledge, then layer payments. Model after Numerai (stake-to-earn quality validation) + Poe (creator-set pricing). Abstract all blockchain complexity from the user — payments in euros, automatic conversion. Budget cap: <15% of total dev investment until PMF signal emerges. |
| **Flywheel quality scoring** | The academic "noisy commons" risk (arXiv survey "Memory in LLM-based Multi-agent Systems", TechRxiv 2025) means raw crowdsourced knowledge degrades. A quality score per knowledge item — derived from downstream consumption signals (how often retrieved, did the retrieving agent succeed?) — creates a self-improving commons where high-quality knowledge surfaces and low-quality knowledge decays. | HIGH | Input signals: retrieval frequency, agent-reported usefulness (thumbs up/down from agent or user), contradiction rate, staleness. Output: per-item quality score (0-1). Use score to rank search results and to gate crypto layer pricing. |
| **Knowledge category taxonomy with domain-aware extraction** | Generic memory systems (Mem0, Letta) extract facts generically. HiveMind knowledge has types: `bug_fix`, `config`, `domain_expertise`, `workaround`, `pricing_data`, `regulatory_rule`. Typed knowledge enables targeted vertical packs and allows category-level consent controls (e.g. "share bug fixes but not pricing data"). | MEDIUM | Start with 6-8 top-level categories. Per-category extraction prompts. Category appears in every knowledge item's metadata and drives search filtering. |
| **Sleep-time / async knowledge distillation** | Letta's "sleep-time agent" concept: a background process that runs when agents are idle, consolidates related knowledge, identifies contradictions, and generates summaries. Applied to a collective commons, this means the knowledge base improves continuously without real-time compute cost. | HIGH | Run as a background job (cron or event-triggered). Inputs: recently contributed knowledge + existing similar knowledge. Actions: merge duplicates, flag contradictions, generate summaries for vertical packs. This is what keeps packs "live" and justifies premium pricing (3-5x over static datasets per the pricing research). |
| **Open-source core with hosted/managed premium** | The Mem0 (Apache 2.0 OSS + SaaS) and Databricks (Delta Sharing open source + enterprise) model: open-source the MCP server and core knowledge graph, monetise the hosted version, vertical packs, and crypto layer. This maximises adoption (the commons needs contributors) while creating a monetisation path. GitHub stars and OSS adoption drive enterprise inbound, as Graphiti demonstrated (20,000 stars in <12 months). | MEDIUM | OSS: MCP server + knowledge graph + PII stripping + basic REST API. Paid: hosted ops, SLA, vertical packs, advanced analytics, crypto trading layer. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like obvious additions but create more problems than they solve in HiveMind's specific context.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| **Fully autonomous knowledge sharing (no user approval step)** | Reduces friction; agents "just work" without human in the loop. | The "noisy commons" problem is existential: if agents dump everything into the commons without human review, knowledge quality degrades, PII leaks, and trust collapses. The academic literature (arXiv:2505.18279) explicitly warns about this. User approval is the trust gate, not a UX tax. | Tiered approval: auto-approve low-risk categories (bug fixes, generic configs) that pass PII check; require explicit approval for domain expertise and pricing data. Users can expand auto-approve scope over time as trust is established. |
| **Real-time everything (live streaming knowledge updates to all connected agents)** | Feels modern; "agents learn instantly from each other." | Massive infrastructure complexity (pub/sub at scale), high latency variance, difficult to implement quality gating in real-time path. Every serious memory system (Graphiti: sequential writes per group_id, Letta: block size limits) imposes write ordering constraints. Real-time streaming without quality gates means agents act on unverified knowledge. | Near-real-time (seconds, not milliseconds) via polling or webhook push after quality gate passes. Reserve true streaming for dashboard UI (which has no quality gate consequence). |
| **Monolithic knowledge blob (single global commons without namespacing)** | Simpler to implement; "one pool of knowledge for everyone." | Violates enterprise data isolation requirements (GDPR, SOC2, internal compliance). A leak from one org's knowledge into another's creates legal liability. No enterprise adopts a platform without namespace isolation. | Hierarchical namespaces: private (org-only) + shared (explicitly published to commons) + vertical packs (curated, sold separately). Start with this model, do not simplify it away. |
| **LLM-generated knowledge quality scores (scoring by asking the LLM if knowledge is good)** | Seems smart; use the LLM to evaluate itself. | LLM evaluation of knowledge quality is expensive (token cost per item), slow (adds latency to every write), inconsistent (non-deterministic), and gameable (agents that know the scoring prompt can optimise for score, not quality). Mem0's A.U.D.N. cycle already shows LLM-in-the-loop at write time adds latency (P95: 1.4s). | Behavioural signals: retrieval frequency, agent outcome reporting (did the task succeed after using this knowledge?), contradiction detection. These are cheaper, more reliable, and harder to game. |
| **A general-purpose horizontal data marketplace** | "Why limit to AI agent knowledge? Sell any dataset!" | The pricing research is explicit: horizontal data marketplaces (Datarade: $2.1M revenue, The Graph: $100-215K/quarter organic revenue) generate minimal value. Vertical SaaS integrating knowledge into workflows generates 10-100x more value. Ocean Protocol pivoted away from horizontal marketplace due to negligible volume. | Maintain vertical focus. Each knowledge pack must answer a specific business question (not "here is data" but "here is an answer"). Sell outcomes, not datasets. |
| **Visible crypto complexity in the user-facing product** | Crypto layer is technically interesting; some users will want to see wallet addresses, token balances, on-chain transactions. | The pricing research is unambiguous: crypto adoption friction (wallets, token management, price volatility) is the primary blocker for B2B SME adoption. 70-80% of French TPE/PME cite compliance and French-language support as top criteria — not blockchain features. Even Story Protocol ($489M mcap) generates only $17-45/day in revenue. | Abstract all crypto. Users see euros, not tokens. Conversion happens invisibly. The token layer is an internal incentive mechanism, not a user-facing feature. Expose it only in an advanced "agent economy" settings panel, opt-in. |
| **Unlimited free tier (unrestricted knowledge reads and writes)** | Drives adoption; "free = more users." | Without request limits, there is no conversion pressure. The pricing research benchmarks freemium SaaS B2B at 2-5% conversion (self-serve) and 5-10% with commercial assistance. Unlimited free creates a pool of users who never have a reason to pay. It also enables abuse (agents scraping the entire commons). | Generous but bounded free tier: 100 queries/month + 50 knowledge contributions/month (enough for genuine evaluation, not enough for production use). Freemium key metrics to watch: contributions per user, queries per user, conversion to paid at 90 days. |

---

## Feature Dependencies

```
[PII Stripping]
    └──required by──> [Knowledge Contribution Flow]
                          └──required by──> [Cross-Org Knowledge Commons]
                          └──required by──> [Vertical Knowledge Packs]

[User Approval / Consent Flow]
    └──required by──> [Knowledge Contribution Flow]
    └──required by──> [Cross-Org Knowledge Commons]

[Access Control / Namespace Isolation]
    └──required by──> [Cross-Org Knowledge Commons]
    └──required by──> [Vertical Knowledge Packs] (orgs must not see others' private namespaces)

[MCP Server]
    └──required by──> [Agent Integration] (agents cannot connect without it)
    └──required by──> [Vertical Knowledge Packs] (packs accessed via MCP)

[Knowledge Provenance + Attribution]
    └──required by──> [Quality Scoring / Flywheel]
    └──required by──> [Crypto Trading Layer] (you cannot price knowledge without knowing who made it)

[Semantic Search / Hybrid Retrieval]
    └──required by──> [Quality Scoring / Flywheel] (retrieval frequency is a quality signal)
    └──required by──> [Vertical Knowledge Packs] (packs are only useful if search surfaces the right items)

[Quality Scoring / Flywheel]
    └──required by──> [Crypto Trading Layer] (stake-to-earn requires a quality signal to stake against)
    └──enhances──> [Vertical Knowledge Packs] (quality score gates what enters a pack)

[Conflict Detection / Deduplication]
    └──required by──> [Cross-Org Knowledge Commons] (noisy commons kills the product)
    └──enhances──> [Quality Scoring / Flywheel]

[Bi-Temporal Tracking]
    └──enhances──> [Vertical Knowledge Packs] (packs need "live" data with expiry)
    └──enhances──> [Conflict Detection] (temporal context resolves many apparent conflicts)

[Knowledge Category Taxonomy]
    └──required by──> [User Approval] (category-level consent controls)
    └──enhances──> [Vertical Knowledge Packs] (packs are category-scoped)
    └──enhances──> [Semantic Search] (category filters improve precision)

[Sleep-Time Distillation]
    └──requires──> [Conflict Detection / Deduplication] (distillation merges, dedup prevents re-creation)
    └──enhances──> [Vertical Knowledge Packs] (distillation is what generates pack summaries)

[Crypto Trading Layer]
    └──requires──> [Quality Scoring / Flywheel] (no quality signal = no basis for pricing)
    └──requires──> [Knowledge Provenance] (cannot pay creator without knowing who created it)
    └──requires──> [Cross-Org Commons at scale] (needs sufficient volume before trading is meaningful)
```

### Dependency Notes

- **PII Stripping is the prerequisite for everything.** Without it, no knowledge can safely enter the commons. It must be implemented before any knowledge contribution feature is shipped.
- **User Approval requires a notification surface.** Email or webhook is sufficient for MVP; the dashboard makes it better but is not strictly required for approval to work.
- **Crypto Trading Layer has a hard dependency on time.** The pricing research recommends 12-18 months of knowledge accumulation before the trading layer launches. Building it too early means launching into an empty market.
- **Vertical Knowledge Packs require both PII Stripping and Quality Scoring before they can be sold.** Selling unscored, potentially PII-contaminated knowledge packs is a legal and reputational risk.
- **Sleep-Time Distillation and Bi-Temporal Tracking are independent of each other** but both enhance Vertical Pack quality. They can be built in parallel after the core is stable.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what is needed to validate the core concept (agents contributing and consuming shared knowledge across organisational boundaries) without requiring trust that has not yet been earned.

- [ ] **MCP server with core tools** (`add_knowledge`, `search_knowledge`, `list_knowledge`, `delete_knowledge`) — without this, no agent can connect
- [ ] **PII stripping pipeline** — automatic, runs on every inbound knowledge item before storage; must be in production before any knowledge is accepted from real users
- [ ] **User approval flow** — webhook or email notification; user approves/rejects before knowledge enters commons; minimum viable consent mechanism
- [ ] **Namespace isolation** — private namespace per org, opt-in public commons namespace; no cross-org leakage without explicit publication
- [ ] **Knowledge provenance** — `source_agent_id`, `contributed_at`, `category`, `org_id` on every item; immutable
- [ ] **Hybrid retrieval (vector + keyword)** — embeddings + BM25 + RRF; must return relevant results in <500ms P95
- [ ] **Conflict detection (similarity threshold)** — reject near-duplicate writes above cosine similarity threshold (configurable, default 0.95); prevents immediate commons pollution
- [ ] **Web dashboard (read-only live view)** — real-time feed of contributions, search interface, provenance detail; makes the commons observable and credible
- [ ] **REST API + Python SDK** — enables non-MCP integrations and developer evaluation
- [ ] **Basic knowledge category taxonomy** — 6-8 top-level categories (bug_fix, config, domain_expertise, workaround, pricing_data, regulatory_rule); used for filtering and consent

### Add After Validation (v1.x)

Features to add once the contribution/retrieval loop has real users and is demonstrably working.

- [ ] **Quality scoring (behavioural signals)** — trigger: first 100 active contributors or first 10,000 knowledge items; retrieval frequency + outcome reporting
- [ ] **Knowledge category-level consent controls** — trigger: user feedback that blanket approval is too coarse; allow per-category auto-approve rules
- [ ] **TypeScript SDK** — trigger: developer demand from JavaScript/TypeScript agent stacks
- [ ] **Bi-temporal knowledge tracking** — trigger: first vertical pack launch or user-reported staleness issues; adds `valid_from`/`valid_until` to storage schema
- [ ] **First vertical knowledge pack (real estate)** — trigger: sufficient real estate knowledge contributed organically OR manual curation; requires quality scoring to be live
- [ ] **Sleep-time distillation (background consolidation)** — trigger: knowledge base exceeds 50K items and quality begins degrading; runs as async job
- [ ] **Advanced conflict resolution (LLM-assisted)** — trigger: similarity threshold alone generates too many false positives; add UPDATE vs NOOP decision layer

### Future Consideration (v2+)

Features to defer until product-market fit is established and the knowledge commons has critical mass.

- [ ] **Crypto trading layer / micropayments** — defer 12-18 months minimum; requires: established user base, quality scoring operational, legal/regulatory clarity on token classification
- [ ] **Vertical knowledge pack marketplace (creator-contributed)** — defer until HiveMind has demonstrated internal curation quality; premature creator marketplace = low-quality pack proliferation (GPT Store failure pattern)
- [ ] **Agent wallets / dynamic pricing** — defer with crypto layer; abstract entirely from user-facing UI when built
- [ ] **Cross-namespace knowledge federation** — defer; complex access control surface, low demand at early stage
- [ ] **AGNTCY / A2A protocol integration** — monitor Google A2A (150+ partners, Linux Foundation); integrate once standard stabilises; not critical for MVP

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| MCP server (core tools) | HIGH | MEDIUM | P1 |
| PII stripping pipeline | HIGH | HIGH | P1 |
| User approval / consent flow | HIGH | MEDIUM | P1 |
| Namespace isolation / access control | HIGH | HIGH | P1 |
| Hybrid semantic search | HIGH | MEDIUM | P1 |
| Knowledge provenance | HIGH | LOW | P1 |
| Conflict detection (similarity threshold) | HIGH | MEDIUM | P1 |
| Web dashboard (live view) | HIGH | MEDIUM | P1 |
| REST API + Python SDK | HIGH | MEDIUM | P1 |
| Knowledge category taxonomy | MEDIUM | LOW | P1 |
| Quality scoring (behavioural) | HIGH | HIGH | P2 |
| Bi-temporal tracking | MEDIUM | HIGH | P2 |
| First vertical knowledge pack (real estate) | HIGH | HIGH | P2 |
| Sleep-time distillation | MEDIUM | HIGH | P2 |
| TypeScript SDK | MEDIUM | LOW | P2 |
| Category-level consent controls | MEDIUM | MEDIUM | P2 |
| LLM-assisted conflict resolution | MEDIUM | HIGH | P2 |
| Vertical pack marketplace (creator) | HIGH | VERY HIGH | P3 |
| Crypto trading layer | MEDIUM | VERY HIGH | P3 |
| Agent wallets / dynamic pricing | MEDIUM | VERY HIGH | P3 |
| Cross-namespace federation | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — MVP is non-functional without it
- P2: Should have — add after validating core contribution/retrieval loop
- P3: Future — defer until product-market fit is confirmed

---

## Competitor Feature Analysis

The research found zero direct competitors. The comparison below maps the closest incumbents across the three axes HiveMind occupies.

| Feature | Mem0 / Zep / Letta (private memory) | OriginTrail / Shinkai (crypto knowledge infra) | ZBrain (vertical agent store) | HiveMind Approach |
|---------|--------------------------------------|------------------------------------------------|-------------------------------|-------------------|
| **Cross-org knowledge sharing** | No — per-user/per-org only | Partial — DKG allows cross-node, but no UX | No — closed enterprise platform | YES — core differentiator; public commons + opt-in publication |
| **MCP integration** | Mem0 yes, Graphiti yes, Letta no (consumes MCP, does not expose) | No | No | YES — MCP as primary interface; first-class, not an afterthought |
| **PII stripping** | No native stripping (user's responsibility) | No | No | YES — automatic pipeline before any commons write; hard requirement |
| **User approval / consent** | No | No | No | YES — notification + approve/reject per item or category |
| **Vertical knowledge packs** | No | OriginTrail: Paranets (partial) | YES — per-vertical agents, closed | YES — MCP-accessible, curated packs; first vertical: real estate |
| **Quality scoring / flywheel** | Mem0: A.U.D.N. (single-user) | No | No | YES — cross-agent behavioural signal; feeds pack curation and crypto pricing |
| **Crypto trading / micropayments** | No | OriginTrail: TRAC costs; Story: ATCP/IP | No | YES (v2+) — x402 micropayments; abstract crypto from user; Numerai model for quality staking |
| **Bi-temporal knowledge** | Graphiti: YES (best in class) | No | No | YES — adopt Graphiti's bi-temporal model; required for live vertical packs |
| **Web dashboard** | Mem0 platform: YES (per-user analytics) | OriginTrail: blockchain explorer | ZBrain: admin console | YES — live commons view; contribution feed; search; provenance detail |
| **Open-source core** | Mem0: Apache 2.0; Graphiti: Apache 2.0 | OriginTrail: open; Shinkai: open | No | YES — MCP server + core graph open-source; packs + crypto + hosted = monetised |

---

## Sources

- **Cartographie du Knowledge Sharing Inter-Agents IA — Février 2026** (primary): 50+ project analysis, white space identification, MCP ecosystem survey, crypto protocol comparison, corporate memory map
- **Trois frameworks de mémoire pour agents IA: analyse comparative approfondie** (primary): Mem0/Graphiti/Letta deep architecture, ingestion pipelines, retrieval latencies, shared memory mechanisms, vector store comparison
- **Stratégie de Pricing pour une Plateforme de Knowledge IA à Trois Couches — 2025** (primary): data marketplace benchmarks, freemium conversion rates, vertical SaaS pricing, crypto protocol revenue reality, sequencing recommendation (delay crypto 12-18 months)
- **arXiv:2505.18279 "Collaborative Memory"**: private + shared memory architecture, bipartite dynamic access graphs, noisy commons warning
- **arXiv:2407.06485 "CrowdTransfer"**: crowdsourced knowledge transfer between agents, provenance requirements
- **Academic survey "Memory in LLM-based Multi-agent Systems" (TechRxiv 2025)**: "team mind" concept, noisy commons as primary collective memory risk
- Market data points: Mem0 ($24M, 41K GitHub stars, 186M API calls/quarter), Graphiti (20K stars in <12 months, $1M revenue), Harvey ($1.2B+ valuation), Pennylane (40x growth in 2 years), x402 protocol (Coinbase, emerging micropayment standard)

---

*Feature research for: HiveMind — shared AI agent memory / knowledge commons*
*Researched: 2026-02-18*
