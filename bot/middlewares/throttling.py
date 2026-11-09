import time

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.last: dict[int, float] = {}

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user:
            now = time.monotonic()
            previous = self.last.get(user.id, 0)
            if now - previous < self.interval:
                return None
            self.last[user.id] = now
        return await handler(event, data)
