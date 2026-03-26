#!/bin/bash
# Stream USB webcam as H.264 RTSP for Frigate person detection
# Reads YUYV from /dev/video0, encodes to H.264, outputs RTSP
# Run as: systemd service or background process

DEVICE="/dev/video0"
WIDTH=640
HEIGHT=480
FPS=10
RTSP_OUT="rtsp://localhost:8554/tv_room_h264"

while true; do
    echo "$(date): Starting webcam stream..."
    ffmpeg -f v4l2 -video_size ${WIDTH}x${HEIGHT} -framerate ${FPS} \
        -i "$DEVICE" \
        -c:v libx264 -preset ultrafast -tune zerolatency \
        -g 20 -bf 0 \
        -f rtsp -rtsp_transport tcp \
        "$RTSP_OUT" 2>&1 | tail -1

    echo "$(date): Stream died, restarting in 5s..."
    sleep 5
done
