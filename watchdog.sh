#!/bin/bash
# Senior TV Local Watchdog
# Runs every 3 minutes via systemd timer
# Checks all components and auto-repairs

LOG="/var/log/senior-tv-watchdog.log"
REPAIR_LOG="/var/log/senior-tv-repairs.log"
REPAIR_COUNT_FILE="/tmp/senior_tv_repair_count"
PROJECT_DIR="/home/media/code_projectsd/senior_tv"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"; }
repair() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') REPAIR: $1" >> "$REPAIR_LOG"
    log "REPAIR: $1"
}

ISSUES=0

# --- 1. Flask Server ---
if ! curl -sf --max-time 5 http://localhost:5000/api/health > /dev/null 2>&1; then
    log "FAIL: Flask not responding on :5000"
    repair "Restarting senior-tv.service (Flask down)"
    systemctl restart senior-tv.service
    ISSUES=$((ISSUES + 1))
    # Service restart handles everything, exit early
    exit 0
fi

# --- 2. Chrome Process ---
if ! pgrep -f "chrome.*senior-tv-chrome" > /dev/null 2>&1; then
    log "FAIL: Chrome not running"
    repair "Restarting senior-tv.service (Chrome down)"
    # Restart the whole service since start.sh manages Chrome
    systemctl restart senior-tv.service
    ISSUES=$((ISSUES + 1))
fi

# --- 3. HDMI Audio ---
AUDIO_OK=false
DEFAULT_SINK=$(sudo -u media XDG_RUNTIME_DIR=/run/user/1000 wpctl status 2>/dev/null | grep -E '^\s*│?\s*\*' | head -1)
if echo "$DEFAULT_SINK" | grep -qi "hdmi\|radeon\|rembrandt\|samsung"; then
    AUDIO_OK=true
fi
if [ "$AUDIO_OK" = "false" ]; then
    log "FAIL: HDMI audio not default (current: $DEFAULT_SINK)"
    repair "Fixing HDMI audio routing"
    sudo -u media bash "$PROJECT_DIR/fix_audio.sh" >> "$LOG" 2>&1
    ISSUES=$((ISSUES + 1))
fi

# --- 4. Disk Space ---
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d '% ')
if [ "$DISK_PCT" -gt 90 ]; then
    log "WARN: Disk usage at ${DISK_PCT}%"
    repair "Cleaning disk (${DISK_PCT}% used)"
    find /home/media/.config/senior-tv-chrome/Crash\ Reports -name "*.dmp" -mtime +1 -delete 2>/dev/null
    find /tmp -name "senior_tv*" -mtime +7 -delete 2>/dev/null
    journalctl --vacuum-time=3d 2>/dev/null
    ISSUES=$((ISSUES + 1))
fi

# --- 5. Memory ---
MEM_AVAIL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
MEM_TOTAL=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
MEM_PCT=$((100 - (MEM_AVAIL * 100 / MEM_TOTAL)))
if [ "$MEM_PCT" -gt 90 ]; then
    log "WARN: Memory at ${MEM_PCT}%"
    repair "Restarting service (memory critical at ${MEM_PCT}%)"
    rm -rf /home/media/.config/senior-tv-chrome/Default/Cache/* 2>/dev/null
    systemctl restart senior-tv.service
    ISSUES=$((ISSUES + 1))
fi

# --- 6. Network (gateway) ---
if ! ping -c 1 -W 2 192.168.50.1 > /dev/null 2>&1; then
    log "WARN: Gateway unreachable"
    sleep 5
    if ! ping -c 1 -W 2 192.168.50.1 > /dev/null 2>&1; then
        repair "Restarting NetworkManager (gateway unreachable)"
        systemctl restart NetworkManager
        ISSUES=$((ISSUES + 1))
    fi
fi

# --- 7. Tailscale ---
if command -v tailscale > /dev/null 2>&1; then
    TS_STATE=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('BackendState',''))" 2>/dev/null)
    if [ "$TS_STATE" != "Running" ]; then
        log "FAIL: Tailscale not running (state: $TS_STATE)"
        repair "Restarting tailscaled"
        systemctl restart tailscaled
        ISSUES=$((ISSUES + 1))
    fi
fi

# --- 8. TV Power/Input (via Home Assistant) ---
# DISABLED: Samsung MU6100 HA integration's "HDMI" source maps to Samsung TV+,
# not the physical HDMI2 port. No way to select a specific HDMI port via HA API
# on this model. Needs CEC adapter or newer Samsung TV for reliable input control.
# Power on still works — just can't select the correct input.
HOUR=$(date +%H)
if [ "$HOUR" -ge 7 ] && [ "$HOUR" -lt 22 ]; then
    cd "$PROJECT_DIR" && source venv/bin/activate && python3 -c "
from cec_control import tv_power_on, tv_get_power_status
status = tv_get_power_status()
if status in ('standby', 'off'):
    tv_power_on()
" 2>/dev/null
fi

# --- Track repair count ---
if [ "$ISSUES" -gt 0 ]; then
    COUNT=$(cat "$REPAIR_COUNT_FILE" 2>/dev/null || echo 0)
    echo $((COUNT + ISSUES)) > "$REPAIR_COUNT_FILE"
fi

# Reset count daily at midnight
HOUR=$(date +%H)
MIN=$(date +%M)
if [ "$HOUR" = "00" ] && [ "$MIN" -lt "5" ]; then
    echo 0 > "$REPAIR_COUNT_FILE"
fi
