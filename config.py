import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get("SENIOR_TV_SECRET", "senior-tv-default-key-change-me")
DATABASE = os.path.join(BASE_DIR, "senior_tv.db")
MEDIA_DIR = os.path.join(BASE_DIR, "static", "media")
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB for video uploads

# Defaults (overridable via admin panel / settings table)
DEFAULTS = {
    "greeting_names": "Colleen & Don",
    "weather_lat": "40.7128",
    "weather_lon": "-74.0060",
    "weather_unit": "fahrenheit",
    "news_feeds": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "jellyfin_url": "http://192.168.50.20:8096",
    "jellyfin_api_key": "",
    "jellyfin_user_id": "",
    "frigate_url": "https://192.168.50.114:8971",
    "frigate_user": "admin",
    "frigate_pass": "",
    "frigate_cameras": "front_door",
    "ha_url": "http://192.168.50.76:8123",
    "ha_token": "",
    "photo_interval": "10",
    "photo_nas_path": "",
    "immich_url": "",
    "immich_api_key": "",
    "admin_password": "family2026",
    "tts_enabled": "1",
    "inactivity_alert_hours": "4",
    "stretch_enabled": "1",
    "stretch_times": "09:00,13:00,17:00,21:00",
    "stretch_duration": "15",
}
