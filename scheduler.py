import json
import sys
import queue
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from models import get_pills, log_pill_acknowledgment

# Global event queue for SSE — bounded to prevent memory growth
reminder_queue = queue.Queue(maxsize=50)

# Track active (unacknowledged) reminders
active_reminders = {}
_lock = threading.Lock()

# Deduplication: prevent pill from firing multiple times per scheduled slot
_last_fired = {}  # {"pill_id_HH:MM": datetime}

DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def check_pills():
    """Called every minute. Check if any pill is due now."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_day_num = now.weekday()

    # Garbage-collect old active reminders (>2 hours = missed)
    _gc_active_reminders(now)

    # Prune dedup cache (entries older than 1 hour)
    stale = [k for k, t in _last_fired.items() if (now - t).total_seconds() > 3600]
    for k in stale:
        del _last_fired[k]

    pills = get_pills(enabled_only=True)
    for pill in pills:
        try:
            times = json.loads(pill["schedule_times"])
            days = json.loads(pill["schedule_days"])
        except (json.JSONDecodeError, TypeError):
            continue
        day_nums = [DAY_MAP[d] for d in days if d in DAY_MAP]

        if current_day_num in day_nums and current_time in times:
            # Dedup: only fire once per pill per time slot
            dedup_key = f"{pill['id']}_{current_time}"
            if dedup_key in _last_fired and (now - _last_fired[dedup_key]).total_seconds() < 120:
                continue
            _last_fired[dedup_key] = now
            trigger_reminder(pill, current_time)


def trigger_reminder(pill, scheduled_time):
    """Push a reminder to the TV UI via SSE."""
    reminder_id = f"{pill['id']}_{scheduled_time}"

    with _lock:
        if reminder_id in active_reminders:
            return
        active_reminders[reminder_id] = {
            "pill": pill,
            "scheduled_time": scheduled_time,
            "triggered_at": datetime.now().isoformat(),
        }

    # Blocking reminders: shower time and stretch breaks — 15 minutes, can't dismiss
    name_lower = pill["name"].lower()
    is_blocking = "shower" in name_lower or "stretch" in name_lower
    is_shower = "shower" in name_lower

    event_data = {
        "type": "pill_reminder",
        "reminder_id": reminder_id,
        "pill_id": pill["id"],
        "name": pill["name"],
        "dosage": pill["dosage"] or "",
        "instructions": pill["instructions"] or "",
        "reminder_type": pill["reminder_type"],
        "reminder_media": pill["reminder_media"],
        "reminder_message": pill["reminder_message"] or f"Time to take your {pill['name']}!",
        "block_minutes": 15 if is_blocking else 0,
        "icon": "🚿" if is_shower else ("🧘" if "stretch" in name_lower else "💊"),
    }
    try:
        reminder_queue.put_nowait(event_data)
    except queue.Full:
        pass  # Drop if queue is full — prevents memory growth


def _gc_active_reminders(now):
    """Remove unacknowledged reminders older than 2 hours and log as missed."""
    with _lock:
        to_remove = []
        for rid, data in active_reminders.items():
            try:
                triggered = datetime.fromisoformat(data["triggered_at"])
                if (now - triggered).total_seconds() > 7200:  # 2 hours
                    to_remove.append((rid, data))
            except Exception as e:
                print(f"Scheduler: GC error for reminder {rid}: {e}", file=sys.stderr)
                to_remove.append((rid, data))

        for rid, data in to_remove:
            del active_reminders[rid]
            # Log as missed if it was a pill (not shower/stretch)
            if "pill" in data and "scheduled_time" in data:
                pill = data["pill"]
                name = pill.get("name", "").lower()
                if "shower" not in name and "stretch" not in name:
                    try:
                        from models import log_missed_pill
                        log_missed_pill(pill["id"], data["scheduled_time"])
                    except Exception as e:
                        print(f"Scheduler: failed to log missed pill: {e}", file=sys.stderr)


def acknowledge_reminder(reminder_id):
    """Called when user presses OK on a pill reminder."""
    with _lock:
        reminder = active_reminders.pop(reminder_id, None)
    if reminder:
        if "pill" in reminder and "scheduled_time" in reminder:
            log_pill_acknowledgment(reminder["pill"]["id"], reminder["scheduled_time"])
        return True
    return False


def get_active_reminders():
    with _lock:
        return dict(active_reminders)


def get_next_pill_info():
    """Get info about the next upcoming pill for the home screen status bar."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_day_num = now.weekday()

    pills = get_pills(enabled_only=True)
    next_pill = None
    next_time = None

    for pill in pills:
        try:
            times = json.loads(pill["schedule_times"])
            days = json.loads(pill["schedule_days"])
        except (json.JSONDecodeError, TypeError):
            continue
        day_nums = [DAY_MAP[d] for d in days if d in DAY_MAP]

        if current_day_num in day_nums:
            for t in sorted(times):
                if t > current_time:
                    if next_time is None or t < next_time:
                        next_time = t
                        next_pill = pill["name"]

    if next_pill:
        # Convert 24h time to 12h for display (e.g. "20:30" -> "8:30 PM")
        h, m = next_time.split(":")
        h_int = int(h)
        ampm = "AM" if h_int < 12 else "PM"
        h_12 = h_int % 12 or 12
        display_time = f"{h_12}:{m} {ampm}"
        return {"name": next_pill, "time": display_time}
    return None


