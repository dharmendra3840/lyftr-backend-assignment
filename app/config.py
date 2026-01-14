from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load configuration from OS environment variables and a `.env` file
    # located in the project root (where you run `python -m app.main`).
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = Field(..., alias="DATABASE_URL")
    webhook_secret: str = Field(..., alias="WEBHOOK_SECRET", min_length=1)
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    @property
    def sqlite_path(self) -> str:
        # Handle both sqlite:/// (3 slashes) and sqlite://// (4 slashes) formats
        # sqlite:////path -> absolute path
        # sqlite:///./path -> relative path
        # sqlite:///path -> relative path
        url = self.database_url
        if not url.startswith("sqlite:///"):
            raise ValueError(
                "Only sqlite URLs are supported. Examples: sqlite:///./test.db or sqlite:////data/app.db"
            )
        
        # Handle sqlite://// (4 slashes) - absolute path
        if url.startswith("sqlite:////"):
            return url.replace("sqlite:////", "/")
        
        # Handle sqlite:/// (3 slashes) - relative or absolute path
        # Remove sqlite:/// prefix
        path = url.replace("sqlite:///", "")
        
        # Handle relative paths starting with ./
        if path.startswith("./"):
            import os
            # Get absolute path relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(project_root, path[2:])
        
        # Handle absolute paths on Windows (e.g., C:/path/to/db.db)
        if len(path) > 1 and path[1] == ":":
            return path
        
        # For Unix-like absolute paths starting with /
        if path.startswith("/"):
            return path
        
        # Otherwise treat as relative path
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, path)