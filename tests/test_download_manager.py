from bot.services.download_manager import FileTooLarge


def test_file_too_large_carries_size():
    error = FileTooLarge(100)
    assert error.size == 100
