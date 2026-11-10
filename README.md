# Legal Movie Bot

A movie-only Telegram search bot built with Python 3.11+, aiogram 3, SQLAlchemy async, and the Internet Archive metadata APIs. It is intentionally conservative: an item is visible only when the Archive metadata contains an explicit allowlisted Creative Commons or public-domain license URL. Unknown, non-commercial, no-derivatives, and contradictory rights metadata are excluded.

## Features implemented

- `/start` welcome screen, inline navigation, Help and About.
- English and Amharic welcome/navigation labels; per-user language preference.
- Internet Archive movie discovery with phrase, all-title-term, and individual-title-term search passes; title-first relevance ranking, pagination, deduplication, in-memory TTL cache, retry and timeout handling. Search results remain restricted to explicitly allowlisted redistribution licenses.
- Movie details sourced from Archive metadata: title, year, description, genre, language, poster, license, source page and available MP4/WebM/M4V/OGV files.
- Conservative license allowlist: CC0, Public Domain Mark, CC BY and CC BY-SA versions 1.0–4.0. License checks run during search and again during metadata retrieval.
- Direct document delivery for files within `MAX_UPLOAD_BYTES`, streamed to a temporary file (not loaded fully into memory); Telegram `file_id` is cached and reused.
- Oversized files are not transferred; users receive the authorized Archive item page and a clear size-limit message.
- Favorites, recently added and popular completed downloads.
- Admin-only `/admin` statistics and `/broadcast` announcements.
- Rate limiting, configured admin IDs, environment-based secrets, structured logs, async SQLite/PostgreSQL support, and `/health` endpoint.
- Unit tests for rights verification, metadata parsing helpers, file-size exception and admin authorization.

## Important legal note

Internet Archive is a hosting/catalog platform, not a blanket redistribution license. The bot checks explicit `licenseurl` metadata against a conservative allowlist. This automated gate is not legal advice and cannot independently prove that an uploader owned the rights or that the metadata is accurate. Before operating publicly, add a human review/notice-and-takedown process and review each catalog item’s license and source record. If a record has no recognized license URL or contains contradictory rights wording, it is excluded. Never bypass the check to make a title appear downloadable.

The current allowlist deliberately excludes CC BY-NC, CC BY-ND, CC BY-NC-SA, CC BY-NC-ND, unknown licenses, and unverified claims of public domain. A future extension should add a separately audited rights-evidence workflow rather than widening this allowlist casually. The allowlist and stored license label are checked again immediately before each file transfer; this still cannot prove uploader authority or replace human rights review.

## Local setup

1. Install Python 3.11 or newer.
2. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy its token.
3. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env`; set `BOT_TOKEN` and comma-separated numeric `ADMIN_IDS`.
5. Run:

   ```bash
   python -m bot.main
   ```

The default SQLite database is `./data/bot.db`. The application creates its schema and parent directory at startup. Do not commit `.env` or the database.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `BOT_TOKEN` | Telegram Bot API token (required) | — |
| `ADMIN_IDS` | Comma-separated Telegram numeric IDs | empty |
| `DATABASE_URL` | SQLAlchemy async database URL | `sqlite+aiosqlite:///./data/bot.db` |
| `LOG_LEVEL` | Python log level | `INFO` |
| `MAX_UPLOAD_BYTES` | Hard cap for Telegram document uploads | 49 MiB |
| `MAX_CONCURRENT_DOWNLOADS` | Concurrent file transfers | `2` |
| `ARCHIVE_PAGE_SIZE` | Archive search page size (1–50) | `10` |
| `CACHE_TTL_SECONDS` | Search cache TTL | `600` |
| `REQUEST_TIMEOUT_SECONDS` | Archive API timeout | `25` |
| `TEMP_DIR` | Temporary download directory | `/tmp/legal-movie-bot` |
| `ARCHIVE_CATALOG_ENABLED` | Enable/disable Archive search | `true` |
| `ACTIVE_DAYS` | Admin activity reporting window (currently fixed at 30d in query) | `30` |

