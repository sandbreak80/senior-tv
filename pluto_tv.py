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

    # Filter out dead/test/junk channels (skip when doing direct ID lookup)
    if not include_all:
        # Only show channels from categories appropriate for seniors
        # This eliminates Testing, Gaming + Anime, En Español, Kids, etc.
        allowed = set(PREFERRED_CATEGORIES)

        # Blacklisted channel names (known dead/promo loops/deprecation screens)
        _BLACKLISTED_NAMES = {
            "growthday network", "pluto tv offerings", "pluto tv slate",
            "buzzr",
        }

        # Auto-blacklist: channels flagged as dead/frozen in recent activity logs
        _auto_blacklisted_ids = set()
        try:
            import models as _models
            from models import get_db_safe as _get_db
            with _get_db() as _db:
                # Channels reported dead in last 7 days (2+ reports = blacklisted)
                rows = _db.execute(
                    """SELECT item_id, COUNT(*) as cnt FROM activity_logs
                       WHERE activity_type IN ('dead_stream', 'frozen_stream', 'silent_stream')
                       AND item_id IS NOT NULL
                       AND logged_at > datetime('now', '-7 days')
                       GROUP BY item_id HAVING cnt >= 2"""
                ).fetchall()
                _auto_blacklisted_ids = {r["item_id"] for r in rows}
        except Exception:
            pass

        def _is_active(c):
            # Category must be in allowlist
            if c.get("category") not in allowed:
                return False
            # Must have a current program
            prog = c.get("current_program")
            if not prog:
                return False
            title = prog.get("title", "").lower()
            name = c.get("name", "").lower()
            # Filter filler/test content by program title
            if any(x in title for x in ["slate", "filler", "test", "off air", "c'est fini", "paid programming"]):
                return False
            # Filter blacklisted channel names
            if name in _BLACKLISTED_NAMES:
                return False
            # Filter auto-blacklisted channels (reported dead 2+ times in 7 days)
            if c.get("id") in _auto_blacklisted_ids:
                return False
            # Filter channels detected as dead via stream fingerprinting
            if c.get("id") in get_dead_channel_ids():
                return False
            return True
        channels = [c for c in channels if _is_active(c)]

    channels.sort(key=lambda c: c["number"])

    # Cache the raw channel data for 30 minutes
    if cached is None:
        _cache.set(cache_key, raw_channels, ttl=1800)

    return channels, None


# Cache of channel IDs confirmed dead via stream fingerprinting
_dead_channel_cache = {"ids": set(), "checked_at": 0}
_dead_cache_lock = threading.Lock()


def validate_channels():
    """Probe a sample of channels to detect the Pluto TV placeholder/deprecation stream.

    All dead channels serve identical HLS segment sequences. We pick two random channels
    and compare their segment hashes — if they match exactly, both are dead. We then
    test remaining channels against the known-dead fingerprint.

    Called periodically by the scheduler (every 30 min). Results cached.
    """
    import hashlib
    import random as _random

    channels, err = get_channels(include_all=True)
    if err or len(channels) < 20:
        return

    # Only re-check every 30 minutes
    with _dead_cache_lock:
        if time.time() - _dead_channel_cache["checked_at"] < 1800:
            return

    # Step 1: Get segment hashes for a sample of channels
    def _get_seg_hashes(channel_id):
        try:
            token, stitcher = _get_session()
            ch = next((c for c in channels if c["id"] == channel_id), None)
            if not ch:
                return None
            resp = requests.get(ch["stream_url"], timeout=10)
            if not resp.ok:
                return None
            # Parse master m3u8 to get first variant
            lines = resp.text.strip().split("\n")
            variant_url = None
            for line in lines:
                if line.startswith("http") and ".m3u8" in line:
                    variant_url = line
                    break
            if not variant_url:
                return None
            resp2 = requests.get(variant_url, timeout=10)
            if not resp2.ok:
                return None
            # Get segment URLs
            seg_urls = [l for l in resp2.text.strip().split("\n") if l.startswith("http") and ".ts" in l]
            if not seg_urls:
                return None
            # Hash first 3 segments
            hashes = []
            for url in seg_urls[:3]:
                r = requests.get(url, timeout=15)
                hashes.append(hashlib.md5(r.content).hexdigest())
            return tuple(hashes)
        except Exception:
            return None

    # Sample 10 random channels and find duplicates
    sample = _random.sample(channels, min(20, len(channels)))
    fingerprints = {}  # hash_tuple → list of channel IDs
    for ch in sample:
        hashes = _get_seg_hashes(ch["id"])
        if hashes:
            key = hashes
            if key not in fingerprints:
                fingerprints[key] = []
            fingerprints[key].append(ch["id"])

    # Any fingerprint shared by 3+ channels is the placeholder
    dead_ids = set()
    placeholder_fingerprint = None
    for fp, ids in fingerprints.items():
        if len(ids) >= 3:
            dead_ids.update(ids)
            placeholder_fingerprint = fp
            break

    if placeholder_fingerprint:
        # Test all channels against the placeholder fingerprint
        for ch in channels:
            if ch["id"] in dead_ids:
                continue
            hashes = _get_seg_hashes(ch["id"])
            if hashes == placeholder_fingerprint:
                dead_ids.add(ch["id"])

    with _dead_cache_lock:
        _dead_channel_cache["ids"] = dead_ids
        _dead_channel_cache["checked_at"] = time.time()

    if dead_ids:
        print(f"PlutoTV: {len(dead_ids)} dead channels detected via stream fingerprint")
    return dead_ids


def get_dead_channel_ids():
    """Return the set of channel IDs known to be dead (cached)."""
    with _dead_cache_lock:
        return _dead_channel_cache["ids"].copy()


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
