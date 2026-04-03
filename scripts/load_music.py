#!/usr/bin/env python3
"""Download curated classical music from Archive.org into Jellyfin music directory.

All tracks are public domain recordings from the Musopen project and other sources.
Organized into album folders for Jellyfin to scan.
"""

import os
import sys
import time
import requests

MUSIC_DIR = os.path.expanduser("~/media/music")

# Archive.org collections with verified classical music
COLLECTIONS = [
    {
        "id": "MusopenCollectionAsFlac",
        "name": "Musopen Classical Collection",
        "format": "mp3",  # download MP3 versions (1.25 GB vs 7.3 GB FLAC)
    },
    {
        "id": "chopin-nocturnes",
        "name": "Chopin - Nocturnes",
        "format": "mp3",
    },
    {
        "id": "CanonPachelbel",
        "name": "Pachelbel - Canon",
        "format": "mp3",
    },
    {
        "id": "SchubertSymphonyNo.8unfinished_347",
        "name": "Schubert - Symphony No. 8 (Unfinished)",
        "format": "mp3",
    },
]


def get_audio_files(identifier, fmt="mp3"):
    """Get list of audio files from an archive.org item."""
    resp = requests.get(
        f"https://archive.org/metadata/{identifier}",
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    files = []
    for f in data.get("files", []):
        name = f.get("name", "")
        if name.endswith(f".{fmt}"):
            files.append({
                "name": name,
                "url": f"https://archive.org/download/{identifier}/{requests.utils.quote(name)}",
                "size": int(f.get("size", 0)),
            })
    return files


def download_collection(collection):
    identifier = collection["id"]
    name = collection["name"]
    fmt = collection["format"]

    print(f"\n  [{name}]")

    # Get file list
    try:
        files = get_audio_files(identifier, fmt)
    except Exception as e:
        print(f"    [ERR] Could not fetch metadata: {e}")
        return 0

    if not files:
        print(f"    [SKIP] No .{fmt} files found")
        return 0

    total_mb = sum(f["size"] for f in files) / (1024 * 1024)
    print(f"    Found {len(files)} tracks ({total_mb:.0f} MB)")

    downloaded = 0
    for f in files:
        # Preserve folder structure (e.g., Bach_GoldbergVariations/track.mp3)
        rel_path = f["name"]
        dest = os.path.join(MUSIC_DIR, rel_path)
        dest_dir = os.path.dirname(dest)

        if os.path.exists(dest):
            downloaded += 1
            continue

        os.makedirs(dest_dir, exist_ok=True)

        try:
            resp = requests.get(f["url"], timeout=60, stream=True)
            if resp.status_code == 429:
                print(f"    [429] Rate limited, waiting 30s...")
                time.sleep(30)
                resp = requests.get(f["url"], timeout=60, stream=True)
            resp.raise_for_status()

            with open(dest, "wb") as out:
                for chunk in resp.iter_content(8192):
                    out.write(chunk)
            downloaded += 1

            if downloaded % 10 == 0:
                print(f"    Progress: {downloaded}/{len(files)}")

        except Exception as e:
            print(f"    [ERR] {rel_path}: {e}")
            continue

        time.sleep(0.5)

    print(f"    Done: {downloaded}/{len(files)} tracks")
    return downloaded


def main():
    os.makedirs(MUSIC_DIR, exist_ok=True)
    print("=" * 50)
    print("  Classical Music for Jellyfin")
    print("=" * 50)

    total = 0
    for coll in COLLECTIONS:
        total += download_collection(coll)

    # Show summary
    print(f"\n{'=' * 50}")
    print(f"  Total: {total} tracks downloaded")
    size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, filenames in os.walk(MUSIC_DIR)
        for f in filenames
    )
    print(f"  Size: {size / (1024**2):.0f} MB")
    print(f"  Location: {MUSIC_DIR}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
