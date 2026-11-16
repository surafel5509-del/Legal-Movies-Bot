import pytest

from bot.config import _csv_hashes
from bot.services.torrentclaw_api import TorrentClaw


def test_approved_infohashes_are_normalized_and_validated():
    digest = "A" * 40
    assert _csv_hashes(f" {digest}, {'b' * 40} ") == {"a" * 40, "b" * 40}


def test_invalid_approved_infohash_is_rejected():
    with pytest.raises(ValueError):
        _csv_hashes("not-a-valid-infohash")


class FakeResponse:
    status = 200

    def __init__(self, data=None):
        self.data = data or {"results": [{"title": "Public Domain Sample"}]}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        return self.data


class FakeSession:
    def __init__(self, data=None):
        self.request = None
        self.data = data

    def get(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeResponse(self.data)


@pytest.mark.asyncio
async def test_search_uses_relevance_sort_exact_year_and_skill_source_header():
    session = FakeSession()
    client = TorrentClaw(session, api_key="tc_live_example")
    result = await client.search("Night of the Living Dead", year=1968, quality="1080p", content_type="movie")
    assert result["results"][0]["title"] == "Public Domain Sample"
    url, kwargs = session.request
    assert url.endswith("/api/v1/search")
    assert kwargs["params"]["q"] == "Night of the Living Dead"
    assert kwargs["params"]["sort"] == "relevance"
    assert kwargs["params"]["year_min"] == 1968
    assert kwargs["params"]["year_max"] == 1968
    assert kwargs["params"]["quality"] == "1080p"
    assert kwargs["params"]["type"] == "movie"
    assert kwargs["headers"]["x-search-source"] == "telegram-bot"
    assert kwargs["headers"]["Authorization"] == "Bearer tc_live_example"


@pytest.mark.asyncio
async def test_popular_and_recent_use_their_dedicated_torrentclaw_endpoints():
    session = FakeSession({"items": [{"id": 1, "title": "Popular Movie", "contentType": "movie"}]})
    client = TorrentClaw(session)
    popular = await client.popular(limit=8, page=2)
    assert popular["items"][0]["title"] == "Popular Movie"
    url, kwargs = session.request
    assert url.endswith("/api/v1/popular")
    assert kwargs["params"] == {"page": 2, "limit": 8}

    recent = await client.recent(limit=6, page=1)
    assert recent["items"][0]["title"] == "Popular Movie"
    url, kwargs = session.request
    assert url.endswith("/api/v1/recent")
    assert kwargs["params"] == {"page": 1, "limit": 6}
