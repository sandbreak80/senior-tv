"""Shared YouTube utilities for Senior TV.

Used by both server.py and scheduler.py to avoid duplicating
the duration-scraping logic.
"""

import re
import requests
import cache


def get_youtube_duration(video_id):
    """Get video duration in seconds by scraping YouTube's page metadata.
    Cached for 1 hour since video durations don't change."""
    cached = cache.get(f"yt_dur_{video_id}")
    if cached is not None:
        return cached
    try:
        resp = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        m = re.search(r'"lengthSeconds":"(\d+)"', resp.text)
        if m:
            duration = int(m.group(1))
            cache.set(f"yt_dur_{video_id}", duration, ttl=3600)
            return duration
    except Exception:
        pass
    return 0
