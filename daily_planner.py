"""Daily content planner for Senior TV.

Generates a 24-hour playlist ONCE per day (early morning) rather than making
content decisions in real time. Benefits:
  - Stable picks all day (a card that shows X at 09:00 still shows X at 19:00)
  - Pre-filters can be complex without impacting user-perceived latency
  - You can inspect/override tomorrow's plan ahead of time
  - A bad pick (`Return of Jafar` etc.) only ever reaches the TV if the plan
    itself contains it, which is a single decision point you can audit

Plan lives at `data/daily_plan.json` relative to the senior-tv BASE_DIR.

Callers:
  - `scheduler.py` runs `regenerate_if_needed()` every hour and forces a
    regenerate once daily at 03:00 local time
  - `server.py`'s /tv/plex/daily reads via `load_plan()`; on any miss it calls
    `generate_plan()` to lazy-build
"""
import glob
import json
import os
import random
from datetime import date, datetime, timedelta
from typing import Any

import config
from jellyfin_api import EXCLUDED_GENRES, _parse_item

PLAN_DIR = os.path.join(config.BASE_DIR, "data", "plans")
PLAN_VERSION = 1
DEFAULT_MOVIE_COUNT = 20
# How far back to look when excluding "recently played" — don't repeat stuff
# the viewer already saw in the last two weeks
RECENT_DAYS = 14
# How long to keep historical plan files for audit/debugging
PLAN_RETENTION_DAYS = 30


def _load_content_exclusions() -> set[str]:
    """Load the hard-excluded item IDs from content_exclusions.json."""
    p = os.path.join(config.BASE_DIR, "content_exclusions.json")
    try:
        with open(p) as f:
            return set(json.load(f).get("excluded_ids", []))
    except Exception:
        return set()


def _load_recently_played(db_path: str) -> set[str]:
    """Return set of item IDs played in the last RECENT_DAYS. Best-effort —
    if the DB is missing or the table doesn't exist, return empty set."""
    import sqlite3

    if not os.path.exists(db_path):
        return set()
    cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).isoformat()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT DISTINCT item_id FROM activity_log "
            "WHERE item_id IS NOT NULL AND timestamp > ?",
            (cutoff,),
        )
        ids = {row["item_id"] for row in cur.fetchall() if row["item_id"]}
        conn.close()
        return ids
    except Exception:
        return set()


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def _tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")


def _plan_path_for(d: str) -> str:
    """Return the on-disk path for a plan dated `d` (YYYY-MM-DD).
    Ensures the parent directory exists.
    """
    os.makedirs(PLAN_DIR, exist_ok=True)
    return os.path.join(PLAN_DIR, f"plan_{d}.json")


