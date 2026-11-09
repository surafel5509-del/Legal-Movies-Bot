from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings
from bot.database.models import Base


def _prepare_sqlite_path(database_url: str) -> None:
    if not database_url.startswith("sqlite+") or ":memory:" in database_url:
        return
    database_path = database_url.split("///", 1)[-1].split("?", 1)[0]
    if database_path and database_path != ":memory:":
        Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


_prepare_sqlite_path(settings.database_url)
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "sqlite":
            await conn.execute(text("PRAGMA foreign_keys=ON"))


@asynccontextmanager
async def session_scope():
    async with Session() as session:
        yield session
