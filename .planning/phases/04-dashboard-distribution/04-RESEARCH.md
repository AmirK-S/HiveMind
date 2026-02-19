# Phase 4: Dashboard & Distribution - Research

**Researched:** 2026-02-19
**Domain:** Next.js 15 App Router + FastAPI SSE, MCP distribution, framework wrappers (LangChain/CrewAI/OpenClaw), Docker publishing, demo GIF creation
**Confidence:** HIGH for core stack; MEDIUM for OpenClaw SKILL.md details and registry submission mechanics

---

## Summary

Phase 4 divides into two distinct work streams: (1) a web dashboard built with Next.js 15 + shadcn/ui that consumes the existing FastAPI backend via REST + SSE for real-time feeds, and (2) a distribution layer that makes HiveMind discoverable and installable in under 5 minutes. Both streams build entirely on the existing FastAPI + PostgreSQL + Redis backend — no new backend infrastructure is needed.

For the dashboard, the standard pattern in 2026 is Next.js 15 App Router + shadcn/ui + Tailwind v4 + TanStack Query for REST data, with SSE via `EventSource` for live feeds. The FastAPI backend needs a single new SSE streaming endpoint (`/api/v1/stream/feed`) backed by PostgreSQL LISTEN/NOTIFY or Redis pub-sub. For approval workflows and analytics (DASH-03, DASH-05), the existing REST endpoints require new routes. Real-time metrics (DASH-06) are best served by periodic SWR polling (1-5 second intervals) rather than SSE, which avoids connection proliferation.

For distribution, the `npx -y hivemind-mcp` pattern is the MCP ecosystem standard. The npx wrapper is a thin Node.js shim that proxies stdio to the FastAPI HTTP endpoint via `mcp-remote`. Docker images use a multi-stage build with `python:3.12-slim` and uv for fast, reproducible layers. Framework wrappers (LangChain `BaseRetriever`, CrewAI `BaseTool`) are both simple thin HTTP clients calling the existing `/api/v1/knowledge/search` endpoint. OpenClaw uses a `SKILL.md` in AgentSkills format. Registry submissions are mostly PR/form-based with no programmatic API.

**Primary recommendation:** Build the dashboard as a standalone Next.js 15 app at `dashboard/` in the repo root, proxy all API calls through Next.js route handlers (avoids CORS, centralizes auth), and add SSE endpoint to FastAPI using `sse-starlette` 3.x with PostgreSQL LISTEN/NOTIFY. Publish all distribution artifacts (npx package, Docker, framework wrappers) as part of a single GitHub Actions release workflow.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | Private namespace feed + public commons feed; public commons is prominent | SSE via FastAPI `sse-starlette` + PostgreSQL LISTEN/NOTIFY; Next.js EventSource in `use client` component; two named event streams (`private` / `public`) |
| DASH-02 | Search the knowledge commons from the dashboard | Existing `GET /api/v1/knowledge/search` endpoint; TanStack Query with debounced input; no new backend work required |
| DASH-03 | Per-user and per-org contribution + retrieval statistics; reciprocity ledger | New `GET /api/v1/stats/org` and `GET /api/v1/stats/user` endpoints reading from `knowledge_items` + `quality_signals` tables; SWR polling |
| DASH-04 | Knowledge item detail with full provenance | Existing `GET /api/v1/knowledge/{item_id}`; renders all provenance fields (source_agent_id, contributed_at, content_hash, org_attribution) |
| DASH-05 | Approve/reject pending contributions from dashboard | New `POST /api/v1/contributions/{id}/approve` and `POST /api/v1/contributions/{id}/reject` endpoints (mirrors existing CLI review logic); optimistic UI update |
| DASH-06 | Public commons health metrics: total items, growth rate, retrieval volume, domains covered | New `GET /api/v1/stats/commons` endpoint; Recharts AreaChart + BarChart; SWR polling every 30s |
| DIST-01 | npx one-liner install for MCP server | Thin Node.js package `hivemind-mcp` published to npm; uses `mcp-remote` to proxy stdio → HTTP; config: `npx -y hivemind-mcp --url https://... --key API_KEY` |
| DIST-02 | Docker image on Docker Hub | Multi-stage Dockerfile with `python:3.12-slim` + uv; GitHub Actions `docker/build-push-action@v6`; tags: `latest`, semver |
| DIST-03 | Install configs for all major MCP clients in README | Standard `mcpServers` JSON format; clients: Claude Desktop, Cursor, VS Code, ChatGPT Desktop, Windsurf, Gemini CLI |
| DIST-04 | Smithery.ai one-click hosted install listing | Submit via `smithery mcp publish <url>` CLI or smithery.ai/new; provide `/.well-known/mcp/server-card.json` with tools metadata |
| DIST-05 | OpenClaw skill wrapper (SKILL.md format) | SKILL.md with YAML frontmatter (name, description); instructions teach agent to call HiveMind REST API; single-line frontmatter keys only |
| DIST-06 | Submit to 6 MCP discovery directories | PulseMCP: pulsemcp.com/submit (form); Glama.ai: `glama.json` in repo root; mcp.so: GitHub issue; AwesomeClaude.ai: curated list; official MCP Registry: PR to modelcontextprotocol/registry; punkpeye/awesome-mcp-servers: PR with standard format |
| DIST-07 | LangChain HiveMindRetriever published to PyPI | Subclass `langchain_core.retrievers.BaseRetriever`; implement `_get_relevant_documents` + `_aget_relevant_documents`; separate pyproject.toml at `wrappers/langchain/`; publish with hatch |
| DIST-08 | CrewAI HiveMindTool published to PyPI or distributed | Subclass `crewai.tools.BaseTool`; implement `_run` (sync) + optionally `_arun` (async) via httpx; Pydantic `args_schema`; separate pyproject.toml at `wrappers/crewai/` |
| DIST-09 | 30-second demo GIF in README | Use VHS (charmbracelet/vhs) with `.tape` file; requires ffmpeg + ttyd; shows two agents sharing knowledge via MCP in Claude Desktop or Cursor |

