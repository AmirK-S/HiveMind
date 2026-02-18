# Stack Research

**Domain:** Shared AI agent memory / knowledge commons platform (MCP server + web dashboard + B2B knowledge packs + crypto trading layer)
**Researched:** 2026-02-18
**Confidence:** MEDIUM-HIGH (core memory layer HIGH, crypto/trading layer MEDIUM)

---

## Recommended Stack

### Layer 0 — MCP Protocol Layer (what agents plug into)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `mcp` (Python SDK) | `>=1.25,<2` | MCP server runtime for agent connections | Official Anthropic SDK, 97M monthly downloads in ecosystem, v1.x is production-stable; v2 planned Q1 2026 — pin to 1.x until v2 ships. Python chosen over TypeScript because the memory pipeline (Graphiti, Presidio, sentence-transformers) is entirely Python-native — mixing runtimes adds ops complexity with no benefit. |
| `fastmcp` | `>=2.0` | FastMCP layer on top of official SDK | Generates tool definitions automatically from Python type hints + docstrings. Cuts boilerplate 70%. Official SDK is lower-level; FastMCP is the de facto way to build production MCP servers fast. |

**What NOT to use:** Custom HTTP-over-stdio wrappers, hand-rolled JSON-RPC. The MCP SDK handles framing, transport negotiation, and capability advertisement — reimplementing this is waste.

---

### Layer 1 — Memory Engine (the core differentiator)

This is where the deep research is clearest: build on **Graphiti** as the collective memory substrate, not Mem0 or Letta.

**Decision rationale from the PDF research:**
- Mem0 has single-user assumption baked in. Its `OpenMemory` MCP layer is cross-tool but not cross-user public federation. Conflict resolution is LLM-driven black box.
- Letta's archival memory is not shareable between agents. Shared blocks are elegant but limited to in-context state. Last-writer-wins semantics break in high-concurrency multi-agent writes.
- Graphiti uses `group_id` as the native namespace for shared graphs. Multiple agents write to and read from the same `group_id`. Multi-namespace queries (`group_ids` list) work natively. Bi-temporal conflict resolution (latest valid edge wins) is automatic, deterministic, and doesn't require an LLM call at retrieval time.
- Graphiti retrieval requires no LLM call — BM25 + vector + graph traversal fused via RRF. Sub-200ms p99 per Zep Cloud benchmarks on Neo4j.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `graphiti-core` | `>=0.27.1` | Temporal knowledge graph engine | The only framework with native multi-agent shared graph semantics via `group_id`. Bi-temporal edge model provides automatic conflict resolution without LLM overhead. Retrieval is purely embedding + BM25 + graph traversal — no LLM call required, keeping latency deterministic. Apache 2.0. |
| `mem0ai` | `>=1.0.3` (optional) | Per-agent private memory complement | Use alongside Graphiti for agent-private episodic memory (the distilled-facts layer). Do NOT use as the collective memory backbone — its public federation is not supported. Only add if individual agent personalization is needed on top of the shared graph. |

**What NOT to use for collective memory:** Letta (archival not shareable), Mem0 alone (no cross-org public graph), custom vector DB + Redis hash map (reinvents what Graphiti already solves with bi-temporal graphs).

---

### Layer 2 — Storage Backends

Two storage tiers are required: graph storage for the knowledge structure, vector storage for semantic retrieval.

#### Graph Database

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **FalkorDB** | `>=4.x` (Redis-based) | Default graph backend for MCP deployments | Graphiti's recommended backend for MCP deployments (explicitly called out in the PDF research). Redis-based, so it co-locates with the existing Redis stack. Lighter operational footprint than Neo4j — no JVM, single Docker container. Supports RedisSearch for hybrid BM25 + vector retrieval on graph nodes/edges. `pip install graphiti-core[falkordb]`. |
| Neo4j | `>=5.26` (Python driver `neo4j>=6.1`) | Graph backend for scale-out deployments | Switch to Neo4j when graph exceeds ~10M edges or when enterprise features (RBAC, clustering) are needed. Primary/original Graphiti backend. Higher operational complexity: JVM, separate vector index management. Prefer FalkorDB for MVP and early production. |

**What NOT to use:** RedisGraph (officially EOL as of January 2025 — FalkorDB is the direct successor). Memgraph (less Graphiti-native support). AWS Neptune (requires separate OpenSearch for vector indexing per the PDF).

