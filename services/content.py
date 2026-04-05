"""Content selection: time-of-day preferences, recently-played tracking."""

from collections import deque
from datetime import datetime

# Shared recently-played tracker
_recently_played = deque(maxlen=50)


def get_time_period(hour=None):
    """Return current time period and genre preferences.
    Returns dict with keys:
        period: str "morning"|"afternoon"|"evening"
        youtube_categories: list for YouTube channel browsing
        pluto_categories: list for Pluto TV
        jellyfin_genres: list for Jellyfin auto-play
        channel_categories: list for YouTube auto-play channels
    """
    if hour is None:
        hour = datetime.now().hour

    if hour < 14:  # Morning: wake to 2 PM
        return {
            "period": "morning",
            "youtube_categories": [
                "Game Shows",
                "Morning Shows",
                "Classic TV",
            ],
            "pluto_categories": [
                "News + Opinion",
                "Daytime + Game Shows",
                "Classic TV",
            ],
            "jellyfin_genres": [
                "Comedy",
                "Family",
                "Western",
            ],
            "channel_categories": [
                "Game Shows",
                "Morning Shows",
                "Local News",
                "Classic TV",
            ],
        }
    elif hour < 17:  # Afternoon: 2-5 PM
        return {
            "period": "afternoon",
            "youtube_categories": [
                "Westerns",
                "Classic TV",
                "Comedy",
                "Crime & Drama",
                "Music & Variety",
            ],
            "pluto_categories": [
                "Westerns",
                "Classic TV",
                "Comedy",
                "Drama",
                "True Crime",
            ],
            "jellyfin_genres": [
                "Western",
                "Comedy",
                "Drama",
                "Crime",
            ],
            "channel_categories": [
                "Westerns",
                "Classic TV",
                "Comedy",
                "Crime & Drama",
            ],
        }
    else:  # Evening: 5 PM+
        return {
            "period": "evening",
            "youtube_categories": [
                "Comedy",
                "Crime & Drama",
                "Wind Down",
                "Westerns",
                "Music & Variety",
                "Nature",
            ],
            "pluto_categories": [
                "Comedy",
                "Classic TV",
                "Drama",
                "True Crime",
                "Westerns",
            ],
            "jellyfin_genres": [
                "Western",
                "Family",
                "Comedy",
                "Crime",
            ],
            "channel_categories": [
                "Wind Down",
                "Comedy",
                "Classic TV",
                "Westerns",
            ],
        }


def mark_played(item_id):
    """Add an item to the recently-played deque."""
    _recently_played.append(item_id)


def was_recently_played(item_id):
    """Check if an item was recently played."""
    return item_id in _recently_played
