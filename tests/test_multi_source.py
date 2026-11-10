import pytest

from bot.services.download_manager import _trusted_download_url, _youtube_video_id
from bot.services.license_verification import verify_archive_rights
from bot.services.multi_source_api import MultiSourceCatalog, _loc_rights, _text, _year
from bot.handlers.movies import _candidate_title_key
from bot.services.youtube_cc_api import (
    YOUTUBE_CC_LABEL, YOUTUBE_LICENSE_URL, YouTubeCCCatalog, is_youtube_cc_license,
)


def test_youtube_cc_license_is_required_and_standard_license_rejected():
    assert is_youtube_cc_license("Creative Commons Attribution license (reuse allowed)")
    assert not is_youtube_cc_license("Standard YouTube License")
    assert not is_youtube_cc_license(None)


def test_youtube_catalog_maps_only_long_cc_videos():
    mapped = YouTubeCCCatalog._map({
        "id": "abcdefghijk", "title": "Public Domain Film (1940)",
        "duration": 3600, "license": "Creative Commons Attribution license (reuse allowed)",
        "ext": "mp4", "height": 720, "filesize": 1234,
    })
    assert mapped["identifier"] == "youtube:abcdefghijk"
    assert mapped["license"] == YOUTUBE_CC_LABEL
    assert mapped["license_url"] == YOUTUBE_LICENSE_URL
    assert mapped["year"] == 1940
    assert mapped["files"][0]["download_url"].endswith("v=abcdefghijk")
    assert YouTubeCCCatalog._map({
        "id": "abcdefghijk", "title": "Short clip",
        "duration": 90, "license": "Creative Commons Attribution license (reuse allowed)",
    }) is None


def test_tmdb_exact_match_normalizes_only_youtube_generic_suffixes():
    assert _candidate_title_key("The General (1926) - Full Movie", "youtube:abcdefghijk") == "the general"
    assert _candidate_title_key("The General (1926)", "archive:film") == "the general 1926"


def test_youtube_urls_are_parsed_strictly():
    assert _youtube_video_id("https://www.youtube.com/watch?v=abcdefghijk") == "abcdefghijk"
    assert _youtube_video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert _youtube_video_id("https://youtube.com.evil.example/watch?v=abcdefghijk") is None
    assert _youtube_video_id("http://youtube.com/watch?v=abcdefghijk") is None


def test_loc_only_accepts_explicit_public_domain_or_supported_cc_rights():
    assert _loc_rights({"rights": "Public domain"})[0] is True
    assert _loc_rights({"rights": "No known copyright restrictions"})[0] is False
    assert _loc_rights({"rights": "Not in the public domain"})[0] is False
    assert _loc_rights({"rights_url": "https://creativecommons.org/licenses/by/4.0/"})[0] is True


def test_archive_license_and_text_helpers():
    assert verify_archive_rights({"licenseurl": "https://creativecommons.org/licenses/by/4.0/"})[0]
    assert verify_archive_rights({"rights": "No known restrictions"}) == (False, None, None)
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
            "pageid": 42, "title": "File:Example Film (1936).mp4",
            "imageinfo": [{
                "url": "https://upload.wikimedia.org/example/film.mp4",
                "size": 123456, "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example_Film",
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
async def test_commons_details_rejects_untrusted_media(monkeypatch):
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
async def test_loc_details_rechecks_public_domain_and_video_resource(monkeypatch):
    api = MultiSourceCatalog(session=None)

    async def fake_json(url, params=None):
        return {"item": {
            "title": "Documentary (1940)", "date": "1940", "rights": "Public domain",
            "url": "https://www.loc.gov/item/test/",
            "resources": [{
                "url": "https://tile.loc.gov/storage/test.mp4",
                "mimetype": "video/mp4", "filesize": "5000",
            }],
        }}

    monkeypatch.setattr(api, "_json", fake_json)
    result = await api.details("loc:test")
    assert result["year"] == 1940
    assert result["license"] == "Public domain (Library of Congress rights statement)"
    assert result["files"][0]["file_size"] == 5000


@pytest.mark.asyncio
async def test_loc_details_rejects_unknown_rights(monkeypatch):
    api = MultiSourceCatalog(session=None)

    async def fake_json(url, params=None):
        return {"item": {"title": "Unknown rights film", "rights": "No known restrictions"}}

    monkeypatch.setattr(api, "_json", fake_json)
    assert await api.details("loc:test") is None
