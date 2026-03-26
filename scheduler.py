import json
import queue
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from models import get_pills, log_pill_acknowledgment

# Global event queue for SSE — pill reminders push here, TV UI reads from here
reminder_queue = queue.Queue()

# Track active (unacknowledged) reminders
active_reminders = {}
_lock = threading.Lock()

DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def check_pills():
    """Called every minute. Check if any pill is due now."""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_day_num = now.weekday()

    pills = get_pills(enabled_only=True)
    for pill in pills:
        try:
            times = json.loads(pill["schedule_times"])
            days = json.loads(pill["schedule_days"])
        except (json.JSONDecodeError, TypeError):
            continue
        day_nums = [DAY_MAP[d] for d in days if d in DAY_MAP]

        if current_day_num in day_nums and current_time in times:
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
    is_stretch = "stretch" in name_lower

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
        "icon": "🚿" if is_shower else ("🧘" if is_stretch else "💊"),
    }
    reminder_queue.put(event_data)


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
            active_reminders[reminder_id] = {"triggered": True}

        event_data = {
            "type": "birthday_alert",
            "reminder_id": reminder_id,
            "name": b["name"],
            "age_str": age_str,
            "relationship": b.get("relationship", ""),
            "message": f"🎂 Happy Birthday {b['name']}{age_str}",
        }
        reminder_queue.put(event_data)


def check_favorite_shows():
    """Called every 10 minutes. Check if a favorite show is on Pluto TV."""
    from models import get_favorite_shows

    shows = get_favorite_shows(enabled_only=True)
    if not shows:
        return

    try:
        import pluto_tv
        channels, _ = pluto_tv.get_channels()
    except Exception:
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
                    active_reminders[reminder_id] = {"triggered": True}

                event_data = {
                    "type": "show_alert",
                    "reminder_id": reminder_id,
                    "show_name": show["name"],
                    "channel_name": ch["name"],
                    "channel_id": ch["id"],
                    "message": f"📺 {show['name']} is on now!\nChannel: {ch['name']}",
                }
                reminder_queue.put(event_data)
                break  # Only alert once per show


def _cache_cleanup():
    import cache
    cache.cleanup()


def trigger_classical_music():
    """Daily 1 hour of classical music (doctor's orders). Triggers at 10 AM."""
    import feedparser
    import random as _random
    from models import get_setting

    enabled = get_setting("classical_music_enabled", "1")
    if enabled != "1":
        return

    # Get a random classical video from the HALIDONMUSIC channel or similar
    channel_id = "UCJ5v_MCY6GNUBTO8-D3XoAg"  # HALIDONMUSIC
    try:
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        if feed.entries:
            entry = _random.choice(feed.entries[:15])
            vid_id = entry.get("yt_videoid", "")
            if vid_id:
                event_data = {
                    "type": "auto_play",
                    "url": f"/tv/youtube/watch/{vid_id}",
                    "title": "Classical Music Time",
                    "message": "Doctor says: 1 hour of classical music daily",
                    "icon": "🎵",
                }
                reminder_queue.put(event_data)
    except Exception:
        pass


scheduler = BackgroundScheduler()
scheduler.add_job(check_pills, "interval", minutes=1, id="pill_checker")
scheduler.add_job(check_birthdays, "interval", hours=1, id="birthday_checker")
scheduler.add_job(check_favorite_shows, "interval", minutes=10, id="show_checker")
scheduler.add_job(_cache_cleanup, "interval", minutes=30, id="cache_cleanup")
scheduler.add_job(trigger_classical_music, "cron", hour=10, minute=0, id="classical_music")


def start_scheduler():
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
