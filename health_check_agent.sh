#!/bin/bash
# Senior TV Health Check Agent
# Runs Claude Code locally every hour to diagnose and fix issues
# Called by cron: 0 * * * * $SCRIPT_DIR/health_check_agent.sh

LOG="/var/log/senior-tv-claude-check.log"
LOCK="/tmp/senior_tv_health_agent.lock"

# Rotate logs if >10MB
for logfile in "$LOG" /var/log/senior-tv-watchdog.log /var/log/senior-tv-repairs.log; do
    if [ -f "$logfile" ] && [ "$(stat -f%z "$logfile" 2>/dev/null || stat -c%s "$logfile" 2>/dev/null)" -gt 10485760 ]; then
        tail -1000 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
    fi
done

# Prevent overlapping runs
if [ -f "$LOCK" ]; then
    PID=$(cat "$LOCK")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date): Health agent already running (PID $PID), skipping" >> "$LOG"
        exit 0
    fi
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export HOME="${HOME:-$(eval echo ~$(whoami))}"
export PATH="$HOME/.local/bin:$PATH"

echo "$(date): Starting health check agent" >> "$LOG"

# Run Claude with the health check prompt
claude --print --dangerously-skip-permissions -p "You are a health check agent for the Senior TV kiosk system. This runs on the local machine.

1. Run: curl -s http://localhost:5000/api/health
   Parse the JSON output. If ALL checks show ok=true, just say 'All systems healthy' and exit.

2. If the endpoint is unreachable:
   - Run: systemctl status senior-tv.service
   - Run: journalctl -u senior-tv.service --since '1 hour ago' --no-pager | tail -50
   - Fix it: sudo systemctl restart senior-tv.service
   - Wait 10 seconds then re-check

3. For each check that is NOT ok:
   - audio: run bash $SCRIPT_DIR/fix_audio.sh
   - chrome not running: sudo systemctl restart senior-tv.service
   - tailscale not ok: sudo systemctl restart tailscaled
   - internet not reachable: ping -c 2 8.8.8.8 and check systemctl status NetworkManager
   - memory high: check what is using memory with ps aux --sort=-%mem | head -10
   - watchdog repairs_today > 10: cat /var/log/senior-tv-repairs.log | tail -20

4. Check for recent errors:
   journalctl -u senior-tv.service --since '1 hour ago' --priority err --no-pager | tail -20

5. Take a SILENT screenshot via Chrome DevTools Protocol (NEVER use gnome-screenshot — it flashes the screen and plays a shutter sound, scaring the users):
   python3 -c \"import json, base64, urllib.request, websocket; tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5).read()); ws_url = next((t['webSocketDebuggerUrl'] for t in tabs if t.get('type') == 'page'), None); ws = websocket.create_connection(ws_url, timeout=10); ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}})); result = json.loads(ws.recv()); ws.close(); open('$SCRIPT_DIR/screenshots/health_check.png', 'wb').write(base64.b64decode(result['result']['data']))\"
   Then read the screenshot file at $SCRIPT_DIR/screenshots/health_check.png
   Verify: Chrome should be fullscreen showing the Senior TV app (dark theme, hotel-style TV interface).
   Problems to flag: GNOME desktop visible, error dialogs, crash popups, wrong app displayed, blank screen.
   If Chrome is not fullscreen or there are error popups visible, investigate and fix.

6. Summarize what you found and any actions taken." >> "$LOG" 2>&1

echo "$(date): Health check complete" >> "$LOG"
echo "---" >> "$LOG"
