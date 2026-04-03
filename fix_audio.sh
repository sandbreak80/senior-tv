#!/bin/bash
# Fix HDMI audio output — ensure PipeWire routes to the TV via HDMI
# Called by watchdog.sh and start.sh
# Handles either HDMI port (HDMI-1 or HDMI-2) on the K11 mini PC

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# Strategy: find HDMI audio sinks via PipeWire node properties
# Look for any Audio/Sink whose object.path contains "hdmi"
HDMI_SINK=""

# Method 1: Use pw-cli to find HDMI sink by object path
if command -v pw-cli &>/dev/null; then
    HDMI_SINK=$(pw-cli list-objects Node 2>/dev/null | awk '
        /^[[:space:]]*id [0-9]+,/ { id = ""; path = ""; class = "" }
        /object.serial =/ { gsub(/[" ]/, ""); split($0, a, "="); id = a[2] }
        /object.path =/ && /hdmi/ { path = 1 }
        /media.class =/ && /Audio\/Sink/ { class = 1 }
        path && class && id { print id; exit }
    ')
fi

# Method 2: Fallback — search wpctl status output for HDMI/hdmi sinks
if [ -z "$HDMI_SINK" ]; then
    HDMI_SINK=$(wpctl status 2>/dev/null | grep -i "hdmi" | grep -v "^[[:space:]]*├\|^[[:space:]]*└\|^[[:space:]]*│[[:space:]]*$" | grep -oP '^\s*\*?\s*\K\d+' | head -1)
fi

# Method 3: Fallback — search pactl for any HDMI sink
if [ -z "$HDMI_SINK" ]; then
    HDMI_SINK=$(pactl list sinks short 2>/dev/null | grep -i "hdmi" | awk '{print $1}' | head -1)
fi

if [ -n "$HDMI_SINK" ]; then
    wpctl set-default "$HDMI_SINK" 2>/dev/null
    wpctl set-volume "$HDMI_SINK" 1.0 2>/dev/null
    wpctl set-mute "$HDMI_SINK" 0 2>/dev/null
    DESC=$(pw-cli list-objects Node 2>/dev/null | grep -A10 "serial = \"$HDMI_SINK\"" | grep "node.description" | head -1 | sed 's/.*= "//;s/"//')
    echo "AUDIO_OK: HDMI sink $HDMI_SINK ($DESC) set as default, volume 100%, unmuted"
else
    echo "AUDIO_FAIL: No HDMI sink found"
    exit 1
fi
