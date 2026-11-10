import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models import Base, MovieFile
from bot.services.catalog import save_movie


@pytest.mark.asyncio
async def test_save_movie_inserts_files_without_async_lazy_loading_and_is_idempotent():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    movie_data = {
        "identifier": "sample-public-domain-film",
        "title": "Sample Public Domain Film",
        "description": "A test film",
        "year": 1930,
        "genre": "Drama",
        "language": "English",
        "poster_url": None,
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "source_url": "https://archive.org/details/sample-public-domain-film",
        "raw": {},
        "files": [{
            "filename": "sample.mp4",
            "format": "MP4",
            "resolution": "480p",
            "file_size": 1024,
            "download_url": "https://archive.org/download/sample-public-domain-film/sample.mp4",
            "codec": None,
        }],
    }

    try:
        async with sessions() as session:
            movie = await save_movie(session, movie_data)
            await session.commit()
            movie_id = movie.id

            # Saving the same metadata again must not duplicate MovieFile rows.
            await save_movie(session, movie_data)
            await session.commit()

            count = await session.scalar(
                select(func.count(MovieFile.id)).where(MovieFile.movie_id == movie_id)
            )
            assert count == 1

            # A refreshed source URL must replace the stale URL and reset the
            # cached Telegram copy so the next delivery fetches current bytes.
            movie_data["files"][0]["download_url"] = "https://archive.org/download/sample-public-domain-film/updated.mp4"
            movie_data["files"][0]["file_size"] = 2048
            await save_movie(session, movie_data)
            await session.commit()
            refreshed = await session.scalar(
                select(MovieFile).where(MovieFile.movie_id == movie_id)
            )
            assert refreshed.download_url.endswith("updated.mp4")
            assert refreshed.file_size == 2048

            # If the source removes a file, its old download option is removed.
            movie_data["files"] = []
            await save_movie(session, movie_data)
            await session.commit()
            count = await session.scalar(
                select(func.count(MovieFile.id)).where(MovieFile.movie_id == movie_id)
            )
            assert count == 0
    finally:
        await engine.dispose()
