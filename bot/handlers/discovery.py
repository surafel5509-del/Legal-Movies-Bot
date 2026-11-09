from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from bot.database.db import Session
from bot.database.models import Download, Movie

router = Router()


@router.callback_query(F.data.in_({"nav:popular", "nav:latest"}))
async def discovery(callback: CallbackQuery):
    async with Session() as session:
        if callback.data == "nav:popular":
            rows = await session.execute(
                select(Movie)
                .join(Download, Download.movie_id == Movie.id)
                .where(Download.status == "sent")
                .group_by(Movie.id)
                .order_by(func.count(Download.id).desc())
                .limit(10)
            )
            movies = list(rows.scalars())
            heading = "🔥 Popular downloads"
        else:
            movies = list((await session.scalars(select(Movie).order_by(Movie.created_at.desc()).limit(10))).all())
            heading = "🆕 Recently added"
        builder = InlineKeyboardBuilder()
        for movie in movies:
            builder.button(text=f"🎬 {movie.title[:50]}", callback_data=f"movie:{movie.source_id}")
        builder.adjust(1)
    if not movies:
        await callback.message.answer("No catalog entries yet. Search for a title to discover verified movies.")
    else:
        await callback.message.answer(heading, reply_markup=builder.as_markup())
    await callback.answer()
