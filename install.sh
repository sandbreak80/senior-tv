#!/bin/bash
set -e

# Senior TV — Full Installation Script
# Installs everything needed on a fresh Ubuntu 22.04/24.04 system.
# Target hardware: GMKtec G3S (Intel N95, 8GB RAM, 256GB SSD) or similar.
#
# Usage: git clone <repo> && cd senior_tv && sudo ./install.sh
#
# What this installs:
#   - Senior TV (Flask app + Chrome kiosk + systemd services)
#   - Jellyfin (personal media library)
#   - Immich (family photo portal, ML disabled)
#   - Bazarr (automatic subtitles)
#   - Tailscale (remote SSH access)
#   - Cloudflare Tunnel (remote admin panel access)
#   - Person detection model (MobileNet SSD, 23MB)
#   - Chrome with uBlock Origin (ad blocker)
#   - HDMI audio routing
#   - CEC TV control

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_USER="${SUDO_USER:-$(whoami)}"
INSTALL_HOME="$(eval echo ~$INSTALL_USER)"
APP_DIR="$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step() { echo -e "\n${BLUE}[$1/$TOTAL_STEPS]${NC} $2"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

TOTAL_STEPS=12

echo ""
echo "============================================"
echo "  Senior TV — Installation"
echo "============================================"
echo "  Target: $APP_DIR"
echo "  User:   $INSTALL_USER"
echo "  Home:   $INSTALL_HOME"
echo "============================================"
echo ""

# Must run as root (for apt, systemd, etc.)
if [ "$EUID" -ne 0 ]; then
    fail "Please run with sudo: sudo ./install.sh"
fi

# -----------------------------------------------------------
# Pre-flight checks
# -----------------------------------------------------------
echo "Running pre-flight checks..."

# Check RAM
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_RAM_MB" -lt 4000 ]; then
    fail "Need at least 4GB RAM (found ${TOTAL_RAM_MB}MB)"
fi
ok "RAM: ${TOTAL_RAM_MB}MB"

# Check disk
FREE_DISK_GB=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
if [ "$FREE_DISK_GB" -lt 20 ]; then
    fail "Need at least 20GB free disk (found ${FREE_DISK_GB}GB)"
fi
ok "Disk: ${FREE_DISK_GB}GB free"

# Check Ubuntu
if [ -f /etc/os-release ]; then
    . /etc/os-release
    ok "OS: $PRETTY_NAME"
fi

# Passwordless sudo for the install user (needed by watchdog, health agent, Claude Code)
if [ -f "/etc/sudoers.d/$INSTALL_USER" ] && grep -q "NOPASSWD" "/etc/sudoers.d/$INSTALL_USER" 2>/dev/null; then
    ok "Passwordless sudo already configured"
else
    echo "$INSTALL_USER ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/$INSTALL_USER"
    chmod 440 "/etc/sudoers.d/$INSTALL_USER"
    ok "Passwordless sudo configured for $INSTALL_USER"
fi

# -----------------------------------------------------------
# Step 1: System packages
# -----------------------------------------------------------
step 1 "Installing system packages..."

apt-get update -qq

apt-get install -y -qq \
    python3-venv python3-pip python3-dev \
    ffmpeg \
    cec-utils \
    xdotool \
    curl wget \
    alsa-utils \
    pipewire pipewire-pulse wireplumber \
    v4l-utils \
    git \
    sqlite3 \
    vainfo intel-media-va-driver-non-free \
    > /dev/null 2>&1

ok "System packages installed"

# -----------------------------------------------------------
# Step 2: Google Chrome
# -----------------------------------------------------------
step 2 "Installing Google Chrome..."

if command -v google-chrome &> /dev/null; then
    ok "Chrome already installed ($(google-chrome --version 2>/dev/null | head -1))"
else
    wget -q -O /tmp/chrome.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
    apt-get install -y -qq /tmp/chrome.deb > /dev/null 2>&1
    rm -f /tmp/chrome.deb
    ok "Chrome installed"
fi

# Chrome policy: force-install uBlock Origin
mkdir -p /etc/opt/chrome/policies/managed
cat > /etc/opt/chrome/policies/managed/senior_tv.json << 'POLICY'
{
  "ExtensionInstallForcelist": [
    "cjpalhdlnbpafiamejdnhcphjbkeiagm;https://clients2.google.com/service/update2/crx"
  ],
  "HomepageLocation": "http://localhost:5000",
  "RestoreOnStartup": 4,
  "RestoreOnStartupURLs": ["http://localhost:5000"]
}
POLICY
ok "uBlock Origin policy configured"

