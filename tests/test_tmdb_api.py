from types import SimpleNamespace

import pytest

from bot.services import tmdb_api


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = payloads
        self.urls = []

    def get(self, url, params=None, timeout=None):
        self.urls.append((url, params))
        return FakeResponse(self.payloads.pop(0))


@pytest.mark.asyncio
async def test_tmdb_search_maps_movie_metadata(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="US"
    ))
    api = tmdb_api.TMDBAPI(FakeSession([{"results": [{
        "id": 123, "title": "Example Film", "release_date": "2024-01-02",
        "overview": "A synopsis.", "poster_path": "/poster.jpg",
    }]}]))
    results = await api.search_movies("Example Film")
    assert results[0]["id"] == 123
    assert results[0]["year"] == "2024"
    assert results[0]["poster_url"].endswith("/poster.jpg")
    assert results[0]["watch_url"].startswith("https://www.themoviedb.org/movie/123/watch")


@pytest.mark.asyncio
async def test_tmdb_details_exposes_watch_providers_not_downloads(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="US"
    ))
    api = tmdb_api.TMDBAPI(FakeSession([
        {"id": 123, "title": "Example Film", "release_date": "2024-01-02", "genres": [{"name": "Drama"}]},
        {"results": {"US": {"link": "https://www.themoviedb.org/movie/123/watch",
                            "flatrate": [{"provider_name": "Example Stream"}]}}},
    ]))
    details = await api.movie_details(123)
    assert details["providers"] == ["Example Stream"]
    assert details["watch_url"].endswith("/watch")
    assert "download_url" not in details
