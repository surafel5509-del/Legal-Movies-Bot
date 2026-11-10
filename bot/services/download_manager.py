from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import aiohttp
from aiogram.types import FSInputFile

from bot.config import settings
from bot.services.youtube_cc_api import YOUTUBE_CC_LABEL, is_youtube_cc_license


class FileTooLarge(Exception):
    def __init__(self, size: int | None):
        self.size = size
        super().__init__("File exceeds configured Telegram upload limit")


def _youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port is not None:
        return None
    host = (parsed.hostname or "").lower()
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"} and parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif host == "youtu.be":
        video_id = parsed.path.strip("/")
    else:
        return None
    return video_id if len(video_id) == 11 and all(c.isalnum() or c in "_-" for c in video_id) else None


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


def _fetch_youtube(url: str, expected_license: str, max_bytes: int, temp_dir: Path) -> Path:
    import yt_dlp

    video_id = _youtube_video_id(url)
    if not video_id or expected_license != YOUTUBE_CC_LABEL:
        raise ValueError("YouTube download requires a freshly verified CC Attribution record")
    target_dir = Path(tempfile.mkdtemp(prefix="ytdlp-", dir=temp_dir))
    exceeded: list[int] = []

    def progress_hook(data: dict) -> None:
        downloaded = int(data.get("downloaded_bytes") or 0)
        if downloaded > max_bytes:
            exceeded.append(downloaded)
            raise FileTooLarge(downloaded)

    def match_filter(info: dict, *, incomplete: bool = False):
        if not is_youtube_cc_license(info.get("license")):
            return "Blocked: the current YouTube metadata does not declare Creative Commons Attribution"
        return None

    options = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "format": "best[ext=mp4]/best",
        "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        "max_filesize": max_bytes,
        "socket_timeout": settings.request_timeout_seconds,
        "retries": 2, "fragment_retries": 2,
        "progress_hooks": [progress_hook],
        "match_filter": match_filter,
        "restrictfilenames": True,
        "overwrites": False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info or not is_youtube_cc_license(info.get("license")):
                raise ValueError("YouTube CC license could not be re-verified")
        files = [p for p in target_dir.iterdir() if p.is_file()]
        if len(files) != 1:
            raise RuntimeError("YouTube downloader did not produce exactly one video file")
        path = files[0]
        size = path.stat().st_size
        if size > max_bytes:
            raise FileTooLarge(size)
        return path
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise


class DownloadManager:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self.session: aiohttp.ClientSession | None = None

    async def fetch(self, url: str, filename: str, expected_license: str | None = None) -> Path:
        video_id = _youtube_video_id(url)
        async with self.semaphore:
            if video_id:
                return await asyncio.to_thread(
                    _fetch_youtube, url, expected_license or "", settings.max_upload_bytes, settings.temp_dir
                )
            if self.session is None:
                raise RuntimeError("Download manager is not initialized")
            if not _trusted_download_url(url):
                raise ValueError("Download host is not allowlisted")
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
    def cleanup(path: Path) -> None:
        if path.parent.name.startswith("ytdlp-"):
            shutil.rmtree(path.parent, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)

    @staticmethod
    def input_file(path: Path, filename: str) -> FSInputFile:
        return FSInputFile(path, filename=filename)
