"""Fixtures shared by the HiveMind test suite.

Rules:
- no test downloads a model or calls an LLM. The three model singletons (PII,
  embeddings, injection) are replaced by doubles set on their class attribute
  before any import of the server, without touching production code;
- the tool tests cross the real HTTP transport (POST /mcp, tools/call) with a
  Bearer token, against a PostgreSQL database migrated to head and created once
  per session;
- the database is named by HIVEMIND_TEST_ADMIN_URL (for example:
  postgresql://hm:hm@localhost:55432/postgres). Without it, the tests that
  depend on it skip cleanly.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FAKE_DIMENSIONS = 384
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
AUTH_ERROR = "Missing or invalid Authorization header. Expected 'Bearer <token>'."
EXPECTED_TOOLS = {
    "add_knowledge",
    "search_knowledge",
    "list_knowledge",
    "delete_knowledge",
    "publish_knowledge",
    "manage_roles",
    "report_outcome",
}

# Must come before any import of hivemind.config: the settings singleton reads
# the environment at import time.
os.environ.setdefault("HIVEMIND_SECRET_KEY", "test-secret-not-for-production")

# ---------------------------------------------------------------------------
# Session database: created and migrated before any import of hivemind, because
# hivemind.db.session builds its engine at import time from settings.database_url.
# ---------------------------------------------------------------------------

ADMIN_URL = os.environ.get("HIVEMIND_TEST_ADMIN_URL")
DATABASE_READY = False
TEST_DB_SYNC_URL: str | None = None
_TEST_DB_NAME: str | None = None


def _admin_connection():
    import psycopg2

    connection = psycopg2.connect(ADMIN_URL)
    connection.autocommit = True
    return connection


if ADMIN_URL:
    _TEST_DB_NAME = f"hm_tools_{uuid.uuid4().hex[:8]}"
    _base, _ = ADMIN_URL.rsplit("/", 1)
    TEST_DB_SYNC_URL = f"{_base}/{_TEST_DB_NAME}"
    _async_url = TEST_DB_SYNC_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    _admin = _admin_connection()
    with _admin.cursor() as _cur:
        _cur.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    _admin.close()
    _migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "HIVEMIND_DATABASE_URL": _async_url},
        capture_output=True,
        text=True,
    )
    if _migration.returncode != 0:  # pragma: no cover
        raise RuntimeError(f"alembic upgrade head failed:\n{_migration.stderr[-3000:]}")
    os.environ["HIVEMIND_DATABASE_URL"] = _async_url
    DATABASE_READY = True

requires_database = pytest.mark.skipif(
    not DATABASE_READY, reason="HIVEMIND_TEST_ADMIN_URL is unset: PostgreSQL with pgvector is required"
)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    if _TEST_DB_NAME:
        admin = _admin_connection()
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        admin.close()


# ---------------------------------------------------------------------------
# Model doubles
# ---------------------------------------------------------------------------


class FakePIIPipeline:
    """PII pipeline double: removes nothing, rejects nothing."""

    def strip(self, text: str) -> tuple[str, bool]:
        return text, False


class FakeInjectionScanner:
    """Injection scanner double: nothing is an injection."""

    def is_injection(self, text: str, *args, **kwargs) -> tuple[bool, float]:
        return False, 0.0


class FakeEmbedder:
    """Embedding provider double.

    A deterministic, non-zero, unit vector derived from the text: the same text
    gives the same vector (zero cosine distance), two different texts give two
    nearly orthogonal vectors. A zero vector would make the cosine distance
    undefined on the pgvector side.
    """

    def embed(self, text: str) -> list[float]:
        generator = random.Random(text)
        values = [generator.uniform(-1.0, 1.0) for _ in range(FAKE_DIMENSIONS)]
        norm = sum(v * v for v in values) ** 0.5
        return [v / norm for v in values]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    @property
    def model_id(self) -> str:
        return "tests/fake-embedder"

    @property
    def model_revision(self) -> str | None:
        return "0"

    @property
    def dimensions(self) -> int:
        return FAKE_DIMENSIONS


@pytest.fixture(scope="session", autouse=True)
def model_doubles() -> None:
    """Set the doubles on the three singletons before any model is loaded."""
    from hivemind.pipeline import embedder as embedder_module
    from hivemind.pipeline.injection import InjectionScanner
    from hivemind.pipeline.pii import PIIPipeline

    PIIPipeline._instance = FakePIIPipeline()  # type: ignore[assignment]
    InjectionScanner._instance = FakeInjectionScanner()  # type: ignore[assignment]
    embedder_module._EmbedderSingleton._instance = FakeEmbedder()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# In-memory HTTP clients
# ---------------------------------------------------------------------------


async def _async_noop(*args, **kwargs):
    return None


async def _client_for(app):
    import httpx
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app, startup_timeout=60, shutdown_timeout=60) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            yield client


@pytest.fixture
async def http_client(monkeypatch):
    """Client on the full application, storage disconnected.

    Used to test the HTTP surface and the protocol (routes, MCP path,
    tools/list). The lifespan steps that touch Redis or PostgreSQL are stubbed
    out.
    """
    import hivemind.server.main as main

    monkeypatch.setattr(main, "init_rate_limiter", _async_noop)
    monkeypatch.setattr(main, "init_enforcer", _async_noop)
    monkeypatch.setattr(main, "_store_deployment_config", _async_noop)
    monkeypatch.setattr(main, "configure_celery", lambda *args, **kwargs: None)

    async for client in _client_for(main.create_app()):
        yield client


@pytest.fixture
async def tool_client(monkeypatch, clean_tables):  # noqa: ARG001
    """Client on the full application, storage wired to the session database.

    Only Redis (rate limiter) and Celery are stubbed out: none of the seven tools
    needs a broker, and the limiter is only active once Redis is initialised.
    """
    import hivemind.security.rbac as rbac
    import hivemind.server.main as main

    monkeypatch.setattr(main, "init_rate_limiter", _async_noop)
    monkeypatch.setattr(main, "configure_celery", lambda *args, **kwargs: None)
    rbac._enforcer = None  # policies reloaded from the database on the first call

    async for client in _client_for(main.create_app()):
        yield client


# ---------------------------------------------------------------------------
# Database: direct SQL access and cleanup between tests
# ---------------------------------------------------------------------------

_TABLES_TO_CLEAN = (
    "quality_signals",
    "knowledge_items",
    "pending_contributions",
    "auto_approve_rules",
    "casbin_rule",
)


@pytest.fixture
def sql():
    """Run one SQL query against the test database and return every row."""
    import psycopg2

    if not DATABASE_READY:
        pytest.skip("HIVEMIND_TEST_ADMIN_URL is unset: PostgreSQL with pgvector is required")
    connection = psycopg2.connect(TEST_DB_SYNC_URL)
    connection.autocommit = True

    def run(query: str, params: tuple = ()):
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    yield run
    connection.close()


@pytest.fixture
def clean_tables(sql):
    sql(f"TRUNCATE {', '.join(_TABLES_TO_CLEAN)} CASCADE")
    yield


# ---------------------------------------------------------------------------
# Tokens and tool calls
# ---------------------------------------------------------------------------

ORG_A = "org-a"
ORG_B = "org-b"
AGENT_1 = "agent-1"
AGENT_2 = "agent-2"


def make_token(org_id: str, agent_id: str) -> str:
    from hivemind.server.auth import create_token

    return create_token(org_id, agent_id)


@pytest.fixture
def token() -> str:
    return make_token(ORG_A, AGENT_1)


@pytest.fixture
def other_org_token() -> str:
    return make_token(ORG_B, AGENT_1)


@pytest.fixture
def other_agent_token() -> str:
    return make_token(ORG_A, AGENT_2)


async def call_tool(client, name: str, arguments: dict, token: str | None = None) -> dict:
    """POST tools/call on /mcp and return the JSON-RPC `result` object."""
    headers = dict(MCP_HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = await client.post("/mcp", json=body, headers=headers)
    assert response.status_code == 200, f"{response.status_code} {response.text[:300]}"
    payload = response.json()
    assert "result" in payload, f"JSON-RPC error: {payload.get('error')}"
    return payload["result"]


def tool_ok(result: dict) -> dict:
    """The tool result must be a success; return its payload."""
    assert result.get("isError") is not True, result["content"][0]["text"][:400]
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and "result" in structured and len(structured) == 1:
        return structured["result"]
    if isinstance(structured, dict):
        return structured
    return json.loads(result["content"][0]["text"])


def tool_error(result: dict) -> str:
    """The result must be an MCP-level refusal (isError true); return its text."""
    assert result.get("isError") is True, (
        "the tool returned a success at the JSON-RPC level; "
        f"content: {result['content'][0]['text'][:300]}"
    )
    return result["content"][0]["text"]


@pytest.fixture
def auto_approve(sql):
    """An auto-approve rule for org-a: add_knowledge then writes into knowledge_items."""
    sql(
        "INSERT INTO auto_approve_rules (id, org_id, category, is_auto_approve, created_at, updated_at) "
        "VALUES (gen_random_uuid(), %s, 'general', true, now(), now())",
        (ORG_A,),
    )


SAMPLE_CONTENT = (
    "On FastAPI 0.115 a response_model set to a Pydantic model with exclude_none only "
    "drops None values at the top level; nested None fields are kept."
)


@pytest.fixture
async def approved_item(tool_client, token, auto_approve):  # noqa: ARG001
    """An approved, private knowledge item owned by org-a / agent-1.

    Created by the add_knowledge tool itself, through the transport, so that the
    handle returned is the one a real client would obtain.
    """
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}, token
    )
    payload = tool_ok(result)
    assert payload["status"] == "auto_approved", payload
    return payload["contribution_id"]
