"""PII pipeline contract: technical text survives, real PII is removed.

Two stages:
  - TestApiKeyPatterns needs no model and runs in the default suite. It calls
    the in-house PatternRecognizer directly, without AnalyzerEngine, so
    without spacy or GLiNER.
  - TestPipelineContract is marked `models` and needs
    knowledgator/gliner-pii-base-v1.0 (about 400 MB, cached in
    ~/.cache/huggingface) plus the spacy model of the `models` group. Run it
    separately:
        uv run pytest -m models

These tests instantiate PIIPipeline() directly and NOT get_instance(), to work
around the autouse `model_doubles` fixture of conftest.py, which replaces the
singleton with a double that removes nothing.
"""

from __future__ import annotations

import pytest

# Four technical statements that must cross the pipeline word for word.
TECHNICAL_TEXTS = [
    "With asyncpg behind SQLAlchemy 2, a pool_size above the PostgreSQL "
    "max_connections divided by the number of workers gives 'too many clients "
    "already' under load; size the pool per worker, not per service.",
    "psycopg2 in threaded mode leaks connections when the parent process forks; "
    "prefer redis-py 5 with a real connection pool.",
    "FastAPI 0.115 with uvicorn --workers 4 behind nginx: edit "
    "/etc/nginx/nginx.conf and raise proxy_read_timeout to 120 seconds.",
    "pgvector on Kubernetes needs an HNSW index; run pip install httpx first, "
    "then benchmark ivfflat with lists=100.",
]

# P5, a documented known limitation: Prometheus comes out as LOCATION and
# Grafana as PERSON, both at 0.85, from SpacyRecognizer. Prometheus and Grafana
# are still redacted by the spaCy recognizer; removing that recognizer is the
# only measured fix and it was not adopted.
TECHNICAL_TEXT_P5 = (
    "Celery worker metrics land in Prometheus, and the pool_size and "
    "max_overflow of SQLAlchemy show up as gauges in Grafana."
)

# Terms that must appear verbatim in the output. A failing test names the term
# that was erased, which beats comparing two pages of text.
# The terms specific to P5 (Celery, Prometheus, max_overflow, Grafana) are
# deliberately absent: they fall under the known limitation above.
PRESERVED_TERMS = [
    "asyncpg", "SQLAlchemy", "pool_size", "PostgreSQL", "max_connections",
    "psycopg2", "redis-py", "FastAPI", "uvicorn", "nginx", "nginx.conf",
    "proxy_read_timeout", "pgvector", "Kubernetes", "HNSW", "httpx", "ivfflat",
]

# Made-up secrets, none of them ever existed. Each one is assembled at runtime
# so that no single line of the repository carries a complete secret pattern,
# which would trip the push protection of the forge.
ANTHROPIC_KEY_BODY = "Rj7Qm2XvT4bN9wLk1ZsY6pHc3EdA8gUiFo5MrVt0"
ANTHROPIC_KEY = "sk-ant-" + "api03-" + ANTHROPIC_KEY_BODY
OPENAI_PROJECT_KEY = "sk-" + "proj-" + "9d8f7a6b5c4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c"
GITHUB_TOKEN = "ghp" + "_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
DSN_WITH_PASSWORD = "postgresql://admin:" + "Hunter2" + "@db.internal:5432/prod"

EMAIL = "marie.dupont@example.com"
NAME = "Jean Moreau"
ADDRESS = "14 rue de la Paix, 75002 Paris"


# ---------------------------------------------------------------------------
# Stage 1: regex patterns alone, no model
# ---------------------------------------------------------------------------


class TestApiKeyPatterns:
    """The in-house PatternRecognizer, called directly, without AnalyzerEngine."""

    @staticmethod
    def _recognizer():
        from presidio_analyzer import PatternRecognizer

        from hivemind.pipeline.pii import _build_api_key_patterns

        return PatternRecognizer(
            supported_entity="API_KEY", patterns=_build_api_key_patterns()
        )

    @pytest.mark.parametrize(
        "text", [*TECHNICAL_TEXTS, TECHNICAL_TEXT_P5]
    )
    def test_no_pattern_matches_a_technical_statement(self, text: str) -> None:
        results = self._recognizer().analyze(text=text, entities=["API_KEY"])
        assert results == [], (
            "a pattern of _build_api_key_patterns matches technical text: "
            f"{[text[r.start:r.end] for r in results]}"
        )

    @pytest.mark.parametrize(
        ("name", "secret"),
        [
            ("anthropic", ANTHROPIC_KEY),
            ("openai_project", OPENAI_PROJECT_KEY),
            ("github", GITHUB_TOKEN),
            ("aws", AWS_KEY),
            ("dsn", DSN_WITH_PASSWORD),
        ],
    )
    def test_the_declared_formats_are_recognised(self, name: str, secret: str) -> None:
        text = f"The value {secret} appeared in the deploy log."
        results = self._recognizer().analyze(text=text, entities=["API_KEY"])
        assert results, f"format not recognised by the in-house patterns: {name} {secret}"
        assert max(r.score for r in results) >= 0.7
        # The span covers the whole secret, not just a neighbouring fragment.
        assert any(secret in text[r.start:r.end] for r in results), (
            f"the {name} secret is only partially covered: "
            f"{[text[r.start:r.end] for r in results]}"
        )


# ---------------------------------------------------------------------------
# Stage 2: full pipeline, needs GLiNER and spacy
# ---------------------------------------------------------------------------


