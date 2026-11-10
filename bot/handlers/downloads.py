import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.db import Session
from bot.database.models import Movie, MovieFile, User
from bot.services.catalog import get_or_create_user, record_download
from bot.services.download_manager import DownloadManager, FileTooLarge

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("download:"))
async def download_movie(callback: CallbackQuery, downloads: DownloadManager, archive):
    try:
        payload = callback.data.removeprefix("download:")
        identifier, raw_file_id = payload.rsplit(":", 1)
        file_id = int(raw_file_id)
    except (ValueError, TypeError):
        await callback.answer("Invalid download selection.", show_alert=True)
        return

    async with Session() as session:
        movie_file = await session.scalar(
            select(MovieFile).join(Movie)
            .where(Movie.source_id == identifier, MovieFile.id == file_id)
            .options(selectinload(MovieFile.movie))
        )
        if not movie_file:
            await callback.answer("This file is no longer available.", show_alert=True)
            return
        movie = movie_file.movie
        file_data = {
            "url": movie_file.download_url,
            "filename": movie_file.filename,
            "movie_title": movie.title,
            "movie_id": movie.id,
            "source_url": movie.source_url,
            "license": movie.license,
            "license_url": movie.license_url,
            "metadata_json": movie.metadata_json,
        }
    # Re-fetch source metadata at click time. Never trust a stale DB license or
    # a URL that has changed since the search result was shown.
    try:
        current = await archive.details(identifier)
    except Exception as exc:
        logger.exception("Fresh rights check failed for %s: %s", identifier, exc)
        current = None
    current_file = next(
        (item for item in (current or {}).get("files", [])
         if item.get("filename") == file_data["filename"]
         and item.get("download_url") == file_data["url"]),
        None,
    )
    if (
        not current
        or current.get("license") != file_data["license"]
        or current.get("license_url") != file_data["license_url"]
        or not current_file
    ):
        await callback.answer("The source rights or file changed. Download blocked.", show_alert=True)
        return

    async with Session() as session:
        movie = await session.get(Movie, file_data["movie_id"])
        movie_file = await session.get(MovieFile, file_id)
        user = await get_or_create_user(session, callback.from_user)
        if not movie or not movie_file:
            await callback.answer("This download is no longer available.", show_alert=True)
            return
        if movie_file.telegram_file_id:
            try:
                await callback.message.answer_document(
                    movie_file.telegram_file_id,
                    caption=f"🎬 {movie.title}\nLicense: {movie.license}",
                )
                await record_download(session, user, movie, "sent")
                await session.commit()
                await callback.answer("Sent")
                return
            except Exception:
                logger.warning("Cached Telegram file expired; downloading fresh copy", exc_info=True)
                movie_file.telegram_file_id = None
        await record_download(session, user, movie, "started")
        await session.commit()

    await callback.answer("Preparing verified file…")
    path = None
    try:
        path = await downloads.fetch(
            file_data["url"], file_data["filename"], expected_license=file_data["license"]
        )
        upload_filename = Path(file_data["filename"]).stem + path.suffix
        try:
            metadata = json.loads(file_data["metadata_json"] or "{}")
        except (TypeError, ValueError):
            metadata = {}
        creator = metadata.get("uploader") or metadata.get("creator") or metadata.get("author")
        if isinstance(creator, list):
            creator = ", ".join(str(value) for value in creator[:3])
        credit_line = f"\nCredit: {str(creator)[:180]}" if creator else ""
        caption = (
            f"🎬 {file_data['movie_title'][:180]}{credit_line}"
            f"\nLicense: {file_data['license'][:120]}"
            f"\nSource: {file_data['source_url']}"
            f"\nLicense terms: {file_data['license_url']}"
        )[:1024]
        sent = await callback.message.answer_document(
            downloads.input_file(path, upload_filename), caption=caption,
        )
        telegram_file_id = sent.document.file_id if sent.document else None
        async with Session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            movie = await session.get(Movie, file_data["movie_id"])
            movie_file = await session.get(MovieFile, file_id)
            if movie_file and telegram_file_id:
                movie_file.telegram_file_id = telegram_file_id
            if user and movie:
                await record_download(session, user, movie, "sent")
            await session.commit()
    except FileTooLarge as exc:
        async with Session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            movie = await session.get(Movie, file_data["movie_id"])
            if user and movie:
                await record_download(session, user, movie, "external_only")
            await session.commit()
        size = f"{exc.size / (1024 * 1024):.1f} MB" if exc.size else "larger than the configured upload cap"
        await callback.message.answer(
            f"This authorized file is {size}, above this bot's Telegram upload limit ({settings.max_upload_bytes / (1024 * 1024):.0f} MB). I have not uploaded it.\n\nOpen the authorized source page: {file_data['source_url']}",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.exception("Download transfer failed for %s: %s", identifier, exc)
        async with Session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            movie = await session.get(Movie, file_data["movie_id"])
            if user and movie:
                await record_download(session, user, movie, "failed")
            await session.commit()
        await callback.message.answer(
            f"The transfer failed. No file was sent. Try later or use the authorized source page: {file_data['source_url']}",
            disable_web_page_preview=True,
        )
    finally:
        if path:
            downloads.cleanup(path)