</phase_requirements>

---

## Standard Stack

### Core (Dashboard)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15.x | App Router, SSR, route handlers | Pre-build decision; standard for React dashboards |
| shadcn/ui | latest (2025) | Component library (copy-into-project) | No version lock-in; owns the code; Tailwind-native |
| Tailwind CSS | v4 | Styling | Paired with shadcn/ui; Tailwind v4 is current |
| TanStack Query | v5 | Server state, REST data fetching | Best for dashboards with mutations + cache invalidation |
| SWR | v2 | Polling-based metrics | Lighter weight for pure read dashboards (DASH-06 metrics) |
| Recharts | v2 | Charts (AreaChart, BarChart, LineChart) | SVG-based, React-native, most popular in 2025 dashboards |
| react-use-websocket | latest | `useEventSource` hook for SSE | Clean typed SSE consumption in React; named event support |

### Core (Backend SSE Extension)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | 3.2.0 (Jan 2026) | SSE endpoint via `EventSourceResponse` | Production-ready W3C SSE; native FastAPI/Starlette; auto disconnect detection |
| asyncpg | >=0.30.0 | PostgreSQL LISTEN/NOTIFY via async connection | Already in `pyproject.toml`; native async PG notifications |

### Core (Distribution)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp-remote | latest npm | Proxies stdio MCP ↔ HTTP/SSE | Standard pattern for npx-installable remote MCP servers |
| docker/build-push-action | v6 | GitHub Actions Docker push | Official Docker action; multi-platform support |
| hatch / hatchling | latest | Python package builds for PyPI | Already in `pyproject.toml`; standard in 2025 Python ecosystem |
| langchain-core | latest | BaseRetriever base class for HiveMindRetriever | Official LangChain integration package |
| crewai | latest | BaseTool base class for HiveMindTool | Official CrewAI tool interface |
| httpx | latest | Async HTTP client in framework wrappers | Already in backend `pyproject.toml`; async-first |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| VHS (charmbracelet/vhs) | latest | Scripted terminal recording to GIF | DIST-09: demo GIF; requires ffmpeg + ttyd; declarative `.tape` file |
| twine | latest | PyPI upload | Fallback if hatch publish is not preferred; `twine upload dist/*` |
| @hey-api/openapi-ts | latest | TypeScript SDK generation from OpenAPI | If TS wrapper needed; already used in Phase 3 research |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette (FastAPI SSE) | WebSockets | SSE is simpler, HTTP/1.1 compatible, no special proxy config; WebSockets need upgrade headers |
| SSE for commons feed | Short polling | SSE holds open connection and pushes; polling creates traffic spikes; SSE better UX |
| TanStack Query | SWR for everything | TanStack Query has better mutation support needed for DASH-05 (approve/reject); use SWR only for simple metrics |
| Recharts | Chart.js (react-chartjs-2) | Recharts is React-native SVG; Chart.js is canvas-based (faster with large datasets) but more setup |
| mcp-remote for npx wrapper | Custom Node.js shim | mcp-remote is maintained and battle-tested; avoids building a proxy from scratch |
| PostgreSQL LISTEN/NOTIFY for SSE | Redis pub-sub | Redis already in stack (Celery broker); either works; LISTEN/NOTIFY avoids extra dependency; Redis scales better for multi-node |

