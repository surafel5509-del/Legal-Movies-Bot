from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.db import Session
from bot.database.models import Movie, MovieFile, User
from bot.services.catalog import get_or_create_user, record_download
from bot.services.download_manager import DownloadManager, FileTooLarge
from bot.services.license_verification import verify_archive_rights

router = Router()


@router.callback_query(F.data.startswith("download:"))
async def download_movie(callback: CallbackQuery, downloads: DownloadManager):
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
        rights_ok, verified_label, verified_url = verify_archive_rights({"licenseurl": movie.license_url})
        if not rights_ok or verified_url != movie.license_url or verified_label != movie.license:
            await callback.answer("Rights verification failed; download blocked.", show_alert=True)
            return
        user = await get_or_create_user(session, callback.from_user)
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
                movie_file.telegram_file_id = None
        file_data = {
            "url": movie_file.download_url, "filename": movie_file.filename,
            "movie_title": movie.title, "movie_id": movie.id,
            "source_url": movie.source_url,
        }
        await record_download(session, user, movie, "started")
        await session.commit()

    await callback.answer("Preparing authorized file…")
    path = None
    try:
        path = await downloads.fetch(file_data["url"], file_data["filename"])
        sent = await callback.message.answer_document(
            downloads.input_file(path, file_data["filename"]),
            caption=f"🎬 {file_data['movie_title']}\nVerified license: see the movie details for full terms.",
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
    except Exception:
        async with Session() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            movie = await session.get(Movie, file_data["movie_id"])
            if user and movie:
                await record_download(session, user, movie, "failed")
            await session.commit()
        await callback.message.answer(
            f"The transfer failed. No download was sent. You can retry later or use the authorized source page: {file_data['source_url']}",
            disable_web_page_preview=True,
        )
    finally:
        if path:
            path.unlink(missing_ok=True)
