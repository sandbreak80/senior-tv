"""YouTube scraping: live streams, RSS feeds, video metadata."""

import random
import re

import feedparser
import requests

import cache

# Re-export for convenience
from youtube_utils import get_youtube_duration  # noqa: F401


# --- Channel Lists ---

NEWS_CHANNELS = [
    ("ABC News", "https://www.youtube.com/@ABCNews/live"),
    ("NBC News NOW", "https://www.youtube.com/@NBCNews/live"),
    ("CBS News", "https://www.youtube.com/@CBSNews/live"),
    ("FOX 11 Los Angeles", "https://www.youtube.com/@FOX11LosAngeles/live"),
]

LOCAL_CHANNELS = [
    ("ABC 7 Los Angeles", "https://www.youtube.com/@abc7/live"),
    ("FOX 11 Los Angeles", "https://www.youtube.com/@FOX11LosAngeles/live"),
    ("NBC Los Angeles", "https://www.youtube.com/@ABORABLE/live"),
    ("CBS 8 San Diego", "https://www.youtube.com/@CBS8/live"),
]

_VIDEO_ID_RE = re.compile(r'"videoId":"([a-zA-Z0-9_-]{11})"')
_VID_PARAM_RE = re.compile(r"[?&]v=([a-zA-Z0-9_-]{11})")


# --- Live Stream Scraping ---


def scrape_live_video_id(channel_url, require_live=True):
    """Scrape a YouTube channel /live page for current video ID.
    Returns video_id (str) or None."""
    cache_key = f"yt_live_{channel_url}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "" else None
    try:
        r = requests.get(
            channel_url,
            timeout=4,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        match = _VIDEO_ID_RE.search(r.text)
        if match:
            if require_live and "isLive" not in r.text:
                cache.set(cache_key, "", ttl=600)
                return None
            vid = match.group(1)
            cache.set(cache_key, vid, ttl=1800)
            return vid
    except Exception:
        pass
    cache.set(cache_key, "", ttl=300)
    return None


def get_live_streams(channel_list, require_live=False):
    """Scrape multiple channels for live streams.
    Args:
        channel_list: list of (name, url) tuples
        require_live: if True, only return when isLive found
    Returns:
        list of dicts with name, video_id, type keys
    """
    streams = []
    for name, url in channel_list:
        vid = scrape_live_video_id(url, require_live=require_live)
        if vid:
            streams.append(
                {
                    "name": name,
                    "video_id": vid,
                    "type": "youtube",
                }
            )
    return streams


# --- RSS Feed Parsing ---


def get_channel_videos(channel_id, limit=20):
    """Fetch recent videos from a channel via RSS feed.
    Returns list of dicts with title, video_id, thumbnail, published.
    """
    videos = []
    try:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            vid_id = entry.get("yt_videoid", "")
            if not vid_id:
                m = _VID_PARAM_RE.search(entry.get("link", ""))
                vid_id = m.group(1) if m else ""
            thumb = ""
            if vid_id:
                thumb = f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg"
            videos.append(
                {
                    "title": entry.get("title", ""),
                    "video_id": vid_id,
                    "thumbnail": thumb,
                    "published": entry.get("published", ""),
                }
            )
    except Exception:
        pass
    return videos


def get_channel_video_ids(channel_id, limit=20):
    """Fetch just valid video IDs from a channel RSS feed."""
    ids = []
    try:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            vid = entry.get("yt_videoid", "")
            if vid and re.match(r"^[a-zA-Z0-9_-]{11}$", vid):
                ids.append(vid)
    except Exception:
        pass
    return ids


# --- Wind Down Video ---


def pick_random_wind_down_video(get_channels_fn):
    """Pick a random video from Wind Down category. Cached 1 hour.
    Args:
        get_channels_fn: callable returning list of channel dicts
    Returns:
        dict with video_id, name, title or None
    """
    cached = cache.get("wind_down_video")
    if cached is not None:
        return cached if cached != "" else None
    try:
        channels = get_channels_fn()
        if not channels:
            return None
        ch = random.choice(channels)
        feed_url = (
            f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['channel_id']}"
        )
        feed = feedparser.parse(feed_url)
        if feed.entries:
            entry = random.choice(feed.entries[:10])
            vid_id = entry.get("yt_videoid", "")
            if vid_id:
                result = {
                    "video_id": vid_id,
                    "name": ch["name"],
                    "title": entry.get("title", ""),
                }
                cache.set("wind_down_video", result, ttl=3600)
                return result
    except Exception:
        pass
    cache.set("wind_down_video", "", ttl=600)
    return None