# Download uBlock Origin for sideloading (--kiosk mode blocks policy-based installs)
UBLOCK_DIR="$INSTALL_HOME/.config/senior-tv-chrome/ublock-origin"
if [ ! -f "$UBLOCK_DIR/manifest.json" ]; then
    sudo -u "$INSTALL_USER" mkdir -p "$UBLOCK_DIR"
    UBLOCK_CRX="/tmp/ublock.crx"
    curl -sL "https://clients2.google.com/service/update2/crx?response=redirect&os=linux&arch=x64&prodversion=146.0&acceptformat=crx2,crx3&x=id%3Dcjpalhdlnbpafiamejdnhcphjbkeiagm%26uc" -o "$UBLOCK_CRX" 2>/dev/null
    if [ -s "$UBLOCK_CRX" ]; then
        sudo -u "$INSTALL_USER" python3 -c "
import zipfile, io
with open('$UBLOCK_CRX', 'rb') as f:
    data = f.read()
idx = data.find(b'PK\x03\x04')
if idx >= 0:
    with zipfile.ZipFile(io.BytesIO(data[idx:])) as z:
        z.extractall('$UBLOCK_DIR')
"
        rm -f "$UBLOCK_CRX"
        ok "uBlock Origin downloaded for sideloading"
    else
        warn "uBlock Origin download failed (will retry on next install)"
    fi
else
    ok "uBlock Origin already installed"
fi

# Disable GNOME keyring password prompt (Chrome triggers unlock dialogs otherwise)
KEYRING_DIR="$INSTALL_HOME/.local/share/keyrings"
sudo -u "$INSTALL_USER" mkdir -p "$KEYRING_DIR"
if [ -f "$KEYRING_DIR/login.keyring" ]; then
    sudo -u "$INSTALL_USER" mv "$KEYRING_DIR/login.keyring" "$KEYRING_DIR/login.keyring.bak" 2>/dev/null
fi
ok "GNOME keyring unlock prompt disabled"

# -----------------------------------------------------------
# Step 3: Python virtual environment + dependencies
# -----------------------------------------------------------
step 3 "Setting up Python environment..."

cd "$APP_DIR"
sudo -u "$INSTALL_USER" python3 -m venv venv
sudo -u "$INSTALL_USER" venv/bin/pip install --quiet --upgrade pip
sudo -u "$INSTALL_USER" venv/bin/pip install --quiet -r requirements.txt
ok "Python venv created with $(venv/bin/pip list --format=columns 2>/dev/null | wc -l) packages"

# -----------------------------------------------------------
# Step 4: Person detection model
# -----------------------------------------------------------
step 4 "Setting up person detection model..."

mkdir -p "$APP_DIR/models"
if [ -f "$APP_DIR/models/MobileNetSSD_deploy.caffemodel" ]; then
    ok "Model already present (23MB)"
else
    sudo -u "$INSTALL_USER" curl -sL \
        "https://github.com/djmv/MobilNet_SSD_opencv/raw/master/MobileNetSSD_deploy.caffemodel" \
        -o "$APP_DIR/models/MobileNetSSD_deploy.caffemodel"
    sudo -u "$INSTALL_USER" curl -sL \
        "https://raw.githubusercontent.com/djmv/MobilNet_SSD_opencv/master/MobileNetSSD_deploy.prototxt" \
        -o "$APP_DIR/models/MobileNetSSD_deploy.prototxt"
    ok "MobileNet SSD model downloaded (23MB)"
fi

# -----------------------------------------------------------
# Step 5: Directory structure
# -----------------------------------------------------------
step 5 "Creating directory structure..."

sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/static/media/photos"
sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/static/camera_snaps"
sudo -u "$INSTALL_USER" mkdir -p "$INSTALL_HOME/media/movies"
sudo -u "$INSTALL_USER" mkdir -p "$INSTALL_HOME/media/shows"
sudo -u "$INSTALL_USER" mkdir -p "$INSTALL_HOME/media/music"
ok "Media directories created"

# -----------------------------------------------------------
# Step 6: Docker + embedded services (Jellyfin, Immich, Bazarr)
# -----------------------------------------------------------
step 6 "Installing Docker and media services..."

if command -v docker &> /dev/null; then
    ok "Docker already installed"
else
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "$INSTALL_USER"
    ok "Docker installed"
fi

# Generate secrets (preserve existing .env values if present)
if [ -f "$APP_DIR/.env" ]; then
    set -a; source "$APP_DIR/.env"; set +a
