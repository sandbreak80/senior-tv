import json
import os
import shutil
import subprocess
from datetime import datetime

import feedparser
import requests
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

import cache
import config
import models
from scheduler import (
    acknowledge_reminder,
    get_active_reminders,
    get_next_pill_info,
    reminder_queue,
    start_scheduler,
    stop_scheduler,
)

app = Flask(__name__)
app_start_time = datetime.now()
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE


# --- Helpers ---

def get_setting_or_default(key):
    val = models.get_setting(key)
    if val is None:
        default = config.DEFAULTS.get(key)
        return str(default) if default is not None else ""
    return val


def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        period = "Good Morning"
    elif hour < 17:
        period = "Good Afternoon"
    else:
        period = "Good Evening"
    names = get_setting_or_default("greeting_names")
    return f"{period}, {names}!"


def get_weather_summary():
    cached = cache.get("weather_summary")
    if cached:
        return cached
    try:
        lat = get_setting_or_default("weather_lat")
        lon = get_setting_or_default("weather_lon")
        unit = get_setting_or_default("weather_unit")
        temp_unit = "fahrenheit" if unit == "fahrenheit" else "celsius"
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "temperature_unit": temp_unit,
            },
            timeout=5,
        )
        data = resp.json()
        current = data["current"]
        temp = round(current["temperature_2m"])
        symbol = "°F" if unit == "fahrenheit" else "°C"
        code = current["weather_code"]
        condition = weather_code_to_text(code)
        result = {"temp": f"{temp}{symbol}", "condition": condition, "code": code}
        cache.set("weather_summary", result, ttl=600)  # 10 min
        return result
    except Exception:
        return {"temp": "--", "condition": "Unavailable", "code": -1}


def weather_code_to_text(code):
    mapping = {
        0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Foggy", 48: "Foggy", 51: "Light Drizzle", 53: "Drizzle",
        55: "Heavy Drizzle", 61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
        71: "Light Snow", 73: "Snow", 75: "Heavy Snow", 80: "Rain Showers",
        81: "Rain Showers", 82: "Heavy Showers", 95: "Thunderstorm",
    }
    return mapping.get(code, "Unknown")


def weather_code_to_icon(code):
    if code <= 1:
        return "☀️"
    elif code <= 3:
        return "⛅"
    elif code <= 48:
        return "🌫️"
    elif code <= 55:
        return "🌦️"
    elif code <= 65:
        return "🌧️"
    elif code <= 75:
        return "❄️"
    elif code <= 82:
        return "🌧️"
    elif code >= 95:
        return "⛈️"
    return "🌡️"


# ========================================
# TV UI Routes
# ========================================

