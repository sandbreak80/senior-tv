import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get("SENIOR_TV_SECRET", "senior-tv-default-key-change-me")
DATABASE = os.path.join(BASE_DIR, "senior_tv.db")
MEDIA_DIR = os.path.join(BASE_DIR, "static", "media")
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB for video uploads

# Defaults (overridable via admin panel / settings table)
DEFAULTS = {
    # Empty = unconfigured (setup wizard will prompt)
    "greeting_names": "",
    "weather_lat": "",
    "weather_lon": "",
    "weather_unit": "fahrenheit",
    "news_feeds": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    # Service URLs — empty until configured via admin panel
    "jellyfin_url": "",
    "jellyfin_api_key": "",
    "jellyfin_user_id": "",
    "frigate_url": "",
    "frigate_user": "",
    "frigate_pass": "",
    "frigate_cameras": "front_door",
    "ha_url": "",
    "ha_token": "",
    "photo_interval": "10",
    "photo_nas_path": "",
    "immich_url": "",
    "immich_api_key": "",
    # Admin password — generated on first boot by init_db() if not set
    "admin_password": "",
    # Scheduled news blocks — 1 hour of live news, 3 times daily
    # Times are 24h format, comma-separated. Empty = disabled.
    "news_schedule": "07:00,12:00,18:00",
    # Pluto TV news channels to rotate through (picked randomly per block)
    "news_channels": "News + Opinion",
    # Whether scheduled content (news, Jeopardy, classical) interrupts current playback
    # "always" = always interrupt, "idle_only" = only if on home screen or screensaver
    "auto_play_interrupt": "always",
    # Minutes before YouTube/video player returns to home for content rotation (0 = never)
    "content_rotation_minutes": "90",
    # Audio/accessibility — sensible universal defaults
    "tts_enabled": "1",
    "audio_processing": "0",
    "voice_boost": "mild",
    "audio_target": "-14",
    # Activity log level: "minimal" (playback only), "normal" (+ pages, alerts),
    # "verbose" (everything — for performance analysis)
    "log_level": "verbose",
}
