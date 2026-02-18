"""
Embedding model abstraction layer for HiveMind (KM-08).

Provides an abstract EmbeddingProvider interface so the embedding model can be
swapped without modifying callers. The SentenceTransformerProvider is the default
Phase 1 implementation using all-MiniLM-L6-v2 (384 dimensions, ~22 MB).

Design decisions:
- model_id and model_revision are queryable properties — stored in deployment_config
  at startup to enable detection of model drift between deployments (KM-08)
- normalize_embeddings=True ensures correct cosine similarity with pgvector's
  cosine_distance operator
- Module-level get_embedder() returns a singleton to avoid reloading the model

Exports: EmbeddingProvider, SentenceTransformerProvider, get_embedder
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Abstract interface for embedding model providers.

    Implementors must:
    - Embed a single text string to a list of floats
    - Embed a batch of texts efficiently
    - Expose model_id (e.g. "sentence-transformers/all-MiniLM-L6-v2")
    - Expose model_revision (HuggingFace commit hash, or None if unavailable)
    - Expose dimensions (vector size, e.g. 384)

    The revision and dimensions are stored in the deployment_config table at
    startup so that model version drift can be detected before vectors are
    queried against an incompatible embedding space.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text and return a normalized float vector."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts and return a list of normalized float vectors."""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Fully-qualified model identifier (e.g. 'sentence-transformers/all-MiniLM-L6-v2')."""
        ...

    @property
    @abstractmethod
    def model_revision(self) -> str | None:
        """HuggingFace commit hash pinning the exact model version, or None."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding vector dimensionality (e.g. 384 for all-MiniLM-L6-v2)."""
        ...


# ---------------------------------------------------------------------------
# SentenceTransformer implementation
# ---------------------------------------------------------------------------


class SentenceTransformerProvider(EmbeddingProvider):
    """EmbeddingProvider backed by sentence-transformers.

    Args:
        model_name: HuggingFace model identifier. Defaults to
            "sentence-transformers/all-MiniLM-L6-v2" (384 dims, 22 MB).

    The model is loaded once at construction. Normalization is applied so that
    vectors are unit-length — this makes cosine similarity equivalent to dot
    product, which is what pgvector's cosine_distance operator computes.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

        # Detect dimensions from the loaded model rather than hardcoding
        self._dimensions: int = self._model.get_sentence_embedding_dimension()

        # Attempt to retrieve the HuggingFace commit hash for revision pinning.
        # This is a best-effort operation — if the model was loaded from a local
        # cache without metadata, we fall back to None.
        self._revision: str | None = self._detect_revision()

    # ------------------------------------------------------------------
    # EmbeddingProvider interface
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Embed a single text string.

        Returns:
            Normalized float vector of length self.dimensions.
        """
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in a single model forward pass.

        Returns:
            List of normalized float vectors, one per input text.
        """
        return [e.tolist() for e in self._model.encode(texts, normalize_embeddings=True)]

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def model_revision(self) -> str | None:
        return self._revision

    @property
    def dimensions(self) -> int:
        return self._dimensions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_revision(self) -> str | None:
        """Try to read the HuggingFace commit hash from the model's metadata."""
        try:
            # sentence-transformers exposes the underlying transformers model config
            # which may carry the _commit_hash attribute set by the HF Hub cache
            config = getattr(self._model, "_modules", {})
            # Walk into the transformer backbone if present
            for module_name, module in config.items():
                commit = getattr(getattr(module, "config", None), "_commit_hash", None)
                if commit:
                    return commit
        except Exception:
            pass

        # Fallback: attempt to use huggingface_hub if available
        try:
            from huggingface_hub import model_info  # type: ignore[import]
            info = model_info(self._model_name)
            return info.sha
        except Exception:
            pass

        return None


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------


class _EmbedderSingleton:
    """Internal singleton holder — prevents repeated model loading."""

    _instance: EmbeddingProvider | None = None


def get_embedder(model_name: str | None = None) -> EmbeddingProvider:
    """Return the module-level embedding provider singleton.

    On first call, instantiates SentenceTransformerProvider with *model_name*
    (or the value of settings.embedding_model if None). Subsequent calls return
    the cached instance regardless of *model_name*.

    The lazy import of settings avoids circular imports — config.py has no
    dependency on the pipeline package.

    Args:
        model_name: Optional model override. Only used on the first call.

    Returns:
        The global EmbeddingProvider instance.
    """
    if _EmbedderSingleton._instance is None:
        if model_name is None:
            # Lazy import to avoid circular dependency with config.py
            from hivemind.config import settings  # noqa: PLC0415
            model_name = settings.embedding_model
        _EmbedderSingleton._instance = SentenceTransformerProvider(model_name)
    return _EmbedderSingleton._instance
