#!/bin/sh
# Startup script for Railway deployment
# Reads PORT from environment and starts uvicorn

# Get PORT from environment, default to 8000 if not set
PORT=${PORT:-8000}

echo "Starting uvicorn on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
