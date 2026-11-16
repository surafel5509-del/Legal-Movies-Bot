from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.config import settings
from bot.database.db import Session
from bot.database.models import AdminClaim, User
from bot.services.catalog import admin_stats

router = Router()


class AdminLogin(StatesGroup):
    waiting_for_code = State()


async def is_admin(user_id: int) -> bool:
    if user_id in settings.admin_ids:
        return True
    async with Session() as session:
        return await session.scalar(select(AdminClaim.id).where(AdminClaim.telegram_id == user_id)) is not None


@router.message(Command("adminlogin"))
async def admin_login_start(message: Message, state: FSMContext):
    async with Session() as session:
        claimed = await session.get(AdminClaim, 1)
    if claimed:
        await message.answer("🔒 The one-time admin setup has already been completed.")
        return
    await state.set_state(AdminLogin.waiting_for_code)
    await message.answer("🔐 Enter the one-time setup code to claim bot administrator access.")


@router.message(AdminLogin.waiting_for_code)
async def admin_login_code(message: Message, state: FSMContext):
    code = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
    if not settings.admin_setup_code or code != settings.admin_setup_code:
        await state.clear()
        await message.answer("❌ Incorrect setup code. Run /adminlogin to try again.")
        return
    user_id = message.from_user.id
    try:
        async with Session() as session:
            session.add(AdminClaim(id=1, telegram_id=user_id))
            await session.commit()
    except IntegrityError:
        await state.clear()
        await message.answer("🔒 Admin setup was claimed already. No further claims are allowed.")
        return
    await state.clear()
    await message.answer("✅ Admin access activated for this Telegram account. You can use /admin.")


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
