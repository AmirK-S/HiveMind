"""Fixtures partagees par la suite de tests HiveMind.

Regle : aucun test ne telecharge un modele ni n'appelle un LLM. Les trois
singletons de modeles (PII, embeddings, injection) sont remplaces par des
doubles poses sur leur attribut de classe avant tout import du serveur, sans
toucher au code de production. Les tests qui exigent PostgreSQL lisent
HIVEMIND_TEST_ADMIN_URL et se sautent proprement s'il est absent.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Doit preceder tout import de hivemind.config : le singleton settings lit
# l'environnement a l'import.
os.environ.setdefault("HIVEMIND_SECRET_KEY", "test-secret-not-for-production")

ROOT = Path(__file__).resolve().parent.parent
FAKE_DIMENSIONS = 384


class FakePIIPipeline:
    """Double du pipeline PII : ne retire rien, ne rejette rien."""

    def strip(self, text: str) -> tuple[str, bool]:
        return text, False


class FakeInjectionScanner:
    """Double du scanner d'injection : rien n'est une injection."""

    def is_injection(self, text: str, *args, **kwargs) -> tuple[bool, float]:
        return False, 0.0


class FakeEmbedder:
    """Double du fournisseur d'embeddings : vecteur constant de la bonne dimension."""

    def embed(self, text: str) -> list[float]:
        return [0.0] * FAKE_DIMENSIONS

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * FAKE_DIMENSIONS for _ in texts]

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


@pytest.fixture
async def http_client(monkeypatch):
    """Client HTTP en memoire sur l'application complete, lifespan MCP inclus.

    Les etapes du lifespan qui touchent Redis ou PostgreSQL sont neutralisees :
    ce client sert a tester la surface HTTP et le protocole, pas le stockage.
    """
    import httpx
    from asgi_lifespan import LifespanManager

    import hivemind.server.main as main

    async def _async_noop(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "init_rate_limiter", _async_noop)
    monkeypatch.setattr(main, "init_enforcer", _async_noop)
    monkeypatch.setattr(main, "_store_deployment_config", _async_noop)
    monkeypatch.setattr(main, "configure_celery", lambda *args, **kwargs: None)

    app = main.create_app()
    async with LifespanManager(app, startup_timeout=60, shutdown_timeout=60) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
