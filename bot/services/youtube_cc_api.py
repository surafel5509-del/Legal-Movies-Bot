from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote

from bot.config import settings

YOUTUBE_LICENSE_URL = "https://support.google.com/youtube/answer/2797468"
YOUTUBE_CC_LABEL = "YouTube Creative Commons Attribution (uploader-declared)"
MIN_DURATION_SECONDS = 20 * 60
logger = logging.getLogger(__name__)


def is_youtube_cc_license(value: object) -> bool:
    normalized = re.sub(r"[^a-z]+", " ", str(value or "").casefold()).strip()
    return normalized in {
        "creative commons attribution license reuse allowed",
        "creative commons attribution",
        "creative commons attribution license",
    }


def _year(value: object) -> int | None:
    match = re.search(r"\b(?:18|19|20)\d{2}\b", str(value or ""))
    return int(match.group()) if match else None


def _clean(value: object, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _extract(url: str, *, download: bool = False, options: dict | None = None) -> dict:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
            "skip_download": not download, "extract_flat": False,
            "socket_timeout": settings.request_timeout_seconds}
    if options:
        opts.update(options)
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(url, download=download)
        if not isinstance(result, dict):
            raise ValueError("YouTube did not return a single video")
        return result


class YouTubeCCCatalog:
    """Find and re-check only videos explicitly marked CC Attribution by YouTube."""

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        query = " ".join(query.split())[:100]
        if len(query) < 2 or limit < 1:
            return []
        try:
            return await asyncio.to_thread(self._search_sync, query, limit)
        except Exception as exc:
            logger.warning("YouTube CC search unavailable: %s", exc)
            return []

    def _search_sync(self, query: str, limit: int) -> list[dict]:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
                "skip_download": True, "extract_flat": False,
                "socket_timeout": settings.request_timeout_seconds}
        results = []
        with yt_dlp.YoutubeDL(opts) as ydl:
            listing = ydl.extract_info(f"ytsearch{max(1, min(limit * 3, 15))}:{query} full movie", download=False)
            for entry in (listing or {}).get("entries") or []:
                video_id = str((entry or {}).get("id") or "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                    continue
                try:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                except Exception:
                    continue
                item = self._map(info)
                if item:
                    results.append(item)
                if len(results) >= limit:
                    break
        return results

    @staticmethod
    def _map(info: dict | None) -> dict | None:
        if not info or not is_youtube_cc_license(info.get("license")):
            return None
        video_id = str(info.get("id") or "")
        title = _clean(info.get("title"))
        duration = info.get("duration")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or not title:
            return None
        if not isinstance(duration, (int, float)) or duration < MIN_DURATION_SECONDS:
            return None
        ext = str(info.get("ext") or "mp4").lower()
        if ext not in {"mp4", "webm", "mkv"}:
            ext = "mp4"
        year = _year(f"{title} {info.get('release_year') or ''}")
        safe_title = re.sub(r"[^A-Za-z0-9._ -]", "", title).strip()[:150] or video_id
        return {
            "identifier": f"youtube:{video_id}", "title": title, "year": year,
            "description": _clean(info.get("description"), 2500),
            "genre": None, "language": info.get("language"),
            "poster_url": info.get("thumbnail"),
            "license": YOUTUBE_CC_LABEL, "license_url": YOUTUBE_LICENSE_URL,
            "source_url": f"https://www.youtube.com/watch?v={quote(video_id)}",
            "files": [{
                "filename": f"{safe_title}.{ext}", "format": ext.upper(),
                "resolution": f"{info.get('height')}p" if info.get("height") else None,
                "file_size": info.get("filesize") or info.get("filesize_approx"),
                "download_url": f"https://www.youtube.com/watch?v={quote(video_id)}",
                "codec": None,
            }],
            "raw": {"source": "YouTube Creative Commons",
                    "uploader": _clean(info.get("uploader"), 200),
                    "duration_seconds": int(duration),
                    "license": _clean(info.get("license"), 200)},
        }

    async def details(self, identifier: str) -> dict | None:
        video_id = identifier.removeprefix("youtube:")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return None
        try:
            info = await asyncio.to_thread(
                _extract, f"https://www.youtube.com/watch?v={quote(video_id)}", download=False
            )
        except Exception:
            return None
        return self._map(info)
