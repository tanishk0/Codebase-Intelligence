from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    db_password: str
    database_url: str

    app_name: str = "Codebase Copilot"
    environment: str = "development"

settings = Settings()
