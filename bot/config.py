from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _csv_ints(value: str) -> set[int]:
    return {int(item.strip()) for item in value.split(",") if item.strip()}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    database_url: str
    log_level: str = "INFO"
    max_upload_bytes: int = 49 * 1024 * 1024
    max_concurrent_downloads: int = 2
    archive_page_size: int = 15
    cache_ttl_seconds: int = 600
    request_timeout_seconds: int = 25
    temp_dir: Path = Path("/tmp/legal-movie-bot")
    catalog_enabled: bool = True
    active_days: int = 30

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN is required")
        database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", 49 * 1024 * 1024))
        if max_upload_bytes < 1:
            raise ValueError("MAX_UPLOAD_BYTES must be a positive integer")
        return cls(
            bot_token=token,
            admin_ids=_csv_ints(os.getenv("ADMIN_IDS", "")),
            database_url=database_url,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            max_upload_bytes=max_upload_bytes,
            max_concurrent_downloads=max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))),
            archive_page_size=max(1, min(30, int(os.getenv("ARCHIVE_PAGE_SIZE", "15")))),
            cache_ttl_seconds=max(30, int(os.getenv("CACHE_TTL_SECONDS", "600"))),
            request_timeout_seconds=max(5, int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))),
            temp_dir=Path(os.getenv("TEMP_DIR", "/tmp/legal-movie-bot")),
            catalog_enabled=os.getenv("ARCHIVE_CATALOG_ENABLED", "true").lower() in {"1", "true", "yes"},
            active_days=max(1, int(os.getenv("ACTIVE_DAYS", "30"))),
        )


settings = Settings.from_env()