@app.route("/")
def tv_home():
    greeting = get_greeting()
    weather = get_weather_summary()
    weather_icon = weather_code_to_icon(weather["code"])
    next_pill = get_next_pill_info()
    now = datetime.now()
    date_str = now.strftime("%A, %B %d")
    time_str = now.strftime("%I:%M %p").lstrip("0")

    # Time-of-day content categories (care plan)
    hour = now.hour
    if hour < 14:  # Morning: wake to 2 PM
        time_period = "morning"
        suggested_categories = ["Game Shows", "Morning Shows", "Classic TV"]
        suggested_pluto = ["News + Opinion", "Daytime + Game Shows", "Classic TV"]
        jf_genres = ["Comedy", "Family", "Western"]
    elif hour < 17:  # Afternoon: 2–5 PM
        time_period = "afternoon"
        suggested_categories = ["Westerns", "Classic TV", "Comedy", "Crime & Drama", "Music & Variety"]
        suggested_pluto = ["Westerns", "Classic TV", "Comedy", "Drama", "True Crime"]
        jf_genres = ["Western", "Comedy", "Drama", "Crime"]
    else:  # Evening: 5 PM+
        time_period = "evening"
        suggested_categories = ["Comedy", "Crime & Drama", "Wind Down", "Westerns", "Music & Variety", "Nature"]
        suggested_pluto = ["Comedy", "Classic TV", "Drama", "True Crime", "Westerns"]
        jf_genres = ["Western", "Family", "Comedy", "Crime"]

    unread_msgs = models.get_unread_count()
    msg_label = f"Messages ({unread_msgs} new)" if unread_msgs > 0 else "Messages"

    # Day info for the left panel
    day_num = now.timetuple().tm_yday
    day_of_year = f"Day {day_num} of {365 + (1 if now.year % 4 == 0 else 0)}"
    # Check if today is a holiday
    today_date = now.strftime("%Y-%m-%d")
    today_events = models.get_upcoming_events(days=1)
    holidays_today = ""
    for ev in today_events:
        if ev["event_date"] == today_date and "🎉" in ev["title"]:
            holidays_today = ev["title"].replace("🎉 ", "")
            break

    menu_items = [
        {"label": "Live TV", "icon": "📺", "url": "/tv/live"},
        {"label": "Movies & Shows", "icon": "🎬", "url": "/tv/plex"},
        {"label": "YouTube", "icon": "▶️", "url": "/tv/youtube"},
        {"label": msg_label, "icon": "💌", "url": "/tv/messages"},
        {"label": "News", "icon": "📰", "url": "/tv/news"},
        {"label": "Weather", "icon": "🌤️", "url": "/tv/weather"},
        {"label": "Calendar", "icon": "📅", "url": "/tv/calendar"},
        {"label": "Photo Frame", "icon": "📷", "url": "/tv/photos"},
    ]

    # Jellyfin recommendations — genre-aware by time of day
    jf_recommendations = []
    jf = _get_jellyfin()
    if jf:
        try:
            resume = jf.get_resume(limit=5)
            # Get genre-specific picks for this time of day
            libs = jf.get_libraries()
            genre_picks = []
            for lib in libs:
                for genre in jf_genres[:3]:
                    try:
                        items = jf.get_library_items(lib["id"], sort="Random",
                                                     sort_order="Ascending", genre=genre, limit=6)
                        genre_picks.extend(items)
                    except Exception:
                        pass
            jf_recommendations = resume + genre_picks
        except Exception:
            pass

    # LA news live stream — only show before 3 PM (care plan: no news in evening)
    la_news_video_id = None
    wind_down_video = None
    if hour < 15:
        la_news_video_id = cache.get("la_news_video_id")
        if la_news_video_id is None:
            try:
                import re as _re
                r = requests.get("https://www.youtube.com/@abc7/live", timeout=4,
                                 headers={"User-Agent": "Mozilla/5.0"})
                match = _re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
                if match and "isLive" in r.text:
                    la_news_video_id = match.group(1)
                    cache.set("la_news_video_id", la_news_video_id, ttl=1800)  # 30 min
            except Exception:
                pass
    else:
        # After 3 PM: embed a calming Wind Down video instead
        wind_down_video = cache.get("wind_down_video")
        if wind_down_video is None:
            try:
                import random as _random
                wd_channels = models.get_youtube_channels(category="Wind Down")
                if wd_channels:
                    ch = _random.choice(wd_channels)
                    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['channel_id']}"
                    feed = feedparser.parse(feed_url)
                    if feed.entries:
                        entry = _random.choice(feed.entries[:10])
                        vid_id = entry.get("yt_videoid", "")
                        if vid_id:
                            wind_down_video = {"video_id": vid_id, "name": ch["name"],
                                               "title": entry.get("title", "")}
                            cache.set("wind_down_video", wind_down_video, ttl=3600)
            except Exception:
                pass

    # Suggested YouTube channels for this time period
    time_youtube = []
    for cat in suggested_categories:
        time_youtube.extend(models.get_youtube_channels(category=cat))

    # Additional category rows
    crime_youtube = models.get_youtube_channels(category="Crime & Drama")
    comedy_youtube = models.get_youtube_channels(category="Comedy")
    local_youtube = (models.get_youtube_channels(category="Local News")
                     + models.get_youtube_channels(category="Morning Shows"))

    # 5-day weather forecast
    forecast = []
    try:
        lat = get_setting_or_default("weather_lat")
        lon = get_setting_or_default("weather_lon")
        unit = get_setting_or_default("weather_unit")
        temp_unit = "fahrenheit" if unit == "fahrenheit" else "celsius"

        forecast_cached = cache.get("forecast_5day")
        if forecast_cached:
            forecast = forecast_cached
        else:
            resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                    "temperature_unit": temp_unit, "timezone": "auto", "forecast_days": 5,
                },
                timeout=5,
            )
            data = resp.json()
            for i in range(5):
                day_name = datetime.strptime(data["daily"]["time"][i], "%Y-%m-%d").strftime("%a")
                if i == 0:
                    day_name = "Today"
                forecast.append({
                    "day": day_name,
                    "high": round(data["daily"]["temperature_2m_max"][i]),
                    "low": round(data["daily"]["temperature_2m_min"][i]),
                    "icon": weather_code_to_icon(data["daily"]["weather_code"][i]),
                })
            cache.set("forecast_5day", forecast, ttl=1800)
    except Exception:
        pass

    # Next calendar event
    upcoming = models.get_upcoming_events(days=7)
    next_event = upcoming[0] if upcoming else None

    # Random family photo for home page widget
    home_photo = None
    try:
        import immich_api
        if immich_api.is_configured():
            photos = immich_api.get_random_photos(count=5)
            if photos:
                home_photo = photos[0]
    except Exception:
        pass

    return render_template(
        "tv/home.html",
        greeting=greeting,
        date_str=date_str,
        time_str=time_str,
        weather=weather,
        weather_icon=weather_icon,
        next_pill=next_pill,
        menu_items=menu_items,
        jf_recommendations=jf_recommendations[:20],
        la_news_video_id=la_news_video_id,
        wind_down_video=wind_down_video,
        next_event=next_event,
        time_period=time_period,
        time_youtube=time_youtube[:10],
        crime_youtube=crime_youtube,
        comedy_youtube=comedy_youtube,
        local_youtube=local_youtube[:8],
        suggested_pluto=suggested_pluto,
        unread_msgs=unread_msgs,
        day_of_year=day_of_year,
        holidays_today=holidays_today,
        forecast=forecast,
        home_photo=home_photo,
    )


@app.route("/tv/weather")
def tv_weather():
    try:
        lat = get_setting_or_default("weather_lat")
        lon = get_setting_or_default("weather_lon")
        unit = get_setting_or_default("weather_unit")
        temp_unit = "fahrenheit" if unit == "fahrenheit" else "celsius"
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "temperature_unit": temp_unit,
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 5,
            },
            timeout=10,
        )
        data = resp.json()
        symbol = "°F" if unit == "fahrenheit" else "°C"

        current = {
            "temp": round(data["current"]["temperature_2m"]),
            "condition": weather_code_to_text(data["current"]["weather_code"]),
            "icon": weather_code_to_icon(data["current"]["weather_code"]),
            "humidity": data["current"]["relative_humidity_2m"],
            "wind": round(data["current"]["wind_speed_10m"]),
            "symbol": symbol,
        }

        forecast = []
        for i in range(5):
            day_name = datetime.strptime(data["daily"]["time"][i], "%Y-%m-%d").strftime("%A")
            if i == 0:
                day_name = "Today"
            forecast.append({
                "day": day_name,
                "high": round(data["daily"]["temperature_2m_max"][i]),
                "low": round(data["daily"]["temperature_2m_min"][i]),
                "icon": weather_code_to_icon(data["daily"]["weather_code"][i]),
                "condition": weather_code_to_text(data["daily"]["weather_code"][i]),
                "symbol": symbol,
            })

        return render_template("tv/weather.html", current=current, forecast=forecast)
    except Exception as e:
        return render_template("tv/weather.html", current=None, forecast=[], error=str(e))


@app.route("/tv/news")
def tv_news():
    """News page with live video streams and headlines."""
    import re as _re

    # YouTube live news streams — we scrape the current video ID from channel /live pages
    live_streams = []
    yt_channels = [
        ("ABC News", "https://www.youtube.com/@ABCNews/live"),
        ("NBC News NOW", "https://www.youtube.com/@NBCNews/live"),
        ("CBS News", "https://www.youtube.com/@CBSNews/live"),
        ("FOX 11 Los Angeles", "https://www.youtube.com/@FOX11LosAngeles/live"),
    ]
    for name, url in yt_channels:
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            match = _re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
            if match:
                live_streams.append({
                    "name": name,
                    "video_id": match.group(1),
                    "type": "youtube",
                })
        except Exception:
            continue

    # Also include Pluto TV news channels for quick access
    pluto_news = []
    try:
        import pluto_tv
        channels, _ = pluto_tv.get_channels(category_filter="News + Opinion")
        for ch in channels[:6]:
            pluto_news.append({
                "name": ch["name"],
                "id": ch["id"],
                "logo": ch.get("logo", ""),
                "current_program": ch.get("current_program"),
            })
    except Exception:
        pass

    # RSS headlines as supplementary
    feeds_str = get_setting_or_default("news_feeds")
    feed_urls = [u.strip() for u in feeds_str.split(",") if u.strip()]
    articles = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:200],
                    "source": feed.feed.get("title", "News"),
                })
        except Exception:
            continue

    return render_template("tv/news.html", live_streams=live_streams,
                           pluto_news=pluto_news, articles=articles[:10])


