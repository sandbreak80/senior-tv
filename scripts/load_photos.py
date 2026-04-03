#!/usr/bin/env python3
"""Download curated photos from Unsplash (no API key) and upload to Immich.

Uses Unsplash source URLs which serve random images from curated topics.
Each URL returns a different image, so we call repeatedly to build a collection.
License: Unsplash License (free for personal use).
"""

import os
import sqlite3
import sys
import tempfile
import time
import hashlib

import requests

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "senior_tv.db")

# Unsplash topic/search URLs — each request returns a random 1920px image
# Using source.unsplash.com which redirects to actual image files
CATEGORIES = {
    "animals": {
        "album": "Animals",
        "searches": ["wildlife", "cute+animals", "puppies", "kittens", "birds", "ocean+animals", "farm+animals", "butterfly", "deer", "horses"],
        "target": 150,
    },
    "landscapes": {
        "album": "Landscapes",
        "searches": ["mountain+landscape", "ocean+sunset", "forest", "desert+landscape", "lake+reflection", "valley", "aurora+borealis", "waterfall", "canyon", "meadow"],
        "target": 150,
    },
    "nature": {
        "album": "Nature",
        "searches": ["flowers+macro", "autumn+leaves", "spring+blossoms", "garden+flowers", "mushroom+forest", "fern", "lavender+field", "cherry+blossom", "sunflower", "roses"],
        "target": 100,
    },
    "scenic": {
        "album": "Scenic & Travel",
        "searches": ["european+architecture", "japanese+garden", "castle", "tropical+beach", "venice", "santorini", "paris+landmark", "ancient+temple", "lighthouse", "bridge+architecture"],
        "target": 100,
    },
}


def get_immich_config():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    url = conn.execute("SELECT value FROM settings WHERE key='immich_url'").fetchone()
    key = conn.execute("SELECT value FROM settings WHERE key='immich_api_key'").fetchone()
    conn.close()
    return url["value"], key["value"]


def create_album(immich_url, api_key, name):
    resp = requests.get(f"{immich_url}/api/albums", headers={"x-api-key": api_key}, timeout=10)
    for album in resp.json():
        if album["albumName"] == name:
            return album["id"]
    resp = requests.post(
        f"{immich_url}/api/albums",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"albumName": name},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def upload_to_immich(immich_url, api_key, image_path, filename):
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{immich_url}/api/assets",
            headers={"x-api-key": api_key},
            files={"assetData": (filename, f, "image/jpeg")},
            data={
                "deviceAssetId": filename,
                "deviceId": "senior-tv-photos",
                "fileCreatedAt": "2026-01-01T00:00:00.000Z",
                "fileModifiedAt": "2026-01-01T00:00:00.000Z",
            },
            timeout=30,
        )
    if resp.status_code in (200, 201):
        return resp.json().get("id")
    elif resp.status_code == 409:
        return resp.json().get("id")
    return None


def add_to_album(immich_url, api_key, album_id, asset_ids):
    if not asset_ids:
        return
    for i in range(0, len(asset_ids), 100):
        batch = asset_ids[i:i + 100]
        resp = requests.put(
            f"{immich_url}/api/albums/{album_id}/assets",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"ids": batch},
            timeout=15,
        )
        added = sum(1 for r in resp.json() if r.get("success"))
        print(f"  Added {added}/{len(batch)} to album")


def download_category(cat_name, config, immich_url, api_key):
    album_name = config["album"]
    searches = config["searches"]
    target = config["target"]

    print(f"\n{'=' * 50}")
    print(f"  {album_name} (target: {target})")
    print(f"{'=' * 50}")

    album_id = create_album(immich_url, api_key, album_name)
    seen_hashes = set()
    asset_ids = []

    with tempfile.TemporaryDirectory() as tmpdir:
        per_search = target // len(searches) + 2
        for search in searches:
            count = 0
            attempts = 0
            while count < per_search and attempts < per_search * 3:
                attempts += 1
                try:
                    # Unsplash source URL — returns a random image matching the search
                    url = f"https://source.unsplash.com/1920x1080/?{search}"
                    resp = requests.get(url, timeout=20, allow_redirects=True)
                    if resp.status_code != 200:
                        time.sleep(2)
                        continue

                    ct = resp.headers.get("content-type", "")
                    if "image" not in ct:
                        continue

                    # Hash to deduplicate (Unsplash may return same image)
                    content = resp.content
                    h = hashlib.md5(content).hexdigest()
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)

                    if len(content) < 10000:
                        continue

                    filename = f"unsplash_{cat_name}_{h[:12]}.jpg"
                    tmp_path = os.path.join(tmpdir, filename)
                    with open(tmp_path, "wb") as f:
                        f.write(content)

                    asset_id = upload_to_immich(immich_url, api_key, tmp_path, filename)
                    if asset_id:
                        asset_ids.append(asset_id)
                        count += 1

                    os.unlink(tmp_path)

                except Exception as e:
                    print(f"    [ERR] {e}")

                time.sleep(1.5)  # be polite to Unsplash

            print(f"  '{search}': {count} images")

            if len(asset_ids) >= target:
                break

    add_to_album(immich_url, api_key, album_id, asset_ids)
    print(f"\n  Total: {len(asset_ids)} images → '{album_name}'")
    return len(asset_ids)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", type=str)
    args = parser.parse_args()

    immich_url, api_key = get_immich_config()
    print(f"Immich: {immich_url}")

    cats = {args.category: CATEGORIES[args.category]} if args.category else CATEGORIES
    total = 0
    for name, config in cats.items():
        total += download_category(name, config, immich_url, api_key)

    print(f"\n{'=' * 50}")
    print(f"  TOTAL: {total} photos uploaded")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
