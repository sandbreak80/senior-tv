#!/bin/bash
# Take desktop + camera snapshots every 15 minutes for admin monitoring
# Called by cron: */15 * * * * /home/media/code_projectsd/senior_tv/take_screenshot.sh

SCREEN_DIR="/home/media/code_projectsd/senior_tv/static/screenshots"
CAM_DIR="/home/media/code_projectsd/senior_tv/static/camera_snaps"
MAX_MB=100
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Take desktop screenshot
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
export DISPLAY=:0
gnome-screenshot -f "$SCREEN_DIR/screen_${TIMESTAMP}.png" 2>/dev/null

# Save camera snapshots from Frigate (check on loved ones)
for camera in tv_room living_room family_room kitchen; do
    curl -sf --max-time 5 "http://localhost:5001/api/${camera}/latest.jpg?h=480" \
        -o "$CAM_DIR/${camera}_${TIMESTAMP}.jpg" 2>/dev/null
done

# Cleanup: remove oldest files if total exceeds limit
for dir in "$SCREEN_DIR" "$CAM_DIR"; do
    TOTAL_KB=$(du -sk "$dir" 2>/dev/null | awk '{print $1}')
    MAX_KB=$((MAX_MB * 1024))
    while [ "$TOTAL_KB" -gt "$MAX_KB" ]; do
        OLDEST=$(ls -1t "$dir"/*.{png,jpg} 2>/dev/null | tail -1)
        [ -z "$OLDEST" ] && break
        rm -f "$OLDEST"
        TOTAL_KB=$(du -sk "$dir" 2>/dev/null | awk '{print $1}')
    done
done
