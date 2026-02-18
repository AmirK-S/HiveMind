# Phase 2: Trust & Security Hardening - Research

**Researched:** 2026-02-18
**Domain:** Security pipeline hardening, RBAC, API key auth, graph store abstraction, rate limiting
**Confidence:** HIGH (most areas verified against installed packages and official docs)

---

## Summary

Phase 2 extends the Phase 1 MCP loop with five distinct security layers: (1) a prompt injection scanner blocking malicious content before it enters the commons, (2) a hardened two-pass PII pipeline with markdown-aware code block preservation, (3) SHA-256 content integrity verification on every knowledge item, (4) RBAC at three levels (namespace/category/item), and (5) API key authentication with tier-based rate limiting. The Graphiti+FalkorDB graph store abstraction (INFRA-02) and webhook push for near-real-time delivery (INFRA-03) are also scoped here.

**Critical discovery:** The project runs Python 3.14.3. `llm-guard` is blocked (requires Python <3.13). However, `transformers 5.1.0` and `torch 2.10.0` are already installed. The DeBERTa prompt injection model (`ProtectAI/deberta-v3-base-prompt-injection-v2`) can be used directly via the `transformers` pipeline without llm-guard. This is the correct path — same model, no extra dependency, Python 3.14 compatible.

**Primary recommendation:** Use the `transformers` pipeline directly for prompt injection (SEC-01), `pycasbin` + `casbin-async-sqlalchemy-adapter` for RBAC (ACL-02/03/04/05), `fastapi-limiter` + Redis for rate limiting (SEC-03, INFRA-04), and implement the Graphiti GraphDriver abstraction layer as a read-through cache pattern on top of existing pgvector (INFRA-02).

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRUST-04 | User can configure auto-approve rules per knowledge category | Config table in PostgreSQL + category-level policy check before manual queue |
| TRUST-05 | PII stripping runs two-pass validation: Pass 1 re-runs analyzer on anonymized text for residual leaks; Pass 2 checks output against original PII values verbatim | Presidio `AnalyzerEngine.analyze()` called twice; string search for original PII fragments |
| TRUST-06 | Pipeline is markdown-aware — extracts and protects fenced/inline code blocks before anonymization, processes only narrative text, then reinjects code blocks intact | Regex extract code blocks → UUID placeholder → strip PII on narrative → reinject blocks |
| SEC-01 | Contributed knowledge scanned for prompt injection and malicious instructions before entering commons | `transformers` pipeline with `ProtectAI/deberta-v3-base-prompt-injection-v2` model; lazy-loaded singleton |
| SEC-02 | Content hash (SHA-256) on every knowledge item for integrity verification | Already implemented on `content_hash` column; need retrieval-time verification function |
| SEC-03 | Rate limiting on contributions per agent + coordinated contribution campaign detection (anti-sybil) | `fastapi-limiter` + Redis sliding window; per agent_id key; burst pattern detection via Redis ZSET |
| ACL-02 | User can explicitly publish knowledge from private namespace to public commons — publication is reversible | Toggle `is_public` flag on `knowledge_items`; new MCP tool + CLI command |
| ACL-03 | Agent roles enforced at three levels: namespace (org), category (knowledge type), and individual item | PyCasbin RBAC with domains; model: `r = sub, dom, obj, act` |
| ACL-04 | Organization admin can manage agents and roles within their namespace | Casbin `AsyncEnforcer` + policy CRUD API; admin role check via JWT claims |
| ACL-05 | Cross-namespace search supported — queries can span both private and public commons with deduplication | Already partially implemented via `(org_id == :org_id) OR (is_public == True)` in search_knowledge; dedup by content_hash |
| INFRA-02 | Knowledge store abstraction following Graphiti's GraphDriver pattern — first graph backend target: Graphiti-on-FalkorDB | `graphiti-core[falkordb]` installs cleanly on Python 3.14; `FalkorDriver` implements GraphDriver ABC |
| INFRA-03 | Near-real-time knowledge availability (seconds, not milliseconds) via webhook push after quality gate | Celery task triggered post-approval; HTTP POST to registered webhook URLs |
| INFRA-04 | API key authentication with associated tier, request counter, and billing period reset | New `api_keys` table with `tier`, `request_count`, `billing_period_start`; JWT replaced/extended |

</phase_requirements>

---

## Standard Stack

