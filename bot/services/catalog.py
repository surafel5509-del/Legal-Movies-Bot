import json

from sqlalchemy import func, select

from bot.database.models import Download, Favorite, Movie, MovieFile, SearchHistory, User, utcnow


async def get_or_create_user(session, tg_user) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == tg_user.id))
    if user is None:
        user = User(telegram_id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name)
        session.add(user)
    user.username = tg_user.username
    user.first_name = tg_user.first_name
    user.last_active = utcnow()
    await session.flush()
    return user


async def record_search(session, user: User, query: str) -> None:
    session.add(SearchHistory(user_id=user.id, query=query[:500]))


async def save_movie(session, data: dict) -> Movie:
    movie = await session.scalar(select(Movie).where(Movie.source_id == data["identifier"]))
    if movie is None:
        movie = Movie(
            source_id=data["identifier"],
            title=data["title"],
            license=data["license"],
            license_url=data["license_url"],
            source_url=data["source_url"],
        )
        session.add(movie)
    movie.title = data["title"]
    movie.description = data.get("description")
    movie.release_year = data.get("year")
    movie.genre = data.get("genre")
    movie.language = data.get("language")
    movie.poster_url = data.get("poster_url")
    movie.license = data["license"]
    movie.license_url = data["license_url"]
    movie.source_url = data["source_url"]
    movie.metadata_json = json.dumps(data.get("raw", {}), ensure_ascii=False, default=str)
    await session.flush()

    # Refresh existing file records because source URLs and metadata can change.
    # Remove retired options so stale download buttons cannot target old files.
    existing_rows = list((await session.scalars(
        select(MovieFile).where(MovieFile.movie_id == movie.id)
    )).all())
    existing = {row.filename: row for row in existing_rows}
    incoming = {item["filename"]: item for item in data.get("files", [])}
    for filename, row in existing.items():
        if filename not in incoming:
            await session.delete(row)
            continue
        file_data = incoming[filename]
        url_changed = row.download_url != file_data["download_url"]
        for key in ("format", "resolution", "file_size", "download_url", "codec"):
            if key in file_data:
                setattr(row, key, file_data[key])
        if url_changed:
            row.telegram_file_id = None
    for filename, file_data in incoming.items():
        if filename not in existing:
            session.add(MovieFile(movie_id=movie.id, **file_data))
    await session.flush()
    return movie


async def toggle_favorite(session, user: User, movie_id: int) -> bool:
    favorite = await session.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id))
    if favorite:
        await session.delete(favorite)
        return False
    session.add(Favorite(user_id=user.id, movie_id=movie_id))
    return True


async def get_favorites(session, user: User) -> list[Movie]:
    stmt = select(Movie).join(Favorite, Favorite.movie_id == Movie.id).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())
    return list((await session.scalars(stmt)).all())


async def record_download(session, user: User, movie: Movie, status: str) -> None:
    session.add(Download(user_id=user.id, movie_id=movie.id, status=status))


async def admin_stats(session) -> dict:
    from datetime import timedelta
    return {
        "users": await session.scalar(select(func.count(User.id))) or 0,
        "active": await session.scalar(select(func.count(User.id)).where(User.last_active >= utcnow() - timedelta(days=30))) or 0,
        "searches": await session.scalar(select(func.count(SearchHistory.id))) or 0,
        "downloads": await session.scalar(select(func.count(Download.id)).where(Download.status == "sent")) or 0,
        "popular": list((await session.execute(select(Movie.title, func.count(Download.id).label("n")).join(Download, Download.movie_id == Movie.id).where(Download.status == "sent").group_by(Movie.id).order_by(func.count(Download.id).desc()).limit(5))).all()),
    }
