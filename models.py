import sqlite3
import json
from contextlib import contextmanager
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
            stopped_at TIMESTAMP
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
    """)
    db.commit()

    # Generate random admin password on first boot if not set
    row = db.execute("SELECT value FROM settings WHERE key = 'admin_password'").fetchone()
    if not row or not row[0]:
        import secrets as _secrets
        pin = f"{_secrets.randbelow(1000000):06d}"
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password', ?)",
            (pin,),
        )
        db.commit()
        print(f"*** First boot: admin password set to {pin} ***")
        print("*** Change it at http://localhost:5000/admin/settings ***")

    # Pre-seed YouTube channels if table is empty
    count = db.execute("SELECT COUNT(*) FROM youtube_channels").fetchone()[0]
    if count == 0:
        seed_channels = [
            # (name, channel_id, category)
            ("Jeopardy!", "UCM-Rl5rQMg0JzuIPnMLBpg", "Game Shows"),
            ("Wheel of Fortune", "UCuMn69gZSgDBp-cYJtJrWlA", "Game Shows"),
            ("The Price Is Right", "UCay1OU-kB0yNLahkQSA70Bg", "Game Shows"),
            ("Family Feud", "UCnB4zUqYfkG6O9t3-eo1TTg", "Game Shows"),
            ("The Andy Griffith Show", "UCUH7JiEWE3c0R3Q_vmlz_SQ", "Classic TV"),
            ("I Love Lucy", "UCFNRr0jGrqNJXJ1Ii8GR9Ig", "Classic TV"),
            ("The Carol Burnett Show", "UCjlCJlb2-a_68WKXQ_3Fz_g", "Classic TV"),
            ("Bob Ross", "UCxcnsr1R5Ge_fbTu5ajt8DQ", "Wind Down"),
            ("Nature Relaxation Films", "UC4lp9Emg1ci8eo2eDkB-Tag", "Wind Down"),
            ("BBC Earth", "UCwmZiChSryoWQCZMIQezgTg", "Wind Down"),
            ("Scenic Relaxation", "UC95bEkaIgwhxSjSsdMFXYGg", "Wind Down"),
            ("Oldies Music Radio", "UCaZDizLXZkR0V2DkZGEWeYw", "Music"),
            ("Lawrence Welk LPs", "UCepuqk1t-8J1nByerAKfP7g", "Music"),
            ("Essential Classic", "UClScm1QV2xecmZrAuADnP9g", "Music"),
            ("America's Funniest Home Videos", "UCYhMHEBSRK3mFW0GMlIHVSg", "Comedy"),
            ("Johnny Carson", "UC7McHNOsrUL2fRxTB_xvgRQ", "Comedy"),
            ("Bonanza", "UCzJhgN8iJpgatGOjPkyE4PA", "Westerns"),
            ("ABC News", "UCBi2mrWuNuyYy4gbM6fU18Q", "News"),
            ("CBS News", "UC8p1vwvWtl6T73JiExfWs1g", "News"),
        ]
        for name, ch_id, cat in seed_channels:
            db.execute(
                "INSERT INTO youtube_channels (name, channel_id, category) VALUES (?, ?, ?)",
                (name, ch_id, cat),
            )
        db.commit()
        print(f"Pre-seeded {len(seed_channels)} YouTube channels")

    db.close()


def log_activity(activity_type, item_id=None, item_title=None, item_type=None, duration_seconds=None):
    with get_db_safe() as db:
        db.execute(
            """INSERT INTO activity_logs (activity_type, item_id, item_title, item_type, duration_seconds)
               VALUES (?, ?, ?, ?, ?)""",
            (activity_type, item_id, item_title, item_type, duration_seconds),
        )
        db.commit()


def log_activity_stop(item_id, duration_seconds):
    with get_db_safe() as db:
        db.execute(
            """UPDATE activity_logs SET stopped_at = CURRENT_TIMESTAMP, duration_seconds = ?
               WHERE item_id = ? AND stopped_at IS NULL
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


