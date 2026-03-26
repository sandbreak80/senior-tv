#!/usr/bin/env python3
"""CEC Bridge - Translates HDMI-CEC remote button presses to keyboard events.

Listens to cec-client output and uses xdotool to inject key presses.
This allows a Samsung TV remote to control the Chrome kiosk browser.

Tries kernel CEC (cec-ctl) first, then libCEC (cec-client).
Exits gracefully if no CEC hardware is available.

Usage: python3 cec_bridge.py
"""

import os
import subprocess
import sys
import signal
import re
import time

# CEC key code to X keyboard key mapping
CEC_KEY_MAP = {
    "00": "Return",      # Select -> OK
    "01": "Up",          # Up
    "02": "Down",        # Down
    "03": "Left",        # Left
    "04": "Right",       # Right
    "09": "Escape",      # Root Menu -> go back
    "0a": "Escape",      # Setup Menu -> go back
    "0b": "Escape",      # Contents Menu -> go back
    "0d": "Escape",      # Exit -> go back
    "20": "0",           # Number 0
    "21": "1",           # Number 1
    "22": "2",           # Number 2
    "23": "3",           # Number 3
    "24": "4",           # Number 4
    "25": "5",           # Number 5
    "26": "6",           # Number 6
    "27": "7",           # Number 7
    "28": "8",           # Number 8
    "29": "9",           # Number 9
    "30": "Page_Up",     # Channel Up
    "31": "Page_Down",   # Channel Down
    "41": "space",       # Play
    "44": "Return",      # Play (Samsung)
    "45": "space",       # Pause
    "46": "space",       # Pause (Samsung)
    "43": "Escape",      # Rewind -> Back
    "49": "Escape",      # Fast Forward -> ignore
    "91": "Escape",      # Return/Back (Samsung)
}


def send_key(key_name):
    """Send a keyboard event using xdotool."""
    try:
        subprocess.run(["xdotool", "key", key_name], timeout=2, check=False)
    except Exception as e:
        print(f"xdotool error: {e}", file=sys.stderr)


def try_kernel_cec():
    """Try to use kernel CEC via cec-ctl --monitor. Returns True if it ran."""
    if not os.path.exists("/dev/cec0"):
        return False

    print("Using kernel CEC (/dev/cec0)...")

    # On startup: wake TV and set input
    subprocess.run(["cec-ctl", "--to", "0", "--image-view-on"],
                   timeout=5, check=False, capture_output=True)
    time.sleep(1)
    subprocess.run(["cec-ctl", "--to", "0", "--active-source", "phys-addr=0x1000"],
                   timeout=5, check=False, capture_output=True)

    # Monitor for key events
    # cec-ctl --monitor outputs lines like: "Received from TV to Playback 1: USER_CONTROL_PRESSED (0x44): ..."
    key_pattern = re.compile(r"USER_CONTROL_PRESSED.*?ui-cmd: (.+?) \(0x([0-9a-f]{2})\)")

    proc = subprocess.Popen(
        ["cec-ctl", "--monitor"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )

    def cleanup(sig, frame):
        proc.terminate()
        sys.exit(0)
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    for line in proc.stdout:
        match = key_pattern.search(line)
        if match:
            key_code = match.group(2).lower()
            x_key = CEC_KEY_MAP.get(key_code)
            if x_key:
                print(f"CEC kernel: {match.group(1)} ({key_code}) -> {x_key}")
                send_key(x_key)

    return True


def try_libcec():
    """Fall back to libCEC cec-client (requires USB CEC adapter)."""
    print("Trying libCEC (cec-client)...")

    key_pattern = re.compile(r"key pressed: (\w+) \((\w+)\)")
    traffic_pattern = re.compile(r">> [\da-f]{2}:44:([0-9a-f]{2})")

    try:
        proc = subprocess.Popen(
            ["cec-client", "-d", "8", "-t", "r"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
    except FileNotFoundError:
        print("cec-client not found", file=sys.stderr)
        return False

    # Check if it starts successfully (give it 5 seconds)
    time.sleep(5)
    if proc.poll() is not None:
        print("cec-client exited immediately — no CEC adapter found", file=sys.stderr)
        return False

    def cleanup(sig, frame):
        proc.terminate()
        sys.exit(0)
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        match = key_pattern.search(line)
        if match:
            key_code = match.group(2).lower()
            x_key = CEC_KEY_MAP.get(key_code)
            if x_key:
                print(f"CEC: {match.group(1)} ({key_code}) -> {x_key}")
                send_key(x_key)
            continue

        match = traffic_pattern.search(line)
        if match:
            key_code = match.group(1).lower()
            x_key = CEC_KEY_MAP.get(key_code)
            if x_key:
                print(f"CEC raw: {key_code} -> {x_key}")
                send_key(x_key)

    return True


def run_cec_bridge():
    """Start CEC bridge — tries kernel CEC, then libCEC, then exits gracefully."""
    print("Starting CEC bridge...")

    # Try kernel CEC first (no USB adapter needed)
    if try_kernel_cec():
        return

    # Try libCEC (requires USB CEC adapter)
    if try_libcec():
        return

    # No CEC available — sleep forever so the PID stays alive
    # (prevents start.sh from constantly restarting us)
    print("No CEC hardware available. Bridge idle — will retry on restart.")
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    run_cec_bridge()
