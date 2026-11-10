# Legal Movie Bot

A movie discovery and legal-download Telegram bot built with Python 3.11+, aiogram 3, SQLAlchemy async, Internet Archive and TMDB metadata.

## Features

- Search broad movie metadata (old and new titles) with TMDB.
- Browse TMDB Popular, Trending this week, and Now Playing lists.
- Open movie details, posters, synopsis, genres, runtime, regional watch providers, and official trailer links.
- Check every TMDB result for an exact title-and-year match in the explicitly licensed Internet Archive catalog.
- Download eligible files directly in Telegram when the source passes the license allowlist and the file fits the configured Telegram upload cap.
- Favorites, Amharic/English navigation, search history and admin tools.

## Configure

Set `BOT_TOKEN`, `ADMIN_IDS`, and `DATABASE_URL`. For broad movie discovery, obtain a TMDB API key at https://www.themoviedb.org/settings/api and set:

- `TMDB_API_KEY` — optional; without it, TMDB discovery lists and trailers are unavailable.
- `TMDB_WATCH_REGION` — two-letter region for watch-provider lookup and regional current releases (default `US`; set to `ET` for Ethiopia).

Never commit secrets. Restart/redeploy after setting variables.

## Trailer playback note

TMDB provides trailer metadata and YouTube trailer keys, not downloadable trailer files. The bot provides a Telegram trailer button and link with a preview where Telegram supports it; YouTube playback may open in Telegram's in-app browser rather than as a native Telegram video. Native in-chat video delivery is only possible for a separately authorized, direct video file.

## Legal download policy

TMDB is a metadata and watch-provider discovery service. It does not provide movie files or grant redistribution rights. Watch-provider links are not guaranteed to be available in every country or subscription tier. Internet Archive is a hosting/catalog platform, not a blanket redistribution license. Direct downloads remain restricted to items with an explicit allowlisted CC0, Public Domain Mark, CC BY or CC BY-SA license URL. For TMDB titles, the bot requires an exact normalized title and release-year match against the Archive result, then re-fetches the item metadata and verifies its license before offering download options. Automated checks cannot prove uploader ownership or legal chain of title; human review and a takedown process are still required. Never bypass rights checks, DRM or paid streaming services.

For copyrighted commercial releases, the bot links users to official watch, rental or purchase options instead of copying the movie file. Oversized authorized files are not sent through Telegram; the bot links to the authorized source page.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

Run tests:

```bash
BOT_TOKEN=123456:TEST ADMIN_IDS=1 DATABASE_URL=sqlite+aiosqlite:///:memory: python -m pytest -q
```

Only one polling replica should run for a Telegram bot token at a time.
