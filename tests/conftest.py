"""Fixtures partagees par la suite de tests HiveMind.

Regles :
- aucun test ne telecharge un modele ni n'appelle un LLM. Les trois singletons de
  modeles (PII, embeddings, injection) sont remplaces par des doubles poses sur leur
  attribut de classe avant tout import du serveur, sans toucher au code de production ;
- les tests d'outils traversent le vrai transport HTTP (POST /mcp, tools/call) avec un
  jeton Bearer, contre une base PostgreSQL migree a head, creee une fois par session ;
- la base est designee par HIVEMIND_TEST_ADMIN_URL (exemple :
  postgresql://hm:hm@localhost:55432/postgres). Sans elle, les tests qui en dependent
  se sautent proprement.
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

# Doit preceder tout import de hivemind.config : le singleton settings lit
# l'environnement a l'import.
os.environ.setdefault("HIVEMIND_SECRET_KEY", "test-secret-not-for-production")

# ---------------------------------------------------------------------------
# Base de donnees de session : creee et migree avant tout import de hivemind, parce
# que hivemind.db.session construit son moteur a l'import depuis settings.database_url.
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
        raise RuntimeError(f"alembic upgrade head a echoue :\n{_migration.stderr[-3000:]}")
    os.environ["HIVEMIND_DATABASE_URL"] = _async_url
    DATABASE_READY = True

requires_database = pytest.mark.skipif(
    not DATABASE_READY, reason="HIVEMIND_TEST_ADMIN_URL absent : PostgreSQL pgvector requis"
)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    if _TEST_DB_NAME:
        admin = _admin_connection()
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        admin.close()


# ---------------------------------------------------------------------------
# Doubles des modeles
# ---------------------------------------------------------------------------


class FakePIIPipeline:
    """Double du pipeline PII : ne retire rien, ne rejette rien."""

    def strip(self, text: str) -> tuple[str, bool]:
        return text, False


class FakeInjectionScanner:
    """Double du scanner d'injection : rien n'est une injection."""

    def is_injection(self, text: str, *args, **kwargs) -> tuple[bool, float]:
        return False, 0.0


class FakeEmbedder:
    """Double du fournisseur d'embeddings.

    Vecteur deterministe, non nul, unitaire, fonction du texte : le meme texte donne le
    meme vecteur (distance cosinus nulle), deux textes differents donnent deux vecteurs
    quasi orthogonaux. Un vecteur nul rendrait la distance cosinus indefinie cote pgvector.
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
    """Pose les doubles sur les trois singletons avant tout chargement de modele."""
    from hivemind.pipeline import embedder as embedder_module
    from hivemind.pipeline.injection import InjectionScanner
    from hivemind.pipeline.pii import PIIPipeline

    PIIPipeline._instance = FakePIIPipeline()  # type: ignore[assignment]
    InjectionScanner._instance = FakeInjectionScanner()  # type: ignore[assignment]
    embedder_module._EmbedderSingleton._instance = FakeEmbedder()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Clients HTTP en memoire
# ---------------------------------------------------------------------------


async def _async_noop(*args, **kwargs):
    return None


async def _client_for(app):
    import httpx
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app, startup_timeout=60, shutdown_timeout=60) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest.fixture
async def http_client(monkeypatch):
    """Client sur l'application complete, stockage debranche.

    Sert a tester la surface HTTP et le protocole (routes, chemin MCP, tools/list).
    Les etapes du lifespan qui touchent Redis ou PostgreSQL sont neutralisees.
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
    """Client sur l'application complete, stockage branche sur la base de session.

    Seuls Redis (limiteur de debit) et Celery sont neutralises : aucun des sept outils
    n'a besoin d'un broker, et le limiteur n'est actif que si Redis est initialise.
    """
    import hivemind.security.rbac as rbac
    import hivemind.server.main as main

    monkeypatch.setattr(main, "init_rate_limiter", _async_noop)
    monkeypatch.setattr(main, "configure_celery", lambda *args, **kwargs: None)
    rbac._enforcer = None  # politiques rechargees depuis la base au premier appel

    async for client in _client_for(main.create_app()):
        yield client


# ---------------------------------------------------------------------------
# Base : acces SQL direct et nettoyage entre tests
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
    """Execute une requete SQL sur la base de test et renvoie toutes les lignes."""
    import psycopg2

    if not DATABASE_READY:
        pytest.skip("HIVEMIND_TEST_ADMIN_URL absent : PostgreSQL pgvector requis")
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
# Jetons et appels d'outils
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
    """POST tools/call sur /mcp et renvoie l'objet `result` JSON-RPC."""
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
    assert "result" in payload, f"erreur JSON-RPC : {payload.get('error')}"
    return payload["result"]


def tool_ok(result: dict) -> dict:
    """Le resultat d'outil doit etre un succes ; renvoie sa charge utile."""
    assert result.get("isError") is not True, result["content"][0]["text"][:400]
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and "result" in structured and len(structured) == 1:
        return structured["result"]
    if isinstance(structured, dict):
        return structured
    return json.loads(result["content"][0]["text"])


def tool_error(result: dict) -> str:
    """Le resultat doit etre un refus au sens MCP (isError vrai) ; renvoie son texte."""
    assert result.get("isError") is True, (
        "l'outil a renvoye un succes au niveau JSON-RPC ; "
        f"contenu : {result['content'][0]['text'][:300]}"
    )
    return result["content"][0]["text"]


@pytest.fixture
def auto_approve(sql):
    """Une regle d'auto-approbation pour org-a : add_knowledge ecrit alors dans knowledge_items."""
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
    """Un item de connaissance approuve, prive, appartenant a org-a / agent-1.

    Cree par l'outil add_knowledge lui-meme, a travers le transport, pour que le handle
    renvoye soit celui qu'un client reel obtiendrait.
    """
    result = await call_tool(
        tool_client, "add_knowledge", {"content": SAMPLE_CONTENT, "category": "general"}, token
    )
    payload = tool_ok(result)
    assert payload["status"] == "auto_approved", payload
    return payload["contribution_id"]
