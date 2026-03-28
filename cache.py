"""Simple in-memory cache with TTL for Senior TV.
Prevents repeated API calls to Pluto TV, weather, YouTube, etc."""

import time
import threading

_cache = {}
_lock = threading.Lock()


def get(key):
    """Get a cached value. Returns None if expired or missing."""
    with _lock:
        entry = _cache.get(key)
        if entry:
            if time.time() < entry["expires"]:
                return entry["value"]
            del _cache[key]
    return None


def set(key, value, ttl=300):
    """Cache a value with TTL in seconds. Default 5 minutes."""
    with _lock:
        _cache[key] = {"value": value, "expires": time.time() + ttl}


def clear(key=None):
    """Clear one key or all."""
    with _lock:
        if key:
            _cache.pop(key, None)
        else:
            _cache.clear()


def cleanup():
    """Remove all expired entries. Called periodically to prevent unbounded growth."""
    now = time.time()
    with _lock:
        expired = [k for k, v in _cache.items() if now >= v["expires"]]
        for k in expired:
            del _cache[k]
    return len(expired)
