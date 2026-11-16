from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()

WELCOME = (
    "🎬 <b>LEGAL MOVIE BOT · POWERED BY TORRENTCLAW</b>\n\n"
    "Search movie titles, browse popular and newly added movies, compare available releases, "
    "and open downloads that have been reviewed and approved for distribution.\n\n"
    "Use /torrent movie title [year], /popular, or /recent."
)


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Search movies", callback_data="nav:torrent")],
        [InlineKeyboardButton(text="🔥 Popular movies", callback_data="nav:popular"),
         InlineKeyboardButton(text="🆕 New movies", callback_data="nav:recent")],
        [InlineKeyboardButton(text="ℹ️ Help", callback_data="nav:help")],
    ])


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=home_keyboard(), parse_mode="HTML")


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "<b>Commands</b>\n"
        "/start — main menu\n"
        "/torrent title [year] — search TorrentClaw\n"
        "/popular — popular TorrentClaw movies\n"
        "/recent — newly added TorrentClaw movies\n\n"
        "Download actions are enabled only for releases with independently verified redistribution permission. "
        "A torrent search result or info hash alone does not establish permission.",
        parse_mode="HTML",
    )


@router.message(Command("myid"))
async def my_id(message: Message):
    await message.answer(f"Your Telegram user ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@router.callback_query(F.data == "nav:home")
async def home_callback(callback: CallbackQuery):
    await callback.message.answer(WELCOME, reply_markup=home_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "nav:help")
async def help_callback(callback: CallbackQuery):
    await callback.message.answer(
        "Use /torrent title [year], /popular or /recent. "
        "Only releases with independently verified redistribution permission can be downloaded."
    )
    await callback.answer()
