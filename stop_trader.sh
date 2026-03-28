#!/bin/bash
# stop_trader.sh - Gracefully stop the background worker

echo "Finding and stopping Algo-Trader worker processes..."
ps aux | grep worker.py | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Worker stopped successfully."
else
    echo "ℹ️ No running worker found."
fi
