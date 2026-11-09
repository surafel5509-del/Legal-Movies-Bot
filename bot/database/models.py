from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(2), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Movie(Base):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    release_year: Mapped[int | None] = mapped_column(Integer)
    genre: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(255))
    poster_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str] = mapped_column(String(255))
    license_url: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    files: Mapped[list["MovieFile"]] = relationship(back_populates="movie", cascade="all, delete-orphan")


class MovieFile(Base):
    __tablename__ = "movie_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    format: Mapped[str] = mapped_column(String(40))
    resolution: Mapped[str | None] = mapped_column(String(32))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    download_url: Mapped[str] = mapped_column(Text)
    telegram_file_id: Mapped[str | None] = mapped_column(Text)
    codec: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("movie_id", "filename", name="uq_movie_filename"),)
    movie: Mapped[Movie] = relationship(back_populates="files")


class Download(Base):
    __tablename__ = "downloads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(24), default="started")


class SearchHistory(Base):
    __tablename__ = "search_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_user_favorite"),)