fi
IMMICH_DB_PASS="${IMMICH_DB_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_hex(16))")}"
FLASK_SECRET="${SENIOR_TV_SECRET:-$(python3 -c "import secrets; print(secrets.token_hex(32))")}"
SYSTEM_TZ=$(cat /etc/timezone 2>/dev/null || echo "America/New_York")
INSTALL_UID=$(id -u "$INSTALL_USER")
INSTALL_GID=$(id -g "$INSTALL_USER")

# Standardized credentials (override via .env or env vars)
JELLYFIN_USER="${JELLYFIN_USER:-seniortv}"
JELLYFIN_PASS="${JELLYFIN_PASS:-seniortv}"
IMMICH_ADMIN_EMAIL="${IMMICH_ADMIN_EMAIL:-bstoner@gmail.com}"
IMMICH_ADMIN_PASS="${IMMICH_ADMIN_PASS:-seniortv}"
CF_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"

# Write .env for secrets (not checked into git)
cat > "$APP_DIR/.env" << ENVFILE
SENIOR_TV_SECRET=$FLASK_SECRET
IMMICH_DB_PASSWORD=$IMMICH_DB_PASS
JELLYFIN_USER=$JELLYFIN_USER
JELLYFIN_PASS=$JELLYFIN_PASS
IMMICH_ADMIN_EMAIL=$IMMICH_ADMIN_EMAIL
IMMICH_ADMIN_PASS=$IMMICH_ADMIN_PASS
CLOUDFLARE_TUNNEL_TOKEN=$CF_TUNNEL_TOKEN
ENVFILE
chown "$INSTALL_USER:$INSTALL_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"
ok "Secrets generated (.env)"

# Create docker-compose for embedded services (no Frigate, no HA)
cat > "$APP_DIR/docker-compose.yml" << COMPOSE
version: "3.8"

# Senior TV — Embedded Services
# Jellyfin (media library), Immich (family photos), Bazarr (subtitles)

services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    container_name: jellyfin
    restart: unless-stopped
    ports:
      - "8096:8096"
    volumes:
      - ./data/jellyfin/config:/config
      - ./data/jellyfin/cache:/cache
      - ~/media/movies:/media/movies:ro
      - ~/media/shows:/media/shows:ro
      - ~/media/music:/media/music:ro
    devices:
      - /dev/dri:/dev/dri
    environment:
      - JELLYFIN_PublishedServerUrl=http://localhost:8096

  immich:
    image: ghcr.io/immich-app/immich-server:release
    container_name: immich
    restart: unless-stopped
    ports:
      - "2283:2283"
    volumes:
      - ./data/immich/upload:/usr/src/app/upload
      - /etc/localtime:/etc/localtime:ro
    environment:
      - DB_HOSTNAME=immich-postgres
      - DB_USERNAME=postgres
      - DB_PASSWORD=$IMMICH_DB_PASS
      - DB_DATABASE_NAME=immich
      - REDIS_HOSTNAME=immich-redis
    depends_on:
      - immich-redis
      - immich-postgres

  # Immich ML intentionally NOT included — saves ~400MB RAM on 8GB boxes.
  # Face recognition is nice-to-have; the photo portal is the feature.

  immich-redis:
    image: redis:7-alpine
    container_name: immich-redis
    restart: unless-stopped

  immich-postgres:
    image: tensorchord/pgvecto-rs:pg14-v0.2.0
    container_name: immich-postgres
    restart: unless-stopped
    volumes:
      - ./data/immich/postgres:/var/lib/postgresql/data
    environment:
      - POSTGRES_PASSWORD=$IMMICH_DB_PASS
      - POSTGRES_USER=postgres
      - POSTGRES_DB=immich
      - POSTGRES_INITDB_ARGS=--data-checksums

  # Nginx reverse proxy — single port 80 for Cloudflare tunnel
  # Routes: / → Flask (5000), /jellyfin/ → 8096, /immich/ → 2283
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - jellyfin
      - immich

  bazarr:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr
    restart: unless-stopped
    ports:
      - "6767:6767"
    volumes:
      - ./data/bazarr/config:/config
      - ~/media/movies:/movies
      - ~/media/shows:/tv
    environment:
      - PUID=$INSTALL_UID
      - PGID=$INSTALL_GID
      - TZ=$SYSTEM_TZ
COMPOSE

sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/data/jellyfin/config" "$APP_DIR/data/jellyfin/cache"
sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/data/immich/upload" "$APP_DIR/data/immich/postgres"
sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/data/bazarr/config"

ok "Docker compose configured (Jellyfin + Immich + Bazarr)"

