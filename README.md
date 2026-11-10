# Legal Movie Bot

A movie discovery and legal-download Telegram bot built with Python 3.11+, aiogram 3, SQLAlchemy async, Internet Archive and optional TMDB metadata.

## Features

- Search broad movie metadata (old and new titles) with TMDB when `TMDB_API_KEY` is configured.
- Search Internet Archive for titles with eligible redistribution licenses.
- Clearly separate discovery from downloads: TMDB provides metadata and watch-provider links, not movie files or download rights.
- Show official TMDB watch-provider availability for the configured region when available.
- Direct Telegram delivery only for Archive items passing the existing conservative explicit-license allowlist.
- Favorites, popular/latest catalog entries, Amharic/English navigation and admin tools.

## Configure

Set `BOT_TOKEN`, `ADMIN_IDS`, and `DATABASE_URL`. For broad movie discovery, obtain a TMDB API key at https://www.themoviedb.org/settings/api and set:

- `TMDB_API_KEY` — optional; without it, Archive-only search remains available.
- `TMDB_WATCH_REGION` — two-letter region for watch-provider lookup (default `US`; availability varies by country).

Never commit secrets. Restart/redeploy after setting variables.

## Legal download policy

TMDB is a metadata and watch-provider discovery service. It does not provide movie files or grant redistribution rights. Watch-provider links are not guaranteed to be available in every country or subscription tier. Internet Archive is a hosting/catalog platform, not a blanket redistribution license. Direct downloads remain restricted to items with an explicit allowlisted CC0, Public Domain Mark, CC BY or CC BY-SA license URL. Automated checks cannot prove uploader ownership or legal chain of title; human review and a takedown process are still required. Never bypass rights checks, DRM or paid streaming services.

For copyrighted commercial releases, the bot links users to official watch, rental or purchase options instead of copying the movie file.

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
