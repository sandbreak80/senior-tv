#!/usr/bin/env python3
"""Download free public domain content into Jellyfin media directories.

All content is public domain or Creative Commons licensed from Archive.org.
Organized into Jellyfin-friendly folder structures.

Usage:
    python3 scripts/load_jellyfin_content.py                      # Download everything (50 GB budget)
    python3 scripts/load_jellyfin_content.py --budget 30          # Custom budget in GB
    python3 scripts/load_jellyfin_content.py --category music     # Just music
    python3 scripts/load_jellyfin_content.py --category movies    # Just movies
    python3 scripts/load_jellyfin_content.py --category shows     # Just TV shows
    python3 scripts/load_jellyfin_content.py --max-episodes 5     # Limit episodes per show
    python3 scripts/load_jellyfin_content.py --list               # Show what would download
    python3 scripts/load_jellyfin_content.py --scan               # Trigger Jellyfin scan only
"""

import argparse
import os
import re
import sqlite3
import sys
import time
from urllib.parse import quote

import requests

# Flush output immediately so progress is visible in logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "senior_tv.db")
MEDIA_ROOT = os.path.expanduser("~/media")
MOVIES_DIR = os.path.join(MEDIA_ROOT, "movies")
SHOWS_DIR = os.path.join(MEDIA_ROOT, "shows")
MUSIC_DIR = os.path.join(MEDIA_ROOT, "music")

# Global size budget (GB) — stop downloading when total media hits this
MAX_MEDIA_GB = 50
# Per-show episode limit — sample, don't download entire series
MAX_EPISODES_PER_SHOW = 10
# Skip any single file larger than this (MB)
MAX_FILE_MB = 2000

# ---------------------------------------------------------------------------
# Content catalog — all verified archive.org identifiers with MP4/video files
# ---------------------------------------------------------------------------

