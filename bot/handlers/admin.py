from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from bot.config import settings
from bot.database.db import Session
from bot.database.models import User
from bot.services.catalog import admin_stats

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    async with Session() as session:
        stats = await admin_stats(session)
    popular = "\n".join(
        f"• {str(title).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}: {count}"
        for title, count in stats["popular"]
    ) or "• No completed downloads"
    await message.answer(
        "🔐 <b>Admin dashboard</b>\n"
        f"Users: {stats['users']}\nActive users (30d): {stats['active']}\n"
        f"Searches: {stats['searches']}\nSuccessful downloads: {stats['downloads']}\n\n"
        f"<b>Top downloads</b>\n{popular}\n\n"
        "Commands: /broadcast followed by your announcement",
        parse_mode="HTML",
    )


@router.message(Command("broadcast"))
async def broadcast(message: Message, bot):
    if not is_admin(message.from_user.id):
        return
    content = (message.text or "").partition(" ")[2].strip()
    if not content:
        await message.answer("Usage: /broadcast Your announcement")
        return
    async with Session() as session:
        ids = list((await session.scalars(select(User.telegram_id))).all())
    sent = 0
    failed = 0
    for telegram_id in ids:
        try:
            await bot.send_message(telegram_id, content)
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"Broadcast finished. Sent: {sent}; failed: {failed}.")
