# Architecture Research

**Domain:** Shared AI agent memory / collective knowledge commons platform
**Researched:** 2026-02-18
**Confidence:** HIGH (sourced from three deep technical research PDFs covering the full ecosystem state as of February 2026)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AGENT LAYER (Clients)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Claude Code  │  │    Cursor    │  │  OpenClaw    │  │  Any MCP     │    │
│  │  (agent A)   │  │  (agent B)   │  │  (agent C)   │  │  client      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────────┘
          │   MCP (stdio/SSE/HTTP)             │                 │
          ▼                 ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         MCP SERVER GATEWAY                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  MCP Protocol Handler                                                  │  │
│  │  Tools: contribute_knowledge | search_knowledge | get_pack |           │  │
│  │         approve_pending | list_pending | trade_knowledge               │  │
│  └──────────────────────────────┬─────────────────────────────────────────┘  │
│                                  │                                            │
│  ┌──────────────────┐  ┌─────────┴────────┐  ┌──────────────────────────┐   │
│  │  Auth / API Key  │  │  Rate Limiter    │  │  Session Manager         │   │
│  │  Validation      │  │  (per agent)     │  │  (WebSocket for RT push) │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────────┐   ┌────────────────────────┐
│  INGESTION       │   │  KNOWLEDGE STORE     │   │  DISTRIBUTION          │
│  PIPELINE        │   │  (Core)              │   │  ENGINE                │
│                  │   │                      │   │                        │
│  Extract         │   │  ┌────────────────┐  │   │  Real-time push        │
│  ↓               │   │  │ Vector Store   │  │   │  (WebSocket/SSE)       │
│  PII Strip       │   │  │ (Qdrant)       │  │   │                        │
│  ↓               │   │  └────────────────┘  │   │  Subscription filter   │
│  Deduplicate     │   │  ┌────────────────┐  │   │  by domain/tag         │
│  ↓               │   │  │ Graph Store    │  │   │                        │
│  Quality Score   │   │  │ (Neo4j/        │  │   │  Pack assembly         │
│  ↓               │   │  │  FalkorDB)     │  │   │  (curate → bundle)     │
│  Approval Queue  │   │  └────────────────┘  │   │                        │
│  ↓               │   │  ┌────────────────┐  │   └────────────────────────┘
│  Index + Store   │   │  │ Relational DB  │  │
└──────────────────┘   │  │ (PostgreSQL)   │  │
                        │  └────────────────┘  │
                        └──────────────────────┘
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────────┐   ┌────────────────────────┐
│  B2B PACK        │   │  CRYPTO / PAYMENT    │   │  WEB DASHBOARD         │
│  SYSTEM          │   │  LAYER               │   │                        │
│                  │   │                      │   │  Live knowledge graph  │
│  Pack registry   │   │  Agent wallets       │   │  Contribution feed     │
│  Pack versioning │   │  x402 micropayments  │   │  Pack marketplace UI   │
│  Waze flywheel   │   │  Knowledge pricing   │   │  Approval workflow     │
│  (contributors   │   │  engine              │   │  Analytics             │
│  improve packs)  │   │  Settlement          │   │                        │
└──────────────────┘   └──────────────────────┘   └────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| MCP Server Gateway | Protocol entry point; exposes HiveMind as MCP tools; handles auth, rate limiting, session management | All agents (inbound), Ingestion Pipeline, Knowledge Store, Distribution Engine |
| Ingestion Pipeline | Extracts knowledge units from raw agent contributions; strips PII; scores quality; deduplicates; routes to approval queue | MCP Gateway (inbound), PII Stripper, Approval Store, Knowledge Store |
| PII Stripper | Stateless processor that removes identifying information from raw knowledge text before it enters the commons | Ingestion Pipeline only |
| Approval Queue | Holds contributed knowledge pending user review; notifies contributing user; applies configurable auto-approve rules | Ingestion Pipeline (inbound), Web Dashboard (UI), Knowledge Store (approved path) |
| Knowledge Store | The shared commons. Three-layer storage: vector (semantic search), graph (entity/relationship/temporal), relational (metadata, ACL, audit) | Ingestion Pipeline, Distribution Engine, MCP Gateway (reads), B2B Pack System |
| Distribution Engine | Pushes newly approved knowledge to connected agents in real time; filters by agent subscription (domain, tag); assembles pack content for delivery | Knowledge Store, MCP Gateway (outbound push), B2B Pack System |
| B2B Pack System | Curates domain-specific knowledge subsets into versioned packs; manages the Waze-model contribution flywheel (pack users contribute back) | Knowledge Store, Distribution Engine, Web Dashboard, Crypto/Payment Layer |
| Crypto / Payment Layer | Agent wallets, micropayment processing (x402 protocol), dynamic pricing engine, settlement for knowledge trades | B2B Pack System, MCP Gateway (trade_knowledge tool), external blockchain/payment rail |
| Web Dashboard | Human-facing UI: live visualization of commons growth, approval workflow, pack marketplace, analytics | Knowledge Store (read), Approval Queue, B2B Pack System, Distribution Engine (WebSocket) |

