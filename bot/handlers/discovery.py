from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from bot.database.db import Session
from bot.database.models import Download, Movie
from bot.keyboards.inline import metadata_results

router = Router()


@router.callback_query(F.data.in_({"nav:popular", "nav:latest", "nav:trending"}))
async def discovery(callback: CallbackQuery, tmdb):
    category = callback.data.split(":", 1)[1]
    movies = []
    if tmdb:
        try:
            movies = await tmdb.discover_movies(category)
        except Exception:
            movies = []

    if movies:
        labels = {
            "popular": "🔥 Popular movies",
            "latest": "🆕 Now playing",
            "trending": "📈 Trending this week",
        }
        await callback.message.answer(
            f"<b>{labels[category]}</b>\nChoose a movie for details, trailer and legal download check.",
            reply_markup=metadata_results(movies),
            parse_mode="HTML",
        )
    else:
        async with Session() as session:
            if category == "popular":
                rows = await session.execute(
                    select(Movie)
                    .join(Download, Download.movie_id == Movie.id)
                    .where(Download.status == "sent")
                    .group_by(Movie.id)
                    .order_by(func.count(Download.id).desc())
                    .limit(10)
                )
                local_movies = list(rows.scalars())
            else:
                local_movies = list((await session.scalars(
                    select(Movie).order_by(Movie.created_at.desc()).limit(10)
                )).all())
            builder = InlineKeyboardBuilder()
            for movie in local_movies:
                builder.button(text=f"🎬 {movie.title[:50]}", callback_data=f"movie:{movie.source_id}")
            builder.adjust(1)
        if not local_movies:
            await callback.message.answer(
                "Movie lists are temporarily unavailable. Make sure TMDB_API_KEY is configured, then try again."
            )
        else:
            await callback.message.answer("🎬 Movies from your verified catalog", reply_markup=builder.as_markup())
    await callback.answer()
