from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.inline import metadata_results

router = Router()


def _escape(value: object) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@router.message(Command("latest"))
async def latest_command(message: Message, tmdb):
    if not tmdb:
        await message.answer("Latest movie discovery is not configured. Add a TMDB_API_KEY in Railway Variables.")
        return
    try:
        items = await tmdb.discover_movies("latest")
    except Exception:
        items = []
    if not items:
        await message.answer("Latest movies are temporarily unavailable. Please try again later.")
        return
    await message.answer(
        "<b>🆕 Latest movies</b>\nChoose a title for details and official watch options.",
        reply_markup=metadata_results(items),
        parse_mode="HTML",
    )


@router.message(Command("categories"))
async def categories_command(message: Message, tmdb):
    if not tmdb:
        await message.answer("Movie categories need a TMDB API key. Add TMDB_API_KEY in Railway Variables.")
        return
    try:
        genres = await tmdb.movie_genres()
    except Exception:
        genres = []
    if not genres:
        await message.answer("Movie categories are temporarily unavailable.")
        return
    builder = InlineKeyboardBuilder()
    for genre in genres:
        builder.button(text=str(genre["name"])[:50], callback_data=f"genre:{genre['id']}")
    builder.adjust(2)
    await message.answer("<b>🎭 Browse by category</b>\nChoose a genre:", reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("genre:"))
async def genre_movies(callback: CallbackQuery, tmdb):
    try:
        genre_id = int(callback.data.split(":", 1)[1])
        items = await tmdb.discover_movies_by_genre(genre_id)
    except (ValueError, TypeError):
        items = []
    except Exception:
        items = []
    if not items:
        await callback.answer("No movies found for this category right now.", show_alert=True)
        return
    await callback.message.answer(
        "<b>🎬 Movies in this category</b>\nOpen a title for details and official watch options.",
        reply_markup=metadata_results(items),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("series"))
async def series_search(message: Message, tmdb):
    query = (message.text or "").partition(" ")[2].strip()
    if len(query) < 2:
        await message.answer("Usage: /series series name")
        return
    if not tmdb:
        await message.answer("TV series discovery is not configured. Add TMDB_API_KEY in Railway Variables.")
        return
    try:
        items = await tmdb.search_tv(query)
    except Exception:
        items = []
    if not items:
        await message.answer("No TV series found, or the catalog is temporarily unavailable.")
        return
    builder = InlineKeyboardBuilder()
    for item in items:
        year = f" ({item['year']})" if item.get("year") else ""
        builder.row(InlineKeyboardButton(
            text=f"📺 {item['title'][:42]}{year}"[:60],
            callback_data=f"tv:{item['id']}",
        ))
    await message.answer(
        f"<b>📺 TV series results</b>\nSearch: <code>{_escape(query[:80])}</code>\nChoose a series:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tv:"))
async def tv_details(callback: CallbackQuery, tmdb):
    try:
        tv_id = int(callback.data.split(":", 1)[1])
        data = await tmdb.tv_details(tv_id)
    except (ValueError, TypeError):
        data = None
    except Exception:
        data = None
    if not data:
        await callback.answer("Series information is temporarily unavailable.", show_alert=True)
        return
    seasons = data.get("seasons", [])
    lines = [
        f"📺 <b>{_escape(data['title'])}</b> ({_escape(data['year'])})",
        f"⭐ Rating: {_escape(data.get('rating') or 'Not listed')}",
        f"🎭 Genres: {_escape(data.get('genres') or 'Not listed')}",
        f"📅 Episodes: {_escape(data.get('episode_count') or 'Not listed')} · Seasons: {len(seasons)}",
        "",
        _escape(data.get("overview") or "No synopsis available."),
        "",
        f"📡 Watch providers ({_escape(data['region'])}): {_escape(', '.join(data.get('providers', [])) or 'Not listed')}",
        "TMDB provides metadata and official watch options, not video files or download rights.",
    ]
    rows = []
    for season in seasons:
        if int(season.get("season_number", 0)) > 0:
            rows.append([InlineKeyboardButton(
                text=f"Season {season['season_number']} · {season.get('episode_count', 0)} episodes",
                callback_data=f"tvseason:{tv_id}:{season['season_number']}",
            )])
    rows.append([InlineKeyboardButton(text="▶️ Official watch options", url=data["watch_url"])])
    rows.append([InlineKeyboardButton(text="ℹ️ TMDB details", url=data["details_url"])])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    caption = "\n".join(lines)
    if data.get("poster_url"):
        try:
            await callback.message.answer_photo(data["poster_url"], caption=caption[:1024], reply_markup=keyboard, parse_mode="HTML")
            if len(caption) > 1024:
                await callback.message.answer(caption[1024:], parse_mode="HTML")
        except Exception:
            await callback.message.answer(caption, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await callback.message.answer(caption, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("tvseason:"))
async def tv_season(callback: CallbackQuery, tmdb):
    try:
        _, raw_tv_id, raw_season = callback.data.split(":", 2)
        tv_id, season_number = int(raw_tv_id), int(raw_season)
        data = await tmdb.tv_season(tv_id, season_number)
    except (ValueError, TypeError):
        data = None
    except Exception:
        data = None
    if not data:
        await callback.answer("Episode information is temporarily unavailable.", show_alert=True)
        return
    episodes = data.get("episodes", [])[:30]
    lines = [f"<b>{_escape(data.get('name') or f'Season {season_number}')}</b>"]
    for episode in episodes:
        air_date = episode.get("air_date") or "Date unknown"
        lines.append(
            f"• S{season_number:02d}E{int(episode.get('episode_number') or 0):02d} "
            f"<b>{_escape(episode.get('name') or 'Untitled')}</b> — {_escape(air_date)}"
        )
        overview = str(episode.get("overview") or "").strip()
        if overview:
            lines.append(f"  {_escape(overview[:180])}")
    if not episodes:
        lines.append("No episode records are listed for this season.")
    lines.append("\nEpisode metadata only. Use the official provider links on the series page to watch.")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()

@router.callback_query(F.data == "nav:series")
async def series_menu(callback: CallbackQuery):
    await callback.message.answer("Search a TV show with /series title — for example: /series Planet Earth")
    await callback.answer()


@router.callback_query(F.data == "nav:categories")
async def categories_menu(callback: CallbackQuery, tmdb):
    if not tmdb:
        await callback.answer("Movie categories need a TMDB API key.", show_alert=True)
        return
    try:
        genres = await tmdb.movie_genres()
    except Exception:
        genres = []
    if not genres:
        await callback.answer("Categories are temporarily unavailable.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for genre in genres:
        builder.button(text=str(genre["name"])[:50], callback_data=f"genre:{genre['id']}")
    builder.adjust(2)
    await callback.message.answer("<b>🎭 Browse by category</b>\nChoose a genre:", reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