def check_birthdays():
    """Called once per hour. Check if today is someone's birthday."""
    from models import get_todays_birthdays
    now = datetime.now()

    # Only trigger at 9 AM
    if now.hour != 9:
        return

    birthdays = get_todays_birthdays()
    for b in birthdays:
        age_str = ""
        if b.get("birth_year"):
            age = now.year - b["birth_year"]
            age_str = f" — turning {age}!"

        reminder_id = f"birthday_{b['id']}_{now.strftime('%Y-%m-%d')}"
        with _lock:
            if reminder_id in active_reminders:
                continue
            active_reminders[reminder_id] = {"triggered_at": datetime.now().isoformat()}

        event_data = {
            "type": "birthday_alert",
            "reminder_id": reminder_id,
            "name": b["name"],
            "age_str": age_str,
            "relationship": b.get("relationship", ""),
            "message": f"🎂 Happy Birthday {b['name']}{age_str}",
        }
        try:
            reminder_queue.put_nowait(event_data)
        except queue.Full:
            pass


def check_favorite_shows():
    """Called every 10 minutes. Check if a favorite show is on Pluto TV."""
    from models import get_favorite_shows

    shows = get_favorite_shows(enabled_only=True)
    if not shows:
        return

    try:
        import pluto_tv
        channels, _ = pluto_tv.get_channels()
    except Exception as e:
        print(f"Scheduler: failed to load Pluto TV channels: {e}", file=sys.stderr)
        return

    now = datetime.now()

    for show in shows:
        search = show["search_term"].lower()
        for ch in channels:
            ch_name_lower = ch["name"].lower()
            prog = ch.get("current_program")
            prog_title = (prog["title"].lower() if prog else "")

            if search in ch_name_lower or search in prog_title:
                reminder_id = f"show_{show['id']}_{now.strftime('%Y-%m-%d_%H')}"
                with _lock:
                    if reminder_id in active_reminders:
                        continue
                    active_reminders[reminder_id] = {"triggered_at": datetime.now().isoformat()}

                # Auto-tune: skip the popup and navigate directly
                auto_tune = "jeopardy" in search

                event_data = {
                    "type": "auto_play" if auto_tune else "show_alert",
                    "reminder_id": reminder_id,
                    "show_name": show["name"],
                    "channel_name": ch["name"],
                    "channel_id": ch["id"],
                    "url": f"/tv/live/play/{ch['id']}",
                    "message": f"📺 {show['name']} is on now!\nChannel: {ch['name']}",
                }
                try:
                    reminder_queue.put_nowait(event_data)
                except queue.Full:
                    pass
                break  # Only alert once per show


def _cache_cleanup():
    import cache
    cache.cleanup()


