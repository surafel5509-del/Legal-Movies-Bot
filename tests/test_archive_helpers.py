from bot.services.archive_api import (
    _int_or_none,
    _lucene_phrase,
    _match_score,
    _plain,
    _resolution,
    _year,
)


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


def test_search_ranking_prefers_exact_title():
    exact = _match_score("sherlock holmes", {"sherlock", "holmes"}, "Sherlock Holmes", "")
    partial = _match_score("sherlock holmes", {"sherlock", "holmes"}, "The Adventures of Sherlock", "")
    assert exact > partial


def test_search_ranking_uses_description_as_secondary_signal():
    title_match = _match_score("moon", {"moon"}, "Moon", "")
    description_match = _match_score("moon", {"moon"}, "Space Journey", "A story about the moon")
    assert title_match > description_match


def test_lucene_phrase_escapes_reserved_characters():
    assert _lucene_phrase('A+B: "Film"') == r'A\+B\: \"Film\"'