**Installation:**
```bash
# Dashboard
npx create-next-app@latest dashboard --typescript --tailwind --app
npx shadcn@latest init
npm install @tanstack/react-query swr recharts react-use-websocket

# Backend SSE
uv add sse-starlette

# Framework wrappers (per wrapper package)
pip install langchain-core httpx
pip install crewai httpx
```

---

## Architecture Patterns

### Recommended Project Structure
```
dashboard/               # Next.js 15 app (new directory at repo root)
├── src/app/
│   ├── layout.tsx       # Root layout with QueryClientProvider
│   ├── page.tsx         # Redirect to /commons or /dashboard
│   ├── commons/         # Public commons feed (DASH-01 prominent view)
│   │   └── page.tsx
│   ├── dashboard/       # Private namespace feed
│   │   └── page.tsx
│   ├── contributions/   # Pending approval list + detail (DASH-05)
│   │   ├── page.tsx
│   │   └── [id]/page.tsx
│   ├── analytics/       # Reciprocity ledger, stats (DASH-03, DASH-06)
│   │   └── page.tsx
│   └── api/             # Next.js route handlers (proxy to FastAPI)
│       ├── stream/
│       │   └── route.ts # SSE proxy: reads FastAPI SSE, re-streams to browser
│       ├── contributions/
│       │   └── [id]/
│       │       ├── approve/route.ts
│       │       └── reject/route.ts
│       └── stats/
│           └── route.ts
├── src/components/
│   ├── feed/
│   │   ├── FeedItem.tsx
│   │   └── LiveFeed.tsx  # useEventSource consumer
│   ├── charts/
│   │   ├── GrowthChart.tsx   # Recharts AreaChart
│   │   └── DomainChart.tsx   # Recharts BarChart
│   └── contributions/
│       └── ReviewCard.tsx    # Approve/Reject with optimistic update
└── src/lib/
    ├── api.ts            # Typed fetch wrappers (calls Next.js route handlers)
    └── query-client.ts   # TanStack Query client singleton

hivemind/api/routes/
├── knowledge.py          # Existing (Phase 3)
├── outcomes.py           # Existing (Phase 3)
├── contributions.py      # NEW: approve/reject endpoints (DASH-05)
├── stats.py              # NEW: commons + org + user stats (DASH-03, DASH-06)
└── stream.py             # NEW: SSE feed endpoint (DASH-01)

wrappers/
├── langchain/
│   ├── pyproject.toml
│   └── hivemind_langchain/
│       ├── __init__.py
│       └── retriever.py   # HiveMindRetriever(BaseRetriever)
└── crewai/
    ├── pyproject.toml
    └── hivemind_crewai/
        ├── __init__.py
        └── tool.py         # HiveMindTool(BaseTool)

npx/
├── package.json            # "bin": { "hivemind-mcp": "./bin/hivemind.js" }
└── bin/
    └── hivemind.js         # Calls: mcp-remote <url> with env-based config

skills/
└── SKILL.md               # OpenClaw AgentSkills spec
```

### Pattern 1: FastAPI SSE with PostgreSQL LISTEN/NOTIFY
**What:** SSE endpoint that broadcasts new knowledge items as they are approved, using PostgreSQL's native pub-sub.
**When to use:** DASH-01 live feeds. No Redis dependency for push notifications.
**Example:**
```python
# Source: sse-starlette 3.2.0 + asyncpg LISTEN/NOTIFY pattern
# hivemind/api/routes/stream.py

import asyncio
import json
import asyncpg
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from hivemind.api.auth import require_api_key
from hivemind.config import settings

stream_router = APIRouter(prefix="/stream", tags=["stream"])

@stream_router.get("/feed")
async def stream_feed(api_key_record = Depends(require_api_key)):
    org_id = api_key_record.org_id

    async def event_generator():
        conn = await asyncpg.connect(settings.database_url)
        queue: asyncio.Queue = asyncio.Queue()

        async def listener(connection, pid, channel, payload):
            data = json.loads(payload)
            await queue.put(data)

        await conn.add_listener("knowledge_published", listener)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=30)
                    # Route to correct event type: public or private
                    event_type = "public" if item.get("is_public") else "private"
                    if event_type == "private" and item.get("org_id") != org_id:
                        continue
                    yield {"event": event_type, "data": json.dumps(item)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}  # keepalive
        finally:
            await conn.remove_listener("knowledge_published", listener)
            await conn.close()

    return EventSourceResponse(event_generator())
```

The FastAPI backend must emit a NOTIFY after approving a contribution:
```python
# In contributions.py approve handler — after inserting KnowledgeItem:
await session.execute(
    text("SELECT pg_notify('knowledge_published', :payload)"),
    {"payload": json.dumps({"id": str(item.id), "is_public": item.is_public,
                             "org_id": item.org_id, "category": item.category.value})}
)
```

