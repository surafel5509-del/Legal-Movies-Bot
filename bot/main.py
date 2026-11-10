import asyncio
import logging
import os

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.database.db import engine, init_db
from bot.handlers import admin, discovery, downloads, favorites, movies, search, start
from bot.middlewares.throttling import RateLimitMiddleware
from bot.services.multi_source_api import MultiSourceCatalog
from bot.services.tmdb_api import TMDBAPI
from bot.services.download_manager import DownloadManager


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "legal-movie-bot"})


async def run_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", health)
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
    http = aiohttp.ClientSession(headers={
        "User-Agent": "LegalMovieBot/2.0 (movie discovery; rights-verified downloads; contact via project repository)"
    })
    archive = MultiSourceCatalog(http)
    tmdb = TMDBAPI(http) if settings.tmdb_api_key else None
    downloads_manager = DownloadManager()
    downloads_manager.session = http
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["archive"] = archive
    dp["tmdb"] = tmdb
    dp["downloads"] = downloads_manager
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware(0.25))
    for router in (start.router, search.router, movies.router, downloads.router, favorites.router, discovery.router, admin.router):
        dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await http.close()
        await bot.session.close()
        await health_runner.cleanup()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
