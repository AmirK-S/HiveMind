"""Ce qu'un clone neuf doit trouver pour que docker compose up demarre.

Ces tests sont statiques et tournent hors reseau. Chacun correspond a une
erreur reellement rencontree lors de la mesure du 05/09/2026.
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
    assert _git_ls_files("uv.lock"), "uv.lock n'est pas suivi par git, le Dockerfile fait COPY uv.lock puis uv sync --frozen"


def test_gitignore_excludes_env_and_internal_research():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored, ".env contient des secrets et doit etre ignore"
    assert "deep_research/" in ignored, "deep_research/ est interne et ne doit jamais partir sur le depot public"


def test_compose_environment_uses_hivemind_prefix():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["hivemind"].get("environment") or {}
    keys = list(env) if isinstance(env, dict) else [e.split("=", 1)[0] for e in env]
    bad = [k for k in keys if not k.startswith("HIVEMIND_")]
    assert not bad, f"variables ignorees par Settings (prefixe HIVEMIND_ manquant) : {bad}"


def test_healthchecks_do_not_depend_on_curl():
    """python:3.12-slim n'embarque pas curl : un healthcheck curl echoue toujours."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name, text in (("Dockerfile", dockerfile), ("docker-compose.yml", compose)):
        directives = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        healthcheck_lines = [line for line in directives if "healthcheck" in line.lower() or "test:" in line]
        assert not any("curl" in line for line in healthcheck_lines), f"{name} : healthcheck via curl"


def test_container_runs_migrations_before_serving():
    """Le serveur ecrit en base des le lifespan : les migrations doivent preceder uvicorn."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd_lines = [line for line in dockerfile.splitlines() if line.startswith(("CMD", "ENTRYPOINT"))]
    assert cmd_lines, "ni CMD ni ENTRYPOINT dans le Dockerfile"
    joined = " ".join(cmd_lines)
    assert "uvicorn" not in joined or "alembic" in joined or "entrypoint" in joined.lower(), (
        "le CMD lance uvicorn sans jouer alembic upgrade head"
    )