### Pattern 2: Next.js Route Handler as API Proxy
**What:** Next.js route handlers forward requests to FastAPI with the session's API key injected. Avoids CORS config and centralizes auth.
**When to use:** All dashboard API calls. The browser never talks directly to FastAPI.
**Example:**
```typescript
// Source: Next.js 15 App Router Route Handler pattern
// dashboard/src/app/api/contributions/[id]/approve/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const apiKey = req.headers.get("x-api-key") ?? process.env.HIVEMIND_API_KEY;
  const res = await fetch(
    `${process.env.HIVEMIND_API_URL}/api/v1/contributions/${params.id}/approve`,
    {
      method: "POST",
      headers: { "X-API-Key": apiKey! },
    }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
```

### Pattern 3: SSE Consumption in React with useEventSource
**What:** Typed React hook for consuming SSE named events from the proxied route handler.
**When to use:** DASH-01 live feed components.
**Example:**
```typescript
// Source: react-use-websocket useEventSource + Next.js 15 pattern
"use client";
import { useState } from "react";
import { useEventSource } from "react-use-websocket";

interface KnowledgeEvent {
  id: string;
  category: string;
  org_id: string;
  is_public: boolean;
}

export function LiveFeed({ type }: { type: "public" | "private" }) {
  const [items, setItems] = useState<KnowledgeEvent[]>([]);

  useEventSource("/api/stream/feed", {
    events: {
      [type]: (evt) => {
        const item: KnowledgeEvent = JSON.parse(evt.data);
        setItems(prev => [item, ...prev].slice(0, 100)); // keep last 100
      },
      ping: () => {}, // ignore keepalives
    },
  });

  return (
    <ul>
      {items.map(item => (
        <li key={item.id}>{item.category} — {item.org_id}</li>
      ))}
    </ul>
  );
}
```

### Pattern 4: LangChain BaseRetriever Wrapper
**What:** Subclass `langchain_core.retrievers.BaseRetriever` to wrap the `/api/v1/knowledge/search` endpoint as a LangChain-compatible retriever.
**When to use:** DIST-07. Users pass `HiveMindRetriever` to any LangChain chain expecting a retriever.
**Example:**
```python
# Source: langchain_core.retrievers.BaseRetriever API
# wrappers/langchain/hivemind_langchain/retriever.py
from typing import List
import httpx
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

class HiveMindRetriever(BaseRetriever):
    """LangChain retriever that queries HiveMind knowledge commons."""

    base_url: str
    api_key: str
    limit: int = 10
    category: str | None = None

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        resp = httpx.get(
            f"{self.base_url}/api/v1/knowledge/search",
            params={"query": query, "limit": self.limit, "category": self.category},
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
        return [
            Document(
                page_content=r["title"],
                metadata={"id": r["id"], "category": r["category"],
                           "confidence": r["confidence"]}
            )
            for r in results
        ]

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/knowledge/search",
                params={"query": query, "limit": self.limit},
                headers={"X-API-Key": self.api_key},
                timeout=10,
            )
        resp.raise_for_status()
        results = resp.json()["results"]
        return [Document(page_content=r["title"], metadata=r) for r in results]
```

### Pattern 5: CrewAI BaseTool Wrapper
**What:** Subclass `crewai.tools.BaseTool` with a Pydantic `args_schema`.
**When to use:** DIST-08. Agents using CrewAI can add `HiveMindTool` to their tool list.
**Example:**
```python
# Source: CrewAI custom tool docs + httpx async pattern
# wrappers/crewai/hivemind_crewai/tool.py
from typing import Optional, Type
import httpx
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class HiveMindSearchInput(BaseModel):
    query: str = Field(..., description="The search query")
    category: Optional[str] = Field(None, description="Optional category filter")
    limit: int = Field(10, ge=1, le=50)

class HiveMindTool(BaseTool):
    name: str = "hivemind_search"
    description: str = (
        "Search the HiveMind shared knowledge commons. "
        "Returns relevant knowledge items that agents have shared."
    )
    args_schema: Type[BaseModel] = HiveMindSearchInput
    base_url: str
    api_key: str

    def _run(self, query: str, category: Optional[str] = None, limit: int = 10) -> str:
        resp = httpx.get(
            f"{self.base_url}/api/v1/knowledge/search",
            params={"query": query, "limit": limit, "category": category},
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
        if not results:
            return "No relevant knowledge found."
        return "\n".join(
            f"[{r['category']}] {r['title']} (confidence: {r['confidence']:.2f})"
            for r in results
        )
```

