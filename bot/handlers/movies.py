from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database.db import Session
from bot.database.models import Favorite, Movie, User
from bot.keyboards.inline import movie_actions
from bot.services.catalog import save_movie, toggle_favorite

router = Router()


@router.callback_query(F.data.startswith("movie:"))
async def movie_details(callback: CallbackQuery, archive):
    identifier = callback.data.split(":", 1)[1]
    try:
        data = await archive.details(identifier)
    except Exception:
        data = None
    if not data:
        await callback.answer("This title no longer passes the catalog rights check.", show_alert=True)
        return
    async with Session() as session:
        movie = await save_movie(session, data)
        await session.commit()
        movie = await session.scalar(select(Movie).options(selectinload(Movie.files)).where(Movie.id == movie.id))
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        fav = False
        if user:
            fav = bool(await session.scalar(select(Favorite.id).where(Favorite.user_id == user.id, Favorite.movie_id == movie.id)))
        files = list(movie.files)
        file_lines = []
        file_options = []
        for movie_file in files[:8]:
            size = _size(movie_file.file_size)
            quality = movie_file.resolution or "resolution not stated"
            file_lines.append(f"• {movie_file.format} · {quality} · {size}")
            file_options.append({
                "id": movie_file.id,
                "format": movie_file.format,
                "resolution": movie_file.resolution,
                "file_size": movie_file.file_size,
                "download_url": movie_file.download_url,
            })
        description = (movie.description or "No description supplied by the catalog.")[:1100]
        text = (
            f"🎬 <b>{_escape(movie.title)}</b>\n"
            f"📅 Year: {movie.release_year or 'Not listed'}\n"
            f"🎭 Genre: {_escape(movie.genre or 'Not listed')}\n"
            f"🌍 Language: {_escape(movie.language or 'Not listed')}\n\n"
            f"{_escape(description)}\n\n"
            f"⚖️ License: <b>{_escape(movie.license)}</b>\n"
            f"License terms: {movie.license_url}\n"
            f"Source record: {movie.source_url}\n\n"
            f"🎞 <b>Available files</b>\n" + ("\n".join(file_lines) if file_lines else "No compatible video files were listed.")
        )
        keyboard = movie_actions(identifier, file_options, fav)
        poster = movie.poster_url
        poster_caption = (
            f"🎬 <b>{_escape(movie.title)}</b>\n"
            f"📅 Year: {movie.release_year or 'Not listed'}\n"
            f"⚖️ {_escape(movie.license)}"
        )
    if poster:
        try:
            await callback.message.answer_photo(poster, caption=poster_caption, parse_mode="HTML")
        except Exception:
            pass
    await callback.message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("favorite:"))
async def favorite(callback: CallbackQuery):
    identifier = callback.data.split(":", 1)[1]
    async with Session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        movie = await session.scalar(select(Movie).where(Movie.source_id == identifier))
        if not user or not movie:
            await callback.answer("Open a movie first.", show_alert=True)
            return
        added = await toggle_favorite(session, user, movie.id)
        await session.commit()
    await callback.answer("Added to favorites" if added else "Removed from favorites")


def _size(value):
    if value is None:
        return "size unknown"
    return f"{value / (1024 * 1024):.1f} MB"


def _escape(value: str) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
