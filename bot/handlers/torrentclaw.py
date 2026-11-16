from __future__ import annotations

import html
import logging
import re
from difflib import SequenceMatcher

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.services.download_manager import FileTooLarge
from bot.services.torrentclaw_api import TorrentClawError
from bot.services.torrent_download_manager import magnet_info_hash

router = Router()
logger = logging.getLogger(__name__)
_HASH = re.compile(r"^[a-f0-9]{40}$")
_YEAR = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2}|2100)\b")


class SearchState(StatesGroup):
    waiting_for_query = State()


def _safe_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _title_key(value: str) -> str:
    value = _YEAR.sub(" ", value or "")
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _extract_query(value: str) -> tuple[str, int | None]:
    match = _YEAR.search(value or "")
    year = int(match.group(1)) if match else None
    query = _YEAR.sub(" ", value or "")
    query = " ".join(query.split()).strip()
    return query, year


def _title_score(query: str, title: str) -> float:
    left, right = _title_key(query), _title_key(title)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


@router.message(Command("torrent"))
async def torrent_search(message: Message, state: FSMContext, torrentclaw):
    query = (message.text or "").partition(" ")[2].strip()
    if len(query) < 2:
        await state.set_state(SearchState.waiting_for_query)
        await message.answer("Send a movie title. Add its release year for a more precise match.\nExample: Night of the Living Dead 1968")
        return
    await state.clear()
    await _render_search(message, state, torrentclaw, query)


@router.message(SearchState.waiting_for_query)
async def torrent_search_text(message: Message, state: FSMContext, torrentclaw):
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Please enter at least two characters.")
        return
    await state.clear()
    await _render_search(message, state, torrentclaw, query)


@router.callback_query(F.data == "nav:torrent")
async def torrent_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await callback.message.answer("Send a movie title. Include the release year to avoid similarly named movies.")
    await callback.answer()


@router.message(Command("popular"))
async def popular_command(message: Message, state: FSMContext, torrentclaw):
    await _render_collection(message, state, torrentclaw, "popular")


@router.callback_query(F.data == "nav:popular")
async def popular_callback(callback: CallbackQuery, state: FSMContext, torrentclaw):
    await callback.answer()
    await _render_collection(callback.message, state, torrentclaw, "popular")


@router.message(Command("recent"))
async def recent_command(message: Message, state: FSMContext, torrentclaw):
    await _render_collection(message, state, torrentclaw, "recent")


@router.callback_query(F.data == "nav:recent")
async def recent_callback(callback: CallbackQuery, state: FSMContext, torrentclaw):
    await callback.answer()
    await _render_collection(callback.message, state, torrentclaw, "recent")