### Pattern 6: OpenClaw SKILL.md
**What:** SKILL.md in AgentSkills format teaches OpenClaw agents how to call HiveMind.
**When to use:** DIST-05.
**Example:**
```markdown
---
name: hivemind
description: Search and contribute to the HiveMind shared knowledge commons
user-invocable: true
metadata: {"homepage": "https://github.com/your-org/hivemind"}
---

# HiveMind Knowledge Commons

Use this skill to search or contribute knowledge via the HiveMind REST API.

## Search
GET {config.base_url}/api/v1/knowledge/search?query=<query>&limit=10
Header: X-API-Key: {config.api_key}

## Add Knowledge
Use the HiveMind MCP tool `add_knowledge` if connected via MCP transport.
```

**Important:** Frontmatter keys must be single-line only (parser limitation). The `metadata` value must be a single-line JSON object.

### Pattern 7: npx Wrapper Package
**What:** Thin Node.js package that starts `mcp-remote` proxying stdio → HiveMind HTTP endpoint.
**When to use:** DIST-01 one-liner install.
**Example:**
```javascript
// npx/bin/hivemind.js  (shebang: #!/usr/bin/env node)
const { spawn } = require('child_process');
const url = process.env.HIVEMIND_URL || process.argv[2];
const apiKey = process.env.HIVEMIND_API_KEY || process.argv[3];

if (!url) {
  console.error('Usage: npx hivemind-mcp <url> [api-key]');
  process.exit(1);
}

const headers = apiKey ? `X-API-Key:${apiKey}` : undefined;
const args = ['mcp-remote', url + '/mcp', ...(headers ? ['--header', headers] : [])];
const child = spawn('npx', ['-y', ...args], { stdio: 'inherit' });
child.on('exit', (code) => process.exit(code ?? 0));
```

```json
// npx/package.json
{
  "name": "hivemind-mcp",
  "version": "0.1.0",
  "bin": { "hivemind-mcp": "./bin/hivemind.js" },
  "dependencies": { "mcp-remote": "latest" }
}
```

Claude Desktop config:
```json
{
  "mcpServers": {
    "hivemind": {
      "command": "npx",
      "args": ["-y", "hivemind-mcp"],
      "env": {
        "HIVEMIND_URL": "https://your-hivemind.com",
        "HIVEMIND_API_KEY": "your-key"
      }
    }
  }
}
```

### Anti-Patterns to Avoid
- **SSE without keepalives:** Proxies (nginx, AWS ALB) close idle SSE connections after 60s. Always emit a `ping` event every 25-30 seconds.
- **SSE for everything real-time:** DASH-03 and DASH-06 metrics don't need SSE. Use SWR polling (refreshInterval: 30000) — fewer open connections, simpler logic.
- **Direct browser → FastAPI calls from Next.js dashboard:** Use Next.js route handlers as a proxy. Avoids CORS, centralizes API key handling, single auth point.
- **asyncpg LISTEN in a shared SQLAlchemy session:** LISTEN/NOTIFY requires a dedicated asyncpg connection (not a SQLAlchemy `async with get_session()`). Use `asyncpg.connect()` directly in the SSE generator.
- **Blocking httpx calls in async CrewAI `_arun`:** Use `httpx.AsyncClient()` as async context manager, not `httpx.get()` (which blocks the event loop).
- **Publishing framework wrappers as part of the main `hivemind` package:** Keep them as separate packages in `wrappers/langchain/` and `wrappers/crewai/` with their own `pyproject.toml`. This lets users install only what they need and avoids LangChain/CrewAI as mandatory deps.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE response format | Custom StreamingResponse subclass | `sse-starlette` 3.2.0 `EventSourceResponse` | Handles W3C spec formatting, client disconnect detection, reconnect IDs, graceful shutdown |
| Proxying stdio ↔ HTTP for npx | Custom Node.js MCP proxy | `mcp-remote` npm package | Battle-tested; handles MCP protocol framing, auth headers, reconnection |
| LangChain retriever interface | Custom callable class | `BaseRetriever` subclass | Required for compatibility with LangChain chains, RAG pipelines, and LangSmith tracing |
| CrewAI tool interface | Custom function | `BaseTool` subclass with `args_schema` | Required for CrewAI agent integration, caching, and event bus hooks |
| Chart components | Custom SVG/Canvas charts | Recharts (AreaChart, BarChart, LineChart) | Responsive, React-native, accessible out of the box |
| Demo GIF recording | Screen recording + manual editing | VHS (charmbracelet/vhs) `.tape` file | Scripted + reproducible; CI-friendly via `charmbracelet/vhs-action` |
| Docker Hub publish workflow | Manual `docker push` | `docker/build-push-action@v6` in GitHub Actions | Multi-platform (amd64/arm64), metadata extraction, SBOM/provenance |

