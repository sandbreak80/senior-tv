#!/usr/bin/env python3
"""Download curated images from free APIs and upload to Immich with album organization.

Sources:
  - Pexels API: animals, landscapes, nature, scenic (CC0-like, free for personal use)
  - Met Museum API: fine art paintings (CC0 public domain)
  - Art Institute of Chicago API: fine art (CC0)

Usage:
  python3 scripts/load_images.py [--dry-run] [--category CATEGORY] [--count N]
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "senior_tv.db")

CATEGORIES = {
    "animals": {
        "source": "wikimedia",
        "queries": [
            "Featured_pictures_of_animals",
            "Featured_pictures_of_mammals",
            "Featured_pictures_of_birds",
            "Featured_pictures_of_reptiles",
            "Featured_pictures_of_fish",
            "Featured_pictures_of_amphibians",
        ],
        "album": "Animals",
        "target": 150,
    },
    "landscapes": {
        "source": "wikimedia",
        "queries": [
            "Featured_pictures_of_landscapes",
            "Quality_images_of_landscapes",
        ],
        "album": "Landscapes",
        "target": 150,
    },
    "fine_art": {
        "source": "met",
        "queries": ["*"],  # broad search — filtered by dept + public domain
        "album": "Fine Art",
        "target": 200,
    },
    "nature": {
        "source": "wikimedia",
        "queries": [
            "Featured_pictures_of_plants",
            "Quality_images_of_plants",
            "Featured_pictures_of_fungi",
        ],
        "album": "Nature",
        "target": 100,
    },
    "scenic": {
        "source": "wikimedia",
        "queries": [
            "Featured_pictures_of_architecture",
            "Featured_pictures_of_bridges",
            "Featured_pictures_of_castles",
            "Featured_pictures_of_churches",
        ],
        "album": "Scenic & Travel",
        "target": 100,
    },
    "classical_art": {
        "source": "artic",
        "queries": ["landscape painting", "impressionism", "still life painting"],
        "album": "Classical Art",
        "target": 150,
    },
}


def get_immich_config():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    url = conn.execute("SELECT value FROM settings WHERE key='immich_url'").fetchone()
    key = conn.execute("SELECT value FROM settings WHERE key='immich_api_key'").fetchone()
    conn.close()
    return url["value"] if url else "", key["value"] if key else ""


# ---------------------------------------------------------------------------
# Wikimedia Commons (Featured Pictures — no API key needed)
# ---------------------------------------------------------------------------

def _wikimedia_files_from_category(category, count, seen_ids):
    """Fetch file pages from a single Wikimedia category (no recursion)."""
    import re as _re
    results = []
    cmcontinue = ""
    while len(results) < count:
        params = {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": f"Category:{category}",
            "gcmtype": "file",
            "gcmlimit": 50,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1920,
            "format": "json",
        }
        if cmcontinue:
            params["gcmcontinue"] = cmcontinue

        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params=params,
            headers={"User-Agent": "SeniorTV/1.0 (family photo kiosk project)"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if len(results) >= count:
                break
            pid = page.get("pageid", 0)
            if pid in seen_ids:
                continue
            info_list = page.get("imageinfo", [])
            if not info_list:
                continue
            info = info_list[0]
            mime = info.get("mime", "")
            if "image" not in mime:
                continue
            if info.get("width", 0) < 1200:
                continue

            url = info.get("thumburl") or info.get("url", "")
            if not url:
                continue

            meta = info.get("extmetadata", {})
            desc = meta.get("ObjectName", {}).get("value", page.get("title", "").replace("File:", ""))
            artist = meta.get("Artist", {}).get("value", "")
            artist = _re.sub(r"<[^>]+>", "", artist).strip() if artist else "Wikimedia Commons"

            ext = "jpg" if "jpeg" in mime or "jpg" in mime else "png"
            seen_ids.add(pid)
            results.append({
                "url": url,
                "filename": f"wiki_{pid}.{ext}",
                "description": f"{desc} — {artist}",
            })

        cmcontinue = data.get("continue", {}).get("gcmcontinue", "")
        if not cmcontinue:
            break
        time.sleep(0.3)

    return results


def _wikimedia_subcats(category):
    """List subcategory names under a Wikimedia category."""
    resp = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{category}", "cmtype": "subcat",
            "cmlimit": 50, "format": "json",
        },
        headers={"User-Agent": "SeniorTV/1.0 (family photo kiosk project)"},
        timeout=15,
    )
    resp.raise_for_status()
    return [m["title"].replace("Category:", "") for m in resp.json().get("query", {}).get("categorymembers", [])]


def fetch_wikimedia(category, count=50):
    """Fetch images from a Wikimedia category, recursing one level into subcats if needed."""
    seen_ids = set()
    # First grab direct files
    results = _wikimedia_files_from_category(category, count, seen_ids)
    if len(results) >= count:
        return results[:count]

    # Recurse into subcategories (one level)
    subcats = _wikimedia_subcats(category)
    remaining = count - len(results)
    per_sub = max(remaining // max(len(subcats), 1), 5) if subcats else 0
    for sub in subcats:
        if len(results) >= count:
            break
        batch = _wikimedia_files_from_category(sub, per_sub, seen_ids)
        results.extend(batch)
        time.sleep(0.3)

    return results[:count]


# ---------------------------------------------------------------------------
# Pexels
# ---------------------------------------------------------------------------

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")


def fetch_pexels(query, count=30, page=1):
    """Fetch landscape-oriented photos from Pexels."""
    if not PEXELS_KEY:
        print("  [SKIP] No PEXELS_API_KEY set")
        return []
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": PEXELS_KEY},
        params={
            "query": query,
            "per_page": min(count, 80),
            "page": page,
            "orientation": "landscape",
            "size": "large",
        },
        timeout=15,
    )
    if resp.status_code == 429:
        print("  [RATE LIMIT] Pexels — waiting 60s")
        time.sleep(60)
        return fetch_pexels(query, count, page)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for p in data.get("photos", []):
        # Use 'large2x' for ~1920px wide, fall back to 'original'
        url = p.get("src", {}).get("large2x") or p.get("src", {}).get("original", "")
        results.append({
            "url": url,
            "filename": f"pexels_{p['id']}.jpeg",
            "description": f"{p.get('alt', query)} — Photo by {p.get('photographer', 'Unknown')} on Pexels",
        })
    return results


# ---------------------------------------------------------------------------
# Met Museum
# ---------------------------------------------------------------------------

def fetch_met_art(count=200):
    """Fetch public-domain paintings from The Met's Open Access API."""
    # Search multiple terms to get broad coverage of the European Paintings dept
    search_terms = ["portrait", "landscape", "still life", "religious", "woman", "man", "river", "flowers"]
    ids = []
    seen_ids = set()
    for term in search_terms:
        print(f"  Searching Met: '{term}' (dept=11, public domain)...")
        try:
            resp = requests.get(
                "https://collectionapi.metmuseum.org/public/collection/v1/search",
                params={"departmentId": 11, "hasImages": True, "q": term, "isPublicDomain": True},
                timeout=30,
            )
            resp.raise_for_status()
            for oid in resp.json().get("objectIDs", []):
                if oid not in seen_ids:
                    seen_ids.add(oid)
                    ids.append(oid)
        except Exception as e:
            print(f"    [WARN] {e}")
        time.sleep(0.5)
    print(f"  Found {len(ids)} unique public-domain paintings, sampling {count}")

    # Sample evenly across the collection
    import random
    random.seed(42)
    sampled = random.sample(ids, min(count * 3, len(ids)))  # over-sample to handle missing images

    results = []
    for oid in sampled:
        if len(results) >= count:
            break
        try:
            obj = requests.get(
                f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}",
                timeout=10,
            ).json()
        except Exception:
            continue

        img = obj.get("primaryImage", "")
        if not img or not img.startswith("http"):
            continue

        artist = obj.get("artistDisplayName", "Unknown Artist")
        title = obj.get("title", "Untitled")
        date = obj.get("objectDate", "")
        results.append({
            "url": img,
            "filename": f"met_{oid}.jpg",
            "description": f"{title} — {artist}" + (f" ({date})" if date else ""),
        })
        if len(results) % 20 == 0:
            print(f"    ...collected {len(results)}/{count} Met paintings")
        time.sleep(0.1)  # be polite

    return results