CONTENT = {
    "music": [
        # Classical — Colleen (music memory preserved longest in Alzheimer's)
        {"id": "MusopenCollectionAsFlac", "title": "Musopen Classical Collection", "format": "mp3"},
        {"id": "chopin-nocturnes", "title": "Chopin - Nocturnes", "format": "mp3"},
        {"id": "CanonPachelbel", "title": "Pachelbel - Canon", "format": "mp3"},
        {"id": "SchubertSymphonyNo.8unfinished_347", "title": "Schubert - Symphony No. 8", "format": "mp3"},
        # Big band / swing — Don & Colleen's youth (1940s-50s dance era)
        {"id": "GlennMillerOrchestra-CompleteStudioRecordings", "title": "Glenn Miller Orchestra", "format": "mp3"},
        {"id": "BigBandRemotes", "title": "Big Band Remotes", "format": "mp3"},
        {"id": "CommandPerformance", "title": "Command Performance", "format": "mp3"},
    ],
    "movies": [
        # ===================================================================
        # ALL content 1936 or later — Don & Colleen born 1931
        # All identifiers verified on Archive.org as of April 2026
        # ===================================================================

        # -- Westerns (Don's favorites) --
        {"id": "mclintok_widescreen", "title": "McLintock! (1963)", "genre": "Western"},
        {"id": "angel_and_the_badman", "title": "Angel and the Badman (1947)", "genre": "Western"},
        {"id": "Santa_Fe_Trail_movie", "title": "Santa Fe Trail (1940)", "genre": "Western"},
        {"id": "OnlytheValaint", "title": "Only the Valiant (1951)", "genre": "Western"},
        {"id": "WarOfTheWildcats-JohnWayne1943", "title": "War of the Wildcats (1943)", "genre": "Western"},
        {"id": "TheOvertheHillGang", "title": "The Over-the-Hill Gang (1969)", "genre": "Western"},
        {"id": "TheOver-the-HillGangRidesAgain", "title": "The Over-the-Hill Gang Rides Again (1970)", "genre": "Western"},
        {"id": "Winds_of_the_Wasteland", "title": "Winds of the Wasteland (1936)", "genre": "Western"},
        {"id": "AbileneTown", "title": "Abilene Town (1946)", "genre": "Western"},
        {"id": "american_empire", "title": "American Empire (1942)", "genre": "Western"},
        {"id": "Hell_Town", "title": "Hell Town (1937)", "genre": "Western"},
        {"id": "VengeanceValley", "title": "Vengeance Valley (1951)", "genre": "Western"},
        {"id": "Daniel_Boone_-_Trail_Blazer", "title": "Daniel Boone, Trail Blazer (1956)", "genre": "Western"},
        {"id": "my_pal_trigger", "title": "My Pal Trigger (1946)", "genre": "Western"},
        {"id": "TheBigTrees720p1952", "title": "The Big Trees (1952)", "genre": "Western"},
        {"id": "BuckskinFrontier1943", "title": "Buckskin Frontier (1943)", "genre": "Western"},
        {"id": "Death_Rides_A_Horse_pan_and_scan", "title": "Death Rides a Horse (1967)", "genre": "Western"},
        {"id": "silver_spurs", "title": "Silver Spurs (1943)", "genre": "Western"},
        {"id": "border_patrol", "title": "Border Patrol (1943)", "genre": "Western"},
        {"id": "aces_and_eights", "title": "Aces and Eights (1936)", "genre": "Western"},

        # -- Comedy --
        {"id": "AfricaScreams", "title": "Africa Screams (1949)", "genre": "Comedy"},
        {"id": "disorder_in_the_court", "title": "Disorder in the Court (1936)", "genre": "Comedy"},
        {"id": "Topper_Returns_41", "title": "Topper Returns (1941)", "genre": "Comedy"},
        {"id": "my_favorite_brunette", "title": "My Favorite Brunette (1947)", "genre": "Comedy"},
        {"id": "TheFlyingDeuces", "title": "The Flying Deuces (1939)", "genre": "Comedy"},
        {"id": "AtWarWithTheArmy", "title": "At War with the Army (1950)", "genre": "Comedy"},
        {"id": "cco_jackandthebeanstalk", "title": "Jack and the Beanstalk (1952)", "genre": "Comedy"},
        {"id": "the_inspector_general", "title": "The Inspector General (1949)", "genre": "Comedy"},
        {"id": "behave_yourself_ipod", "title": "Behave Yourself (1951)", "genre": "Comedy"},
        {"id": "Pygmalion", "title": "Pygmalion (1938)", "genre": "Comedy"},
        {"id": "NothingSacred", "title": "Nothing Sacred (1937)", "genre": "Comedy"},
        {"id": "my_dear_secretary", "title": "My Dear Secretary (1949)", "genre": "Comedy"},
        {"id": "amazing_adventure", "title": "The Amazing Adventure (1936)", "genre": "Comedy"},

        # -- Drama / Noir --
        {"id": "his_girl_friday", "title": "His Girl Friday (1940)", "genre": "Drama"},
        {"id": "its-a-wonderful-life-1946_202108", "title": "It's a Wonderful Life (1946)", "genre": "Drama"},
        {"id": "penny_serenade", "title": "Penny Serenade (1941)", "genre": "Drama"},
        {"id": "suddenly", "title": "Suddenly (1954)", "genre": "Drama"},
        {"id": "ScarletStreet", "title": "Scarlet Street (1945)", "genre": "Drama"},
        {"id": "impact", "title": "Impact (1949)", "genre": "Drama"},
        {"id": "TheStranger_0", "title": "The Stranger (1946)", "genre": "Drama"},
        {"id": "Detour", "title": "Detour (1945)", "genre": "Drama"},
        {"id": "meet_john_doe", "title": "Meet John Doe (1941)", "genre": "Drama"},
        {"id": "Cyrano_DeBergerac", "title": "Cyrano de Bergerac (1950)", "genre": "Drama"},
        {"id": "He_Walked_By_Night.avi", "title": "He Walked by Night (1948)", "genre": "Drama"},
        {"id": "Hitch_Hiker", "title": "The Hitch-Hiker (1953)", "genre": "Drama"},
        {"id": "angel_on_my_shoulder", "title": "Angel on My Shoulder (1946)", "genre": "Drama"},
        {"id": "AStarIsBorn", "title": "A Star Is Born (1937)", "genre": "Drama"},
        {"id": "They_Made_Me_A_Criminal_1939", "title": "They Made Me a Criminal (1939)", "genre": "Drama"},
        {"id": "Martha_Ivers_movie", "title": "Strange Love of Martha Ivers (1946)", "genre": "Drama"},
        {"id": "kansascityconfidencial", "title": "Kansas City Confidential (1952)", "genre": "Drama"},
        {"id": "BloodontheSun", "title": "Blood on the Sun (1945)", "genre": "Drama"},
        {"id": "CaptainKidd_", "title": "Captain Kidd (1945)", "genre": "Adventure"},
        {"id": "LoveAffair", "title": "Love Affair (1939)", "genre": "Romance"},
        {"id": "made_for_each_other_film", "title": "Made for Each Other (1939)", "genre": "Drama"},
        {"id": "TheRedHouse", "title": "The Red House (1947)", "genre": "Drama"},
        {"id": "sabrina-1954", "title": "Sabrina (1954)", "genre": "Romance"},

        # -- War (Don's era) --
        {"id": "Gung_Ho", "title": "Gung Ho! (1943)", "genre": "War"},
        {"id": "In_Which_We_Serve", "title": "In Which We Serve (1942)", "genre": "War"},

        # -- Musical / Family --
        {"id": "gullivers_travels1939", "title": "Gulliver's Travels (1939)", "genre": "Musical"},
        {"id": "royal_wedding", "title": "Royal Wedding (1951)", "genre": "Musical"},
        {"id": "little_princess", "title": "The Little Princess (1939)", "genre": "Family"},
        {"id": "till_the_clouds_roll_by", "title": "Till the Clouds Roll By (1946)", "genre": "Musical"},
        {"id": "pot_o_gold", "title": "Pot o' Gold (1941)", "genre": "Musical"},
        {"id": "second_chorus_1940", "title": "Second Chorus (1940)", "genre": "Musical"},
        {"id": "The_Pied_Piper_of_Hamelin", "title": "The Pied Piper of Hamelin (1957)", "genre": "Musical"},
        {"id": "this_is_the_army", "title": "This Is the Army (1943)", "genre": "Musical"},

        # -- Suspense (lighter ones — avoid high-stimulation for sundowning) --
        {"id": "house_on_haunted_hill_ipod", "title": "House on Haunted Hill (1959)", "genre": "Thriller"},
        {"id": "dressed_to_kill", "title": "Dressed to Kill (1946)", "genre": "Thriller"},
    ],
    "shows": [
        # -- Game Shows (Don loves these) --
        {"id": "whats-my-line", "title": "What's My Line", "genre": "Game Show"},
        {"id": "ybylcollection", "title": "You Bet Your Life (Groucho Marx)", "genre": "Game Show"},
        {"id": "Queen_For_A_Day", "title": "Queen for a Day", "genre": "Game Show"},
        {"id": "BeatTheClock13October1951", "title": "Beat the Clock", "genre": "Game Show"},
        {"id": "toTellTheTruth-May221967", "title": "To Tell the Truth", "genre": "Game Show"},
        {"id": "TruthConsequences1955", "title": "Truth or Consequences", "genre": "Game Show"},
        {"id": "strikeItRich-26August1955", "title": "Strike It Rich", "genre": "Game Show"},
        # -- Sitcoms --
        {"id": "bevhill-s01e01-36", "title": "Beverly Hillbillies S1", "genre": "Sitcom"},
        {"id": "pdburnsallen", "title": "Burns and Allen", "genre": "Sitcom"},
        {"id": "georgeburnsandgracieallen", "title": "George Burns & Gracie Allen", "genre": "Sitcom"},
        {"id": "The_Beverly_Hillbillies", "title": "Beverly Hillbillies", "genre": "Sitcom"},
        {"id": "GreenAcresCompleteSeries", "title": "Green Acres", "genre": "Sitcom"},
        {"id": "The_Dick_van_Dyke_Show", "title": "The Dick Van Dyke Show", "genre": "Sitcom"},
        {"id": "I_Married_Joan", "title": "I Married Joan", "genre": "Sitcom"},
        {"id": "Petticoat_Junction_Series", "title": "Petticoat Junction", "genre": "Sitcom"},
        {"id": "Topper-HenriettaSellsTheHouse", "title": "Topper", "genre": "Sitcom"},
        # -- Variety --
        {"id": "Cavalcade_Of_Stars", "title": "Cavalcade of Stars (1951)", "genre": "Variety"},
        {"id": "TheDeanMartinShow", "title": "The Dean Martin Show", "genre": "Variety"},
        {"id": "ColgateComedyHour_AbbottCostello", "title": "Colgate Comedy Hour", "genre": "Variety"},
        {"id": "hollywoodpalace", "title": "The Hollywood Palace", "genre": "Variety"},
        {"id": "Red_Skelton_CarolChanningGuest", "title": "Red Skelton Show", "genre": "Variety"},
        # -- Westerns --
        {"id": "enter_the_lone_ranger", "title": "The Lone Ranger", "genre": "Western"},
        {"id": "theloneranger_201705", "title": "Lone Ranger TV Show", "genre": "Western"},
        {"id": "Bonanza_pd", "title": "Bonanza", "genre": "Western"},
        {"id": "Bonanza_-_The_Trail_Gang", "title": "Bonanza - The Trail Gang", "genre": "Western"},
        {"id": "Bonanza_-_Day_Of_Reckoning", "title": "Bonanza - Day of Reckoning", "genre": "Western"},
        {"id": "Bonanza-BitterWater", "title": "Bonanza - Bitter Water", "genre": "Western"},
        {"id": "Bonanza-TheFearMerchants", "title": "Bonanza - Fear Merchants", "genre": "Western"},
        {"id": "Bonanza-BloodOnTheLand", "title": "Bonanza - Blood on the Land", "genre": "Western"},
        {"id": "Bonanza-EscapeToPonderosa", "title": "Bonanza - Escape to Ponderosa", "genre": "Western"},
        {"id": "theriflemanpd", "title": "The Rifleman", "genre": "Western"},
        {"id": "tateseason1", "title": "Tate (1960)", "genre": "Western"},
        # -- Drama --
        {"id": "Dragnet1951", "title": "Dragnet", "genre": "Drama"},
        {"id": "SherlockHolmes1954", "title": "Adventures of Sherlock Holmes", "genre": "Drama"},
        {"id": "Andy_Griffith_A_Wife_For_Andy", "title": "Andy Griffith Show", "genre": "Drama"},
    ],
    "ambient": [
        # Wind-down content for after 3 PM
        {"id": "fluxusfireplace", "title": "Fireplace", "genre": "Ambient"},
        {"id": "TheBestFireplaceVideo3HoursHD", "title": "Fireplace 3 Hours HD", "genre": "Ambient"},
        {"id": "AquariumWonderland", "title": "Aquarium Wonderland", "genre": "Ambient"},
    ],
}

