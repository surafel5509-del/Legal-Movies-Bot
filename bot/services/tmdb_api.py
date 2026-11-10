from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import aiohttp

from bot.config import settings

API_ROOT = "https://api.themoviedb.org/3"
IMAGE_ROOT = "https://image.tmdb.org/t/p/w500"


class TMDBAPI:
    """Movie metadata discovery and official watch/trailer links; never a video host."""

    def __init__(self, session: aiohttp.ClientSession):
        self.http = session

    async def _json(self, path: str, params: dict[str, Any] | None = None) -> dict:
        if not settings.tmdb_api_key:
            return {}
        request_params = dict(params or {})
        request_params["api_key"] = settings.tmdb_api_key
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
        async with self.http.get(f"{API_ROOT}/{path.lstrip('/')}", params=request_params, timeout=timeout) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    @staticmethod
    def _map_movie(item: dict) -> dict | None:
        movie_id = item.get("id")
        if not isinstance(movie_id, int):
            return None
        return {
            "id": movie_id,
            "title": str(item.get("title") or "Untitled")[:250],
            "year": str(item.get("release_date") or "")[:4] or None,
            "overview": str(item.get("overview") or "")[:1200],
            "poster_url": f"{IMAGE_ROOT}{item['poster_path']}" if item.get("poster_path") else None,
            "details_url": f"https://www.themoviedb.org/movie/{movie_id}",
            "watch_url": f"https://www.themoviedb.org/movie/{movie_id}/watch?locale={quote(settings.tmdb_watch_region)}",
        }

    async def search_movies(self, query: str, page: int = 1) -> list[dict]:
        query = " ".join(query.split())[:100]
        if len(query) < 2 or not settings.tmdb_api_key:
            return []
        payload = await self._json("search/movie", {
            "query": query, "page": max(1, min(int(page), 500)), "include_adult": "false",
        })
        return [mapped for item in payload.get("results", [])[:10]
                if (mapped := self._map_movie(item)) is not None]

    async def discover_movies(self, category: str, page: int = 1) -> list[dict]:
        """Return curated TMDB lists for popular, trending, and current releases."""
        endpoints = {
            "popular": "movie/popular",
            "trending": "trending/movie/week",
            "latest": "movie/now_playing",
        }
        endpoint = endpoints.get(category)
        if not endpoint or not settings.tmdb_api_key:
            return []
        payload = await self._json(endpoint, {
            "page": max(1, min(int(page), 500)),
            "region": settings.tmdb_watch_region,
        })
        return [mapped for item in payload.get("results", [])[:10]
                if (mapped := self._map_movie(item)) is not None]

    async def movie_details(self, movie_id: int) -> dict | None:
        if not settings.tmdb_api_key or movie_id < 1:
            return None
        movie = await self._json(f"movie/{movie_id}")
        if not movie or not movie.get("id"):
            return None
        provider_payload = await self._json(f"movie/{movie_id}/watch/providers")
        region = provider_payload.get("results", {}).get(settings.tmdb_watch_region, {})
        providers = []
        for category in ("flatrate", "free", "ads", "rent", "buy"):
            for provider in region.get(category, [])[:8]:
                name = str(provider.get("provider_name") or "").strip()
                if name and name not in providers:
                    providers.append(name)
        trailer_url = None
        try:
            videos = await self._json(f"movie/{movie_id}/videos")
            candidates = [
                video for video in videos.get("results", [])
                if video.get("site") == "YouTube"
                and video.get("type") in {"Trailer", "Teaser"}
                and video.get("key")
            ]
            candidates.sort(key=lambda video: (
                video.get("type") != "Trailer",
                not video.get("official", False),
            ))
            if candidates:
                trailer_url = f"https://www.youtube.com/watch?v={quote(candidates[0]['key'])}"
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            trailer_url = None
        return {
            "id": movie_id,
            "title": str(movie.get("title") or "Untitled")[:250],
            "year": str(movie.get("release_date") or "")[:4] or "Not listed",
            "overview": str(movie.get("overview") or "No synopsis available.")[:2500],
            "genres": ", ".join(g["name"] for g in movie.get("genres", []) if g.get("name"))[:300],
            "runtime": movie.get("runtime"),
            "poster_url": f"{IMAGE_ROOT}{movie['poster_path']}" if movie.get("poster_path") else None,
            "details_url": f"https://www.themoviedb.org/movie/{movie_id}",
            "watch_url": region.get("link") or f"https://www.themoviedb.org/movie/{movie_id}/watch?locale={quote(settings.tmdb_watch_region)}",
            "providers": providers,
            "region": settings.tmdb_watch_region,
            "trailer_url": trailer_url,
        }