# Pull images in background (large downloads)
echo "  Pulling Docker images (this may take a few minutes)..."
# Use sg to pick up the docker group immediately (usermod -aG doesn't apply until re-login)
sudo -u "$INSTALL_USER" sg docker -c "docker compose -f $APP_DIR/docker-compose.yml pull --quiet" 2>/dev/null || \
    docker compose -f "$APP_DIR/docker-compose.yml" pull --quiet 2>/dev/null || true
ok "Docker images pulled"

# -----------------------------------------------------------
# Step 7: Add user to required groups
# -----------------------------------------------------------
step 7 "Configuring user permissions..."

usermod -aG video "$INSTALL_USER" 2>/dev/null || true
usermod -aG audio "$INSTALL_USER" 2>/dev/null || true
usermod -aG docker "$INSTALL_USER" 2>/dev/null || true
ok "User $INSTALL_USER added to video, audio, docker groups"

# -----------------------------------------------------------
# Step 8: HDMI audio routing
# -----------------------------------------------------------
step 8 "Configuring display and HDMI audio..."

# --- Display: Set 1080p for HDMI (no 4K content, saves GPU/memory, correct font sizes) ---
# Write monitors.xml for both HDMI ports so GNOME applies 1080p on login regardless of which port is used.
# The start.sh script also enforces this via Mutter DBus API as a backup.
sudo -u "$INSTALL_USER" mkdir -p "$INSTALL_HOME/.config"
cat > "$INSTALL_HOME/.config/monitors.xml" << 'MONITORS'
<monitors version="2">
  <configuration>
    <logicalmonitor>
      <x>0</x>
      <y>0</y>
      <scale>1</scale>
      <primary>yes</primary>
      <monitor>
        <monitorspec>
          <connector>HDMI-1</connector>
          <vendor>SAM</vendor>
          <product>SAMSUNG</product>
          <serial>0x01000e00</serial>
        </monitorspec>
        <mode>
          <width>1920</width>
          <height>1080</height>
          <rate>60.000</rate>
        </mode>
      </monitor>
    </logicalmonitor>
  </configuration>
  <configuration>
    <logicalmonitor>
      <x>0</x>
      <y>0</y>
      <scale>1</scale>
      <primary>yes</primary>
      <monitor>
        <monitorspec>
          <connector>HDMI-2</connector>
          <vendor>SAM</vendor>
          <product>SAMSUNG</product>
          <serial>0x01000e00</serial>
        </monitorspec>
        <mode>
          <width>1920</width>
          <height>1080</height>
          <rate>60.000</rate>
        </mode>
      </monitor>
    </logicalmonitor>
  </configuration>
</monitors>
MONITORS
chown "$INSTALL_USER:$INSTALL_USER" "$INSTALL_HOME/.config/monitors.xml"
ok "Display set to 1080p (monitors.xml for HDMI-1 and HDMI-2)"

# --- HDMI Audio ---
chmod +x "$APP_DIR/fix_audio.sh"
# Test audio routing
sudo -u "$INSTALL_USER" bash "$APP_DIR/fix_audio.sh" 2>/dev/null && ok "HDMI audio configured" || warn "HDMI audio not detected (will retry on boot)"

# -----------------------------------------------------------
# Step 9: Systemd services
# -----------------------------------------------------------
step 9 "Installing systemd services..."

# Main service
cat > /etc/systemd/system/senior-tv.service << EOF
[Unit]
Description=Senior TV Entertainment System
After=network.target graphical.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=$INSTALL_USER
WorkingDirectory=$APP_DIR
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u $INSTALL_USER)
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u $INSTALL_USER)/bus
ExecStartPre=/bin/sleep 5
ExecStart=$APP_DIR/start.sh
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

# Watchdog service
cat > /etc/systemd/system/senior-tv-watchdog.service << EOF
[Unit]
Description=Senior TV Watchdog
After=senior-tv.service

[Service]
Type=oneshot
User=$INSTALL_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/watchdog.sh
EOF

# Watchdog timer (every 3 minutes)
cat > /etc/systemd/system/senior-tv-watchdog.timer << 'EOF'
[Unit]
Description=Senior TV Watchdog Timer

[Timer]
OnBootSec=120
OnUnitActiveSec=180
AccuracySec=30

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable senior-tv.service
systemctl enable senior-tv-watchdog.timer

# Cron jobs (screenshots + health check agent)
CRON_TMP=$(mktemp /tmp/senior-tv-cron.XXXXXX)
chmod 644 "$CRON_TMP"
sudo -u "$INSTALL_USER" crontab -l 2>/dev/null | grep -v "senior_tv\|take_screenshot\|health_check_agent" > "$CRON_TMP" || true
echo "*/15 * * * * $APP_DIR/take_screenshot.sh" >> "$CRON_TMP"
echo "7 * * * * $APP_DIR/health_check_agent.sh" >> "$CRON_TMP"
sudo -u "$INSTALL_USER" crontab "$CRON_TMP"
rm -f "$CRON_TMP"

