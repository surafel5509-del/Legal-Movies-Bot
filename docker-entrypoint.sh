#!/bin/sh
set -eu

VOLUME_PATH="${RAILWAY_VOLUME_MOUNT_PATH:-/data}"
mkdir -p "$VOLUME_PATH"
chown -R app:app "$VOLUME_PATH" /tmp/legal-movie-bot
exec gosu app "$@"