---

## Recommended Project Structure

```
hivemind/
├── packages/
│   ├── mcp-server/               # MCP protocol gateway (entry point for agents)
│   │   ├── src/
│   │   │   ├── tools/            # MCP tool definitions (contribute, search, approve, trade)
│   │   │   ├── auth/             # API key validation, per-agent rate limiting
│   │   │   ├── session/          # WebSocket/SSE connection management
│   │   │   └── server.ts         # MCP server bootstrap
│   │   └── package.json
│   │
│   ├── ingestion/                # Knowledge processing pipeline
│   │   ├── src/
│   │   │   ├── extractor/        # LLM-based knowledge extraction from raw agent sessions
│   │   │   ├── pii-stripper/     # PII detection and removal (local model, no external calls)
│   │   │   ├── deduplicator/     # Hash + vector similarity dedup
│   │   │   ├── quality-scorer/   # Heuristic + LLM quality scoring
│   │   │   └── approval-queue/   # Queue management, notification dispatch
│   │   └── package.json
│   │
│   ├── knowledge-store/          # Storage abstraction layer
│   │   ├── src/
│   │   │   ├── vector/           # Qdrant client + embedding logic
│   │   │   ├── graph/            # Neo4j/FalkorDB client, bi-temporal edge model
│   │   │   ├── relational/       # PostgreSQL schema (metadata, ACL, audit trail)
│   │   │   └── index.ts          # Unified store interface
│   │   └── package.json
│   │
│   ├── distribution/             # Real-time knowledge push engine
│   │   ├── src/
│   │   │   ├── pubsub/           # Internal event bus (knowledge approved → push)
│   │   │   ├── subscription/     # Per-agent subscription filters (domain, tag)
│   │   │   └── pack-assembler/   # Pack content assembly for delivery
│   │   └── package.json
│   │
│   ├── packs/                    # B2B vertical knowledge pack system
│   │   ├── src/
│   │   │   ├── registry/         # Pack metadata, versioning, changelog
│   │   │   ├── curator/          # Tools for curating knowledge into packs
│   │   │   └── flywheel/         # Contribution-back tracking for Waze model
│   │   └── package.json
│   │
│   ├── crypto/                   # Crypto / payment layer (Phase 3+)
│   │   ├── src/
│   │   │   ├── wallet/           # Agent wallet management
│   │   │   ├── pricing/          # Dynamic knowledge pricing engine
│   │   │   ├── x402/             # x402 micropayment protocol integration
│   │   │   └── settlement/       # Trade settlement logic
│   │   └── package.json
│   │
│   └── dashboard/                # Web dashboard (Next.js)
│       ├── src/
│       │   ├── app/              # App Router pages
│       │   ├── components/       # Live graph visualization, approval UI, pack marketplace
│       │   └── hooks/            # WebSocket subscriptions for live feed
│       └── package.json
│
├── apps/
│   └── api/                      # Main HTTP API server (ties packages together)
│       ├── src/
│       │   ├── routes/           # REST endpoints for dashboard + external integrations
│       │   └── index.ts
│       └── package.json
│
├── infra/
│   ├── docker-compose.yml        # Local dev: PostgreSQL, Qdrant, Neo4j/FalkorDB
│   └── migrations/               # Database schema migrations
│
└── docs/
    └── mcp-tools.md              # MCP tool documentation for agent developers
```

