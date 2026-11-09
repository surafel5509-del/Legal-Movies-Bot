from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.database.db import Session
from bot.database.models import User
from bot.services.catalog import get_favorites

router = Router()


@router.callback_query(F.data == "nav:favorites")
async def show_favorites(callback: CallbackQuery):
    async with Session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        movies = await get_favorites(session, user) if user else []
        builder = InlineKeyboardBuilder()
        for movie in movies:
            builder.button(text=f"🎬 {movie.title[:50]}", callback_data=f"movie:{movie.source_id}")
        builder.button(text="🏠 Home", callback_data="nav:home")
        builder.adjust(1)
    if not movies:
        await callback.message.answer("You have no saved favorites yet.")
    else:
        await callback.message.answer("❤️ <b>Your favorites</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
