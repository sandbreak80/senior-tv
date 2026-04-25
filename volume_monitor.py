#!/usr/bin/env python3
"""Room volume monitor — reads audio from multiple Frigate cameras and averages.

Frigate already runs audio analysis on each camera's RTSP stream (when the
camera has an `audio` role), and exposes `audio_rms` + `audio_dBFS` per camera
in /api/stats. We poll a list of cameras, average the RMS (linear) across
cameras that report usable signal, and log dB + RMS to `volume_logs`.

Why multiple cameras, not living_room: the living_room camera sits right next
to the Sonos soundbar, so its mic picks up the TV output almost directly.
Cameras farther away (dining_room, den) give a better reading of how loud
the TV actually sounds *in the room* as experienced by a viewer on the couch.
"""

import math
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INTERVAL = 1.0  # seconds between samples (one row per second)
DEFAULT_CAMERAS = "dining_room,den"

# Frigate's /api/stats endpoint caches values for ~1 second — sub-second polling
# returns identical readings. 1 Hz is the practical ceiling for this data path.
# For true sub-second precision we'd need to pull RTSP audio directly via ffmpeg.


def _get_frigate_url():
    from models import get_setting

    url = (get_setting("frigate_url") or "").rstrip("/")
    return url or None


def _get_volume_cameras():
    from models import get_setting

    raw = get_setting("frigate_volume_cameras") or DEFAULT_CAMERAS
    return [c.strip() for c in raw.split(",") if c.strip()]


def measure_volume_from_frigate(frigate_url, cameras):
    """Poll Frigate /api/stats once, average audio RMS across `cameras`.

    Returns (rms, db_level, per_camera_dict) where per_camera_dict maps
    camera name -> its own dBFS reading (for debug logging). If none of
    the cameras report usable audio, returns (None, None, {}).
    """
    try:
        resp = requests.get(f"{frigate_url}/api/stats", timeout=5)
        if not resp.ok:
            return None, None, {}
        cams = resp.json().get("cameras", {})
    except Exception:
        return None, None, {}

    per_cam = {}
    rms_values = []
    for name in cameras:
        cam = cams.get(name)
        if not cam:
            continue
        rms = cam.get("audio_rms")
        db = cam.get("audio_dBFS")
        if rms is None or db is None:
            continue
        # Frigate reports 0.0/0.0 when the audio role isn't wired up or stream
        # dropped — skip that camera rather than averaging zeros in.
        if rms == 0.0 and db == 0.0:
            continue
        rms_values.append(float(rms))
        per_cam[name] = round(float(db), 1)

    if not rms_values:
        return None, None, per_cam

    avg_rms = sum(rms_values) / len(rms_values)
    # Convert averaged RMS to dBFS. Frigate's dBFS reference is 32768 (int16 full-scale);
    # we replicate that so the new numbers are directly comparable to historical data
    # from the old USB-mic-based volume_monitor.
    if avg_rms > 0:
        db_level = 20 * math.log10(avg_rms / 32768)
    else:
        db_level = -96.0
    return round(avg_rms, 1), round(db_level, 1), per_cam


def get_speaker_volume():
    """Read current speaker volume (0.0-1.0) from Home Assistant media_player entity."""
    try:
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

    cameras = _get_volume_cameras()
    frigate_url = _get_frigate_url()
    if not frigate_url:
        print("Volume monitor: frigate_url not configured, exiting", file=sys.stderr)
        return
    print(
        f"Volume monitor started (frigate={frigate_url} cameras={cameras})",
        file=sys.stderr,
    )

    missing_streak = 0
    while True:
        try:
            rms, db_level, per_cam = measure_volume_from_frigate(
                frigate_url, cameras
            )
            if rms is None:
                missing_streak += 1
                if missing_streak in (1, 6, 60):
                    print(
                        f"Volume monitor: no audio data from any of {cameras} "
                        f"(streak={missing_streak})",
                        file=sys.stderr,
                    )
            else:
                missing_streak = 0
                speaker_vol = get_speaker_volume()
                store(rms, db_level, speaker_vol)
                vol_pct = (
                    f"{int(speaker_vol * 100)}%" if speaker_vol is not None else "?"
                )
                detail = " ".join(f"{k}={v}" for k, v in per_cam.items())
                print(
                    f"AVG dB: {db_level:>6.1f}  RMS: {rms:>7.1f}  "
                    f"Speaker: {vol_pct}  [{detail}]",
                    file=sys.stderr,
                )
        except Exception as e:
            try:
                import cache
                cache.log_throttled(
                    "volume_monitor:loop", f"Volume monitor error: {e}"
                )
            except Exception:
                print(f"Volume monitor error: {e}", file=sys.stderr)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