@app.route("/tv/news/youtube/<video_id>")
def tv_news_youtube(video_id):
    """Watch a YouTube live news stream."""
    # Sanitize video_id
    import re as _re
    if not _re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        return redirect("/tv/news")
    return render_template("tv/news_player.html", video_id=video_id)


@app.route("/tv/calendar")
def tv_calendar():
    import calendar as cal_mod
    view = request.args.get("view", "daily")
    now = datetime.now()
    events = models.get_upcoming_events(days=60)

    if view == "daily":
        today_str = now.strftime("%A, %B %d, %Y")
        today_date = now.strftime("%Y-%m-%d")
        today_events = [e for e in events if e["event_date"] == today_date]
        # Build hourly timeline 6am to 10pm
        day_hours = []
        for h in range(6, 23):
            ampm = f"{h % 12 or 12}:00 {'AM' if h < 12 else 'PM'}"
            hour_events = [e for e in today_events if e.get("event_time", "").startswith(f"{h:02d}:")]
            day_hours.append({"label": ampm, "events": hour_events})
        return render_template("tv/calendar.html", view="daily", today_str=today_str,
                               day_hours=day_hours, events=events)

    elif view == "monthly":
        month_name = now.strftime("%B")
        year = now.year
        month = now.month
        weekday_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        # Build month grid
        first_day = datetime(year, month, 1)
        first_weekday = (first_day.weekday() + 1) % 7  # 0=Sun
        days_in_month = cal_mod.monthrange(year, month)[1]
        event_dates = {e["event_date"] for e in events}

        month_days = []
        for _ in range(first_weekday):
            month_days.append({"num": None, "is_today": False, "has_event": False})
        for d in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{d:02d}"
            month_days.append({
                "num": d,
                "is_today": d == now.day,
                "has_event": date_str in event_dates,
            })

        return render_template("tv/calendar.html", view="monthly", month_name=month_name,
                               year=year, weekday_labels=weekday_labels, month_days=month_days,
                               events=events)
    else:
        events = models.get_upcoming_events(days=365)
        return render_template("tv/calendar.html", view="upcoming", events=events)


# --- Plex Integration ---

def _get_jellyfin():
    """Get a JellyfinAPI instance from settings."""
    from jellyfin_api import JellyfinAPI
    url = get_setting_or_default("jellyfin_url")
    api_key = get_setting_or_default("jellyfin_api_key")
    user_id = get_setting_or_default("jellyfin_user_id")
    if not url or not api_key or not user_id:
        return None
    return JellyfinAPI(url, api_key, user_id)


@app.route("/tv/plex")
def tv_plex():
    """Media library browser (Jellyfin-powered)."""
    jf = _get_jellyfin()
    if not jf:
        return render_template("tv/plex.html", libraries=[], on_deck=[], recent=[],
                               error="Media server not configured. Ask your family member to set it up in the admin panel.")

    try:
        libraries = jf.get_libraries()
        on_deck = jf.get_resume(limit=10)
        recent = jf.get_latest(limit=20)
        return render_template("tv/plex.html", libraries=libraries, on_deck=on_deck, recent=recent, error=None)
    except Exception as e:
        return render_template("tv/plex.html", libraries=[], on_deck=[], recent=[], error=str(e))


@app.route("/tv/plex/library/<library_id>")
def tv_plex_library(library_id):
    """Browse items in a Jellyfin library with genre filtering and sorting."""
    jf = _get_jellyfin()
    if not jf:
        return redirect("/tv/plex")

    genre = request.args.get("genre")
    sort = request.args.get("sort", "SortName")
    try:
        page = int(request.args.get("page", 0))
    except (ValueError, TypeError):
        page = 0
    per_page = 40

    SORT_OPTIONS = [
        ("SortName", "Ascending", "A - Z"),
        ("SortName", "Descending", "Z - A"),
        ("DateCreated", "Descending", "Recently Added"),
        ("CommunityRating", "Descending", "Top Rated"),
        ("ProductionYear", "Descending", "Newest"),
        ("ProductionYear", "Ascending", "Oldest"),
        ("Random", "Ascending", "Surprise Me"),
    ]
    sort_order = "Ascending"
    sort_label = "A - Z"
    for s_key, s_order, s_label in SORT_OPTIONS:
        if s_key == sort:
            sort_order = request.args.get("order", s_order)
            sort_label = s_label
            break

    try:
        genres = jf.get_genres(library_id)
        items = jf.get_library_items(library_id, sort=sort, sort_order=sort_order,
                                     genre=genre, limit=per_page, start=page * per_page)
        libraries = jf.get_libraries()
        lib_name = next((lib["title"] for lib in libraries if lib["id"] == library_id), "Library")
        has_more = len(items) == per_page

        return render_template("tv/plex_browse.html", items=items, library_name=lib_name,
                               library_id=library_id, genres=genres, selected_genre=genre,
                               sort_options=SORT_OPTIONS, selected_sort=sort, sort_label=sort_label,
                               page=page, has_more=has_more)
    except Exception as e:
        return render_template("tv/plex_browse.html", items=[], library_name="Library",
                               library_id=library_id, genres=[], selected_genre=None,
                               sort_options=[], selected_sort="SortName", sort_label="A-Z",
                               page=0, has_more=False, error=str(e))


@app.route("/tv/plex/daily")
def tv_plex_daily():
    """Today's 20 movies — different every day."""
    jf = _get_jellyfin()
    if not jf:
        return redirect("/tv/plex")

    try:
        libs = jf.get_libraries()
        movies_lib = next((lib for lib in libs if lib["type"] == "movies"), None)
        if not movies_lib:
            return redirect("/tv/plex")
        movies = jf.get_daily_picks(movies_lib["id"], count=20)
        from datetime import date
        today_str = date.today().strftime("%A, %B %d")
        return render_template("tv/plex_daily.html", movies=movies, today_str=today_str)
    except Exception as e:
        return render_template("tv/plex_daily.html", movies=[], today_str="Today", error=str(e))


