import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

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
    await callback.message.answer("🔎 Send any movie title or a few words from its title. You can also use /search movie title.")
    await callback.answer()


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext, archive, tmdb):
    query = (message.text or "").partition(" ")[2].strip()
    if len(query) < 2:
        await message.answer("Usage: /search movie title")
        return
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(query=query, page=0)
    await _show_results(message, state, archive, tmdb, query, 0, actor=message.from_user)


@router.message(SearchState.waiting_for_query)
async def run_search(message: Message, state: FSMContext, archive, tmdb):
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Please enter at least two characters.")
        return
    await state.update_data(query=query, page=0)
    await _show_results(message, state, archive, tmdb, query, 0, actor=message.from_user)


@router.callback_query(F.data.startswith("page:"))
async def change_page(callback: CallbackQuery, state: FSMContext, archive, tmdb):
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
    await _show_results(callback.message, state, archive, tmdb, query, page, actor=callback.from_user)
    await callback.answer()


async def _show_results(message, state, archive, tmdb, query: str, page: int, actor=None):
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
    async with Session() as session:
        user = await get_or_create_user(session, actor) if actor else None
        if user:
            await record_search(session, user, query)
        await session.commit()
    if not items and not tmdb_items:
        await message.answer("No legal downloadable matches were found, or the free catalogs are temporarily unavailable. Try a shorter title, or use /help to see supported sources.")
        return

    def escape_html(value: object) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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
    if items:
        await message.answer(
            heading + "\n".join(lines),
            reply_markup=results(items, page, has_next=len(items) >= settings.archive_page_size),
            parse_mode="HTML",
        )
    if tmdb_items:
        from bot.keyboards.inline import metadata_results
        await message.answer(
            "<b>🌍 More movie matches (TMDB)</b>\nThese are discovery results, not downloadable files. Open a title to see official watch options.",
            reply_markup=metadata_results(tmdb_items),
            parse_mode="HTML",
        )