# Screenshots directory
sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/screenshots"

# Log files (writable by install user)
touch /var/log/senior-tv-watchdog.log /var/log/senior-tv-repairs.log /var/log/senior-tv-claude-check.log
chown "$INSTALL_USER:$INSTALL_USER" /var/log/senior-tv-*.log

ok "Systemd services, cron jobs, log files installed and enabled"

# -----------------------------------------------------------
# Step 10: Tailscale
# -----------------------------------------------------------
step 10 "Installing Tailscale..."

if command -v tailscale &> /dev/null; then
    ok "Tailscale already installed"
else
    curl -fsSL https://tailscale.com/install.sh | sh
    ok "Tailscale installed"
fi
warn "Run 'sudo tailscale up --ssh' after install to connect"

# -----------------------------------------------------------
# Step 11: Cloudflare Tunnel
# -----------------------------------------------------------
step 11 "Installing Cloudflare Tunnel..."

if command -v cloudflared &> /dev/null; then
    ok "cloudflared already installed"
else
    mkdir -p --mode=0755 /usr/share/keyrings
    curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg \
        | tee /usr/share/keyrings/cloudflare-public-v2.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared any main" \
        > /etc/apt/sources.list.d/cloudflared.list
    apt-get update -qq && apt-get install -y -qq cloudflared > /dev/null 2>&1
    ok "cloudflared installed"
fi

# Auto-register tunnel service if token provided
if [ -n "$CF_TUNNEL_TOKEN" ]; then
    if systemctl is-active --quiet cloudflared 2>/dev/null; then
        ok "Cloudflare tunnel already running"
    else
        cloudflared service install "$CF_TUNNEL_TOKEN" 2>/dev/null && ok "Cloudflare tunnel registered and started" || warn "Cloudflare tunnel registration failed (check token)"
    fi
else
    warn "No CLOUDFLARE_TUNNEL_TOKEN in .env — set it and run: sudo cloudflared service install <token>"
fi

# -----------------------------------------------------------
# Step 12: Initialize database + start services + configure
# -----------------------------------------------------------
step 12 "Initializing..."

# Load secrets into environment for Flask
cd "$APP_DIR"
if [ -f "$APP_DIR/.env" ]; then
    set -a; source "$APP_DIR/.env"; set +a
fi

# Initialize the database
sudo -u "$INSTALL_USER" SENIOR_TV_SECRET="$FLASK_SECRET" venv/bin/python3 -c "from models import init_db; init_db()"
ok "Database initialized"

# Start Docker services (sg docker to pick up group without re-login)
sudo -u "$INSTALL_USER" sg docker -c "docker compose -f $APP_DIR/docker-compose.yml up -d" 2>/dev/null || \
    docker compose -f "$APP_DIR/docker-compose.yml" up -d 2>/dev/null || warn "Docker services failed to start (can retry later)"

# Wait for Docker services to be healthy
echo "  Waiting for services to start..."
for i in $(seq 1 60); do
    JELLY=0; IMMICH=0
    curl -sf http://localhost:8096 > /dev/null 2>&1 && JELLY=1
    curl -sf http://localhost:2283 > /dev/null 2>&1 && IMMICH=1
    [ "$JELLY" -eq 1 ] && [ "$IMMICH" -eq 1 ] && break
    sleep 2
done
[ "$JELLY" -eq 1 ] && ok "Jellyfin is up" || warn "Jellyfin not ready yet"
[ "$IMMICH" -eq 1 ] && ok "Immich is up" || warn "Immich not ready yet"

# Make scripts executable
chmod +x "$APP_DIR/start.sh" "$APP_DIR/watchdog.sh" "$APP_DIR/fix_audio.sh"
chmod +x "$APP_DIR/health_check_agent.sh" 2>/dev/null || true

# -----------------------------------------------------------
# Step 12a: Auto-configure Jellyfin
# -----------------------------------------------------------
echo "  Configuring Jellyfin..."

