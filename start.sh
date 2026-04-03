#!/bin/bash
# Senior TV - Start script with process supervision
# Monitors Flask, Chrome, and CEC bridge; restarts any that die
cd "$(dirname "$0")"

source venv/bin/activate

# Pick up Xwayland auth if running under Wayland
if [ -z "$XAUTHORITY" ]; then
    XAUTH=$(find /run/user/1000/ -name '.mutter-Xwaylandauth.*' 2>/dev/null | head -1)
    [ -n "$XAUTH" ] && export XAUTHORITY="$XAUTH"
fi

# Set display to 1080p — no 4K content, saves GPU/memory, correct font sizes
# Uses Mutter DBus API (works under Wayland), handles either HDMI port
python3 - << 'PYEOF'
import subprocess, re, sys
try:
    r = subprocess.run([
        'gdbus', 'call', '--session',
        '--dest', 'org.gnome.Mutter.DisplayConfig',
        '--object-path', '/org/gnome/Mutter/DisplayConfig',
        '--method', 'org.gnome.Mutter.DisplayConfig.GetCurrentState'
    ], capture_output=True, text=True, env={
        **__import__('os').environ,
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/1000/bus'
    })
    serial = int(re.search(r'\(uint32 (\d+),', r.stdout).group(1))
    # Find connected HDMI output
    connector = re.search(r"'(HDMI-\d+)'", r.stdout).group(1)
    # Check if already 1080p
    if '1920x1080' in r.stdout.split('is-current')[0].split(connector)[-1:][0] if 'is-current' in r.stdout else '':
        pass  # already set
    subprocess.run([
        'gdbus', 'call', '--session',
        '--dest', 'org.gnome.Mutter.DisplayConfig',
        '--object-path', '/org/gnome/Mutter/DisplayConfig',
        '--method', 'org.gnome.Mutter.DisplayConfig.ApplyMonitorsConfig',
        str(serial), '1',  # method 1 = temporary (no confirmation popup); monitors.xml handles persistence
        f'[(0, 0, 1.0, 0, true, [("{connector}", "1920x1080@60.000", {{}})])]',
        '{}'
    ], capture_output=True, text=True, env={
        **__import__('os').environ,
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/1000/bus'
    })
    print(f"Display: {connector} set to 1920x1080@60Hz")
except Exception as e:
    print(f"Display config skipped: {e}", file=sys.stderr)
PYEOF

# Fix audio routing on startup
bash fix_audio.sh 2>/dev/null

# TV automation disabled — device is connected to 65" Samsung, no CEC/HA control needed
# python3 -c "from cec_control import tv_power_on; tv_power_on()" 2>/dev/null &

# --- Process PIDs ---
CEC_PID=0
SERVER_PID=0
CHROME_PID=0
VOLMON_PID=""
RUNNING=true

cleanup() {
    RUNNING=false
    kill $CEC_PID $SERVER_PID $CHROME_PID ${VOLMON_PID:-} 2>/dev/null
    wait 2>/dev/null
}
trap cleanup EXIT INT TERM

start_cec() {
    python3 cec_bridge.py >> /tmp/senior_tv_cec.log 2>&1 &
    CEC_PID=$!
    echo "$(date): CEC bridge started (PID $CEC_PID)"
}

start_server() {
    python3 server.py &
    SERVER_PID=$!
    echo "$(date): Flask server started (PID $SERVER_PID)"
}

start_chrome() {
    # Clear Chrome cache to ensure latest JS/CSS is loaded
    rm -rf $HOME/.config/senior-tv-chrome/Default/Cache 2>/dev/null
    rm -rf $HOME/.config/senior-tv-chrome/Default/Code\ Cache 2>/dev/null

    # Wait for server to respond
    for i in $(seq 1 15); do
        curl -sf http://localhost:5000/ > /dev/null 2>&1 && break
        sleep 1
    done

    # Wait for display
    for i in $(seq 1 30); do
        if xdpyinfo -display :0 >/dev/null 2>&1 || [ -n "$WAYLAND_DISPLAY" ]; then
            break
        fi
        echo "Waiting for display... ($i/30)"
        sleep 2
    done

    google-chrome \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-translate \
        --no-first-run \
        --start-fullscreen \
        --load-extension=$HOME/.config/senior-tv-chrome/ublock-origin \
        --autoplay-policy=no-user-gesture-required \
        --password-store=basic \
        --remote-debugging-port=9222 \
        --remote-allow-origins=* \
        --user-data-dir=$HOME/.config/senior-tv-chrome \
        http://localhost:5000 &
    CHROME_PID=$!
    echo "$(date): Chrome started (PID $CHROME_PID)"
}

# --- Initial startup ---
start_cec
start_server
sleep 3
start_chrome

# --- Supervision loop: check every 10 seconds ---
while $RUNNING; do
    sleep 10

    # Check Flask server
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "$(date): Flask server died, restarting..."
        start_server
        sleep 3
        # Restart Chrome too since it was connected to the old server
        kill $CHROME_PID 2>/dev/null
        start_chrome
    fi

    # Check Chrome
    if ! kill -0 $CHROME_PID 2>/dev/null; then
        echo "$(date): Chrome died, restarting..."
        start_chrome
    fi

    # Check CEC bridge (non-critical)
    if ! kill -0 $CEC_PID 2>/dev/null; then
        start_cec
    fi

    # Check volume monitor (non-critical)
    if [ -z "$VOLMON_PID" ] || ! kill -0 $VOLMON_PID 2>/dev/null; then
        python3 volume_monitor.py >> /tmp/senior_tv_volume.log 2>&1 &
        VOLMON_PID=$!
    fi
done