**Key insight:** Every "hand-rolled" item in this phase has a purpose-built tool. The distribution surface (npm, PyPI, Docker, directories) has established conventions — fighting them wastes time and creates fragile integrations.

---

## Common Pitfalls

### Pitfall 1: SSE Connection Proliferation on Dashboard
**What goes wrong:** Every tab/component creates its own `EventSource` connection to `/api/stream/feed`. With 10 components, that is 10 open connections to FastAPI.
**Why it happens:** `useEventSource` is typically called once per component without a shared context.
**How to avoid:** Create a single `FeedContext` provider at the app level that owns the single `EventSource` connection. Distribute events via React context to all subscribed components.
**Warning signs:** Network tab showing multiple `text/event-stream` requests to the same endpoint.

### Pitfall 2: asyncpg LISTEN in SQLAlchemy Session
**What goes wrong:** `asyncpg`'s `LISTEN` command requires the connection to be in a persistent idle state, waiting for notifications. SQLAlchemy sessions are designed for transactional use and return connections to the pool after the transaction. Mixing them causes `asyncpg.exceptions.InterfaceError`.
**Why it happens:** Assuming `get_session()` is equivalent to a raw `asyncpg.connect()`.
**How to avoid:** Use `asyncpg.connect(dsn)` directly in the SSE generator. Close the connection in the `finally` block.
**Warning signs:** `InterfaceError: cannot call LISTEN inside a transaction` in logs.

### Pitfall 3: npm Package Name Conflicts
**What goes wrong:** `hivemind-mcp` or `hivemind` may already be taken on npm.
**Why it happens:** Common names are claimed early.
**How to avoid:** Check `npm info hivemind-mcp` before planning the name. Use a scoped package (`@your-org/hivemind-mcp`) as fallback.
**Warning signs:** `npm ERR! 403 Forbidden - You do not have permission to publish`.

### Pitfall 4: CrewAI BaseTool Missing Class in Recent Versions
**What goes wrong:** In CrewAI 0.114.0, `BaseTool` was temporarily moved/renamed, causing import errors.
**Why it happens:** Fast-moving CrewAI releases break the import path.
**How to avoid:** Import from `crewai.tools import BaseTool`. Pin the crewai version in `pyproject.toml` if compatibility issues arise. Test import in CI.
**Warning signs:** `ImportError: cannot import name 'BaseTool' from 'crewai'`.

### Pitfall 5: Next.js Middleware Bypass (CVE-2025-29927)
**What goes wrong:** Attackers can bypass Next.js middleware by manipulating `x-middleware-subrequest` header, exposing unauthenticated dashboard routes.
**Why it happens:** Relying solely on middleware for auth without Route Handler-level verification.
**How to avoid:** Validate the API key or session token in every route handler that returns sensitive data. Middleware is a first line of defense only. Ensure Next.js >= 15.2.3.
**Warning signs:** Running Next.js 15.0.x or 15.1.x without the patch.

### Pitfall 6: Next.js Route Handler SSE Buffering
**What goes wrong:** Some deployments (Vercel serverless, certain nginx configs) buffer SSE responses, causing events to batch and arrive late.
**Why it happens:** Proxy buffering is on by default.
**How to avoid:** Set `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no` headers on the SSE response. For Vercel, SSE works only in Node.js runtime (`export const runtime = 'nodejs'` in route.ts), not Edge runtime.
**Warning signs:** Events arrive in bursts rather than individually; response appears to "hang" until multiple events accumulate.

### Pitfall 7: VHS Demo GIF Machine-Specific
**What goes wrong:** VHS `.tape` files use hardcoded paths or API keys that fail on other machines or CI.
**Why it happens:** Demos are recorded manually on developer machines.
**How to avoid:** Use environment variable substitution in the `.tape` file. Run VHS in Docker via `charmbracelet/vhs-action` in CI so the GIF can be regenerated reproducibly.
**Warning signs:** GIF file is committed but the `.tape` source is not in the repo.

---

## Code Examples

Verified patterns from official sources:

### FastAPI SSE Endpoint (sse-starlette 3.2.0)
```python
# Source: sse-starlette PyPI 3.2.0 docs (Jan 2026)
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

@router.get("/stream/feed")
async def stream_feed():
    async def generator():
        while True:
            event_data = await get_next_event()  # await queue or LISTEN
            yield ServerSentEvent(data=json.dumps(event_data), event="public")

    return EventSourceResponse(generator(), ping=25)  # ping every 25s
```

