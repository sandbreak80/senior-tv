#!/bin/bash
# Take a desktop screenshot every 15 minutes for admin monitoring
# Called by cron: */15 * * * * /home/media/code_projectsd/senior_tv/take_screenshot.sh

DIR="/home/media/code_projectsd/senior_tv/static/screenshots"
MAX_MB=100
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Take screenshot
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
export DISPLAY=:0
gnome-screenshot -f "$DIR/screen_${TIMESTAMP}.png" 2>/dev/null

# Cleanup: remove oldest screenshots if total exceeds 100MB
TOTAL_KB=$(du -sk "$DIR" 2>/dev/null | awk '{print $1}')
MAX_KB=$((MAX_MB * 1024))

while [ "$TOTAL_KB" -gt "$MAX_KB" ]; do
    OLDEST=$(ls -1t "$DIR"/screen_*.png 2>/dev/null | tail -1)
    [ -z "$OLDEST" ] && break
    rm -f "$OLDEST"
    TOTAL_KB=$(du -sk "$DIR" 2>/dev/null | awk '{print $1}')
done
