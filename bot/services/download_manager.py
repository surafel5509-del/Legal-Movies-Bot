from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import aiohttp
from aiogram.types import FSInputFile

from bot.config import settings


class FileTooLarge(Exception):
    def __init__(self, size: int | None):
        self.size = size
        super().__init__("File exceeds configured Telegram upload limit")


def _trusted_download_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port is not None:
        return False
    return (
        host == "archive.org" or host.endswith(".archive.org")
        or host == "upload.wikimedia.org"
        or host == "loc.gov" or host.endswith(".loc.gov")
    )


class DownloadManager:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self.session: aiohttp.ClientSession | None = None

    async def fetch(self, url: str, filename: str) -> Path:
        if self.session is None:
            raise RuntimeError("Download manager is not initialized")
        if not _trusted_download_url(url):
            raise ValueError("Download host is not allowlisted")
        async with self.semaphore:
            current_url = url
            for _ in range(6):
                if not _trusted_download_url(current_url):
                    raise ValueError("Redirect target is not an allowlisted download host")
                response = await self.session.get(
                    current_url,
                    timeout=aiohttp.ClientTimeout(total=None, sock_connect=settings.request_timeout_seconds),
                    allow_redirects=False,
                )
                if response.status not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("Location")
                response.release()
                if not location:
                    raise ValueError("Download redirect did not include a location")
                current_url = urljoin(current_url, location)
            else:
                raise ValueError("Too many download redirects")
            async with response:
                response.raise_for_status()
                length = response.content_length
                if length and length > settings.max_upload_bytes:
                    raise FileTooLarge(length)
                fd, path = tempfile.mkstemp(prefix="movie-", suffix=Path(filename).suffix or ".mp4", dir=settings.temp_dir)
                total = 0
                try:
                    with os.fdopen(fd, "wb") as output:
                        async for chunk in response.content.iter_chunked(256 * 1024):
                            total += len(chunk)
                            if total > settings.max_upload_bytes:
                                raise FileTooLarge(total)
                            output.write(chunk)
                    return Path(path)
                except Exception:
                    Path(path).unlink(missing_ok=True)
                    raise

    @staticmethod
    def input_file(path: Path, filename: str) -> FSInputFile:
        return FSInputFile(path, filename=filename)