### Next.js 15 SSE Route Handler
```typescript
// Source: Next.js 15 App Router route handler pattern
// dashboard/src/app/api/stream/feed/route.ts
export const runtime = 'nodejs';  // REQUIRED for SSE; edge runtime won't work

export async function GET(req: Request) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      // Proxy to FastAPI SSE
      const upstream = await fetch(`${process.env.HIVEMIND_API_URL}/api/v1/stream/feed`, {
        headers: { 'X-API-Key': process.env.HIVEMIND_API_KEY! }
      });
      const reader = upstream.body!.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          controller.enqueue(value);
        }
      } finally {
        reader.releaseLock();
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    }
  });
}
```

### Glama.ai Submission (glama.json)
```json
// Source: Glama.ai official blog (2025-07-08)
// Place in repo root: glama.json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["your-github-username"]
}
```

### Smithery server-card.json
```json
// Source: Smithery docs (smithery.ai/docs/build/publish)
// Serve at: /.well-known/mcp/server-card.json
{
  "serverInfo": {
    "name": "hivemind",
    "description": "Shared memory system for AI agents",
    "version": "0.1.0"
  },
  "authentication": {
    "type": "apiKey",
    "in": "header",
    "name": "X-API-Key"
  },
  "tools": [
    { "name": "add_knowledge", "description": "Contribute knowledge to the commons" },
    { "name": "search_knowledge", "description": "Search the knowledge commons" }
  ]
}
```

### Docker Multi-Stage Build (Python + uv)
```dockerfile
# Source: Python Docker multi-stage + uv pattern (2025)
FROM python:3.12-slim AS builder
RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY hivemind/ hivemind/
COPY alembic/ alembic/
COPY alembic.ini .
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "hivemind.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### MCP Client Configs (DIST-03)
```json
// Claude Desktop: ~/Library/Application Support/Claude/claude_desktop_config.json
// Cursor: ~/.cursor/mcp.json
// VS Code: .vscode/mcp.json
{
  "mcpServers": {
    "hivemind": {
      "command": "npx",
      "args": ["-y", "hivemind-mcp"],
      "env": {
        "HIVEMIND_URL": "https://your-hivemind-instance.com",
        "HIVEMIND_API_KEY": "your-api-key"
      }
    }
  }
}
```

### VHS Demo Tape (DIST-09)
```tape
# Source: charmbracelet/vhs docs
Output demo.gif
Set FontSize 14
Set Width 1200
Set Height 600

Type "# Agent 1 contributes knowledge"
Enter
Type "mcp call add_knowledge --content 'FastAPI async context vars work in middleware' --category tooling"
Enter
Sleep 2s