def load_plan(plan_date: str | None = None) -> dict[str, Any] | None:
    """Read the plan for the given date (default today). None if missing."""
    if plan_date is None:
        plan_date = _today_str()
    try:
        with open(_plan_path_for(plan_date)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_plan(plan: dict[str, Any]) -> None:
    """Write the plan to disk atomically. Uses plan['plan_date'] for filename."""
    plan_date = plan.get("plan_date") or _today_str()
    path = _plan_path_for(plan_date)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(plan, f, indent=2)
    os.replace(tmp, path)


def is_plan_current(plan: dict[str, Any] | None) -> bool:
    """A plan is current if it exists and its plan_date == today's local date."""
    if not plan:
        return False
    return plan.get("plan_date") == _today_str()


def prune_old_plans(retention_days: int = PLAN_RETENTION_DAYS) -> int:
    """Delete plan files older than retention_days. Returns count removed."""
    cutoff = (date.today() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    removed = 0
    for path in glob.glob(os.path.join(PLAN_DIR, "plan_*.json")):
        name = os.path.basename(path)
        # plan_YYYY-MM-DD.json
        date_part = name[len("plan_"):-len(".json")]
        if date_part < cutoff:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed


def generate_plan(
    jellyfin,
    count: int = DEFAULT_MOVIE_COUNT,
    db_path: str | None = None,
    for_date: str | None = None,
) -> dict[str, Any]:
    """Build a fresh daily plan.

    Args:
        jellyfin: a JellyfinAPI instance
        count: how many movies to pick (default 20)
        db_path: path to senior_tv.db for recently-played lookup; defaults to
                 config.DATABASE
        for_date: target date in YYYY-MM-DD; defaults to today. Pass tomorrow's
                  date when running the nightly job to stage a plan ahead of time.

    Returns:
        plan dict ready to save. Raises RuntimeError if the Jellyfin library
        is unreachable or the Movies library can't be found.
    """
    if db_path is None:
        db_path = config.DATABASE
    if for_date is None:
        for_date = _today_str()

    # Find the Movies library — get_libraries returns items with key "type"
    libs = jellyfin.get_libraries() or []
    movies_lib = next((lib for lib in libs if lib.get("type") == "movies"), None)
    if not movies_lib:
        raise RuntimeError("No 'movies' library found in Jellyfin")
    library_id = movies_lib["id"]

    # Over-fetch 10× count sorted random. Jellyfin's Random sort gives real
    # randomness per request; we apply client-side filters after.
    raw = jellyfin._get(
        f"/Users/{jellyfin.user_id}/Items",
        params={
            "ParentId": library_id,
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
            "SortBy": "Random",
            "Limit": count * 10,
            "Fields": "Overview,PrimaryImageAspectRatio,Genres,ProductionYear",
            "ImageTypeLimit": 1,
        },
    )
    items = raw.get("Items", []) if isinstance(raw, dict) else []

    # Apply all filters
    excluded_genres = {g.lower() for g in EXCLUDED_GENRES}
    hard_excluded_ids = _load_content_exclusions()
    recently_played = _load_recently_played(db_path)

    def _ok(item: dict) -> bool:
        # English audio is a senior-tv requirement (old users, no subtitles)
        # but we rely on jellyfin_api._filter_english being applied elsewhere;
        # here we just do metadata checks.
        item_id = item.get("Id")
        if not item_id:
            return False
        if item_id in hard_excluded_ids:
            return False
        if item_id in recently_played:
            return False
        genres = item.get("Genres") or []
        if any(g.lower() in excluded_genres for g in genres):
            return False
        return True

    filtered = [it for it in items if _ok(it)]

    # Deterministic shuffle: use the target date as the seed so the same plan
    # is reproducible if we regenerate mid-day (safety for debugging)
    rng = random.Random(for_date)
    rng.shuffle(filtered)
    picked = filtered[:count]

    # Parse each picked item into the full senior-tv item shape the templates
    # already expect (thumb, backdrop, duration, etc.). Storing these in the
    # plan means the server endpoint can render without another Jellyfin call.
    parsed_movies = [
        _parse_item(it, jellyfin.base_url, jellyfin.api_key) for it in picked
    ]
    # Keep the genres alongside each parsed item for admin / debugging
    for parsed, raw in zip(parsed_movies, picked):
        parsed["genres"] = raw.get("Genres") or []

    plan = {
        "plan_date": for_date,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator_version": PLAN_VERSION,
        "excluded_genres": list(EXCLUDED_GENRES),
        "hard_excluded_count": len(hard_excluded_ids),
        "recently_played_count": len(recently_played),
        "pool_size": len(items),
        "pool_after_filter": len(filtered),
        "movies": parsed_movies,
    }
    return plan


def regenerate_if_needed(jellyfin) -> tuple[bool, dict[str, Any] | None]:
    """Read today's plan; if missing, generate one for today.

    Used by the user-facing endpoint as a lazy-load fallback. Won't touch
    tomorrow's pre-staged plan (different filename).

    Returns:
        (was_regenerated, plan) — plan is None only if generation itself failed.
    """
    plan = load_plan()  # today's
    if is_plan_current(plan):
        return (False, plan)
    try:
        new_plan = generate_plan(jellyfin, for_date=_today_str())
        save_plan(new_plan)
        return (True, new_plan)
    except Exception as e:
        print(f"daily_planner: generate failed: {e}")
        return (False, plan)


def regenerate_now(jellyfin, for_date: str | None = None) -> dict[str, Any]:
    """Force-build a plan for the given date (default today) and save it."""
    plan = generate_plan(jellyfin, for_date=for_date)
    save_plan(plan)
    return plan


def regenerate_tomorrow(jellyfin) -> dict[str, Any]:
    """Build tomorrow's plan and save it. Called by the nightly cron at 22:00.
    Does NOT touch today's plan file — tomorrow's lives at a different path."""
    return regenerate_now(jellyfin, for_date=_tomorrow_str())
