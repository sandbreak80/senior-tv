#!/bin/bash
# Take desktop + camera snapshots every 15 minutes for admin monitoring
# Called by cron: */15 * * * * /path/to/senior_tv/take_screenshot.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCREEN_DIR="$SCRIPT_DIR/static/screenshots"
CAM_DIR="$SCRIPT_DIR/static/camera_snaps"
MAX_MB=100
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

mkdir -p "$SCREEN_DIR" "$CAM_DIR"

# Take screenshot via Chrome DevTools Protocol (silent, captures actual TV output)
OUTFILE="$SCREEN_DIR/screen_${TIMESTAMP}.png"
"$SCRIPT_DIR/venv/bin/python3" -c "
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

# Save camera snapshot from local webcam via person detector
"$SCRIPT_DIR/venv/bin/python3" -c "
import subprocess
subprocess.run(['ffmpeg', '-f', 'v4l2', '-input_format', 'mjpeg',
    '-i', '/dev/video0', '-frames:v', '1', '-y', '-loglevel', 'error',
    '-update', '1', '$CAM_DIR/tv_room_${TIMESTAMP}.jpg'],
    timeout=5)
" 2>/dev/null

# Save snapshots from configured IP cameras
"$SCRIPT_DIR/venv/bin/python3" -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR')
from models import get_setting
import subprocess
cam_url = get_setting('ip_camera_snapshot_url')
if cam_url:
    subprocess.run(['curl', '-sf', '--max-time', '5', cam_url,
        '-o', '$CAM_DIR/front_door_${TIMESTAMP}.jpg'], timeout=10)
" 2>/dev/null

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
