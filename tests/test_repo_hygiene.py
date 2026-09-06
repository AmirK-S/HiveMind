"""What a fresh clone must find for docker compose up to start.

These tests are static and run offline. Each one matches an error actually hit
during the run of 2026-09-05.
"""

from __future__ import annotations

import subprocess

import yaml

from tests.conftest import ROOT


def _git_ls_files(path: str) -> str:
    return subprocess.run(
        ["git", "ls-files", "--error-unmatch", path], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()


def test_uv_lock_is_tracked():
    assert _git_ls_files("uv.lock"), "uv.lock is not tracked by git; the Dockerfile does COPY uv.lock then uv sync --frozen"


def test_gitignore_excludes_env_and_internal_research():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored, ".env holds secrets and must be ignored"
    assert "deep_research/" in ignored, "deep_research/ is internal and must never reach the public repository"


def test_compose_environment_uses_hivemind_prefix():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["hivemind"].get("environment") or {}
    keys = list(env) if isinstance(env, dict) else [e.split("=", 1)[0] for e in env]
    bad = [k for k in keys if not k.startswith("HIVEMIND_")]
    assert not bad, f"variables ignored by Settings (missing HIVEMIND_ prefix): {bad}"


def test_healthchecks_do_not_depend_on_curl():
    """python:3.12-slim ships no curl: a curl healthcheck always fails."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name, text in (("Dockerfile", dockerfile), ("docker-compose.yml", compose)):
        directives = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        healthcheck_lines = [line for line in directives if "healthcheck" in line.lower() or "test:" in line]
        assert not any("curl" in line for line in healthcheck_lines), f"{name}: healthcheck through curl"


def test_container_runs_migrations_before_serving():
    """The server writes to the database from the lifespan on: migrations must precede uvicorn."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd_lines = [line for line in dockerfile.splitlines() if line.startswith(("CMD", "ENTRYPOINT"))]
    assert cmd_lines, "neither CMD nor ENTRYPOINT in the Dockerfile"
    joined = " ".join(cmd_lines)
    assert "uvicorn" not in joined or "alembic" in joined or "entrypoint" in joined.lower(), (
        "the CMD starts uvicorn without running alembic upgrade head"
    )
