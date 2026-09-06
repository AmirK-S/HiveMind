"""Contrat du pipeline PII : le texte technique survit, la vraie PII part.

Deux etages :
  - TestApiKeyPatterns, sans modele, tourne dans la suite par defaut. Il appelle
    le PatternRecognizer maison directement, sans AnalyzerEngine, donc sans
    spacy ni GLiNER.
  - TestPipelineContract, marque `models`, exige knowledgator/gliner-pii-base-v1.0
    (environ 400 Mo, cache dans ~/.cache/huggingface) et le modele spacy du
    groupe `models`. A lancer a part :
        uv run pytest -m models

Ces tests instancient PIIPipeline() directement et NON get_instance(), pour
contourner la fixture autouse `model_doubles` de conftest.py qui remplace le
singleton par un double ne retirant rien.
"""

from __future__ import annotations

import pytest

# Quatre enonces techniques qui doivent traverser le pipeline mot pour mot.
TEXTES_TECHNIQUES = [
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

# P5, documentee comme limite connue : Prometheus sort en LOCATION et Grafana en
# PERSON, tous deux a 0.85, depuis SpacyRecognizer. Seule l'option D du rapport
# E8 les sauve, et elle n'a pas ete retenue.
TEXTE_TECHNIQUE_P5 = (
    "Celery worker metrics land in Prometheus, and the pool_size and "
    "max_overflow of SQLAlchemy show up as gauges in Grafana."
)

# Termes qui doivent apparaitre tels quels dans la sortie. Un test qui echoue
# nomme le terme efface, ce qui vaut mieux qu'une comparaison de deux pages.
# Les termes propres a P5 (Celery, Prometheus, max_overflow, Grafana) sont
# volontairement absents : ils relevent de la limite connue ci-dessus.
TERMES_PRESERVES = [
    "asyncpg", "SQLAlchemy", "pool_size", "PostgreSQL", "max_connections",
    "psycopg2", "redis-py", "FastAPI", "uvicorn", "nginx", "nginx.conf",
    "proxy_read_timeout", "pgvector", "Kubernetes", "HNSW", "httpx", "ivfflat",
]

# Secrets fabriques, aucun n'a jamais existe.
CLE_ANTHROPIC = "sk-ant-api03-Rj7Qm2XvT4bN9wLk1ZsY6pHc3EdA8gUiFo5MrVt0"
CLE_OPENAI_PROJET = "sk-proj-9d8f7a6b5c4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c"
JETON_GITHUB = "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
CLE_AWS = "AKIAIOSFODNN7EXAMPLE"
DSN_AVEC_MOT_DE_PASSE = "postgresql://admin:Hunter2@db.internal:5432/prod"

COURRIEL = "marie.dupont@example.com"
NOM = "Jean Moreau"
ADRESSE = "14 rue de la Paix, 75002 Paris"


# ---------------------------------------------------------------------------
# Etage 1 : motifs regex seuls, sans modele
# ---------------------------------------------------------------------------


class TestApiKeyPatterns:
    """Le PatternRecognizer maison, appele directement, sans AnalyzerEngine."""

    @staticmethod
    def _recognizer():
        from presidio_analyzer import PatternRecognizer

        from hivemind.pipeline.pii import _build_api_key_patterns

        return PatternRecognizer(
            supported_entity="API_KEY", patterns=_build_api_key_patterns()
        )

    @pytest.mark.parametrize(
        "texte", [*TEXTES_TECHNIQUES, TEXTE_TECHNIQUE_P5]
    )
    def test_aucun_motif_ne_touche_un_enonce_technique(self, texte: str) -> None:
        resultats = self._recognizer().analyze(text=texte, entities=["API_KEY"])
        assert resultats == [], (
            "un motif de _build_api_key_patterns matche du texte technique : "
            f"{[texte[r.start:r.end] for r in resultats]}"
        )

    @pytest.mark.parametrize(
        ("nom", "secret"),
        [
            ("anthropic", CLE_ANTHROPIC),
            ("openai_project", CLE_OPENAI_PROJET),
            ("github", JETON_GITHUB),
            ("aws", CLE_AWS),
            ("dsn", DSN_AVEC_MOT_DE_PASSE),
        ],
    )
    def test_les_formats_declares_sont_reconnus(self, nom: str, secret: str) -> None:
        texte = f"The value {secret} appeared in the deploy log."
        resultats = self._recognizer().analyze(text=texte, entities=["API_KEY"])
        assert resultats, f"format non reconnu par les motifs maison : {nom} {secret}"
        assert max(r.score for r in resultats) >= 0.7
        # L'empan couvre bien le secret, pas seulement un fragment voisin.
        assert any(secret in texte[r.start:r.end] for r in resultats), (
            f"le secret {nom} n'est couvert que partiellement : "
            f"{[texte[r.start:r.end] for r in resultats]}"
        )


# ---------------------------------------------------------------------------
# Etage 2 : pipeline complet, exige GLiNER et spacy
# ---------------------------------------------------------------------------


def _texte_avec_bloc_de_code() -> str:
    """Un DSN complet, mot de passe compris, a l'interieur d'un bloc clos."""
    return (
        "Set the DSN as follows:\n\n"
        "```python\n"
        f'DSN = "{DSN_AVEC_MOT_DE_PASSE}"\n'
        "```\n\n"
        "then restart the worker."
    )


@pytest.fixture(scope="module")
def pipeline():
    """Le vrai pipeline, charge une seule fois pour le module.

    PIIPipeline() et non get_instance() : la fixture autouse `model_doubles` de
    conftest.py a remplace le singleton par un double inerte.
    """
    from hivemind.pipeline.pii import PIIPipeline

    return PIIPipeline()


@pytest.mark.models
class TestPipelineContract:
    """Contrat de bout en bout. Un seul chargement de modele pour le module."""

    @pytest.mark.parametrize("texte", TEXTES_TECHNIQUES)
    def test_texte_technique_preserve_mot_pour_mot(self, pipeline, texte: str) -> None:
        nettoye, rejete = pipeline.strip(texte)
        assert not rejete, "un enonce technique legitime a ete rejete par le garde 50 %"
        assert nettoye == texte, (
            "le texte technique a ete modifie.\n"
            f"  attendu : {texte}\n"
            f"  obtenu  : {nettoye}"
        )

    @pytest.mark.xfail(
        reason="SpacyRecognizer, option D non appliquee",
        strict=True,
    )
    def test_p5_preserve_mot_pour_mot(self, pipeline) -> None:
        """Limite connue : Prometheus sort en LOCATION et Grafana en PERSON."""
        nettoye, _ = pipeline.strip(TEXTE_TECHNIQUE_P5)
        assert nettoye == TEXTE_TECHNIQUE_P5

    @pytest.mark.parametrize("terme", TERMES_PRESERVES)
    def test_aucun_nom_de_bibliotheque_n_est_efface(self, pipeline, terme: str) -> None:
        texte = next(t for t in TEXTES_TECHNIQUES if terme in t)
        nettoye, _ = pipeline.strip(texte)
        assert terme in nettoye, f"le terme technique '{terme}' a ete efface"

    def test_le_courriel_est_retire(self, pipeline) -> None:
        texte = f"Contact the maintainer at {COURRIEL} for the migration plan."
        nettoye, _ = pipeline.strip(texte)
        assert COURRIEL not in nettoye
        assert "marie.dupont" not in nettoye
        assert "[EMAIL]" in nettoye

    def test_la_cle_est_retiree(self, pipeline) -> None:
        texte = f"Use the key {CLE_ANTHROPIC} when calling the API from the worker."
        nettoye, _ = pipeline.strip(texte)
        assert CLE_ANTHROPIC not in nettoye
        assert "Rj7Qm2XvT4bN9wLk1ZsY6pHc3EdA8gUiFo5MrVt0" not in nettoye
        assert "[API_KEY]" in nettoye

    def test_le_nom_et_l_adresse_sont_retires(self, pipeline) -> None:
        texte = f"{NOM} lives at {ADRESSE}, and owns the runbook."
        nettoye, _ = pipeline.strip(texte)
        assert NOM not in nettoye
        assert "Moreau" not in nettoye
        assert "rue de la Paix" not in nettoye
        assert "[NAME]" in nettoye
        assert "[LOCATION]" in nettoye

    def test_aucun_marqueur_a_crochets_doubles(self, pipeline) -> None:
        """La passe 2a ne doit pas re-rediger ses propres marqueurs."""
        for texte in (
            *TEXTES_TECHNIQUES,
            f"{NOM} lives at {ADRESSE}.",
            f"Contact {COURRIEL} today.",
            f"Use the key {CLE_ANTHROPIC} now.",
        ):
            nettoye, _ = pipeline.strip(texte)
            assert "[[" not in nettoye, f"marqueur doublement redige : {nettoye}"

    def test_la_redaction_est_stable_dans_un_processus(self, pipeline) -> None:
        """Dix passages successifs donnent le meme texte, donc le meme content_hash."""
        from hivemind.pipeline.integrity import compute_content_hash

        texte = TEXTES_TECHNIQUES[0]
        sorties = [pipeline.strip(texte)[0] for _ in range(10)]
        condenses = {compute_content_hash(s) for s in sorties}
        assert len(condenses) == 1, (
            f"dix appels ont produit {len(condenses)} sorties distinctes : "
            f"{sorted(set(sorties))}"
        )

    def test_le_code_est_preserve(self, pipeline, monkeypatch) -> None:
        """TRUST-06 : rien n'est retire a l'interieur d'un bloc de code.

        Le tirage d'UUID est fige : laisse libre, ce test echoue environ trois
        fois sur cent, pour la raison exposee par le test suivant.
        """
        import uuid

        monkeypatch.setattr(
            uuid, "uuid4", lambda: uuid.UUID("1f0a4c73-5d21-4e88-a0b6-77c9e2d41a5b")
        )
        nettoye, _ = pipeline.strip(_texte_avec_bloc_de_code())
        assert DSN_AVEC_MOT_DE_PASSE in nettoye

    def test_le_code_est_preserve_meme_avec_un_jeton_malheureux(
        self, pipeline, monkeypatch
    ) -> None:
        """Meme contrat, sur un identifiant de bloc que l'analyseur classait PERSON a 0.85.

        Avant le filtre _drop_results_over_code_tokens, 9 tirages d'UUID sur 300
        perdaient le bloc de code entier, mot de passe compris.
        """
        import uuid

        malheureux = uuid.UUID("b2be4e42-bc74-46f6-996a-1165a11cfe5f")
        monkeypatch.setattr(uuid, "uuid4", lambda: malheureux)
        nettoye, _ = pipeline.strip(_texte_avec_bloc_de_code())
        assert DSN_AVEC_MOT_DE_PASSE in nettoye
