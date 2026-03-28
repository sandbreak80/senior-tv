#!/bin/bash
# Take desktop + camera snapshots every 15 minutes for admin monitoring
# Called by cron: */15 * * * * /home/media/code_projectsd/senior_tv/take_screenshot.sh

SCREEN_DIR="/home/media/code_projectsd/senior_tv/static/screenshots"
CAM_DIR="/home/media/code_projectsd/senior_tv/static/camera_snaps"
MAX_MB=100
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Take screenshot via Chrome DevTools Protocol (silent, captures actual TV output)
OUTFILE="$SCREEN_DIR/screen_${TIMESTAMP}.png"
/home/media/code_projectsd/senior_tv/venv/bin/python3 -c "
import json, base64, urllib.request, websocket
tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5).read())
ws_url = next((t['webSocketDebuggerUrl'] for t in tabs if t.get('type') == 'page'), None)
if ws_url:
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
    result = json.loads(ws.recv())
    ws.close()
    if 'result' in result:
        with open('$OUTFILE', 'wb') as f:
            f.write(base64.b64decode(result['result']['data']))
" 2>/dev/null

# Save camera snapshots from Frigate (check on loved ones)
# Local USB camera (tv_room) via local Frigate
curl -sf --max-time 5 "http://localhost:5001/api/tv_room/latest.jpg?h=480" \
    -o "$CAM_DIR/tv_room_${TIMESTAMP}.jpg" 2>/dev/null
# Network cameras via remote Frigate
FRIGATE_URL="http://192.168.50.114:5000"
for camera in front_door den living_room family_room kitchen; do
    curl -sf --max-time 5 "${FRIGATE_URL}/api/${camera}/latest.jpg?h=480" \
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
