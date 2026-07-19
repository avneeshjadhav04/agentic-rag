#!/usr/bin/env bash
set -e

# Render/Railway provide $PORT. Default to 3000 otherwise.
export PORT=${PORT:-3000}
export BACKEND_PORT=${BACKEND_PORT:-8000}

# Ensure the data directory exists for Chroma.
mkdir -p /app/data/chroma_db
mkdir -p /app/logs

exec supervisord -c /app/supervisord.conf
