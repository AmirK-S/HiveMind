# Phase 1: Agent Connection Loop - Research

**Researched:** 2026-02-18
**Domain:** MCP server (Streamable HTTP), PII pipeline (Presidio + GLiNER), PostgreSQL/pgvector, async FastAPI, CLI approval workflow
**Confidence:** HIGH (core stack verified against official docs and Context7/official sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Approval experience
- CLI-based approval in Phase 1 (web dashboard comes in Phase 4)
- Async flow: agent contributes and moves on, contribution queued for user review
- User reviews pending contributions via CLI command
- Approval feel is positive and rewarding — no scary PII warnings, just clean content
- Light gamification: contribution count, "You've helped X agents" style messages on approval
- User can override agent-suggested category during approval
- "Flag as sensitive" button available if PII stripping missed something

#### Knowledge structure
- Multiple knowledge types with categories: solutions, patterns, config snippets, explanations, etc.
- Agent suggests a category on contribution; user can override during approval
- Rich metadata: source language/framework, tags, confidence level — BUT no project-specific info (no file paths, repo names, project structure)
- Timestamps on everything (no decay in Phase 1, but data foundation for future freshness scoring)
- Privacy guardrail: metadata must not reveal what someone is specifically building

#### Search & retrieval
- Preview-first (like Google search snippets): agent gets summaries, requests full content for specific items
- Result count: Claude's discretion (sensible default with pagination)
- Show contributor org attribution on results
- Both private org namespace AND public commons available from Phase 1
- When knowledge is approved, it goes to private namespace, public commons, or both

#### PII stripping behavior
- Strip silently — user only sees clean version, no before/after comparison
- PII stripping happens BEFORE quarantine — PII never stored, not even in pending queue
- Universal PII first: emails, phone numbers, names, addresses (French-specific identifiers deferred)
- API keys, tokens, passwords, connection strings treated as PII — always stripped
- Code snippets stripped too — safety first, even for test data
- Auto-reject if stripping removes >50% of content (don't pollute commons with redacted gibberish)
- Placeholders: typed tags (`[EMAIL]`, `[PHONE]`, `[API_KEY]`) when type is confident, `[REDACTED]` as fallback

### Claude's Discretion
- Default search result count and pagination design
- Exact gamification copy and contribution stats format
- Loading/error states in CLI approval flow
- Knowledge schema field names and validation rules
- Quarantine queue storage and ordering
- MCP tool parameter design and response shapes

### Deferred Ideas (OUT OF SCOPE)
- French-specific PII identifiers (SIRET, SIREN, NIR) — Phase 2 or later
- Web dashboard for approval — Phase 4
- Knowledge decay/freshness scoring — Phase 3
- Advanced PII stripping improvements from "flag as sensitive" feedback loop — Phase 2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-01 | Agent connects via MCP (Streamable HTTP transport per spec 2025-11-25) | FastMCP v2 with `create_streamable_http_app()` or `mcp.run(transport="streamable-http")`; MCP spec 2025-03-26 transport doc is authoritative (latest stable spec) |
| MCP-02 | Agent contributes via `add_knowledge` tool | FastMCP `@mcp.tool()` decorator pattern; async tool support confirmed; Pydantic v2 input validation |
| MCP-03 | Agent searches via `search_knowledge` with tiered response (summary → full) | pgvector cosine similarity + full-text GIN index hybrid; pagination via cursor; tiered response is a custom field design (discretion area) |
| MCP-04 | Agent lists contributions via `list_knowledge` | Standard SQLAlchemy async query filtered by `source_agent_id + org_id`; MCP tool pattern |
| MCP-05 | Agent deletes contributions via `delete_knowledge` with cascade | PostgreSQL CASCADE on FK constraints handles derived items; soft-delete pattern recommended for auditability |
| TRUST-01 | All inbound knowledge PII-stripped before storage (Presidio + GLiNER + API secrets + private URL detection) | Presidio `AnalyzerEngine` + `AnonymizerEngine`; GLiNERRecognizer with `knowledgator/gliner-pii-base-v1.0`; custom PatternRecognizer for API keys; pipeline runs before any DB write |
| TRUST-02 | User notified when agent proposes knowledge contribution | CLI `hivemind review` command displays pending queue; Celery/Redis handles async decoupling |
| TRUST-03 | User can approve/reject each contribution before commons entry | CLI workflow with `questionary`/`rich`; approval writes to `knowledge_items`, rejection deletes from `pending_contributions` |
| ACL-01 | Each org has isolated namespace | `org_id` column on all tables; all queries filter by org_id extracted from JWT claim or API key; no cross-org data leakage in query layer |
| KM-01 | Immutable provenance: source_agent_id, contributed_at, category, org_id, confidence_score, run_id, content_hash | SQLAlchemy model with `created_at` auto-set, `content_hash` as SHA-256 of original (pre-strip) content identity; columns set on insert, never updated |
| KM-04 | Knowledge typed by category with framework/library version metadata | Enum for category field in SQLAlchemy model; optional `framework`, `language`, `version` columns; Pydantic v2 validation on input |
| KM-08 | Embedding model pinned at deployment; abstraction layer decouples storage from model version | `sentence-transformers` model loaded once at startup; model name + commit hash stored in deployment config table; `EmbeddingProvider` abstraction class wraps the model |
| INFRA-01 | PostgreSQL + pgvector as primary store | `asyncpg` driver + SQLAlchemy 2 async engine; `pgvector-python` for vector column type and HNSW index; Alembic for migrations |
| INFRA-05 | Concurrent multi-agent writes handled safely | `FOR UPDATE SKIP LOCKED` for quarantine queue processing; PostgreSQL row-level locking handles concurrent inserts naturally; async connection pool via `AsyncAdaptedQueuePool` |
</phase_requirements>

---

## Summary

Phase 1 builds a complete MCP server loop: agents connect via Streamable HTTP, contribute knowledge that is PII-stripped and queued, and users approve via CLI before knowledge enters the searchable commons. The technical stack is well-established and all components have stable Python libraries with official documentation.

The three main implementation challenges are (1) the Celery/asyncio boundary — Celery workers are synchronous by nature but the FastAPI MCP server is async, requiring careful bridging; (2) the PII pipeline accuracy trade-off — GLiNER + Presidio together achieve ~81% F1 on PII detection, so the "flag as sensitive" escape hatch in the CLI is genuinely important; and (3) the 50% auto-reject threshold, which has no built-in Presidio support and must be calculated as a ratio of `[REDACTED]`-token count to original token count post-anonymization.

The embedding model abstraction (KM-08) is a day-one concern: once vectors are stored against a specific model's embedding space, changing models requires re-embedding everything. Pin the model at initialization and store the model identifier in a `deployment_config` table so migrations can detect version changes.

**Primary recommendation:** Use FastMCP v2 (not v3 RC) for the MCP server, Presidio + GLiNER for PII stripping with custom API-key PatternRecognizers, pgvector/asyncpg/SQLAlchemy 2 for storage, Celery + Redis for the async contribution pipeline, and Typer + Rich for the CLI approval workflow.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastmcp` | `<3` (v2 stable) | MCP server framework with Streamable HTTP | Powers ~70% of all MCP servers; incorporates into official SDK; `@mcp.tool()` decorator pattern eliminates boilerplate |
| `mcp` | latest v1.x | Official MCP Python SDK (FastMCP depends on it) | Reference implementation from Anthropic/protocol authors |
| `fastapi` | latest | HTTP server underlying FastMCP; also used for health endpoints | FastMCP integrates directly via `create_streamable_http_app()`; async support built-in |
| `uvicorn` | latest | ASGI server to run FastAPI/FastMCP | Standard for FastAPI production deployments |
| `sqlalchemy` | 2.x | Async ORM for PostgreSQL | SQLAlchemy 2 async support is mature; `AsyncSession` + `create_async_engine` well-documented |
| `asyncpg` | `<0.29.0` | Async PostgreSQL driver | **Pin below 0.29.0** — known issues with SQLAlchemy `create_async_engine` above this version |
| `pgvector` | latest | pgvector Python adapter (vector columns + HNSW index in SQLAlchemy) | Official pgvector Python library; supports `VECTOR`, `HALFVEC`, `SPARSEVEC` types and all distance operators |
| `alembic` | latest | Database migrations | Standard for SQLAlchemy projects; handles pgvector custom type registration in `env.py` |
| `presidio-analyzer` | latest | PII detection engine (orchestrator) | Microsoft-backed; GLiNER plugin available via `presidio-analyzer[gliner]` extra |
| `presidio-anonymizer` | latest | PII replacement/redaction | Paired with analyzer; supports typed placeholders `[EMAIL]`, `[PHONE]` etc. |
| `gliner` | latest | GLiNER model inference | Required for `knowledgator/gliner-pii-base-v1.0` model |
| `sentence-transformers` | latest | Embedding generation | `all-MiniLM-L6-v2` (384-dim, 22MB) for Phase 1; model pinned by name + HuggingFace commit hash |
| `celery` | 5.x | Async task queue for PII pipeline and contribution processing | Mature; Redis broker + Postgres result backend pattern is standard for this stack |
| `redis` | latest | Celery broker | Fastest transport for small messages; acceptable for contribution pipeline volume |
| `pydantic` | v2 | Request/response validation, knowledge item schemas | FastAPI and FastMCP use Pydantic v2 natively |
| `typer` | latest | CLI framework for `hivemind review` command | FastAPI-family project; rich integration built-in |
| `rich` | latest | Terminal formatting for CLI approval workflow | Used by Typer; `Table`, `Panel`, `Prompt` cover all approval UI needs |
| `questionary` | latest | Interactive prompts for approval/rejection/category override | Built on Prompt Toolkit; cleaner multi-choice UX than raw `rich.Prompt` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `spacy` | latest + `en_core_web_sm` | Lightweight NLP engine required by Presidio | Required as Presidio's NLP backend even when using GLiNER recognizer |
| `python-jose` | latest | JWT parsing for org_id extraction from bearer tokens | Used server-side to decode agent auth tokens and extract org claims |
| `hashlib` | stdlib | SHA-256 content hashing for KM-01 provenance | Built into Python stdlib; no install needed |
| `httpx` | latest | Async HTTP client (FastMCP client uses it) | Used in tests and potentially in CLI health checks |
| `pytest-asyncio` | latest | Async test support | Required for testing async FastAPI/SQLAlchemy code |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastMCP v2 | Raw `mcp` SDK | Raw SDK requires manual JSON-RPC handling, schema generation, lifecycle management — no benefit |
| FastMCP v2 | FastMCP v3 RC | v3 is release candidate as of Feb 2026; breaking changes possible; stick with v2 for Phase 1 stability |
| Celery + Redis | Background asyncio tasks | Asyncio tasks don't survive server restarts; Celery provides durability for the contribution queue |
| Celery + Redis | PostgreSQL `FOR UPDATE SKIP LOCKED` as queue | Valid alternative — avoids Redis dependency — but Celery provides retry, monitoring, and worker scaling out of the box |
| `asyncpg` | `psycopg3` async | Both work; asyncpg is more widely used with SQLAlchemy 2 in tutorials; psycopg3 is newer but less example coverage |
| `sentence-transformers/all-MiniLM-L6-v2` | OpenAI `text-embedding-3-small` | Self-hosted is required for privacy (no knowledge leaves the server); OpenAI suitable only if user opts into cloud embeddings |
| `questionary` | `rich.Prompt` | `rich.Prompt` is fine for y/n but `questionary` provides select lists for category override without boilerplate |

**Installation:**

```bash
pip install "fastmcp<3" fastapi uvicorn sqlalchemy asyncpg "asyncpg<0.29.0" pgvector alembic \
  "presidio-analyzer[gliner]" presidio-anonymizer gliner \
  sentence-transformers celery redis \
  pydantic typer rich questionary \
  spacy python-jose httpx

python -m spacy download en_core_web_sm
```

---

## Architecture Patterns

### Recommended Project Structure

```
hivemind/
├── server/
│   ├── main.py              # FastMCP app + uvicorn entrypoint
│   ├── tools/
│   │   ├── add_knowledge.py    # MCP-02
│   │   ├── search_knowledge.py # MCP-03
│   │   ├── list_knowledge.py   # MCP-04
│   │   └── delete_knowledge.py # MCP-05
│   └── auth.py              # Bearer token / API key extraction → org_id
├── pipeline/
│   ├── pii.py               # Presidio + GLiNER anonymizer
│   ├── embedder.py          # EmbeddingProvider abstraction (KM-08)
│   └── tasks.py             # Celery task definitions
├── db/
│   ├── models.py            # SQLAlchemy ORM models
│   ├── session.py           # Async engine + session factory
│   └── migrations/          # Alembic migration scripts
├── cli/
│   └── review.py            # `hivemind review` command (Typer + Rich)
└── config.py                # Settings (Pydantic BaseSettings)
```

### Pattern 1: FastMCP Streamable HTTP Server

**What:** FastMCP wraps Python functions as MCP tools, served over HTTP. Agents POST to a single `/mcp` endpoint.
**When to use:** All MCP tool implementations follow this pattern.

```python
# Source: https://gofastmcp.com/python-sdk/fastmcp-server-http
from fastmcp import FastMCP
from fastmcp.server.http import create_streamable_http_app

mcp = FastMCP("HiveMind")

@mcp.tool()
async def add_knowledge(
    content: str,
    category: str,
    confidence: float = 0.8,
    framework: str | None = None,
    language: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Contribute a piece of knowledge to HiveMind commons."""
    # PII strip → quarantine → return contribution_id
    ...

# For production: stateless_http=True for horizontal scaling
app = create_streamable_http_app(
    server=mcp,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)
# uvicorn hivemind.server.main:app --host 0.0.0.0 --port 8000
```

### Pattern 2: MCP Tool Response (Tiered / isError)

**What:** MCP tools return `dict` (auto-wrapped) or explicit `CallToolResult`. Errors use `isError: true`.
**When to use:** All five MCP tools.

```python
# Source: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
# Tool execution error (not protocol error) — use isError in content
from mcp.types import CallToolResult, TextContent

# Success — FastMCP auto-wraps dict to TextContent
return {"contribution_id": str(uuid), "status": "queued", "category": category}

# Error — set isError; LLM receives descriptive message not stack trace
return CallToolResult(
    content=[TextContent(type="text", text="Rejected: content too short after PII stripping")],
    isError=True,
)
```

### Pattern 3: Tiered Search Response

**What:** `search_knowledge` returns summaries by default; agent requests full content by ID.
**When to use:** MCP-03. Prevents token explosion when commons has thousands of items.

```python
# Summary tier: ~30-50 tokens per result
{
  "results": [
    {
      "id": "uuid",
      "title": "...",          # first ~80 chars of content
      "category": "bug_fix",
      "confidence": 0.9,
      "org_attribution": "acme-corp",
      "relevance_score": 0.87
    }
  ],
  "next_cursor": "...",
  "total_found": 42
}

# Full tier: agent calls search_knowledge(id="uuid", full_content=True)
{
  "id": "uuid",
  "content": "...",            # full content
  "metadata": { ... }
}
```

### Pattern 4: PII Pipeline (TRUST-01)

**What:** Multi-layer PII stripping runs synchronously before any DB write. Never touches the original in storage.
**When to use:** All inbound `add_knowledge` calls, before queuing.

```python
# Source: https://microsoft.github.io/presidio/samples/python/gliner/
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.predefined_recognizers import GLiNERRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import re, hashlib

# --- Setup (once at startup) ---
analyzer = AnalyzerEngine()

# GLiNER for zero-shot NER (names, addresses, IDs, health data, etc.)
gliner = GLiNERRecognizer(
    model_name="knowledgator/gliner-pii-base-v1.0",
    entity_mapping={
        "name": "PERSON", "email address": "EMAIL_ADDRESS",
        "phone number": "PHONE_NUMBER", "location address": "LOCATION",
        "password": "PASSWORD", "username": "USERNAME",
        # ... map all 60+ GLiNER entities to Presidio entity types
    },
    flat_ner=False, multi_label=True, map_location="cpu"
)
analyzer.registry.add_recognizer(gliner)

# Custom recognizer for API keys / tokens (regex-based)
api_key_patterns = [
    Pattern("aws_key", r"AKIA[0-9A-Z]{16}", 0.9),
    Pattern("github_token", r"ghp_[A-Za-z0-9]{36}", 0.9),
    Pattern("jwt", r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", 0.85),
    Pattern("generic_secret", r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S+", 0.7),
]
analyzer.registry.add_recognizer(
    PatternRecognizer(supported_entity="API_KEY", patterns=api_key_patterns)
)

anonymizer = AnonymizerEngine()

# Operator map: typed placeholders for high-confidence entities, [REDACTED] fallback
OPERATORS = {
    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
    "PERSON": OperatorConfig("replace", {"new_value": "[NAME]"}),
    "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
    "API_KEY": OperatorConfig("replace", {"new_value": "[API_KEY]"}),
    "PASSWORD": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
    "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
}

# --- Runtime ---
def strip_pii(text: str) -> tuple[str, bool]:
    """Returns (cleaned_text, should_reject).
    should_reject=True if >50% of content was redacted.
    """
    results = analyzer.analyze(text=text, language="en")
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=OPERATORS)
    cleaned = anonymized.text

    # 50% rejection check: count placeholder tokens vs total tokens
    placeholder_count = len(re.findall(r'\[(?:EMAIL|PHONE|NAME|LOCATION|API_KEY|REDACTED)\]', cleaned))
    total_tokens = max(len(cleaned.split()), 1)
    redacted_ratio = placeholder_count / total_tokens
    should_reject = redacted_ratio > 0.50

    return cleaned, should_reject
```

### Pattern 5: SQLAlchemy Models with pgvector

**What:** ORM models for `pending_contributions` and `knowledge_items` tables. Vector column for embeddings.
**When to use:** INFRA-01, KM-01.

```python
# Source: https://github.com/pgvector/pgvector-python
from sqlalchemy import String, Float, DateTime, Enum, Index, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import VECTOR
import uuid, datetime, enum

class KnowledgeCategory(str, enum.Enum):
    bug_fix = "bug_fix"
    config = "config"
    domain_expertise = "domain_expertise"
    workaround = "workaround"
    tooling = "tooling"
    reasoning_trace = "reasoning_trace"
    failed_approach = "failed_approach"
    version_workaround = "version_workaround"
    general = "general"

class Base(DeclarativeBase):
    pass

class PendingContribution(Base):
    __tablename__ = "pending_contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)  # already PII-stripped
    category: Mapped[KnowledgeCategory] = mapped_column(Enum(KnowledgeCategory), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    framework: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[list | None] = mapped_column(JSONB)
    contributed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    is_sensitive_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # True = public commons
    source_agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # SHA-256
    category: Mapped[KnowledgeCategory] = mapped_column(Enum(KnowledgeCategory), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    framework: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[list | None] = mapped_column(JSONB)
    embedding: Mapped[list | None] = mapped_column(VECTOR(384))  # all-MiniLM-L6-v2 dims
    contributed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    # HNSW index for cosine similarity search
    __table_args__ = (
        Index(
            "ix_knowledge_items_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
```

### Pattern 6: Quarantine Queue with FOR UPDATE SKIP LOCKED

**What:** PostgreSQL-native queue pattern for the CLI poller to claim pending items without race conditions.
**When to use:** `hivemind review` CLI command fetching the next pending item.

```python
# Source: https://www.inferable.ai/blog/posts/postgres-skip-locked
async def fetch_pending_for_review(session: AsyncSession, org_id: str, limit: int = 10):
    """Fetch pending contributions for CLI review, claiming them atomically."""
    stmt = (
        select(PendingContribution)
        .where(PendingContribution.org_id == org_id)
        .order_by(PendingContribution.contributed_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
```

### Pattern 7: Embedding Provider Abstraction (KM-08)

**What:** Wrap the embedding model behind an interface so the model can be swapped without changing callers.
**When to use:** All embedding generation; model name + revision stored in DB at startup.

```python
from sentence_transformers import SentenceTransformer
from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]: ...
    @property
    @abstractmethod
    def model_id(self) -> str: ...
    @property
    @abstractmethod
    def dimensions(self) -> int: ...

class SentenceTransformerProvider(EmbeddingProvider):
    # Pin model by name + HuggingFace commit hash (stored in deployment_config table)
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    # Pin revision at deployment time: MODEL_REVISION = "<commit_hash>"

    def __init__(self):
        self._model = SentenceTransformer(self.MODEL_NAME)

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()

    @property
    def model_id(self) -> str:
        return self.MODEL_NAME

    @property
    def dimensions(self) -> int:
        return 384
```

### Pattern 8: Org Namespace Isolation (ACL-01)

**What:** Every DB query scoped to `org_id`. Extracted from JWT bearer token in request context.
**When to use:** All MCP tool handlers; enforced at the ORM layer, never trusted from tool arguments.

```python
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

security = HTTPBearer()

async def get_org_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract org_id from bearer JWT. Never accept org_id as a tool argument."""
    try:
        payload = jwt.decode(credentials.credentials, key=SECRET_KEY, algorithms=["HS256"])
        org_id = payload.get("org_id")
        if not org_id:
            raise HTTPException(status_code=403, detail="Missing org_id claim")
        return org_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Pattern 9: CLI Approval Workflow

**What:** Typer command that fetches pending items, displays with Rich, prompts approve/reject/flag.
**When to use:** `hivemind review` — the user-facing approval experience (TRUST-02, TRUST-03).

```python
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import questionary

app = typer.Typer()
console = Console()

@app.command()
def review(org_id: str = typer.Option(..., envvar="HIVEMIND_ORG_ID")):
    """Review pending knowledge contributions."""
    pending = fetch_pending(org_id)  # sync HTTP call to server API

    if not pending:
        console.print("[green]All caught up! No pending contributions.[/green]")
        return

    for item in pending:
        console.print(Panel(
            f"[bold]{item.category}[/bold]\n\n{item.content}\n\n"
            f"[dim]Contributed by agent {item.source_agent_id} · {item.contributed_at}[/dim]",
            title="Knowledge Contribution",
            border_style="blue"
        ))

        action = questionary.select(
            "What would you like to do?",
            choices=["Approve", "Approve & make public", "Change category", "Flag as sensitive", "Reject"]
        ).ask()

        if action == "Change category":
            new_cat = questionary.select("Choose category:", choices=CATEGORIES).ask()
            approve_contribution(item.id, category_override=new_cat)
        elif action in ("Approve", "Approve & make public"):
            approve_contribution(item.id, is_public=(action == "Approve & make public"))
            # Gamification message
            stats = get_stats(org_id)
            console.print(f"[green]Approved! You've shared {stats.total} pieces of knowledge "
                          f"that have helped {stats.agent_count} agents.[/green]")
        elif action == "Flag as sensitive":
            flag_contribution(item.id)
            console.print("[yellow]Flagged for manual review.[/yellow]")
        else:  # Reject
            reject_contribution(item.id)
```

### Anti-Patterns to Avoid

- **Trusting `org_id` from tool arguments:** Agents must not be able to write to another org's namespace. Always extract `org_id` from the authenticated JWT/API key server-side.
- **Storing raw content before PII stripping:** The decision is explicit: PII never enters storage, not even the pending queue. Strip first, then write.
- **Loading GLiNER model per-request:** The GLiNER model is large (~400MB). Load once at startup in a module-level singleton, not inside each tool call.
- **Using Celery async tasks with `asyncio.run()`:** Celery workers are synchronous; calling `asyncio.run()` inside a Celery task works but is fragile. Better pattern: Celery calls a sync wrapper, or the pipeline is sync end-to-end inside the task.
- **No HNSW index at table creation:** Adding HNSW index to a table with millions of rows is slow and locks the table. Create it in the migration before data arrives.
- **Forgetting `asyncpg<0.29.0` pin:** SQLAlchemy `create_async_engine` has known compatibility issues with asyncpg 0.29.0+. Pin in `requirements.txt`.
- **Single `AsyncSession` shared across concurrent requests:** `AsyncSession` is not concurrency-safe. Each request must get its own session from the factory.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol compliance | Custom JSON-RPC server | FastMCP v2 | Session management, SSE/JSON response modes, schema generation, lifecycle — all edge-case-heavy |
| PII entity detection | Custom regex library | Presidio + GLiNER | Presidio handles 40+ entity types, confidence scoring, multi-language; GLiNER adds zero-shot NER; regex alone misses contextual PII |
| API key / secret detection | `re.search(r"sk-...")` | Presidio `PatternRecognizer` with curated patterns | Multiple secret formats; PatternRecognizer plugs into the same pipeline without branching logic |
| Vector similarity search | Custom cosine in Python | pgvector + HNSW index | pgvector pushes distance computation into the DB engine; HNSW gives approximate nearest neighbor at O(log n) vs O(n) naive scan |
| Async task queuing | `asyncio.create_task()` | Celery + Redis | `asyncio.create_task()` tasks die with the process; Celery survives restarts, supports retries, provides visibility |
| Database migrations | Manual `ALTER TABLE` | Alembic | Alembic autogenerates diffs, supports pgvector type registration, version-controls schema |
| Token-count-based 50% rejection | Count words manually | Count `[PLACEHOLDER]` tokens post-anonymization vs total tokens (simple split) | Presidio does not have this check built-in; the custom calculation is trivial — 5 lines of Python. Just implement it directly in `strip_pii()` |

**Key insight:** The Presidio + GLiNER pipeline eliminates the single biggest hand-roll risk — PII detection accuracy. Building custom regex for names, addresses, and org-specific identifiers is a reliability failure point. The library combination hits 81% F1 out of the box, with the "flag as sensitive" escape hatch covering the remaining 19%.

---

## Common Pitfalls

### Pitfall 1: MCP Spec Version Confusion
**What goes wrong:** The project specifies "MCP spec 2025-11-25" but the current published transport spec is dated 2025-03-26. LiteLLM v1.80.18 references protocol version 2025-11-25 internally, but the canonical public spec on modelcontextprotocol.io is 2025-03-26 (Streamable HTTP) and 2025-06-18 (Tools with `outputSchema`).
**Why it happens:** The protocol has had multiple revisions; date-based versioning creates confusion.
**How to avoid:** Implement against the 2025-03-26 transport spec + 2025-06-18 tools spec. FastMCP v2 handles version negotiation automatically; do not implement transport manually.
**Warning signs:** Tests failing when connecting from a different MCP client version.

### Pitfall 2: GLiNER Model Loading Latency
**What goes wrong:** `GLiNERRecognizer` loads `knowledgator/gliner-pii-base-v1.0` (~400MB) on first instantiation, causing 10-30s startup delay and high memory if re-loaded.
**Why it happens:** HuggingFace models are not lazy-loaded by default.
**How to avoid:** Instantiate `AnalyzerEngine` once in a module-level singleton at server startup (FastAPI `lifespan`). Download the model during Docker build, not at runtime.
**Warning signs:** `add_knowledge` calls timing out; memory spikes on concurrent requests.

### Pitfall 3: Celery + asyncio Event Loop Conflict
**What goes wrong:** Calling async database functions from inside a Celery task raises `RuntimeError: no running event loop` or creates nested event loop errors.
**Why it happens:** Celery workers run in a synchronous context; `asyncio.run()` inside a task is technically valid but fragile under forking workers.
**How to avoid:** Keep the Celery PII pipeline fully synchronous. Use synchronous `psycopg2` (not asyncpg) for any DB writes inside Celery tasks. The MCP server (async) and Celery workers (sync) are separate processes with separate DB connections.
**Warning signs:** `RuntimeError: This event loop is already running` in Celery logs.

### Pitfall 4: content_hash Collision on Different Orgs
**What goes wrong:** Two orgs contribute identical knowledge; `UNIQUE` constraint on `content_hash` prevents the second insert.
**Why it happens:** SHA-256 of content is org-agnostic; the unique constraint is wrong if it's global.
**How to avoid:** Make the unique constraint `(content_hash, org_id)` for private items. Public commons items can use global `content_hash` uniqueness (deduplication is desirable there). Implement this in the Alembic migration explicitly.
**Warning signs:** `UniqueViolation` errors when two orgs contribute the same bug fix.

### Pitfall 5: asyncpg Version Breaking SQLAlchemy Async
**What goes wrong:** After `pip install asyncpg`, the latest version (0.29.0+) causes `create_async_engine` to fail silently or raise obscure errors.
**Why it happens:** Known incompatibility between SQLAlchemy 2.0.x and asyncpg 0.29.0+.
**How to avoid:** Pin `asyncpg<0.29.0` in `requirements.txt` and `pyproject.toml`.
**Warning signs:** `AttributeError` or connection pool errors on startup; works with sync engine but not async.

### Pitfall 6: Forgetting `org_id` Filter on Deletion Cascade
**What goes wrong:** `delete_knowledge` deletes items by ID without verifying org ownership. Agent A can delete Agent B's knowledge.
**Why it happens:** DELETE by primary key is fast to write but skips the ownership check.
**How to avoid:** Always add `WHERE id = :id AND org_id = :org_id` to delete queries. Return 404 (not 403) if not found — don't reveal whether the item exists in another org.
**Warning signs:** Integration test showing Agent B can delete Agent A's contributions.

### Pitfall 7: 50% Rejection Threshold Off-by-One
**What goes wrong:** The rejection check miscounts because `[REDACTED]` is treated as 1 token but occupies multiple visual chars; or the original token count is used instead of the post-strip token count.
**Why it happens:** `len(text.split())` gives word count, but after anonymization, multi-word names become single `[NAME]` tokens, shrinking total count and inflating the apparent ratio.
**How to avoid:** Count placeholders in the anonymized text, divide by `max(len(anonymized.split()), 1)`. Test with a string that's 60% email addresses to confirm rejection fires correctly.

---

## Code Examples

Verified patterns from official sources:

### SQLAlchemy Async Engine + Session Setup

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/hivemind"

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)

@asynccontextmanager
async def get_session():
    async with AsyncSessionFactory() as session:
        yield session
```

### pgvector Cosine Search Query

```python
# Source: https://github.com/pgvector/pgvector-python
from sqlalchemy import select

async def search_knowledge(query_embedding: list[float], org_id: str, limit: int = 10, offset: int = 0):
    async with get_session() as session:
        stmt = (
            select(KnowledgeItem)
            .where(
                (KnowledgeItem.org_id == org_id) | (KnowledgeItem.is_public == True)
            )
            .order_by(KnowledgeItem.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return result.scalars().all()
```

### Alembic env.py with pgvector type registration

```python
# Source: https://github.com/sqlalchemy/alembic/discussions/1324
# In alembic/env.py — register vector type so alembic autogenerate recognizes it
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import dialect as pg_dialect

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=False,
    )
    # Register pgvector type
    from pgvector.sqlalchemy import register_vector
    register_vector(connection)
    with context.begin_transaction():
        context.run_migrations()
```

### FastAPI Lifespan for Startup Init

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load models once
    from hivemind.pipeline.pii import initialize_pii_pipeline
    from hivemind.pipeline.embedder import SentenceTransformerProvider
    app.state.pii = initialize_pii_pipeline()
    app.state.embedder = SentenceTransformerProvider()
    yield
    # Shutdown: dispose DB engine
    await engine.dispose()
```

### SHA-256 Content Hash

```python
# Source: Python stdlib hashlib
import hashlib

def content_hash(text: str) -> str:
    """Compute SHA-256 of content for KM-01 provenance."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HTTP+SSE transport (2024-11-05 spec) | Streamable HTTP (2025-03-26 spec) | MCP spec 2025-03-26 | Single endpoint replaces `/sse` + `/messages` dual-endpoint pattern |
| `spacy` large NER for PII | Presidio + GLiNER zero-shot | 2024-2025 | Zero-shot NER eliminates need to train custom models for new entity types |
| `IVFFlat` index in pgvector | `HNSW` index | pgvector 0.5.0 (2023), now dominant | HNSW supports concurrent inserts without reindex; better recall at fixed ef_search |
| SQLAlchemy 1.x | SQLAlchemy 2 async | 2023 | `AsyncSession` + `create_async_engine` are first-class; no `greenlet` dependency |
| FastMCP v1 (Jeff Ling's library) | FastMCP v2 (incorporated into official MCP SDK, independently maintained) | 2024 | Incorporated into official SDK codebase but remains independently maintained by jlowin |

**Deprecated/outdated:**
- `HTTP+SSE transport` (2024-11-05): Replaced by Streamable HTTP. Old SSE clients supported via backwards compatibility in FastMCP but should not be the primary target.
- `IVFFlat` index for pgvector: Works but requires rebuilding when data grows significantly; HNSW is preferred for production.
- `asyncpg >= 0.29.0` with SQLAlchemy 2.0.x: Pin below 0.29.0 until SQLAlchemy releases a fix.

---

## Open Questions

1. **Celery vs PostgreSQL queue for Phase 1**
   - What we know: `FOR UPDATE SKIP LOCKED` is fully sufficient for a simple pending queue; Celery adds Redis dependency but provides retries and worker monitoring
   - What's unclear: Whether the PII pipeline (GLiNER inference is ~50-100ms) is fast enough to run synchronously inside the MCP tool call, or whether async decoupling is needed from day one
   - Recommendation: Run PII pipeline synchronously inside `add_knowledge` for Phase 1 (simpler architecture); add Celery only if latency becomes a problem. Agent async flow (contributes and moves on) is already satisfied by returning immediately after sync strip + DB insert.

2. **Bearer JWT vs API key for Phase 1 agent auth**
   - What we know: FastMCP supports `BearerAuthProvider` with RSA key pairs for full OAuth; simpler API key in `Authorization: Bearer <key>` header is also viable
   - What's unclear: Phase 1 has no key management UI — how does an org get their API key/token?
   - Recommendation: Simple hardcoded shared secret per org for Phase 1 (stored in config/env); full OAuth/key management in Phase 2. Treat the `Authorization: Bearer <token>` as an opaque org identifier for now.

3. **Public commons visibility scope**
   - What we know: Approved contributions go to private namespace, public commons, or both (user decides at approval time)
   - What's unclear: The `is_public` flag on `knowledge_items` is the data model, but the CLI approval step needs to make this decision clear to the user without being intimidating
   - Recommendation: Default to private namespace only. "Approve & make public" is the explicit opt-in action in the CLI, not the default.

4. **Embedding model revision pinning mechanics**
   - What we know: HuggingFace supports `revision` parameter (commit hash) when loading models
   - What's unclear: Whether to pin at a specific commit hash in code, or store the commit hash in the `deployment_config` DB table and load dynamically
   - Recommendation: Store model name + revision in a `deployment_config` table populated at first startup. This enables detection of model drift and documents the pin for future migration tooling.

---

## Sources

### Primary (HIGH confidence)
- https://modelcontextprotocol.io/specification/2025-03-26/basic/transports — MCP Streamable HTTP transport spec (full doc fetched)
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools — MCP tools spec: `isError`, response types, `outputSchema` (full doc fetched)
- https://gofastmcp.com/python-sdk/fastmcp-server-http — FastMCP HTTP configuration: `create_streamable_http_app`, `stateless_http`, `json_response` (fetched)
- https://github.com/jlowin/fastmcp — FastMCP README: version status, tool decorator, async support (fetched)
- https://microsoft.github.io/presidio/samples/python/gliner/ — Presidio GLiNER integration: setup code, recommended model (fetched)
- https://huggingface.co/knowledgator/gliner-pii-base-v1.0 — GLiNER-PII model: entity types, benchmarks, usage (fetched)
- https://github.com/pgvector/pgvector-python — pgvector Python SQLAlchemy patterns: vector column, cosine search, HNSW index (fetched)

### Secondary (MEDIUM confidence)
- WebSearch: FastMCP v2 confirmed as `<3` install, 70% MCP server adoption (multiple sources agree)
- WebSearch: asyncpg <0.29.0 pin required (SQLAlchemy discussion confirmed)
- WebSearch: `FOR UPDATE SKIP LOCKED` as idiomatic PostgreSQL queue pattern (multiple 2025 sources)
- WebSearch: Celery 5.5.x stable as of 2025, Redis broker standard
- WebSearch: Typer + Rich for Python CLI (official docs confirmed)

### Tertiary (LOW confidence)
- WebSearch: FastMCP v3.0.0rc1 status — marked LOW because it's a release candidate; stick to v2

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against official docs or official GitHub
- Architecture patterns: HIGH — patterns derived directly from official source code examples
- PII pipeline: HIGH — Presidio+GLiNER integration verified against official Microsoft Presidio docs; entity list verified against HuggingFace model card
- Pitfalls: MEDIUM/HIGH — asyncpg version issue and Celery/asyncio conflict are well-documented; 50% threshold implementation is custom logic (LOW confidence on exact token counting approach, but the approach is straightforward)
- MCP spec version: MEDIUM — "2025-11-25" referenced in requirements vs "2025-03-26/2025-06-18" in public docs; FastMCP handles negotiation, so implementation impact is LOW

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (30 days — stable libraries; FastMCP v3 GA could change recommendations)
