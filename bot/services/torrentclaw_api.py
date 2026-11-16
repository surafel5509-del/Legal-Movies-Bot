from __future__ import annotations

import aiohttp

BASE_URL = "https://torrentclaw.com"


class TorrentClawError(RuntimeError):
    pass


class TorrentClaw:
    """TorrentClaw search client. It never assumes a search result is licensed."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str = ""):
        self.session = session
        self.api_key = api_key.strip()

    def _headers(self) -> dict[str, str]:
        headers = {"x-search-source": "telegram-bot"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def search(self, query: str, *, page: int = 1, limit: int = 10,
                     quality: str = "", content_type: str = "") -> dict:
        params: dict[str, str | int] = {
            "q": query[:160],
            "sort": "seeders",
            "page": max(1, min(page, 1000)),
            "limit": max(1, min(limit, 20)),
        }
        if quality in {"480p", "720p", "1080p", "2160p"}:
            params["quality"] = quality
        if content_type in {"movie", "show"}:
            params["type"] = content_type
        try:
            async with self.session.get(
                f"{BASE_URL}/api/v1/search",
                params=params,
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
            raise TorrentClawError("TorrentClaw is temporarily unavailable.") from exc
        if not isinstance(data, dict) or not isinstance(data.get("results", []), list):
            raise TorrentClawError("TorrentClaw returned an unexpected response.")
        return data

    async def track(self, info_hash: str, action: str = "copy") -> None:
        if action not in {"magnet", "torrent_download", "copy"}:
            raise ValueError("Unsupported TorrentClaw tracking action")
        async with self.session.post(
            f"{BASE_URL}/api/v1/track",
            json={"infoHash": info_hash, "action": action},
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
