"""Home Assistant + Frigate integration for Senior TV.

Presence tracking hierarchy:
  1. Frigate via HA — person count + face recognition (living room camera)
  2. USB webcam + MobileNet SSD — local fallback (~100MB RAM)
  3. HA binary sensor — last resort fallback

Pushes presence changes and doorbell alerts via the SSE reminder queue.
"""

import os  # noqa: F401 — used in start_presence_monitor
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
    "person_count": 0,
    "who": [],  # list of recognized face names
    "last_seen": None,  # datetime when person last detected
    "last_empty": None,  # datetime when room became empty
    "source": None,  # "frigate", "webcam", or "ha_sensor"
    "sound_level": None,  # dB from Frigate audio
    "today_minutes": 0,
    "today_date": None,
    "hourly": {},
}
_presence_lock = threading.Lock()

# --- Movement Tracking ---
# Maps person entity → (display_name, last known room)
_TRACKED_PEOPLE = {
    "sensor.frigate_donald_fenrich_last_camera": "Donald",
    "sensor.frigate_colleen_fenrich_last_camera": "Colleen",
}
_last_known_rooms = {}  # person_name → room_name
_movement_lock = threading.Lock()


def get_tracked_locations():
    """Get current room for each tracked person (thread-safe copy)."""
    with _movement_lock:
        return dict(_last_known_rooms)


_tv_power_state = {"on": False, "last_on": None, "last_off": None}
_tv_power_lock = threading.Lock()


def get_tv_power():
    """Get current TV power state (thread-safe copy)."""
    with _tv_power_lock:
        return dict(_tv_power_state)


def start_movement_tracker(ha_url=None, ha_token=None):
    """Start background thread that polls Frigate face sensors for room changes
    and monitors TV power state for wake/sleep tracking.

    Logs transitions to movement_logs when a person moves between rooms.
    TV power on = wake time, TV power off = sleep time.
    Computes daily activity summaries at end of each day.
    """

    def _track():
        last_day = None
        last_tv_state = None

        while True:
            try:
                from models import get_setting

                url = ha_url or (get_setting("ha_url") or "").rstrip("/")
                token = ha_token or get_setting("ha_token") or ""
                if not url or not token:
                    time.sleep(30)
                    continue

                # --- Track TV power for wake/sleep ---
                tv_entity = get_setting(
                    "ha_tv_entity", "media_player.samsung_tv"
                )
                tv_state = _ha_get_state(url, token, tv_entity)
                if tv_state:
                    tv_on = tv_state.get("state") not in (
                        "off", "standby", "unavailable",
                    )
                    now = datetime.now()
                    today = now.strftime("%Y-%m-%d")

                    with _tv_power_lock:
                        if tv_on and not _tv_power_state["on"]:
                            # TV turned on — wake time
                            _tv_power_state["on"] = True
                            _tv_power_state["last_on"] = now
                            wake_str = now.strftime("%H:%M")
                            print(
                                f"TV ON — wake time: {wake_str}",
                                file=sys.stderr,
                            )
                            try:
                                from models import upsert_daily_activity
                                upsert_daily_activity(
                                    "household", today,
                                    wake_time=wake_str,
                                )
                            except Exception as e:
                                print(
                                    f"Wake log error: {e}",
                                    file=sys.stderr,
                                )

                        elif not tv_on and _tv_power_state["on"]:
                            # TV turned off — sleep time
                            _tv_power_state["on"] = False
                            _tv_power_state["last_off"] = now
                            sleep_str = now.strftime("%H:%M")
                            print(
                                f"TV OFF — sleep time: {sleep_str}",
                                file=sys.stderr,
                            )
                            try:
                                from models import upsert_daily_activity
                                # Compute active minutes
                                active = 0
                                if _tv_power_state["last_on"]:
                                    delta = now - _tv_power_state[
                                        "last_on"
                                    ]
                                    active = int(
                                        delta.total_seconds() / 60
                                    )
                                upsert_daily_activity(
                                    "household", today,
                                    sleep_time=sleep_str,
                                    active_minutes=active,
                                )
                            except Exception as e:
                                print(
                                    f"Sleep log error: {e}",
                                    file=sys.stderr,
                                )

                        # Initialize state on first poll
                        if last_tv_state is None:
                            _tv_power_state["on"] = tv_on
                    last_tv_state = tv_on

                # --- Track room-to-room movement ---
                for entity_id, person_name in _TRACKED_PEOPLE.items():
                    state = _ha_get_state(url, token, entity_id)
                    if not state:
                        continue

                    current_room = state.get("state", "")
                    if current_room in ("unavailable", "unknown", ""):
                        continue

                    with _movement_lock:
                        prev_room = _last_known_rooms.get(person_name)
                        if current_room != prev_room:
                            _last_known_rooms[person_name] = current_room
                            if prev_room is not None:
                                try:
                                    from models import log_movement
                                    log_movement(
                                        person_name,
                                        prev_room,
                                        current_room,
                                    )
                                except Exception as e:
                                    print(
                                        f"Movement log error: {e}",
                                        file=sys.stderr,
                                    )

                # End-of-day summary computation
                today = datetime.now().strftime("%Y-%m-%d")
                if last_day and last_day != today:
                    _compute_day_summary(last_day)
                last_day = today

            except Exception as e:
                print(f"Movement tracker error: {e}", file=sys.stderr)
            time.sleep(10)

    t = threading.Thread(target=_track, daemon=True)
    t.start()
    print("Movement tracker started", file=sys.stderr)
    return t


