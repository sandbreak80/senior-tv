"""Home Assistant + Frigate integration for Senior TV.

Polls Frigate for person detection events (doorbell alerts).
Connects to Home Assistant for entity states.
Pushes notifications via the SSE reminder queue.
"""

import time
import threading
import requests
from datetime import datetime

# Frigate session
_frigate_cookies = {}
_last_event_id = None


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
    except Exception:
        pass
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
    except Exception:
        pass
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
    except Exception:
        pass
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
    except Exception:
        pass
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
