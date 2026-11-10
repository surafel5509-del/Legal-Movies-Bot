# Legal Movie Bot

A Telegram movie discovery and legal-download bot built with Python 3.11+, aiogram 3, SQLAlchemy async and yt-dlp.

## Features

- TMDB movie discovery, metadata, posters, trailers and regional official watch options.
- Search across Internet Archive, Library of Congress, Wikimedia Commons and YouTube videos explicitly marked Creative Commons Attribution.
- Direct Telegram delivery for source files that pass a fresh rights check and fit the configured upload cap.
- Source-specific metadata verification before displaying a download and again when the user presses Download.
- Strict URL/redirect allowlists, bounded streaming and upload-size checks.
- Favorites, Amharic/English navigation, search history and admin tools.

## Configure

Set `BOT_TOKEN`, `ADMIN_IDS`, and `DATABASE_URL`. For broad movie discovery, set a TMDB API key:

- `TMDB_API_KEY` — optional; without it, TMDB discovery, trailers and official provider metadata are unavailable.
- `TMDB_WATCH_REGION` — two-letter region for watch-provider lookup (for example `ET`).
- `MAX_UPLOAD_BYTES` — Telegram upload cap; defaults to 49 MiB.
- `ARCHIVE_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `REQUEST_TIMEOUT_SECONDS` — catalog tuning.

Internet Archive, Library of Congress and Wikimedia Commons public metadata APIs do not require paid keys. YouTube discovery/download uses the free open-source `yt-dlp` Python package; no YouTube API key is configured.

## Sources and rights policy

- **Internet Archive:** item metadata must expose an allowlisted CC0, Public Domain Mark, CC BY or CC BY-SA URL.
- **Library of Congress:** automated delivery requires an explicit supported Creative Commons URL or an item-level rights statement explicitly identifying the work as public domain. "No known copyright restrictions" by itself is not treated as a redistribution license.
- **Wikimedia Commons:** the file page must expose an allowlisted license URL and a trusted Wikimedia file URL.
- **YouTube:** only videos whose current extractor metadata explicitly declares the Creative Commons Attribution license are eligible. Standard YouTube-licensed videos are rejected. The uploader's declaration is not an independent proof of ownership; the source page and attribution are shown.

TMDB is a metadata and watch-provider discovery service. It does not provide movie files or grant redistribution rights. A source catalog is not a blanket license. The bot fetches source metadata again immediately before delivery and verifies the exact file URL, filename and license have not changed. It does not bypass DRM, paid streaming or access restrictions.

Automated rights checks cannot prove chain of title. Commercial copyrighted films such as many studio releases will generally have official watch/rent/buy options, not a free downloadable copy. The bot must never promise a legal free download when the source does not grant redistribution rights.

## Download behavior

Direct files are restricted to HTTPS URLs on known source domains. Redirects are checked hop by hop. Files are streamed to temporary storage under a strict byte cap. YouTube videos are downloaded using yt-dlp only after a fresh CC license check, with a second license check inside the downloader. Unsupported or oversized files are not sent to Telegram. Temporary files are removed after delivery.

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