### Core (already in pyproject.toml or confirmed installable)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `transformers` | 5.1.0 (installed) | Prompt injection scanner model runtime | `deberta-v3-base-prompt-injection-v2` is the best open-source prompt injection classifier; already installed |
| `torch` | 2.10.0 (installed) | Model inference backend | Required by transformers; already installed |
| `pycasbin` | >=2.8.0 | RBAC with domain/tenant support | Pure Python, no C extensions; installs cleanly on Python 3.14; has async enforcer |
| `casbin-async-sqlalchemy-adapter` | 1.17.0 | Policy storage in PostgreSQL | Reuses existing SQLAlchemy+PostgreSQL; no extra infra |
| `fastapi-limiter` | 0.2.0 | Rate limiting via Redis | Integrates with FastAPI dependency injection; reuses existing Redis |
| `pyrate-limiter` | 4.0.2 (pulled by fastapi-limiter) | Rate algorithm implementation | Sliding window, fixed window, token bucket |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `graphiti-core[falkordb]` | 0.28.0 | Graph store abstraction + FalkorDB backend | INFRA-02: implement GraphDriver-style abstraction; FalkorDB as first backend |
| `falkordb` | 1.5.0 | FalkorDB Python client (pulled by graphiti-core) | Redis-based graph database; high-performance for multi-agent knowledge graphs |
| `celery` | latest | Background task for webhook push | INFRA-03: post-approval webhook delivery |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `transformers` pipeline direct | `llm-guard` | llm-guard requires Python <3.13; blocked on Python 3.14 |
| `pycasbin` | `oso`/`osohq` | Oso uses Polar policy language (extra learning); casbin uses .conf + .csv which is simpler to reason about |
| `fastapi-limiter` | `slowapi` | slowapi is more popular but uses flask-limiter style decorators; fastapi-limiter uses dependency injection which fits our patterns |
| `casbin-async-sqlalchemy-adapter` | Redis-backed casbin adapter | We already have PostgreSQL; no extra infra needed for policy storage |

**Installation (new packages to add):**
```bash
pip install pycasbin casbin-async-sqlalchemy-adapter fastapi-limiter "graphiti-core[falkordb]" celery
```

Confirmed installable on Python 3.14 (dry-run verified):
- `pycasbin` 2.8.0: installs (simpleeval, wcmatch deps only)
- `casbin-async-sqlalchemy-adapter` 1.17.0: installs (pycasbin 2.8.0, SQLAlchemy already present)
- `fastapi-limiter` 0.2.0: installs (pyrate-limiter 4.0.2; FastAPI already present)
- `graphiti-core[falkordb]` 0.28.0: installs (falkordb 1.5.0, uses redis 7.2.0 already present)
- `llm-guard`: BLOCKED — requires Python <3.13

---

## Architecture Patterns

### Recommended Project Structure (additions to existing)

```
hivemind/
├── pipeline/
│   ├── pii.py               # EXISTS — extend with two-pass + markdown-aware (TRUST-05, TRUST-06)
│   ├── injection.py         # NEW — prompt injection scanner (SEC-01)
│   └── integrity.py         # NEW — SHA-256 verification helpers (SEC-02)
├── security/
│   ├── __init__.py          # NEW
│   ├── rbac.py              # NEW — casbin enforcer singleton (ACL-03/04)
│   └── rate_limit.py        # NEW — fastapi-limiter setup + tier helpers (SEC-03, INFRA-04)
├── db/
│   ├── models.py            # EXTEND — add ApiKey, AutoApproveRule, CasbinRule models
│   └── session.py           # EXISTS
├── server/
│   ├── tools/
│   │   ├── add_knowledge.py        # EXTEND — inject injection scanner + rate limit
│   │   ├── search_knowledge.py     # EXTEND — cross-namespace dedup (ACL-05)
│   │   ├── publish_knowledge.py    # NEW — ACL-02 explicit publication tool
│   │   └── admin_tools.py          # NEW — ACL-04 org admin RBAC management
│   └── main.py              # EXTEND — add rate limit init, casbin init, Redis init
├── graph/
│   └── driver.py            # NEW — GraphDriver abstraction + FalkorDB impl (INFRA-02)
└── webhooks/
    ├── __init__.py          # NEW
    └── tasks.py             # NEW — Celery task for webhook push (INFRA-03)

alembic/versions/
├── 001_initial_schema.py    # EXISTS
├── 002_add_deleted_at.py    # EXISTS
├── 003_api_keys.py          # NEW — api_keys table (INFRA-04)
├── 004_auto_approve_rules.py # NEW — auto_approve_rules table (TRUST-04)
├── 005_casbin_rules.py      # NEW — casbin_rule table (ACL-03/04)
└── 006_webhook_endpoints.py  # NEW — webhook_endpoints table (INFRA-03)
```

---

### Pattern 1: Prompt Injection Scanner (SEC-01)

**What:** Lazy-loaded singleton using `transformers` pipeline with `ProtectAI/deberta-v3-base-prompt-injection-v2`. Scans content in `add_knowledge` before PII stripping. If injection detected with score >= 0.5, reject with clear error message.

**Why before PII stripping:** Injection patterns may be hidden in text that gets partially redacted — scan raw text before any modification.

**Model details:** 95.25% accuracy, 99.74% recall, Apache 2.0 license, 0.2B params, max 512 tokens, CPU ~213ms/call, CPU+ONNX ~104ms.

