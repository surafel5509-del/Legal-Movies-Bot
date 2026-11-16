from __future__ import annotations

import aiohttp

BASE_URL = "https://torrentclaw.com"


class TorrentClawError(RuntimeError):
    pass


class TorrentClaw:
    """Async client for TorrentClaw movie discovery endpoints."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str = ""):
        self.session = session
        self.api_key = api_key.strip()

    def _headers(self) -> dict[str, str]:
        headers = {"x-search-source": "telegram-bot"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            async with self.session.get(
                f"{BASE_URL}{path}",
                params=params or {},
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status == 429:
                    raise TorrentClawError("TorrentClaw rate limit reached. Try again shortly.")
                response.raise_for_status()
                data = await response.json(content_type=None)
        except TorrentClawError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise TorrentClawError("TorrentClaw is temporarily unavailable. Please try again.") from exc
        if not isinstance(data, dict):
            raise TorrentClawError("TorrentClaw returned an unexpected response.")
        return data

    async def search(
        self, query: str, *, page: int = 1, limit: int = 20,
        quality: str = "", content_type: str = "movie", year: int | None = None,
    ) -> dict:
        if len(query.strip()) < 2:
            raise ValueError("Search query must contain at least two characters")
        params: dict[str, str | int] = {
            "q": query.strip()[:160],
            "sort": "relevance",
            "page": max(1, min(page, 1000)),
            "limit": max(1, min(limit, 50)),
        }
        if quality in {"480p", "720p", "1080p", "2160p"}:
            params["quality"] = quality
        if content_type in {"movie", "show"}:
            params["type"] = content_type
        if year and 1888 <= year <= 2100:
            params["year_min"] = year
            params["year_max"] = year
        data = await self._get("/api/v1/search", params)
        if not isinstance(data.get("results", []), list):
            raise TorrentClawError("TorrentClaw returned an invalid search result list.")
        return data

    async def popular(self, *, page: int = 1, limit: int = 12) -> dict:
        data = await self._get("/api/v1/popular", {
            "page": max(1, min(page, 1000)),
            "limit": max(1, min(limit, 24)),
        })
        if not isinstance(data.get("items", []), list):
            raise TorrentClawError("TorrentClaw returned an invalid popular list.")
        return data

    async def recent(self, *, page: int = 1, limit: int = 12) -> dict:
        data = await self._get("/api/v1/recent", {
            "page": max(1, min(page, 1000)),
            "limit": max(1, min(limit, 24)),
        })
        if not isinstance(data.get("items", []), list):
            raise TorrentClawError("TorrentClaw returned an invalid recent list.")
        return data

    async def track(self, info_hash: str, action: str = "copy") -> None:
        if action not in {"magnet", "torrent_download", "copy"}:
            raise ValueError("Unsupported TorrentClaw tracking action")
        try:
            async with self.session.post(
                f"{BASE_URL}/api/v1/track",
                json={"infoHash": info_hash, "action": action},
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise TorrentClawError("TorrentClaw tracking is temporarily unavailable.") from exc
