#!/bin/bash
# QuantDeck stopper — double-click to stop the running app.
lsof -ti tcp:8000 2>/dev/null | xargs kill 2>/dev/null
pkill -f "uvicorn api.main" 2>/dev/null
echo "QuantDeck stopped. You can close this window."
sleep 1
