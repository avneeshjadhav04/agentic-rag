#!/usr/bin/env bash
set -e

# Next.js standalone server entrypoint.
# HOSTNAME=0.0.0.0 ensures the server accepts external connections.
export HOSTNAME=${HOSTNAME:-0.0.0.0}
export PORT=${PORT:-3000}

cd /app/frontend
exec node server.js