def _text_with_code_block() -> str:
    """A full DSN, password included, inside a fenced block."""
    return (
        "Set the DSN as follows:\n\n"
        "```python\n"
        f'DSN = "{DSN_WITH_PASSWORD}"\n'
        "```\n\n"
        "then restart the worker."
    )


@pytest.fixture(scope="module")
def pipeline():
    """The real pipeline, loaded once for the module.

    PIIPipeline() and not get_instance(): the autouse `model_doubles` fixture of
    conftest.py has replaced the singleton with an inert double.
    """
    from hivemind.pipeline.pii import PIIPipeline

    return PIIPipeline()


@pytest.mark.models
class TestPipelineContract:
    """End-to-end contract. A single model load for the whole module."""

    @pytest.mark.parametrize("text", TECHNICAL_TEXTS)
    def test_technical_text_is_preserved_word_for_word(self, pipeline, text: str) -> None:
        cleaned, rejected = pipeline.strip(text)
        assert not rejected, "a legitimate technical statement was rejected by the 50% guard"
        assert cleaned == text, (
            "the technical text was modified.\n"
            f"  expected: {text}\n"
            f"  got     : {cleaned}"
        )

    @pytest.mark.xfail(
        reason="SpacyRecognizer still redacts Prometheus and Grafana; the only "
        "measured fix, removing that recognizer, was not adopted",
        strict=True,
    )
    def test_p5_is_preserved_word_for_word(self, pipeline) -> None:
        """Known limitation: Prometheus comes out as LOCATION and Grafana as PERSON."""
        cleaned, _ = pipeline.strip(TECHNICAL_TEXT_P5)
        assert cleaned == TECHNICAL_TEXT_P5

    @pytest.mark.parametrize("term", PRESERVED_TERMS)
    def test_no_library_name_is_erased(self, pipeline, term: str) -> None:
        text = next(t for t in TECHNICAL_TEXTS if term in t)
        cleaned, _ = pipeline.strip(text)
        assert term in cleaned, f"the technical term '{term}' was erased"

    def test_the_email_is_removed(self, pipeline) -> None:
        text = f"Contact the maintainer at {EMAIL} for the migration plan."
        cleaned, _ = pipeline.strip(text)
        assert EMAIL not in cleaned
        assert "marie.dupont" not in cleaned
        assert "[EMAIL]" in cleaned

    def test_the_key_is_removed(self, pipeline) -> None:
        text = f"Use the key {ANTHROPIC_KEY} when calling the API from the worker."
        cleaned, _ = pipeline.strip(text)
        assert ANTHROPIC_KEY not in cleaned
        assert ANTHROPIC_KEY_BODY not in cleaned
        assert "[API_KEY]" in cleaned

    def test_the_name_and_the_address_are_removed(self, pipeline) -> None:
        text = f"{NAME} lives at {ADDRESS}, and owns the runbook."
        cleaned, _ = pipeline.strip(text)
        assert NAME not in cleaned
        assert "Moreau" not in cleaned
        assert "rue de la Paix" not in cleaned
        assert "[NAME]" in cleaned
        assert "[LOCATION]" in cleaned

    def test_no_doubly_bracketed_placeholder(self, pipeline) -> None:
        """Pass 2a must not redact its own placeholders."""
        for text in (
            *TECHNICAL_TEXTS,
            f"{NAME} lives at {ADDRESS}.",
            f"Contact {EMAIL} today.",
            f"Use the key {ANTHROPIC_KEY} now.",
        ):
            cleaned, _ = pipeline.strip(text)
            assert "[[" not in cleaned, f"doubly redacted placeholder: {cleaned}"

    def test_redaction_is_stable_within_one_process(self, pipeline) -> None:
        """Ten successive passes give the same text, hence the same content_hash."""
        from hivemind.pipeline.integrity import compute_content_hash

        text = TECHNICAL_TEXTS[0]
        outputs = [pipeline.strip(text)[0] for _ in range(10)]
        digests = {compute_content_hash(output) for output in outputs}
        assert len(digests) == 1, (
            f"ten calls produced {len(digests)} distinct outputs: "
            f"{sorted(set(outputs))}"
        )

    def test_code_is_preserved(self, pipeline, monkeypatch) -> None:
        """TRUST-06: nothing is removed inside a code block.

        The UUID draw is pinned: left free, this test fails about three times
        out of a hundred, for the reason the next test spells out.
        """
        import uuid

        monkeypatch.setattr(
            uuid, "uuid4", lambda: uuid.UUID("1f0a4c73-5d21-4e88-a0b6-77c9e2d41a5b")
        )
        cleaned, _ = pipeline.strip(_text_with_code_block())
        assert DSN_WITH_PASSWORD in cleaned

    def test_code_is_preserved_even_with_an_unlucky_token(
        self, pipeline, monkeypatch
    ) -> None:
        """Same contract, on a block id the analyzer used to classify PERSON at 0.85.

        Before the _drop_results_over_code_tokens filter, 9 UUID draws out of 300
        lost the whole code block, password included.
        """
        import uuid

        unlucky = uuid.UUID("b2be4e42-bc74-46f6-996a-1165a11cfe5f")
        monkeypatch.setattr(uuid, "uuid4", lambda: unlucky)
        cleaned, _ = pipeline.strip(_text_with_code_block())
        assert DSN_WITH_PASSWORD in cleaned
