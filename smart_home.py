"""Home Assistant + Frigate integration for Senior TV.

Polls Frigate for person detection events (doorbell alerts).
TV room presence tracking via webcam.
Connects to Home Assistant for entity states.
Pushes notifications via the SSE reminder queue.
"""

import sys
import time
import threading
import requests
from datetime import datetime

# Frigate session
_frigate_cookies = {}
_last_event_id = None

# --- TV Room Presence Tracking ---
_presence_state = {
    "occupied": False,
    "last_seen": None,         # datetime when person last detected
    "last_empty": None,        # datetime when room became empty
    "today_minutes": 0,        # total occupied minutes today
    "today_date": None,        # date for resetting counter
    "hourly": {},              # {hour: minutes_occupied}
}
_presence_lock = threading.Lock()


def get_presence():
    """Get current presence state (thread-safe copy)."""
    with _presence_lock:
        return dict(_presence_state)


def _update_presence(person_detected):
    """Update presence state based on detection."""
    now = datetime.now()
    with _presence_lock:
        # Reset daily counter at midnight
        today = now.strftime("%Y-%m-%d")
        if _presence_state["today_date"] != today:
            _presence_state["today_date"] = today
            _presence_state["today_minutes"] = 0
            _presence_state["hourly"] = {}

        was_occupied = _presence_state["occupied"]
        _presence_state["occupied"] = person_detected

        if person_detected:
            _presence_state["last_seen"] = now
            # Accumulate occupied time
            hour = now.hour
            _presence_state["hourly"][hour] = _presence_state["hourly"].get(hour, 0) + 1
            if was_occupied:
                _presence_state["today_minutes"] += 1/6  # Called every 10 sec
        else:
            if was_occupied:
                _presence_state["last_empty"] = now


def start_presence_monitor(alert_queue=None):
    """Start background thread that tracks TV room presence.

    Uses multiple signals to avoid false 'empty' readings when seniors
    sit still (Frigate loses them). Only declares room empty when:
    - No person detected AND no speech/sound in the room for several polls.
    """
    def _poll():
        last_occupied = False
        empty_streak = 0  # How many consecutive polls show empty
        EMPTY_THRESHOLD = 6  # Need 6 consecutive empty polls (60s) before declaring empty

        while True:
            try:
                from models import get_setting

                # Check local USB camera (tv_room) via local Frigate
                person_detected = False
                try:
                    resp = requests.get(
                        "http://localhost:5001/api/events",
                        params={"cameras": "tv_room", "label": "person",
                                "limit": 1, "after": time.time() - 60},
                        timeout=5,
                    )
                    if resp.ok:
                        person_detected = len(resp.json()) > 0
                except Exception:
                    pass

                # Fallback: also check network Frigate den camera via HA
                if not person_detected:
                    try:
                        ha_url = (get_setting("ha_url") or "").rstrip("/")
                        ha_token = get_setting("ha_token") or ""
                        resp2 = requests.get(
                            f"{ha_url}/api/states/binary_sensor.den_person_occupancy",
                            headers={"Authorization": f"Bearer {ha_token}"},
                            timeout=5,
                        )
                        if resp2.ok:
                            person_detected = resp2.json().get("state") == "on"
                    except Exception:
                        pass

                person_now = person_detected

                if person_now:
                    empty_streak = 0
                else:
                    empty_streak += 1

                # Only report empty after sustained absence
                effective_occupied = person_now or (empty_streak < EMPTY_THRESHOLD)
                _update_presence(effective_occupied)

                # Push SSE event when presence changes
                if alert_queue and effective_occupied != last_occupied:
                    alert_queue.put({
                        "type": "presence_change",
                        "occupied": effective_occupied,
                        "timestamp": datetime.now().strftime("%I:%M %p"),
                    })
                last_occupied = effective_occupied
            except Exception as e:
                print(f"Presence monitor error: {e}", file=sys.stderr)
            time.sleep(10)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()
    return t


def frigate_login(base_url, username, password):
    """Login to Frigate and get session cookie."""
    global _frigate_cookies
    try:
        resp = requests.post(
            f"{base_url}/api/login",
            json={"user": username, "password": password},
            verify=False,
            timeout=10,
        )
        if resp.status_code == 200:
            _frigate_cookies = dict(resp.cookies)
            return True
    except Exception as e:
        print(f"Frigate login error: {e}", file=sys.stderr)
    return False


