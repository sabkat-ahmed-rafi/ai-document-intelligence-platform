from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_NAME: str = "AI Document Intelligence Platform"
    DEBUG: bool = False

    # Storage configuration
    STORAGE_PROVIDER: str = "supabase"  # "supabase", "s3", or "local"
    STORAGE_PATH: str = "./uploads"

    # Supabase Storage configuration
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "documents"
    SUPABASE_SIGNED_URL_EXPIRE_SECONDS: int = 3600
    SUPABASE_BUCKET_PUBLIC: bool = False
    MAX_FILE_SIZE_MB: int = 50

    # Authentication & JWT configuration
    ACCESS_TOKEN_SECRET: str = "supersecret_access_token_key_change_in_production"
    REFRESH_TOKEN_SECRET: str = "supersecret_refresh_token_key_change_in_production"
    PASSWORD_RESET_SECRET: str = "supersecret_password_reset_key_change_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    API_KEY: str = "test-api-key"

    # Email configuration (Google SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: str = ""

    # AI Processing, Chunking & Embedding Configuration
    EMBEDDING_PROVIDER: str = "fastembed"  # "fastembed", "openai", "gemini"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150

    # Celery & Distributed Task Queue Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # LLM & RAG Generation Configuration
    LLM_PROVIDER: str = "groq"  # "groq", "openai", "gemini", "ollama"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str | None = None
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
