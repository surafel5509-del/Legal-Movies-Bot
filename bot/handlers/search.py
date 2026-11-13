import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.database.db import Session
from bot.keyboards.inline import results
from bot.services.catalog import get_or_create_user, record_search

router = Router()
logger = logging.getLogger(__name__)


class SearchState(StatesGroup):
    waiting_for_query = State()


@router.callback_query(F.data == "nav:search")
async def begin_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(page=0)
    await callback.message.answer(
        "🔎 Send a movie or TV title. Search includes MovieBox discovery, "
        "licensed downloadable catalogs, and TMDB metadata. "
        "You can also use /moviebox title."
    )
    await callback.answer()


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext, archive, tmdb, moviebox):
    query = (message.text or "").partition(" ")[2].strip()
    if len(query) < 2:
        await message.answer("Usage: /search movie title")
        return
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(query=query, page=0)
    await _show_results(message, state, archive, tmdb, moviebox, query, 0, actor=message.from_user)


@router.message(Command("moviebox"))
async def moviebox_command(message: Message, state: FSMContext, archive, tmdb, moviebox):
    query = (message.text or "").partition(" ")[2].strip()
    if len(query) < 2:
        await message.answer("Usage: /moviebox title")
        return
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(query=query, page=0)
    await _show_results(message, state, archive, tmdb, moviebox, query, 0, actor=message.from_user)


@router.message(SearchState.waiting_for_query)
async def run_search(message: Message, state: FSMContext, archive, tmdb, moviebox):
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Please enter at least two characters.")
        return
    await state.update_data(query=query, page=0)
    await _show_results(message, state, archive, tmdb, moviebox, query, 0, actor=message.from_user)


@router.callback_query(F.data.startswith("page:"))
async def change_page(callback: CallbackQuery, state: FSMContext, archive, tmdb, moviebox):
    data = await state.get_data()
    query = data.get("query")
    if not query:
        await callback.answer("Start a new search first.", show_alert=True)
        return
    try:
        page = max(0, min(int(callback.data.split(":", 1)[1]), 1000))
    except (TypeError, ValueError):
        await callback.answer("Invalid page.", show_alert=True)
        return
    await state.update_data(page=page)
    await _show_results(callback.message, state, archive, tmdb, moviebox, query, page, actor=callback.from_user)
    await callback.answer()


@router.callback_query(F.data.startswith("moviebox:"))
async def moviebox_details(callback: CallbackQuery, state: FSMContext, moviebox):
    subject_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    item = (data.get("moviebox_items") or {}).get(subject_id)
    if not item:
        await callback.answer("Search again to refresh this MovieBox result.", show_alert=True)
        return

    await callback.answer("Loading MovieBox metadata…")
    try:
        details = await moviebox.details(item["detail_path"], item)
    except Exception as exc:
        logger.warning("MovieBox details request failed: %s", exc)
        await callback.message.answer("MovieBox details are temporarily unavailable. Please try again.")
        return

    def esc(value):
        return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        f"🎞 <b>{esc(details['title'])}</b>",
        f"Type: {esc(item['kind'])} · Year: {esc(details.get('year') or 'Not listed')}",
        f"⭐ Rating: {esc(details.get('rating') or 'Not listed')}",
        f"🎭 Genres: {esc(', '.join(details.get('genres') or []) or 'Not listed')}",
        f"🌍 Country: {esc(details.get('country') or 'Not listed')}",
        f"⏱ Duration: {esc(details.get('duration') or 'Not listed')}",
        "",
        esc(details.get("description") or "No description supplied."),
    ]
    seasons = details.get("seasons") or []
    if seasons:
        lines.extend(["", "<b>Seasons</b>"])
        for season in seasons[:12]:
            resolutions = ", ".join(f"{value}p" for value in season.get("resolutions", []))
            lines.append(
                f"• Season {esc(season.get('number'))}: "
                f"{esc(season.get('episodes'))} episodes"
                + (f" · {esc(resolutions)}" if resolutions else "")
            )
    lines.extend([
        "",
        "MovieBox supplied this discovery metadata. This bot does not expose unlicensed stream or download URLs.",
    ])
    await callback.message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


async def _show_results(message, state, archive, tmdb, moviebox, query: str, page: int, actor=None):
    items = []
    if settings.catalog_enabled:
        try:
            items = await archive.search(query, page)
        except Exception as exc:
            logger.exception("Legal catalog search failed: %s", exc)
            items = []

    tmdb_items = []
    if tmdb:
        try:
            tmdb_items = await tmdb.search_movies(query, page + 1)
        except Exception:
            tmdb_items = []

    moviebox_data = {"items": [], "has_next": False}
    try:
        moviebox_data = await moviebox.search(query, page + 1)
    except Exception as exc:
        logger.warning("MovieBox search failed: %s", exc)
    moviebox_items = moviebox_data.get("items", [])

    await state.update_data(
        moviebox_items={
            item["subject_id"]: item
            for item in moviebox_items
            if item.get("subject_id") and item.get("detail_path")
        }
    )

    async with Session() as session:
        user = await get_or_create_user(session, actor) if actor else None
        if user:
            await record_search(session, user, query)
        await session.commit()

    if not items and not tmdb_items and not moviebox_items:
        await message.answer(
            "No matches were found. MovieBox or the other catalogs may be temporarily unavailable. "
            "Try a shorter title, or use /help."
        )
        return

    def escape_html(value: object) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if items:
        heading = (
            f"<b>🎬 Legal catalog results</b>\n"
            f"Search: <code>{escape_html(query[:80])}</code> · Page {page + 1}\n"
            "Only records with an explicit allowlisted license are listed.\n\n"
        )
        lines = []
        for item in items:
            title = escape_html(item["title"])
            year = f" ({item['year']})" if item.get("year") else ""
            lines.append(f"• {title}{year}")
        await message.answer(
            heading + "\n".join(lines),
            reply_markup=results(items, page, has_next=len(items) >= settings.archive_page_size),
            parse_mode="HTML",
        )

    if moviebox_items:
        builder = InlineKeyboardBuilder()
        for item in moviebox_items[:8]:
            year = f" ({item['year']})" if item.get("year") else ""
            label = f"🎞 {item['title'][:38]}{year} · {item['kind']}"[:60]
            builder.row(InlineKeyboardButton(
                text=label,
                callback_data=f"moviebox:{item['subject_id']}",
            ))
        if not items:
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"page:{page - 1}"))
            if moviebox_data.get("has_next"):
                nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"page:{page + 1}"))
            if nav:
                builder.row(*nav)
        await message.answer(
            f"<b>🎞 MovieBox results</b>\nSearch: <code>{escape_html(query[:80])}</code> · Page {page + 1}\n"
            "Choose a title to view its MovieBox metadata:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )

    if tmdb_items:
        from bot.keyboards.inline import metadata_results
        await message.answer(
            "<b>🌍 More movie matches (TMDB)</b>\nThese are discovery results, not downloadable files. Open a title to see official watch options.",
            reply_markup=metadata_results(tmdb_items),
            parse_mode="HTML",
        )
