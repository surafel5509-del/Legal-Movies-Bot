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

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        return {"results": [{"title": "Public Domain Sample"}]}


class FakeSession:
    def __init__(self):
        self.request = None

    def get(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeResponse()


@pytest.mark.asyncio
async def test_search_uses_encoded_params_and_skill_source_header():
    session = FakeSession()
    client = TorrentClaw(session, api_key="tc_live_example")
    result = await client.search("Night & Day", quality="1080p", content_type="movie")
    assert result["results"][0]["title"] == "Public Domain Sample"
    url, kwargs = session.request
    assert url.endswith("/api/v1/search")
    assert kwargs["params"]["q"] == "Night & Day"
    assert kwargs["params"]["quality"] == "1080p"
    assert kwargs["params"]["type"] == "movie"
    assert kwargs["headers"]["x-search-source"] == "telegram-bot"
    assert kwargs["headers"]["Authorization"] == "Bearer tc_live_example"
