"""Centralized settings for HiveMind via Pydantic BaseSettings.

All configuration is read from environment variables with the HIVEMIND_ prefix,
falling back to the defaults defined here. Set values in a .env file or export
them in the shell before starting the server.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variable names are formed by uppercasing the field name and
    prepending the HIVEMIND_ prefix.  Example: HIVEMIND_DATABASE_URL overrides
    database_url.
    """

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hivemind"

    # Security
    secret_key: str = "dev-secret-change-me"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # PII pipeline
    pii_rejection_threshold: float = 0.50

    # Search
    default_search_limit: int = 10
    max_search_limit: int = 50

    # Redis (rate limiting, Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # Rate limiting / anti-sybil (SEC-03)
    burst_threshold: int = 50
    burst_window_seconds: int = 60

    # FalkorDB (INFRA-02)
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_database: str = "hivemind"

    # Injection scanner (SEC-01)
    injection_threshold: float = 0.5

    # Quality Intelligence — scoring weights (QI-01)
    # Weights must sum to ~1.0 for a balanced score; tunable via env vars.
    # Do NOT read from deployment_config at compute time — these are config-time settings.
    quality_staleness_half_life_days: float = 90.0  # freshness decay half-life
    quality_weights_usefulness: float = 0.40  # helpful / (helpful + not_helpful)
    quality_weights_popularity: float = 0.25  # tanh(retrieval_count / 50)
    quality_weights_freshness: float = 0.20   # exp(-ln2 * days / half_life)
    quality_weights_contradiction: float = 0.15  # penalty for contradiction flags

    # Distillation thresholds (KM-03, Phase 3)
    distillation_volume_threshold: int = 50   # min pending items before distillation runs
    distillation_conflict_threshold: int = 5  # min unresolved conflicts before distillation

    # MinHash LSH deduplication (KM-03)
    minhash_threshold: float = 0.95   # Jaccard similarity threshold for near-duplicate detection
    minhash_num_perm: int = 128       # number of permutations for MinHash accuracy/speed tradeoff

    # LLM for conflict resolution and stage-3 dedup (Phase 3)
    llm_provider: str = "anthropic"                    # LLM provider backend
    llm_model: str = "claude-3-haiku-20240307"         # model for conflict resolution
    anthropic_api_key: str = ""                        # HIVEMIND_ANTHROPIC_API_KEY — empty = LLM stages skip gracefully

    model_config = SettingsConfigDict(
        env_prefix="HIVEMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Module-level singleton — import this throughout the codebase
settings = Settings()
