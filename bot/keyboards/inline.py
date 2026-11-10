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


def results(items: list[dict], page: int, has_next: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"🎬 {item['title'][:48]}", callback_data=f"movie:{item['identifier']}")
    builder.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"page:{page-1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"))
    return builder.as_markup()


def metadata_results(items: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        year = f" ({item['year']})" if item.get("year") else ""
        builder.button(text=f"🎞 {item['title'][:42]}{year}"[:60], callback_data=f"tmdb:{item['id']}")
    builder.adjust(1)
    return builder.as_markup()


def movie_actions(identifier: str, file_ids: list[int], favorite: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for file_id in file_ids:
        builder.button(text=f"⬇️ Download option {file_id}", callback_data=f"download:{identifier}:{file_id}")
    builder.button(text="❤️ Remove favorite" if favorite else "❤️ Add favorite", callback_data=f"favorite:{identifier}")
    builder.button(text="⬅️ Search", callback_data="nav:search")
    builder.adjust(1)
    return builder.as_markup()
