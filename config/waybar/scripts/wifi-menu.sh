#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/tmp/waybar-wifi-popup.pid"
SCRIPT="$HOME/.config/waybar/scripts/wifi-menu.py"

if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" && -r "/proc/$pid/cmdline" ]] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "wifi-menu.py"; then
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so exec python3 "$SCRIPT"
