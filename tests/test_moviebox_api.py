from bot.services.moviebox_api import normalize_details, normalize_search_item


def test_normalize_search_item_accepts_movie_and_series_metadata():
    movie = normalize_search_item({
        "subjectId": "12345",
        "subjectType": 1,
        "detailPath": "movie/example",
        "title": "Example Movie",
        "releaseDate": "2024-05-01",
        "genre": "Drama,Action",
        "imdbRatingValue": 7.5,
    })
    series = normalize_search_item({
        "subjectId": "67890",
        "subjectType": 2,
        "detailPath": "tv/example",
        "title": "Example Series",
    })

    assert movie["kind"] == "Movie"
    assert movie["year"] == "2024"
    assert movie["genres"] == ["Drama", "Action"]
    assert series["kind"] == "TV series"


def test_normalize_search_item_rejects_other_types_and_incomplete_records():
    assert normalize_search_item({"subjectId": "1", "subjectType": 7, "title": "Anime"}) is None
    assert normalize_search_item({"subjectType": 1, "title": "No id", "detailPath": "x"}) is None


def test_normalize_details_exposes_metadata_but_not_media_urls():
    details = normalize_details({
        "subject": {
            "title": "Example",
            "releaseDate": "2022-01-01",
            "genre": ["Drama"],
            "countryName": "ET",
            "duration": 90,
        },
        "metadata": {"title": "Example", "description": "A description"},
        "resource": {"seasons": [{"se": 1, "maxEp": 8, "resolutions": [{"resolution": 720}]}]},
        "streams": [{"url": "https://media.invalid/video.mp4"}],
    }, {"title": "Fallback"})

    assert details["title"] == "Example"
    assert details["description"] == "A description"
    assert details["seasons"] == [{"number": 1, "episodes": 8, "resolutions": [720]}]
    assert "streams" not in details
    assert "url" not in details
