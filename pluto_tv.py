"""Pluto TV API client for Senior TV.

Fetches live channel listings and stream URLs from Pluto TV's free service.
Streams are HLS and play directly in HTML5 video.
"""

import requests
from datetime import datetime, timezone

SESSION_CACHE = {"token": None, "stitcher": None}

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
    SESSION_CACHE["token"] = None
    return _get_session()


def _get_session():
    """Get a session token and stitcher URL from Pluto boot endpoint."""
    if SESSION_CACHE["token"]:
        return SESSION_CACHE["token"], SESSION_CACHE["stitcher"]

    resp = requests.get(
        "https://boot.pluto.tv/v4/start",
        params={
            "appName": "web",
            "appVersion": "na",
            "deviceVersion": "100",
            "deviceModel": "web",
            "deviceMake": "chrome",
            "deviceType": "web",
            "clientID": "senior-tv",
            "clientModelNumber": "1.0",
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
    return token, stitcher


def get_channels(category_filter=None):
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
            resp = requests.get(
                "https://api.pluto.tv/v2/channels",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            # Retry with fresh token on auth failure
            if resp.status_code == 401:
                token, stitcher = _refresh_session()
                resp = requests.get(
                    "https://api.pluto.tv/v2/channels",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
            resp.raise_for_status()
            raw_channels = resp.json()
        except Exception as e:
            return [], str(e)
    else:
        raw_channels = cached

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
        stitcher_params = SESSION_CACHE.get("stitcher_params", "")

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
    """Get a single channel by ID."""
    channels, error = get_channels()
    if error:
        return None, error

    for ch in channels:
        if ch["id"] == channel_id:
            return ch, None

    return None, "Channel not found"