@app.route("/tv/plex/shuffle/<item_id>")
def tv_plex_shuffle(item_id):
    """Play a random episode from a TV show."""
    jf = _get_jellyfin()
    if not jf:
        return redirect("/tv/plex")

    try:
        episode = jf.get_random_episode(item_id)
        if episode:
            stream_url = jf.get_stream_url(episode["id"])
            transcode_url = jf.get_transcode_url(episode["id"])
            subtitle_url = jf.get_subtitle_url(episode["id"])
            return render_template("tv/player.html", item=episode, stream_url=stream_url,
                                   transcode_url=transcode_url, subtitle_url=subtitle_url,
                                   item_id=episode["id"])
        return redirect(f"/tv/plex/show/{item_id}")
    except Exception:
        return redirect(f"/tv/plex/show/{item_id}")


@app.route("/tv/plex/show/<item_id>")
def tv_plex_show(item_id):
    """Show seasons and episodes for a TV show."""
    jf = _get_jellyfin()
    if not jf:
        return redirect("/tv/plex")

    try:
        show = jf.get_item(item_id)
        seasons = jf.get_seasons(item_id)
        selected_season = request.args.get("season")
        episodes = []
        season_id = None
        if seasons:
            season_id = selected_season or seasons[0]["id"]
            episodes = jf.get_episodes(item_id, season_id)
        return render_template("tv/plex_show.html", show=show, seasons=seasons,
                               episodes=episodes, selected_season=season_id)
    except Exception as e:
        return render_template("tv/plex_show.html", show=None, seasons=[], episodes=[], selected_season=None, error=str(e))


@app.route("/tv/plex/play/<item_id>")
def tv_plex_play(item_id):
    """Play a Jellyfin item in our built-in player."""
    jf = _get_jellyfin()
    if not jf:
        return redirect("/tv/plex")

    try:
        item = jf.get_item(item_id)
        stream_url = jf.get_stream_url(item_id)
        transcode_url = jf.get_transcode_url(item_id)
        subtitle_url = jf.get_subtitle_url(item_id)
        jf.report_playback_start(item_id)
        return render_template("tv/player.html", item=item, stream_url=stream_url,
                               transcode_url=transcode_url, subtitle_url=subtitle_url,
                               item_id=item_id)
    except Exception:
        return redirect("/tv/plex")


# --- Family Messages ---

@app.route("/tv/messages")
def tv_messages():
    """View family messages on the TV."""
    messages = models.get_messages(limit=20)
    unread = models.get_unread_count()
    return render_template("tv/messages.html", messages=messages, unread=unread)


@app.route("/tv/messages/<int:msg_id>")
def tv_message_view(msg_id):
    """View a single message full-screen."""
    msg = models.get_message(msg_id)
    if not msg:
        return redirect("/tv/messages")
    models.mark_message_read(msg_id)
    return render_template("tv/message_view.html", message=msg)


# --- Pluto TV Live Channels ---

@app.route("/tv/live")
def tv_live():
    """Live TV channel guide powered by Pluto TV."""
    import pluto_tv
    category = request.args.get("category")
    channels, error = pluto_tv.get_channels(category_filter=category)
    categories, _ = pluto_tv.get_categories()
    return render_template("tv/live.html", channels=channels, categories=categories,
                           selected_category=category, error=error)


@app.route("/tv/live/play/<channel_id>")
def tv_live_play(channel_id):
    """Play a live Pluto TV channel."""
    import pluto_tv
    # Force fresh session token
    pluto_tv.SESSION_CACHE["token"] = None
    channel, error = pluto_tv.get_channel_by_id(channel_id)
    if not channel:
        return redirect("/tv/live")
    return render_template("tv/live_player.html", channel=channel)


@app.route("/api/pluto-stream/<channel_id>")
def pluto_stream_master(channel_id):
    """Proxy Pluto TV master m3u8, rewriting URLs to go through our proxy."""
    import pluto_tv
    from urllib.parse import urljoin, quote
    pluto_tv.SESSION_CACHE["token"] = None
    channel, error = pluto_tv.get_channel_by_id(channel_id)
    if not channel:
        return "", 404
    try:
        stream_url = channel["stream_url"]
        resp = requests.get(stream_url, timeout=15)
        base_url = stream_url.rsplit("/", 1)[0] + "/"

        rewritten = _rewrite_m3u8(resp.text, base_url)
        return Response(rewritten, mimetype="application/x-mpegurl",
                        headers={"Access-Control-Allow-Origin": "*"})
    except Exception:
        return "", 502


def _rewrite_m3u8(content, base_url):
    """Rewrite m3u8 playlist URLs to go through our proxy."""
    from urllib.parse import urljoin, quote
    lines = content.split("\n")
    rewritten = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if stripped.startswith("http"):
                abs_url = stripped
            else:
                abs_url = urljoin(base_url, stripped)
            rewritten.append(f"/api/pluto-proxy?url={quote(abs_url, safe='')}")
        elif stripped.startswith("#") and "URI=" in stripped:
            # Rewrite URI= in #EXT tags (subtitles, etc.)
            import re as _re
            def rewrite_uri(m):
                uri = m.group(1)
                if uri.startswith("http"):
                    abs_uri = uri
                else:
                    abs_uri = urljoin(base_url, uri)
                return f'URI="/api/pluto-proxy?url={quote(abs_uri, safe="")}"'
            rewritten.append(_re.sub(r'URI="([^"]*)"', rewrite_uri, stripped))
        else:
            rewritten.append(line)
    return "\n".join(rewritten)


@app.route("/api/pluto-proxy")
def pluto_proxy():
    """Proxy any Pluto TV URL (segments, sub-playlists) to bypass CORS."""
    from urllib.parse import urljoin, quote
    url = request.args.get("url")
    if not url or not any(d in url for d in ("pluto.tv", "plutotv.com", "pluto-prod-")):
        return "", 403
    try:
        resp = requests.get(url, timeout=15, stream=True)
        content_type = resp.headers.get("content-type", "application/octet-stream")

        if "mpegurl" in content_type or ".m3u8" in url:
            base_url = url.rsplit("/", 1)[0] + "/"
            rewritten = _rewrite_m3u8(resp.text, base_url)
            return Response(rewritten, mimetype="application/x-mpegurl",
                            headers={"Access-Control-Allow-Origin": "*"})
        else:
            return Response(resp.content, mimetype=content_type,
                            headers={"Access-Control-Allow-Origin": "*"})
    except Exception:
        return "", 502


