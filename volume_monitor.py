#!/usr/bin/env python3
"""Room volume monitor — records 1-second average volume every 10 seconds via webcam mic."""

import math
import struct
import subprocess
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RATE = 16000
DURATION = 1  # 1-second sample
INTERVAL = 10  # every 10 seconds


def _detect_mic_device():
    """Auto-detect the best USB microphone ALSA device.

    Prefers webcam mics (C920, etc.) over generic USB audio adapters,
    since webcams pick up room audio while USB HID devices may be silent.
    """
    try:
        result = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5
        )
        usb_cards = []
        for line in result.stdout.splitlines():
            if "card" not in line:
                continue
            card = line.split(":")[0].replace("card", "").strip()
            name = line.upper()
            if "WEBCAM" in name or "C920" in name or "C930" in name or "C922" in name:
                return f"plughw:{card},0"  # prefer webcam mic
            if "USB" in name:
                usb_cards.append(card)
        if usb_cards:
            return f"plughw:{usb_cards[-1]},0"  # last USB card (usually the webcam)
    except Exception:
        pass
    return "plughw:0,0"


def measure_volume(device):
    """Record 1 second from the webcam mic and return (rms, db_level)."""
    proc = subprocess.run(
        [
            "arecord",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-r",
            str(RATE),
            "-c",
            "1",
            "-d",
            str(DURATION),
            "-t",
            "raw",
            "-q",
        ],
        capture_output=True,
        timeout=5,
    )
    if proc.returncode != 0:
        return None, None

    raw = proc.stdout
    if len(raw) < 2:
        return None, None

    n_samples = len(raw) // 2
    samples = struct.unpack(f"<{n_samples}h", raw[: n_samples * 2])
    rms = math.sqrt(sum(s * s for s in samples) / n_samples)
    db_level = 20 * math.log10(rms / 32768) if rms > 0 else -96.0
    return round(rms, 1), round(db_level, 1)


def get_speaker_volume():
    """Read current speaker volume (0.0-1.0) from Home Assistant media_player entity."""
    try:
        import requests
        from models import get_setting

        ha_url = get_setting("ha_url")
        ha_token = get_setting("ha_token")
        entity = get_setting("ha_speaker_entity") or ""
        if not ha_url or not ha_token or not entity:
            return None
        r = requests.get(
            f"{ha_url}/api/states/{entity}",
            headers={"Authorization": f"Bearer {ha_token}"},
            timeout=3,
        )
        data = r.json()
        vol = data.get("attributes", {}).get("volume_level")
        return round(vol, 2) if vol is not None else None
    except Exception:
        return None


def store(rms, db_level, sonos_volume):
    from models import get_db_safe

    with get_db_safe() as db:
        db.execute(
            "INSERT INTO volume_logs (rms, db_level, sonos_volume) VALUES (?, ?, ?)",
            (rms, db_level, sonos_volume),
        )
        db.commit()


def main():
    from models import init_db

    init_db()

    mic_device = _detect_mic_device()
    print(f"Volume monitor started (mic: {mic_device})", file=sys.stderr)

    while True:
        try:
            rms, db_level = measure_volume(mic_device)
            if rms is not None:
                speaker_vol = get_speaker_volume()
                store(rms, db_level, speaker_vol)
                vol_pct = (
                    f"{int(speaker_vol * 100)}%" if speaker_vol is not None else "?"
                )
                print(
                    f"RMS: {rms:>8.1f}  dB: {db_level:>6.1f}  Speaker: {vol_pct}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Volume monitor error: {e}", file=sys.stderr)
        time.sleep(INTERVAL - DURATION)


if __name__ == "__main__":
    main()
