from bot.services.archive_api import _int_or_none, _plain, _resolution, _year


def test_year_parsing():
    assert _year("released in 1928") == 1928
    assert _year("unknown") is None


def test_resolution_parsing():
    assert _resolution("film_1080p.mp4") == "1080p"
    assert _resolution("film.mp4") is None


def test_size_parsing():
    assert _int_or_none("12345") == 12345
    assert _int_or_none("unknown") is None


def test_description_cleanup():
    assert _plain("<p>Classic  film</p>") == "Classic film"
