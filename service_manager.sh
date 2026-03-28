#!/bin/bash
# service_manager.sh - Manage Algo-Trader macOS service

PROJECT_ROOT=$(cd "$(dirname "$0")" && pwd)
PLIST_NAME="com.user.algotrader.plist"
PLIST_SRC="$PROJECT_ROOT/backend/service/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

case "$1" in
    install)
        echo "Installing Algo-Trader service..."
        cp "$PLIST_SRC" "$PLIST_DEST"
        # Update paths in the installed plist
        sed -i '' "s|/Users/manas/Documents/AlphaCentuari/algo-trader|$PROJECT_ROOT|g" "$PLIST_DEST"
        launchctl load "$PLIST_DEST"
        echo "✅ Installed and Loaded."
        ;;
    uninstall)
        echo "Uninstalling Algo-Trader service..."
        launchctl unload "$PLIST_DEST"
        rm "$PLIST_DEST"
        echo "✅ Uninstalled."
        ;;
    start)
        echo "Starting service..."
        launchctl load "$PLIST_DEST" 2>/dev/null
        launchctl start com.user.algotrader
        echo "✅ Started."
        ;;
    stop)
        echo "Stopping service..."
        launchctl stop com.user.algotrader
        # launchctl unload "$PLIST_DEST"
        echo "✅ Stopped."
        ;;
    status)
        echo "--- Service Status ---"
        launchctl list | grep com.user.algotrader
        echo "----------------------"
        echo "Tail logs: tail -f $PROJECT_ROOT/worker_output.log"
        ;;
    *)
        echo "Usage: $0 {install|uninstall|start|stop|status}"
        exit 1
        ;;
esac