### Structure Rationale

- **packages/ monorepo:** Each major system boundary is its own package with explicit interfaces. This allows the open-source core (mcp-server, ingestion, knowledge-store, distribution) to be separated cleanly from monetized layers (packs, crypto).
- **mcp-server/ separate from api/:** The MCP gateway and the REST API have different transport, auth, and lifecycle requirements. Keeping them separate avoids coupling.
- **ingestion/ as pipeline:** The ingestion steps (extract, strip, dedup, score, queue) are sequential and stateful. A dedicated package with clear stage boundaries makes testing and hot-swapping of individual steps (e.g., swapping the PII model) straightforward.
- **knowledge-store/ as abstraction:** Storage technology decisions (Qdrant vs pgvector, Neo4j vs FalkorDB) are volatile. A unified interface lets Phase 1 start simple (pgvector only) and add graph storage in Phase 2 without rewriting callers.
- **crypto/ isolated:** The payment layer is the highest-risk architectural dependency. Isolation means it can be built late and fail without affecting core functionality.

---

## Architectural Patterns

### Pattern 1: Bi-Temporal Knowledge Graph for Conflict Resolution

**What:** Every knowledge entry carries four timestamps: `valid_at` (when the fact became true), `invalid_at` (when it ceased being true), `created_at` (ingestion time), `expired_at` (system invalidation). Old facts are never deleted — only invalidated. New contradictory contributions create new edges rather than overwriting.

**When to use:** All knowledge in the graph layer. This is the only proven approach to multi-contributor conflict resolution at the knowledge level. Borrowed from Graphiti's architecture (which powers Zep Cloud).

**Trade-offs:** More storage, more complex queries, but no data loss and clear audit trail. Critical for trust: users can always see what changed and when.

**Example:**
```typescript
interface KnowledgeEdge {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation: string;
  fact: string;
  // Bi-temporal timestamps
  valid_at: Date;       // when this became true in the world
  invalid_at: Date | null;  // when it stopped being true (null = still valid)
  created_at: Date;     // when HiveMind ingested this
  expired_at: Date | null;  // when HiveMind invalidated it (null = not invalidated)
  // Provenance
  contributor_agent_id: string;
  confidence_score: number;
}
```

### Pattern 2: Hybrid Vector + Graph Retrieval with Reciprocal Rank Fusion

**What:** Knowledge retrieval uses two parallel queries — cosine similarity on dense embeddings (Qdrant) for semantic match, and graph traversal (Neo4j/FalkorDB) for relationship context. Results are fused using Reciprocal Rank Fusion (RRF). No LLM call at retrieval time.

**When to use:** All `search_knowledge` MCP tool calls. This is the retrieval pattern used by Graphiti/Zep (sub-200ms p50 latency claimed in production).

**Trade-offs:** More complex retrieval logic, two storage systems to maintain. Payoff is significantly better results than vector-only for queries requiring relational context (e.g., "how does X interact with Y in this framework").

**Example:**
```typescript
async function searchKnowledge(query: string, filters: SearchFilters) {
  const [vectorResults, graphResults] = await Promise.all([
    vectorStore.search(query, { limit: 20, filters }),
    graphStore.traverse(query, { depth: 2, filters }),
  ]);
  return reciprocalRankFusion([vectorResults, graphResults], { k: 60 });
}
```

### Pattern 3: Four-Stage Ingestion Pipeline with Approval Gate

**What:** Every contribution passes through four sequential stages before entering the commons: (1) Extraction — LLM distills the raw agent session into discrete knowledge units; (2) PII Strip — local model removes names, emails, org identifiers, API endpoints; (3) Quality + Dedup — vector similarity check against existing knowledge, quality heuristic score; (4) Approval Gate — user notification, configurable auto-approve threshold, manual review UI.

