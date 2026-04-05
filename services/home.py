"""Home screen data assembly for Senior TV."""

from datetime import datetime

import models


def get_jellyfin_recommendations(jf, excluded_ids):
    """Fetch random Jellyfin movies and shows for the home screen.
    Returns (movies_list, shows_list)."""
    jf_movies = []
    jf_shows = []
    if not jf:
        return jf_movies, jf_shows
    try:
        resume = jf.get_resume(limit=5)
        libs = jf.get_libraries()
        for lib in libs:
            lib_type = lib.get("type", "")
            try:
                items = jf.get_library_items(
                    lib["id"],
                    sort="Random",
                    sort_order="Ascending",
                    limit=30,
                )
                items = [i for i in items if i["id"] not in excluded_ids][:20]
                for item in items:
                    if item.get("type") == "series" or lib_type == "tvshows":
                        jf_shows.append(item)
                    else:
                        jf_movies.append(item)
            except Exception:
                pass
        jf_movies = resume + jf_movies
    except Exception:
        pass
    return jf_movies, jf_shows


def get_home_photo():
    """Get a random Immich photo for the home page widget.
    Returns photo dict or None."""
    try:
        import immich_api

        if immich_api.is_configured():
            photos = immich_api.get_random_photos(count=5)
            if photos:
                return photos[0]
    except Exception:
        pass
    return None


def get_day_info():
    """Get day-of-year and holiday info for the left panel.
    Returns dict with day_of_year and holidays_today."""
    now = datetime.now()
    day_num = now.timetuple().tm_yday
    total = 365 + (1 if now.year % 4 == 0 else 0)
    day_of_year = f"Day {day_num} of {total}"

    today_date = now.strftime("%Y-%m-%d")
    today_events = models.get_upcoming_events(days=1)
    holidays_today = ""
    for ev in today_events:
        if ev["event_date"] == today_date and "\U0001f389" in ev["title"]:
            holidays_today = ev["title"].replace("\U0001f389 ", "")
            break

    return {
        "day_of_year": day_of_year,
        "holidays_today": holidays_today,
    }


def build_menu_items(unread_msgs, free_movie_count):
    """Build the home screen navigation menu."""
    msg_label = f"Messages ({unread_msgs} new)" if unread_msgs > 0 else "Messages"
    return [
        {"label": "Live TV", "icon": "\U0001f4fa", "url": "/tv/live"},
        {
            "label": f"Free Movies ({free_movie_count})",
            "icon": "\U0001f37f",
            "url": "/tv/free-movies",
        },
        {"label": "Movies & Shows", "icon": "\U0001f3ac", "url": "/tv/plex"},
        {"label": "YouTube", "icon": "\u25b6\ufe0f", "url": "/tv/youtube"},
        {"label": msg_label, "icon": "\U0001f48c", "url": "/tv/messages"},
        {"label": "News", "icon": "\U0001f4f0", "url": "/tv/news"},
        {"label": "Weather", "icon": "\U0001f324\ufe0f", "url": "/tv/weather"},
        {"label": "Calendar", "icon": "\U0001f4c5", "url": "/tv/calendar"},
        {"label": "Photo Frame", "icon": "\U0001f4f7", "url": "/tv/photos"},
    ]
