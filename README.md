# Legal Movie Bot

A professional Telegram movie-discovery bot with metadata, posters, trailers, TV-season guides, favorites, and downloads from explicitly licensed/open-media catalogs.

## Features

- Search movies and TV shows with TMDB metadata and poster enrichment.
- Browse popular, trending, latest releases, genres, trailers, and official watch-provider links.
- Search open-media catalogs: Internet Archive, Library of Congress, Wikimedia Commons, and eligible YouTube Creative Commons Attribution videos.
- Re-check a source's current license and file record immediately before every file transfer. Unknown or unsupported rights fail closed.
- Send supported, authorized video files directly in Telegram, subject to the configured upload-size limit.
- Save favorites, record searches/downloads, and provide an admin statistics/broadcast command.
- PostgreSQL/SQLite persistence, bounded concurrency, request timeouts, download host allowlists, and a Railway `/health` endpoint.
- English and Amharic welcome/menu copy.

## Rights and download policy

This bot does not search or distribute unauthorized copies, torrent magnets, stream-ripping links, or files from unverified sources. TMDB is used for metadata and official watch-provider discovery only; it does not grant download rights. A download is offered only when the source exposes a supported, explicit license from the bot's allowlist, and that source record is checked again when the user selects the file.

Supported open-license families currently include CC0, Public Domain Mark, CC BY and CC BY-SA on supported catalogs. License metadata is not a legal guarantee that an uploader owns every underlying right; the bot displays source and license attribution so users can review the terms.

## Commands

- `/start` — open the main menu
- `/search title` — search legal catalogs and movie metadata
- `/moviebox title` — metadata-only discovery; no stream or download URLs are exposed
- `/series title` — search TV series and browse seasons/episodes
- `/latest` — browse current releases
- `/categories` — browse genres
- `/admin` — admin statistics (configured admins only)
- `/myid` — show your Telegram user ID
- `/help` — usage and rights information

## Required environment variables

- `BOT_TOKEN` — Telegram bot token from @BotFather.

## Recommended environment variables

- `DATABASE_URL` — Railway PostgreSQL URL or local SQLite URL. Railway's mounted volume is available at `/data`; for SQLite on Railway use `sqlite+aiosqlite:////data/bot.db`.
- `TMDB_API_KEY` — TMDB API key for search, metadata, posters, trailers, TV guides, and watch-provider links.
- `TMDB_WATCH_REGION` — two-letter region code used for official provider discovery (default `US`; set to `ET` for Ethiopia where provider data is available).
- `ADMIN_IDS` — comma-separated Telegram numeric user IDs allowed to access admin commands.
- `ARCHIVE_CATALOG_ENABLED` — set `false` to disable open-media downloads while retaining TMDB discovery.
- `MAX_UPLOAD_BYTES`, `MAX_CONCURRENT_DOWNLOADS`, `ARCHIVE_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `REQUEST_TIMEOUT_SECONDS`, `TEMP_DIR`, `LOG_LEVEL` — operational settings.

Never commit API keys or Telegram tokens. Configure secrets in Railway → Service → Variables.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set BOT_TOKEN; TMDB_API_KEY is optional.
python -m bot.main
```

Run tests:

```bash
BOT_TOKEN=123456:TEST DATABASE_URL=sqlite+aiosqlite:///:memory: python -m pytest -q
```

## Railway

The service starts with `python -m bot.main` and exposes `/health` on Railway's assigned `PORT`. Configure `BOT_TOKEN`, `DATABASE_URL`, and optionally `TMDB_API_KEY` and `TMDB_WATCH_REGION` in the Railway service variables. Use a persistent PostgreSQL database for production, or point SQLite at the attached `/data` volume.

## TMDB attribution

This product uses the TMDB API but is not endorsed or certified by TMDB. TMDB metadata and provider availability can vary by region and may change over time.