# --- YouTube ---

@app.route("/tv/youtube")
def tv_youtube():
    """YouTube viewer with curated channels."""
    yt_channels = models.get_youtube_channels()
    # Group by category
    categories = {}
    for ch in yt_channels:
        cat = ch.get("category", "Entertainment")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ch)

    # Also add local live streams
    local_streams = _get_local_live_streams()

    return render_template("tv/youtube.html", categories=categories,
                           local_streams=local_streams, channels=yt_channels)


def _get_local_live_streams():
    """Get current live YouTube streams for local LA/SD stations."""
    import re as _re
    streams = []
    local_channels = [
        ("ABC 7 Los Angeles", "https://www.youtube.com/@abc7/live"),
        ("FOX 11 Los Angeles", "https://www.youtube.com/@FOX11LosAngeles/live"),
        ("NBC Los Angeles", "https://www.youtube.com/@ABORABLE/live"),
        ("CBS 8 San Diego", "https://www.youtube.com/@CBS8/live"),
    ]
    for name, url in local_channels:
        try:
            r = requests.get(url, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
            match = _re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
            if match and "isLive" in r.text:
                streams.append({"name": name, "video_id": match.group(1)})
        except Exception:
            continue
    return streams


@app.route("/tv/youtube/channel/<channel_id>")
def tv_youtube_channel(channel_id):
    """Browse a YouTube channel's recent videos."""
    import re as _re
    # Fetch channel page for recent uploads
    ch_record = None
    yt_channels = models.get_youtube_channels()
    for ch in yt_channels:
        if ch["channel_id"] == channel_id:
            ch_record = ch
            break

    channel_name = ch_record["name"] if ch_record else "YouTube"

    # Fetch recent videos via RSS (no API key needed)
    videos = []
    try:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:20]:
            # Try yt:videoId tag first, then URL param
            vid_id = entry.get("yt_videoid", "")
            if not vid_id:
                vid_match = _re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', entry.get("link", ""))
                vid_id = vid_match.group(1) if vid_match else ""
            thumb = f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""
            videos.append({
                "title": entry.get("title", ""),
                "video_id": vid_id,
                "thumbnail": thumb,
                "published": entry.get("published", ""),
            })
    except Exception:
        pass

    return render_template("tv/youtube_channel.html", channel_name=channel_name,
                           channel_id=channel_id, videos=videos)


@app.route("/tv/youtube/watch/<video_id>")
def tv_youtube_watch(video_id):
    """Watch a YouTube video."""
    import re as _re
    if not _re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        return redirect("/tv/youtube")
    return render_template("tv/youtube_player.html", video_id=video_id)


# --- YouTube Admin ---

@app.route("/admin/youtube")
def admin_youtube():
    channels = models.get_youtube_channels()
    return render_template("admin/youtube.html", channels=channels)


@app.route("/admin/youtube/new", methods=["GET", "POST"])
def admin_youtube_new():
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "channel_id": request.form["channel_id"],
            "description": request.form.get("description", ""),
            "thumbnail_url": request.form.get("thumbnail_url", ""),
            "category": request.form.get("category", "Entertainment"),
            "sort_order": int(request.form.get("sort_order", 0)),
        }
        models.create_youtube_channel(data)
        return redirect("/admin/youtube")
    return render_template("admin/youtube_form.html", channel=None)


@app.route("/admin/youtube/<int:ch_id>/edit", methods=["GET", "POST"])
def admin_youtube_edit(ch_id):
    ch = models.get_youtube_channel(ch_id)
    if not ch:
        return redirect("/admin/youtube")
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "channel_id": request.form["channel_id"],
            "description": request.form.get("description", ""),
            "thumbnail_url": request.form.get("thumbnail_url", ""),
            "category": request.form.get("category", "Entertainment"),
            "sort_order": int(request.form.get("sort_order", 0)),
        }
        models.update_youtube_channel(ch_id, data)
        return redirect("/admin/youtube")
    return render_template("admin/youtube_form.html", channel=ch)


@app.route("/admin/youtube/<int:ch_id>/delete", methods=["POST"])
def admin_youtube_delete(ch_id):
    models.delete_youtube_channel(ch_id)
    return redirect("/admin/youtube")


# --- SSE endpoint for pill reminders ---

@app.route("/events")
def sse_events():
    def stream():
        while True:
            try:
                event = reminder_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
            except Exception:
                yield ": keepalive\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/acknowledge", methods=["POST"])
def api_acknowledge():
    data = request.get_json()
    reminder_id = data.get("reminder_id")
    if reminder_id and acknowledge_reminder(reminder_id):
        return jsonify({"status": "ok"})
    return jsonify({"status": "not_found"}), 404


# ========================================
# Admin Panel Routes
# ========================================

@app.route("/admin")
def admin_dashboard():
    pills = models.get_pills()
    for pill in pills:
        pill["schedule_times_display"] = ", ".join(json.loads(pill["schedule_times"]))
    events = models.get_upcoming_events(days=14)
    settings = models.get_all_settings()
    return render_template("admin/dashboard.html", pills=pills, events=events, settings=settings)


# --- Pills CRUD ---

@app.route("/admin/pills")
def admin_pills():
    pills = models.get_pills()
    for pill in pills:
        pill["schedule_times_display"] = ", ".join(json.loads(pill["schedule_times"]))
        days = json.loads(pill["schedule_days"])
        pill["schedule_days_display"] = ", ".join(d.capitalize() for d in days)
    return render_template("admin/pills.html", pills=pills)


@app.route("/admin/pills/new", methods=["GET", "POST"])
def admin_pill_new():
    if request.method == "POST":
        data = _parse_pill_form(request)
        models.create_pill(data)
        return redirect("/admin/pills")
    return render_template("admin/pill_form.html", pill=None)


@app.route("/admin/pills/<int:pill_id>/edit", methods=["GET", "POST"])
def admin_pill_edit(pill_id):
    pill = models.get_pill(pill_id)
    if not pill:
        return redirect("/admin/pills")
    if request.method == "POST":
        data = _parse_pill_form(request)
        models.update_pill(pill_id, data)
        return redirect("/admin/pills")
    pill["schedule_times"] = json.loads(pill["schedule_times"])
    pill["schedule_days"] = json.loads(pill["schedule_days"])
    return render_template("admin/pill_form.html", pill=pill)