```python
# Source: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2
# hivemind/pipeline/injection.py

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import Pipeline

_MODEL_ID = "ProtectAI/deberta-v3-base-prompt-injection-v2"
_THRESHOLD = 0.5


class InjectionScanner:
    """Singleton prompt injection scanner using DeBERTa-v3."""

    _instance: "InjectionScanner | None" = None

    def __init__(self) -> None:
        # Lazy import: transformers is large; defer until first instantiation
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
        import torch
        tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._pipeline: Pipeline = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=512,
            device=device,
        )

    @classmethod
    def get_instance(cls) -> "InjectionScanner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_injection(self, text: str, threshold: float = _THRESHOLD) -> bool:
        """Returns True if content is classified as prompt injection."""
        result = self._pipeline(text[:2000])  # cap to avoid OOM on very long inputs
        # Labels: LABEL_0 = benign, LABEL_1 = injection
        label = result[0]["label"]
        score = result[0]["score"]
        return label == "LABEL_1" and score >= threshold
```

**Integration in add_knowledge.py** (before PII strip):
```python
from hivemind.pipeline.injection import InjectionScanner

# After input validation, before PII strip:
if InjectionScanner.get_instance().is_injection(content):
    return CallToolResult(
        content=[TextContent(type="text", text="Rejected: content contains potential prompt injection.")],
        isError=True,
    )
```

---

### Pattern 2: Two-Pass PII Validation + Markdown-Aware (TRUST-05, TRUST-06)

**What:** Extend `PIIPipeline.strip()` with:
1. Code block extraction via regex before any analysis (TRUST-06)
2. PII stripping on narrative text only
3. Pass 2: re-run `AnalyzerEngine.analyze()` on the anonymized text for residual leaks
4. Pass 2 verbatim check: verify none of the original PII values appear literally in the output

**Code block preservation pattern (TRUST-06):**
```python
import re
import uuid

# Regex patterns for code blocks
_FENCED_CODE_RE = re.compile(r'(```[\s\S]*?```|~~~[\s\S]*?~~~)', re.MULTILINE)
_INLINE_CODE_RE = re.compile(r'(`[^`\n]+`)')

def _extract_code_blocks(text: str) -> tuple[str, dict[str, str]]:
    """Replace code blocks with UUID placeholders; return (modified_text, placeholder_map)."""
    placeholder_map: dict[str, str] = {}

    def replace_fenced(m: re.Match) -> str:
        key = f"__CODE_BLOCK_{uuid.uuid4().hex}__"
        placeholder_map[key] = m.group(0)
        return key

    def replace_inline(m: re.Match) -> str:
        key = f"__INLINE_{uuid.uuid4().hex}__"
        placeholder_map[key] = m.group(0)
        return key

    text = _FENCED_CODE_RE.sub(replace_fenced, text)
    text = _INLINE_CODE_RE.sub(replace_inline, text)
    return text, placeholder_map

def _reinject_code_blocks(text: str, placeholder_map: dict[str, str]) -> str:
    for key, original in placeholder_map.items():
        text = text.replace(key, original)
    return text
```

**Two-pass validation (TRUST-05):**
```python
def strip(self, text: str) -> tuple[str, bool]:
    # TRUST-06: Extract code blocks first
    narrative, code_map = _extract_code_blocks(text)

    # Pass 1: strip PII from narrative text
    results = self._analyzer.analyze(text=narrative, language="en")
    original_pii_values = [narrative[r.start:r.end] for r in results]

    anonymized = self._anonymizer.anonymize(
        text=narrative, analyzer_results=results, operators=self._operators
    )
    cleaned_narrative = anonymized.text

    # TRUST-05 Pass 2a: re-analyze anonymized text for residual leaks
    residual_results = self._analyzer.analyze(text=cleaned_narrative, language="en")
    if residual_results:
        # Re-strip residual findings
        cleaned_narrative = self._anonymizer.anonymize(
            text=cleaned_narrative, analyzer_results=residual_results, operators=self._operators
        ).text

    # TRUST-05 Pass 2b: verbatim check — ensure no original PII values survived
    for pii_value in original_pii_values:
        if len(pii_value) >= 4 and pii_value in cleaned_narrative:
            cleaned_narrative = cleaned_narrative.replace(pii_value, "[REDACTED]")

    # Reinject code blocks intact (TRUST-06)
    cleaned = _reinject_code_blocks(cleaned_narrative, code_map)

    # 50% rejection check on POST-strip token count (existing decision)
    placeholder_count = len(_PLACEHOLDER_RE.findall(cleaned))
    total_tokens = max(len(cleaned.split()), 1)
    should_reject = (placeholder_count / total_tokens) > 0.50

    return cleaned, should_reject
```

---

### Pattern 3: Content Hash Integrity Verification (SEC-02)

**What:** SHA-256 hash is already stored on `content_hash` column (set on insert, never updated). Phase 2 adds a retrieval-time verification function and exposes it in the fetch-by-id path.

**Status:** Hash *storage* is already implemented (Phase 1). What's new in Phase 2 is *verification at retrieval time*.

```python
# hivemind/pipeline/integrity.py
import hashlib

