#!/usr/bin/env python3
"""Lightweight person detection via webcam — replaces Frigate for presence tracking.

Uses MobileNet SSD (23MB) with OpenCV DNN. Grabs one frame every poll interval
via ffmpeg, runs inference (~30ms), and updates presence state.

Resource usage: ~100MB RAM, <1% CPU (one frame every 10s).
Replaces: Frigate (2.7GB RAM, 17 processes, Docker container).
"""

import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
PROTOTXT = os.path.join(MODEL_DIR, "MobileNetSSD_deploy.prototxt")
CAFFEMODEL = os.path.join(MODEL_DIR, "MobileNetSSD_deploy.caffemodel")
DEVICE = "/dev/video0"
CONFIDENCE_THRESHOLD = 0.4
PERSON_CLASS_ID = 15
POLL_INTERVAL = 10  # seconds


def capture_frame(device, output_path):
    """Grab a single frame from the webcam via ffmpeg.

    Uses a short timeout and explicit process cleanup to ensure the V4L2
    device is released before the next poll interval.
    """
    try:
        proc = subprocess.Popen(
            ["ffmpeg", "-f", "v4l2", "-input_format", "mjpeg",
             "-i", device, "-frames:v", "1",
             "-y", "-loglevel", "error", "-update", "1", output_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        proc.wait(timeout=5)
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return False
    except Exception:
        return False


def detect_person(net, image_path):
    """Run MobileNet SSD on an image, return (person_detected, confidence, all_detections)."""
    import cv2

    frame = cv2.imread(image_path)
    if frame is None:
        return False, 0.0, []

    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
    )
    net.setInput(blob)
    detections = net.forward()

    results = []
    best_person_conf = 0.0
    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])
        class_id = int(detections[0, 0, i, 1])
        if confidence > CONFIDENCE_THRESHOLD:
            results.append((class_id, confidence))
            if class_id == PERSON_CLASS_ID and confidence > best_person_conf:
                best_person_conf = confidence

    return best_person_conf > 0, best_person_conf, results


def main():
    import cv2

    print("Person detector starting...", file=sys.stderr)
    net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
    print(f"Model loaded ({os.path.getsize(CAFFEMODEL) // 1024 // 1024}MB)", file=sys.stderr)

    # Use a persistent temp file for frames
    frame_path = os.path.join(tempfile.gettempdir(), "person_detect_frame.jpg")

    consecutive_fails = 0
    while True:
        try:
            if capture_frame(DEVICE, frame_path):
                person, confidence, all_dets = detect_person(net, frame_path)
                print(
                    f"Person: {'YES' if person else 'no ':3s} "
                    f"conf={confidence:.0%}  "
                    f"detections={len(all_dets)}",
                    file=sys.stderr,
                )

                # Update presence state in smart_home module
                try:
                    from smart_home import _update_presence
                    _update_presence(person)
                except ImportError:
                    pass

                consecutive_fails = 0
            else:
                consecutive_fails += 1
                if consecutive_fails <= 3 or consecutive_fails % 30 == 0:
                    print(
                        f"Frame capture failed ({consecutive_fails} consecutive)",
                        file=sys.stderr,
                    )
        except Exception as e:
            print(f"Person detector error: {e}", file=sys.stderr)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
