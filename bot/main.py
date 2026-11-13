import asyncio
import logging
import os

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import ai_tools
from bot.services.ai_providers import AIProviders


async def health(_request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "service": "ai-image-voice-bot",
        "providers": {
            "image": "AI Horde",
            "voice": "JSON2Video" if os.getenv("JSON2VIDEO_API_KEY") else "not_configured",
        },
    })


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
    health_runner = await run_health_server()
    timeout = aiohttp.ClientTimeout(total=60, connect=15, sock_read=45)
    http = aiohttp.ClientSession(
        timeout=timeout,
        headers={"User-Agent": "Surafel-AI-Image-Voice-Bot/1.0"},
    )
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp["ai"] = AIProviders(http)
    dp.include_router(ai_tools.router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await http.close()
        await bot.session.close()
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