if [ "$JELLY" -eq 1 ]; then
    # Check if Jellyfin needs first-time setup
    JELLY_STARTUP=$(curl -sf http://localhost:8096/Startup/Configuration 2>/dev/null)
    if [ $? -eq 0 ]; then
        # First-time setup — run wizard via API
        # Set initial config
        curl -sf -X POST http://localhost:8096/Startup/Configuration \
            -H "Content-Type: application/json" \
            -d '{"UICulture":"en-US","MetadataCountryCode":"US","PreferredMetadataLanguage":"en"}' > /dev/null 2>&1

        # Create admin user
        curl -sf -X POST http://localhost:8096/Startup/User \
            -H "Content-Type: application/json" \
            -d "{\"Name\":\"$JELLYFIN_USER\",\"Password\":\"$JELLYFIN_PASS\"}" > /dev/null 2>&1

        # Set remote access
        curl -sf -X POST http://localhost:8096/Startup/RemoteAccess \
            -H "Content-Type: application/json" \
            -d '{"EnableRemoteAccess":true,"EnableAutomaticPortMapping":false}' > /dev/null 2>&1

        # Complete wizard
        curl -sf -X POST http://localhost:8096/Startup/Complete > /dev/null 2>&1
        ok "Jellyfin first-time setup completed (user: $JELLYFIN_USER)"
    else
        ok "Jellyfin already configured"
    fi

    # Authenticate and get token
    JELLY_AUTH=$(curl -sf -X POST http://localhost:8096/Users/AuthenticateByName \
        -H "Content-Type: application/json" \
        -H "X-Emby-Authorization: MediaBrowser Client=\"SeniorTV\", Device=\"Installer\", DeviceId=\"install-script\", Version=\"1.0\"" \
        -d "{\"Username\":\"$JELLYFIN_USER\",\"Pw\":\"$JELLYFIN_PASS\"}" 2>/dev/null)

    if [ -n "$JELLY_AUTH" ]; then
        JELLY_TOKEN=$(echo "$JELLY_AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['AccessToken'])" 2>/dev/null)
        JELLY_USER_ID=$(echo "$JELLY_AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['User']['Id'])" 2>/dev/null)

        if [ -n "$JELLY_TOKEN" ]; then
            # Create libraries if they don't exist
            EXISTING_LIBS=$(curl -sf "http://localhost:8096/Library/VirtualFolders" \
                -H "X-Emby-Token: $JELLY_TOKEN" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)

            if [ "${EXISTING_LIBS:-0}" -eq 0 ]; then
                curl -sf -X POST "http://localhost:8096/Library/VirtualFolders?name=Movies&collectionType=movies&refreshLibrary=false" \
                    -H "X-Emby-Token: $JELLY_TOKEN" \
                    -H "Content-Type: application/json" \
                    -d '{"LibraryOptions":{"Enabled":true,"EnableRealtimeMonitor":true,"PathInfos":[{"Path":"/media/movies"}]}}' > /dev/null 2>&1
                curl -sf -X POST "http://localhost:8096/Library/VirtualFolders?name=Shows&collectionType=tvshows&refreshLibrary=false" \
                    -H "X-Emby-Token: $JELLY_TOKEN" \
                    -H "Content-Type: application/json" \
                    -d '{"LibraryOptions":{"Enabled":true,"EnableRealtimeMonitor":true,"PathInfos":[{"Path":"/media/shows"}]}}' > /dev/null 2>&1
                curl -sf -X POST "http://localhost:8096/Library/VirtualFolders?name=Music&collectionType=music&refreshLibrary=false" \
                    -H "X-Emby-Token: $JELLY_TOKEN" \
                    -H "Content-Type: application/json" \
                    -d '{"LibraryOptions":{"Enabled":true,"EnableRealtimeMonitor":true,"PathInfos":[{"Path":"/media/music"}]}}' > /dev/null 2>&1
                ok "Jellyfin libraries created (Movies, Shows, Music)"
            else
                ok "Jellyfin libraries already exist ($EXISTING_LIBS)"
            fi

            # Create permanent API key
            curl -sf -X POST "http://localhost:8096/Auth/Keys?app=SeniorTV" \
                -H "X-Emby-Token: $JELLY_TOKEN" > /dev/null 2>&1
            JELLY_API_KEY=$(curl -sf "http://localhost:8096/Auth/Keys" \
                -H "X-Emby-Token: $JELLY_TOKEN" \
                | python3 -c "import sys,json; keys=json.load(sys.stdin)['Items']; print(next(k['AccessToken'] for k in keys if k['AppName']=='SeniorTV'))" 2>/dev/null)

            if [ -n "$JELLY_API_KEY" ]; then
                # Store in Senior TV database
                sudo -u "$INSTALL_USER" venv/bin/python3 -c "
from models import get_db_safe
with get_db_safe() as db:
    for k,v in [('jellyfin_url','http://localhost:8096'),('jellyfin_api_key','$JELLY_API_KEY'),('jellyfin_user_id','$JELLY_USER_ID'),('jellyfin_username','$JELLYFIN_USER'),('jellyfin_password','$JELLYFIN_PASS')]:
        db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, v))
    db.commit()
