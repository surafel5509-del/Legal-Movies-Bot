from bot.services.license_verification import verify_archive_rights
from bot.services.multi_source_api import _text, _year
from bot.services.download_manager import _trusted_download_url


def test_accepts_http_creative_commons_url_and_canonicalizes_to_https():
    ok, label, url = verify_archive_rights({
        "licenseurl": "http://creativecommons.org/licenses/by-sa/4.0/"
    })
    assert ok
    assert label == "CC BY-SA 4.0"
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