async def _render_collection(message: Message, state: FSMContext, torrentclaw, kind: str):
    try:
        payload = await (torrentclaw.popular(limit=12) if kind == "popular" else torrentclaw.recent(limit=12))
    except TorrentClawError as exc:
        await message.answer(str(exc))
        return
    items = [
        item for item in payload.get("items", [])
        if isinstance(item, dict) and item.get("title")
        and str(item.get("contentType") or "movie").lower() == "movie"
    ]
    if not items:
        await message.answer("TorrentClaw has no movie entries in this list right now.")
        return
    lookup = {}
    builder = InlineKeyboardBuilder()
    lines = ["<b>🔥 TorrentClaw popular movies</b>" if kind == "popular" else "<b>🆕 Newly added TorrentClaw movies</b>", ""]
    for item in items[:12]:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        title = str(item.get("title") or "Untitled")[:100]
        year = item.get("year")
        rating = item.get("ratingImdb") or item.get("ratingTmdb")
        seeders = _safe_int(item.get("maxSeeders"))
        label = f"{title} ({year})" if year else title
        line = f"• <b>{html.escape(label)}</b>"
        if rating:
            line += f" · ⭐ {html.escape(str(rating))}"
        if seeders:
            line += f" · {seeders} seeders"
        lines.append(line)
        lookup[item_id] = {"title": title, "year": year}
        builder.row(InlineKeyboardButton(text=f"🔎 Find releases: {label}"[:60], callback_data=f"popular:{item_id}"))
    await state.update_data(torrentclaw_collection=lookup)
    builder.row(InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"))
    await message.answer("\n".join(lines)[:3900], reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("popular:"))
async def search_collection_movie(callback: CallbackQuery, state: FSMContext, torrentclaw):
    item_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    item = (data.get("torrentclaw_collection") or {}).get(item_id)
    if not item:
        await callback.answer("Open the popular or recent list again to refresh it.", show_alert=True)
        return
    query = f"{item['title']} {item['year']}" if item.get("year") else item["title"]
    await callback.answer("Finding matching TorrentClaw releases…")
    await _render_search(callback.message, state, torrentclaw, query)


async def _render_search(message: Message, state: FSMContext, torrentclaw, raw_query: str):
    query, year = _extract_query(raw_query)
    if len(query) < 2:
        await message.answer("Enter a movie title with at least two characters.")
        return
    try:
        payload = await torrentclaw.search(query, limit=50, content_type="movie", year=year)
    except (TorrentClawError, ValueError) as exc:
        await message.answer(str(exc))
        return

    candidates = [
        item for item in payload.get("results", [])
        if isinstance(item, dict) and item.get("title")
        and str(item.get("contentType") or "movie").lower() == "movie"
    ]
    if year:
        candidates = [item for item in candidates if _safe_int(item.get("year")) == year]
    scored = [(item, _title_score(query, str(item.get("title") or ""))) for item in candidates]
    exact = [(item, score) for item, score in scored if score == 1.0]
    selected = exact if exact else [(item, score) for item, score in scored if score >= 0.72]
    selected.sort(key=lambda pair: (pair[1], _safe_int(pair[0].get("maxSeeders"))), reverse=True)
    selected = selected[:6]
    if not selected:
        await message.answer(
            f"No close movie-title match found in TorrentClaw for <b>{html.escape(query)}</b>"
            + (f" ({year})" if year else "")
            + ". Try the original title or add the correct year.",
            parse_mode="HTML",
        )
        return

    builder = InlineKeyboardBuilder()
    movie_lookup: dict[str, dict] = {}
    lines = [f"<b>🔎 Movie search results</b> · {html.escape(query[:80])}", ""]
    if year:
        lines[0] += f" ({year})"
    if not exact:
        lines.append("<i>Closest title matches — check the year before choosing.</i>")
        lines.append("")
    for index, (item, _score) in enumerate(selected):
        title_raw = str(item.get("title") or "Untitled")[:100]
        title = html.escape(title_raw)
        item_year = item.get("year")
        rating = item.get("ratingImdb") or item.get("ratingTmdb")
        lines.append(f"<b>{title}</b>{f' ({item_year})' if item_year else ''}")
        if rating:
            lines.append(f"⭐ Rating: {html.escape(str(rating))}")
        lines.append("Choose this movie to view its available qualities.")
        lines.append("")
        key = str(index)
        movie_lookup[key] = item
        label = f"🎬 {title_raw}" + (f" ({item_year})" if item_year else "")
        builder.row(InlineKeyboardButton(text=label[:60], callback_data=f"moviepick:{key}"))

    await state.update_data(torrentclaw_movies=movie_lookup, torrentclaw_magnets={}, torrentclaw_selected_hash=None, torrentclaw_search_query=raw_query)
    builder.row(InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"))
    await message.answer(
        "\n".join(lines)[:3900],
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "torrentback")
async def back_to_movie_results(callback: CallbackQuery, state: FSMContext, torrentclaw):
    data = await state.get_data()
    query = data.get("torrentclaw_search_query")
    if not isinstance(query, str) or len(query.strip()) < 2:
        await callback.answer("Run /torrent to search again.", show_alert=True)
        return
    await callback.answer()
    await _render_search(callback.message, state, torrentclaw, query)


@router.callback_query(F.data.startswith("moviepick:"))
async def select_movie(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    item = (data.get("torrentclaw_movies") or {}).get(key)
    if not isinstance(item, dict):
        await callback.answer("Search again to refresh the movie list.", show_alert=True)
        return

    title_raw = str(item.get("title") or "Untitled")[:100]
    title = html.escape(title_raw)
    year = item.get("year")
    rating = item.get("ratingImdb") or item.get("ratingTmdb")
    overview = str(item.get("overview") or item.get("description") or "").strip()
    overview = html.escape(overview[:900])
    lines = [f"<b>🎬 {title}</b>" + (f" ({year})" if year else "")]
    if rating:
        lines.append(f"⭐ Rating: {html.escape(str(rating))}")
    if overview:
        lines.extend(["", overview])

    approved = settings.torrentclaw_approved_infohashes or set()
    magnet_map: dict[str, dict[str, str]] = {}
    builder = InlineKeyboardBuilder()
    torrents = item.get("torrents") or []
    torrents = sorted(
        (t for t in torrents if isinstance(t, dict)),
        key=lambda t: (_safe_int(t.get("qualityScore")), _safe_int(t.get("seeders"))),
        reverse=True,
    )
    for torrent in torrents[:12]:
        info_hash = str(torrent.get("infoHash") or "").lower()
        quality_raw = str(torrent.get("quality") or "Unknown")
        quality = html.escape(quality_raw)
        codec = html.escape(str(torrent.get("codec") or ""))
        size_bytes = _safe_int(torrent.get("sizeBytes"))
        size = f"{size_bytes / (1024 ** 3):.2f} GB" if size_bytes else "size n/a"
        seeders = _safe_int(torrent.get("seeders"))
        lines.append(f"• {quality} {codec} · {size} · {seeders} seeders")
        magnet = torrent.get("magnetUrl")
        if (
            info_hash in approved and _HASH.fullmatch(info_hash)
            and isinstance(magnet, str) and magnet_info_hash(magnet) == info_hash
        ):
            magnet_map[info_hash] = {"magnet": magnet, "title": title_raw, "quality": quality_raw}
            builder.row(InlineKeyboardButton(
                text=f"🎞 Select quality · {quality_raw}"[:60],
                callback_data=f"torrentquality:{info_hash}",
            ))

    if not torrents:
        lines.extend(["", "No release qualities are listed for this movie yet."])
    elif not magnet_map:
        lines.extend([
            "",
            "No quality can be downloaded yet. Downloads are enabled only for exact releases whose redistribution permission has been independently verified and approved.",
        ])
    else:
        lines.extend(["", "<b>Choose an approved quality below.</b>"])

    await state.update_data(torrentclaw_magnets=magnet_map, torrentclaw_selected_hash=None, torrentclaw_selected_movie_key=key)
    builder.row(InlineKeyboardButton(text="⬅️ Back to movie results", callback_data="torrentback"))
    builder.row(InlineKeyboardButton(text="🏠 Home", callback_data="nav:home"))
    await callback.message.answer("\n".join(lines)[:3900], reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("torrentquality:"))
async def select_torrent_quality(callback: CallbackQuery, state: FSMContext):
    info_hash = callback.data.split(":", 1)[1].lower()
    data = await state.get_data()
    entry = (data.get("torrentclaw_magnets") or {}).get(info_hash)
    if (
        not _HASH.fullmatch(info_hash)
        or info_hash not in (settings.torrentclaw_approved_infohashes or set())
        or not isinstance(entry, dict)
    ):
        await callback.answer("This quality is not approved. Search and select the movie again.", show_alert=True)
        return

    await state.update_data(torrentclaw_selected_hash=info_hash)
    builder = InlineKeyboardBuilder()
    builder.button(text="⬇️ Download selected movie", callback_data=f"torrentdl:{info_hash}")
    builder.button(text="⬅️ Choose another quality", callback_data=f"moviepick:{data.get('torrentclaw_selected_movie_key', '0')}")
    builder.adjust(1)
    await callback.message.answer(
        f"Selected: <b>{html.escape(entry.get('title', 'Movie'))}</b>\n"
        f"Quality: <b>{html.escape(entry.get('quality', 'Unknown'))}</b>\n\n"
        "Press Download to receive this approved release.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer("Quality selected")


@router.callback_query(F.data.startswith("torrentdl:"))
async def send_approved_magnet(callback: CallbackQuery, state: FSMContext, torrentclaw, torrent_downloads):
    info_hash = callback.data.split(":", 1)[1].lower()
    if not _HASH.fullmatch(info_hash) or info_hash not in (settings.torrentclaw_approved_infohashes or set()):
        await callback.answer("This release is not approved for distribution.", show_alert=True)
        return
    data = await state.get_data()
    entry = (data.get("torrentclaw_magnets") or {}).get(info_hash)
    if data.get("torrentclaw_selected_hash") != info_hash:
        await callback.answer("Select a quality first.", show_alert=True)
        return
    magnet = entry.get("magnet") if isinstance(entry, dict) else None
    title = entry.get("title", "Approved movie") if isinstance(entry, dict) else "Approved movie"
    if not isinstance(magnet, str) or magnet_info_hash(magnet) != info_hash:
        await callback.answer("Search for this title again to refresh the release.", show_alert=True)
        return

    if not torrent_downloads.enabled:
        try:
            await torrentclaw.track(info_hash, "magnet")
        except Exception:
            logger.info("TorrentClaw tracking failed for approved hash %s", info_hash)
        await callback.message.answer(
            "⬇️ <b>Approved magnet link</b>\nOpen this link in a compatible torrent client:\n"
            f"<code>{html.escape(magnet)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await callback.answer("Magnet link ready")
        return

    await callback.answer("Starting approved download…")
    status_message = await callback.message.answer(f"⬇️ Preparing <b>{html.escape(title)}</b>…")
    path = None
    try:
        path = await torrent_downloads.fetch(magnet, info_hash)
        size_bytes = path.stat().st_size
        if size_bytes > settings.telegram_upload_max_bytes:
            await status_message.edit_text(
                "This approved file exceeds Telegram's upload size limit. "
                "Open the approved magnet in your own torrent client:\n"
                f"<code>{html.escape(magnet)}</code>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        sent = await callback.message.answer_document(
            torrent_downloads.input_file(path, path.name),
            caption=f"🎬 {html.escape(title)}\nApproved release · {size_bytes / (1024 * 1024):.1f} MB",
        )
        if sent.document:
            try:
                await torrentclaw.track(info_hash, "torrent_download")
            except Exception:
                logger.info("TorrentClaw tracking failed for approved hash %s", info_hash)
        await status_message.edit_text("✅ Your approved movie file has been sent.")
    except FileTooLarge as exc:
        size = f"{exc.size / (1024 * 1024):.1f} MB" if exc.size else "above the configured safety limit"
        await status_message.edit_text(f"This approved torrent is {size}. No file was sent.")
    except Exception as exc:
        logger.exception("Approved torrent transfer failed for %s: %s", info_hash, exc)
        await status_message.edit_text(
            "The server could not complete this approved download. Try the approved magnet in your torrent client:\n"
            f"<code>{html.escape(magnet)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    finally:
        if path:
            torrent_downloads.cleanup(path)
