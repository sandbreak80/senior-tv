"""CEC / TV control for Senior TV.

Tries native kernel CEC first (/dev/cec0), falls back to Home Assistant
Samsung TV integration for power on/off and input switching.
"""

import os
import sys
import subprocess

import requests


def _cec_available():
    """Check if kernel CEC device exists."""
    return os.path.exists("/dev/cec0")


def _get_ha_config():
    """Read HA config from settings DB."""
    from models import get_setting
    return {
        "url": (get_setting("ha_url") or "").rstrip("/"),
        "token": get_setting("ha_token") or "",
        "entity": get_setting("ha_tv_entity") or "media_player.samsung_tv",
    }


def _ha_call_service(domain, service, data=None):
    cfg = _get_ha_config()
    if not cfg["url"] or not cfg["token"]:
        return False
    try:
        resp = requests.post(
            f"{cfg['url']}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {cfg['token']}"},
            json=data or {},
            timeout=10,
        )
        return resp.ok
    except Exception as e:
        print(f"HA service call {domain}/{service} error: {e}", file=sys.stderr)
        return False


def tv_power_on():
    """Turn TV on."""
    if _cec_available():
        subprocess.run(
            ["cec-ctl", "--to", "0", "--image-view-on"],
            timeout=5, check=False, capture_output=True,
        )
        return True
    cfg = _get_ha_config()
    return _ha_call_service("media_player", "turn_on",
                            {"entity_id": cfg["entity"]})


def tv_power_off():
    """Turn TV to standby."""
    if _cec_available():
        subprocess.run(
            ["cec-ctl", "--to", "0", "--standby"],
            timeout=5, check=False, capture_output=True,
        )
        return True
    cfg = _get_ha_config()
    return _ha_call_service("media_player", "turn_off",
                            {"entity_id": cfg["entity"]})


def tv_set_input():
    """Switch TV to our HDMI input."""
    if _cec_available():
        subprocess.run(
            ["cec-ctl", "--to", "0", "--active-source", "phys-addr=0x1000"],
            timeout=5, check=False, capture_output=True,
        )
        return True
    cfg = _get_ha_config()
    return _ha_call_service("media_player", "select_source",
                            {"entity_id": cfg["entity"], "source": "HDMI"})


def tv_get_power_status():
    """Query TV power status. Returns 'on', 'standby', or 'unknown'."""
    if _cec_available():
        result = subprocess.run(
            ["cec-ctl", "--to", "0", "--give-device-power-status"],
            capture_output=True, text=True, timeout=5,
        )
        if "pwr-state: on" in result.stdout:
            return "on"
        if "pwr-state: standby" in result.stdout:
            return "standby"
        return "unknown"
    cfg = _get_ha_config()
    if not cfg["url"] or not cfg["token"]:
        return "unknown"
    try:
        resp = requests.get(
            f"{cfg['url']}/api/states/{cfg['entity']}",
            headers={"Authorization": f"Bearer {cfg['token']}"},
            timeout=5,
        )
        state = resp.json().get("state", "unknown")
        return "on" if state in ("playing", "on", "idle") else state
    except Exception as e:
        print(f"HA power status error: {e}", file=sys.stderr)
        return "unknown"


def ensure_tv_ready():
    """Power on TV and set to correct input. Best-effort."""
    try:
        status = tv_get_power_status()
        if status != "on":
            tv_power_on()
        tv_set_input()
    except Exception as e:
        print(f"ensure_tv_ready error: {e}", file=sys.stderr)
