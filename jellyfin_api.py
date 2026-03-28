"""Jellyfin API client for Senior TV.

Communicates with a Jellyfin Media Server to authenticate, browse libraries,
get metadata, and construct direct stream URLs for HTML5 video playback.
"""

import requests

AUTH_HEADER = 'MediaBrowser Client="SeniorTV", Device="MiniPC", DeviceId="senior-tv", Version="1.0"'


class JellyfinAPI:
    def __init__(self, base_url, api_key=None, user_id=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id

    def _headers(self):
        h = {"X-Emby-Authorization": AUTH_HEADER}
        if self.api_key:
            h["X-Emby-Token"] = self.api_key
        return h

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def authenticate(self, username, password):
        """Authenticate and get an access token + user ID."""
        resp = requests.post(
            f"{self.base_url}/Users/AuthenticateByName",
            headers={
                "Content-Type": "application/json",
                "X-Emby-Authorization": AUTH_HEADER,
            },
            json={"Username": username, "Pw": password},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self.api_key = data["AccessToken"]
        self.user_id = data["User"]["Id"]
        return {
            "api_key": self.api_key,
            "user_id": self.user_id,
            "user_name": data["User"]["Name"],
            "server_name": data.get("ServerName", data.get("ServerId", "")),
        }

    def test_connection(self):
        """Test if the server is reachable and token is valid."""
        try:
            data = self._get("/System/Info/Public")
            server_name = data.get("ServerName", "Unknown")

            # If we have a token, test it
            if self.api_key:
                self._get(f"/Users/{self.user_id}")

            return {"ok": True, "server_name": server_name}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return {"ok": False, "error": "Invalid token. Please re-authenticate."}
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_libraries(self):
        """Get all media libraries (views)."""
        data = self._get(f"/Users/{self.user_id}/Views")
        libraries = []
        for item in data.get("Items", []):
            ctype = item.get("CollectionType", "")
            if ctype in ("movies", "tvshows", "mixed"):
                libraries.append({
                    "id": item["Id"],
                    "title": item["Name"],
                    "type": ctype,
                    "icon": "🎬" if ctype == "movies" else "📺" if ctype == "tvshows" else "📁",
                })
        return libraries

    def get_genres(self, library_id):
        """Get genres available in a library."""
        data = self._get("/Genres", params={
            "ParentId": library_id,
            "SortBy": "SortName",
        })
        return [g["Name"] for g in data.get("Items", [])]

    def get_library_items(self, library_id, sort="SortName", sort_order="Ascending",
                          item_type=None, genre=None, limit=100, start=0):
        """Get items in a library with optional genre filter and pagination."""
        params = {
            "ParentId": library_id,
            "SortBy": sort,
            "SortOrder": sort_order,
            "Fields": "Overview,PrimaryImageAspectRatio,Genres",
            "ImageTypeLimit": 1,
            "Limit": limit,
            "StartIndex": start,
            "Recursive": "true",
            "IncludeItemTypes": item_type or "Movie,Series",
        }
        if genre:
            params["Genres"] = genre

        data = self._get(f"/Users/{self.user_id}/Items", params=params)
        return [_parse_item(item, self.base_url, self.api_key) for item in data.get("Items", [])]

    def get_latest(self, library_id=None, limit=20):
        """Get recently added items."""
        params = {"Limit": limit, "Fields": "Overview", "ImageTypeLimit": 1}
        if library_id:
            params["ParentId"] = library_id
        data = self._get(f"/Users/{self.user_id}/Items/Latest", params=params)
        items = data if isinstance(data, list) else data.get("Items", []) if isinstance(data, dict) else []
        return [_parse_item(item, self.base_url, self.api_key) for item in items]

    def get_resume(self, limit=10):
        """Get continue watching items."""
        params = {
            "Limit": limit,
            "Fields": "Overview",
            "ImageTypeLimit": 1,
            "MediaTypes": "Video",
        }
        data = self._get(f"/Users/{self.user_id}/Items/Resume", params=params)
        items = data.get("Items", []) if isinstance(data, dict) else []
        return [_parse_item(item, self.base_url, self.api_key) for item in items]

    def get_item(self, item_id):
        """Get detailed metadata for a single item."""
        data = self._get(f"/Users/{self.user_id}/Items/{item_id}")
        return _parse_item(data, self.base_url, self.api_key)

    def get_seasons(self, show_id):
        """Get seasons for a TV show."""
        data = self._get(f"/Shows/{show_id}/Seasons", params={
            "UserId": self.user_id,
            "Fields": "Overview",
        })
        seasons = []
        for item in data.get("Items", []):
            seasons.append({
                "id": item["Id"],
                "title": item.get("Name", ""),
                "index": item.get("IndexNumber", 0),
                "episode_count": item.get("ChildCount", 0),
                "thumb": _image_url(item, self.base_url, self.api_key, "Primary", 400),
            })
        return seasons

    def get_episodes(self, show_id, season_id):
        """Get episodes for a season."""
        data = self._get(f"/Shows/{show_id}/Episodes", params={
            "SeasonId": season_id,
            "UserId": self.user_id,
            "Fields": "Overview",
        })
        episodes = []
        for item in data.get("Items", []):
            episodes.append({
                "id": item["Id"],
                "title": item.get("Name", ""),
                "index": item.get("IndexNumber", 0),
                "summary": (item.get("Overview") or "")[:200],
                "duration": _format_duration(item.get("RunTimeTicks")),
                "thumb": _image_url(item, self.base_url, self.api_key, "Primary", 400),
            })
        return episodes

    def get_music_tracks(self, genre=None, limit=20):
        """Get random music tracks, optionally filtered by genre."""
        params = {
            "IncludeItemTypes": "Audio",
            "Recursive": "true",
            "SortBy": "Random",
            "Limit": limit,
            "Fields": "RunTimeTicks,Artists,Album,AlbumId",
        }
        if genre:
            params["Genres"] = genre
        data = self._get(f"/Users/{self.user_id}/Items", params=params)
        tracks = []
        for item in data.get("Items", []):
            tracks.append({
                "id": item.get("Id", ""),
                "title": item.get("Name", ""),
                "artist": ", ".join(item.get("Artists", []) or ["Unknown"]),
                "album": item.get("Album", ""),
                "duration": _format_duration(item.get("RunTimeTicks")),
                "stream_url": f"/api/jellyfin-stream/{item.get('Id', '')}/stream?Static=true",
                "thumb": _image_url(item, self.base_url, self.api_key, "Primary", 200),
            })
        return tracks

    def get_english_audio_index(self, item_id):
        """Find the English audio track index. Returns None if default is already English."""
        try:
            resp = requests.get(
                f"{self.base_url}/Items/{item_id}",
                params={"api_key": self.api_key, "Fields": "MediaStreams"},
                timeout=10,
            )
            if not resp.ok:
                return None
            streams = resp.json().get("MediaStreams", [])
            default_audio = None
            english_audio = None
            for s in streams:
                if s.get("Type") != "Audio":
                    continue
                if s.get("IsDefault"):
                    default_audio = s
                lang = (s.get("Language") or "").lower()
                if lang in ("eng", "en", "english") and english_audio is None:
                    english_audio = s
            # If default is already English, no override needed
            if default_audio and (default_audio.get("Language") or "").lower() in ("eng", "en", "english"):
                return None
            # If we found an English track, return its index
            if english_audio:
                return english_audio.get("Index")
            return None
        except Exception:
            return None

    def get_stream_url(self, item_id):
        """Get a proxied stream URL that works from both LAN and remote.
        Uses static (direct) stream — fastest, works for AAC/MP3 audio.
        Always selects the English audio track if the default is non-English.
        The player template also includes a transcode_url fallback (HLS with AAC)
        for files with EAC3/DTS/TrueHD audio that Chrome can't decode."""
        eng_idx = self.get_english_audio_index(item_id)
        url = f"/api/jellyfin-stream/{item_id}/stream?Static=true"
        if eng_idx is not None:
            url += f"&AudioStreamIndex={eng_idx}"
        return url

    def get_subtitle_url(self, item_id):
        """Get proxied subtitle URL."""
        return f"/api/jellyfin-stream/{item_id}/Subtitles/0/0/Stream.vtt"

    def get_transcode_url(self, item_id):
        """Get a proxied HLS transcode URL as fallback."""
        eng_idx = self.get_english_audio_index(item_id)
        url = (
            f"/api/jellyfin-stream/{item_id}/master.m3u8"
            f"?MediaSourceId={item_id}"
            f"&VideoCodec=h264"
            f"&AudioCodec=aac"
            f"&MaxStreamingBitrate=20000000"
        )
        if eng_idx is not None:
            url += f"&AudioStreamIndex={eng_idx}"
        return url

    def get_daily_picks(self, library_id, count=20):
        """Get a daily rotation of movies — same all day, different tomorrow.
        Uses the date as a seed offset into the full library."""
        from datetime import date
        today = date.today()
        day_seed = today.year * 10000 + today.month * 100 + today.day

        # Get total count
        data = self._get(f"/Users/{self.user_id}/Items", params={
            "ParentId": library_id, "Recursive": "true",
            "IncludeItemTypes": "Movie", "Limit": 0,
        })
        total = data.get("TotalRecordCount", 0)
        if total == 0:
            return []

        # Use date as offset into the library, wrapping around
        start_index = (day_seed * 7) % max(1, total - count)

        data = self._get(f"/Users/{self.user_id}/Items", params={
            "ParentId": library_id,
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "Fields": "Overview,PrimaryImageAspectRatio,Genres",
            "ImageTypeLimit": 1,
            "Limit": count,
            "StartIndex": start_index,
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
        })
        return [_parse_item(item, self.base_url, self.api_key) for item in data.get("Items", [])]

    def get_random_episode(self, show_id):
        """Get a random episode from a TV show."""
        # Get all episodes
        data = self._get(f"/Users/{self.user_id}/Items", params={
            "ParentId": show_id,
            "Recursive": "true",
            "IncludeItemTypes": "Episode",
            "SortBy": "Random",
            "SortOrder": "Ascending",
            "Fields": "Overview",
            "Limit": 1,
        })
        items = data.get("Items", [])
        if items:
            return _parse_item(items[0], self.base_url, self.api_key)
        return None

    def search(self, query, limit=20):
        """Search across all libraries."""
        data = self._get(f"/Users/{self.user_id}/Items", params={
            "SearchTerm": query,
            "Limit": limit,
            "Fields": "Overview",
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Series,Episode",
        })
        return [_parse_item(item, self.base_url, self.api_key) for item in data.get("Items", [])]

    def report_playback_start(self, item_id):
        """Tell Jellyfin we started playing (updates "Now Playing")."""
        try:
            requests.post(
                f"{self.base_url}/Sessions/Playing",
                headers=self._headers(),
                json={"ItemId": item_id, "CanSeek": True},
                timeout=5,
            )
        except Exception:
            pass

    def report_playback_stop(self, item_id, position_ticks=0):
        """Tell Jellyfin we stopped playing (updates resume position)."""
        try:
            requests.post(
                f"{self.base_url}/Sessions/Playing/Stopped",
                headers=self._headers(),
                json={"ItemId": item_id, "PositionTicks": position_ticks},
                timeout=5,
            )
        except Exception:
            pass


# --- Helpers ---

def _parse_item(item, base_url, api_key):
    item_type = item.get("Type", "Unknown").lower()
    ticks = item.get("RunTimeTicks")

    return {
        "id": item.get("Id", ""),
        "title": item.get("Name", ""),
        "type": item_type,
        "year": item.get("ProductionYear"),
        "summary": (item.get("Overview") or "")[:300],
        "rating": item.get("CommunityRating"),
        "official_rating": item.get("OfficialRating", ""),
        "duration": _format_duration(ticks),
        "thumb": _image_url(item, base_url, api_key, "Primary", 400),
        "backdrop": _image_url(item, base_url, api_key, "Backdrop", 1280),
        "series_name": item.get("SeriesName", ""),
        "season_name": item.get("SeasonName", ""),
        "index_number": item.get("IndexNumber"),
        "parent_index": item.get("ParentIndexNumber"),
        "episode_count": item.get("ChildCount"),
        "season_count": item.get("ChildCount"),
        "played_percentage": item.get("UserData", {}).get("PlayedPercentage", 0),
    }


def _image_url(item, base_url, api_key, image_type="Primary", width=400):
    """Generate a proxied image URL that works from both LAN and remote."""
    item_id = item.get("Id", "")
    image_tags = item.get("ImageTags", {})

    if image_type in image_tags:
        tag = image_tags[image_type]
        return f"/api/jellyfin-image/{item_id}/{image_type}?w={width}&tag={tag}"

    # For episodes, try series primary image
    if image_type == "Primary" and item.get("SeriesPrimaryImageTag"):
        series_id = item.get("SeriesId", "")
        tag = item["SeriesPrimaryImageTag"]
        return f"/api/jellyfin-image/{series_id}/Primary?w={width}&tag={tag}"

    # Try backdrop tags (array)
    if image_type == "Backdrop":
        backdrop_tags = item.get("BackdropImageTags", [])
        if backdrop_tags:
            return f"/api/jellyfin-image/{item_id}/Backdrop?w={width}&tag={backdrop_tags[0]}"

    return None


def _format_duration(ticks):
    if not ticks:
        return ""
    minutes = ticks // 600000000
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    return f"{minutes}m"