def trigger_classical_music():
    """Daily classical music (doctor's orders). Checks hourly, plays at configured time."""
    import feedparser
    import random as _random
    from models import get_setting

    enabled = get_setting("classical_music_enabled", "1")
    if enabled != "1":
        return

    # Check if current hour matches the configured time
    target_hour = int(get_setting("classical_music_hour", "10"))
    if datetime.now().hour != target_hour:
        return

    # Get a random classical video (must be >= 15 minutes)
    channel_id = get_setting("classical_music_channel", "UClScm1QV2xecmZrAuADnP9g")
    try:
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        if feed.entries:
            candidates = list(feed.entries[:15])
            _random.shuffle(candidates)
            vid_id = ""
            for entry in candidates:
                vid_id = entry.get("yt_videoid", "")
                if not vid_id:
                    continue
                # Check duration — skip short videos
                try:
                    import urllib.request
                    import re
                    req = urllib.request.Request(
                        f"https://www.youtube.com/watch?v={vid_id}",
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
                    m = re.search(r'"lengthSeconds":"(\d+)"', html)
                    if m and int(m.group(1)) < 900:  # 15 minutes
                        print(f"Scheduler: skipping short video {vid_id} ({int(m.group(1))}s)", file=sys.stderr)
                        vid_id = ""
                        continue
                except Exception:
                    pass  # If we can't check duration, allow it
                break
            if vid_id:
                event_data = {
                    "type": "auto_play",
                    "url": f"/tv/youtube/watch/{vid_id}",
                    "title": "Classical Music Time",
                    "message": "Doctor says: 1 hour of classical music daily",
                    "icon": "🎵",
                }
                try:
                    reminder_queue.put_nowait(event_data)
                except queue.Full:
                    pass
    except Exception as e:
        print(f"Scheduler: classical music error: {e}", file=sys.stderr)


def trigger_exercise():
    """Daily seated exercise videos (Sit and Be Fit). Checks hourly, plays at configured times."""
    import feedparser
    import random as _random
    from models import get_setting

    enabled = get_setting("exercise_enabled", "1")
    if enabled != "1":
        return

    # Check if current hour matches either configured time
    now_hour = datetime.now().hour
    time1 = int(get_setting("exercise_hour_1", "9"))
    time2 = int(get_setting("exercise_hour_2", "15"))
    if now_hour != time1 and now_hour != time2:
        return

    channel_id = get_setting("exercise_channel", "UCLgvL3aGzMByecNYtMcyK_g")
    try:
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        if feed.entries:
            entry = _random.choice(feed.entries[:15])
            vid_id = entry.get("yt_videoid", "")
            if vid_id:
                event_data = {
                    "type": "auto_play",
                    "url": f"/tv/youtube/watch/{vid_id}",
                    "title": "Exercise Time",
                    "message": "Time for your stretching exercises!",
                    "icon": "🏋️",
                }
                try:
                    reminder_queue.put_nowait(event_data)
                except queue.Full:
                    pass
    except Exception as e:
        print(f"Scheduler: exercise error: {e}", file=sys.stderr)


def _daily_maintenance():
    """Daily database cleanup — runs at 3 AM."""
    try:
        from models import prune_old_logs
        prune_old_logs(activity_days=30, remote_days=7)
    except Exception as e:
        print(f"Scheduler: daily maintenance error: {e}", file=sys.stderr)


scheduler = BackgroundScheduler()
scheduler.add_job(check_pills, "interval", minutes=1, id="pill_checker")
scheduler.add_job(check_birthdays, "interval", hours=1, id="birthday_checker")
scheduler.add_job(check_favorite_shows, "interval", minutes=10, id="show_checker")
scheduler.add_job(_cache_cleanup, "interval", minutes=30, id="cache_cleanup")
scheduler.add_job(trigger_classical_music, "interval", hours=1, id="classical_music")
scheduler.add_job(trigger_exercise, "interval", hours=1, id="exercise")
scheduler.add_job(_daily_maintenance, "cron", hour=3, minute=15, id="daily_maintenance")


def start_scheduler():
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
