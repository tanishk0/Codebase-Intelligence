from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        extra="ignore",
    )

    # External API & Database credentials
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    NVIDIA_API_KEY: str = ""

    # Embedding configuration (NVIDIA NIM)
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_EMBED_MODEL: str = "nvidia/nemotron-3.5-embed-1b"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBED_BATCH_SIZE: int = 50
    NVIDIA_REQUESTS_PER_MINUTE: int = 35  # Free tier is ~40 RPM; keep headroom
    SUPABASE_BATCH_SIZE: int = 100

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
