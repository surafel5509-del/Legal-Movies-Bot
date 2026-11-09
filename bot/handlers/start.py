from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from bot.database.db import Session
from bot.database.models import User
from bot.keyboards.inline import home
from bot.services.catalog import get_or_create_user

router = Router()

WELCOME = {
    "en": "🎬 <b>WELCOME TO LEGAL MOVIE BOT</b>\n\nDiscover movies that are explicitly licensed for redistribution. Search the catalog, review verified rights, and download supported files directly here.\n\nOnly verified public-domain and compatible Creative Commons titles are listed.",
    "am": "🎬 <b>ወደ LEGAL MOVIE BOT እንኳን በደህና መጡ</b>\n\nለማሰራጨት ፈቃድ ያላቸውን ፊልሞች ይፈልጉ። የፈቃድ መረጃን ይመልከቱ እና የሚደገፉ ፋይሎችን በቀጥታ ያውርዱ።",
}


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    async with Session() as session:
        user = await get_or_create_user(session, message.from_user)
        await session.commit()
        lang = user.language
    await message.answer(WELCOME.get(lang, WELCOME["en"]), reply_markup=home(lang), parse_mode="HTML")


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer("Search by movie title. Open a result to inspect the source, license, file size and format. Direct delivery is limited by the configured Telegram upload cap; larger files are linked only to their authorized Archive.org item page. Unknown or incompatible rights are excluded.")


@router.callback_query(F.data == "nav:home")
async def home_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    async with Session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        lang = user.language if user else "en"
    await callback.message.answer(WELCOME.get(lang, WELCOME["en"]), reply_markup=home(lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "nav:help")
async def help_callback(callback: CallbackQuery):
    await callback.message.answer("Type a title to search. Only catalog entries with an explicit allowlisted redistribution license are shown. A download is sent as a Telegram document only when it fits the configured upload cap; otherwise the bot gives the authorized source page.")
    await callback.answer()


@router.callback_query(F.data == "nav:about")
async def about_callback(callback: CallbackQuery):
    await callback.message.answer("Legal Movie Bot is a movie-only discovery bot. Initial catalog: Internet Archive. License checks are conservative and automated; metadata can still be inaccurate, so always review the linked license and source record.")
    await callback.answer()


@router.callback_query(F.data == "nav:language")
async def language_callback(callback: CallbackQuery):
    await callback.message.answer("Choose language / ቋንቋ ይምረጡ", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="English", callback_data="lang:en"),
        InlineKeyboardButton(text="አማርኛ", callback_data="lang:am"),
    ]]))
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split(":", 1)[1]
    if lang not in {"en", "am"}:
        await callback.answer("Unsupported language", show_alert=True)
        return
    async with Session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
        if user:
            user.language = lang
            await session.commit()
    await callback.message.answer(WELCOME[lang], reply_markup=home(lang), parse_mode="HTML")
    await callback.answer("Language updated")