# Video file extensions we want to download, in priority order
VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mpeg", ".mpg", ".ogv")


def media_usage_gb():
    """Return current total media usage in GB."""
    total = 0
    for dp, _, fns in os.walk(MEDIA_ROOT):
        for f in fns:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total / (1024 ** 3)


def budget_ok(label=""):
    """Return True if we're under the size budget."""
    used = media_usage_gb()
    if used >= MAX_MEDIA_GB:
        print(f"\n  *** BUDGET REACHED: {used:.1f} GB / {MAX_MEDIA_GB} GB — stopping {label} ***")
        return False
    return True


# ---------------------------------------------------------------------------
# Archive.org helpers
# ---------------------------------------------------------------------------

def get_downloadable_files(identifier, wanted_ext=VIDEO_EXTS):
    """Get downloadable file URLs from an archive.org item."""
    resp = requests.get(f"https://archive.org/metadata/{identifier}", timeout=30)
    resp.raise_for_status()
    data = resp.json()

    files = []
    for f in data.get("files", []):
        name = f.get("name", "")
        lower = name.lower()
        if any(lower.endswith(ext) for ext in wanted_ext):
            size = int(f.get("size", 0))
            files.append({
                "name": name,
                "url": f"https://archive.org/download/{identifier}/{quote(name)}",
                "size": size,
            })

    # Sort: prefer mp4, then by size descending (best quality)
    def sort_key(f):
        name = f["name"].lower()
        ext_priority = next((i for i, e in enumerate(wanted_ext) if name.endswith(e)), 99)
        return (ext_priority, -f["size"])

    files.sort(key=sort_key)
    return files