#### Vector Database (for Mem0 private layer and cross-encoder reranking)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Qdrant** | `qdrant-client>=1.16.1` | Pure vector search for agent-private memories | When using Mem0 as the per-agent private layer, Qdrant is the default and best-performing option: p99 <10ms, 4.5K QPS at 1M scale with HNSW+Rust. Superior pure vector performance to pgvector. Self-hosted via Docker, no managed dependency required. |
| **pgvector** (PostgreSQL extension) | `>=0.8.0` | Vector search co-located with relational data | Use pgvector (on PostgreSQL 16+) for the web dashboard metadata, B2B pack metadata, access control queries, and API key management. Co-locating vector search with relational data in a single SQL database simplifies multi-tenant access control logic. This mirrors Letta's production architecture. |

**Stack pattern:** FalkorDB for graph (Graphiti), Qdrant for pure vector (Mem0 private layer), PostgreSQL+pgvector for relational+metadata+dashboard.

---

### Layer 3 — PII Anonymization Pipeline

This is safety-critical infrastructure — knowledge contributed by agents must have PII stripped before entering the shared graph.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `presidio-analyzer` | `>=2.2.361` | PII detection engine | The 2025 anonymization research PDF establishes Presidio as the open-source standard. MIT license, modular architecture (AnalyzerEngine + RecognizerRegistry + NlpEngine). 50 native entity types. Free (infra cost only). Framework, not a black box — every recognizer is customizable. |
| `presidio-anonymizer` | `>=2.2.361` | PII transformation (replace/hash/encrypt) | Bundled with Presidio. Use `hash` (SHA-256/512 with salt) for irreversible scrubbing in the shared graph, `encrypt` (AES) for reversible deanonymization in audit logs. |
| `gliner` | `>=0.2.24` | Zero-shot NER for novel entity types | GLiNER (NAACL 2024, DeBERTa-v3 backbone) integrates natively with Presidio via `GLiNERRecognizer`. Critical for handling domain-specific PII types (crypto wallet addresses, proprietary system names) that Presidio's regex/NER recognizers miss. No retraining needed for new entity types — zero-shot via span matching. F1 60.9 OOD vs GPT-4o's 59.1. Use `knowledgator/gliner-pii-base-v1.0` (60+ PII categories, ONNX-optimized). |
| `spacy` | `>=3.8` | NLP engine for Presidio | Default Presidio NLP engine. 10,014 WPS on CPU — fast enough for inline agent contribution processing. Use `en_core_web_lg` model. Switch to HuggingFace Transformers engine (89.8+ F1) only if false-positive rate on person name detection is unacceptable in production. |

**What NOT to use for PII:**
- Amazon Comprehend PII: English+Spanish only, no custom entity types, no advanced transforms. Eliminates multilingual B2B packs.
- Google Cloud DLP: Best feature set but $1-3/GB pricing at scale will erode margins on a knowledge commons. Use only if a B2B vertical explicitly requires regulatory-grade transforms (FPE, crypto deterministic).
- Vanilla Presidio without GLiNER: The PDF research is explicit — "vanilla Presidio results aren't very accurate" (their own docs say this). F1 drops to ~0.60 on health domain. GLiNER as a fallback recognizer brings it to production-viable accuracy.

---