For PostgreSQL, use `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME`. Railway's `DATABASE_URL` can be mapped to this variable; the app normalizes common `postgres://` and `postgresql://` forms automatically.

## Railway deployment

1. Push this repository to GitHub and connect the repository to Railway.
2. Create a Railway project and deploy the `main` branch as a Python service. Railway reads `railway.json`; the Procfile is also included.
3. Set `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL`, and any desired tuning variables in the Railway service Variables panel. Never place the bot token in Git.
4. **Persistent SQLite:** add a Railway Volume mounted at `/data`, then set `DATABASE_URL=sqlite+aiosqlite:////data/bot.db`. The volume must be mounted before the bot starts. Without a volume, local SQLite data can be lost when a container is replaced.
5. **Recommended production database:** provision Railway PostgreSQL and set `DATABASE_URL` to its connection string (use the async `postgresql+asyncpg` scheme if needed). PostgreSQL avoids single-container SQLite persistence constraints.
6. The app listens on Railway's `PORT` and serves `GET /health` for health checks while aiogram polls Telegram.

Only one bot polling replica should run for a token at a time. Do not scale this long-polling worker horizontally without moving to a webhook/leader-election design.

## Admin commands

- `/admin` — counts and top completed downloads; configured admin IDs only.
- `/broadcast Your message` — sends a plain-text announcement to registered users; configured admin IDs only.

The admin dashboard currently covers core counters and broadcast. Featured-movie management, category curation, source toggles via admin UI, detailed recent-activity/error dashboards, and search-history UI are not yet implemented.

## Tests

```bash
BOT_TOKEN=123456:TEST ADMIN_IDS=1 DATABASE_URL=sqlite+aiosqlite:///:memory: python -m pytest -q
```

GitHub Actions runs compile checks and the test suite on Python 3.11, 3.12 and 3.13 for pushes to `main` and pull requests. Tests use local helpers and do not fetch or download movie content. For integration tests, mock Archive HTTP responses; do not use copyrighted movie payloads.

## Known limitations / production hardening still needed

- This repository is an application scaffold, not a guarantee that every Archive.org record is lawful to redistribute. Operate only after reviewing applicable law, source records and licenses, and establishing a contact and takedown process.
- Rights verification relies on explicit Archive `licenseurl` metadata and a conservative allowlist. It is not a legal determination of chain of title; human review and a takedown process are required for a public service.
- Search uses Internet Archive's indexed metadata; it cannot guarantee that every film exists in that catalog. Results can vary as the Archive index changes. Spelling correction, multilingual title translation, and a separate commercial-film metadata provider are not configured.
- Movie metadata availability varies; runtime, codec, quality and language may be absent. The bot never invents these values. Resolution is inferred only when encoded in the filename; codec is left unknown.
- The Archive search endpoint may omit license metadata for some records; such records are intentionally excluded even if their item page may show a license.
- The bot sends files only up to its configured upload cap. Actual Telegram Bot API limits can change; tune `MAX_UPLOAD_BYTES` conservatively for the Bot API endpoint in use.
- Download progress bars are not shown because aiogram upload callbacks depend on the exact transport behavior; users receive a preparation notice and a completion message only after Telegram accepts the file.
- The in-memory search cache is per process; no distributed cache is configured.
- Admin feature/category management, admin UI source controls, recommendation ranking, category browse screens, detailed recent activity/error views, and robust search-history screens remain future work.
- Automated tests do not yet cover live Telegram startup, a full mocked API-to-database search flow, database CRUD against PostgreSQL, or a full Telegram upload. Validate these in a staging bot before public launch.

## Project layout

```text
legal-movie-bot/
├── bot/
│   ├── handlers/       # Telegram commands and callbacks
│   ├── keyboards/      # Inline keyboards
│   ├── services/       # Archive API, license gate, downloads, catalog persistence
│   ├── database/       # SQLAlchemy models and async session setup
│   ├── middlewares/    # Rate limiting
│   ├── config.py
│   └── main.py
├── tests/
├── requirements.txt
├── Procfile
├── railway.json
├── .env.example
└── README.md
```