@app.route("/admin/pills/<int:pill_id>/delete", methods=["POST"])
def admin_pill_delete(pill_id):
    models.delete_pill(pill_id)
    return redirect("/admin/pills")


def _parse_pill_form(req):
    media_file = req.files.get("reminder_media_file")
    media_filename = None
    if media_file and media_file.filename:
        media_filename = secure_filename(media_file.filename)
        media_file.save(os.path.join(config.MEDIA_DIR, media_filename))

    times = [t.strip() for t in req.form.get("schedule_times", "").split(",") if t.strip()]
    days = req.form.getlist("schedule_days") or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    data = {
        "name": req.form["name"],
        "dosage": req.form.get("dosage", ""),
        "instructions": req.form.get("instructions", ""),
        "schedule_times": times,
        "schedule_days": days,
        "reminder_type": req.form.get("reminder_type", "text"),
        "reminder_message": req.form.get("reminder_message", ""),
        "enabled": 1 if req.form.get("enabled") else 0,
    }
    if media_filename:
        data["reminder_media"] = media_filename
    return data


# --- Calendar CRUD ---

@app.route("/admin/calendar")
def admin_calendar():
    events = models.get_all_events()
    return render_template("admin/calendar.html", events=events)


@app.route("/admin/calendar/new", methods=["GET", "POST"])
def admin_event_new():
    if request.method == "POST":
        data = {
            "title": request.form["title"],
            "description": request.form.get("description", ""),
            "event_date": request.form["event_date"],
            "event_time": request.form.get("event_time") or None,
            "recurring": request.form.get("recurring") or None,
        }
        models.create_event(data)
        return redirect("/admin/calendar")
    return render_template("admin/event_form.html", event=None)


@app.route("/admin/calendar/<int:event_id>/edit", methods=["GET", "POST"])
def admin_event_edit(event_id):
    event = models.get_event(event_id)
    if not event:
        return redirect("/admin/calendar")
    if request.method == "POST":
        data = {
            "title": request.form["title"],
            "description": request.form.get("description", ""),
            "event_date": request.form["event_date"],
            "event_time": request.form.get("event_time") or None,
            "recurring": request.form.get("recurring") or None,
        }
        models.update_event(event_id, data)
        return redirect("/admin/calendar")
    return render_template("admin/event_form.html", event=event)


@app.route("/admin/calendar/<int:event_id>/delete", methods=["POST"])
def admin_event_delete(event_id):
    models.delete_event(event_id)
    return redirect("/admin/calendar")


# --- Jellyfin Setup ---

@app.route("/admin/plex-setup", methods=["GET", "POST"])
def admin_jellyfin_setup():
    message = None
    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_url":
            models.set_setting("jellyfin_url", request.form.get("jellyfin_url", "").rstrip("/"))
            return redirect("/admin/plex-setup")

        elif action == "authenticate":
            from jellyfin_api import JellyfinAPI
            url = get_setting_or_default("jellyfin_url")
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if url and username:
                try:
                    jf = JellyfinAPI(url)
                    result = jf.authenticate(username, password)
                    models.set_setting("jellyfin_api_key", result["api_key"])
                    models.set_setting("jellyfin_user_id", result["user_id"])
                    message = f"Logged in as {result['user_name']}!"
                except Exception as e:
                    message = f"Login failed: {e}"
            return redirect("/admin/plex-setup")

    jellyfin_url = get_setting_or_default("jellyfin_url")
    api_key = get_setting_or_default("jellyfin_api_key")
    user_id = get_setting_or_default("jellyfin_user_id")

    connection = None
    libraries = []
    if jellyfin_url and api_key and user_id:
        jf = _get_jellyfin()
        if jf:
            connection = jf.test_connection()
            if connection.get("ok"):
                try:
                    libraries = jf.get_libraries()
                except Exception:
                    pass

    return render_template("admin/plex_setup.html", jellyfin_url=jellyfin_url,
                           api_key=api_key, user_id=user_id,
                           connection=connection, libraries=libraries, message=message)


# --- Family Messages Admin ---

@app.route("/admin/messages")
def admin_messages():
    messages = models.get_messages(limit=50)
    return render_template("admin/messages.html", messages=messages)


@app.route("/admin/messages/send", methods=["GET", "POST"])
def admin_message_send():
    if request.method == "POST":
        media_file = request.files.get("media_file")
        media_filename = None
        media_type = "text"

        if media_file and media_file.filename:
            media_filename = secure_filename(media_file.filename)
            media_file.save(os.path.join(config.MEDIA_DIR, media_filename))
            ext = media_filename.rsplit(".", 1)[-1].lower()
            if ext in ("jpg", "jpeg", "png", "gif", "webp"):
                media_type = "image"
            elif ext in ("mp4", "webm", "mov"):
                media_type = "video"

        msg_id = models.create_message({
            "sender": request.form.get("sender", "Family"),
            "message": request.form.get("message", ""),
            "media_type": media_type,
            "media_file": media_filename,
        })

        # Push notification to TV via SSE
        reminder_queue.put({
            "type": "family_message",
            "msg_id": msg_id,
            "sender": request.form.get("sender", "Family"),
            "message": request.form.get("message", "")[:100],
        })

        return redirect("/admin/messages")
    return render_template("admin/message_form.html")


@app.route("/admin/messages/<int:msg_id>/delete", methods=["POST"])
def admin_message_delete(msg_id):
    models.delete_message(msg_id)
    return redirect("/admin/messages")


# --- Birthdays ---

@app.route("/admin/birthdays")
def admin_birthdays():
    birthdays = models.get_birthdays()
    return render_template("admin/birthdays.html", birthdays=birthdays)


@app.route("/admin/birthdays/new", methods=["GET", "POST"])
def admin_birthday_new():
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "birth_date": request.form["birth_date"],  # MM-DD
            "birth_year": int(request.form["birth_year"]) if request.form.get("birth_year") else None,
            "relationship": request.form.get("relationship", ""),
        }
        models.create_birthday(data)
        return redirect("/admin/birthdays")
    return render_template("admin/birthday_form.html", birthday=None)


@app.route("/admin/birthdays/<int:b_id>/delete", methods=["POST"])
def admin_birthday_delete(b_id):
    models.delete_birthday(b_id)
    return redirect("/admin/birthdays")