# ---------------------------------------------------------------------------
# Art Institute of Chicago
# ---------------------------------------------------------------------------

def fetch_artic(query, count=50):
    """Fetch CC0 artworks from Art Institute of Chicago API."""
    results = []
    page = 1
    while len(results) < count:
        resp = requests.get(
            "https://api.artic.edu/api/v1/artworks/search",
            params={
                "q": query,
                "query[term][is_public_domain]": "true",
                "fields": "id,title,artist_display,date_display,image_id",
                "limit": 50,
                "page": page,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        iiif_url = data.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")

        for item in data.get("data", []):
            if len(results) >= count:
                break
            img_id = item.get("image_id")
            if not img_id:
                continue
            # IIIF: full image at 1920px wide
            url = f"{iiif_url}/{img_id}/full/1920,/0/default.jpg"
            artist = item.get("artist_display", "Unknown")
            title = item.get("title", "Untitled")
            date = item.get("date_display", "")
            results.append({
                "url": url,
                "filename": f"artic_{item['id']}.jpg",
                "description": f"{title} — {artist}" + (f" ({date})" if date else ""),
            })

        if not data.get("data"):
            break
        page += 1
        time.sleep(0.5)

    return results


# ---------------------------------------------------------------------------
# Immich upload
# ---------------------------------------------------------------------------

def create_album(immich_url, api_key, name):
    """Create an Immich album, return its ID."""
    # Check if album already exists
    resp = requests.get(f"{immich_url}/api/albums", headers={"x-api-key": api_key}, timeout=10)
    for album in resp.json():
        if album["albumName"] == name:
            print(f"  Album '{name}' already exists (id={album['id']})")
            return album["id"]

    resp = requests.post(
        f"{immich_url}/api/albums",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"albumName": name},
        timeout=10,
    )
    resp.raise_for_status()
    album_id = resp.json()["id"]
    print(f"  Created album '{name}' (id={album_id})")
    return album_id


def upload_to_immich(immich_url, api_key, image_path, filename, description=""):
    """Upload a single image to Immich, return asset ID or None."""
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{immich_url}/api/assets",
            headers={"x-api-key": api_key},
            files={"assetData": (filename, f, "image/jpeg")},
            data={
                "deviceAssetId": filename,
                "deviceId": "senior-tv-loader",
                "fileCreatedAt": "2026-01-01T00:00:00.000Z",
                "fileModifiedAt": "2026-01-01T00:00:00.000Z",
            },
            timeout=30,
        )
    if resp.status_code in (200, 201):
        asset_id = resp.json().get("id")
        return asset_id
    elif resp.status_code == 409:
        # Duplicate — already uploaded
        dup = resp.json()
        return dup.get("id")
    else:
        print(f"    [ERR] Upload {filename}: {resp.status_code} {resp.text[:100]}")
        return None


