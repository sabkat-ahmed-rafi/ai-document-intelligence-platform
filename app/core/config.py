from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_NAME: str = "AI Document Intelligence Platform"
    DEBUG: bool = False

    # Storage configuration
    STORAGE_PROVIDER: str = "local"
    STORAGE_PATH: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