# --- Favorite Shows ---

@app.route("/admin/shows")
def admin_shows():
    shows = models.get_favorite_shows()
    return render_template("admin/shows.html", shows=shows)


@app.route("/admin/shows/new", methods=["GET", "POST"])
def admin_show_new():
    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "search_term": request.form["search_term"],
            "enabled": 1 if request.form.get("enabled") else 0,
        }
        models.create_favorite_show(data)
        return redirect("/admin/shows")
    return render_template("admin/show_form.html", show=None)


@app.route("/admin/shows/<int:s_id>/delete", methods=["POST"])
def admin_show_delete(s_id):
    models.delete_favorite_show(s_id)
    return redirect("/admin/shows")


# --- Settings ---

@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    if request.method == "POST":
        for key in ["greeting_names", "weather_lat", "weather_lon", "weather_unit",
                     "news_feeds", "jellyfin_url",
                     "frigate_url", "frigate_user", "frigate_pass", "frigate_cameras",
                     "ha_url", "ha_token", "photo_interval", "photo_nas_path"]:
            val = request.form.get(key)
            if val is not None:
                models.set_setting(key, val)
        return redirect("/admin/settings")
    settings = {}
    for key in config.DEFAULTS:
        settings[key] = get_setting_or_default(key)
    return render_template("admin/settings.html", settings=settings)


# --- API for TV UI ---

@app.route("/api/home-data")
def api_home_data():
    """AJAX endpoint so the TV home screen can refresh without full reload."""
    return jsonify({
        "greeting": get_greeting(),
        "date": datetime.now().strftime("%A, %B %d"),
        "weather": get_weather_summary(),
        "next_pill": get_next_pill_info(),
        "active_reminders": list(get_active_reminders().values()),
    })


@app.route("/api/trigger-reminder/<int:pill_id>", methods=["POST"])
def api_trigger_test_reminder(pill_id):
    """Admin: trigger a test reminder for a pill."""
    from scheduler import trigger_reminder
    pill = models.get_pill(pill_id)
    if pill:
        trigger_reminder(pill, "test")
        return jsonify({"status": "triggered"})
    return jsonify({"status": "not_found"}), 404


# --- Frigate snapshot proxy ---

@app.route("/api/frigate-snapshot/<path:path>")
def frigate_snapshot_proxy(path):
    """Proxy Frigate snapshots to avoid CORS/HTTPS issues."""
    frigate_url = get_setting_or_default("frigate_url")
    if not frigate_url:
        return "", 404
    try:
        from smart_home import _frigate_cookies
        resp = requests.get(
            f"{frigate_url}/api/{path}",
            cookies=_frigate_cookies,
            verify=False,
            timeout=10,
        )
        return Response(resp.content, mimetype=resp.headers.get("content-type", "image/jpeg"))
    except Exception:
        return "", 404


# --- Photo Gallery ---

@app.route("/tv/photos")
def tv_photos():
    """Photo frame / gallery slideshow."""
    import immich_api
    photos = _get_all_photos()
    has_immich = immich_api.is_configured()
    if not photos and not has_immich and not request.args.get("screensaver"):
        return render_template("tv/photos.html", photos=photos, has_immich=False, interval=10)
    if not photos and not has_immich and request.args.get("screensaver"):
        return redirect("/")
    interval = int(get_setting_or_default("photo_interval") or 10)
    return render_template("tv/photos.html", photos=photos, has_immich=has_immich, interval=interval)


@app.route("/admin/photos", methods=["GET", "POST"])
def admin_photos():
    if request.method == "POST":
        files = request.files.getlist("photos")
        for f in files:
            if f and f.filename:
                filename = secure_filename(f.filename)
                f.save(os.path.join(config.MEDIA_DIR, "photos", filename))
        return redirect("/admin/photos")

    photos = _get_all_photos()
    return render_template("admin/photos.html", photos=photos)


@app.route("/admin/photos/delete/<filename>", methods=["POST"])
def admin_photo_delete(filename):
    safe_name = secure_filename(filename)
    path = os.path.join(config.MEDIA_DIR, "photos", safe_name)
    if os.path.exists(path):
        os.remove(path)
    return redirect("/admin/photos")


def _get_all_photos():
    """Get all photos from the upload folder and optional NAS path."""
    photos = []
    # Uploaded photos
    photo_dir = os.path.join(config.MEDIA_DIR, "photos")
    os.makedirs(photo_dir, exist_ok=True)
    for f in sorted(os.listdir(photo_dir)):
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            photos.append({"url": f"/static/media/photos/{f}", "name": f, "source": "upload"})

    # NAS photos
    nas_path = get_setting_or_default("photo_nas_path")
    if nas_path and os.path.isdir(nas_path):
        for f in sorted(os.listdir(nas_path))[:200]:  # Limit to 200
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                photos.append({"url": f"/api/nas-photo/{f}", "name": f, "source": "nas"})

    # Immich photos
    import immich_api
    if immich_api.is_configured():
        photos.extend(immich_api.get_random_photos(count=30))

    return photos


@app.route("/api/has-photos")
def api_has_photos():
    import immich_api
    photos = _get_all_photos()
    has = len(photos) > 0 or immich_api.get_photo_count() > 0
    return jsonify({"has_photos": has})


@app.route("/api/nas-photo/<filename>")
def nas_photo(filename):
    """Serve a photo from the NAS path."""
    nas_path = get_setting_or_default("photo_nas_path")
    if not nas_path:
        return "", 404
    safe_name = secure_filename(filename)
    return send_from_directory(nas_path, safe_name)


@app.route("/api/immich-photo/<asset_id>")
def immich_photo_proxy(asset_id):
    """Proxy an Immich photo to avoid exposing the API key to the browser."""
    import re
    if not re.match(r'^[a-f0-9-]{36}$', asset_id):
        return "", 400
    size = request.args.get("size", "preview")
    if size not in ("preview", "thumbnail"):
        size = "preview"

    import immich_api
    data, content_type = immich_api.get_photo_data(asset_id, size=size)
    if data is None:
        return "", 404
    response = app.response_class(data, mimetype=content_type)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/api/immich-slideshow")
