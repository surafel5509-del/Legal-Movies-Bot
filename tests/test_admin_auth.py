import pytest
from sqlalchemy import delete

from bot.config import settings
from bot.database.db import Session, init_db
from bot.database.models import AdminClaim
from bot.handlers.admin import is_admin


@pytest.mark.asyncio
async def test_configured_admin_ids_are_authorized():
    if settings.admin_ids:
        admin_id = next(iter(settings.admin_ids))
        assert await is_admin(admin_id)


@pytest.mark.asyncio
async def test_first_admin_claim_is_persisted_and_authorized():
    await init_db()
    async with Session() as session:
        await session.execute(delete(AdminClaim))
        await session.commit()
        session.add(AdminClaim(id=1, telegram_id=987654321))
        await session.commit()
    assert await is_admin(987654321)
    assert not await is_admin(987654322)
