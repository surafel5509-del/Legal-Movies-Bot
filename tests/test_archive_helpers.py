from bot.services.archive_api import _build_search_query, _int_or_none, _plain, _resolution, _year


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


def test_search_query_includes_phrase_title_and_description_terms():
    query = _build_search_query("The Great Escape")
    assert query.startswith("mediatype:movies AND")
    assert 'title:"The Great Escape"' in query
    assert 'title:("The" AND "Great" AND "Escape")' in query
    assert 'description:("The" AND "Great" AND "Escape")' in query


def test_search_query_sanitizes_lucene_operators_and_caps_terms():
    query = _build_search_query('film) OR *:* "bad"')
    assert query.startswith("mediatype:movies AND")
    assert "*:*" not in query
    assert "OR *" not in query
    assert query.count('"') < 30


def test_search_query_empty_input_is_safe():
    assert _build_search_query("!!!") == "mediatype:movies"
