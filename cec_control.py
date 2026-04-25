"""CEC / TV control for Senior TV.

Tries native kernel CEC first (/dev/cec0), falls back to Home Assistant
Samsung TV integration for power on/off and input switching.
"""

import os
import subprocess

import requests
import cache

_BRK_HA = "home_assistant"


def _cec_available():
    """Check if kernel CEC device exists."""
    return os.path.exists("/dev/cec0")


def _cec_cmd(*args):
    """Run a cec-ctl command with standard options."""
    return subprocess.run(
        ["cec-ctl", "--to", "0", *args],
        timeout=5,
        check=False,
        capture_output=True,
        text=True,
    )


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
    if cache.is_circuit_open(_BRK_HA):
        return False
    try:
        resp = requests.post(
            f"{cfg['url']}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {cfg['token']}"},
            json=data or {},
            timeout=10,
        )
        if resp.ok:
            cache.record_success(_BRK_HA)
            return True
        cache.record_failure(_BRK_HA, f"HTTP {resp.status_code}")
        cache.log_throttled(
            "ha:service_call",
            f"HA {domain}/{service}: HTTP {resp.status_code}",
        )
        return False
    except Exception as e:
        cache.record_failure(_BRK_HA, e)
        cache.log_throttled(
            "ha:service_call",
            f"HA service call {domain}/{service} error: {e}",
        )
        return False


def tv_power_on():
    """Turn TV on."""
    if _cec_available():
        _cec_cmd("--image-view-on")
        return True
    cfg = _get_ha_config()
    return _ha_call_service("media_player", "turn_on", {"entity_id": cfg["entity"]})


def tv_power_off():
    """Turn TV to standby."""
    if _cec_available():
        _cec_cmd("--standby")
        return True
    cfg = _get_ha_config()
    return _ha_call_service("media_player", "turn_off", {"entity_id": cfg["entity"]})


def tv_set_input():
    """Switch TV to our HDMI input."""
    if _cec_available():
        _cec_cmd("--active-source", "phys-addr=0x1000")
        return True
    cfg = _get_ha_config()
    return _ha_call_service(
        "media_player", "select_source", {"entity_id": cfg["entity"], "source": "HDMI"}
    )


def tv_get_power_status():
    """Query TV power status. Returns 'on', 'standby', or 'unknown'."""
    if _cec_available():
        result = _cec_cmd("--give-device-power-status")
        if "pwr-state: on" in result.stdout:
            return "on"
        if "pwr-state: standby" in result.stdout:
            return "standby"
        return "unknown"
    cfg = _get_ha_config()
    if not cfg["url"] or not cfg["token"]:
        return "unknown"
    if cache.is_circuit_open(_BRK_HA):
        return "unknown"
    try:
        resp = requests.get(
            f"{cfg['url']}/api/states/{cfg['entity']}",
            headers={"Authorization": f"Bearer {cfg['token']}"},
            timeout=5,
        )
        if resp.ok:
            cache.record_success(_BRK_HA)
            state = resp.json().get("state", "unknown")
            return "on" if state in ("playing", "on", "idle") else state
        cache.record_failure(_BRK_HA, f"HTTP {resp.status_code}")
        return "unknown"
    except Exception as e:
        cache.record_failure(_BRK_HA, e)
        cache.log_throttled("ha:power_status", f"HA power status error: {e}")
        return "unknown"


def ensure_tv_ready():
    """Power on TV and set to correct input. Best-effort."""
    try:
        status = tv_get_power_status()
        if status != "on":
            tv_power_on()
        tv_set_input()
    except Exception as e:
        cache.log_throttled("ha:ensure_ready", f"ensure_tv_ready error: {e}")
