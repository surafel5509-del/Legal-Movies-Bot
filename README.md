# Legal Movie Bot — TorrentClaw Edition

A Telegram movie-discovery bot powered by TorrentClaw.

## Features

- TorrentClaw-only movie search; no MovieBox, TMDB, or external catalog fallback.
- Relevance-sorted search with optional exact release-year filtering.
- Exact-title matching is preferred; approximate matches are clearly labelled.
- Separate Popular Movies and Newly Added Movies lists, both sourced from TorrentClaw.
- Popular/recent selections open a year-aware TorrentClaw release search.
- Release details include quality, codec, size, seeders, and quality score.
- Download buttons are rendered only for exact info hashes independently reviewed and approved for authorized redistribution.
- Optional aria2 server-side transfer for approved releases; otherwise the approved magnet opens in the user's torrent client.
- Persistent Railway volume support and health endpoint.

## Download authorization and technical limits

TorrentClaw aggregates torrent metadata from multiple sources. A search result, seeder count, rating, source name, or info hash does not prove that a release is legal to redistribute. An administrator must independently verify that the exact release is public domain, openly licensed, or otherwise authorized for redistribution before adding its 40-character SHA-1 info hash to TORRENTCLAW_APPROVED_INFOHASHES.

The exact hash check is retained to prevent a different magnet from being substituted after review. The bot does not provide unrestricted download buttons for unverified releases.

Server-side transfer is disabled by default. Set TORRENT_DOWNLOAD_ENABLED=true only after at least one release has been rights-verified and allowlisted. The engine is restricted to approved single-video torrents, does not seed, and enforces MAX_UPLOAD_BYTES (3 GB by default). Telegram's Bot API upload limit is separate; files above TELEGRAM_UPLOAD_MAX_BYTES (49 MB by default) cannot be sent as Telegram documents and are handed off through the approved magnet link.

These controls cannot be removed merely for testing. For development, use public-domain or explicitly licensed test torrents.

## Commands

- /start — main menu
- /torrent title [year] — search TorrentClaw
- /popular — popular TorrentClaw movies
- /recent — newly added TorrentClaw movies
- /help — usage and download policy
- /myid — show Telegram user ID

## Environment

- BOT_TOKEN — required Telegram token.
- DATABASE_URL — no longer used by the TorrentClaw-only bot runtime.
- TORRENTCLAW_API_KEY — optional TorrentClaw key.
- TORRENTCLAW_APPROVED_INFOHASHES — comma-separated exact hashes independently reviewed for authorized redistribution.
- TORRENT_DOWNLOAD_ENABLED — enable aria2 server-side downloads for approved hashes (default false).
- ARIA2_RPC_SECRET, ARIA2_RPC_PORT — local aria2 RPC settings.
- MAX_UPLOAD_BYTES — server-side safety ceiling (default 3 GB).
- TELEGRAM_UPLOAD_MAX_BYTES — Telegram document upload ceiling configured by this bot (default 49 MB).
- MAX_CONCURRENT_DOWNLOADS, TEMP_DIR, LOG_LEVEL — operational settings.

Never commit secrets. Configure them in Railway service variables.

## TorrentClaw API endpoints used

- GET /api/v1/search
- GET /api/v1/popular
- GET /api/v1/recent
- POST /api/v1/track