def get_activity_logs(days=7, limit=200):
    with get_db_safe() as db:
        rows = db.execute(
            """SELECT * FROM activity_logs
               WHERE started_at >= datetime('now', ? || ' days')
               ORDER BY started_at DESC LIMIT ?""",
            (f"-{days}", limit),
        ).fetchall()
        return [dict(r) for r in rows]


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
                json.dumps(data.get("schedule_days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])),
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
        for key in ["name", "dosage", "instructions", "reminder_type", "reminder_media", "reminder_message", "enabled"]:
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

                results.append({
                    "pill_name": pill["name"],
                    "scheduled_time": t,
                    "display_time": display_time,
                    "status": status,
                    "acknowledged_at": log["acknowledged_at"] if log else None,
                })

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
        db.execute("VACUUM")
        db.commit()


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
        rows = db.execute("SELECT * FROM calendar_events ORDER BY event_date DESC, event_time").fetchall()
        return [dict(r) for r in rows]


def get_event(event_id):
    with get_db_safe() as db:
        row = db.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,)).fetchone()
        return dict(row) if row else None


def create_event(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT INTO calendar_events (title, description, event_date, event_time, recurring)
               VALUES (?, ?, ?, ?, ?)""",
            (data["title"], data.get("description", ""), data["event_date"], data.get("event_time"), data.get("recurring")),
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
            db.execute(f"UPDATE calendar_events SET {', '.join(fields)} WHERE id = ?", values)
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
            rows = db.execute("SELECT * FROM favorites ORDER BY platform, category, sort_order, title").fetchall()
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
        for key in ["platform", "title", "description", "thumbnail_url", "url", "category", "sort_order"]:
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
            rows = db.execute("SELECT * FROM youtube_channels ORDER BY category, sort_order, name").fetchall()
        return [dict(r) for r in rows]


def get_youtube_channel(ch_id):
    with get_db_safe() as db:
        row = db.execute("SELECT * FROM youtube_channels WHERE id = ?", (ch_id,)).fetchone()
        return dict(row) if row else None


def create_youtube_channel(data):
    with get_db_safe() as db:
        cursor = db.execute(
            """INSERT INTO youtube_channels (name, channel_id, description, thumbnail_url, category, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["name"], data["channel_id"], data.get("description", ""),
             data.get("thumbnail_url", ""), data.get("category", "Entertainment"),
             data.get("sort_order", 0)),
        )
        db.commit()
        return cursor.lastrowid


def update_youtube_channel(ch_id, data):
    with get_db_safe() as db:
        fields = []
        values = []
        for key in ["name", "channel_id", "description", "thumbnail_url", "category", "sort_order"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if fields:
            values.append(ch_id)
            db.execute(f"UPDATE youtube_channels SET {', '.join(fields)} WHERE id = ?", values)
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
        row = db.execute("SELECT COUNT(*) as c FROM family_messages WHERE read_at IS NULL").fetchone()
        return row["c"] if row else 0


def get_message(msg_id):
    with get_db_safe() as db:
        row = db.execute("SELECT * FROM family_messages WHERE id = ?", (msg_id,)).fetchone()
        return dict(row) if row else None


def create_message(data):
    with get_db_safe() as db:
        cursor = db.execute(
            "INSERT INTO family_messages (sender, message, media_type, media_file) VALUES (?, ?, ?, ?)",
            (data["sender"], data.get("message", ""), data.get("media_type", "text"), data.get("media_file")),
        )
        db.commit()
        return cursor.lastrowid


def mark_message_read(msg_id):
    with get_db_safe() as db:
        db.execute("UPDATE family_messages SET read_at = CURRENT_TIMESTAMP WHERE id = ?", (msg_id,))
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
        rows = db.execute("SELECT * FROM birthdays WHERE birth_date = ?", (today_mmdd,)).fetchall()
        return [dict(r) for r in rows]


def create_birthday(data):
    with get_db_safe() as db:
        cursor = db.execute(
            "INSERT INTO birthdays (name, birth_date, birth_year, relationship) VALUES (?, ?, ?, ?)",
            (data["name"], data["birth_date"], data.get("birth_year"), data.get("relationship", "")),
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
