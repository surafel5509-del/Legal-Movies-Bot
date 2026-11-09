from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import aiohttp
from aiogram.types import FSInputFile

from bot.config import settings


class FileTooLarge(Exception):
    def __init__(self, size: int | None):
        self.size = size
        super().__init__("File exceeds configured Telegram upload limit")


class DownloadManager:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self.session: aiohttp.ClientSession | None = None

    async def fetch(self, url: str, filename: str) -> Path:
        if self.session is None:
            raise RuntimeError("Download manager is not initialized")
        async with self.semaphore:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=None, sock_connect=settings.request_timeout_seconds)) as response:
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
