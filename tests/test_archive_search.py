import pytest

from bot.services.archive_api import ArchiveAPI, DETAIL_URL


@pytest.mark.asyncio
async def test_search_falls_back_to_item_metadata_when_search_index_omits_license(monkeypatch):
    api = ArchiveAPI(session=None)
    calls = []

    async def fake_json(url, *, params=None):
        calls.append(url)
        if url.endswith("advancedsearch.php"):
            return {
                "response": {
                    "docs": [
                        {
                            "identifier": "licensed-indexed",
                            "title": "Indexed Movie",
                            "year": "1935",
                            "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
                        },
                        {
                            "identifier": "licensed-fallback",
                            "title": "Fallback Movie",
                            "year": "1940",
                        },
                        {
                            "identifier": "unlicensed-fallback",
                            "title": "Unlicensed Movie",
                        },
                    ]
                }
            }
        if url == DETAIL_URL.format(identifier="licensed-fallback"):
            return {"metadata": {
                "title": "Fallback Movie",
                "year": "1940",
                "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
            }}
        if url == DETAIL_URL.format(identifier="unlicensed-fallback"):
            return {"metadata": {"title": "Unlicensed Movie"}}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(api, "_json", fake_json)
    results = await api.search("classic movie")

    assert [item["identifier"] for item in results] == [
        "licensed-indexed",
        "licensed-fallback",
    ]
    assert results[1]["license"] == "CC BY 4.0"
    assert DETAIL_URL.format(identifier="licensed-fallback") in calls
    assert DETAIL_URL.format(identifier="unlicensed-fallback") in calls
