#!/bin/bash
# Fix HDMI audio output — ensure PipeWire routes to Samsung TV
# Called by watchdog.sh and start.sh

export XDG_RUNTIME_DIR=/run/user/1000

# Find the HDMI sink ID (starred = default)
HDMI_SINK=$(wpctl status 2>/dev/null | grep -i "rembrandt.*hdmi\|radeon.*hdmi\|SAMSUNG" | grep -oP '^\s*[*]?\s*\K\d+' | head -1)

if [ -z "$HDMI_SINK" ]; then
    # Broader search for any HDMI sink
    HDMI_SINK=$(pactl list sinks short 2>/dev/null | grep -i "hdmi" | awk '{print $1}' | head -1)
fi

if [ -n "$HDMI_SINK" ]; then
    wpctl set-default "$HDMI_SINK" 2>/dev/null
    wpctl set-volume "$HDMI_SINK" 1.0 2>/dev/null
    wpctl set-mute "$HDMI_SINK" 0 2>/dev/null
    echo "AUDIO_OK: HDMI sink $HDMI_SINK set as default, volume 100%, unmuted"
else
    echo "AUDIO_FAIL: No HDMI sink found"
    exit 1
fi
