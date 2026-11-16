from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.database.db import engine, init_db
from bot.handlers import admin, discovery, downloads, favorites, movies, search, series, start, torrentclaw
from bot.services.download_manager import DownloadManager
from bot.services.multi_source_api import MultiSourceCatalog
from bot.services.moviebox_api import MovieBoxCatalog
from bot.services.tmdb_api import TMDBAPI
from bot.services.torrentclaw_api import TorrentClaw
from bot.services.torrent_download_manager import TorrentDownloadManager

logger = logging.getLogger(__name__)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "service": "legal-movie-bot",
        "features": {
            "movie_search": True,
            "tv_search": bool(settings.tmdb_api_key),
            "licensed_downloads": settings.catalog_enabled,
            "torrentclaw_search": True,
            "approved_torrent_buttons": bool(settings.torrentclaw_approved_infohashes),
            "torrent_server_downloads": settings.torrent_download_enabled,
            "favorites": True,
        },
        "metadata_provider": "TMDB" if settings.tmdb_api_key else "not_configured",
        "torrentclaw": "configured",
    })


async def run_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080")))
    await site.start()
    return runner


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    await init_db()

    health_runner = await run_health_server()
    timeout = aiohttp.ClientTimeout(total=60, connect=15, sock_read=45)
    http = aiohttp.ClientSession(
        timeout=timeout,
        headers={"User-Agent": "LegalMovieBot/2.0 (+https://github.com/surafel5509-del/Legal-Movies-Bot)"},
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    archive = MultiSourceCatalog(http)
    downloads_manager = DownloadManager()
    downloads_manager.session = http
    torrent_downloads = TorrentDownloadManager(http)
    await torrent_downloads.start()

    dp["archive"] = archive
    dp["tmdb"] = TMDBAPI(http) if settings.tmdb_api_key else None
    dp["moviebox"] = MovieBoxCatalog()
    dp["downloads"] = downloads_manager
    dp["torrentclaw"] = TorrentClaw(http, settings.torrentclaw_api_key)
    dp["torrent_downloads"] = torrent_downloads

    for router in (start.router, search.router, torrentclaw.router, discovery.router,
                   movies.router, series.router, favorites.router, downloads.router, admin.router):
        dp.include_router(router)

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Open the movie bot"),
            BotCommand(command="search", description="Search licensed catalogs"),
            BotCommand(command="torrent", description="Search TorrentClaw releases"),
            BotCommand(command="moviebox", description="Search movie metadata"),
            BotCommand(command="series", description="Search TV series"),
            BotCommand(command="latest", description="Browse latest releases"),
            BotCommand(command="categories", description="Browse movie genres"),
            BotCommand(command="help", description="Show help"),
        ])
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Legal Movie Bot is starting")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await torrent_downloads.close()
        await http.close()
        await bot.session.close()
        await health_runner.cleanup()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
