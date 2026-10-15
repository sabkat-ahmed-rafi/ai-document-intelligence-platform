from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_NAME: str = "AI Document Intelligence Platform"
    DEBUG: bool = False

    # Storage configuration
    STORAGE_PROVIDER: str = "local"
    STORAGE_PATH: str = "./uploads"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
