from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def home(lang: str = "en") -> InlineKeyboardMarkup:
    labels = {
        "en": [("🔎 Search Movies", "search"), ("🔥 Popular Movies", "popular"), ("🆕 Latest Movies", "latest"), ("❤️ Favorites", "favorites"), ("🌐 Language", "language"), ("ℹ️ Help", "help"), ("About", "about")],
        "am": [("🔎 ፊልም ፈልግ", "search"), ("🔥 ተወዳጅ ፊልሞች", "popular"), ("🆕 አዳዲስ ፊልሞች", "latest"), ("❤️ ተወዳጆች", "favorites"), ("🌐 ቋንቋ", "language"), ("ℹ️ እገዛ", "help"), ("ስለ ቦቱ", "about")],
    }
    builder = InlineKeyboardBuilder()
    for label, callback in labels.get(lang, labels["en"]):
        builder.button(text=label, callback_data=f"nav:{callback}")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def results(items: list[dict], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"🎬 {item['title'][:48]}", callback_data=f"movie:{item['identifier']}")
    builder.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"page:{page-1}"))
    if len(items) > 0:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"))
    return builder.as_markup()


def movie_actions(identifier: str, files: list[dict], favorite: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for movie_file in files:
        file_id = movie_file["id"]
        fmt = str(movie_file.get("format") or "VIDEO").upper()
        quality = movie_file.get("resolution") or "quality n/a"
        size = movie_file.get("file_size")
        size_label = f"{size / (1024 * 1024):.0f} MB" if size else "size n/a"
        builder.button(
            text=f"⬇️ Send {fmt} · {quality} · {size_label}"[:60],
            callback_data=f"download:{identifier}:{file_id}",
        )
        direct_url = movie_file.get("download_url")
        if direct_url:
            builder.button(text=f"🌐 Direct {fmt} download", url=direct_url)
    builder.button(text="❤️ Remove favorite" if favorite else "❤️ Add favorite", callback_data=f"favorite:{identifier}")
    builder.button(text="⬅️ Search", callback_data="nav:search")
    builder.adjust(1)
    return builder.as_markup()
