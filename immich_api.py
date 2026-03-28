"""Immich API client for Senior TV.

Fetches random family photos from an Immich server for the photo slideshow
and home page widget.
"""

import sys

import requests
import cache


def _get_config():
    """Get Immich URL and API key from settings."""
    from models import get_setting
    url = (get_setting("immich_url") or "").rstrip("/")
    api_key = get_setting("immich_api_key") or ""
    return url, api_key


def _headers(api_key):
    return {"x-api-key": api_key, "Accept": "application/json"}


def get_random_photos(count=20):
    """Fetch random photo metadata from Immich. Cached for 10 minutes."""
    cache_key = f"immich_random_{count}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url, api_key = _get_config()
    if not url or not api_key:
        return []

    try:
        resp = requests.get(
            f"{url}/api/assets/random",
            params={"count": count},
            headers=_headers(api_key),
            timeout=10,
        )
        resp.raise_for_status()
        photos = []
        for asset in resp.json():
            if asset.get("type") != "IMAGE":
                continue
            photos.append({
                "id": asset["id"],
                "url": f"/api/immich-photo/{asset['id']}",
                "thumb": f"/api/immich-photo/{asset['id']}?size=thumbnail",
                "name": asset.get("originalFileName", ""),
                "date": asset.get("localDateTime", ""),
                "source": "immich",
            })
        cache.set(cache_key, photos, ttl=600)  # 10 min
        return photos
    except Exception as e:
        print(f"Immich: get_random_photos error: {e}", file=sys.stderr)
        return []


def get_photo_data(asset_id, size="preview"):
    """Fetch actual photo bytes from Immich. Returns (bytes, content_type) or (None, None)."""
    url, api_key = _get_config()
    if not url or not api_key:
        return None, None

    try:
        resp = requests.get(
            f"{url}/api/assets/{asset_id}/thumbnail",
            params={"size": size},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")
    except Exception as e:
        print(f"Immich: get_photo_data error: {e}", file=sys.stderr)
        return None, None


def get_photo_count():
    """Get total photo count from Immich."""
    url, api_key = _get_config()
    if not url or not api_key:
        return 0

    cached = cache.get("immich_count")
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            f"{url}/api/assets/statistics",
            headers=_headers(api_key),
            timeout=5,
        )
        resp.raise_for_status()
        count = resp.json().get("images", 0)
        cache.set("immich_count", count, ttl=3600)
        return count
    except Exception as e:
        print(f"Immich: get_photo_count error: {e}", file=sys.stderr)
        return 0


def is_configured():
    """Check if Immich is configured with URL and API key."""
    url, api_key = _get_config()
    return bool(url and api_key)


def test_connection():
    """Test Immich API connectivity. Returns (ok, message)."""
    url, api_key = _get_config()
    if not url or not api_key:
        return False, "Not configured"
    try:
        resp = requests.get(
            f"{url}/api/server/about",
            headers=_headers(api_key),
            timeout=5,
        )
        resp.raise_for_status()
        version = resp.json().get("version", "unknown")
        count = get_photo_count()
        return True, f"Connected (v{version}, {count:,} photos)"
    except Exception as e:
        return False, str(e)
