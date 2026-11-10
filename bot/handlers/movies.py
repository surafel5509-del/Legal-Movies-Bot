import re
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
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
        file_ids = []
        for movie_file in files[:8]:
            size = _size(movie_file.file_size)
            quality = movie_file.resolution or "resolution not stated"
            file_lines.append(f"• {movie_file.format} · {quality} · {size}")
            file_ids.append(movie_file.id)
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
        keyboard = movie_actions(identifier, file_ids, fav)
        poster = movie.poster_url
    try:
        await callback.message.answer_photo(poster, caption=text[:1024], reply_markup=keyboard, parse_mode="HTML")
        if len(text) > 1024:
            await callback.message.answer(text[1024:], disable_web_page_preview=True)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
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


def _normalized_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


@router.callback_query(F.data.startswith("tmdb:"))
async def tmdb_movie_details(callback: CallbackQuery, tmdb):
    if not tmdb:
        await callback.answer("Movie discovery is not configured yet.", show_alert=True)
        return
    try:
        movie_id = int(callback.data.split(":", 1)[1])
        data = await tmdb.movie_details(movie_id)
    except Exception:
        data = None
    if not data:
        await callback.answer("Movie information is temporarily unavailable.", show_alert=True)
        return
    providers = ", ".join(data["providers"]) if data["providers"] else "No provider data listed for this region."
    text = (
        f"🎞 <b>{_escape(data['title'])}</b> ({_escape(data['year'])})\n"
        f"🎭 {_escape(data['genres'] or 'Genre not listed')}\n"
        f"⏱ {data['runtime'] or 'Unknown'} min\n\n"
        f"{_escape(data['overview'])}\n\n"
        f"📺 <b>Watch providers ({_escape(data['region'])})</b>\n{_escape(providers)}\n\n"
        "TMDB provides movie information and provider links, not movie files or download rights."
    )
    buttons = [[
        InlineKeyboardButton(text="▶️ Official watch options", url=data["watch_url"]),
        InlineKeyboardButton(text="ℹ️ TMDB details", url=data["details_url"]),
    ]]
    if data.get("trailer_url"):
        buttons.insert(0, [InlineKeyboardButton(text="🎬 Watch trailer", url=data["trailer_url"])])
    buttons.append([InlineKeyboardButton(text="⬇️ Check legal download", callback_data=f"tmdbdownload:{movie_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    if data.get("poster_url"):
        try:
            await callback.message.answer_photo(data["poster_url"], caption=text[:1024], reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)
    else:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)
    if data.get("trailer_url"):
        await callback.message.answer(
            "🎬 Trailer link (opens in Telegram's in-app browser when supported):\n" + data["trailer_url"],
            disable_web_page_preview=False,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("tmdbdownload:"))
async def tmdb_legal_download_check(callback: CallbackQuery, tmdb, archive):
    try:
        movie_id = int(callback.data.split(":", 1)[1])
        movie_data = await tmdb.movie_details(movie_id) if tmdb else None
    except Exception:
        movie_data = None
    if not movie_data:
        await callback.answer("Movie information is unavailable.", show_alert=True)
        return
    title_key = _normalized_title(movie_data["title"])
    year = movie_data["year"]
    if not title_key or year == "Not listed":
        await callback.message.answer("I cannot safely match this movie to a downloadable file because its title or release year is missing.")
        await callback.answer()
        return

    await callback.answer("Checking licensed sources…")
    try:
        candidates = await archive.search(movie_data["title"], 0)
    except Exception:
        candidates = []
    verified_data = None
    for candidate in candidates[:8]:
        if _normalized_title(candidate.get("title", "")) != title_key:
            continue
        if str(candidate.get("year") or "") != str(year):
            continue
        try:
            details = await archive.details(candidate["identifier"])
        except Exception:
            continue
        if not details:
            continue
        if _normalized_title(details.get("title", "")) != title_key or str(details.get("year") or "") != str(year):
            continue
        if not details.get("files"):
            continue
        verified_data = details
        break

    if not verified_data:
        await callback.message.answer(
            f"⬇️ No exact-match, explicitly licensed downloadable file was found for <b>{_escape(movie_data['title'])}</b> ({_escape(year)}).\n"
            "You can still use the official watch options. I will not offer an unrelated or unlicensed copy.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="▶️ Official watch options", url=movie_data["watch_url"])
            ]]),
        )
        return

    async with Session() as session:
        movie = await save_movie(session, verified_data)
        await session.commit()
        movie = await session.scalar(
            select(Movie).options(selectinload(Movie.files)).where(Movie.id == movie.id)
        )
        file_ids = [item.id for item in list(movie.files)[:8]]
    if not file_ids:
        await callback.message.answer("The source passed its license check but has no supported video files.")
        return
    await callback.message.answer(
        f"✅ Exact title and year matched, and the source license passed verification.\n"
        f"<b>{_escape(verified_data['title'])}</b> ({year})\nChoose a file to download:",
        reply_markup=movie_actions(verified_data["identifier"], file_ids),
        parse_mode="HTML",
    )
