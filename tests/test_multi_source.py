import pytest

from bot.services.license_verification import verify_archive_rights
from bot.services.multi_source_api import MultiSourceCatalog, _text, _year
from bot.services.download_manager import _trusted_download_url


def test_accepts_http_creative_commons_url_and_canonicalizes_to_https():
    ok, label, url = verify_archive_rights({"licenseurl": "http://creativecommons.org/licenses/by-sa/4.0/"})
    assert ok and label == "CC BY-SA 4.0"
    assert url == "https://creativecommons.org/licenses/by-sa/4.0/"


def test_rejects_no_known_restrictions_without_license_url():
    assert verify_archive_rights({"rights": "No known restrictions"}) == (False, None, None)


def test_external_catalog_text_and_year_normalization():
    assert _text("<p>  Silent   Film </p>") == "Silent Film"
    assert _year("Copyright 1936, restored 2001") == 1936
    assert _year("unknown") is None


def test_download_hosts_are_allowlisted_and_https_only():
    assert _trusted_download_url("https://archive.org/download/id/movie.mp4")
    assert _trusted_download_url("https://upload.wikimedia.org/a/b/movie.webm")
    assert _trusted_download_url("https://tile.loc.gov/path/movie.mp4")
    assert not _trusted_download_url("http://archive.org/download/id/movie.mp4")
    assert not _trusted_download_url("https://evil.example/movie.mp4")
    assert not _trusted_download_url("https://archive.org.evil.example/movie.mp4")
    assert not _trusted_download_url("https://archive.org:8443/download/id/movie.mp4")


@pytest.mark.asyncio
async def test_commons_details_refetches_license_and_media_metadata(monkeypatch):
    api = MultiSourceCatalog(session=None)

    async def fake_json(url, params=None):
        assert params["pageids"] == "42"
        return {"query": {"pages": {"42": {
            "pageid": 42,
            "title": "File:Example Film (1936).mp4",
            "imageinfo": [{
                "url": "https://upload.wikimedia.org/example/film.mp4",
                "size": 123456,
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example_Film",
                "extmetadata": {
                    "LicenseUrl": {"value": "http://creativecommons.org/licenses/by-sa/4.0/"},
                    "DateTimeOriginal": {"value": "1936-01-01"},
                    "ImageDescription": {"value": "<p>Public domain era film</p>"},
                },
            }],
        }}}}

    monkeypatch.setattr(api, "_json", fake_json)
    result = await api.details("commons:42")
    assert result["title"] == "Example Film (1936)"
    assert result["year"] == 1936
    assert result["license"] == "CC BY-SA 4.0"
    assert result["files"][0]["download_url"].startswith("https://upload.wikimedia.org/")


@pytest.mark.asyncio
async def test_commons_details_rejects_unlicensed_or_untrusted_media(monkeypatch):
    api = MultiSourceCatalog(session=None)

    async def fake_json(url, params=None):
        return {"query": {"pages": {"7": {
            "pageid": 7, "title": "File:Film.mp4",
            "imageinfo": [{
                "url": "https://evil.example/film.mp4",
                "extmetadata": {"LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"}},
            }],
        }}}}

    monkeypatch.setattr(api, "_json", fake_json)
    assert await api.details("commons:7") is None


@pytest.mark.asyncio
async def test_loc_details_requires_explicit_license_and_trusted_video_resource(monkeypatch):
    api = MultiSourceCatalog(session=None)

    async def fake_json(url, params=None):
        return {"item": {
            "title": "Documentary (1940)", "date": "1940",
            "rights_url": "https://creativecommons.org/publicdomain/mark/1.0/",
            "url": "https://www.loc.gov/item/test/",
            "resources": [{
                "url": "https://tile.loc.gov/storage/test.mp4",
                "mimetype": "video/mp4", "filesize": "5000",
            }],
        }}

    monkeypatch.setattr(api, "_json", fake_json)
    result = await api.details("loc:test")
    assert result["year"] == 1940
    assert result["license"] == "Public Domain Mark 1.0"
    assert result["files"][0]["file_size"] == 5000


@pytest.mark.asyncio
async def test_loc_details_rejects_unknown_rights(monkeypatch):
    api = MultiSourceCatalog(session=None)

    async def fake_json(url, params=None):
        return {"item": {"title": "Unknown rights film", "rights": "No known restrictions"}}

    monkeypatch.setattr(api, "_json", fake_json)
    assert await api.details("loc:test") is None