"
                ok "Jellyfin API key stored in Senior TV settings"

                # Configure hardware transcoding (Intel VA-API)
                if [ -e /dev/dri/renderD128 ]; then
                    curl -sf -X POST "http://localhost:8096/System/Configuration/encoding" \
                        -H "X-Emby-Token: $JELLY_TOKEN" \
                        -H "Content-Type: application/json" \
                        -d '{
                            "EncodingThreadCount": -1,
                            "EnableAudioVbr": true,
                            "DownMixAudioBoost": 2,
                            "MaxMuxingQueueSize": 2048,
                            "EnableThrottling": true,
                            "ThrottleDelaySeconds": 180,
                            "HardwareAccelerationType": "vaapi",
                            "VaapiDevice": "/dev/dri/renderD128",
                            "EnableTonemapping": true,
                            "EnableVppTonemapping": true,
                            "H264Crf": 23,
                            "H265Crf": 28,
                            "EnableDecodingColorDepth10Hevc": true,
                            "EnableDecodingColorDepth10Vp9": true,
                            "PreferSystemNativeHwDecoder": true,
                            "EnableIntelLowPowerH264HwEncoder": true,
                            "EnableIntelLowPowerHevcHwEncoder": true,
                            "EnableHardwareEncoding": true,
                            "AllowHevcEncoding": true,
                            "AllowAv1Encoding": false,
                            "EnableSubtitleExtraction": true,
                            "HardwareDecodingCodecs": ["h264","hevc","mpeg2video","vc1","vp8","vp9","av1"]
                        }' > /dev/null 2>&1
                    ok "Jellyfin VA-API hardware transcoding enabled"
                else
                    warn "No /dev/dri/renderD128 — Jellyfin will use software transcoding"
                fi
            fi
        fi
    else
        warn "Jellyfin authentication failed — configure manually at http://localhost:8096"
    fi
else
    warn "Jellyfin not ready — configure manually after services start"
fi

# -----------------------------------------------------------
# Step 12b: Auto-configure Immich
# -----------------------------------------------------------
echo "  Configuring Immich..."

if [ "$IMMICH" -eq 1 ]; then
    # Try to sign up admin (only works on first run)
    IMMICH_SIGNUP=$(curl -sf -X POST http://localhost:2283/api/auth/admin-sign-up \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$IMMICH_ADMIN_EMAIL\",\"password\":\"$IMMICH_ADMIN_PASS\",\"name\":\"seniortv\"}" 2>/dev/null)

    if [ -n "$IMMICH_SIGNUP" ]; then
        ok "Immich admin account created ($IMMICH_ADMIN_EMAIL)"
    else
        ok "Immich admin already exists"
    fi

    # Authenticate
    IMMICH_AUTH=$(curl -sf -X POST http://localhost:2283/api/auth/login \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$IMMICH_ADMIN_EMAIL\",\"password\":\"$IMMICH_ADMIN_PASS\"}" 2>/dev/null)

    if [ -n "$IMMICH_AUTH" ]; then
        IMMICH_TOKEN=$(echo "$IMMICH_AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])" 2>/dev/null)
        IMMICH_USER_ID=$(echo "$IMMICH_AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['userId'])" 2>/dev/null)

        if [ -n "$IMMICH_TOKEN" ]; then
            # Create permanent API key
            IMMICH_API_KEY=$(curl -sf -X POST http://localhost:2283/api/api-keys \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer $IMMICH_TOKEN" \
                -d '{"name":"SeniorTV","permissions":["all"]}' \
                | python3 -c "import sys,json; print(json.load(sys.stdin)['secret'])" 2>/dev/null)

            if [ -n "$IMMICH_API_KEY" ]; then
                # Disable ML (no ML container, saves ~400MB RAM)
                IMMICH_CONFIG=$(curl -sf http://localhost:2283/api/system-config \
                    -H "x-api-key: $IMMICH_API_KEY")
                echo "$IMMICH_CONFIG" | python3 -c "
import sys, json
c = json.load(sys.stdin)
c['machineLearning']['enabled'] = False
c['map']['enabled'] = False
# Reduce job concurrency for 8GB RAM systems
c['job']['thumbnailGeneration']['concurrency'] = 2
c['job']['metadataExtraction']['concurrency'] = 2
c['job']['videoConversion']['concurrency'] = 1
c['job']['smartSearch']['concurrency'] = 1
c['job']['backgroundTask']['concurrency'] = 1
c['job']['migration']['concurrency'] = 1
# Enable VA-API hardware video transcoding if available
import os
if os.path.exists('/dev/dri/renderD128'):
    c['ffmpeg']['accel'] = 'vaapi'
    c['ffmpeg']['accelDecode'] = True
json.dump(c, sys.stdout)
" | curl -sf -X PUT http://localhost:2283/api/system-config \
                    -H "x-api-key: $IMMICH_API_KEY" \
                    -H "Content-Type: application/json" \
                    -d @- > /dev/null 2>&1
                ok "Immich ML disabled, jobs tuned for low-RAM, VA-API enabled"

                # Create library
                curl -sf -X POST http://localhost:2283/api/libraries \
                    -H "x-api-key: $IMMICH_API_KEY" \
                    -H "Content-Type: application/json" \
                    -d "{\"name\":\"Family Photos\",\"ownerId\":\"$IMMICH_USER_ID\",\"importPaths\":[\"/usr/src/app/upload\"],\"exclusionPatterns\":[\"**/thumbs/**\",\"**/encoded-video/**\"]}" > /dev/null 2>&1

                # Store in Senior TV database
                sudo -u "$INSTALL_USER" venv/bin/python3 -c "
from models import get_db_safe
with get_db_safe() as db:
    for k,v in [('immich_url','http://localhost:2283'),('immich_api_key','$IMMICH_API_KEY')]:
        db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, v))
    db.commit()
