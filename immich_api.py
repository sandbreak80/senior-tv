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
    """Fetch random photo metadata from Immich. Cached for 10 minutes.

    If immich_album_id is set in settings, pulls only from that album.
    Otherwise pulls from the entire library.
    """
    from models import get_setting
    # Support albums, folders, or all photos
    album_ids_str = get_setting("immich_album_ids") or get_setting("immich_album_id") or ""
    album_ids = [a.strip() for a in album_ids_str.split(",") if a.strip()]
    folder_paths_str = get_setting("immich_folder_paths") or ""
    folder_paths = [f.strip() for f in folder_paths_str.split(",") if f.strip()]

    cache_key = f"immich_random_{count}_{album_ids_str}_{folder_paths_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url, api_key = _get_config()
    if not url or not api_key:
        return []

    try:
        import random
        if album_ids or folder_paths:
            assets = []
            # Fetch from selected albums
            for album_id in album_ids:
                try:
                    resp = requests.get(
                        f"{url}/api/albums/{album_id}",
                        headers=_headers(api_key),
                        timeout=10,
                    )
                    resp.raise_for_status()
                    assets.extend(resp.json().get("assets", []))
                except Exception:
                    continue
            # Fetch from selected folders
            for folder in folder_paths:
                try:
                    resp = requests.post(
                        f"{url}/api/search/metadata",
                        headers=_headers(api_key),
                        json={"originalPath": folder, "type": "IMAGE",
                              "size": 250, "page": random.randint(1, 10)},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    assets.extend(resp.json().get("assets", {}).get("items", []))
                except Exception:
                    continue
            random.shuffle(assets)
            assets = assets[:count]
        else:
            # Fetch random from entire library
            resp = requests.get(
                f"{url}/api/assets/random",
                params={"count": count},
                headers=_headers(api_key),
                timeout=10,
            )
            resp.raise_for_status()
            assets = resp.json()

        photos = []
        for asset in assets:
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


def get_folder_photos(folder_path, count=20):
    """Fetch random photos from a specific folder path in Immich."""
    url, api_key = _get_config()
    if not url or not api_key:
        return []
    try:
        import random as _random
        resp = requests.post(
            f"{url}/api/search/metadata",
            headers=_headers(api_key),
            json={"originalPath": folder_path, "type": "IMAGE", "size": min(count * 3, 250), "page": _random.randint(1, 5)},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("assets", {}).get("items", [])
        _random.shuffle(items)
        photos = []
        for asset in items[:count]:
            photos.append({
                "id": asset["id"],
                "url": f"/api/immich-photo/{asset['id']}",
                "thumb": f"/api/immich-photo/{asset['id']}?size=thumbnail",
                "name": asset.get("originalFileName", ""),
                "date": asset.get("localDateTime", ""),
                "source": "immich",
            })
        return photos
    except Exception as e:
        print(f"Immich: get_folder_photos error: {e}", file=sys.stderr)
        return []


def search_folders(sample_size=500):
    """Discover top-level folder structure from Immich photo paths."""
    url, api_key = _get_config()
    if not url or not api_key:
        return []
    try:
        resp = requests.get(
            f"{url}/api/assets/random",
            params={"count": sample_size},
            headers=_headers(api_key),
            timeout=15,
        )
        resp.raise_for_status()
        folders = {}
        base_prefix = None
        for asset in resp.json():
            path = asset.get("originalPath", "")
            parts = path.split("/")
            # Find common base (e.g., /mypool/photos/)
            if base_prefix is None and len(parts) > 2:
                # Heuristic: base is everything before the varying part
                for i, part in enumerate(parts):
                    if part.isdigit() and len(part) == 4:  # year folder
                        base_prefix = "/".join(parts[:i]) + "/"
                        break
                if base_prefix is None and len(parts) > 3:
                    base_prefix = "/".join(parts[:3]) + "/"
            if base_prefix and path.startswith(base_prefix):
                top = path[len(base_prefix):].split("/")[0]
            elif len(parts) > 3:
                top = parts[3] if len(parts) > 3 else parts[-2]
            else:
                continue
            folders[top] = folders.get(top, 0) + 1
        # Sort by count, return as list
        result = [{"name": k, "estimated_count": v} for k, v in folders.items()]
        result.sort(key=lambda x: -x["estimated_count"])
        return result
    except Exception as e:
        print(f"Immich: search_folders error: {e}", file=sys.stderr)
        return []


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
