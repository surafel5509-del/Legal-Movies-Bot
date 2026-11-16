from __future__ import annotations

from dataclasses import dataclass
import os
import secrets
from pathlib import Path


def _csv_ints(value: str) -> set[int]:
    return {int(item.strip()) for item in value.split(",") if item.strip()}


def _csv_hashes(value: str) -> set[str]:
    import re
    hashes = {item.strip().lower() for item in value.split(",") if item.strip()}
    invalid = [item for item in hashes if not re.fullmatch(r"[a-f0-9]{40}", item)]
    if invalid:
        raise ValueError("TORRENTCLAW_APPROVED_INFOHASHES must contain only 40-character hexadecimal info hashes")
    return hashes


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    database_url: str
    admin_setup_code: str = "1212"
    log_level: str = "INFO"
    max_upload_bytes: int = 3_000_000_000
    telegram_upload_max_bytes: int = 49_000_000
    max_concurrent_downloads: int = 2
    archive_page_size: int = 10
    cache_ttl_seconds: int = 600
    request_timeout_seconds: int = 25
    temp_dir: Path = Path("/tmp/legal-movie-bot")
    catalog_enabled: bool = True
    active_days: int = 30
    tmdb_api_key: str = ""
    tmdb_watch_region: str = "US"
    torrentclaw_api_key: str = ""
    torrentclaw_approved_infohashes: set[str] | None = None
    torrent_download_enabled: bool = False
    aria2_rpc_secret: str = ""
    aria2_rpc_port: int = 6800

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

        # Railway mounts persistent volumes at RAILWAY_VOLUME_MOUNT_PATH.
        # Keep explicitly configured absolute SQLite paths and all PostgreSQL URLs,
        # but move relative SQLite paths onto the persistent volume.
        volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
        if database_url.startswith("sqlite+") and ":memory:" not in database_url and volume_path:
            sqlite_location = database_url.split("///", 1)[-1].split("?", 1)[0]
            if sqlite_location and not Path(sqlite_location).is_absolute():
                database_url = f"sqlite+aiosqlite:///{Path(volume_path) / 'bot.db'}"

        max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", 3 * 1024 * 1024 * 1024))
        telegram_upload_max_bytes = int(os.getenv("TELEGRAM_UPLOAD_MAX_BYTES", 49 * 1024 * 1024))
        if max_upload_bytes < 1 or telegram_upload_max_bytes < 1:
            raise ValueError("Download and Telegram upload limits must be positive integers")
        return cls(
            bot_token=token,
            admin_ids=_csv_ints(os.getenv("ADMIN_IDS", "")),
            database_url=database_url,
            admin_setup_code=os.getenv("ADMIN_SETUP_CODE", "1212").strip(),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            max_upload_bytes=max_upload_bytes,
            telegram_upload_max_bytes=telegram_upload_max_bytes,
            max_concurrent_downloads=max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))),
            archive_page_size=max(1, min(50, int(os.getenv("ARCHIVE_PAGE_SIZE", "10")))),
            cache_ttl_seconds=max(30, int(os.getenv("CACHE_TTL_SECONDS", "600"))),
            request_timeout_seconds=max(5, int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))),
            temp_dir=Path(os.getenv("TEMP_DIR", "/tmp/legal-movie-bot")),
            catalog_enabled=os.getenv("ARCHIVE_CATALOG_ENABLED", "true").lower() in {"1", "true", "yes"},
            active_days=max(1, int(os.getenv("ACTIVE_DAYS", "30"))),
            tmdb_api_key=os.getenv("TMDB_API_KEY", "").strip(),
            tmdb_watch_region=os.getenv("TMDB_WATCH_REGION", "US").strip().upper()[:2] or "US",
            torrentclaw_api_key=os.getenv("TORRENTCLAW_API_KEY", "").strip(),
            torrentclaw_approved_infohashes=_csv_hashes(os.getenv("TORRENTCLAW_APPROVED_INFOHASHES", "")),
            torrent_download_enabled=os.getenv("TORRENT_DOWNLOAD_ENABLED", "false").lower() in {"1", "true", "yes"},
            aria2_rpc_secret=os.getenv("ARIA2_RPC_SECRET", "").strip() or secrets.token_urlsafe(32),
            aria2_rpc_port=max(1024, min(65535, int(os.getenv("ARIA2_RPC_PORT", "6800")))),
        )


settings = Settings.from_env()