def download_file(url, dest, desc=""):
    """Download a file with progress indication."""
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        return True  # already downloaded

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        resp = requests.get(url, timeout=120, stream=True,
                            headers={"User-Agent": "SeniorTV/1.0 (family kiosk project)"})
        if resp.status_code == 429:
            print(f"      [429] Rate limited — waiting 60s")
            time.sleep(60)
            resp = requests.get(url, timeout=120, stream=True,
                                headers={"User-Agent": "SeniorTV/1.0 (family kiosk project)"})
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest + ".partial", "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                downloaded += len(chunk)

        os.rename(dest + ".partial", dest)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        if desc:
            print(f"      {desc} ({size_mb:.0f} MB)")
        return True

    except Exception as e:
        print(f"      [ERR] {e}")
        # Clean up partial
        for p in (dest + ".partial", dest):
            if os.path.exists(p) and os.path.getsize(p) < 10000:
                os.unlink(p)
        return False


# ---------------------------------------------------------------------------
# Category downloaders
# ---------------------------------------------------------------------------

def download_music():
    """Download classical music from archive.org."""
    print(f"\n{'=' * 60}")
    print(f"  MUSIC — Classical collection for Jellyfin")
    print(f"{'=' * 60}")

    total = 0
    for item in CONTENT["music"]:
        if not budget_ok("music"):
            break
        fmt = item.get("format", "mp3")
        print(f"\n  [{item['title']}]")

        try:
            resp = requests.get(f"https://archive.org/metadata/{item['id']}", timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"    [ERR] {e}")
            continue

        files = [f for f in data.get("files", []) if f["name"].endswith(f".{fmt}")]
        if not files:
            print(f"    No .{fmt} files found")
            continue

        total_mb = sum(int(f.get("size", 0)) for f in files) / (1024 ** 2)
        print(f"    {len(files)} tracks ({total_mb:.0f} MB)")

        for f in files:
            rel_path = f["name"]
            dest = os.path.join(MUSIC_DIR, rel_path)
            if os.path.exists(dest):
                total += 1
                continue

            url = f"https://archive.org/download/{item['id']}/{quote(f['name'])}"
            if download_file(url, dest):
                total += 1

            time.sleep(0.3)

        count = sum(1 for f in files if os.path.exists(os.path.join(MUSIC_DIR, f["name"])))
        print(f"    Done: {count}/{len(files)} tracks")

    print(f"\n  Music total: {total} tracks")
    return total


