#!/bin/bash
# Start Uvicorn API in background
python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT &

# Start Telegram Bot in foreground
python main.py
