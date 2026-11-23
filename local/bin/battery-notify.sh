#!/usr/bin/env bash
set -euo pipefail

# Detecta la primera batería disponible en /sys/class/power_supply
BAT_DIR=""
for dir in /sys/class/power_supply/BAT*; do
    if [ -d "$dir" ]; then
        BAT_DIR="$dir"
        break
    fi
done

if [ -z "$BAT_DIR" ]; then
    exit 0
fi

CAPACITY=$(cat "$BAT_DIR/capacity")
STATUS=$(cat "$BAT_DIR/status")
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/battery-notify.state"

POPUP_BIN="/home/kovac/.local/bin/battery-popup.py"

send_notification() {
    local level="$1"
    local urgency="$2"
    local icon="$3"
    local title="$4"

    if [ -x "$POPUP_BIN" ]; then
        nohup python3 "$POPUP_BIN" --level "$level" --capacity "$CAPACITY" >/dev/null 2>&1 &
    else
        notify-send \
            -a "Batería" \
            -u "$urgency" \
            -i "$icon" \
            -h string:x-dunst-stack-tag:battery \
            "$title"
    fi
}

# Si está cargando o llena, reinicia el estado para el próximo ciclo de descarga
if [ "$STATUS" != "Discharging" ]; then
    rm -f "$STATE_FILE"
    exit 0
fi

LAST_LEVEL=100
if [ -f "$STATE_FILE" ]; then
    LAST_LEVEL=$(cat "$STATE_FILE" 2>/dev/null || echo 100)
fi

if [ "$CAPACITY" -le 5 ] && [ "$LAST_LEVEL" -gt 5 ]; then
    send_notification "critical" "critical" "battery-empty" "Batería crítica ${CAPACITY}%"
    echo 5 > "$STATE_FILE"
elif [ "$CAPACITY" -le 10 ] && [ "$LAST_LEVEL" -gt 10 ]; then
    send_notification "low" "critical" "battery-caution" "Batería muy baja ${CAPACITY}%"
    echo 10 > "$STATE_FILE"
elif [ "$CAPACITY" -le 20 ] && [ "$LAST_LEVEL" -gt 20 ]; then
    send_notification "warning" "normal" "battery-low" "Batería baja ${CAPACITY}%"
    echo 20 > "$STATE_FILE"
fi
