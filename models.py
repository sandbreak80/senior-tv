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
    """)
    db.commit()
    db.close()


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
