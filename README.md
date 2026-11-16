# Legal Movie Bot

Professional Telegram movie discovery with TMDB metadata, TV guides, favorites, licensed downloads, and TorrentClaw-powered torrent search.

## Features

- Search movies and TV shows with TMDB metadata.
- Browse trending/popular/latest titles, genres, trailers, and official watch-provider links.
- Search TorrentClaw using `/torrent title`; display quality, codec, size, seeders, and quality score.
- TorrentClaw download buttons remain disabled unless an administrator independently verifies redistribution rights and approves the exact release.
- Optional local aria2 engine can download a single approved video file; disabled by default and configured not to seed.
- Search open-media catalogs: Internet Archive, Library of Congress, Wikimedia Commons, and eligible YouTube Creative Commons Attribution videos.
- Re-check supported source license and file metadata before licensed catalog downloads.
- Favorites, search history, admin statistics, PostgreSQL/SQLite persistence, request timeouts, and Railway health endpoint.

## Download limits and Telegram delivery

- Server-side downloads are capped at **3 GB** by default. Files larger than this are rejected.
- Telegram's hosted Bot API upload cap is separate (configured to **49 MB** by default). Files above that limit are not uploaded through Telegram; users receive the authorized source page or approved magnet so they can retrieve the file with a suitable client.
- Set `MAX_UPLOAD_BYTES` to change the server-side safety ceiling and `TELEGRAM_UPLOAD_MAX_BYTES` to configure the bot's Telegram upload ceiling. Raising the Telegram value does not raise Telegram's own API limit.

## TorrentClaw behavior and rights

TorrentClaw search results provide torrent metadata and magnet URLs but do not establish copyright ownership or distribution permission. A search result alone never enables a download button. An administrator must independently verify that the work is public domain, openly licensed, or otherwise authorized for redistribution, then add its exact 40-character info hash to `TORRENTCLAW_APPROVED_INFOHASHES`. The hash is used to bind approval to the exact torrent release and prevent a different magnet from being substituted; it is not evidence of copyright permission by itself.

By default the bot sends an approved magnet link to the user's compatible torrent client. To enable server-side transfer, set `TORRENT_DOWNLOAD_ENABLED=true` only after the approved list contains releases with independently verified redistribution rights. The Dockerfile installs aria2 and the bot starts it with RPC bound to localhost only. The engine re-checks the approved magnet, rejects multi-file and non-video outputs, enforces the 3 GB server-side limit, and disables seeding. The feature is off by default.

Do not approve hashes based only on the title, source reputation, seed count, or AI matching score. Verify the rights for the exact release and territory.

## Commands

- `/start` — open the main menu
- `/search title` — search licensed catalogs and movie metadata
- `/torrent title` — search TorrentClaw
- `/moviebox title` — metadata-only discovery
- `/series title` — search TV series
- `/latest` — browse current releases
- `/categories` — browse genres
- `/admin` — admin statistics
- `/myid` — show Telegram user ID
- `/help` — usage and rights information

## Environment

- `BOT_TOKEN` — required Telegram bot token.
- `DATABASE_URL` — Railway PostgreSQL or local SQLite.
- `TMDB_API_KEY` — optional TMDB metadata key.
- `TMDB_WATCH_REGION` — two-letter provider region (default recommendation: `ET`).
- `TORRENTCLAW_API_KEY` — optional TorrentClaw key for higher rate limits.
- `TORRENTCLAW_APPROVED_INFOHASHES` — comma-separated exact hashes reviewed for authorized redistribution; leave empty to disable TorrentClaw download buttons.
- `TORRENT_DOWNLOAD_ENABLED` — set to `true` to enable local aria2 server-side downloads for approved hashes (default `false`).
- `ARIA2_RPC_SECRET` — optional local aria2 RPC secret; a random secret is generated when blank. RPC listens only on localhost.
- `ARIA2_RPC_PORT` — local aria2 RPC port (default `6800`).
- `ADMIN_IDS` — comma-separated Telegram numeric admin IDs.
- `ARCHIVE_CATALOG_ENABLED` — enable/disable open-media catalog downloads.
- `MAX_UPLOAD_BYTES` — server-side download safety cap (default 3 GB).
- `TELEGRAM_UPLOAD_MAX_BYTES` — Telegram upload cap (default 49 MiB).
- `MAX_CONCURRENT_DOWNLOADS`, `ARCHIVE_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `REQUEST_TIMEOUT_SECONDS`, `TEMP_DIR`, `LOG_LEVEL` — operational settings.

Never commit API keys or Telegram tokens. Configure secrets in Railway → Service → Variables.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

Run tests:

```bash
BOT_TOKEN=123456:TEST DATABASE_URL=sqlite+aiosqlite:///:memory: python -m pytest -q
```

## Railway

The service starts with `python -m bot.main` and exposes `/health` on the assigned `PORT`. Railway builds the included Dockerfile, which installs aria2. Configure required variables in Railway. Keep torrent downloads disabled until the approved-hash list is populated with independently rights-verified releases. Use PostgreSQL or a persistent volume for SQLite.

## Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB. TorrentClaw is an independent search service.