def _compute_day_summary(day):
    """Compute and store daily activity summaries for all tracked people."""
    from models import compute_daily_activity, upsert_daily_activity

    for person_name in _TRACKED_PEOPLE.values():
        try:
            metrics = compute_daily_activity(person_name, day)
            if metrics:
                upsert_daily_activity(person_name, day, **metrics)
                print(
                    f"Daily summary: {person_name} {day} — "
                    f"{metrics['transition_count']} transitions, "
                    f"kitchen={metrics['kitchen_trips']}, "
                    f"wake={metrics['wake_time']}, "
                    f"sleep={metrics['sleep_time']}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                f"Daily summary error ({person_name}): {e}",
                file=sys.stderr,
            )


def get_presence():
    """Get current presence state (thread-safe copy)."""
    with _presence_lock:
        return dict(_presence_state)


def _update_presence(occupied, person_count=0, who=None,
                     source=None, sound_level=None):
    """Update presence state based on detection."""
    now = datetime.now()
    with _presence_lock:
        today = now.strftime("%Y-%m-%d")
        if _presence_state["today_date"] != today:
            _presence_state["today_date"] = today
            _presence_state["today_minutes"] = 0
            _presence_state["hourly"] = {}

        was_occupied = _presence_state["occupied"]
        _presence_state["occupied"] = occupied
        _presence_state["person_count"] = person_count
        _presence_state["who"] = who or []
        if source:
            _presence_state["source"] = source
        if sound_level is not None:
            _presence_state["sound_level"] = sound_level

        if occupied:
            _presence_state["last_seen"] = now
            hour = now.hour
            _presence_state["hourly"][hour] = (
                _presence_state["hourly"].get(hour, 0) + 1
            )
            if was_occupied:
                _presence_state["today_minutes"] += 1 / 6  # every 10s
        else:
            if was_occupied:
                _presence_state["last_empty"] = now


def _ha_get_state(ha_url, ha_token, entity_id):
    """Get a single HA entity state. Returns parsed JSON or None."""
    try:
        resp = requests.get(
            f"{ha_url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {ha_token}"},
            timeout=5,
        )
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return None


def _poll_frigate_presence(ha_url, ha_token, room="living_room"):
    """Query Frigate entities via HA for room presence.

    Returns (person_count, who_list, sound_level) or None if HA unavailable.
    """
    if not ha_url or not ha_token:
        return None

    # Person count from Frigate
    count_entity = f"sensor.{room}_person_count"
    state = _ha_get_state(ha_url, ha_token, count_entity)
    if state is None:
        return None

    try:
        person_count = int(state.get("state", 0))
    except (ValueError, TypeError):
        person_count = 0

    # Face recognition — only check when people are present
    who = []
    if person_count > 0:
        room_title = room.replace("_", " ").title()
        for name_entity in [
            "sensor.frigate_donald_fenrich_last_camera",
            "sensor.frigate_colleen_fenrich_last_camera",
        ]:
            face_state = _ha_get_state(ha_url, ha_token, name_entity)
            if face_state and face_state.get("state") == room_title:
                name = name_entity.split("frigate_")[1].split("_")[0].title()
                who.append(name)

    # Sound level
    sound_level = None
    sound_state = _ha_get_state(
        ha_url, ha_token, f"sensor.{room}_sound_level"
    )
    if sound_state:
        try:
            sound_level = float(sound_state.get("state", 0))
        except (ValueError, TypeError):
            pass

    return person_count, who, sound_level


def _poll_webcam():
    """Fallback: detect people via USB webcam + MobileNet SSD.

    Returns (person_count, confidence) or None if unavailable.
    """
    try:
        import cv2
        import tempfile
        from person_detector import (
            capture_frame,
            count_persons,
            detect_person,
            detect_video_device,
        )

        model_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "models"
        )
        prototxt = os.path.join(model_dir, "MobileNetSSD_deploy.prototxt")
        caffemodel = os.path.join(model_dir, "MobileNetSSD_deploy.caffemodel")
        if not os.path.exists(prototxt) or not os.path.exists(caffemodel):
            return None

        net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
        device = detect_video_device() or "/dev/video0"
        frame_path = os.path.join(
            tempfile.gettempdir(), "presence_frame.jpg"
        )

        if capture_frame(device, frame_path):
            detected, confidence, all_dets = detect_person(net, frame_path)
            return count_persons(all_dets), confidence
    except Exception as e:
        print(f"Presence: webcam detection failed: {e}", file=sys.stderr)
    return None


