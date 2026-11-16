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
from bot.services.download_manager import FileTooLarge
from bot.services.torrent_download_manager import magnet_info_hash

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
    magnet_map: dict[str, dict[str, str]] = {}
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
            if info_hash in approved and _HASH.fullmatch(info_hash) and isinstance(magnet, str) and magnet_info_hash(magnet) == info_hash:
                magnet_map[info_hash] = {"magnet": magnet, "title": str(item.get("title") or "Approved movie")[:180]}
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
async def send_approved_magnet(callback: CallbackQuery, state: FSMContext, torrentclaw, torrent_downloads):
    info_hash = callback.data.split(":", 1)[1].lower()
    if not _HASH.fullmatch(info_hash) or info_hash not in settings.torrentclaw_approved_infohashes:
        await callback.answer("This torrent is not approved for download.", show_alert=True)
        return
    data = await state.get_data()
    entry = (data.get("torrentclaw_magnets") or {}).get(info_hash)
    magnet = entry.get("magnet") if isinstance(entry, dict) else None
    title = entry.get("title", "Approved movie") if isinstance(entry, dict) else "Approved movie"
    if not isinstance(magnet, str) or magnet_info_hash(magnet) != info_hash:
        await callback.answer("Search for this title again to refresh the download.", show_alert=True)
        return

    if not torrent_downloads.enabled:
        try:
            await torrentclaw.track(info_hash, "magnet")
        except Exception:
            logger.info("TorrentClaw tracking request failed for approved hash %s", info_hash)
        await callback.message.answer(
            "⬇️ <b>Approved torrent magnet</b>\n"
            "Server-side downloads are disabled. Open this link in a compatible torrent client:\n"
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
                "This approved file is within the 3 GB server-download safety limit, "
                "but is too large for Telegram's upload limit. Open the approved magnet "
                "in your own torrent client:\n"
                f"<code>{html.escape(magnet)}</code>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        size_mb = size_bytes / (1024 * 1024)
        sent = await callback.message.answer_document(
            torrent_downloads.input_file(path, path.name),
            caption=f"🎬 {html.escape(title)}\nRights-checked torrent approved by the bot administrator.\nSize: {size_mb:.1f} MB",
        )
        if sent.document:
            try:
                await torrentclaw.track(info_hash, "torrent_download")
            except Exception:
                logger.info("TorrentClaw tracking request failed for approved hash %s", info_hash)
        await status_message.edit_text("✅ Your approved movie file has been sent.")
    except FileTooLarge as exc:
        size = f"{exc.size / (1024 * 1024):.1f} MB" if exc.size else "above the configured limit"
        await status_message.edit_text(
            f"This approved torrent is {size}, above the 3 GB server-download safety limit. No file was sent."
        )
    except Exception as exc:
        logger.exception("Approved torrent transfer failed for %s: %s", info_hash, exc)
        await status_message.edit_text(
            "The server could not complete this approved download. No file was sent.\n"
            "You can still open the approved magnet in your own torrent client:\n"
            f"<code>{html.escape(magnet)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    finally:
        if path:
            torrent_downloads.cleanup(path)
