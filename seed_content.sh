#!/bin/bash
# Senior TV — Seed sample content for new deployments
# Downloads free-licensed nature/landscape photos for the screensaver
# and validates Immich connectivity.
#
# Usage: bash seed_content.sh [--photos-only]
#
# Photos source: Unsplash (CC0/Unsplash License — free for any use)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }

echo ""
echo "============================================"
echo "  Senior TV — Sample Content Setup"
echo "============================================"
echo ""

# -----------------------------------------------------------
# Sample Photos for Screensaver/Slideshow
# -----------------------------------------------------------
echo "Setting up sample photos..."

PHOTO_DIR="$SCRIPT_DIR/static/media/photos"
mkdir -p "$PHOTO_DIR"

# Curated list of beautiful, calming nature/landscape photos from Unsplash
# These are direct download URLs (Unsplash allows hotlinking for downloads)
# All photos are free for personal use under the Unsplash License
PHOTOS=(
    # Landscapes
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1920&q=80"  # Yosemite valley
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=1920&q=80"  # Foggy forest
    "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=1920&q=80"  # Sunlit forest
    "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=1920&q=80"  # Green valley
    "https://images.unsplash.com/photo-1500534623283-312aade485b7?w=1920&q=80"  # Mountain lake
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1920&q=80"  # Mountain peaks
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1920&q=80"  # Tropical beach
    "https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=1920&q=80"  # Ocean waves
    "https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?w=1920&q=80"  # Pine trees
    "https://images.unsplash.com/photo-1433086966358-54859d0ed716?w=1920&q=80"  # Waterfall
    # Flowers & Gardens
    "https://images.unsplash.com/photo-1490750967868-88aa4f44baee?w=1920&q=80"  # Lavender field
    "https://images.unsplash.com/photo-1462275646964-a0e3c11f18a6?w=1920&q=80"  # Sunflowers
    "https://images.unsplash.com/photo-1444021465936-c6ca81d39b84?w=1920&q=80"  # Rose garden
    "https://images.unsplash.com/photo-1490750967868-88aa4f44baee?w=1920&q=80"  # Tulip field
    "https://images.unsplash.com/photo-1468581264429-2548ef9eb732?w=1920&q=80"  # Cherry blossoms
    # Sunsets & Skies
    "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?w=1920&q=80"  # Golden sunset
    "https://images.unsplash.com/photo-1502790671504-542ad42d5189?w=1920&q=80"  # Purple sunset
    "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=1920&q=80"  # Starry sky
    "https://images.unsplash.com/photo-1534088568595-a066f410bcda?w=1920&q=80"  # Cloud panorama
    "https://images.unsplash.com/photo-1504701954957-2010ec3bcec1?w=1920&q=80"  # Sunset pier
    # Animals
    "https://images.unsplash.com/photo-1474511320723-9a56873571b7?w=1920&q=80"  # Deer in meadow
    "https://images.unsplash.com/photo-1425082661507-01ad497dc78e?w=1920&q=80"  # Birds flying
    "https://images.unsplash.com/photo-1437622368342-7a3d73a34c8f?w=1920&q=80"  # Sea turtle
    "https://images.unsplash.com/photo-1484406566174-9da000fda645?w=1920&q=80"  # Butterfly
    "https://images.unsplash.com/photo-1518020382113-a7e8fc38eac9?w=1920&q=80"  # Golden retriever
    # Cozy & Warm
    "https://images.unsplash.com/photo-1416339306562-f3d12fefd36f?w=1920&q=80"  # Autumn road
    "https://images.unsplash.com/photo-1418065460487-3e41a6c84dc5?w=1920&q=80"  # Fall foliage
    "https://images.unsplash.com/photo-1457269449834-928af64c684d?w=1920&q=80"  # Snowy cabin
    "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=1920&q=80"  # Lake house
    "https://images.unsplash.com/photo-1505765050516-f72dcac9c60e?w=1920&q=80"  # Autumn lake
)

DOWNLOADED=0
EXISTING=0
for i in "${!PHOTOS[@]}"; do
    FNAME="sample_$(printf '%02d' $((i+1))).jpg"
    FPATH="$PHOTO_DIR/$FNAME"
    if [ -f "$FPATH" ]; then
        EXISTING=$((EXISTING + 1))
        continue
    fi
    if curl -sfL "${PHOTOS[$i]}" -o "$FPATH" 2>/dev/null; then
        DOWNLOADED=$((DOWNLOADED + 1))
    fi
done
ok "Photos: $DOWNLOADED downloaded, $EXISTING already present (${#PHOTOS[@]} total)"

# -----------------------------------------------------------
# Upload to Immich if connected
# -----------------------------------------------------------
echo "Checking Immich connection..."

source venv/bin/activate 2>/dev/null || true

python3 -c "
import os, sys, glob, requests
sys.path.insert(0, '.')
from models import get_setting

immich_url = get_setting('immich_url') or ''
immich_key = get_setting('immich_api_key') or ''

if not immich_url or not immich_key:
    print('  ! Immich not configured — photos saved locally for screensaver')
    sys.exit(0)

# Check connection
try:
    r = requests.get(f'{immich_url}/api/server/ping', headers={'x-api-key': immich_key}, timeout=5)
    if not r.ok:
        print('  ! Immich not reachable — photos saved locally')
        sys.exit(0)
except:
    print('  ! Immich not reachable — photos saved locally')
    sys.exit(0)

# Check how many assets already exist
r = requests.get(f'{immich_url}/api/server/statistics', headers={'x-api-key': immich_key}, timeout=5)
if r.ok:
    stats = r.json()
    total = stats.get('photos', 0)
    if total > 0:
        print(f'  ✓ Immich already has {total} photos — skipping upload')
        sys.exit(0)

# Upload sample photos
photo_dir = 'static/media/photos'
uploaded = 0
for f in sorted(glob.glob(os.path.join(photo_dir, 'sample_*.jpg'))):
    try:
        with open(f, 'rb') as fp:
            r = requests.post(
                f'{immich_url}/api/assets',
                headers={'x-api-key': immich_key},
                files={'assetData': (os.path.basename(f), fp, 'image/jpeg')},
                data={'deviceAssetId': os.path.basename(f), 'deviceId': 'senior-tv-seed', 'fileCreatedAt': '2026-01-01T00:00:00.000Z', 'fileModifiedAt': '2026-01-01T00:00:00.000Z'},
                timeout=30,
            )
            if r.status_code in (200, 201):
                uploaded += 1
    except Exception as e:
        pass
print(f'  ✓ Uploaded {uploaded} sample photos to Immich')
"

echo ""
echo "============================================"
echo -e "  ${GREEN}Sample content ready!${NC}"
echo "============================================"
echo ""
echo "  Photos: $PHOTO_DIR/"
echo "  These will appear in the screensaver and photo slideshow."
echo "  Family can add their own photos via Immich or the admin panel."
echo ""