"
                ok "Immich API key stored in Senior TV settings"
            fi
        fi
    else
        warn "Immich authentication failed — configure manually at http://localhost:2283"
    fi
else
    warn "Immich not ready — configure manually after services start"
fi

# -----------------------------------------------------------
# Step 12c: Apply environment settings to database
# -----------------------------------------------------------
echo "  Applying settings from environment..."

sudo -u "$INSTALL_USER" venv/bin/python3 -c "
import os
from models import get_db_safe

env_to_setting = {
    'GREETING_NAMES': 'greeting_names',
    'WEATHER_LAT': 'weather_lat',
    'WEATHER_LON': 'weather_lon',
    'ADMIN_PASSWORD': 'admin_password',
    'HA_URL': 'ha_url',
    'HA_TOKEN': 'ha_token',
    'HA_TV_ENTITY': 'ha_tv_entity',
    'FRIGATE_URL': 'frigate_url',
    'FRIGATE_CAMERAS': 'frigate_cameras',
}

with get_db_safe() as db:
    applied = 0
    for env_key, setting_key in env_to_setting.items():
        val = os.environ.get(env_key, '')
        if val:
            db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (setting_key, val))
            applied += 1
    db.commit()
    print(f'Applied {applied} settings from environment')
"

# -----------------------------------------------------------
# Step 12d: Seed sample content (photos for screensaver)
# -----------------------------------------------------------
echo "  Seeding sample content..."
sudo -u "$INSTALL_USER" bash "$APP_DIR/seed_content.sh" 2>/dev/null && ok "Sample photos seeded" || warn "Sample content skipped (can run later: bash seed_content.sh)"

echo ""
echo "============================================"
echo "  ${GREEN}Installation Complete!${NC}"
echo "============================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. BIOS: Set 'Restore on AC Power Loss = Power On'"
echo "     (so the system recovers from power outages)"
echo ""
echo "  2. Reboot to start Senior TV:"
echo "     ${YELLOW}sudo reboot${NC}"
echo ""
echo "  3. After reboot, the TV should show the home screen."
echo "     Open the admin panel from any device on your network:"
echo "     ${YELLOW}http://$(hostname -I | awk '{print $1}'):5000/admin${NC}"
echo ""
echo "  4. Remote access (optional):"
echo "     ${YELLOW}sudo tailscale up --ssh${NC}"
echo "     ${YELLOW}cloudflared tunnel login${NC}"
echo ""
echo "  5. Copy movies/shows to: ${YELLOW}~/media/movies/${NC} and ${YELLOW}~/media/shows/${NC}"
echo "     Jellyfin will find them automatically at http://localhost:8096"
echo ""
echo "  6. Family photo uploads:"
echo "     Immich is running at http://localhost:2283"
echo "     Or use the admin panel: http://localhost:5000/admin/photos"
echo ""
echo "  Hardware:"
echo "  - Plug a USB webcam in for presence detection + volume monitoring"
echo "  - TV connects via HDMI (CEC remote control works automatically)"
echo "  - Front door IP camera: configure in admin settings"
echo ""
echo "============================================"
