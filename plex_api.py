"""Plex API client for Senior TV.

Communicates with a Plex Media Server to browse libraries,
get metadata, and construct streaming URLs.
"""

import requests
from urllib.parse import urljoin, quote


class PlexAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {
            "X-Plex-Token": token,
            "Accept": "application/json",
        }

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def test_connection(self):
        """Test if the Plex server is reachable and token is valid."""
        try:
            data = self._get("/")
            server_name = data.get("MediaContainer", {}).get("friendlyName", "Unknown")
            return {"ok": True, "server_name": server_name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_libraries(self):
        """Get all libraries (Movies, TV Shows, Music, etc.)."""
        data = self._get("/library/sections")
        libraries = []
        for lib in data.get("MediaContainer", {}).get("Directory", []):
            libraries.append({
                "id": lib["key"],
                "title": lib["title"],
                "type": lib["type"],  # movie, show, artist, photo
                "icon": _lib_icon(lib["type"]),
            })
        return libraries

    def get_library_items(self, library_id, sort="titleSort"):
        """Get all items in a library."""
        data = self._get(f"/library/sections/{library_id}/all", params={"sort": sort})
        items = []
        for item in data.get("MediaContainer", {}).get("Metadata", []):
            items.append(_parse_item(item, self.base_url, self.token))
        return items

    def get_recently_added(self, library_id=None, count=20):
        """Get recently added items, optionally filtered by library."""
        if library_id:
            data = self._get(f"/library/sections/{library_id}/recentlyAdded",
                             params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": count})
        else:
            data = self._get("/library/recentlyAdded",
                             params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": count})
        items = []
        for item in data.get("MediaContainer", {}).get("Metadata", []):
            items.append(_parse_item(item, self.base_url, self.token))
        return items

    def get_item(self, rating_key):
        """Get detailed metadata for a single item."""
        data = self._get(f"/library/metadata/{rating_key}")
        items = data.get("MediaContainer", {}).get("Metadata", [])
        if items:
            return _parse_item(items[0], self.base_url, self.token)
        return None

    def get_seasons(self, show_key):
        """Get seasons for a TV show."""
        data = self._get(f"/library/metadata/{show_key}/children")
        seasons = []
        for item in data.get("MediaContainer", {}).get("Metadata", []):
            seasons.append({
                "key": item["ratingKey"],
                "title": item.get("title", ""),
                "index": item.get("index", 0),
                "episode_count": item.get("leafCount", 0),
                "thumb": _thumb_url(item.get("thumb"), self.base_url, self.token),
            })
        return seasons

    def get_episodes(self, season_key):
        """Get episodes for a season."""
        data = self._get(f"/library/metadata/{season_key}/children")
        episodes = []
        for item in data.get("MediaContainer", {}).get("Metadata", []):
            episodes.append({
                "key": item["ratingKey"],
                "title": item.get("title", ""),
                "index": item.get("index", 0),
                "summary": item.get("summary", "")[:200],
                "duration": _format_duration(item.get("duration", 0)),
                "thumb": _thumb_url(item.get("thumb"), self.base_url, self.token),
            })
        return episodes

    def get_stream_url(self, rating_key):
        """Get a direct play URL for an item. Falls back to transcode."""
        data = self._get(f"/library/metadata/{rating_key}")
        items = data.get("MediaContainer", {}).get("Metadata", [])
        if not items:
            return None

        item = items[0]
        media_list = item.get("Media", [])
        if not media_list:
            return None

        # Try direct play first
        parts = media_list[0].get("Part", [])
        if parts:
            part_key = parts[0].get("key", "")
            if part_key:
                return f"{self.base_url}{part_key}?X-Plex-Token={self.token}"

        return None

    def get_transcode_url(self, rating_key):
        """Get a transcode/stream URL suitable for HTML5 video."""
        # Universal transcode endpoint for HLS
        path = f"/video/:/transcode/universal/start.m3u8"
        params = {
            "path": f"/library/metadata/{rating_key}",
            "mediaIndex": "0",
            "partIndex": "0",
            "protocol": "hls",
            "directPlay": "1",
            "directStream": "1",
            "X-Plex-Token": self.token,
        }
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{self.base_url}{path}?{query}"

    def search(self, query, limit=20):
        """Search across all libraries."""
        data = self._get("/hubs/search", params={"query": query, "limit": limit})
        results = []
        for hub in data.get("MediaContainer", {}).get("Hub", []):
            for item in hub.get("Metadata", []):
                results.append(_parse_item(item, self.base_url, self.token))
        return results

    def get_on_deck(self, count=20):
        """Get on-deck (continue watching) items."""
        try:
            data = self._get("/library/onDeck",
                             params={"X-Plex-Container-Size": count})
            items = []
            for item in data.get("MediaContainer", {}).get("Metadata", []):
                items.append(_parse_item(item, self.base_url, self.token))
            return items
        except Exception:
            return []


# --- Helpers ---

def _parse_item(item, base_url, token):
    """Parse a Plex metadata item into our standard format."""
    item_type = item.get("type", "unknown")
    return {
        "key": item.get("ratingKey", ""),
        "title": item.get("title", ""),
        "type": item_type,
        "year": item.get("year"),
        "summary": item.get("summary", "")[:300],
        "rating": item.get("rating"),
        "content_rating": item.get("contentRating", ""),
        "duration": _format_duration(item.get("duration", 0)),
        "thumb": _thumb_url(item.get("thumb"), base_url, token),
        "art": _thumb_url(item.get("art"), base_url, token),
        "grandparent_title": item.get("grandparentTitle", ""),  # Show name for episodes
        "parent_title": item.get("parentTitle", ""),  # Season name for episodes
        "index": item.get("index"),  # Episode/season number
        "parent_index": item.get("parentIndex"),  # Season number for episodes
        "episode_count": item.get("leafCount"),
        "season_count": item.get("childCount"),
    }


def _thumb_url(thumb_path, base_url, token):
    if not thumb_path:
        return None
    return f"{base_url}/photo/:/transcode?width=400&height=600&minSize=1&url={quote(thumb_path)}&X-Plex-Token={token}"


def _lib_icon(lib_type):
    icons = {
        "movie": "🎬",
        "show": "📺",
        "artist": "🎵",
        "photo": "📷",
    }
    return icons.get(lib_type, "📁")


def _format_duration(ms):
    if not ms:
        return ""
    minutes = ms // 60000
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    return f"{minutes}m"
