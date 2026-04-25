"""System health checks for Senior TV monitoring and watchdog."""

import json
import os
import shutil
import subprocess
from datetime import datetime

import requests

from models import get_setting, get_setting_or_default


def check_all(app_start_time):
    """Run all health checks. Returns the full health dict."""
    health = {
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": int((datetime.now() - app_start_time).total_seconds()),
        "status": "ok",
        "checks": {},
    }

    health["checks"]["disk"] = _check_disk()
    health["checks"]["memory"] = _check_memory()
    health["checks"]["chrome"] = _check_chrome()
    health["checks"]["audio"] = _check_audio()
    health["checks"]["jellyfin"] = _check_jellyfin()
    health["checks"]["internet"] = _check_internet()
    health["checks"]["tailscale"] = _check_tailscale()
    health["checks"]["watchdog"] = _check_watchdog()
    health["checks"]["scheduler"] = _check_scheduler()
    health["checks"]["presence"] = _check_presence()
    _check_immich(health)

    all_ok = all(c.get("ok", True) for c in health["checks"].values())
    health["status"] = "ok" if all_ok else "degraded"
    return health


def _check_disk():
    disk = shutil.disk_usage("/")
    return {
        "used_pct": round(disk.used / disk.total * 100, 1),
        "ok": disk.used / disk.total < 0.9,
    }


def _check_memory():
    import psutil

    mem = psutil.virtual_memory()
    return {"used_pct": mem.percent, "ok": mem.percent < 85}


def _check_chrome():
    import psutil

    running = any(
        "senior-tv-chrome" in " ".join(p.info["cmdline"] or [])
        for p in psutil.process_iter(["cmdline"])
    )
    return {"running": running, "ok": running}


def _check_audio():
    try:
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = "/run/user/1000"
        result = subprocess.run(
            ["wpctl", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        hdmi = False
        for line in result.stdout.split("\n"):
            if "*" in line and ("hdmi" in line.lower() or "rembrandt" in line.lower()):
                hdmi = True
                break
        return {"hdmi_default": hdmi, "ok": hdmi}
    except Exception:
        return {"hdmi_default": False, "ok": False}


def _check_jellyfin():
    try:
        jf_url = get_setting_or_default("jellyfin_url")
        resp = requests.get(f"{jf_url}/System/Ping", timeout=3)
        return {"reachable": resp.ok, "ok": resp.ok}
    except Exception:
        return {"reachable": False, "ok": False}


def _check_internet():
    try:
        requests.get(
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=0&longitude=0&current=temperature_2m",
            timeout=5,
        )
        return {"reachable": True, "ok": True}
    except Exception:
        return {"reachable": False, "ok": False}


def _check_tailscale():
    try:
        ts = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        state = json.loads(ts.stdout).get("BackendState", "")
        return {"state": state, "ok": state == "Running"}
    except Exception:
        return {"state": "unknown", "ok": False}


def _check_watchdog():
    try:
        with open("/tmp/senior_tv_repair_count") as f:
            count = int(f.read().strip())
    except Exception:
        count = 0
    return {"repairs_today": count, "ok": count < 20}


def _check_scheduler():
    from scheduler import scheduler as _sched

    return {"running": _sched.running, "ok": _sched.running}


def _check_presence():
    """Verify TV-room presence detection is sourcing from Frigate, not stuck on fallback.

    Degraded if the last hour of presence_logs contains no Frigate samples — that
    means _poll_frigate_presence() is failing and we're silently running on ha_sensor
    or webcam fallback (or nothing), which hides "someone is watching" from the system.
    """
    from models import get_db_safe

    if (get_setting("presence_enabled") or "1") != "1":
        return {"enabled": False, "ok": True}

    try:
        with get_db_safe() as db:
            rows = db.execute(
                "SELECT source, person_count FROM presence_logs "
                "WHERE datetime(logged_at) > datetime('now','-1 hour') "
                "ORDER BY id DESC LIMIT 20"
            ).fetchall()
    except Exception as e:
        return {"enabled": True, "ok": False, "error": f"{type(e).__name__}: {e}"}

    if not rows:
        return {
            "enabled": True,
            "ok": False,
            "detail": "no presence_logs entries in last hour — monitor thread not running?",
        }

    sources = {}
    for r in rows:
        src = (r["source"] or "unknown") if hasattr(r, "__getitem__") else "unknown"
        sources[src] = sources.get(src, 0) + 1

    primary = max(sources, key=sources.get)
    has_frigate = "frigate" in sources
    return {
        "enabled": True,
        "primary_source": primary,
        "source_counts": sources,
        "recent_samples": len(rows),
        "ok": has_frigate,
        "detail": (
            "Frigate presence active"
            if has_frigate
            else f"stuck on fallback '{primary}' — Frigate→HA chain likely broken"
        ),
    }


def _check_immich(health):
    try:
        import immich_api

        if immich_api.is_configured():
            ok, msg = immich_api.test_connection()
            health["checks"]["immich"] = {
                "connected": ok,
                "detail": msg,
                "ok": ok,
            }
    except Exception:
        pass