def add_to_album(immich_url, api_key, album_id, asset_ids):
    """Add assets to an album."""
    if not asset_ids:
        return
    resp = requests.put(
        f"{immich_url}/api/albums/{album_id}/assets",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"ids": asset_ids},
        timeout=15,
    )
    resp.raise_for_status()
    added = sum(1 for r in resp.json() if r.get("success"))
    print(f"  Added {added}/{len(asset_ids)} assets to album")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_category(cat_name, cat_config, immich_url, api_key, dry_run=False):
    print(f"\n{'='*60}")
    print(f"Category: {cat_config['album']} (target: {cat_config['target']})")
    print(f"{'='*60}")

    # Fetch image metadata
    images = []
    source = cat_config["source"]
    target = cat_config["target"]

    if source == "wikimedia":
        per_cat = target // len(cat_config["queries"]) + 1
        for cat in cat_config["queries"]:
            print(f"  Fetching Wikimedia: '{cat}' (up to {per_cat})...")
            batch = fetch_wikimedia(cat, count=per_cat)
            images.extend(batch)
            print(f"    Got {len(batch)} results")
            time.sleep(0.5)
    elif source == "pexels":
        per_query = target // len(cat_config["queries"]) + 1
        for q in cat_config["queries"]:
            print(f"  Searching Pexels: '{q}' (up to {per_query})...")
            batch = fetch_pexels(q, count=per_query)
            images.extend(batch)
            print(f"    Got {len(batch)} results")
            time.sleep(1)  # respect rate limits
    elif source == "met":
        images = fetch_met_art(count=target)
    elif source == "artic":
        per_query = target // len(cat_config["queries"]) + 1
        for q in cat_config["queries"]:
            print(f"  Searching AIC: '{q}' (up to {per_query})...")
            batch = fetch_artic(q, count=per_query)
            images.extend(batch)
            print(f"    Got {len(batch)} results")

    # Deduplicate by filename
    seen = set()
    unique = []
    for img in images:
        if img["filename"] not in seen:
            seen.add(img["filename"])
            unique.append(img)
    images = unique[:target]
    print(f"\n  Total unique images to process: {len(images)}")

    if dry_run:
        for img in images[:5]:
            print(f"    [DRY] {img['filename']}: {img['description'][:60]}")
        print(f"    ... and {len(images)-5} more")
        return len(images)

    # Create album
    album_id = create_album(immich_url, api_key, cat_config["album"])

    # Download and upload
    asset_ids = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, img in enumerate(images):
            try:
                # Download (with retry on 429)
                dl_headers = {"User-Agent": "SeniorTV/1.0 (family photo kiosk project)"}
                resp = requests.get(img["url"], timeout=30, stream=True, headers=dl_headers)
                if resp.status_code == 429:
                    print(f"    [429] Rate limited — waiting 60s...")
                    time.sleep(60)
                    resp = requests.get(img["url"], timeout=30, stream=True, headers=dl_headers)
                if resp.status_code == 429:
                    print(f"    [429] Still limited — waiting 120s...")
                    time.sleep(120)
                    resp = requests.get(img["url"], timeout=30, stream=True, headers=dl_headers)
                if resp.status_code != 200:
                    print(f"    [SKIP] {img['filename']}: HTTP {resp.status_code}")
                    continue
                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type and "octet" not in content_type:
                    continue

                tmp_path = os.path.join(tmpdir, img["filename"])
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)

                # Skip tiny images (likely errors/placeholders)
                if os.path.getsize(tmp_path) < 10000:
                    continue

                # Upload to Immich
                asset_id = upload_to_immich(immich_url, api_key, tmp_path, img["filename"], img["description"])
                if asset_id:
                    asset_ids.append(asset_id)

                # Clean up temp file
                os.unlink(tmp_path)

                if (i + 1) % 10 == 0:
                    print(f"  Progress: {i+1}/{len(images)} downloaded, {len(asset_ids)} uploaded")

            except Exception as e:
                print(f"    [ERR] {img['filename']}: {e}")
                continue

            time.sleep(5)  # be gentle on Wikimedia rate limits

    # Add to album
    if asset_ids:
        # Batch in groups of 100
        for batch_start in range(0, len(asset_ids), 100):
            batch = asset_ids[batch_start:batch_start + 100]
            add_to_album(immich_url, api_key, album_id, batch)

    print(f"\n  Done: {len(asset_ids)} images uploaded to '{cat_config['album']}'")
    return len(asset_ids)


def main():
    parser = argparse.ArgumentParser(description="Load curated images into Immich")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    parser.add_argument("--category", type=str, help="Process single category (e.g. 'animals')")
    parser.add_argument("--count", type=int, help="Override target count per category")
    args = parser.parse_args()

    immich_url, api_key = get_immich_config()
    if not immich_url or not api_key:
        print("ERROR: Immich not configured in settings DB")
        sys.exit(1)

    print(f"Immich: {immich_url}")
    print(f"Pexels API key: {'SET' if PEXELS_KEY else 'NOT SET (photo categories will be skipped)'}")

    cats = {args.category: CATEGORIES[args.category]} if args.category else CATEGORIES
    total = 0

    for name, config in cats.items():
        if args.count:
            config = {**config, "target": args.count}
        total += process_category(name, config, immich_url, api_key, args.dry_run)

    print(f"\n{'='*60}")
    print(f"TOTAL: {total} images processed across {len(cats)} categories")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
