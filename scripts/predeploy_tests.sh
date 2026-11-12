#!/bin/sh
set -eu

# Use isolated test settings; never connect release checks to the production DB.
BOT_TOKEN=123456:TEST \
ADMIN_IDS=1 \
DATABASE_URL=sqlite+aiosqlite:///:memory: \
python -m pytest -q
