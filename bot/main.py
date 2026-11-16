from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import settings
from bot.database.db import init_db
from bot.handlers import admin, start, torrentclaw
from bot.services.torrentclaw_api import TorrentClaw
from bot.services.torrent_download_manager import TorrentDownloadManager

logger = logging.getLogger(__name__)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "service": "legal-movie-bot",
        "mode": "torrentclaw_only",
        "features": {
            "torrentclaw_search": True,
            "popular_movies": True,
            "recent_movies": True,
            "approved_download_buttons": bool(settings.torrentclaw_approved_infohashes),
            "server_downloads": settings.torrent_download_enabled,
            "one_time_admin_setup": True,
        },
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
    await init_db()
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    health_runner = await run_health_server()
    timeout = aiohttp.ClientTimeout(total=60, connect=15, sock_read=45)
    http = aiohttp.ClientSession(
        timeout=timeout,
        headers={"User-Agent": "LegalMovieBot/3.0 (+https://github.com/surafel5509-del/Legal-Movies-Bot)"},
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    torrent_downloads = TorrentDownloadManager(http)
    dp["torrentclaw"] = TorrentClaw(http, settings.torrentclaw_api_key)
    dp["torrent_downloads"] = torrent_downloads
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(torrentclaw.router)

    try:
        await torrent_downloads.start()
        await bot.set_my_commands([
            BotCommand(command="start", description="Open TorrentClaw movie bot"),
            BotCommand(command="torrent", description="Search TorrentClaw movies"),
            BotCommand(command="popular", description="Popular TorrentClaw movies"),
            BotCommand(command="recent", description="New TorrentClaw movies"),
            BotCommand(command="adminlogin", description="One-time administrator setup"),
            BotCommand(command="admin", description="Administrator dashboard"),
            BotCommand(command="help", description="Show help"),
        ])
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("TorrentClaw-only Legal Movie Bot is starting")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await torrent_downloads.close()
        await http.close()
        await bot.session.close()
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