def download_video_category(category, dest_base):
    """Download movies, shows, or ambient content."""
    items = CONTENT.get(category, [])
    if not items:
        return 0

    print(f"\n{'=' * 60}")
    print(f"  {category.upper()} — {len(items)} titles")
    print(f"{'=' * 60}")

    downloaded = 0
    for item in items:
        if not budget_ok(category):
            break

        title = item["title"]
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        item_dir = os.path.join(dest_base, safe_title)

        print(f"\n  [{title}]")

        # Check if already downloaded
        if os.path.isdir(item_dir):
            existing = [f for f in os.listdir(item_dir)
                        if any(f.lower().endswith(e) for e in VIDEO_EXTS)]
            if existing:
                print(f"    Already have {len(existing)} file(s) — skipping")
                downloaded += 1
                continue

        try:
            files = get_downloadable_files(item["id"])
        except Exception as e:
            print(f"    [ERR] Could not fetch metadata: {e}")
            continue

        if not files:
            print(f"    No video files found")
            continue

        # Filter out files that are too large
        files = [f for f in files if f["size"] / (1024 ** 2) <= MAX_FILE_MB]
        if not files:
            print(f"    All files exceed {MAX_FILE_MB} MB limit — skipping")
            continue

        if category in ("movies", "ambient"):
            # Single best file per title
            best = files[0]
            size_mb = best["size"] / (1024 ** 2)
            ext = os.path.splitext(best["name"])[1]
            dest = os.path.join(item_dir, f"{safe_title}{ext}")
            print(f"    Best: {best['name']} ({size_mb:.0f} MB)")

            if download_file(best["url"], dest, "Downloaded"):
                downloaded += 1
            time.sleep(1)

        elif category == "shows":
            # SAMPLE episodes — don't download entire series
            import random
            random.seed(hash(item["id"]))  # deterministic sample per show

            to_sample = files[:MAX_EPISODES_PER_SHOW]
            if len(files) > MAX_EPISODES_PER_SHOW:
                # Evenly sample across the series for variety
                step = len(files) // MAX_EPISODES_PER_SHOW
                to_sample = [files[i * step] for i in range(MAX_EPISODES_PER_SHOW)
                             if i * step < len(files)]

            sample_mb = sum(f["size"] for f in to_sample) / (1024 ** 2)
            print(f"    Sampling {len(to_sample)} of {len(files)} episodes ({sample_mb:.0f} MB)")

            ep_count = 0
            for f in to_sample:
                if not budget_ok(category):
                    break
                dest = os.path.join(item_dir, f["name"])
                if download_file(f["url"], dest):
                    ep_count += 1
                if ep_count % 5 == 0 and ep_count > 0:
                    print(f"      Progress: {ep_count}/{len(to_sample)}")
                time.sleep(0.5)

            print(f"    Done: {ep_count}/{len(to_sample)} episodes")
            if ep_count > 0:
                downloaded += 1

    print(f"\n  {category.title()} total: {downloaded}/{len(items)} titles")
    return downloaded


