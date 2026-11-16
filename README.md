# Legal Movie Bot

Professional Telegram movie discovery with TMDB metadata, TV guides, favorites, licensed downloads, and TorrentClaw-powered torrent search.

## Features

- Search movies and TV shows with TMDB metadata.
- Browse trending/popular/latest titles, genres, trailers, and official watch-provider links.
- Search TorrentClaw using `/torrent title`; display quality, codec, size, seeders, and quality score.
- TorrentClaw download buttons are disabled by default. They appear only for info hashes independently reviewed and explicitly allowlisted by the operator.
- Optional local aria2 engine can download a single approved video file and upload it to Telegram; disabled by default, with file-size limits and no seeding.
- Search open-media catalogs: Internet Archive, Library of Congress, Wikimedia Commons, and eligible YouTube Creative Commons Attribution videos.
- Re-check supported source license and file metadata before licensed catalog downloads.
- Favorites, search history, admin statistics, PostgreSQL/SQLite persistence, request timeouts, and Railway health endpoint.

## TorrentClaw behavior and rights

TorrentClaw search results provide torrent metadata and magnet URLs but do not establish copyright ownership or distribution permission. Therefore, a search result alone never enables a download button. To enable a specific torrent, an administrator must independently verify that the work is public domain, openly licensed, or otherwise authorized for redistribution, then add its exact 40-character info hash to `TORRENTCLAW_APPROVED_INFOHASHES`. By default the bot sends the approved magnet link to the user, who opens it with a compatible torrent client. To enable server-side transfer, set `TORRENT_DOWNLOAD_ENABLED=true`. The Dockerfile installs aria2 and the bot starts it with RPC bound to localhost only. The engine re-checks that the magnet's info hash exactly matches the allowlist, rejects multi-file torrents and non-video outputs, enforces `MAX_UPLOAD_BYTES`, and disables seeding. The feature is off by default; only enable it after independently verifying redistribution rights for every allowlisted release. The engine does not establish or verify copyright ownership itself.

Do not add hashes based only on the title, source reputation, seed count, or AI matching score. Verify the rights for the exact release and territory.

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
- `MAX_UPLOAD_BYTES`, `MAX_CONCURRENT_DOWNLOADS`, `ARCHIVE_PAGE_SIZE`, `CACHE_TTL_SECONDS`, `REQUEST_TIMEOUT_SECONDS`, `TEMP_DIR`, `LOG_LEVEL` — operational settings.

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

The service starts with `python -m bot.main` and exposes `/health` on the assigned `PORT`. Railway builds the included Dockerfile, which installs aria2. Configure the required variables in Railway. Keep torrent downloads disabled until the approved-hash list is populated with independently rights-verified releases. Use PostgreSQL or a persistent volume for SQLite.

## Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB. TorrentClaw is an independent search service.