**When to use:** Every `contribute_knowledge` call. The gate is the key trust mechanism — users must feel they control what enters the commons.

**Trade-offs:** Adds latency before knowledge is available (seconds to minutes depending on approval). This is intentional — the research identifies "noisy commons" as the primary risk for collective memory systems. Quality gate is the mitigation.

**Example:**
```typescript
async function ingestContribution(raw: RawContribution): Promise<void> {
  const units = await extractor.extract(raw.session_text);
  const stripped = await piiStripper.strip(units);
  const { unique, quality } = await deduplicator.score(stripped);

  if (quality < AUTO_APPROVE_THRESHOLD || !raw.agent_settings.auto_approve) {
    await approvalQueue.enqueue({ units: unique, contributor: raw.agent_id });
    await notifier.notify(raw.user_id, { pending_count: unique.length });
  } else {
    await knowledgeStore.insert(unique);
    await distributor.publish(unique);
  }
}
```

### Pattern 4: Namespace-Scoped Access Control (Multi-Tenant Commons)

**What:** Every knowledge entry belongs to a namespace hierarchy: `global` (available to all) or `pack:<pack_id>` (available to pack subscribers) or `private:<org_id>` (org-internal). Agents query with a list of namespace IDs they have access to. Borrowing Graphiti's `group_id` pattern extended to three tiers.

**When to use:** All reads and writes to the knowledge store. This is what separates the open commons from the paid B2B layer.

**Trade-offs:** Namespace filtering adds a metadata join to every query. At scale, materialized views or denormalized namespace tags on vector metadata mitigate this.

---

## Data Flow

### Knowledge Contribution Flow

```
Agent Session Ends
    ↓
Agent calls contribute_knowledge(session_context, metadata)
    ↓ [MCP tool call over stdio/SSE]
MCP Server Gateway
    ↓ [auth check, rate limit, session attribution]
Ingestion Pipeline: Extractor
    ↓ [LLM call: distill session → discrete knowledge units]
Ingestion Pipeline: PII Stripper
    ↓ [local NLP model: remove PII in-process, no external calls]
Ingestion Pipeline: Deduplicator
    ↓ [vector similarity vs. existing commons, hash check]
Ingestion Pipeline: Quality Scorer
    ↓ [heuristic score: specificity, actionability, source signal]
Approval Gate
    ├── [auto-approve if score > threshold AND user setting = auto]
    │       ↓
    │   Knowledge Store (insert to vector + graph)
    │       ↓
    │   Distribution Engine (publish to subscribed agents)
    │       ↓
    │   Connected agents receive new knowledge via SSE push
    │
    └── [else: queue for user approval]
            ↓
        User notified (Web Dashboard or MCP notification)
            ↓
        User approves/rejects via Dashboard
            ↓
        If approved: Knowledge Store → Distribution Engine → Agents
        If rejected: Entry discarded, rejection signal fed back to quality scorer
```

### Knowledge Retrieval Flow

```
Agent calls search_knowledge(query, filters)
    ↓ [MCP tool call]
MCP Server Gateway
    ↓ [auth check, namespace filter injected based on agent's subscriptions]
Knowledge Store: Parallel Retrieval
    ├── Vector Store: cosine similarity on query embedding (Qdrant)
    └── Graph Store: entity extraction + graph traversal (Neo4j/FalkorDB)
    ↓ [Reciprocal Rank Fusion — no LLM at retrieval time]
Merged + ranked results
    ↓ [rerank by recency + confidence if needed]
MCP response: list of knowledge units with metadata
    ↓
Agent incorporates knowledge into context
```

### Pack Distribution Flow

```
B2B Customer purchases pack subscription (via Dashboard)
    ↓
Pack System: assigns pack namespace access to customer's agents
    ↓
Agent calls get_pack(pack_id) or search_knowledge with pack namespace
    ↓ [standard retrieval flow above, scoped to pack namespace]
Agent receives pack knowledge

Pack Contribution Flywheel:
Agent using pack encounters new knowledge in the pack's domain
    ↓ [contribute_knowledge with pack_domain tag]
Standard ingestion flow above
    ↓ [curators review contributions tagged for pack domains]
Pack System: Curator approves contribution into pack namespace
    ↓
Pack version bumped, all pack subscribers receive new knowledge
```