### Layer 4 — Embedding Models

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `BAAI/bge-m3` (via `FlagEmbedding>=1.3.5` or `sentence-transformers>=5.2.2`) | Model: current HF checkpoint | Primary embedding model for self-hosted deployments | MIT license, 1024 dimensions, 100+ languages, 8192 token context. Supports dense + sparse + multi-vector retrieval simultaneously — uniquely suited for Graphiti's hybrid BM25+vector retrieval. The PDF research identifies this as "the strongest open-source embedding model for self-hosted deployments." |
| `text-embedding-3-small` (OpenAI API) | API | Embedding model for API-based deployments / B2B packs | $0.02/M tokens. Best cost/performance ratio when self-hosting GPU is cost-prohibitive. 1536 dimensions. Use for B2B pack customers who want managed inference. Pin embedding model at graph creation time — changing it requires full re-embedding (destructive operation per Letta's architecture note). |
| `BAAI/bge-reranker-v2-m3` | Current HF checkpoint | Cross-encoder reranking for search quality | Use as a reranker on top of initial BM25+vector retrieval. Graphiti's RRF handles first-pass fusion; this reranker improves precision for complex queries. Load via sentence-transformers. |

**What NOT to use:** OpenAI `text-embedding-ada-002` (deprecated, superseded by text-embedding-3-small with better performance at lower cost). Mixing embedding models within a single graph namespace (requires full re-embedding — operationally dangerous).

---

### Layer 5 — API Backend

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `fastapi` | `>=0.129.0` | REST API for web dashboard, B2B pack endpoints, admin | The de facto standard for Python async REST APIs in the AI infrastructure space. Native async/await, Pydantic v2 validation, OpenAPI generation. Used by Mem0's self-hosted server (`mem0-server`) on port 8080 with SSE support — same pattern applies here. Avoids a Node.js service just for HTTP. |
| `uvicorn` | `>=0.34` | ASGI server | Production-grade ASGI server for FastAPI. Use with `--workers` for multi-process on CPU-bound routes. |
| `pydantic` | `>=2.10` | Data validation and serialization | FastAPI's validation layer. Pydantic v2 is 5-50x faster than v1 (Rust core). Use for all MCP tool input/output schemas and API request/response models. |
| `celery` | `>=5.4` | Async task queue for knowledge ingestion pipeline | Graphiti's ingestion pipeline makes multiple LLM calls per episode — it's inherently async and slow (minutes for complex data). Celery with Redis broker decouples agent submissions from graph writes. Standard Python async task queue in 2026. Use `celery[redis]`. |
| `redis` | `>=5.2` (Python client) | Celery broker + pub/sub for live dashboard events | Already required by FalkorDB. Double-use as Celery broker and WebSocket event bus for the live dashboard. Redis Streams (not bare pub/sub) for reliable event delivery with consumer groups. |

---

### Layer 6 — Web Dashboard

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Next.js | `>=15.x` (v16 available but 15 is stable LTS) | Web dashboard frontend | React-based, App Router, SSR + client components. Standard for AI infrastructure dashboards in 2026. Turbopack dev is stable in v15. Use Next.js 15 over 16 until 16 has wider ecosystem adoption. |
| TypeScript | `>=5.7` | Type safety across frontend | Mandatory for any production dashboard — catches API contract mismatches before runtime. |
| Drizzle ORM | `>=0.39` | Database ORM for dashboard PostgreSQL queries | Chosen over Prisma 7 for this use case: no code-gen step, SQL-transparent, zero runtime dependencies (~7.4kb). Excellent for serverless/edge-deployed dashboard components. Prisma 7 eliminated the Rust engine but still requires the generation step — Drizzle's feedback loop is tighter for iterative dashboard development. |
| `shadcn/ui` | Current | Component library | Unstyled, copy-paste component system built on Radix UI + Tailwind. No vendor lock-in, full customizability. Standard for developer-facing dashboards in 2026. |
| Recharts or Tremor | `>=2.x` | Real-time knowledge graph metrics visualization | Recharts for custom D3-style charts, Tremor for rapid dashboard components. Use Tremor for time-series memory ingestion metrics (pre-built), Recharts for custom graph topology visualization. |

---

### Layer 7 — Crypto / Agent-to-Agent Trading Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| x402 protocol (Coinbase SDK) | TypeScript SDK (current) / Go SDK | Agent-to-agent micropayments for knowledge pack access | x402 is the 2026 standard for machine-to-machine HTTP payments. Built on HTTP 402 status code. Coinbase CDP facilitator handles settlement on Base (EVM) and Solana. 35M+ transactions, $10M+ volume since launch. Solana's $0.00025/tx and 400ms finality make it the preferred settlement layer for high-frequency agent-to-agent knowledge trades. Free tier: 1,000 tx/month. |
| Solana web3.js / `@solana/web3.js` | `>=2.x` | Solana on-chain transactions for high-frequency settlement | Solana accounts for 77% of x402 transaction volume (Dec 2025). Use for the knowledge marketplace settlement layer. Base (EVM via x402) as fallback for B2B clients with EVM wallet infrastructure. |
| Privy or Crossmint | Current SDK | Embedded agent wallets | Agents need programmatic wallets to pay for knowledge. Privy unveiled embedded wallet infrastructure for autonomous AI agents (lobster.cash on Solana, built by Crossmint). Use Privy for custodial agent wallets with owner override capability; Crossmint for non-custodial. |

**What NOT to use for crypto layer:** Building custom payment settlement — x402 + CDP facilitator handles this. Rolling custom Solana programs — the x402 SDK abstracts the on-chain complexity. Ethereum mainnet for micropayments — gas costs make it non-viable for knowledge trades under $1.

---

### Layer 8 — Infrastructure and DevOps

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Docker Compose | V2 | Local development and single-node deployment | Graphiti ships with official Docker Compose configs for FalkorDB and Neo4j. Mem0's `OpenMemory` MCP uses Docker Compose (FastAPI + Postgres + Qdrant). Match this pattern for zero-friction developer onboarding. |
| PostgreSQL | `>=16` | Relational data: API keys, B2B orgs, billing, audit logs | Stable, proven. pgvector requires PostgreSQL 11+ (prefer 16 for performance improvements). Co-locate with pgvector for dashboard metadata. |
| Prometheus + Grafana | Current stable | Metrics and observability | Standard open-source observability stack. Export memory ingestion latency, graph write throughput, PII detection hit rates, x402 payment success rates. |

---

## Alternatives Considered

| Recommended | Alternative | Why Alternative Loses |
|-------------|-------------|----------------------|
| Graphiti (collective memory) | Mem0 alone | Mem0 has no cross-org public federation; `OpenMemory` is cross-tool for one user, not cross-user collective memory. Single-user assumption is architectural, not a feature gap. |
| Graphiti (collective memory) | Letta | Letta's archival memory is per-agent, not shareable. Shared blocks are in-context only. Last-writer-wins breaks concurrent multi-agent writes at scale. |
| FalkorDB | Neo4j (for MVP) | FalkorDB has equal Graphiti support, lighter footprint (no JVM), Redis-native (already in stack). Switch to Neo4j at scale when clustering/RBAC needed. |
| Qdrant | pgvector (for vector-only queries) | Qdrant's p99 <10ms at 1M scale vs pgvector's ~10-50ms. For the high-frequency agent memory search path, pure vector performance matters. pgvector is used for dashboard metadata, not the hot search path. |
| GLiNER + Presidio | Google Cloud DLP | DLP pricing ($1-3/GB) is prohibitive at knowledge-commons scale. Presidio + GLiNER is free (infra cost only) with comparable accuracy after tuning. |
| FastAPI (Python) | Express/Node.js | Memory pipeline is Python-native (Graphiti, Presidio, sentence-transformers). Single runtime eliminates cross-language IPC complexity. FastAPI's async performance is sufficient for API serving. |
| Celery + Redis | Temporal | Temporal provides better workflow visibility and stateful agents but requires rearchitecting the application around Temporal workers and clients — high initial overhead. Celery covers the knowledge ingestion async requirement with lower operational complexity. Revisit Temporal if multi-step agent orchestration becomes core product functionality. |
| x402 | Custom smart contract | x402 is an open standard with Coinbase CDP facilitator handling settlement. Custom contracts require auditing, maintenance, and chain-specific integrations. x402 handles Base + Solana + multi-EVM out of the box. |
| Next.js 15 | SvelteKit | Next.js has larger ecosystem for dashboard component libraries (shadcn, Tremor) and more developer familiarity. For AI infrastructure dashboards, Next.js is the near-universal choice in 2026. |
| Drizzle ORM | Prisma 7 | Prisma 7 eliminated the Rust engine but still has a code-gen step. Drizzle is SQL-transparent, ~7.4kb, and has no gen step — better DX for iterative dashboard development. Both are production-viable; Drizzle is recommended for this use case. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| RedisGraph | Officially EOL January 2025. No security patches. | FalkorDB (direct successor, binary-compatible) |
| Zep Community Edition | Deprecated — sits in `legacy/` folder on GitHub. Contributors must sign Zep's CLA for the commercial product. | `graphiti-core` directly (the open-source engine that powers Zep) |
| Vanilla Presidio (no GLiNER) | F1 ~0.60 on health domain. Microsoft's own docs warn results "aren't very accurate." False-negative rate on person names is the recurring failure mode. | Presidio + GLiNER (`GLiNERRecognizer`) combination |
| `text-embedding-ada-002` | Deprecated by OpenAI. Superseded by `text-embedding-3-small` with better performance at lower cost. | `text-embedding-3-small` for API, `bge-m3` for self-hosted |
| Ethereum mainnet for micropayments | Gas fees make sub-$1 knowledge trades non-viable. | Solana via x402 ($0.00025/tx, 400ms finality) |
| LangChain as a core dependency | LangChain adds abstraction overhead and version churn that has repeatedly broken dependent projects. Graphiti, Mem0, and Presidio all integrate directly with LLM APIs. | Direct LLM API calls (Anthropic SDK, OpenAI SDK) + Graphiti natively |
| Pinecone (managed vector only) | Vendor lock-in, egress costs, no self-hosted option. Qdrant is self-hostable with equivalent performance. | Qdrant (self-hosted Docker) |
| Raw pub/sub (Redis bare pub/sub) | No message persistence. If a dashboard consumer disconnects, events are lost. | Redis Streams with consumer groups for reliable event delivery |

---

## Stack Patterns by Variant

**If deploying open-source core (self-hosted):**
- Full stack as specified: FalkorDB + Qdrant + PostgreSQL + Celery + FastAPI + MCP Python SDK
- Docker Compose for single-node, FalkorDB handles graph + vector adjacency
- `BAAI/bge-m3` self-hosted for embeddings — no per-token API cost

**If deploying managed/cloud (B2B SaaS tier):**
- Swap FalkorDB → Neo4j AuraDB (managed) for enterprise SLA
- Swap `bge-m3` → `text-embedding-3-small` API (no GPU infra needed)
- Add Google Cloud DLP alongside Presidio for regulatory compliance (healthcare/finance verticals)
- x402 payments on Base for EVM-native enterprise customers, Solana for crypto-native customers

**If MCP server language is TypeScript (alternative path):**
- Use `@modelcontextprotocol/sdk` TypeScript SDK (v1.x, v2 in Q1 2026)
- All memory pipeline work must be Python microservice behind the TypeScript MCP server
- This adds a service boundary — only justified if team is TypeScript-primary
- Recommendation: stay Python unless team composition demands TypeScript

**If PII requirements are French/multilingual:**
- Presidio has no native French recognizers. Add `Flair ner-french` (F1 90.61) via custom Presidio recognizer
- `CamemBERT-NER` (F1 89.14) as alternative
- GLiNER handles multilingual zero-shot — works cross-language without retraining

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `graphiti-core>=0.27.1` | Python `>=3.10,<4` | Requires structured output support from LLM — use GPT-4o, Claude 3.5+, or Gemini 1.5+. Not compatible with models lacking tool-use/structured output. |
| `mcp>=1.25,<2` | Python `>=3.10` | Pin below v2 — v2 API changes expected Q1 2026. Migration guide will be published. |
| `presidio-analyzer>=2.2.361` | spaCy `>=3.8` | `en_core_web_lg` required (not sm). The hash operator uses random salt by default since v2.2.361 — upgrade if on older version for consistent hashing. |
| `gliner>=0.2.24` | Integrates with Presidio via `GLiNERRecognizer` | Use ONNX-optimized model (`knowledgator/gliner-pii-base-v1.0`) for CPU inference speed. |
| `fastapi>=0.129.0` | `pydantic>=2.10`, `uvicorn>=0.34` | FastAPI 0.129+ requires Pydantic v2. Do not mix with Pydantic v1 models. |
| `graphiti-core[falkordb]` | FalkorDB requires Redis 7.4+ | Use `falkordblite>=0.8.0` for the Python client. |
| `neo4j>=6.1` (if using Neo4j backend) | Neo4j Server `>=5.26` | `neo4j-driver` package name is deprecated — install `neo4j` (drop-in replacement). |
| `sentence-transformers>=5.2.2` | `transformers>=4.41`, `torch>=2.0` | For `bge-m3` inference via sentence-transformers. Alternatively use `FlagEmbedding>=1.3.5` for the BAAI-native interface. |
| Next.js `15.x` | React `>=19` (App Router), React `18` (Pages Router) | App Router requires React 19. Do not mix App Router + React 18 — use Pages Router if staying on React 18. |
| Drizzle ORM `>=0.39` | PostgreSQL `>=16` via `pg` or `postgres` driver | Works with `@neondatabase/serverless` for serverless Postgres. |

---

## Installation

```bash
# === MCP Server (Python) ===
pip install "mcp>=1.25,<2" fastmcp

# === Memory Engine ===
pip install "graphiti-core[falkordb]>=0.27.1"
# OR for Neo4j backend:
pip install "graphiti-core[neo4j]>=0.27.1"

# Optional per-agent private memory
pip install "mem0ai>=1.0.3"

# === PII Anonymization ===
pip install "presidio-analyzer>=2.2.361" "presidio-anonymizer>=2.2.361"
pip install "gliner>=0.2.24"
python -m spacy download en_core_web_lg

# === Embeddings ===
pip install "sentence-transformers>=5.2.2"
# OR BAAI native interface:
pip install "FlagEmbedding>=1.3.5"

# === API Backend ===
pip install "fastapi>=0.129.0" "uvicorn[standard]>=0.34" "pydantic>=2.10"
pip install "celery[redis]>=5.4" "redis>=5.2"

# === Vector DB client (for Mem0/Qdrant) ===
pip install "qdrant-client>=1.16.1"

# === Web Dashboard (Node.js) ===
npx create-next-app@15 --typescript
npm install drizzle-orm postgres
npm install -D drizzle-kit
npm install @shadcn/ui recharts

# === Crypto Layer ===
npm install x402                      # Coinbase x402 TypeScript SDK
npm install @solana/web3.js@2         # Solana transactions
# OR Python x402 if keeping single runtime (Go SDK also available)
```

---

## Sources

- graphiti-core PyPI (verified Feb 2026): https://pypi.org/project/graphiti-core/ — version 0.27.1, Python >=3.10
- MCP Python SDK PyPI: https://pypi.org/project/mcp/ — v1.25 current stable, v2 planned Q1 2026; GitHub: https://github.com/modelcontextprotocol/python-sdk
- mem0ai PyPI: https://pypi.org/project/mem0ai/ — v1.0.3 current
- qdrant-client PyPI: https://pypi.org/project/qdrant-client/ — v1.16.1 current
- FastAPI PyPI: https://pypi.org/project/fastapi/ — v0.129.0 (Feb 12, 2026)
- Neo4j Python driver: https://neo4j.com/docs/api/python-driver/current/ — v6.1; install `neo4j` not deprecated `neo4j-driver`
- Presidio GitHub: https://github.com/microsoft/presidio — presidio-anonymizer current (Feb 2026)
- GLiNER PyPI: https://pypi.org/project/gliner/ — v0.2.24; PII model: https://huggingface.co/knowledgator/gliner-pii-base-v1.0
- sentence-transformers PyPI: https://pypi.org/project/sentence-transformers/ — v5.2.2 (Jan 27, 2026)
- FlagEmbedding PyPI: https://pypi.org/project/FlagEmbedding/ — v1.3.5
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- pgvector releases: https://github.com/pgvector/pgvector/releases — v0.8.0 current
- FalkorDB: https://github.com/FalkorDB/FalkorDB — Redis 7.4+ required; MCP integration: https://www.falkordb.com/blog/mcp-integration-falkordb-graphrag/
- x402 protocol: https://www.x402.org/ — Coinbase CDP: https://docs.cdp.coinbase.com/x402/welcome; GitHub: https://github.com/coinbase/x402
- Solana x402: https://solana.com/x402/what-is-x402 — 77% of x402 volume, $0.00025/tx, 400ms finality
- BullMQ npm: https://www.npmjs.com/package/bullmq — v5.69.3 (Feb 16, 2026)
- Prisma 7: https://www.prisma.io/blog/announcing-prisma-orm-7-0-0 — Rust-free client
- Next.js 15: https://nextjs.org/blog/next-15 — stable; v16 available
- PDF research 1: "AI Agent Memory Frameworks: A Deep Technical Comparison of Mem0, Graphiti, and Letta" — HIGH confidence source for memory layer architecture decisions
- PDF research 2: "The Open-Source AI Virality Playbook: Launching into the OpenClaw and MCP Ecosystems" — MEDIUM confidence for MCP ecosystem context
- PDF research 3: "Anonymisation automatique des données LLM: état de l'art technique 2025" — HIGH confidence for PII stack decisions

---

*Stack research for: HiveMind — shared AI agent memory/knowledge commons platform*
*Researched: 2026-02-18*
