import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from config import DATABASE


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


@contextmanager
def get_db_safe():
    """Context manager that guarantees DB connection is closed."""
    db = get_db()
    try:
        yield db
    finally:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT,
            instructions TEXT,
            schedule_times TEXT NOT NULL,  -- JSON array of "HH:MM" strings
            schedule_days TEXT NOT NULL DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]',
            reminder_type TEXT NOT NULL DEFAULT 'text',  -- text, image, video
            reminder_media TEXT,  -- filename in static/media/
            reminder_message TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pill_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pill_id INTEGER NOT NULL,
            scheduled_time TEXT NOT NULL,
            acknowledged_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pill_id) REFERENCES pills(id)
        );

        CREATE TABLE IF NOT EXISTS family_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            message TEXT,
            media_type TEXT DEFAULT 'text',  -- text, image, video
            media_file TEXT,
            read_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS birthdays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birth_date TEXT NOT NULL,  -- MM-DD
            birth_year INTEGER,        -- for age calculation, nullable
            relationship TEXT,         -- e.g. "Grandson", "Daughter"
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS favorite_shows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            search_term TEXT NOT NULL,  -- used to match Pluto TV channel names
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS youtube_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            channel_id TEXT NOT NULL,    -- YouTube channel ID (UC...)
            description TEXT,
            thumbnail_url TEXT,
            category TEXT DEFAULT 'Entertainment',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,  -- netflix, hbo
            title TEXT NOT NULL,
            description TEXT,
            thumbnail_url TEXT,
            url TEXT NOT NULL,
            category TEXT DEFAULT 'Shows',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            event_date TEXT NOT NULL,  -- YYYY-MM-DD
            event_time TEXT,           -- HH:MM (optional)
            recurring TEXT,            -- null, daily, weekly, monthly, yearly
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            item_id TEXT,
            item_title TEXT,
            item_type TEXT,
            duration_seconds INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stopped_at TIMESTAMP,
            trigger TEXT,
            source TEXT
        );

        CREATE TABLE IF NOT EXISTS remote_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cec_code TEXT,
            x_key TEXT,
            button_description TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS volume_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rms REAL NOT NULL,
            db_level REAL NOT NULL,
            sonos_volume REAL,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS youtube_movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            year INTEGER,
            genre TEXT DEFAULT 'Drama',
            duration_minutes INTEGER,
            thumbnail_url TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            play_count INTEGER NOT NULL DEFAULT 0,
            last_played_at TIMESTAMP,
            added_by TEXT DEFAULT 'seed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS presence_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_count INTEGER NOT NULL DEFAULT 0,
            max_confidence REAL NOT NULL DEFAULT 0.0,
            who_detected TEXT,
            source TEXT,
            sound_level REAL,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movement_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            from_room TEXT,
            to_room TEXT NOT NULL,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            day TEXT NOT NULL,
            wake_time TEXT,
            sleep_time TEXT,
            active_minutes INTEGER DEFAULT 0,
            transition_count INTEGER DEFAULT 0,
            kitchen_trips INTEGER DEFAULT 0,
            kitchen_minutes INTEGER DEFAULT 0,
            bathroom_trips INTEGER DEFAULT 0,
            bathroom_minutes INTEGER DEFAULT 0,
            living_room_minutes INTEGER DEFAULT 0,
            UNIQUE(person, day)
        );

        -- Performance indexes for frequently-queried timestamp columns
        CREATE INDEX IF NOT EXISTS idx_activity_started ON activity_logs(started_at);
        CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_logs(activity_type, started_at);
        CREATE INDEX IF NOT EXISTS idx_remote_logged ON remote_logs(logged_at);
        CREATE INDEX IF NOT EXISTS idx_volume_logged ON volume_logs(logged_at);
        CREATE INDEX IF NOT EXISTS idx_pill_logs_pill_date ON pill_logs(pill_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_presence_logged ON presence_logs(logged_at);
        CREATE INDEX IF NOT EXISTS idx_movement_logged ON movement_logs(logged_at);
        CREATE INDEX IF NOT EXISTS idx_movement_person ON movement_logs(person, logged_at);
        CREATE INDEX IF NOT EXISTS idx_daily_activity_day ON daily_activity(person, day);
    """)
    db.commit()

    # Migrate: add trigger and source columns to activity_logs if missing
    cols = [r[1] for r in db.execute("PRAGMA table_info(activity_logs)").fetchall()]
    if "trigger" not in cols:
        db.execute("ALTER TABLE activity_logs ADD COLUMN trigger TEXT")
    if "source" not in cols:
        db.execute("ALTER TABLE activity_logs ADD COLUMN source TEXT")

    # Migrate: add who_detected, source, sound_level to presence_logs
    pcols = [r[1] for r in db.execute("PRAGMA table_info(presence_logs)").fetchall()]
    if "who_detected" not in pcols:
        db.execute("ALTER TABLE presence_logs ADD COLUMN who_detected TEXT")
    if "source" not in pcols:
        db.execute("ALTER TABLE presence_logs ADD COLUMN source TEXT")
    if "sound_level" not in pcols:
        db.execute("ALTER TABLE presence_logs ADD COLUMN sound_level REAL")
    db.commit()

    # Generate random admin password on first boot if not set
    # Passwords are stored as werkzeug hashes
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'admin_password'"
    ).fetchone()
    if not row or not row[0]:
        import secrets as _secrets
        from werkzeug.security import generate_password_hash

        pin = f"{_secrets.randbelow(1000000):06d}"
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password', ?)",
            (generate_password_hash(pin),),
        )
        db.commit()
        print(f"*** First boot: admin password set to {pin} ***")
        print("*** Change it at http://localhost:5000/admin/settings ***")

    # YouTube channels are added via admin UI — no auto-seeding

    db.close()


def log_activity(
    activity_type,
    item_id=None,
    item_title=None,
    item_type=None,
    duration_seconds=None,
    trigger=None,
    source=None,
):
    with get_db_safe() as db:
        db.execute(
            """INSERT INTO activity_logs
               (activity_type, item_id, item_title, item_type, duration_seconds, trigger, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (activity_type, item_id, item_title, item_type, duration_seconds, trigger, source),
        )
        db.commit()


def log_activity_stop(item_id, duration_seconds, trigger=None):
    """Update the most recent open activity for this item with stop time and duration."""
    with get_db_safe() as db:
        if trigger:
            db.execute(
                """UPDATE activity_logs SET stopped_at = CURRENT_TIMESTAMP,
                   duration_seconds = ?, trigger = ?
                   WHERE item_id = ? AND activity_type = 'playback_start'
                   AND stopped_at IS NULL
                   ORDER BY id DESC LIMIT 1""",
                (duration_seconds, trigger, item_id),
            )
        else:
            db.execute(
                """UPDATE activity_logs SET stopped_at = CURRENT_TIMESTAMP,
                   duration_seconds = ?
                   WHERE item_id = ? AND activity_type = 'playback_start'
                   AND stopped_at IS NULL
                   ORDER BY id DESC LIMIT 1""",
                (duration_seconds, item_id),
            )
        db.commit()


def log_remote_button(cec_code, x_key, description):
    with get_db_safe() as db:
        db.execute(
            "INSERT INTO remote_logs (cec_code, x_key, button_description) VALUES (?, ?, ?)",
            (cec_code, x_key, description),
        )
        db.commit()


def get_activity_logs(days=7, limit=200, filter_type=""):
    filter_map = {
        "playback": "activity_type LIKE 'playback%'",
        "auto_play": "activity_type = 'auto_play'",
        "alert": "activity_type LIKE 'alert%'",
        "page": "activity_type LIKE 'page%'",
        "error": "activity_type IN ('dead_stream', 'frozen_stream')",
    }
    where = filter_map.get(filter_type, "")
    with get_db_safe() as db:
        sql = "SELECT * FROM activity_logs WHERE started_at >= datetime('now', ? || ' days')"
        params = [f"-{days}"]
        if where:
            sql += " AND " + where
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_now_playing():
    """Get the most recent playback_start or auto_play that hasn't been stopped."""
    with get_db_safe() as db:
        row = db.execute(
            """SELECT * FROM activity_logs
               WHERE activity_type IN ('playback_start', 'auto_play')
                 AND stopped_at IS NULL
                 AND started_at >= datetime('now', '-4 hours')
               ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None


def get_last_activity_time():
    with get_db_safe() as db:
        row = db.execute(
            "SELECT MAX(started_at) as last_time FROM activity_logs"
        ).fetchone()
        return row["last_time"] if row else None


def get_remote_log_count(hours=1):
    with get_db_safe() as db:
        row = db.execute(
            "SELECT COUNT(*) as c FROM remote_logs WHERE logged_at >= datetime('now', ? || ' hours')",
            (f"-{hours}",),
        ).fetchone()
        return row["c"] if row else 0


# --- Settings helpers ---


def get_setting(key, default=None):
    with get_db_safe() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def is_quiet_hours():
    """Check if current time falls within configured quiet hours.
    Canonical implementation — used by both server.py and scheduler.py."""
    start = get_setting("quiet_hours_start", "22:00")
    end = get_setting("quiet_hours_end", "07:00")
    if not start or not end:
        return False
    try:
        now = datetime.now()
        now_min = now.hour * 60 + now.minute
        sh, sm = int(start.split(":")[0]), int(start.split(":")[1])
        eh, em = int(end.split(":")[0]), int(end.split(":")[1])
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        if start_min <= end_min:
            return start_min <= now_min < end_min
        else:  # Wraps midnight (e.g., 22:00 - 07:00)
            return now_min >= start_min or now_min < end_min
    except (ValueError, IndexError):
        return False


def get_setting_or_default(key):
    """Get setting from DB, falling back to config.py DEFAULTS.
    Cached for 60 seconds to reduce DB reads."""
    import cache

    cached = cache.get(f"setting_{key}")
    if cached is not None:
        return cached
    val = get_setting(key)
    if val is None:
        from config import DEFAULTS

        default = DEFAULTS.get(key)
        result = str(default) if default is not None else ""
    else:
        result = val
    cache.set(f"setting_{key}", result, ttl=60)
    return result


def set_setting(key, value):
    with get_db_safe() as db:
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )
        db.commit()


def get_all_settings():
    with get_db_safe() as db:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}


# --- Pills helpers ---


def get_pills(enabled_only=False):
    with get_db_safe() as db:
        query = "SELECT * FROM pills"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name"
        rows = db.execute(query).fetchall()
        return [dict(r) for r in rows]


def get_pill(pill_id):
    with get_db_safe() as db:
        row = db.execute("SELECT * FROM pills WHERE id = ?", (pill_id,)).fetchone()
        return dict(row) if row else None


def create_pill(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT INTO pills (name, dosage, instructions, schedule_times, schedule_days,
               reminder_type, reminder_media, reminder_message, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"],
                data.get("dosage", ""),
                data.get("instructions", ""),
                json.dumps(data.get("schedule_times", [])),
                json.dumps(
                    data.get(
                        "schedule_days",
                        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    )
                ),
                data.get("reminder_type", "text"),
                data.get("reminder_media"),
                data.get("reminder_message", ""),
                data.get("enabled", 1),
            ),
        )
        db.commit()
        return cursor.lastrowid


def update_pill(pill_id, data):
    with get_db_safe() as db:
        fields = []
        values = []
        for key in [
            "name",
            "dosage",
            "instructions",
            "reminder_type",
            "reminder_media",
            "reminder_message",
            "enabled",
        ]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        for key in ["schedule_times", "schedule_days"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(json.dumps(data[key]))
        if fields:
            values.append(pill_id)
            db.execute(f"UPDATE pills SET {', '.join(fields)} WHERE id = ?", values)
            db.commit()


def delete_pill(pill_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM pills WHERE id = ?", (pill_id,))
        db.execute("DELETE FROM pill_logs WHERE pill_id = ?", (pill_id,))
        db.commit()


def log_pill_acknowledgment(pill_id, scheduled_time):
    with get_db_safe() as db:
        db.execute(
            "INSERT INTO pill_logs (pill_id, scheduled_time, acknowledged_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (pill_id, scheduled_time),
        )
        db.commit()


def log_missed_pill(pill_id, scheduled_time):
    """Log a pill that was never acknowledged (expired after 2 hours)."""
    with get_db_safe() as db:
        db.execute(
            "INSERT INTO pill_logs (pill_id, scheduled_time, acknowledged_at) VALUES (?, ?, 'missed')",
            (pill_id, scheduled_time),
        )
        db.commit()


def get_pill_adherence_today():
    """Get today's pill status for each enabled pill and scheduled time.

    Returns list of dicts: {pill_name, scheduled_time, display_time, status, acknowledged_at}
    where status is 'taken', 'missed', or 'pending'.
    """
    import json
    from datetime import datetime

    now = datetime.now()
    current_day = now.strftime("%a").lower()[:3]  # mon, tue, etc.
    current_time = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")

    pills = get_pills(enabled_only=True)
    results = []

    with get_db_safe() as db:
        for pill in pills:
            try:
                times = json.loads(pill["schedule_times"])
                days = json.loads(pill["schedule_days"])
            except (json.JSONDecodeError, TypeError):
                continue

            if current_day not in days:
                continue

            for t in sorted(times):
                # Check pill_logs for this pill + time today
                log = db.execute(
                    """SELECT acknowledged_at FROM pill_logs
                       WHERE pill_id = ? AND scheduled_time = ?
                       AND DATE(created_at) = ?
                       ORDER BY created_at DESC LIMIT 1""",
                    (pill["id"], t, today_str),
                ).fetchone()

                if log:
                    ack = log["acknowledged_at"]
                    if ack and ack != "missed":
                        status = "taken"
                    else:
                        status = "missed"
                else:
                    status = "pending" if t >= current_time else "missed"

                # Convert to 12h display
                h, m = t.split(":")
                h_int = int(h)
                display_time = f"{h_int % 12 or 12}:{m} {'AM' if h_int < 12 else 'PM'}"

                results.append(
                    {
                        "pill_name": pill["name"],
                        "scheduled_time": t,
                        "display_time": display_time,
                        "status": status,
                        "acknowledged_at": log["acknowledged_at"] if log else None,
                    }
                )

    return results


def prune_old_logs(activity_days=30, remote_days=7):
    """Delete old logs and vacuum database."""
    activity_days = int(activity_days)
    remote_days = int(remote_days)
    with get_db_safe() as db:
        db.execute(
            "DELETE FROM activity_logs WHERE started_at < datetime('now', ?)",
            (f"-{activity_days} days",),
        )
        db.execute(
            "DELETE FROM remote_logs WHERE logged_at < datetime('now', ?)",
            (f"-{remote_days} days",),
        )
        db.execute(
            "DELETE FROM volume_logs WHERE logged_at < datetime('now', '-30 days')",
        )
        db.commit()
    # Lightweight maintenance — wal_checkpoint + optimize is sufficient for a small DB
    # (VACUUM requires autocommit mode outside get_db_safe() and is overkill here)
    with get_db_safe() as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.execute("PRAGMA optimize")


# --- Calendar helpers ---


def get_upcoming_events(days=14):
    with get_db_safe() as db:
        rows = db.execute(
            """SELECT * FROM calendar_events
               WHERE event_date >= date('now') AND event_date <= date('now', ? || ' days')
               ORDER BY event_date, event_time""",
            (str(days),),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_events():
    with get_db_safe() as db:
        rows = db.execute(
            "SELECT * FROM calendar_events ORDER BY event_date DESC, event_time"
        ).fetchall()
        return [dict(r) for r in rows]


def get_event(event_id):
    with get_db_safe() as db:
        row = db.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
        return dict(row) if row else None


def create_event(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT INTO calendar_events (title, description, event_date, event_time, recurring)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["title"],
                data.get("description", ""),
                data["event_date"],
                data.get("event_time"),
                data.get("recurring"),
            ),
        )
        db.commit()
        return cursor.lastrowid


def update_event(event_id, data):
    with get_db_safe() as db:
        fields = []
        values = []
        for key in ["title", "description", "event_date", "event_time", "recurring"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            values.append(event_id)
            db.execute(
                f"UPDATE calendar_events SET {', '.join(fields)} WHERE id = ?", values
            )
            db.commit()


def delete_event(event_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        db.commit()


# --- Favorites helpers ---


def get_favorites(platform=None):
    with get_db_safe() as db:
        if platform:
            rows = db.execute(
                "SELECT * FROM favorites WHERE platform = ? ORDER BY category, sort_order, title",
                (platform,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM favorites ORDER BY platform, category, sort_order, title"
            ).fetchall()
        return [dict(r) for r in rows]


def get_favorite(fav_id):
    with get_db_safe() as db:
        row = db.execute("SELECT * FROM favorites WHERE id = ?", (fav_id,)).fetchone()
        return dict(row) if row else None


def create_favorite(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT INTO favorites (platform, title, description, thumbnail_url, url, category, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["platform"],
                data["title"],
                data.get("description", ""),
                data.get("thumbnail_url", ""),
                data["url"],
                data.get("category", "Shows"),
                data.get("sort_order", 0),
            ),
        )
        db.commit()
        return cursor.lastrowid


def update_favorite(fav_id, data):
    with get_db_safe() as db:
        fields = []
        values = []
        for key in [
            "platform",
            "title",
            "description",
            "thumbnail_url",
            "url",
            "category",
            "sort_order",
        ]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            values.append(fav_id)
            db.execute(f"UPDATE favorites SET {', '.join(fields)} WHERE id = ?", values)
            db.commit()


# --- YouTube channel helpers ---


def get_youtube_channels(category=None):
    with get_db_safe() as db:
        if category:
            rows = db.execute(
                "SELECT * FROM youtube_channels WHERE category = ? ORDER BY sort_order, name",
                (category,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM youtube_channels ORDER BY category, sort_order, name"
            ).fetchall()
        return [dict(r) for r in rows]


def get_youtube_channel(ch_id):
    with get_db_safe() as db:
        row = db.execute(
            "SELECT * FROM youtube_channels WHERE id = ?", (ch_id,)
        ).fetchone()
        return dict(row) if row else None


def create_youtube_channel(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT INTO youtube_channels (name, channel_id, description, thumbnail_url, category, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["name"],
                data["channel_id"],
                data.get("description", ""),
                data.get("thumbnail_url", ""),
                data.get("category", "Entertainment"),
                data.get("sort_order", 0),
            ),
        )
        db.commit()
        return cursor.lastrowid


def update_youtube_channel(ch_id, data):
    with get_db_safe() as db:
        fields = []
        values = []
        for key in [
            "name",
            "channel_id",
            "description",
            "thumbnail_url",
            "category",
            "sort_order",
        ]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            values.append(ch_id)
            db.execute(
                f"UPDATE youtube_channels SET {', '.join(fields)} WHERE id = ?", values
            )
            db.commit()


# --- Family message helpers ---


def get_messages(unread_only=False, limit=50):
    with get_db_safe() as db:
        query = "SELECT * FROM family_messages"
        if unread_only:
            query += " WHERE read_at IS NULL"
        query += " ORDER BY created_at DESC LIMIT ?"
        rows = db.execute(query, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_unread_count():
    with get_db_safe() as db:
        row = db.execute(
            "SELECT COUNT(*) as c FROM family_messages WHERE read_at IS NULL"
        ).fetchone()
        return row["c"] if row else 0


def get_message(msg_id):
    with get_db_safe() as db:
        row = db.execute(
            "SELECT * FROM family_messages WHERE id = ?", (msg_id,)
        ).fetchone()
        return dict(row) if row else None


def create_message(data):
    with get_db_safe() as db:
        cursor = db.execute(
            "INSERT INTO family_messages (sender, message, media_type, media_file) VALUES (?, ?, ?, ?)",
            (
                data["sender"],
                data.get("message", ""),
                data.get("media_type", "text"),
                data.get("media_file"),
            ),
        )
        db.commit()
        return cursor.lastrowid


def mark_message_read(msg_id):
    with get_db_safe() as db:
        db.execute(
            "UPDATE family_messages SET read_at = CURRENT_TIMESTAMP WHERE id = ?",
            (msg_id,),
        )
        db.commit()


def delete_message(msg_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM family_messages WHERE id = ?", (msg_id,))
        db.commit()


# --- Birthday helpers ---


def get_birthdays():
    with get_db_safe() as db:
        rows = db.execute("SELECT * FROM birthdays ORDER BY birth_date").fetchall()
        return [dict(r) for r in rows]


def get_todays_birthdays():
    from datetime import datetime

    today_mmdd = datetime.now().strftime("%m-%d")
    with get_db_safe() as db:
        rows = db.execute(
            "SELECT * FROM birthdays WHERE birth_date = ?", (today_mmdd,)
        ).fetchall()
        return [dict(r) for r in rows]


def create_birthday(data):
    with get_db_safe() as db:
        cursor = db.execute(
            "INSERT INTO birthdays (name, birth_date, birth_year, relationship) VALUES (?, ?, ?, ?)",
            (
                data["name"],
                data["birth_date"],
                data.get("birth_year"),
                data.get("relationship", ""),
            ),
        )
        db.commit()
        return cursor.lastrowid


def delete_birthday(b_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM birthdays WHERE id = ?", (b_id,))
        db.commit()


# --- Favorite shows helpers ---


def get_favorite_shows(enabled_only=False):
    with get_db_safe() as db:
        query = "SELECT * FROM favorite_shows"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name"
        rows = db.execute(query).fetchall()
        return [dict(r) for r in rows]


def create_favorite_show(data):
    with get_db_safe() as db:
        cursor = db.execute(
            "INSERT INTO favorite_shows (name, search_term, enabled) VALUES (?, ?, ?)",
            (data["name"], data["search_term"], data.get("enabled", 1)),
        )
        db.commit()
        return cursor.lastrowid


def delete_favorite_show(s_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM favorite_shows WHERE id = ?", (s_id,))
        db.commit()


def delete_youtube_channel(ch_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM youtube_channels WHERE id = ?", (ch_id,))
        db.commit()


def delete_favorite(fav_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
        db.commit()


# --- YouTube free movies helpers ---


def get_youtube_movies(genre=None, limit=100):
    with get_db_safe() as db:
        if genre:
            rows = db.execute(
                "SELECT * FROM youtube_movies WHERE enabled = 1 AND genre = ? ORDER BY title LIMIT ?",
                (genre, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM youtube_movies WHERE enabled = 1 ORDER BY genre, title LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_youtube_movie_genres():
    with get_db_safe() as db:
        rows = db.execute(
            "SELECT DISTINCT genre FROM youtube_movies WHERE enabled = 1 ORDER BY genre"
        ).fetchall()
        return [r["genre"] for r in rows]


def get_random_youtube_movies(genre=None, limit=10, exclude_ids=None):
    with get_db_safe() as db:
        if genre:
            rows = db.execute(
                "SELECT * FROM youtube_movies WHERE enabled = 1 AND genre = ? ORDER BY RANDOM() LIMIT ?",
                (genre, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM youtube_movies WHERE enabled = 1 ORDER BY RANDOM() LIMIT ?",
                (limit,),
            ).fetchall()
        results = [dict(r) for r in rows]
        if exclude_ids:
            results = [m for m in results if m["video_id"] not in exclude_ids]
        return results


def create_youtube_movie(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT OR IGNORE INTO youtube_movies
               (video_id, title, year, genre, duration_minutes, thumbnail_url, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["video_id"],
                data["title"],
                data.get("year"),
                data.get("genre", "Drama"),
                data.get("duration_minutes"),
                data.get(
                    "thumbnail_url",
                    f"https://i.ytimg.com/vi/{data['video_id']}/hqdefault.jpg",
                ),
                data.get("added_by", "manual"),
            ),
        )
        db.commit()
        return cursor.lastrowid


def delete_youtube_movie(movie_id):
    with get_db_safe() as db:
        db.execute("DELETE FROM youtube_movies WHERE id = ?", (movie_id,))
        db.commit()


def get_youtube_movie_count():
    with get_db_safe() as db:
        row = db.execute(
            "SELECT COUNT(*) as c FROM youtube_movies WHERE enabled = 1"
        ).fetchone()
        return row["c"] if row else 0


def get_youtube_movie(movie_id):
    with get_db_safe() as db:
        row = db.execute(
            "SELECT * FROM youtube_movies WHERE id = ?", (movie_id,)
        ).fetchone()
        return dict(row) if row else None


def get_youtube_movie_by_video_id(video_id):
    with get_db_safe() as db:
        row = db.execute(
            "SELECT * FROM youtube_movies WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None


def update_youtube_movie(movie_id, data):
    with get_db_safe() as db:
        fields = []
        values = []
        for key in [
            "title",
            "video_id",
            "year",
            "genre",
            "duration_minutes",
            "thumbnail_url",
            "enabled",
        ]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            values.append(movie_id)
            db.execute(
                f"UPDATE youtube_movies SET {', '.join(fields)} WHERE id = ?", values
            )
            db.commit()


def record_youtube_movie_play(video_id):
    """Increment play count and set last_played timestamp."""
    with get_db_safe() as db:
        db.execute(
            """UPDATE youtube_movies SET play_count = play_count + 1,
               last_played_at = CURRENT_TIMESTAMP WHERE video_id = ?""",
            (video_id,),
        )
        db.commit()


def get_youtube_movie_stats():
    """Get aggregate stats for the free movies catalog."""
    with get_db_safe() as db:
        total = db.execute("SELECT COUNT(*) as c FROM youtube_movies").fetchone()["c"]
        enabled = db.execute(
            "SELECT COUNT(*) as c FROM youtube_movies WHERE enabled = 1"
        ).fetchone()["c"]
        total_plays = db.execute(
            "SELECT COALESCE(SUM(play_count), 0) as c FROM youtube_movies"
        ).fetchone()["c"]
        total_minutes = db.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) as c FROM youtube_movies WHERE enabled = 1"
        ).fetchone()["c"]
        genre_counts = db.execute(
            "SELECT genre, COUNT(*) as c FROM youtube_movies WHERE enabled = 1 GROUP BY genre ORDER BY c DESC"
        ).fetchall()
        most_played = db.execute(
            "SELECT * FROM youtube_movies WHERE play_count > 0 ORDER BY play_count DESC LIMIT 5"
        ).fetchall()
        recently_played = db.execute(
            "SELECT * FROM youtube_movies WHERE last_played_at IS NOT NULL ORDER BY last_played_at DESC LIMIT 5"
        ).fetchall()
        never_played = db.execute(
            "SELECT COUNT(*) as c FROM youtube_movies WHERE play_count = 0 AND enabled = 1"
        ).fetchone()["c"]
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "total_plays": total_plays,
            "total_hours": round(total_minutes / 60, 1),
            "genre_counts": [dict(r) for r in genre_counts],
            "most_played": [dict(r) for r in most_played],
            "recently_played": [dict(r) for r in recently_played],
            "never_played": never_played,
        }


def log_presence(person_count, max_confidence, who_detected=None,
                 source=None, sound_level=None):
    """Log a presence detection reading."""
    who_str = ",".join(who_detected) if who_detected else None
    with get_db_safe() as db:
        db.execute(
            """INSERT INTO presence_logs
               (person_count, max_confidence, who_detected, source, sound_level)
               VALUES (?, ?, ?, ?, ?)""",
            (person_count, round(max_confidence, 3), who_str, source,
             round(sound_level, 1) if sound_level is not None else None),
        )
        db.commit()


def get_presence_logs(days=7):
    """Get presence logs for the last N days."""
    with get_db_safe() as db:
        rows = db.execute(
            "SELECT * FROM presence_logs WHERE logged_at >= datetime('now', ?) ORDER BY logged_at DESC",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_presence_summary(days=1):
    """Get hourly summary of presence detection for the last N days."""
    with get_db_safe() as db:
        rows = db.execute("""
            SELECT
                date(logged_at, 'localtime') as day,
                strftime('%H', logged_at, 'localtime') as hour,
                COUNT(*) as readings,
                SUM(CASE WHEN person_count = 0 THEN 1 ELSE 0 END) as empty,
                SUM(CASE WHEN person_count = 1 THEN 1 ELSE 0 END) as one_person,
                SUM(CASE WHEN person_count = 2 THEN 1 ELSE 0 END) as two_people,
                SUM(CASE WHEN person_count > 2 THEN 1 ELSE 0 END) as more,
                ROUND(AVG(max_confidence), 2) as avg_confidence
            FROM presence_logs
            WHERE logged_at >= datetime('now', ?)
            GROUP BY day, hour
            ORDER BY day DESC, hour DESC
        """, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]


def cleanup_presence_logs(keep_days=30):
    """Delete presence logs older than N days."""
    with get_db_safe() as db:
        db.execute(
            "DELETE FROM presence_logs WHERE logged_at < datetime('now', ?)",
            (f"-{keep_days} days",),
        )
        db.commit()


# --- Movement Tracking ---

def log_movement(person, from_room, to_room):
    """Log a room transition for a person."""
    with get_db_safe() as db:
        db.execute(
            "INSERT INTO movement_logs (person, from_room, to_room) VALUES (?, ?, ?)",
            (person, from_room, to_room),
        )
        db.commit()


def get_movement_logs(person=None, days=1):
    """Get movement logs, optionally filtered by person."""
    with get_db_safe() as db:
        if person:
            rows = db.execute(
                """SELECT * FROM movement_logs
                   WHERE person = ? AND logged_at >= datetime('now', ?)
                   ORDER BY logged_at DESC""",
                (person, f"-{days} days"),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT * FROM movement_logs
                   WHERE logged_at >= datetime('now', ?)
                   ORDER BY logged_at DESC""",
                (f"-{days} days",),
            ).fetchall()
        return [dict(r) for r in rows]


def get_daily_activity(person, day):
    """Get or create daily activity summary for a person."""
    with get_db_safe() as db:
        row = db.execute(
            "SELECT * FROM daily_activity WHERE person = ? AND day = ?",
            (person, day),
        ).fetchone()
        return dict(row) if row else None


def upsert_daily_activity(person, day, **kwargs):
    """Insert or update daily activity summary."""
    with get_db_safe() as db:
        existing = db.execute(
            "SELECT id FROM daily_activity WHERE person = ? AND day = ?",
            (person, day),
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [person, day]
            db.execute(
                f"UPDATE daily_activity SET {sets} WHERE person = ? AND day = ?",
                vals,
            )
        else:
            cols = ["person", "day"] + list(kwargs.keys())
            placeholders = ", ".join(["?"] * len(cols))
            vals = [person, day] + list(kwargs.values())
            db.execute(
                f"INSERT INTO daily_activity ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )
        db.commit()


def get_daily_activity_range(person, days=7):
    """Get daily activity summaries for trending."""
    with get_db_safe() as db:
        rows = db.execute(
            """SELECT * FROM daily_activity
               WHERE person = ? AND day >= date('now', ?)
               ORDER BY day DESC""",
            (person, f"-{days} days"),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_daily_activity(days=7):
    """Get daily activity summaries for all people."""
    with get_db_safe() as db:
        rows = db.execute(
            """SELECT * FROM daily_activity
               WHERE day >= date('now', ?)
               ORDER BY day DESC, person""",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]


def compute_daily_activity(person, day):
    """Compute daily activity metrics from movement_logs for a given day."""
    with get_db_safe() as db:
        rows = db.execute(
            """SELECT * FROM movement_logs
               WHERE person = ? AND date(logged_at, 'localtime') = ?
               ORDER BY logged_at ASC""",
            (person, day),
        ).fetchall()

    if not rows:
        return None

    movements = [dict(r) for r in rows]
    wake_time = movements[0]["logged_at"].split(" ")[1][:5] if movements else None
    sleep_time = movements[-1]["logged_at"].split(" ")[1][:5] if movements else None

    transition_count = len(movements)
    kitchen_trips = 0
    bathroom_trips = 0

    # Estimate time in rooms from transitions
    kitchen_minutes = 0
    bathroom_minutes = 0
    living_room_minutes = 0

    for i, m in enumerate(movements):
        to_room = (m["to_room"] or "").lower()

        if "kitchen" in to_room:
            kitchen_trips += 1
        elif "bathroom" in to_room or "pantry" in to_room:
            bathroom_trips += 1

        # Estimate duration: time until next transition
        if i + 1 < len(movements):
            try:
                from datetime import datetime as _dt
                t1 = _dt.fromisoformat(m["logged_at"])
                t2 = _dt.fromisoformat(movements[i + 1]["logged_at"])
                mins = (t2 - t1).total_seconds() / 60
                # Cap at 120 min to handle overnight gaps
                mins = min(mins, 120)

                if "kitchen" in to_room:
                    kitchen_minutes += mins
                elif "bathroom" in to_room or "pantry" in to_room:
                    bathroom_minutes += mins
                elif "living" in to_room:
                    living_room_minutes += mins
            except (ValueError, TypeError):
                pass

    # Active minutes = wake to sleep span (rough)
    active_minutes = 0
    if len(movements) >= 2:
        try:
            from datetime import datetime as _dt
            t_first = _dt.fromisoformat(movements[0]["logged_at"])
            t_last = _dt.fromisoformat(movements[-1]["logged_at"])
            active_minutes = int((t_last - t_first).total_seconds() / 60)
        except (ValueError, TypeError):
            pass

    return {
        "wake_time": wake_time,
        "sleep_time": sleep_time,
        "active_minutes": active_minutes,
        "transition_count": transition_count,
        "kitchen_trips": kitchen_trips,
        "kitchen_minutes": int(kitchen_minutes),
        "bathroom_trips": bathroom_trips,
        "bathroom_minutes": int(bathroom_minutes),
        "living_room_minutes": int(living_room_minutes),
    }


def cleanup_movement_logs(keep_days=90):
    """Delete movement logs older than N days. Keep longer than presence."""
    with get_db_safe() as db:
        db.execute(
            "DELETE FROM movement_logs WHERE logged_at < datetime('now', ?)",
            (f"-{keep_days} days",),
        )
        db.commit()