### Real-Time Distribution Flow

```
Knowledge Store: new entry approved
    ↓ [internal event: knowledge_approved {id, namespaces, domains, tags}]
Distribution Engine: pubsub broadcast
    ↓ [filter: which agents have active SSE/WebSocket connections?]
    ↓ [filter: do agent's subscriptions match this entry's namespaces/domains?]
Matching connected agents: receive push notification via SSE
    ↓
Agent context updated without explicit poll
```

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 agents | Single-process Node.js. PostgreSQL with pgvector (vector + relational in one DB). No graph DB yet — defer Neo4j. All in Docker Compose. Qdrant as separate container. |
| 100-10K agents | Split MCP server and API server into separate processes. Add Redis for approval queue and pubsub. Keep PostgreSQL + Qdrant. Add Neo4j when graph queries appear in retrieval benchmarks. Horizontal scale on MCP server (stateless after auth). |
| 10K-100K agents | Qdrant cluster mode. Neo4j or FalkorDB cluster. PostgreSQL read replicas. Message queue (Kafka or BullMQ) replaces in-process pipeline. Ingestion workers scale independently from gateway. CDN for pack content delivery. |
| 100K+ agents | Evaluate moving to a managed vector DB (Pinecone/Weaviate) if Qdrant ops become a bottleneck. Regional deployment for latency. Pack content cached at edge. Knowledge Store sharded by namespace. |

### Scaling Priorities

1. **First bottleneck: ingestion pipeline LLM calls.** Extraction requires an LLM call per contribution. At volume, this creates latency spikes and cost pressure. Mitigation: async pipeline with BullMQ queues from day one, even if single-worker in Phase 1. Batching contributions per agent session reduces LLM calls.

2. **Second bottleneck: real-time distribution fan-out.** When a popular knowledge item is approved, it needs to fan out to thousands of connected agents simultaneously. Mitigation: Redis pub/sub or a lightweight message broker. SSE connections are cheap; the bottleneck is the fan-out loop, not the transport.

3. **Third bottleneck: graph traversal at read time.** Graph queries are expensive. Mitigation: cache frequent traversal results in Redis, use FalkorDB for deployments where Neo4j operational complexity is too high (FalkorDB is Redis-based, simpler ops, is also the default for Graphiti MCP deployments).

---

## Anti-Patterns

### Anti-Pattern 1: Eager Shared Memory (No Approval Gate)

**What people do:** Trust agents to contribute directly without user oversight. Auto-approve all contributions to maximize "real-time" feel.

**Why it's wrong:** The research identifies "noisy commons" as the primary risk for collective memory systems (arXiv 2505.18279 on "team mind"). Without a gate, low-quality, hallucinated, or contextually wrong knowledge accumulates and poisons retrieval for all agents. The value proposition of HiveMind is trustworthy collective knowledge, not just fast collective knowledge.

**Do this instead:** Ship with approval gate on by default. Allow users to configure auto-approve thresholds for high-confidence contributions, but make the gate opt-out not opt-in.

### Anti-Pattern 2: Single-Vector-Store Architecture

**What people do:** Use only a vector database (Qdrant or pgvector) because it's simpler and retrieval is fast.

**Why it's wrong:** Collective knowledge has rich relational structure — bug fix X depends on config Y which only applies to framework version Z. Pure vector search misses these multi-hop relationships. Mem0's flat memory architecture was benchmarked at 20,000x the construction time of BM25, and academic critics note its retrieval fails for compositional queries.

**Do this instead:** Start with pgvector for Phase 1 (simplicity), add the graph layer in Phase 2 before scale. Design the knowledge-store abstraction from day one to support both.

### Anti-Pattern 3: PII Stripping via External API Calls

**What people do:** Send raw agent sessions to an external LLM or cloud NLP API for PII removal before storing.

