from __future__ import annotations

import html
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.services.torrentclaw_api import TorrentClawError

router = Router()
logger = logging.getLogger(__name__)
_HASH = re.compile(r"^[a-fA-F0-9]{40}$")


def _safe_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


@router.message(Command("torrent"))
async def torrent_search(message: Message, state: FSMContext, torrentclaw):
    query = (message.text or "").partition(" ")[2].strip()
    if len(query) < 2:
        await message.answer("Usage: /torrent movie title\nExample: /torrent Night of the Living Dead")
        return
    await _render(message, state, torrentclaw, query)


@router.callback_query(F.data == "nav:torrent")
async def torrent_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Send a movie or series title, or use /torrent title.")
    await callback.answer()


async def _render(message: Message, state: FSMContext, torrentclaw, query: str):
    try:
        payload = await torrentclaw.search(query, limit=10)
    except TorrentClawError as exc:
        await message.answer(str(exc))
        return
    results = payload.get("results") or []
    if not results:
        await message.answer("TorrentClaw found no matches for that title.")
        return

    approved = settings.torrentclaw_approved_infohashes
    magnet_map: dict[str, str] = {}
    builder = InlineKeyboardBuilder()
    lines = [f"<b>🔎 TorrentClaw results</b> · {html.escape(query[:80])}", ""]
    shown = 0
    for item in results[:10]:
        title = html.escape(str(item.get("title") or "Untitled")[:100])
        year = item.get("year")
        rating = item.get("ratingImdb") or item.get("ratingTmdb")
        lines.append(f"<b>{title}</b>{f' ({year})' if year else ''}")
        if rating:
            lines.append(f"⭐ Rating: {html.escape(str(rating))}")
        torrents = item.get("torrents") or []
        for torrent in torrents[:5]:
            info_hash = str(torrent.get("infoHash") or "").lower()
            quality = html.escape(str(torrent.get("quality") or "Unknown"))
            codec = html.escape(str(torrent.get("codec") or ""))
            size_bytes = _safe_int(torrent.get("sizeBytes"))
            size = f"{size_bytes / (1024 ** 3):.2f} GB" if size_bytes else "size n/a"
            seeders = _safe_int(torrent.get("seeders"))
            score = _safe_int(torrent.get("qualityScore"))
            lines.append(f"  • {quality} {codec} · {size} · {seeders} seeders · score {score}/100")
            magnet = torrent.get("magnetUrl")
            # TorrentClaw does not return license evidence. A magnet is actionable
            # only when an operator has independently reviewed and allowlisted its hash.
            if info_hash in approved and _HASH.fullmatch(info_hash) and isinstance(magnet, str) and magnet.startswith("magnet:?"):
                magnet_map[info_hash] = magnet
                builder.row(InlineKeyboardButton(
                    text=f"⬇️ Download approved · {quality}"[:60],
                    callback_data=f"torrentdl:{info_hash}",
                ))
                shown += 1
        lines.append("")
    await state.update_data(torrentclaw_magnets=magnet_map)
    if shown == 0:
        lines.extend([
            "No download buttons are enabled for these results yet.",
            "TorrentClaw search results do not prove distribution rights. An administrator must independently verify a torrent's license/permission and add its info hash to TORRENTCLAW_APPROVED_INFOHASHES before enabling its button.",
        ])
    else:
        lines.append("Download buttons are shown only for hashes reviewed and approved by the administrator.")
    await message.answer("\n".join(lines)[:4000], reply_markup=builder.as_markup() if shown else None,
                         parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data.startswith("torrentdl:"))
async def send_approved_magnet(callback: CallbackQuery, state: FSMContext, torrentclaw):
    info_hash = callback.data.split(":", 1)[1].lower()
    if not _HASH.fullmatch(info_hash) or info_hash not in settings.torrentclaw_approved_infohashes:
        await callback.answer("This torrent is not approved for download.", show_alert=True)
        return
    data = await state.get_data()
    magnet = (data.get("torrentclaw_magnets") or {}).get(info_hash)
    if not isinstance(magnet, str) or not magnet.startswith("magnet:?"):
        await callback.answer("Search for this title again to refresh the download.", show_alert=True)
        return
    try:
        await torrentclaw.track(info_hash, "magnet")
    except Exception:
        logger.info("TorrentClaw tracking request failed for approved hash %s", info_hash)
    await callback.message.answer(
        "⬇️ <b>Approved torrent magnet</b>\n"
        "Open/copy this magnet link in a compatible torrent client:\n"
        f"<code>{html.escape(magnet)}</code>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer("Magnet link ready")
