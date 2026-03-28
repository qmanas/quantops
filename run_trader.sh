#!/bin/bash
# run_trader.sh - Keep the Algo-Trader running for 7 days

# Ensure we are in the project root
PROJECT_ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$PROJECT_ROOT"

# Set PYTHONPATH to include the current directory
export PYTHONPATH=$PYTHONPATH:.

# Kill existing worker if any to avoid DB locks
echo "Stopping any existing workers..."
ps aux | grep worker.py | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

echo "Starting Algo-Trader Background Worker..."
echo "Using 'caffeinate' to prevent system sleep."
echo "Logs are being recorded in: worker_output.log"

# caffeinate -i: prevents the system from sleeping as long as the command is active
# nohup: allows the process to continue running after the terminal is closed
nohup caffeinate -i python3 -u backend/worker.py > worker_output.log 2>&1 &

echo "------------------------------------------------"
echo "✅ Worker started in background with PID: $!"
echo "📈 View live logs: tail -f worker_output.log"
echo "📊 Check stats:   python cli/trader.py stats"
echo "------------------------------------------------"
echo "Note: Keep your Mac plugged into power for the full 7 days."