**Why it's wrong:** This creates a privacy violation before the privacy protection is applied. Any external API call with raw session data is a GDPR/CCPA risk. The PII stripper must run locally, in-process, with no data leaving the system until after stripping.

**Do this instead:** Use a local NLP model for PII detection (spaCy with NER, or a quantized local model). The deep research PDF on anonymization (found in project's deep_research folder) confirms this is the correct pattern — external API PII stripping is legally untenable.

### Anti-Pattern 4: Monolithic MCP + Business Logic

**What people do:** Implement business logic directly inside MCP tool handlers for speed.

**Why it's wrong:** MCP server code is highly coupled to protocol specifics (message format, transport, capability negotiation). Mixing domain logic in creates a hard-to-test, hard-to-maintain codebase. When MCP spec updates (it has updated significantly — Tasks, MCP Apps, Streamable HTTP were added in the 2025-11-25 spec), protocol changes force business logic rewrites.

**Do this instead:** MCP tool handlers are thin — they validate input, delegate to service functions in separate packages, and format the response. All business logic lives in `ingestion/`, `knowledge-store/`, `distribution/` packages.

### Anti-Pattern 5: Building the Crypto Layer First

**What people do:** Because crypto trading is the differentiator, it gets built in Phase 1 to attract crypto-native users.

**Why it's wrong:** The crypto layer has no value without a working knowledge commons. x402 micropayments require agent wallets, pricing engines, and settlement — all of which depend on the knowledge store and pack system being stable first. The research notes that Virtuals/Olas process 25,000+ ACP transactions/week but for services, not structured knowledge — the trading infra exists but the knowledge commons it would trade on does not.

**Do this instead:** Build the commons (Phases 1-2), then the B2B pack system (Phase 3), then add crypto trading as an optional payment rail for packs (Phase 4). Crypto should enhance monetization, not gate adoption.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Qdrant (vector DB) | REST/gRPC client from knowledge-store package | Default vector store. FalkorDB's built-in vector support is an alternative for smaller deployments (single-process). |
| Neo4j / FalkorDB (graph DB) | Bolt protocol client (Neo4j) or Redis protocol (FalkorDB) | Start with FalkorDB in dev (simpler Docker setup). Neo4j for production graph workloads. The knowledge-store abstraction should make this switchable. |
| PostgreSQL (relational) | pg client from knowledge-store package | Metadata, ACL, audit trail, approval queue state. Also houses pgvector for Phase 1 before Qdrant is added. |
| LLM for extraction | HTTP client to OpenAI/Anthropic API or Ollama (local) | Used only in ingestion pipeline (extraction stage). Must be async + queued. |
| Local NLP for PII | In-process (spaCy Python sidecar or WASM NER model) | No external calls. HiveMind must run the model locally. |
| x402 Protocol (micropayments) | HTTP middleware / payment header parsing | Coinbase's emerging standard for agent micropayments. Shinkai Protocol uses this; Story Protocol uses ATCP/IP. x402 is the most practical first target. |
| MCP Registry | Well-known URL discovery (`/.well-known/mcp`) | For discoverability in the MCP ecosystem. The MCP registry supports federation; HiveMind should register as a federated server. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| MCP Server Gateway ↔ Ingestion Pipeline | Function call (monorepo) or HTTP in split deployment | Async: gateway enqueues contribution, returns immediately to agent, pipeline processes in background |
| Ingestion Pipeline ↔ Approval Queue | Internal queue (BullMQ/Redis) | Decouples ingestion throughput from user approval latency |
| Approval Queue ↔ Knowledge Store | Direct write after approval confirmed | Atomic: approval = write + distribute together |
| Knowledge Store ↔ Distribution Engine | Internal event bus (EventEmitter in Phase 1, Redis pub/sub in Phase 2+) | Knowledge approved event triggers distribution fan-out |
| Distribution Engine ↔ MCP Gateway | WebSocket/SSE push to connected agent sessions | Gateway maintains connection registry; distribution engine publishes to matching connections |
| B2B Pack System ↔ Knowledge Store | Read: scoped queries by pack namespace. Write: curator-approved contributions get pack namespace tag added | Pack system is a view + curation layer over the commons, not a separate store |
| Crypto Layer ↔ Pack System | Payment rail for pack subscriptions and knowledge trades | Optional dependency. Pack system functions without crypto layer (SaaS billing in Phase 3). |
| Web Dashboard ↔ API | REST + WebSocket | Dashboard reads approval queue state, knowledge store stats, pack registry from REST API. Receives live feed via WebSocket. |

---

## Build Order (Dependency Chain)

The following order reflects the dependency structure of the architecture. Each phase can only be built after its predecessors are stable.

```
Phase 1: Foundation
  MCP Server Gateway (auth, tool stubs)
  ↓ requires nothing but MCP spec compliance
  Knowledge Store (pgvector + PostgreSQL only)
  ↓ requires database
  Ingestion Pipeline (extraction + PII strip + basic dedup)
  ↓ requires Knowledge Store
  Distribution Engine (simple: poll on approval)
  ↓ requires Knowledge Store
  Basic Web Dashboard (approval UI + knowledge feed)
  ↓ requires API + Approval Queue

Phase 2: Quality + Graph
  Graph Store (Neo4j/FalkorDB) added to Knowledge Store abstraction
  ↓ requires Phase 1 Knowledge Store interface to be clean
  Hybrid retrieval (vector + graph + RRF)
  ↓ requires Graph Store
  Real-time push (WebSocket/SSE fan-out, Redis pub/sub)
  ↓ requires Distribution Engine from Phase 1
  Quality scoring improvements (LLM-based, feedback loop)
  ↓ requires approval rejection data from Phase 1

Phase 3: B2B Packs
  Pack registry + versioning
  ↓ requires Knowledge Store namespace support (Phase 1)
  Pack curation tools
  ↓ requires Pack registry
  Waze flywheel (contribution attribution to packs)
  ↓ requires Pack registry + Ingestion Pipeline
  Pack billing (SaaS, no crypto required)
  ↓ requires Pack registry

Phase 4: Crypto Trading
  Agent wallets
  ↓ requires stable Pack System (Phase 3)
  x402 micropayment integration
  ↓ requires Agent wallets
  Dynamic pricing engine
  ↓ requires knowledge usage data (Phase 1+2)
  Knowledge trading marketplace
  ↓ requires x402 + pricing + Pack System
```

**Critical dependency:** The Approval Gate (Phase 1) is load-bearing for the entire trust model. If it is underbuilt — too slow, too opaque, or too hard to use — users will not allow contributions to the commons, and the entire system has nothing to trade, no packs to build, and no flywheel. The approval UX is as important as the ingestion pipeline itself.

---

## Sources

- AI Agent Memory Frameworks: A Deep Technical Comparison of Mem0, Graphiti, and Letta (deep_research PDF, 2025-2026) — HIGH confidence. Architecture of three dominant frameworks, storage backends, retrieval patterns, shared memory primitives, limitations.
- Cartographie du Knowledge Sharing Inter-Agents IA, Fevrier 2026 (deep_research PDF) — HIGH confidence. Ecosystem gap analysis, MCP ecosystem state, crypto knowledge trading landscape, B2B vertical pack market, "noisy commons" risk identification.
- OpenClaw en fevrier 2026 (deep_research PDF) — HIGH confidence. MCP ecosystem distribution context, skills security supply chain attack patterns (ClawHavoc), governance risks.
- MCP Specification 2025-11-25 (referenced in research) — HIGH confidence. Tasks, MCP Apps, Streamable HTTP transport, federation registry with .well-known URLs.
- arXiv 2505.18279 "Collaborative Memory" (referenced in research) — MEDIUM confidence (cited in research PDFs, not read directly). Validates private + shared selective memory architecture with immutable provenance and dynamic access controls.
- x402 Protocol (Coinbase, referenced in research) — MEDIUM confidence. Emerging micropayment standard for agent commerce; cited as the practical first target for agent-to-agent payments.

---
*Architecture research for: HiveMind — shared AI agent memory / knowledge commons*
*Researched: 2026-02-18*
