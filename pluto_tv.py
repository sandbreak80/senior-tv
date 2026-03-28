"""Pluto TV API client for Senior TV.

Fetches live channel listings and stream URLs from Pluto TV's free service.
Streams are HLS and play directly in HTML5 video.
"""

import time
import uuid
import threading
import requests
from datetime import datetime, timezone, timedelta

_session_lock = threading.Lock()
SESSION_CACHE = {"token": None, "stitcher": None, "stitcher_params": "", "acquired_at": 0}

# Refresh session proactively after 4 hours (tokens last ~24h but 4h is safest)
_SESSION_MAX_AGE = 4 * 3600

# Categories most relevant for seniors
PREFERRED_CATEGORIES = [
    "News + Opinion",
    "Local News",
    "Movies",
    "Classic TV",
    "Drama",
    "Comedy",
    "Daytime + Game Shows",
    "Entertainment",
    "True Crime",
    "Reality",
    "Home + Food",
    "Animals + Nature",
    "History + Science",
    "Sports",
    "Music Videos",
    "Westerns",
]


def _refresh_session():
    """Force refresh the Pluto TV session token."""
    with _session_lock:
        SESSION_CACHE["token"] = None
    return _get_session()


def _get_session():
    """Get a session token and stitcher URL from Pluto boot endpoint.

    Thread-safe: uses a lock to prevent concurrent boot API calls.
    Proactively refreshes tokens older than 4 hours.
    """
    with _session_lock:
        token = SESSION_CACHE["token"]
        age = time.time() - SESSION_CACHE["acquired_at"]
        if token and age < _SESSION_MAX_AGE:
            return token, SESSION_CACHE["stitcher"]
        # Token missing or expired — fetch new one (still under lock)
        resp = requests.get(
            "https://boot.pluto.tv/v4/start",
            params={
                "appName": "web",
                "appVersion": "9.0.0",
                "deviceVersion": "122.0.0",
                "deviceModel": "web",
                "deviceMake": "chrome",
                "deviceType": "web",
                "clientID": str(uuid.uuid4()),
                "clientModelNumber": "1.0",
                "serverSideAds": "false",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("sessionToken", "")
        stitcher = data.get("servers", {}).get("stitcher", "")
        stitcher_params = data.get("stitcherParams", "")
        SESSION_CACHE["token"] = token
        SESSION_CACHE["stitcher"] = stitcher
        SESSION_CACHE["stitcher_params"] = stitcher_params
        SESSION_CACHE["acquired_at"] = time.time()
        return token, stitcher


def invalidate_session():
    """Mark current session as expired so next call gets a fresh one."""
    with _session_lock:
        SESSION_CACHE["token"] = None
    import cache
    cache.clear("pluto_all_channels")


def get_channels(category_filter=None, include_all=False):
    """Fetch all Pluto TV channels with caching.

    Returns (channels_list, error_string).
    """
    import cache as _cache
    cache_key = "pluto_all_channels"

    # Always ensure we have a session
    try:
        token, stitcher = _get_session()
    except Exception as e:
        return [], str(e)

    cached = _cache.get(cache_key)
    if cached is None:
        try:
            # Include start/stop to get EPG timeline data
            now = datetime.now(timezone.utc)
            params = {
                "start": now.strftime("%Y-%m-%dT%H:00:00.000Z"),
                "stop": (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:00:00.000Z"),
            }
            def _fetch_channels(tk):
                return requests.get(
                    "https://api.pluto.tv/v2/channels",
                    headers={"Authorization": f"Bearer {tk}"},
                    params=params,
                    timeout=15,
                )
            resp = _fetch_channels(token)
            # Retry with fresh token on auth failure
            if resp.status_code == 401:
                token, stitcher = _refresh_session()
                resp = _fetch_channels(token)
            resp.raise_for_status()
            raw_channels = resp.json()
        except Exception as e:
            return [], str(e)
    else:
        raw_channels = cached

    # Read session values once (thread-safe snapshot)
    with _session_lock:
        stitcher_params = SESSION_CACHE.get("stitcher_params", "")

    channels = []
    for ch in raw_channels:
        if ch.get("visibility") == "hidden" or not ch.get("isStitched"):
            continue

        category = ch.get("category", "Other")
        if category_filter and category != category_filter:
            continue

        # Build the HLS stream URL
        slug = ch.get("slug", "")
        channel_id = ch.get("_id", "")

        if stitcher and slug:
            stream_url = f"{stitcher}/stitch/hls/channel/{channel_id}/master.m3u8?{stitcher_params}&jwt={token}"
        else:
            continue

        # Get logo (API uses "path" key, not "url")
        logo = ""
        for logo_key in ("colorLogoPNG", "logo", "solidLogoPNG"):
            logo_obj = ch.get(logo_key)
            if isinstance(logo_obj, dict):
                logo = logo_obj.get("path", "") or logo_obj.get("url", "")
            elif isinstance(logo_obj, str) and logo_obj:
                logo = logo_obj
            if logo:
                break

        # Get current program from the timelines if available
        current_program = None
        timelines = ch.get("timelines", [])
        now = datetime.now(timezone.utc)
        for tl in timelines:
            try:
                start = datetime.fromisoformat(tl["start"].replace("Z", "+00:00"))
                stop = datetime.fromisoformat(tl["stop"].replace("Z", "+00:00"))
                if start <= now <= stop:
                    ep = tl.get("episode", {})
                    current_program = {
                        "title": tl.get("title", ep.get("name", "")),
                        "description": ep.get("description", "")[:200],
                    }
                    break
            except (KeyError, ValueError):
                continue

        channels.append({
            "id": channel_id,
            "name": ch.get("name", ""),
            "slug": slug,
            "number": ch.get("number", 0),
            "category": category,
            "summary": (ch.get("summary") or "")[:150],
            "logo": logo,
            "stream_url": stream_url,
            "current_program": current_program,
        })

    # Filter out dead/test channels (skip when doing direct ID lookup)
    if not include_all:
        def _is_active(c):
            prog = c.get("current_program")
            if not prog:
                return False
            title = prog.get("title", "").lower()
            # Filter filler/test content
            if any(x in title for x in ["slate", "filler", "test", "off air", "c'est fini"]):
                return False
            return True
        channels = [c for c in channels if _is_active(c)]

    channels.sort(key=lambda c: c["number"])

    # Cache the raw channel data for 30 minutes
    if cached is None:
        _cache.set(cache_key, raw_channels, ttl=1800)

    return channels, None


def get_categories():
    """Get list of available channel categories."""
    channels, error = get_channels()
    if error:
        return [], error

    cats = {}
    for ch in channels:
        cat = ch["category"]
        if cat not in cats:
            cats[cat] = 0
        cats[cat] += 1

    sorted_cats = []
    for cat in PREFERRED_CATEGORIES:
        if cat in cats:
            sorted_cats.append({"name": cat, "count": cats.pop(cat)})
    for cat in sorted(cats.keys()):
        sorted_cats.append({"name": cat, "count": cats[cat]})

    return sorted_cats, None


def get_channel_by_id(channel_id):
    """Get a single channel by ID, skipping the active-program filter.

    When looking up a specific channel (e.g. from a show alert or direct URL),
    the channel should be returned regardless of its current EPG status —
    the stream itself is always available even if the timeline has a gap.
    """
    channels, error = get_channels(include_all=True)
    if error:
        return None, error

    for ch in channels:
        if ch["id"] == channel_id:
            return ch, None

    return None, "Channel not found"
