#!/usr/bin/env python3
"""Room volume monitor — records 1-second average volume every 10 seconds via webcam mic."""

import math
import struct
import subprocess
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEVICE = "plughw:1,0"  # C920 webcam mic
RATE = 16000
DURATION = 1  # 1-second sample
INTERVAL = 10  # every 10 seconds
SONOS_ENTITY = "media_player.family_room"


def measure_volume():
    """Record 1 second from the webcam mic and return (rms, db_level)."""
    proc = subprocess.run(
        ["arecord", "-D", DEVICE, "-f", "S16_LE", "-r", str(RATE), "-c", "1",
         "-d", str(DURATION), "-t", "raw", "-q"],
        capture_output=True, timeout=5,
    )
    if proc.returncode != 0:
        return None, None

    raw = proc.stdout
    if len(raw) < 2:
        return None, None

    n_samples = len(raw) // 2
    samples = struct.unpack(f"<{n_samples}h", raw[:n_samples * 2])
    rms = math.sqrt(sum(s * s for s in samples) / n_samples)
    db_level = 20 * math.log10(rms / 32768) if rms > 0 else -96.0
    return round(rms, 1), round(db_level, 1)


def get_sonos_volume():
    """Read current Sonos volume (0.0-1.0) from Home Assistant."""
    try:
        import requests
        from models import get_setting
        ha_url = get_setting("ha_url")
        ha_token = get_setting("ha_token")
        if not ha_url or not ha_token:
            return None
        r = requests.get(
            f"{ha_url}/api/states/{SONOS_ENTITY}",
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
    print("Volume monitor started", file=sys.stderr)
    from models import init_db
    init_db()

    while True:
        try:
            rms, db_level = measure_volume()
            if rms is not None:
                sonos_vol = get_sonos_volume()
                store(rms, db_level, sonos_vol)
                sonos_pct = f"{int(sonos_vol * 100)}%" if sonos_vol is not None else "?"
                print(f"RMS: {rms:>8.1f}  dB: {db_level:>6.1f}  Sonos: {sonos_pct}", file=sys.stderr)
        except Exception as e:
            print(f"Volume monitor error: {e}", file=sys.stderr)
        time.sleep(INTERVAL - DURATION)


if __name__ == "__main__":
    main()
