#!/usr/bin/env bash
set -e

echo "🚀 Starting deployment process..."
echo "🧩 Running Alembic migrations..."
python -m alembic upgrade head

echo "🔥 Starting Gunicorn server..."
exec gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