def start_presence_monitor(alert_queue=None):
    """Start background thread that tracks TV room presence.

    Priority:
      1. Frigate person count + face recognition via HA
      2. USB webcam + MobileNet SSD
      3. HA binary occupancy sensor
    """

    def _poll():
        last_occupied = False
        empty_streak = 0
        EMPTY_THRESHOLD = 6  # 6 consecutive empty polls (60s)

        # Check if Frigate/HA is available on first poll
        frigate_available = False
        webcam_available = False

        while True:
            try:
                from models import get_setting

                ha_url = (get_setting("ha_url") or "").rstrip("/")
                ha_token = get_setting("ha_token") or ""
                enabled = get_setting("presence_enabled", "1")
                if enabled != "1":
                    time.sleep(10)
                    continue

                person_count = 0
                who = []
                sound_level = None
                source = None

                # 1. Try Frigate via HA
                result = _poll_frigate_presence(ha_url, ha_token)
                if result is not None:
                    person_count, who, sound_level = result
                    source = "frigate"
                    if not frigate_available:
                        print(
                            "Presence monitor: using Frigate via HA",
                            file=sys.stderr,
                        )
                        frigate_available = True
                else:
                    # 2. Try USB webcam
                    webcam_result = _poll_webcam()
                    if webcam_result is not None:
                        person_count, _ = webcam_result
                        source = "webcam"
                        if not webcam_available:
                            print(
                                "Presence monitor: Frigate unavailable,"
                                " using USB webcam",
                                file=sys.stderr,
                            )
                            webcam_available = True
                    else:
                        # 3. Last resort: HA binary sensor
                        occ = _ha_get_state(
                            ha_url, ha_token,
                            "binary_sensor.living_room_person_occupancy",
                        )
                        if occ and occ.get("state") == "on":
                            person_count = 1
                        source = "ha_sensor"

                person_now = person_count > 0

                if person_now:
                    empty_streak = 0
                else:
                    empty_streak += 1

                effective_occupied = person_now or (
                    empty_streak < EMPTY_THRESHOLD
                )
                _update_presence(
                    effective_occupied,
                    person_count=person_count,
                    who=who,
                    source=source,
                    sound_level=sound_level,
                )

                # Log to DB every 5 minutes (not every 10s poll)
                from models import log_presence
                if not hasattr(_poll, "_last_db_log"):
                    _poll._last_db_log = 0
                now_ts = time.time()
                if now_ts - _poll._last_db_log >= 300:
                    try:
                        log_presence(
                            person_count=person_count,
                            max_confidence=0.0,
                            who_detected=",".join(who) if who else None,
                            source=source,
                            sound_level=sound_level,
                        )
                        _poll._last_db_log = now_ts
                    except Exception as e:
                        print(f"Presence DB log error: {e}", file=sys.stderr)

                # Push SSE event when presence changes
                if alert_queue and effective_occupied != last_occupied:
                    try:
                        alert_queue.put_nowait({
                            "type": "presence_change",
                            "occupied": effective_occupied,
                            "person_count": person_count,
                            "who": who,
                            "timestamp": datetime.now().strftime(
                                "%I:%M %p"
                            ),
                        })
                    except Exception:
                        pass
                last_occupied = effective_occupied
            except Exception as e:
                print(f"Presence monitor error: {e}", file=sys.stderr)
            time.sleep(10)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()
    return t


# --- Frigate Event Monitoring (doorbell alerts) ---

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


def frigate_get_events(base_url, camera=None, label="person",
                       limit=5, after=None):
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
            return None
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
    """Get a Home Assistant entity state (public API)."""
    return _ha_get_state(base_url, token, entity_id)


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

    def __init__(
        self,
        frigate_url,
        frigate_user,
        frigate_pass,
        ha_url,
        ha_token,
        alert_queue,
        cameras=None,
    ):
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
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True
        )
        self._thread.start()

    def stop(self):
        self.running = False

    def _poll_loop(self):
        """Poll Frigate every 5 seconds for new person events."""
        if self.frigate_user and self.frigate_pass:
            frigate_login(
                self.frigate_url, self.frigate_user, self.frigate_pass
            )

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
                if self.frigate_user and self.frigate_pass:
                    frigate_login(
                        self.frigate_url,
                        self.frigate_user,
                        self.frigate_pass,
                    )
                continue

            for event in events:
                event_id = event.get("id", "")
                with self._seen_lock:
                    if event_id in self._seen_events:
                        continue
                    self._seen_events.add(event_id)
                start_time = event.get("start_time", 0)

                if time.time() - start_time > 30:
                    continue

                camera_name = event.get("camera", camera)
                score = (
                    event.get("top_score")
                    or event.get("data", {}).get("score", 0)
                    or 0
                )

                snapshot_url = frigate_get_snapshot_url(
                    self.frigate_url, event_id
                )

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
                    title = (
                        f"Person detected - "
                        f"{camera_name.replace('_', ' ').title()}"
                    )
                    icon = "👤"

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
                try:
                    self.alert_queue.put_nowait(alert_data)
                except Exception:
                    pass
                print(f"ALERT: {title} (score={score:.0%})")

        self._last_event_time = time.time()

        with self._seen_lock:
            if len(self._seen_events) > 1000:
                trim = list(self._seen_events)[:500]
                self._seen_events = set(trim)
