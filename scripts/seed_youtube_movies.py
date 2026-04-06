#!/usr/bin/env python3
"""Seed YouTube movies database with public domain classics.

Usage:
    python3 scripts/seed_youtube_movies.py          # Insert all movies
    python3 scripts/seed_youtube_movies.py --list    # Just print the list
    python3 scripts/seed_youtube_movies.py --dry-run # Show what would be inserted
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

movies = [
    # ===== WESTERNS (10) =====
    {"video_id": "_QnijAAAqv4", "title": "McLintock!", "year": 1963, "genre": "Western", "duration_minutes": 127},
    {"video_id": "Z7QkzDsIy5Q", "title": "Angel and the Badman", "year": 1947, "genre": "Western", "duration_minutes": 100},
    {"video_id": "y-5ZHTzd1hQ", "title": "Blue Steel", "year": 1934, "genre": "Western", "duration_minutes": 51},
    {"video_id": "n0Ivtv0P1FA", "title": "The Star Packer", "year": 1934, "genre": "Western", "duration_minutes": 55},
    {"video_id": "ECpRiMpQhiI", "title": "The Dawn Rider", "year": 1935, "genre": "Western", "duration_minutes": 54},
    {"video_id": "k7JeFX98460", "title": "Riders of Destiny", "year": 1933, "genre": "Western", "duration_minutes": 51},
    {"video_id": "YYN3Zn7a7fQ", "title": "The Lucky Texan", "year": 1934, "genre": "Western", "duration_minutes": 53},
    {"video_id": "L6e_HCmOGfw", "title": "Randy Rides Alone", "year": 1934, "genre": "Western", "duration_minutes": 52},
    {"video_id": "VF0yHHdICW4", "title": "West of the Divide", "year": 1934, "genre": "Western", "duration_minutes": 53},
    {"video_id": "4ljub_Qd1jI", "title": "The Man from Utah", "year": 1934, "genre": "Western", "duration_minutes": 51},
    {"video_id": "RAwZv9T0YV8", "title": "Sagebrush Trail", "year": 1933, "genre": "Western", "duration_minutes": 54},
    {"video_id": "hyxIZ8h6LUs", "title": "Neath the Arizona Skies", "year": 1934, "genre": "Western", "duration_minutes": 52},
    {"video_id": "yngrxUsiDzU", "title": "The Lawless Frontier", "year": 1934, "genre": "Western", "duration_minutes": 50},
    {"video_id": "v6x8R1kbhr8", "title": "The Outlaw", "year": 1943, "genre": "Western", "duration_minutes": 116},
    {"video_id": "GN_BYsJGYio", "title": "The Painted Desert", "year": 1931, "genre": "Western", "duration_minutes": 75},
    {"video_id": "qXTbgexyRcM", "title": "Santa Fe Trail", "year": 1940, "genre": "Western", "duration_minutes": 109},
    {"video_id": "nJfF5Ar0jYA", "title": "The Cisco Kid", "year": 1931, "genre": "Western", "duration_minutes": 62},

    # ===== COMEDIES (10) =====
    {"video_id": "kmYcT5gT6a4", "title": "His Girl Friday", "year": 1940, "genre": "Comedy", "duration_minutes": 92},
    {"video_id": "fiSjeLhg25w", "title": "My Man Godfrey", "year": 1936, "genre": "Comedy", "duration_minutes": 93},
    {"video_id": "5myY1ILoN8E", "title": "Africa Screams", "year": 1949, "genre": "Comedy", "duration_minutes": 79},
    {"video_id": "F89AU80mkQM", "title": "Jack and the Beanstalk", "year": 1952, "genre": "Comedy", "duration_minutes": 83},
    {"video_id": "fNsPlIwaNOg", "title": "The Flying Deuces", "year": 1939, "genre": "Comedy", "duration_minutes": 73},
    {"video_id": "Y15brea9qLQ", "title": "Utopia (Atoll K)", "year": 1951, "genre": "Comedy", "duration_minutes": 82},
    {"video_id": "D_UdtS-8QS0", "title": "The General", "year": 1926, "genre": "Comedy", "duration_minutes": 79},
    {"video_id": "Rf6rB3_t5rY", "title": "The Kid", "year": 1921, "genre": "Comedy", "duration_minutes": 68},
    {"video_id": "BjAn02ynpSg", "title": "The Gold Rush", "year": 1925, "genre": "Comedy", "duration_minutes": 87},
    {"video_id": "H_3Tyd3EVsU", "title": "Topper", "year": 1937, "genre": "Comedy", "duration_minutes": 97},
    {"video_id": "aZ2CuqGkHZ8", "title": "The Little Shop of Horrors", "year": 1960, "genre": "Comedy", "duration_minutes": 73},
    {"video_id": "gTXEr7sO9rQ", "title": "Have Rocket, Will Travel", "year": 1959, "genre": "Comedy", "duration_minutes": 76},

    # ===== DRAMAS (10) =====
    {"video_id": "6ROvPFaUl80", "title": "Charade", "year": 1963, "genre": "Drama", "duration_minutes": 113},
    {"video_id": "RmSdum4BMqI", "title": "The 39 Steps", "year": 1935, "genre": "Drama", "duration_minutes": 86},
    {"video_id": "IiCbaTkdEGM", "title": "Suddenly", "year": 1954, "genre": "Drama", "duration_minutes": 77},
    {"video_id": "BhbPMf7Jz10", "title": "D.O.A.", "year": 1949, "genre": "Drama", "duration_minutes": 84},
    {"video_id": "tap67KjjPu8", "title": "Detour", "year": 1945, "genre": "Drama", "duration_minutes": 68},
    {"video_id": "WGyEelzJaMs", "title": "Kansas City Confidential", "year": 1952, "genre": "Drama", "duration_minutes": 99},
    {"video_id": "MNRSxu22NxU", "title": "Scarlet Street", "year": 1945, "genre": "Drama", "duration_minutes": 102},
    {"video_id": "Q-iglYhLl-8", "title": "The Stranger", "year": 1946, "genre": "Drama", "duration_minutes": 91},
    {"video_id": "3ZOV4YhquXI", "title": "Meet John Doe", "year": 1941, "genre": "Drama", "duration_minutes": 123},
    {"video_id": "3ER9-pWmdxQ", "title": "Penny Serenade", "year": 1941, "genre": "Drama", "duration_minutes": 120},
    {"video_id": "iUI_Gb6UDiY", "title": "Cyrano de Bergerac", "year": 1950, "genre": "Drama", "duration_minutes": 113},
    {"video_id": "mAVEaMMQffA", "title": "A Star Is Born", "year": 1937, "genre": "Drama", "duration_minutes": 111},
    {"video_id": "RfgWByfinqI", "title": "The Man with the Golden Arm", "year": 1955, "genre": "Drama", "duration_minutes": 119},
    {"video_id": "xZeMB8rbDAs", "title": "The Phantom of the Opera", "year": 1925, "genre": "Drama", "duration_minutes": 89},

    # ===== MUSICALS (5) =====
    {"video_id": "HgWPPDrdhM0", "title": "Royal Wedding", "year": 1951, "genre": "Musical", "duration_minutes": 93},
    {"video_id": "LNmVnnulO8U", "title": "Second Chorus", "year": 1940, "genre": "Musical", "duration_minutes": 84},
    {"video_id": "sBgvmX9b2uU", "title": "Stage Door Canteen", "year": 1943, "genre": "Musical", "duration_minutes": 131},
    {"video_id": "Ogat6aVGC_4", "title": "Till the Clouds Roll By", "year": 1946, "genre": "Musical", "duration_minutes": 135},
    {"video_id": "mPkBwJiN4-M", "title": "The Bells of St. Mary's", "year": 1945, "genre": "Musical", "duration_minutes": 127},

    # ===== HOLIDAY (5) =====
    {"video_id": "C7reQ44-sLw", "title": "It's a Wonderful Life", "year": 1946, "genre": "Holiday", "duration_minutes": 91},
    {"video_id": "wonsUt5FfWo", "title": "A Christmas Carol", "year": 1951, "genre": "Holiday", "duration_minutes": 86},
    {"video_id": "eBedXP4T_Sg", "title": "Scrooge", "year": 1935, "genre": "Holiday", "duration_minutes": 78},
    {"video_id": "y4CKmmikN0s", "title": "March of the Wooden Soldiers", "year": 1934, "genre": "Holiday", "duration_minutes": 77},
    {"video_id": "KrfW-JoY-Iw", "title": "The Great Rupert", "year": 1950, "genre": "Holiday", "duration_minutes": 84},
    {"video_id": "1o9SskdQWzw", "title": "The Bishop's Wife", "year": 1947, "genre": "Holiday", "duration_minutes": 110},
]


def main():
    if "--list" in sys.argv:
        print(f"\n{'Genre':<10} {'Year':<6} {'Dur':<6} {'Title'}")
        print("-" * 60)
        for m in sorted(movies, key=lambda x: (x["genre"], x["title"])):
            print(f"{m['genre']:<10} {m['year']:<6} {m['duration_minutes']:<6} {m['title']}")
        print(f"\nTotal: {len(movies)} movies")
        genres = {}
        for m in movies:
            genres[m["genre"]] = genres.get(m["genre"], 0) + 1
        for g, c in sorted(genres.items()):
            print(f"  {g}: {c}")
        return

    from models import create_youtube_movie, get_youtube_movie_by_video_id

    dry_run = "--dry-run" in sys.argv
    inserted = 0
    skipped = 0

    for m in movies:
        existing = get_youtube_movie_by_video_id(m["video_id"])
        if existing:
            print(f"  SKIP (exists): {m['title']} ({m['year']})")
            skipped += 1
            continue

        if dry_run:
            print(f"  WOULD INSERT: {m['title']} ({m['year']}) [{m['genre']}]")
        else:
            m["added_by"] = "seed"
            create_youtube_movie(m)
            print(f"  INSERTED: {m['title']} ({m['year']}) [{m['genre']}]")
        inserted += 1

    print(f"\nDone. {'Would insert' if dry_run else 'Inserted'}: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
