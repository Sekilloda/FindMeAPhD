#!/usr/bin/env bash
# ==============================================================================
# Helper to install, start, or remove the periodic launchd monitor on macOS
# ==============================================================================

set -euo pipefail

PLIST_NAME="com.hypatia.phdmonitor.plist"
SRC_PLIST="$(cd "$(dirname "$0")/.." && pwd)/$PLIST_NAME"
DEST_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

ACTION="${1:-status}"

case "$ACTION" in
    install|start)
        echo "[*] Installing launchd agent to $DEST_PLIST..."
        mkdir -p "$HOME/Library/LaunchAgents"
        cp "$SRC_PLIST" "$DEST_PLIST"
        
        # Unload first if already loaded to avoid error
        launchctl unload "$DEST_PLIST" 2>/dev/null || true
        launchctl load "$DEST_PLIST"
        echo "[+] Successfully installed and loaded $PLIST_NAME!"
        echo "    The monitor will run automatically in the background every 12 hours."
        echo "    Logs: $(dirname "$SRC_PLIST")/monitor.log"
        ;;
    uninstall|stop)
        echo "[*] Unloading and removing $PLIST_NAME..."
        launchctl unload "$DEST_PLIST" 2>/dev/null || true
        rm -f "$DEST_PLIST"
        echo "[+] Successfully uninstalled launchd agent."
        ;;
    status)
        echo "=== Hypatia Periodic Task Status ==="
        if [ -f "$DEST_PLIST" ]; then
            echo "[✓] Plist exists at: $DEST_PLIST"
            if launchctl list | grep -q "com.hypatia.phdmonitor"; then
                echo "[✓] Agent is currently LOADED and RUNNING in launchd."
            else
                echo "[!] Plist exists but is NOT currently loaded."
            fi
        else
            echo "[i] Agent is NOT installed."
            echo "    Run: ./scripts/setup_schedule.sh install"
        fi
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
