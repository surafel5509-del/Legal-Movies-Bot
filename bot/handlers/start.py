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
    "en": "🎬 <b>WELCOME TO LEGAL MOVIE BOT</b>\n\nDiscover movies with explicit redistribution licenses. Search Internet Archive, Library of Congress, Wikimedia Commons and YouTube CC videos, inspect rights, and download supported files directly here.\n\nExplore movie details, official watch options, TV series and episode guides. TMDB provides metadata and official provider links, not movie files.",
    "am": "🎬 <b>ወደ LEGAL MOVIE BOT እንኳን በደህና መጡ</b>\n\nበInternet Archive፣ Library of Congress፣ Wikimedia Commons እና YouTube CC ውስጥ ግልጽ የስርጭት ፈቃድ ያላቸውን ፊልሞች ይፈልጉ። የፈቃድ ሁኔታን ያረጋግጡ እና የሚደገፉ ፋይሎችን ያውርዱ።\n\nየTV ተከታታይ ፊልሞችን እና የክፍል መረጃዎችንም ይፈልጉ። TMDB የፊልም መረጃና የኦፊሴላዊ መመልከቻ ሊንኮችን ብቻ ያቀርባል።",
}


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    async with Session() as session:
        user = await get_or_create_user(session, message.from_user)
        await session.commit()
        lang = user.language
    await message.answer(WELCOME.get(lang, WELCOME["en"]), reply_markup=home(lang), parse_mode="HTML")


@router.message(Command("myid"))
async def my_id(message: Message):
    await message.answer(
        f"Your Telegram user ID is: <code>{message.from_user.id}</code>\n"
        "Send this number to the bot owner so it can be added to ADMIN_IDS.",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "<b>Commands</b>\n"
        "/start — open the main menu\n"
        "/search title — search MovieBox, licensed catalogs and TMDB\n"
        "/moviebox title — search MovieBox directly\n"
        "/series title — search TV series and view season/episode guides\n"
        "/latest — browse currently released movies\n"
        "/categories — browse movie genres\n"
        "/admin — administrator statistics (admins only)\n"
        "/myid — show your Telegram user ID\n"
        "/help — show this help\n\n"
        "TMDB supplies metadata and official watch-provider links, not movie files. "
        "Downloads are offered only when a source passes the bot's explicit license checks. "
        "Unknown or unverified rights are blocked.",
        parse_mode="HTML",
    )


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
    await callback.message.answer(
        "Commands: /search title, /moviebox title, /series title, /latest, /categories, /myid and /help. "
        "Only explicitly licensed media can be downloaded. TMDB provides metadata and official watch links only."
    )
    await callback.answer()


@router.callback_query(F.data == "nav:about")
async def about_callback(callback: CallbackQuery):
    await callback.message.answer(
        "Legal Movie Bot uses TMDB for movie and TV metadata and official watch links, and checks "
        "Internet Archive, Library of Congress, Wikimedia Commons and YouTube CC for openly licensed media. "
        "TMDB does not supply files or download rights. This product uses the TMDB API but is not endorsed "
        "or certified by TMDB. Automated rights checks are conservative and cannot prove uploader ownership; "
        "always review the source license."
    )
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
