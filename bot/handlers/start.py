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
    "en": "🎬 <b>WELCOME TO LEGAL MOVIE BOT</b>\n\nDiscover movies with explicit redistribution licenses. Search Internet Archive, Library of Congress, Wikimedia Commons and YouTube CC videos, inspect rights, and download supported files directly here.\n\nTMDB adds broad movie discovery, trailers and official watch options; it does not provide movie files.",
    "am": "🎬 <b>ወደ LEGAL MOVIE BOT እንኳን በደህና መጡ</b>\n\nበInternet Archive፣ Library of Congress፣ Wikimedia Commons እና YouTube CC ውስጥ የሚገኙ ግልጽ የስርጭት ፈቃድ ያላቸውን ፊልሞች ይፈልጉ። የፈቃድ ሁኔታን ያረጋግጡ እና የሚደገፉ ፋይሎችን ያውርዱ።\n\nTMDB የፊልም መረጃ፣ ትሬይለር እና የሕጋዊ መመልከቻ አማራጮችን ብቻ ያቀርባል።",
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
    await message.answer("Search a movie title, open a result, and review its source and license. Only explicit allowlisted CC0, Public Domain Mark, CC BY or CC BY-SA license URLs pass the automated rights gate. Files are delivered only when within the configured Telegram upload cap; larger files link to the authorized source record. Unknown rights are excluded.")


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
    await callback.message.answer("Search by title. Results can come from Internet Archive, Library of Congress, Wikimedia Commons and YouTube CC. Only supported CC0, Public Domain Mark, CC BY/CC BY-SA, explicit LOC public-domain statements and YouTube CC Attribution records are eligible. A Telegram upload is attempted only below the configured size cap.")
    await callback.answer()


@router.callback_query(F.data == "nav:about")
async def about_callback(callback: CallbackQuery):
    await callback.message.answer("Legal Movie Bot uses TMDB for metadata and official watch links, and checks Internet Archive, Library of Congress, Wikimedia Commons and YouTube CC for openly licensed media. TMDB does not supply files or download rights. This product uses the TMDB API but is not endorsed or certified by TMDB. Automated rights checks are conservative and cannot prove uploader ownership; always review the source license.")
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
