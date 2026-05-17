from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_prefix": "KAIROS_", "env_file": ".env", "extra": "ignore"}

    env: str = Field(default="development", alias="KAIROS_ENV")
    log_level: str = Field(default="DEBUG", alias="LOG_LEVEL")

    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    database_url: str = Field(
        default="postgresql+asyncpg://kairos:kairos_dev@localhost:5432/kairos",
        alias="DATABASE_URL",
    )

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")

    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_model: str = Field(default="text-embedding-ada-002", alias="EMBEDDING_MODEL")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")

    scoring_weight_recency: float = Field(default=0.25, alias="SCORING_WEIGHT_RECENCY")
    scoring_weight_relevance: float = Field(default=0.35, alias="SCORING_WEIGHT_RELEVANCE")
    scoring_weight_outcome: float = Field(default=0.25, alias="SCORING_WEIGHT_OUTCOME")
    scoring_weight_frequency: float = Field(default=0.15, alias="SCORING_WEIGHT_FREQUENCY")

    evaluator_model: str = Field(default="gpt-4o-mini", alias="EVALUATOR_MODEL")
    evaluation_threshold: float = Field(default=0.6, alias="EVALUATION_THRESHOLD")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_cors_origins: str = Field(default="*", alias="API_CORS_ORIGINS")

    profiles_dir: str = Field(default="./profiles", alias="PROFILES_DIR")
    obsidian_vault: str = Field(default="", alias="OBSIDIAN_VAULT")
    telegram_token: str = Field(default="", alias="TELEGRAM_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # GOOGLE_API_KEY se usa directo porque el provider lo necesita en os.environ
    # y el alias evita el prefijo KAIROS_
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # Fase B: optimización
    classifier_confidence_threshold: float = Field(default=0.65, alias="CLASSIFIER_CONFIDENCE_THRESHOLD")
    pattern_mine_every: int = Field(default=10, alias="PATTERN_MINE_EVERY")
    memory_ttl_raw_days: int = Field(default=90, alias="MEMORY_TTL_RAW_DAYS")
    memory_ttl_execution_days: int = Field(default=30, alias="MEMORY_TTL_EXECUTION_DAYS")

    # Fase C: rate limiting por plan
    rate_limit_free: int = Field(default=60, alias="RATE_LIMIT_FREE")
    rate_limit_pro: int = Field(default=300, alias="RATE_LIMIT_PRO")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")

    # Fase F: MinIO secure document storage
    minio_host: str = Field(default="localhost", alias="MINIO_HOST")
    minio_port: int = Field(default=9000, alias="MINIO_PORT")
    minio_access_key: str = Field(default="kairos_admin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="kairos_secure_dev_key_32chars", alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    minio_encryption: bool = Field(default=True, alias="MINIO_ENCRYPTION")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
