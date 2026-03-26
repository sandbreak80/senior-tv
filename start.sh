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

# Fix audio routing on startup
bash fix_audio.sh 2>/dev/null

# TV input switching disabled — Samsung MU6100 "HDMI" source unreliable
# Re-enable after Roku is unplugged. See ROADMAP.md Known Limitations.
# python3 -c "from cec_control import tv_power_on, tv_set_input; tv_power_on(); tv_set_input()" 2>/dev/null &

# --- Process PIDs ---
CEC_PID=0
SERVER_PID=0
CHROME_PID=0
RUNNING=true

cleanup() {
    RUNNING=false
    kill $CEC_PID $SERVER_PID $CHROME_PID 2>/dev/null
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
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-translate \
        --no-first-run \
        --start-fullscreen \
        --autoplay-policy=no-user-gesture-required \
        --password-store=basic \
        --user-data-dir=/home/media/.config/senior-tv-chrome \
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
done
