from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ingestion limits
    MAX_FILE_SIZE_BYTES: int = 500_000  # 500 KB per file limit
    MAX_TOTAL_FILES: int = 2_000        # Safety cap for huge repos

    # File / directory filters
    IGNORED_DIRS: set[str] = {
        ".git",
        ".github",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".vscode",
        ".idea",
    }

    IGNORED_EXTENSIONS: set[str] = {
        # Binaries & archives
        ".exe", ".dll", ".so", ".dylib", ".zip", ".tar", ".gz", ".7z",
        # Images & Media
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".mp4", ".mp3", ".pdf",
        # Lockfiles (too noisy for code RAG)
        ".lock",
        # Compiled Python
        ".pyc", ".pyo", ".pyd",
    }


settings = Settings()
