"""The Alembic migrations apply on an empty database and describe the whole schema.

Requires a PostgreSQL with pgvector, named by HIVEMIND_TEST_ADMIN_URL (for
example: postgresql://hm:hm@localhost:55432/postgres). A throwaway database is
created per test and then dropped.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest

from tests.conftest import ROOT

ADMIN_URL = os.environ.get("HIVEMIND_TEST_ADMIN_URL")

pytestmark = pytest.mark.skipif(
    not ADMIN_URL, reason="HIVEMIND_TEST_ADMIN_URL is unset: PostgreSQL with pgvector is required"
)


@pytest.fixture
def fresh_database():
    import psycopg2

    name = f"hm_test_{uuid.uuid4().hex[:8]}"
    base, _ = ADMIN_URL.rsplit("/", 1)
    admin = psycopg2.connect(ADMIN_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    try:
        yield {
            "sync": f"{base}/{name}",
            "async": f"{base}/{name}".replace("postgresql://", "postgresql+asyncpg://", 1),
        }
    finally:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.close()


def _alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HIVEMIND_DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True
    )


def _tables(sync_url: str) -> set[str]:
    import psycopg2

    with psycopg2.connect(sync_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return {row[0] for row in cur.fetchall()}


def test_upgrade_head_applies_on_empty_database(fresh_database):
    result = _alembic(fresh_database["async"], "upgrade", "head")
    assert result.returncode == 0, result.stderr[-3000:]


def test_upgrade_head_is_idempotent(fresh_database):
    first = _alembic(fresh_database["async"], "upgrade", "head")
    assert first.returncode == 0, first.stderr[-3000:]
    second = _alembic(fresh_database["async"], "upgrade", "head")
    assert second.returncode == 0, second.stderr[-3000:]


def test_schema_covers_every_table_the_server_touches_at_startup(fresh_database):
    result = _alembic(fresh_database["async"], "upgrade", "head")
    assert result.returncode == 0, result.stderr[-3000:]
    tables = _tables(fresh_database["sync"])
    required = {"alembic_version", "deployment_config", "casbin_rule"}
    missing = required - tables
    assert not missing, f"tables missing after upgrade head: {sorted(missing)}"


def test_category_enum_exists_once_with_labels(fresh_database):
    import psycopg2

    result = _alembic(fresh_database["async"], "upgrade", "head")
    assert result.returncode == 0, result.stderr[-3000:]
    with psycopg2.connect(fresh_database["sync"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM pg_type WHERE typname = 'knowledgecategory'")
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'knowledgecategory'"
        )
        assert cur.fetchone()[0] > 0, "the knowledgecategory enum is empty"