Type "# Agent 2 searches and finds it"
Enter
Type "mcp call search_knowledge --query 'FastAPI middleware context'"
Enter
Sleep 2s
```

---

## Registry Submission Checklists

### DIST-04: Smithery.ai
1. Ensure `/mcp` endpoint is publicly accessible (HTTPS required)
2. Add `/.well-known/mcp/server-card.json` to FastAPI app (serve as static file)
3. Run: `npx smithery mcp publish "https://your-hivemind.com/mcp"`
   - Alternative: submit via smithery.ai/new web form

### DIST-06: Six Registry Submissions
| Directory | Method | URL | Notes |
|-----------|--------|-----|-------|
| PulseMCP | Web form | pulsemcp.com/submit | Fill in name, description, GitHub URL |
| Glama.ai | glama.json in repo root | glama.ai/mcp/servers | Add file, then trigger claim ownership flow |
| mcp.so | GitHub issue | github.com/modelcontextprotocol/servers (or mcp.so GH) | Title: "Add HiveMind MCP server" |
| AwesomeClaude.ai | Curated list | awesomeclaude.ai | Contact or submit via their form |
| Official MCP Registry | PR | github.com/modelcontextprotocol/registry | Follow CONTRIBUTING.md |
| punkpeye/awesome-mcp-servers | PR | github.com/punkpeye/awesome-mcp-servers | Format: name + language indicator + scope tag + description |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSockets for all real-time | SSE for server-push only use cases | 2024-2025 | Simpler, HTTP/1.1 compatible, no special proxy setup |
| react-query v4 | TanStack Query v5 (rebranded) | 2023 | Same API, better TypeScript, devtools v5 |
| poetry for Python packaging | uv + hatchling | 2024-2025 | 10-100x faster; `uv sync --frozen` replaces `poetry install --no-dev` |
| sse-starlette 1.x | sse-starlette 3.2.0 | Jan 2026 | `JSONServerSentEvent`, better disconnect handling |
| CrewAI BaseTool (pre-0.114.0) | `from crewai.tools import BaseTool` | 2024 | BaseTool moved; old import path breaks |

**Deprecated/outdated:**
- `fastapi-sse` PyPI package: Superseded by `sse-starlette` which is the canonical Starlette/FastAPI SSE library. `fastapi-sse` is a lighter wrapper but less maintained.
- Next.js `pages/api/` route handlers: Use `app/api/route.ts` (App Router) in Next.js 15.
- `@hey-api/openapi-ts` for this phase: Not needed unless adding a TypeScript SDK. Phase 3 research already covers SDK generation if needed.

---

## Open Questions

1. **Next.js dashboard deployment target**
   - What we know: Next.js 15 App Router + static export works for Vercel, Docker, or self-hosted
   - What's unclear: Should the dashboard be a standalone deployment or served by FastAPI (as mounted static files)?
   - Recommendation: Start with standalone Next.js app in `dashboard/` directory; mount is fragile and limits Next.js features (SSR, route handlers)

2. **SSE vs Redis pub-sub for live feed**
   - What we know: Both PostgreSQL LISTEN/NOTIFY and Redis pub-sub work; Redis is already in the stack (Celery)
   - What's unclear: Multi-node deployments require Redis pub-sub (each node needs to receive events); LISTEN/NOTIFY is per-connection
   - Recommendation: Implement with PostgreSQL LISTEN/NOTIFY first (simpler, no extra dep); add Redis pub-sub adapter if horizontal scaling is needed

3. **punkpeye/awesome-mcp-servers format details**
   - What we know: Submissions are PRs; each entry uses language/scope tags (e.g., 🐍 Python, ☁️ Cloud)
   - What's unclear: Exact category placement for knowledge management servers
   - Recommendation: Read CONTRIBUTING.md in the repo before writing the PR; category "knowledge & memory" or "productivity" likely

4. **OpenClaw SKILL.md for calling HTTP API vs MCP tool**
   - What we know: SKILL.md teaches agents via instructions; supports REST API calls in the instructions body; metadata must be single-line JSON
   - What's unclear: Whether OpenClaw supports MCP tool invocations natively from SKILL.md (vs REST API calls)
   - Recommendation: Write SKILL.md that teaches REST API usage (unambiguous); note MCP path as alternative if agent is already connected via MCP transport

---

## Sources

### Primary (HIGH confidence)
- `sse-starlette` PyPI 3.2.0 (Jan 2026) — EventSourceResponse API, ServerSentEvent, JSONServerSentEvent
- FastAPI official docs (fastapi.tiangolo.com/deployment/docker) — Docker multi-stage build pattern
- Next.js 15 App Router Route Handlers — SSE ReadableStream pattern, runtime directive
- langchain_core.retrievers API reference (reference.langchain.com) — BaseRetriever interface, _get_relevant_documents signature
- CrewAI custom tools docs (docs.crewai.com/en/learn/create-custom-tools) — BaseTool, args_schema, _run/_arun
- Smithery docs (smithery.ai/docs/build/publish) — server-card.json format, publish CLI command
- Glama.ai blog (glama.ai/blog/2025-07-08-what-is-glamajson) — glama.json format and ownership claim
- PulseMCP (pulsemcp.com) — submission via pulsemcp.com/submit form
- charmbracelet/vhs GitHub — .tape format, ffmpeg/ttyd dependencies, Output command

### Secondary (MEDIUM confidence)
- damianhodgkiss.com SSE + Next.js 15 tutorial — ReadableStream route handler pattern, useEventSource
- tom.catshoek.dev postgres LISTEN/NOTIFY + SSE — asyncpg listener pattern with queue
- docker/build-push-action@v6 GitHub Marketplace — workflow YAML structure
- shadcn/ui + Next.js 15 official install (ui.shadcn.com/docs/installation/next) — standard stack confirmation
- mcp.so FAQ — GitHub issue submission process

### Tertiary (LOW confidence - flag for validation)
- OpenClaw SKILL.md `user-invocable`, `metadata` fields — docs.openclaw.ai partially loaded; DeepWiki secondhand
- AwesomeClaude.ai submission process — no dedicated submission docs found; "curated list" implies manual review
- mcp.so GitHub issue URL — precise GitHub repo URL for submission not confirmed; may be a separate private repo

---

## Metadata

**Confidence breakdown:**
- Standard stack (Next.js, shadcn/ui, sse-starlette, Recharts): HIGH — all verified with official docs or PyPI
- Architecture patterns (SSE + LISTEN/NOTIFY, route handler proxy): HIGH — multiple authoritative sources agree
- Framework wrappers (LangChain, CrewAI): HIGH — official API docs verified
- Distribution mechanics (npm, Docker, registry submissions): MEDIUM — submission forms and URLs verified; exact PR formats LOW
- OpenClaw SKILL.md details: LOW-MEDIUM — official docs partially loaded; frontmatter fields confirmed from secondary source

**Research date:** 2026-02-19
**Valid until:** 2026-03-20 (sse-starlette, CrewAI, and Next.js release frequently; re-verify import paths before implementation)
