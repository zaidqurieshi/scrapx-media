#!/usr/bin/env bash
# ==============================================================================
# ScrapX Media — macOS LaunchAgent Service Manager
# ==============================================================================
set -e

PLIST_NAME="com.scrapx.media.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_PLIST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

action="${1:-status}"

case "${action}" in
  install)
    echo "Installing ScrapX Media background LaunchAgent..."
    mkdir -p "${HOME}/Library/LaunchAgents"
    mkdir -p "${PROJECT_DIR}/logs"
    cp "${SCRIPT_DIR}/${PLIST_NAME}" "${TARGET_PLIST}"
    # Unload if previously running
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
    # Load and start the service
    launchctl load "${TARGET_PLIST}"
    echo "✅ ScrapX Media service successfully installed and started!"
    echo "Status: Running continuously in background via launchd"
    ;;

  status)
    echo "=== ScrapX Media Background Service Status ==="
    if launchctl list | grep -q "com.scrapx.media"; then
      echo "✅ Service Status: ACTIVE / RUNNING"
      launchctl list | grep "com.scrapx.media"
      echo ""
      echo "--- Recent Activity Log (logs/scrapx.log) ---"
      tail -n 15 "${PROJECT_DIR}/logs/scrapx.log" 2>/dev/null || echo "No logs yet."
    else
      echo "❌ Service Status: NOT RUNNING"
    fi
    ;;

  stop)
    echo "Stopping ScrapX Media service..."
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
    echo "Service stopped."
    ;;

  start)
    echo "Starting ScrapX Media service..."
    launchctl load "${TARGET_PLIST}"
    echo "Service started."
    ;;

  restart)
    echo "Restarting ScrapX Media service..."
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
    sleep 1
    launchctl load "${TARGET_PLIST}"
    echo "Service restarted."
    ;;

  uninstall)
    echo "Uninstalling ScrapX Media service..."
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
    rm -f "${TARGET_PLIST}"
    echo "Service uninstalled."
    ;;

  *)
    echo "Usage: $0 {install|start|stop|restart|status|uninstall}"
    exit 1
    ;;
esac