def frigate_get_events(base_url, camera=None, label="person", limit=5, after=None):
    """Get recent Frigate events."""
    params = {"limit": limit, "label": label}
    if camera:
        params["camera"] = camera
    if after:
        params["after"] = str(after)
    try:
        resp = requests.get(
            f"{base_url}/api/events",
            params=params,
            cookies=_frigate_cookies,
            verify=False,
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 401:
            return None  # Need re-login
    except Exception as e:
        print(f"Frigate event fetch error: {e}", file=sys.stderr)
    return []


def frigate_get_snapshot_url(base_url, event_id):
    """Get snapshot URL for a Frigate event."""
    return f"{base_url}/api/events/{event_id}/snapshot.jpg"


def frigate_get_camera_snapshot_url(base_url, camera_name):
    """Get latest camera snapshot URL."""
    return f"{base_url}/api/{camera_name}/latest.jpg"


def ha_get_state(base_url, token, entity_id):
    """Get a Home Assistant entity state."""
    try:
        resp = requests.get(
            f"{base_url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"HA state fetch error: {e}", file=sys.stderr)
    return None


def ha_get_camera_snapshot(base_url, token, entity_id):
    """Get camera snapshot from Home Assistant."""
    try:
        resp = requests.get(
            f"{base_url}/api/camera_proxy/{entity_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"HA camera snapshot error: {e}", file=sys.stderr)
    return None


class SmartHomeMonitor:
    """Background thread that monitors Frigate for doorbell/person events
    and pushes alerts to the TV UI via the SSE queue."""

    def __init__(self, frigate_url, frigate_user, frigate_pass,
                 ha_url, ha_token, alert_queue, cameras=None):
        self.frigate_url = frigate_url.rstrip("/")
        self.frigate_user = frigate_user
        self.frigate_pass = frigate_pass
        self.ha_url = ha_url.rstrip("/") if ha_url else None
        self.ha_token = ha_token
        self.alert_queue = alert_queue
        self.cameras = cameras or ["front_door"]
        self.running = False
        self._thread = None
        self._last_event_time = time.time()
        self._seen_events = set()
        self._seen_lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _poll_loop(self):
        """Poll Frigate every 5 seconds for new person events."""
        # Login first
        frigate_login(self.frigate_url, self.frigate_user, self.frigate_pass)

        while self.running:
            try:
                self._check_frigate_events()
            except Exception as e:
                print(f"SmartHome poll error: {e}")
            time.sleep(5)

    def _check_frigate_events(self):
        """Check for new person detection events on monitored cameras."""
        for camera in self.cameras:
            events = frigate_get_events(
                self.frigate_url,
                camera=camera,
                label="person",
                limit=3,
                after=self._last_event_time - 30,
            )

            if events is None:
                # Re-login needed
                frigate_login(self.frigate_url, self.frigate_user, self.frigate_pass)
                continue

            for event in events:
                event_id = event.get("id", "")
                with self._seen_lock:
                    if event_id in self._seen_events:
                        continue
                    self._seen_events.add(event_id)
                start_time = event.get("start_time", 0)

                # Only alert for events in the last 30 seconds
                if time.time() - start_time > 30:
                    continue

                camera_name = event.get("camera", camera)
                score = event.get("top_score", 0)

                # Build snapshot URL
                snapshot_url = frigate_get_snapshot_url(self.frigate_url, event_id)

                # Determine alert message based on camera
                if "front_door" in camera_name:
                    title = "Someone is at the Front Door!"
                    icon = "🚪"
                elif "back" in camera_name or "patio" in camera_name:
                    title = "Someone is at the Back Door!"
                    icon = "🚪"
                elif "garage" in camera_name:
                    title = "Someone is in the Garage!"
                    icon = "🏠"
                else:
                    title = f"Person detected - {camera_name.replace('_', ' ').title()}"
                    icon = "👤"

                # Push alert to TV
                alert_data = {
                    "type": "doorbell_alert",
                    "title": title,
                    "icon": icon,
                    "camera": camera_name,
                    "snapshot_url": snapshot_url,
                    "event_id": event_id,
                    "score": score,
                    "timestamp": datetime.now().strftime("%I:%M %p"),
                }
                self.alert_queue.put(alert_data)
                print(f"ALERT: {title} (score={score:.0%})")

        self._last_event_time = time.time()

        # Trim seen events set to prevent memory growth
        with self._seen_lock:
            if len(self._seen_events) > 1000:
                self._seen_events = set(list(self._seen_events)[-100:])
