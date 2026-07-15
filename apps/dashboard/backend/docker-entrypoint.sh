#!/bin/sh
# Container entrypoint: make the database directory writable, then drop root.
#
# Why this exists
# ---------------
# A managed platform (Railway, Fly, Render) attaches its persistent volume at
# runtime and it arrives **root-owned**, whatever the image says. Baking
# `mkdir -p /app/data` + `chown app` into the image is enough for a plain Docker
# named volume — that inherits the image's ownership — but NOT for a PaaS disk.
# The non-root app then cannot create the SQLite file, `db.connect()` raises
# "unable to open database file", and the container crashes on startup.
#
# So: start as root, fix the one directory we need, and immediately hand off to
# the unprivileged user with `exec` (which keeps PID 1, so signals and graceful
# shutdown still work).
set -e

DB_PATH="${STRATAGENT_DB:-/app/data/dashboard.db}"
DB_DIR=$(dirname "$DB_PATH")

mkdir -p "$DB_DIR"
# Ignore failure: on a read-only or already-correct mount this is a no-op, and a
# chown error must not stop the app from booting.
chown -R app "$DB_DIR" 2>/dev/null || true

# Honour the platform's assigned port. Railway/Heroku/Render inject $PORT and
# route to it; a hardcoded port makes the app unreachable (502) even though the
# container is healthy. Falls back to 8000 for docker-compose and local runs.
exec gosu app uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
