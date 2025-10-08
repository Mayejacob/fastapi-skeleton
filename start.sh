#!/usr/bin/env bash
set -e

echo "🚀 Starting deployment process..."
echo "🧩 Running Alembic migrations..."
alembic upgrade head || echo "⚠️ Alembic migration failed — continuing anyway."

echo "🔥 Starting Gunicorn server..."
exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT
