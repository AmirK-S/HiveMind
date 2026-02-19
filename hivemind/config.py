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

    model_config = SettingsConfigDict(
        env_prefix="HIVEMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Module-level singleton — import this throughout the codebase
settings = Settings()