def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content string."""
    return hashlib.sha256(content.encode()).hexdigest()

def verify_content_hash(content: str, stored_hash: str) -> bool:
    """Returns True if content matches the stored hash."""
    return compute_content_hash(content) == stored_hash
```

**In `_fetch_by_id()`:** After retrieving an item, call `verify_content_hash(item.content, item.content_hash)`. If False, log a tamper warning and return an error response with a tamper-detected message.

---

### Pattern 4: RBAC at Three Levels (ACL-03, ACL-04)

**What:** PyCasbin `AsyncEnforcer` with domain-aware RBAC model. Three enforcement levels:
- `dom` = namespace (org_id): e.g. `"acme-corp"`
- `obj` prefix = category: e.g. `"category:bug_fix"` or `"namespace:acme-corp"`
- `obj` prefix = item: e.g. `"item:<uuid>"`

**Casbin model (`rbac_with_domains.conf`):**
```ini
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
```

**Policy examples (stored in `casbin_rule` table):**
```
# Org admin can do anything in their namespace
p, admin, acme-corp, namespace:acme-corp, *

# Agent can read bug_fix category
p, agent-1, acme-corp, category:bug_fix, read

# Agent can write a specific item
p, agent-1, acme-corp, item:uuid-here, write

# Role assignment: agent-1 has role "contributor" in acme-corp
g, agent-1, contributor, acme-corp
```

**Async enforcer setup (reuse existing asyncpg PostgreSQL):**
```python
# hivemind/security/rbac.py
import casbin_async_sqlalchemy_adapter
import casbin

_enforcer: casbin.AsyncEnforcer | None = None

async def get_enforcer() -> casbin.AsyncEnforcer:
    global _enforcer
    if _enforcer is None:
        from hivemind.config import settings
        adapter = casbin_async_sqlalchemy_adapter.Adapter(
            settings.database_url.replace("+asyncpg", "+asyncpg")  # already async URL
        )
        _enforcer = casbin.AsyncEnforcer("path/to/rbac_with_domains.conf", adapter)
        await _enforcer.load_policy()
    return _enforcer
```

**NOTE:** `casbin-async-sqlalchemy-adapter` creates its own `casbin_rule` table automatically — no manual migration needed for the table itself, but Alembic should stamp it.

---

### Pattern 5: API Key Authentication with Tiers (INFRA-04)

**What:** New `api_keys` table extends/replaces the bare JWT approach. API key contains: `key_hash` (not the raw key), `org_id`, `agent_id`, `tier` (free/pro/enterprise), `request_count`, `billing_period_start`, `billing_period_reset_days`.

**Schema additions (Alembic migration 003):**
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_prefix VARCHAR(8) NOT NULL,      -- first 8 chars for display/lookup
    key_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA-256 of full API key
    org_id VARCHAR(255) NOT NULL,
    agent_id VARCHAR(255) NOT NULL,
    tier VARCHAR(20) NOT NULL DEFAULT 'free',  -- free|pro|enterprise
    request_count INTEGER NOT NULL DEFAULT 0,
    billing_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    billing_period_reset_days INTEGER NOT NULL DEFAULT 30,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ
);
CREATE INDEX ix_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX ix_api_keys_org_id ON api_keys (org_id);
```

**Rate limits by tier (fastapi-limiter):**
```python
TIER_LIMITS = {
    "free":       {"contributions": "10/minute", "searches": "30/minute"},
    "pro":        {"contributions": "60/minute", "searches": "200/minute"},
    "enterprise": {"contributions": "300/minute", "searches": "1000/minute"},
}
```

**Anti-sybil (SEC-03) — coordinated campaign detection:**
Track per-org contribution velocity in Redis using a sliding window ZSET. If an org submits >N contributions within a short burst window (e.g., >50 in 60 seconds), flag for manual review rather than outright block. This detects coordinated sybil campaigns without false-positiving on legitimate bulk uploads.

```python
# Redis ZSET key: "burst:{org_id}:contributions"
# Score = Unix timestamp, Member = contribution_id
# Check: ZCOUNT key (now-60) now > BURST_THRESHOLD
```

---

### Pattern 6: Auto-Approve Rules (TRUST-04)

**What:** New `auto_approve_rules` table maps org_id + category to an auto_approve boolean. Before queuing to pending_contributions, check if this org has an auto-approve rule for this category. If yes, skip the queue and insert directly into `knowledge_items`.

**Schema additions (Alembic migration 004):**
```sql
CREATE TABLE auto_approve_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id VARCHAR(255) NOT NULL,
    category knowledgecategory NOT NULL,
    is_auto_approve BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, category)
);
```

**Usage in add_knowledge.py:**
```python
rule = await session.execute(
    select(AutoApproveRule).where(
        AutoApproveRule.org_id == auth.org_id,
        AutoApproveRule.category == category_enum,
        AutoApproveRule.is_auto_approve == True,
    )
)
if rule.scalar_one_or_none():
    # Skip pending queue; insert directly with embedding
    await _insert_knowledge_item(session, ...)
else:
    # Normal flow: insert to pending_contributions
    await _insert_pending_contribution(session, ...)
```

---

### Pattern 7: Cross-Namespace Search with Deduplication (ACL-05)

**What:** The current `search_knowledge` already implements the correct SQL pattern: `(org_id == :org_id) OR (is_public == True)`. What's missing is deduplication when the same item (by content_hash) appears in both private and public results.

**Deduplication approach:** After retrieving rows, filter on content_hash uniqueness in Python. Private results take priority over public duplicates (if an agent has a private copy and there's a public copy with the same content, prefer the private one so org attribution is correct).

```python
# After collecting rows, deduplicate by content_hash:
seen_hashes: set[str] = set()
deduped = []
for item, distance in rows:
    if item.content_hash not in seen_hashes:
        seen_hashes.add(item.content_hash)
        deduped.append((item, distance))
```

**Alternative:** Add `DISTINCT ON (content_hash)` in SQL — but pgvector + DISTINCT ON doesn't compose well with ORDER BY distance. Python dedup is simpler and correct.

---

### Pattern 8: GraphDriver Abstraction (INFRA-02)

**What:** `graphiti-core` provides `GraphDriver` ABC with 11 operation interfaces. `FalkorDriver` implements it. The task is to add a `hivemind/graph/driver.py` that wraps our existing PostgreSQL/pgvector store behind the same interface pattern — not to replace pgvector, but to create a driver abstraction layer that lets the planner later swap backends.

**Key insight from research:** INFRA-02 says "following Graphiti's GraphDriver pattern." This means we adopt the *interface pattern*, not necessarily that we replace our entire storage with Graphiti. The first implementation wraps pgvector; FalkorDB is the second target.

**Install:**
```bash
pip install "graphiti-core[falkordb]"  # adds graphiti_core + falkordb packages
```

**FalkorDriver instantiation:**
```python
from graphiti_core.driver.falkordb_driver import FalkorDriver

driver = FalkorDriver(
    host="localhost",
    port=6379,        # FalkorDB runs on Redis port
    database="hivemind"
)
```

---

### Pattern 9: Webhook Push (INFRA-03)

**What:** After a contribution is approved (in CLI `review.py`), trigger a Celery task that POSTs to registered webhook URLs. Delivery within seconds satisfies "near-real-time."

**Celery not yet installed** (it's in pyproject.toml as a dependency but not in the venv). Needs to be added and a worker started.

```python
# hivemind/webhooks/tasks.py
from celery import Celery
from hivemind.config import settings

celery_app = Celery("hivemind", broker=settings.redis_url)

@celery_app.task(bind=True, max_retries=3)
def deliver_webhook(self, knowledge_item_id: str, org_id: str, event: str):
    """POST knowledge event to all registered webhook endpoints for this org."""
    ...
```

---

### Anti-Patterns to Avoid

- **Scanning PII-stripped text for injections:** Scan raw content before PII stripping — injections may be hidden in text that gets partially redacted.
- **Storing raw API keys in the database:** Store SHA-256 hash only (`key_hash`). The raw key is shown once at creation time. Use `key_prefix` (first 8 chars) for display.
- **Using llm-guard on Python 3.14:** Confirmed blocked. Use `transformers` pipeline directly.
- **Casbin policy in a flat file:** Use `casbin-async-sqlalchemy-adapter` to store policies in PostgreSQL alongside existing data. No extra infrastructure.
- **Blocking injection scan in critical path:** The injection scanner (~213ms CPU) adds latency. This is acceptable for `add_knowledge` (not a latency-sensitive path). Do NOT add it to `search_knowledge`.
- **Rebuilding the Casbin rule table manually:** `casbin-async-sqlalchemy-adapter` creates the `casbin_rule` table automatically on first `load_policy()`. Don't add a manual DDL for it; instead `alembic stamp` after first run.
- **Cross-namespace dedup in SQL with DISTINCT ON:** DISTINCT ON + ORDER BY distance doesn't compose in pgvector. Do dedup in Python after fetching.
- **FalkorDB as drop-in replacement for pgvector immediately:** INFRA-02 is an *abstraction layer*. pgvector remains as the operational store. FalkorDB integration is the new graph traversal backend, not a replacement for the vector search.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prompt injection detection | Custom regex heuristics | `transformers` pipeline + `ProtectAI/deberta-v3-base-prompt-injection-v2` | 95.25% accuracy; regex can't detect semantic injection patterns |
| Access control policy enforcement | Custom permission tables | `pycasbin` + `casbin-async-sqlalchemy-adapter` | Handles role inheritance, domain isolation, policy CRUD; avoids policy logic bugs |
| Rate limiting per agent | Custom Redis INCR + TTL | `fastapi-limiter` + `pyrate-limiter` | Handles sliding window, atomic Redis operations, FastAPI dependency injection |
| Content hash computation | Custom hashing | `hashlib.sha256()` (stdlib) | Already used in Phase 1; no new dep needed |
| Markdown code block extraction | Ad-hoc string splitting | Regex patterns `(```[\s\S]*?```)` | Handles fenced, tilded, and inline code blocks correctly |
| Graph store abstraction | Custom abstract class | Follow Graphiti's `GraphDriver` ABC pattern | Proven 11-operation interface; FalkorDB first-class backend already exists |

**Key insight:** The PII pipeline (Presidio + GLiNER) already handles PII well. Phase 2's TRUST-05/06 improvements are surgical extensions to the existing `PIIPipeline.strip()` method, not a rewrite.

---

## Common Pitfalls

### Pitfall 1: Python 3.14 Incompatible Security Packages
**What goes wrong:** `llm-guard` fails to install — `requires-python = ">=3.10,<3.13"`.
**Why it happens:** llm-guard pins to Python <3.13 due to its own spacy/dependency constraints.
**How to avoid:** Use `transformers` pipeline directly. Same underlying model (`ProtectAI/deberta-v3-base-prompt-injection-v2`), same accuracy, no version conflict. `transformers 5.1.0` is already installed.
**Warning signs:** `pip install llm-guard` with Python 3.14 — immediate incompatibility error.

### Pitfall 2: Injection Scanner Cold-Start Penalty
**What goes wrong:** First call to `InjectionScanner.get_instance()` takes 2-5 seconds to load the DeBERTa model.
**Why it happens:** 0.2B parameter model requires disk load + tokenizer initialization.
**How to avoid:** Initialize `InjectionScanner.get_instance()` in the server `lifespan()` function alongside PIIPipeline and EmbeddingProvider. Same pattern already used in Phase 1.
**Warning signs:** First contribution after server start takes 5+ seconds; subsequent calls are fast.

### Pitfall 3: Casbin Policy Table Auto-Creation vs. Alembic
**What goes wrong:** `casbin-async-sqlalchemy-adapter` creates `casbin_rule` table on its own. Alembic doesn't know about it. `alembic check` reports drift.
**Why it happens:** Casbin adapters manage their own schema.
**How to avoid:** After first startup with Casbin, run `alembic stamp head` or add an empty migration that creates the `casbin_rule` table explicitly. The latter is cleaner for reproducibility.
**Warning signs:** `alembic check` shows untracked tables.

### Pitfall 4: PII Two-Pass Verbatim Check Length Threshold
**What goes wrong:** Single-character or very short PII fragments (e.g., "A", "J") trigger false positives in the verbatim check.
**Why it happens:** Short strings appear everywhere in natural language text.
**How to avoid:** Only verbatim-check PII values with `len(pii_value) >= 4`. Shorter values are acceptable residual risk given typing context (the PII scanner uses context anyway).
**Warning signs:** Excessive `[REDACTED]` insertions in output for normal words.

### Pitfall 5: Markdown Code Block Regex and Nested Backticks
**What goes wrong:** Inline code regex `(`[^`\n]+`)` doesn't handle double-backtick inline code (` ``like this`` `).
**Why it happens:** Markdown allows double-backtick for inline code containing single backticks.
**How to avoid:** Apply fenced block regex first (captures triple-backtick blocks), then inline regex. This ensures fenced blocks are already placeholder'd when inline regex runs. Fenced block regex uses `[\s\S]*?` (non-greedy) to handle multiline correctly.
**Warning signs:** Code blocks containing single backticks get mangled.

### Pitfall 6: Rate Limit Key Collision Across Orgs
**What goes wrong:** If rate limit key is `"add_knowledge:{agent_id}"` and two different orgs have agents with the same `agent_id` string, they share a rate limit bucket.
**Why it happens:** agent_id is user-supplied and may not be globally unique.
**How to avoid:** Key should be `"add_knowledge:{org_id}:{agent_id}"` — namespaced by org. Also use `"burst:{org_id}:contributions"` for anti-sybil tracking.
**Warning signs:** Agent A's rate limit blocks Agent B in a different org.

### Pitfall 7: SHA-256 Verification Adds Latency on Every Fetch
**What goes wrong:** Computing SHA-256 on every `fetch_by_id()` call adds ~1ms per call, but is pointless for search (too many results to verify inline).
**Why it happens:** Applying the same verification logic everywhere.
**How to avoid:** Only verify hash in `fetch_by_id()` (where the user explicitly requested an item). Search results are summary-tier anyway — they don't return full content so hash verification doesn't apply.
**Warning signs:** Search latency increases measurably.

### Pitfall 8: Graphiti FalkorDB Requires a Running Redis Instance
**What goes wrong:** FalkorDB runs on the same port/protocol as Redis but is NOT the same as the Redis used for rate limiting.
**Why it happens:** FalkorDB is Redis-based (uses Redis modules), but graph operations and rate limit operations should not share the same Redis instance in production.
**How to avoid:** Configure separate Redis instances: `HIVEMIND_REDIS_URL` for Celery/rate-limiting, `HIVEMIND_FALKORDB_HOST`/`HIVEMIND_FALKORDB_PORT` for FalkorDB. For development, a single instance is acceptable.
**Warning signs:** FalkorDB graph operations interfere with rate limit key TTLs.

---

## Code Examples

### SEC-01: Prompt Injection Scanner Singleton

```python
# Source: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2
# hivemind/pipeline/injection.py

from __future__ import annotations

_MODEL_ID = "ProtectAI/deberta-v3-base-prompt-injection-v2"
_THRESHOLD = 0.5
_MAX_INPUT_CHARS = 2000  # truncate to prevent OOM on very long inputs

class InjectionScanner:
    _instance: "InjectionScanner | None" = None

    def __init__(self) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
        import torch
        self._pipeline = pipeline(
            "text-classification",
            model=AutoModelForSequenceClassification.from_pretrained(_MODEL_ID),
            tokenizer=AutoTokenizer.from_pretrained(_MODEL_ID),
            truncation=True,
            max_length=512,
            device=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
        )

    @classmethod
    def get_instance(cls) -> "InjectionScanner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_injection(self, text: str) -> tuple[bool, float]:
        """Returns (is_injection, confidence_score)."""
        result = self._pipeline(text[:_MAX_INPUT_CHARS])
        label = result[0]["label"]   # "LABEL_0" or "LABEL_1"
        score = result[0]["score"]
        return (label == "LABEL_1" and score >= _THRESHOLD), score
```

### ACL-03/04: Casbin RBAC with Domains

```python
# Source: https://github.com/pycasbin/async-sqlalchemy-adapter
# hivemind/security/rbac.py

from __future__ import annotations
import casbin
import casbin_async_sqlalchemy_adapter

_enforcer: casbin.AsyncEnforcer | None = None

async def get_enforcer() -> casbin.AsyncEnforcer:
    global _enforcer
    if _enforcer is None:
        from hivemind.config import settings
        adapter = casbin_async_sqlalchemy_adapter.Adapter(settings.database_url)
        _enforcer = casbin.AsyncEnforcer(
            "hivemind/security/rbac_model.conf", adapter
        )
        await _enforcer.load_policy()
    return _enforcer

async def enforce(subject: str, domain: str, obj: str, action: str) -> bool:
    """Check if subject can perform action on obj within domain."""
    e = await get_enforcer()
    return await e.enforce(subject, domain, obj, action)
```

### SEC-03/INFRA-04: Rate Limiting Setup

```python
# Source: https://github.com/long2ice/fastapi-limiter
# hivemind/security/rate_limit.py

from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as aioredis

TIER_LIMITS = {
    "free":       10,   # requests per minute for add_knowledge
    "pro":        60,
    "enterprise": 300,
}

async def init_rate_limiter(redis_url: str) -> None:
    """Call in server lifespan."""
    r = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r)

async def get_api_key_identifier(request: Request) -> str:
    """Use '{org_id}:{agent_id}' as the rate limit bucket key."""
    # Extract from JWT claims already decoded by auth layer
    auth_header = request.headers.get("authorization", "")
    token = auth_header[len("Bearer "):]
    from hivemind.server.auth import decode_token
    ctx = decode_token(token)
    return f"{ctx.org_id}:{ctx.agent_id}"
```

### INFRA-03: Webhook Celery Task

```python
# hivemind/webhooks/tasks.py
from celery import Celery
import httpx

celery_app = Celery("hivemind")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def deliver_webhook(self, webhook_url: str, payload: dict) -> None:
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(webhook_url, json=payload)
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| llm-guard wrapper | Direct `transformers` pipeline | Python 3.14 requirement | Same DeBERTa model; no llm-guard overhead |
| Single-pass PII stripping | Two-pass with verbatim check + markdown-aware | Phase 2 (this phase) | Eliminates residual leaks and code-block PII contamination |
| JWT-only auth (org_id, agent_id) | API key table + JWT (tier, billing, rate counters) | Phase 2 | Enables commercial tiers and per-key analytics |
| Flat permission check (org_id == token.org_id) | Casbin RBAC at namespace/category/item level | Phase 2 | Enables multi-role orgs and granular access |
| No webhook delivery | Celery async webhook push post-approval | Phase 2 (INFRA-03) | External agents notified within seconds |
| pgvector direct access | GraphDriver abstraction + FalkorDB option | Phase 2 (INFRA-02) | Backend-agnostic; enables graph-native queries |

**Not deprecated:**
- JWT (`python-jose`) remains for request authentication — API keys are an *additional* auth layer, not a replacement
- Presidio + GLiNER remain the core PII engine — Phase 2 adds passes, doesn't replace
- pgvector HNSW index remains the primary search backend

---

## Open Questions

1. **Casbin policy initialization for existing orgs**
   - What we know: On Phase 2 launch, existing orgs have no Casbin policies. All access would be denied.
   - What's unclear: Do we default to permissive (allow all existing agents) or restrictive (deny until policy assigned)?
   - Recommendation: Default permissive for existing orgs — auto-create an `admin` role with full access for any org_id that already has rows in `knowledge_items`. New orgs start with default `contributor` role assignment.

2. **FalkorDB as optional vs. required backend**
   - What we know: INFRA-02 says "first graph backend target: Graphiti-on-FalkorDB." `graphiti-core[falkordb]` installs cleanly on Python 3.14.
   - What's unclear: Does INFRA-02 mean FalkorDB replaces pgvector for knowledge storage, or augments it for graph traversal queries?
   - Recommendation: Treat as augmentation — FalkorDB for relationship graph queries (which agents share knowledge? which categories are related?), pgvector for vector similarity search. Both are operational simultaneously.

3. **Anti-sybil threshold values**
   - What we know: Redis ZSET sliding window can track burst patterns.
   - What's unclear: What burst threshold and window constitute a coordinated campaign? (50 in 60s? 100 in 300s?)
   - Recommendation: Make burst threshold and window configurable via `Settings` (e.g., `HIVEMIND_BURST_THRESHOLD=50`, `HIVEMIND_BURST_WINDOW_SECONDS=60`). Start with conservative values; tune based on observed traffic.

4. **Injection scanner latency impact on add_knowledge**
   - What we know: ~213ms on CPU for deberta-v3-base. The server is async; other requests are not blocked.
   - What's unclear: Whether 213ms latency is acceptable for fire-and-forget `add_knowledge` pattern.
   - Recommendation: Acceptable — `add_knowledge` is already fire-and-forget (agent doesn't wait for review). 213ms is fine. Document it. If it becomes a problem, use `deberta-v3-small-prompt-injection-v2` (faster, slightly less accurate) or ONNX quantization.

5. **Webhook endpoint registration UI/API**
   - What we know: INFRA-03 requires webhook push. Need a place to store webhook URLs.
   - What's unclear: Is webhook registration a CLI command, an API endpoint, or an admin UI?
   - Recommendation: Add `webhook_endpoints` table and a CLI admin command `hivemind webhooks add <url>`. No UI needed in Phase 2.

---

## Sources

### Primary (HIGH confidence)
- Installed packages verified via `pip list` in `.venv` — Python 3.14.3 confirmed
- `transformers 5.1.0`, `torch 2.10.0` — already installed, no new dependency
- `casbin-async-sqlalchemy-adapter` 1.17.0 — dry-run install confirmed clean
- `fastapi-limiter` 0.2.0 — dry-run install confirmed clean
- `graphiti-core[falkordb]` 0.28.0 — dry-run install confirmed clean
- Hugging Face model card: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2
- Graphiti GraphDriver ABC: https://deepwiki.com/getzep/graphiti/7.2-falkordb-driver
- PyCasbin async adapter: https://github.com/pycasbin/async-sqlalchemy-adapter
- fastapi-limiter: https://github.com/long2ice/fastapi-limiter
- Existing codebase: models.py, pii.py, auth.py, add_knowledge.py, search_knowledge.py, main.py (all read)

### Secondary (MEDIUM confidence)
- llm-guard blocked: https://pypi.org/project/llm-guard/ (Python <3.13 confirmed)
- Casbin RBAC with domains: https://casbin.org/docs/adapters/ + https://pypi.org/project/casbin/
- Rate limiting patterns: https://medium.com/@pranavprakash4777/how-i-designed-a-tiered-api-rate-limiter-with-redis-and-fastapi-c6b6fbf447ab
- FalkorDB+Graphiti integration: https://blog.getzep.com/graphiti-knowledge-graphs-falkordb-support/
- Anti-sybil Redis patterns: https://redis.io/learn/howtos/ratelimiting

### Tertiary (LOW confidence — validate before use)
- Two-pass PII validation: no official Presidio documentation found; pattern is engineered from Presidio API primitives. LOW confidence on whether `analyze()` on anonymized text catches materially more residual PII.
- Burst/sybil threshold values: no authoritative source; values are engineering judgment.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages dry-run verified on Python 3.14
- Architecture: HIGH — follows Phase 1 patterns exactly; no framework changes
- Pitfalls: HIGH for Python 3.14 / llm-guard; MEDIUM for others (documented from research and codebase inspection)
- FalkorDB integration depth: MEDIUM — GraphDriver pattern documented; operational tuning unclear

**Research date:** 2026-02-18
**Valid until:** 2026-03-20 (stable libraries; 30 days)
