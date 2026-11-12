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
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="ET"
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
async def test_tmdb_details_exposes_watch_providers_and_official_trailer(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="ET"
    ))
    api = tmdb_api.TMDBAPI(FakeSession([
        {"id": 123, "title": "Example Film", "release_date": "2024-01-02", "genres": [{"name": "Drama"}]},
        {"results": {"ET": {"link": "https://www.themoviedb.org/movie/123/watch",
                            "flatrate": [{"provider_name": "Example Stream"}]}}},
        {"results": [
            {"site": "YouTube", "type": "Teaser", "key": "teaser", "official": True},
            {"site": "YouTube", "type": "Trailer", "key": "official-trailer", "official": True},
            {"site": "Vimeo", "type": "Trailer", "key": "ignored", "official": True},
        ]},
    ]))
    details = await api.movie_details(123)
    assert details["providers"] == ["Example Stream"]
    assert details["watch_url"].endswith("/watch")
    assert details["trailer_url"] == "https://www.youtube.com/watch?v=official-trailer"
    assert "download_url" not in details


@pytest.mark.asyncio
async def test_tmdb_discovery_uses_expected_endpoint(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="ET"
    ))
    session = FakeSession([{"results": [{
        "id": 456, "title": "Popular Film", "release_date": "2025-01-01",
    }]}])
    api = tmdb_api.TMDBAPI(session)
    movies = await api.discover_movies("popular")
    assert movies[0]["id"] == 456
    assert session.urls[0][0].endswith("/movie/popular")
    assert session.urls[0][1]["region"] == "ET"


@pytest.mark.asyncio
async def test_tmdb_discovery_rejects_unknown_category(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(tmdb_api_key="test-key"))
    api = tmdb_api.TMDBAPI(FakeSession([]))
    assert await api.discover_movies("unknown") == []


@pytest.mark.asyncio
async def test_tmdb_search_tv_maps_series_metadata(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="ET"
    ))
    session = FakeSession([{"results": [{
        "id": 789, "name": "Example Series", "first_air_date": "2022-04-01",
        "overview": "Series synopsis.", "poster_path": "/series.jpg",
    }]}])
    api = tmdb_api.TMDBAPI(session)
    items = await api.search_tv("Example Series")
    assert items[0]["id"] == 789
    assert items[0]["year"] == "2022"
    assert session.urls[0][0].endswith("/search/tv")


@pytest.mark.asyncio
async def test_tmdb_tv_season_returns_episode_metadata(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="ET"
    ))
    session = FakeSession([{"id": 22, "name": "Season One", "episodes": [{
        "episode_number": 1, "name": "Pilot", "air_date": "2024-01-01",
        "overview": "First episode.",
    }]}])
    api = tmdb_api.TMDBAPI(session)
    season = await api.tv_season(789, 1)
    assert season["episodes"][0]["name"] == "Pilot"
    assert session.urls[0][0].endswith("/tv/789/season/1")


@pytest.mark.asyncio
async def test_tmdb_movie_genres_and_genre_discovery(monkeypatch):
    monkeypatch.setattr(tmdb_api, "settings", SimpleNamespace(
        tmdb_api_key="test-key", request_timeout_seconds=10, tmdb_watch_region="ET"
    ))
    session = FakeSession([
        {"genres": [{"id": 18, "name": "Drama"}]},
        {"results": [{"id": 123, "title": "Drama film", "release_date": "2020-01-01"}]},
    ])
    api = tmdb_api.TMDBAPI(session)
    genres = await api.movie_genres()
    movies = await api.discover_movies_by_genre(18)
    assert genres == [{"id": 18, "name": "Drama"}]
    assert movies[0]["id"] == 123
    assert session.urls[1][0].endswith("/discover/movie")
    assert session.urls[1][1]["with_genres"] == 18
