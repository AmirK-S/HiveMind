"""Configuration is only read under the HIVEMIND_ prefix.

The original docker-compose passed DATABASE_URL and REDIS_URL without a prefix,
and the container silently connected to itself. These tests pin the contract and
check that .env.example does not repeat the mistake.
"""

from __future__ import annotations

import re

import pytest

from tests.conftest import ROOT


def _settings_without_dotenv(monkeypatch, **env: str):
    from hivemind.config import Settings

    for key in ("DATABASE_URL", "REDIS_URL", "HIVEMIND_DATABASE_URL", "HIVEMIND_REDIS_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_prefixed_variable_overrides_default(monkeypatch):
    settings = _settings_without_dotenv(
        monkeypatch, HIVEMIND_DATABASE_URL="postgresql+asyncpg://u:p@db:5432/x"
    )
    assert settings.database_url == "postgresql+asyncpg://u:p@db:5432/x"


def test_unprefixed_variable_is_ignored(monkeypatch):
    settings = _settings_without_dotenv(
        monkeypatch, DATABASE_URL="postgresql+asyncpg://u:p@db:5432/should-be-ignored"
    )
    assert "should-be-ignored" not in settings.database_url


def test_env_example_exists_at_root():
    assert (ROOT / ".env.example").is_file(), ".env.example is missing at the root; the README and the compose file assume it"


def test_env_example_keys_are_prefixed_and_known():
    from hivemind.config import Settings

    path = ROOT / ".env.example"
    if not path.is_file():
        pytest.skip("covered by test_env_example_exists_at_root")
    known = {f"HIVEMIND_{name.upper()}" for name in Settings.model_fields}
    keys = re.findall(r"^\s*#?\s*([A-Z_][A-Z0-9_]*)\s*=", path.read_text(encoding="utf-8"), flags=re.M)
    assert keys, ".env.example declares no variable"
    unknown = [k for k in keys if k not in known]
    assert not unknown, f"variables unknown to Settings or missing the HIVEMIND_ prefix: {unknown}"