# ---------------------------------------------------------------------------
# Jellyfin scan
# ---------------------------------------------------------------------------

def trigger_jellyfin_scan():
    """Trigger a Jellyfin library scan."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        url = conn.execute("SELECT value FROM settings WHERE key='jellyfin_url'").fetchone()
        key = conn.execute("SELECT value FROM settings WHERE key='jellyfin_api_key'").fetchone()
        conn.close()

        if not url or not key:
            print("  Jellyfin not configured — scan manually")
            return

        resp = requests.post(f"{url['value']}/Library/Refresh",
                             headers={"X-Emby-Token": key["value"]}, timeout=10)
        if resp.status_code == 204:
            print("  Jellyfin library scan triggered!")
        else:
            print(f"  Jellyfin scan returned: {resp.status_code}")
    except Exception as e:
        print(f"  Could not trigger scan: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def list_content():
    """Show what would be downloaded."""
    for category, items in CONTENT.items():
        print(f"\n  {category.upper()} ({len(items)} items):")
        for item in items:
            genre = item.get("genre", "")
            fmt = item.get("format", "")
            extra = f" [{genre}]" if genre else f" ({fmt})" if fmt else ""
            print(f"    - {item['title']}{extra}")
    total = sum(len(v) for v in CONTENT.values())
    print(f"\n  Total: {total} items across {len(CONTENT)} categories")


def main():
    parser = argparse.ArgumentParser(
        description="Download free public domain content for Jellyfin")
    parser.add_argument("--category", choices=["music", "movies", "shows", "ambient"],
                        help="Download only this category")
    parser.add_argument("--budget", type=int, default=50,
                        help="Max total media size in GB (default: 50)")
    parser.add_argument("--max-episodes", type=int, default=10,
                        help="Max episodes per show (default: 10)")
    parser.add_argument("--list", action="store_true", help="List content without downloading")
    parser.add_argument("--scan", action="store_true", help="Trigger Jellyfin library scan only")
    args = parser.parse_args()

    global MAX_MEDIA_GB, MAX_EPISODES_PER_SHOW
    MAX_MEDIA_GB = args.budget
    MAX_EPISODES_PER_SHOW = args.max_episodes

    if args.list:
        list_content()
        return

    if args.scan:
        trigger_jellyfin_scan()
        return

    # Create media directories
    for d in (MOVIES_DIR, SHOWS_DIR, MUSIC_DIR):
        os.makedirs(d, exist_ok=True)

    print("=" * 60)
    print("  Senior TV — Jellyfin Content Loader")
    print("  All content is public domain / Creative Commons")
    print(f"  Budget: {MAX_MEDIA_GB} GB | Current: {media_usage_gb():.1f} GB")
    print(f"  Episodes per show: {MAX_EPISODES_PER_SHOW}")
    print("=" * 60)

    categories = [args.category] if args.category else ["music", "movies", "shows", "ambient"]
    results = {}

    for cat in categories:
        if cat == "music":
            results[cat] = download_music()
        elif cat == "movies":
            results[cat] = download_video_category("movies", MOVIES_DIR)
        elif cat == "shows":
            results[cat] = download_video_category("shows", SHOWS_DIR)
        elif cat == "ambient":
            results[cat] = download_video_category("ambient", MOVIES_DIR)

    # Summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    for cat, count in results.items():
        print(f"    {cat:10s}: {count} items")

    # Disk usage
    for label, path in [("Movies", MOVIES_DIR), ("Shows", SHOWS_DIR), ("Music", MUSIC_DIR)]:
        if os.path.isdir(path):
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _, fns in os.walk(path) for f in fns)
            print(f"    {label:10s}: {size / (1024 ** 3):.1f} GB")

    # Trigger Jellyfin scan
    print()
    trigger_jellyfin_scan()


if __name__ == "__main__":
    main()