def api_immich_slideshow():
    """Get a batch of random Immich photos for the slideshow."""
    import immich_api
    try:
        count = min(int(request.args.get("count", 20)), 50)
    except (ValueError, TypeError):
        count = 20
    # Bypass cache to get fresh random photos
    cache.set("immich_random_20", None, ttl=0)
    photos = immich_api.get_random_photos(count=count)
    return jsonify(photos)


# --- Daily Digest API ---

@app.route("/api/daily-digest")
def api_daily_digest():
    """Get this day in history and a daily quote."""
    digest = {}

    # This Day in History (Wikipedia)
    try:
        now = datetime.now()
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{now.month}/{now.day}",
            headers={"User-Agent": "SeniorTV/1.0"},
            timeout=5,
        )
        if resp.status_code == 200:
            events = resp.json().get("selected", [])
            if events:
                import random
                event = random.choice(events[:10])
                digest["history"] = {
                    "year": event.get("year", ""),
                    "text": event.get("text", ""),
                }
    except Exception:
        pass

    # Daily quote — use /api/random for rotation, /api/today for daily
    try:
        fresh = request.args.get("fresh", "0") == "1"
        quote_url = "https://zenquotes.io/api/random" if fresh else "https://zenquotes.io/api/today"
        resp = requests.get(quote_url, timeout=5)
        if resp.status_code == 200:
            quotes = resp.json()
            if quotes:
                digest["quote"] = {
                    "text": quotes[0].get("q", ""),
                    "author": quotes[0].get("a", ""),
                }
    except Exception:
        pass

    return jsonify(digest)


@app.route("/api/health")
def api_health():
    """System health check for monitoring and watchdog."""
    import psutil

    health = {
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": int((datetime.now() - app_start_time).total_seconds()),
        "status": "ok",
        "checks": {},
    }

    # Disk
    disk = shutil.disk_usage("/")
    health["checks"]["disk"] = {
        "used_pct": round(disk.used / disk.total * 100, 1),
        "ok": disk.used / disk.total < 0.9,
    }

    # Memory
    mem = psutil.virtual_memory()
    health["checks"]["memory"] = {
        "used_pct": mem.percent,
        "ok": mem.percent < 85,
    }

    # Chrome process
    chrome_running = any(
        "senior-tv-chrome" in " ".join(p.info["cmdline"] or [])
        for p in psutil.process_iter(["cmdline"])
    )
    health["checks"]["chrome"] = {"running": chrome_running, "ok": chrome_running}

    # CEC
    cec_running = any(
        "cec_bridge" in " ".join(p.info["cmdline"] or [])
        for p in psutil.process_iter(["cmdline"])
    )
    cec_device = os.path.exists("/dev/cec0")
    health["checks"]["cec"] = {
        "bridge_running": cec_running,
        "device_exists": cec_device,
        "ok": True,
    }

    # Audio — check if HDMI is default sink
    try:
        result = subprocess.run(
            ["wpctl", "status"], capture_output=True, text=True, timeout=5
        )
        hdmi_default = False
        for line in result.stdout.split("\n"):
            if "*" in line and ("hdmi" in line.lower() or "rembrandt" in line.lower()):
                hdmi_default = True
                break
        health["checks"]["audio"] = {"hdmi_default": hdmi_default, "ok": hdmi_default}
    except Exception:
        health["checks"]["audio"] = {"hdmi_default": False, "ok": False}

    # Jellyfin
    try:
        jf_url = get_setting_or_default("jellyfin_url")
        resp = requests.get(f"{jf_url}/System/Ping", timeout=3)
        health["checks"]["jellyfin"] = {"reachable": resp.ok, "ok": resp.ok}
    except Exception:
        health["checks"]["jellyfin"] = {"reachable": False, "ok": False}

    # Internet
    try:
        requests.get("https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m", timeout=5)
        health["checks"]["internet"] = {"reachable": True, "ok": True}
    except Exception:
        health["checks"]["internet"] = {"reachable": False, "ok": False}

    # Tailscale
    try:
        ts = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=5)
        ts_state = json.loads(ts.stdout).get("BackendState", "")
        health["checks"]["tailscale"] = {"state": ts_state, "ok": ts_state == "Running"}
    except Exception:
        health["checks"]["tailscale"] = {"state": "unknown", "ok": False}

    # Watchdog repair count
    try:
        with open("/tmp/senior_tv_repair_count") as f:
            repair_count = int(f.read().strip())
    except Exception:
        repair_count = 0
    health["checks"]["watchdog"] = {"repairs_today": repair_count, "ok": repair_count < 20}

    # Scheduler
    from scheduler import scheduler as _sched
    health["checks"]["scheduler"] = {"running": _sched.running, "ok": _sched.running}

    # Immich
    try:
        import immich_api
        if immich_api.is_configured():
            ok, msg = immich_api.test_connection()
            health["checks"]["immich"] = {"connected": ok, "detail": msg, "ok": ok}
    except Exception:
        pass

    # Overall
    all_ok = all(c.get("ok", True) for c in health["checks"].values())
    health["status"] = "ok" if all_ok else "degraded"
    return jsonify(health)


# ========================================
# Startup
# ========================================

_smart_home_monitor = None

def _start_smart_home():
    """Start the Frigate doorbell monitor if configured."""
    global _smart_home_monitor
    frigate_url = get_setting_or_default("frigate_url")
    frigate_user = get_setting_or_default("frigate_user")
    frigate_pass = get_setting_or_default("frigate_pass")

    if frigate_url and frigate_user and frigate_pass:
        from smart_home import SmartHomeMonitor
        ha_url = get_setting_or_default("ha_url")
        ha_token = get_setting_or_default("ha_token")
        cameras_str = get_setting_or_default("frigate_cameras") or "front_door"
        cameras = [c.strip() for c in cameras_str.split(",")]

        _smart_home_monitor = SmartHomeMonitor(
            frigate_url, frigate_user, frigate_pass,
            ha_url, ha_token, reminder_queue, cameras,
        )
        _smart_home_monitor.start()
        print(f"Smart home monitor started (cameras: {cameras})")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    models.init_db()
    for key, val in config.DEFAULTS.items():
        if models.get_setting(key) is None:
            models.set_setting(key, val)
    start_scheduler()
    _start_smart_home()
    try:
        debug_mode = os.environ.get("SENIOR_TV_DEBUG", "0") == "1"
        app.run(host="0.0.0.0", port=5000, debug=debug_mode, threaded=True)
    finally:
        stop_scheduler()
        if _smart_home_monitor:
            _smart_home_monitor.stop()
