from bot.handlers.admin import is_admin


def test_admin_authorization_uses_configured_ids():
    from bot.config import settings

    if settings.admin_ids:
        admin_id = next(iter(settings.admin_ids))
        assert is_admin(admin_id)
        assert not is_admin(admin_id + 1)
    else:
        assert not is_admin(1)
