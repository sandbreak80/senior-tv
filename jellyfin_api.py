"""Jellyfin API client for Senior TV.

Communicates with a Jellyfin Media Server to authenticate, browse libraries,
get metadata, and construct direct stream URLs for HTML5 video playback.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import cache as _cache

AUTH_HEADER = 'MediaBrowser Client="SeniorTV", Device="MiniPC", DeviceId="senior-tv", Version="1.0"'

# Shared session with connection pooling and automatic retry on transient errors
_session = requests.Session()
_retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503])
_session.mount("http://", HTTPAdapter(max_retries=_retry))
_session.mount("https://", HTTPAdapter(max_retries=_retry))

_ENG_ALIASES = {"eng", "en", "english"}


def _has_english_audio(raw_item):
    """Return True only if the item has at least one explicit English audio track.

    Strict mode: rejects both explicit non-English (`fra`, `jpn`, ...) AND
    `und`/unknown. Mislabeled-but-actually-English files will be hidden —
    re-tag the file in Jellyfin/Radarr to bring it back. Dementia-friendly
    kiosk safety outweighs the cost of hiding ~7% of a mislabeled library.
    If MediaStreams aren't in the payload at all, fail-open (we couldn't check).
    """
    streams = raw_item.get("MediaStreams")
    if streams is None:
        return True  # query didn't request MediaStreams — don't filter here
    audios = [s for s in streams if s.get("Type") == "Audio"]
    if not audios:
        return True  # no audio info available — inconclusive, allow
    for a in audios:
        lang = (a.get("Language") or "").lower().strip()
        if lang in _ENG_ALIASES:
            return True
    return False


def _filter_english(raw_items):
    return [it for it in raw_items if _has_english_audio(it)]


# Genres that should never appear in recommendations/picks for the care
# recipient demographic (elderly couple, 90s, dementia + Alzheimer's).
# Per CLAUDE.md design constraints: they want game shows, sitcoms, westerns,
# familiar old films. Modern animated kids movies (Disney sequels, Pixar,
# DreamWorks, anime) are not recognized, not memorable, and create cognitive
# load. Horror/Thriller are anxiety-inducing. These get filtered at the API
# layer so EVERY picker (daily, latest, browse, search) respects them.
EXCLUDED_GENRES = [
    "Animation",
    "Anime",
    "Horror",
    "Thriller",
]


class JellyfinAPI:
    def __init__(self, base_url, api_key=None, user_id=None, excluded_genres=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.excluded_genres = (
            excluded_genres if excluded_genres is not None else list(EXCLUDED_GENRES)
        )

    def _with_genre_filter(self, params):
        """Ensure Fields includes Genres so we can client-side filter.
        Jellyfin's own NotGenres param does not work (silently ignored across
        multiple spellings on our version), so we over-fetch and filter in
        Python via _drop_excluded_genres below.
        Also over-fetches when Limit is set to account for filtered items."""
        if not self.excluded_genres:
            return params
        fields = params.get("Fields", "")
        if "Genres" not in fields:
            params["Fields"] = (fields + ",Genres").lstrip(",") if fields else "Genres"
        # Over-fetch to leave margin after filtering. ~30% of the library is
        # animation, so 2x gives safe headroom.
        if "Limit" in params and params["Limit"] > 0:
            params["_orig_limit"] = params["Limit"]
            params["Limit"] = params["Limit"] * 2
        return params

    def _drop_excluded_genres(self, items):
        """Drop any item whose Genres intersect self.excluded_genres.
        Case-insensitive. Items with no Genres field are kept."""
        if not self.excluded_genres:
            return items
        excluded_lower = {g.lower() for g in self.excluded_genres}
        kept = []
        for it in items:
            genres = it.get("Genres") or []
            if any(g.lower() in excluded_lower for g in genres):
                continue
            kept.append(it)
        return kept

    def _headers(self):
        h = {"X-Emby-Authorization": AUTH_HEADER}
        if self.api_key:
            h["X-Emby-Token"] = self.api_key
        return h

    def _get(self, path, params=None):
        if _cache.is_circuit_open("jellyfin"):
            raise ConnectionError("Jellyfin circuit breaker open — skipping request")
        url = f"{self.base_url}{path}"
        try:
            resp = _session.get(url, headers=self._headers(), params=params, timeout=10)
            resp.raise_for_status()
            _cache.record_success("jellyfin")
            return resp.json()
        except Exception:
            _cache.record_failure("jellyfin")
            raise

    def authenticate(self, username, password):
        """Authenticate and get an access token + user ID."""
        resp = _session.post(
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
                libraries.append(
                    {
                        "id": item["Id"],
                        "title": item["Name"],
                        "type": ctype,
                        "icon": "🎬"
                        if ctype == "movies"
                        else "📺"
                        if ctype == "tvshows"
                        else "📁",
                    }
                )
        return libraries

    def get_genres(self, library_id):
        """Get genres available in a library."""
        data = self._get(
            "/Genres",
            params={
                "ParentId": library_id,
                "SortBy": "SortName",
            },
        )
        return [g["Name"] for g in data.get("Items", [])]

    def get_library_items(
        self,
        library_id,
        sort="SortName",
        sort_order="Ascending",
        item_type=None,
        genre=None,
        limit=100,
        start=0,
        exclude_tags=None,
    ):
        """Get items in a library with optional genre filter and pagination."""
        params = {
            "ParentId": library_id,
            "SortBy": sort,
            "SortOrder": sort_order,
            "Fields": "Overview,PrimaryImageAspectRatio,Genres,MediaStreams",
            "ImageTypeLimit": 1,
            "Limit": limit,
            "StartIndex": start,
            "Recursive": "true",
            "IncludeItemTypes": item_type or "Movie,Series",
        }
        if genre:
            params["Genres"] = genre
        if exclude_tags:
            params["ExcludeTags"] = ",".join(exclude_tags)
        params = self._with_genre_filter(params)
        orig_limit = params.pop("_orig_limit", limit)

        data = self._get(f"/Users/{self.user_id}/Items", params=params)
        items = self._drop_excluded_genres(_filter_english(data.get("Items", [])))
        return [
            _parse_item(item, self.base_url, self.api_key)
            for item in items[:orig_limit]
        ]

    def get_latest(self, library_id=None, limit=20):
        """Get recently added items."""
        params = {
            "Limit": limit,
            "Fields": "Overview,MediaStreams",
            "ImageTypeLimit": 1,
        }
        if library_id:
            params["ParentId"] = library_id
        params = self._with_genre_filter(params)
        orig_limit = params.pop("_orig_limit", limit)
        data = self._get(f"/Users/{self.user_id}/Items/Latest", params=params)
        items = (
            data
            if isinstance(data, list)
            else data.get("Items", [])
            if isinstance(data, dict)
            else []
        )
        items = self._drop_excluded_genres(_filter_english(items))
        return [
            _parse_item(item, self.base_url, self.api_key)
            for item in items[:orig_limit]
        ]

    def get_resume(self, limit=10):
        """Get continue watching items."""
        params = {
            "Limit": limit,
            "Fields": "Overview,MediaStreams",
            "ImageTypeLimit": 1,
            "MediaTypes": "Video",
        }
        data = self._get(f"/Users/{self.user_id}/Items/Resume", params=params)
        items = data.get("Items", []) if isinstance(data, dict) else []
        return [
            _parse_item(item, self.base_url, self.api_key)
            for item in _filter_english(items)
        ]

    def get_item(self, item_id):
        """Get detailed metadata for a single item."""
        data = self._get(
            f"/Users/{self.user_id}/Items/{item_id}",
            params={"Fields": "MediaStreams,Overview"},
        )
        return _parse_item(data, self.base_url, self.api_key)

    def is_english_audio_available(self, item_id):
        """Play-time gate: does this item have an explicit English audio track?

        Fails open on network errors so a Jellyfin hiccup never blocks playback.
        """
        try:
            resp = _session.get(
                f"{self.base_url}/Users/{self.user_id}/Items/{item_id}",
                params={"api_key": self.api_key, "Fields": "MediaStreams"},
                timeout=10,
            )
            if not resp.ok:
                return True
            return _has_english_audio(resp.json())
        except Exception:
            return True

    def get_seasons(self, show_id):
        """Get seasons for a TV show."""
        data = self._get(
            f"/Shows/{show_id}/Seasons",
            params={
                "UserId": self.user_id,
                "Fields": "Overview",
            },
        )
        seasons = []
        for item in data.get("Items", []):
            seasons.append(
                {
                    "id": item["Id"],
                    "title": item.get("Name", ""),
                    "index": item.get("IndexNumber", 0),
                    "episode_count": item.get("ChildCount", 0),
                    "thumb": _image_url(
                        item, self.base_url, self.api_key, "Primary", 400
                    ),
                }
            )
        return seasons

    def get_episodes(self, show_id, season_id):
        """Get episodes for a season."""
        data = self._get(
            f"/Shows/{show_id}/Episodes",
            params={
                "SeasonId": season_id,
                "UserId": self.user_id,
                "Fields": "Overview,MediaStreams",
            },
        )
        episodes = []
        for item in _filter_english(data.get("Items", [])):
            episodes.append(
                {
                    "id": item["Id"],
                    "title": item.get("Name", ""),
                    "index": item.get("IndexNumber", 0),
                    "summary": (item.get("Overview") or "")[:200],
                    "duration": _format_duration(item.get("RunTimeTicks")),
                    "thumb": _image_url(
                        item, self.base_url, self.api_key, "Primary", 400
                    ),
                }
            )
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
            tracks.append(
                {
                    "id": item.get("Id", ""),
                    "title": item.get("Name", ""),
                    "artist": ", ".join(item.get("Artists", []) or ["Unknown"]),
                    "album": item.get("Album", ""),
                    "duration": _format_duration(item.get("RunTimeTicks")),
                    "stream_url": f"/api/jellyfin-stream/{item.get('Id', '')}/stream?Static=true",
                    "thumb": _image_url(
                        item, self.base_url, self.api_key, "Primary", 200
                    ),
                }
            )
        return tracks

    def get_english_audio_index(self, item_id):
        """Find the English audio track index. Returns None if default is already English."""
        try:
            resp = _session.get(
                f"{self.base_url}/Users/{self.user_id}/Items/{item_id}",
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
            if default_audio and (default_audio.get("Language") or "").lower() in (
                "eng",
                "en",
                "english",
            ):
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
        """Get proxied subtitle URL for English subtitles.
        Returns None if no English subtitle track exists.
        Prefers external SRT (from Bazarr) > embedded, and HI > non-HI."""
        try:
            resp = _session.get(
                f"{self.base_url}/Users/{self.user_id}/Items/{item_id}",
                params={"api_key": self.api_key, "Fields": "MediaStreams"},
                timeout=10,
            )
            if not resp.ok:
                return None
            streams = resp.json().get("MediaStreams", [])
            best = None
            best_score = -1
            for s in streams:
                if s.get("Type") != "Subtitle":
                    continue
                lang = (s.get("Language") or "").lower()
                if lang not in ("eng", "en", "english", ""):
                    continue
                # Score: prefer external (Bazarr .srt), then HI tracks
                score = 0
                if s.get("IsExternal"):
                    score += 10  # External subs (Bazarr) are most reliable
                title = (s.get("Title") or s.get("DisplayTitle") or "").lower()
                if "hi" in title or "hearing" in title or "sdh" in title:
                    score += 5  # HI/SDH tracks include [sounds] descriptions
                if s.get("IsDefault"):
                    score += 2
                if score > best_score:
                    best_score = score
                    best = s
            if best is None:
                return None
            idx = best.get("Index", 0)
            return f"/api/jellyfin-stream/{item_id}/Subtitles/{idx}/0/Stream.vtt"
        except Exception:
            return None

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

        # Get total count (no genre filter in count — we filter client-side)
        count_params = {
            "ParentId": library_id,
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
            "Limit": 0,
        }
        data = self._get(f"/Users/{self.user_id}/Items", params=count_params)
        total = data.get("TotalRecordCount", 0)
        if total == 0:
            return []

        # Over-fetch 3x so we still have enough after dropping excluded genres.
        # SortName+StartIndex gives a deterministic daily window (same all day,
        # different tomorrow). start_index is bounded so we don't run off end.
        overfetch = count * 3
        start_index = (day_seed * 7) % max(1, total - overfetch)

        pick_params = {
            "ParentId": library_id,
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "Fields": "Overview,PrimaryImageAspectRatio,Genres,MediaStreams",
            "ImageTypeLimit": 1,
            "Limit": overfetch,
            "StartIndex": start_index,
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
        }
        data = self._get(f"/Users/{self.user_id}/Items", params=pick_params)
        items = self._drop_excluded_genres(_filter_english(data.get("Items", [])))
        return [
            _parse_item(item, self.base_url, self.api_key)
            for item in items[:count]
        ]

    def get_random_episode(self, show_id):
        """Get a random English-audio episode from a TV show.

        Over-fetches then filters so we don't return None when the random pick
        happened to land on a non-English episode.
        """
        data = self._get(
            f"/Users/{self.user_id}/Items",
            params={
                "ParentId": show_id,
                "Recursive": "true",
                "IncludeItemTypes": "Episode",
                "SortBy": "Random",
                "SortOrder": "Ascending",
                "Fields": "Overview,MediaStreams",
                "Limit": 10,
            },
        )
        items = _filter_english(data.get("Items", []))
        if items:
            return _parse_item(items[0], self.base_url, self.api_key)
        return None

    def search(self, query, limit=20):
        """Search across all libraries."""
        params = self._with_genre_filter({
            "SearchTerm": query,
            "Limit": limit,
            "Fields": "Overview,MediaStreams",
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Series,Episode",
        })
        orig_limit = params.pop("_orig_limit", limit)
        data = self._get(f"/Users/{self.user_id}/Items", params=params)
        items = self._drop_excluded_genres(_filter_english(data.get("Items", [])))
        return [
            _parse_item(item, self.base_url, self.api_key)
            for item in items[:orig_limit]
        ]

    def report_playback_start(self, item_id):
        """Tell Jellyfin we started playing (updates "Now Playing")."""
        try:
            _session.post(
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
            _session.post(
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
