from bot.keyboards.inline import movie_actions


def test_movie_actions_include_telegram_and_direct_download():
    keyboard = movie_actions(
        "classic-film",
        [{
            "id": 12,
            "format": "MP4",
            "resolution": "720p",
            "file_size": 12 * 1024 * 1024,
            "download_url": "https://archive.org/download/classic-film/movie.mp4",
        }],
    )

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    telegram_button = next(button for button in buttons if button.callback_data == "download:classic-film:12")
    direct_button = next(button for button in buttons if button.url)

    assert telegram_button.text.startswith("⬇️ Send MP4")
    assert direct_button.url == "https://archive.org/download/classic-film/movie.mp4"


def test_movie_actions_keep_favorites_when_no_downloadable_files():
    keyboard = movie_actions("classic-film", [], favorite=True)
    buttons = [button for row in keyboard.inline_keyboard for button in row]

    assert any(button.callback_data == "favorite:classic-film" for button in buttons)
    assert any(button.callback_data == "nav:search" for button in buttons)
