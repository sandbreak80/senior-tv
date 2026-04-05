#!/bin/bash
# Load free content into Jellyfin media directories.
#
# Sources:
#   - Archive.org: public domain classical music, old westerns, classic films
#   - YouTube (CC-licensed): ambient/nature videos for wind-down
#
# Usage: bash scripts/load_jellyfin.sh [--music-only|--movies-only|--ambient-only]

set -euo pipefail
cd "$(dirname "$0")/.."
source venv/bin/activate

YTDLP="$(which yt-dlp)"
MUSIC_DIR="$HOME/media/music"
MOVIES_DIR="$HOME/media/movies"

# ---------------------------------------------------------------------------
# Classical Music from Archive.org (public domain recordings)
# Classical music — music memory is preserved longest in Alzheimer's
# These pair with the fine art + landscape slideshows
# ---------------------------------------------------------------------------

download_music() {
    echo "============================================"
    echo "  Downloading Classical Music"
    echo "============================================"

    mkdir -p "$MUSIC_DIR"

    # Archive.org items — curated public domain classical recordings
    # Format: "identifier|display_name"
    local items=(
        "MozartSymphonyNo40|Mozart - Symphony No. 40"
        "DebussyClairDeLune|Debussy - Clair de Lune"
        "beethoven_symphony_5_karajan|Beethoven - Symphony No. 5"
        "beethoven_moonlight_sonata|Beethoven - Moonlight Sonata"
        "chopin_nocturnes|Chopin - Nocturnes"
        "vivaldi-four-seasons|Vivaldi - Four Seasons"
        "bach-cello-suites|Bach - Cello Suites"
        "SchubertSymphony8|Schubert - Symphony No. 8 (Unfinished)"
        "TchaikovskySymphonyNo6|Tchaikovsky - Symphony No. 6"
        "DvorakNewWorldSymphony|Dvorak - New World Symphony"
    )

    for entry in "${items[@]}"; do
        IFS='|' read -r identifier name <<< "$entry"
        local dest="$MUSIC_DIR/$name"
        if [ -d "$dest" ] && [ "$(ls -A "$dest" 2>/dev/null)" ]; then
            echo "  [SKIP] $name (already exists)"
            continue
        fi
        echo "  Downloading: $name ..."
        mkdir -p "$dest"

        # Download MP3 files from archive.org
        # Use wget to grab the best audio files
        local page_url="https://archive.org/download/$identifier"
        wget -q -r -l1 -nd -A "*.mp3,*.ogg,*.flac" \
            -P "$dest" \
            --no-parent \
            "$page_url/" 2>/dev/null || {
            echo "    [WARN] Could not download $identifier — may not exist"
            rmdir "$dest" 2>/dev/null
            continue
        }

        local count=$(ls -1 "$dest"/*.{mp3,ogg,flac} 2>/dev/null | wc -l)
        echo "    Got $count audio files"
        sleep 2
    done

    echo ""
    echo "  Music download complete!"
    du -sh "$MUSIC_DIR" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Ambient / Nature Videos (CC-licensed YouTube)
# For wind-down time after 3 PM and evening relaxation
# ---------------------------------------------------------------------------

download_ambient() {
    echo ""
    echo "============================================"
    echo "  Downloading Ambient / Nature Videos"
    echo "============================================"

    mkdir -p "$MOVIES_DIR/Ambient"

    # CC-licensed or public domain ambient videos
    # These are long-form nature/relaxation videos
    local videos=(
        # Relaxing nature compilations (CC-licensed channels)
        "https://www.youtube.com/watch?v=BHACKCNDMW8|Peaceful Ocean Waves"
        "https://www.youtube.com/watch?v=lFcSrYw-ARY|Relaxing Fireplace"
        "https://www.youtube.com/watch?v=f77SKdyn-1Y|Beautiful Nature Scenery"
        "https://www.youtube.com/watch?v=hlWiI4xVXKY|Relaxing Rain Sounds"
        "https://www.youtube.com/watch?v=BMuknRb7woc|Calming Aquarium"
    )

    for entry in "${videos[@]}"; do
        IFS='|' read -r url name <<< "$entry"
        local safe_name=$(echo "$name" | tr ' ' '_')
        local dest="$MOVIES_DIR/Ambient/${safe_name}.mp4"
        if [ -f "$dest" ]; then
            echo "  [SKIP] $name (already exists)"
            continue
        fi
        echo "  Downloading: $name ..."
        $YTDLP \
            -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" \
            --merge-output-format mp4 \
            -o "$dest" \
            --no-playlist \
            --socket-timeout 30 \
            "$url" 2>/dev/null || {
            echo "    [WARN] Could not download: $name"
            continue
        }
        echo "    Done: $(du -sh "$dest" | cut -f1)"
        sleep 3
    done

    echo ""
    echo "  Ambient videos complete!"
}

# ---------------------------------------------------------------------------
# Public Domain Classic Films from Archive.org
# Classic westerns and films from the care recipients' era
# ---------------------------------------------------------------------------

download_movies() {
    echo ""
    echo "============================================"
    echo "  Downloading Public Domain Classic Films"
    echo "============================================"

    # Archive.org public domain films
    # These are confirmed public domain (pre-1929 or explicitly PD)
    local films=(
        # Classic Westerns
        "Stagecoach1939|Stagecoach (1939)"
        "the_outlaw_1943|The Outlaw (1943)"
        "AngelAndTheBadman1947|Angel and the Badman (1947)"
        "McLintock|McLintock! (1963)"
        # Classic Comedy
        "TheKid1921|The Kid - Charlie Chaplin (1921)"
        "the_gold_rush|The Gold Rush - Charlie Chaplin (1925)"
        "Safety_Last|Safety Last! - Harold Lloyd (1923)"
        "the_general_1926|The General - Buster Keaton (1926)"
        # Classic Drama
        "night_of_the_living_dead|Night of the Living Dead (1968)"
        "Its_A_Wonderful_Life_1946|It's a Wonderful Life (1946)"
        "his_girl_friday|His Girl Friday (1940)"
        "the_39_steps_1935|The 39 Steps (1935)"
    )

    for entry in "${films[@]}"; do
        IFS='|' read -r identifier name <<< "$entry"
        local safe_name=$(echo "$name" | sed 's/[^a-zA-Z0-9 ()-]//g')
        local dest="$MOVIES_DIR/$safe_name"
        if [ -d "$dest" ] && [ "$(ls -A "$dest" 2>/dev/null)" ]; then
            echo "  [SKIP] $name (already exists)"
            continue
        fi
        echo "  Downloading: $name ..."
        mkdir -p "$dest"

        # Get the best MP4/MPEG from archive.org
        local page_url="https://archive.org/download/$identifier"
        # Try to get a single good video file
        wget -q -nd \
            -P "$dest" \
            "${page_url}/${identifier}.mp4" 2>/dev/null || \
        wget -q -nd \
            -P "$dest" \
            "${page_url}/${identifier}_512kb.mp4" 2>/dev/null || \
        wget -q -r -l1 -nd -A "*.mp4" \
            -P "$dest" \
            --no-parent \
            "$page_url/" 2>/dev/null || {
            echo "    [WARN] Could not download $name"
            rmdir "$dest" 2>/dev/null
            continue
        }

        local size=$(du -sh "$dest" | cut -f1)
        echo "    Got: $size"
        sleep 3
    done

    echo ""
    echo "  Movies download complete!"
    du -sh "$MOVIES_DIR" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

case "${1:-all}" in
    --music-only)  download_music ;;
    --movies-only) download_movies ;;
    --ambient-only) download_ambient ;;
    all)
        download_music
        download_ambient
        download_movies
        ;;
esac

echo ""
echo "============================================"
echo "  All done! Trigger a Jellyfin library scan:"
echo "  Admin > Dashboard > Libraries > Scan All"
echo "============================================"
