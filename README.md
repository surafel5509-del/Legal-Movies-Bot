# Legal Movie Bot

A Telegram movie discovery and legal-download bot built with Python 3.11+, aiogram 3 and SQLAlchemy async.

## Features

- Broad movie search and metadata, posters, synopsis, trailers and regional official watch options via TMDB.
- Search across Internet Archive, Library of Congress film/video records and Wikimedia Commons media.
- A unified conservative rights gate: only explicit CC0, Public Domain Mark, CC BY and CC BY-SA license URLs are eligible for automated direct delivery.
- Exact normalized title-and-year matching for TMDB download checks.
- Telegram document delivery for supported files below the configured upload cap; oversized files link to their authorized source record.
- Favorites, Amharic/English navigation, search history and admin tools.

## Configure

Set `BOT_TOKEN`, `ADMIN_IDS`, and `DATABASE_URL`. For broad movie discovery, obtain a TMDB API key at https://www.themoviedb.org/settings/api and set:

- `TMDB_API_KEY` — optional; without it, TMDB discovery, trailers and official provider metadata are unavailable.
- `TMDB_WATCH_REGION` — two-letter region for watch-provider lookup (set to `ET` for Ethiopia).
- `MAX_UPLOAD_BYTES` — Telegram upload cap; defaults to 49 MiB.
- `ARCHIVE_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `REQUEST_TIMEOUT_SECONDS` — catalog tuning.

Internet Archive, Library of Congress and Wikimedia Commons public search/metadata endpoints do not require paid API keys.

## Legal download policy

TMDB is a metadata and watch-provider discovery service. It does not provide movie files or grant redistribution rights. Internet Archive, Library of Congress and Wikimedia Commons are source catalogs, not blanket redistribution licenses. This bot only offers direct files when the item's own metadata exposes an explicit allowlisted CC0, Public Domain Mark, CC BY or CC BY-SA license URL. Statements such as "no known restrictions", missing rights fields and non-allowlisted licenses are excluded. The license is revalidated before delivery.

For TMDB titles, the bot requires an exact normalized title-and-year match, then fetches item details and verifies the license again before offering files. Automated checks cannot prove uploader ownership or chain of title; human review and a takedown process are still required. Never bypass rights checks, DRM or paid streaming services. Copyrighted commercial titles such as many current studio releases will generally have official watch/rent/buy links, not a free downloadable copy.

Downloads are restricted to HTTPS URLs on known source domains. Redirects are checked hop by hop, files are streamed under a strict byte cap, and unsupported/oversized files are not sent to Telegram.

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
