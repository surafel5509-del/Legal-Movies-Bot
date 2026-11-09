from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database.db import Session
from bot.keyboards.inline import results
from bot.services.catalog import get_or_create_user, record_search

router = Router()


class SearchState(StatesGroup):
    waiting_for_query = State()


@router.callback_query(F.data == "nav:search")
async def begin_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await state.update_data(page=0)
    await callback.message.answer("🔎 Send a movie title to search (for example: Sherlock Holmes).")
    await callback.answer()


@router.message(SearchState.waiting_for_query)
async def run_search(message: Message, state: FSMContext, archive):
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Please enter at least two characters.")
        return
    await state.update_data(query=query, page=0)
    await _show_results(message, state, archive, query, 0, actor=message.from_user)


@router.callback_query(F.data.startswith("page:"))
async def change_page(callback: CallbackQuery, state: FSMContext, archive):
    data = await state.get_data()
    query = data.get("query")
    if not query:
        await callback.answer("Start a new search first.", show_alert=True)
        return
    page = max(0, int(callback.data.split(":", 1)[1]))
    await state.update_data(page=page)
    await _show_results(callback.message, state, archive, query, page, actor=callback.from_user)
    await callback.answer()


async def _show_results(message, state, archive, query: str, page: int, actor=None):
    if not settings.catalog_enabled:
        await message.answer("The movie catalog is temporarily disabled.")
        return
    try:
        items = await archive.search(query, page)
    except Exception:
        await message.answer("The movie catalog is temporarily unavailable. Please try again later.")
        return
    async with Session() as session:
        user = await get_or_create_user(session, actor) if actor else None
        if user:
            await record_search(session, user, query)
        await session.commit()
    if not items:
        await message.answer("No movies with a currently recognized redistribution license were found. Try a shorter title or another spelling.")
        return

    def escape_html(value: object) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    text = "<b>Verified catalog matches</b>\nOnly entries with an allowlisted explicit license are shown.\n\n" + "\n".join(
        f"• {escape_html(item['title'])}" + (f" ({item['year']})" if item.get("year") else "") for item in items
    )
    await message.answer(text, reply_markup=results(items, page), parse_mode="HTML")
