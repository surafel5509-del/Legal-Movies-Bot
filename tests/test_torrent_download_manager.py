from pathlib import Path

from bot.services.torrent_download_manager import _inside_directory, magnet_info_hash


def test_magnet_info_hash_extracts_exact_sha1():
    digest = "0123456789abcdef" * 2 + "01234567"
    magnet = f"magnet:?xt=urn:btih:{digest}&dn=Public+Domain+Film"
    assert magnet_info_hash(magnet) == digest


def test_magnet_info_hash_rejects_non_sha1_or_non_magnet():
    assert magnet_info_hash("https://example.com/file.mp4") is None
    assert magnet_info_hash("magnet:?xt=urn:btih:short") is None
    assert magnet_info_hash("magnet:?dn=no-info-hash") is None


def test_download_output_must_stay_inside_task_directory(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    safe = task_dir / "movie.mp4"
    outside = tmp_path / "outside.mp4"
    assert _inside_directory(safe, task_dir)
    assert not _inside_directory(outside, task_dir)
    assert not _inside_directory(Path(""), task_dir)
