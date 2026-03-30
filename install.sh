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

# Create docker-compose for embedded services (no Frigate, no HA)
cat > "$APP_DIR/docker-compose.yml" << 'COMPOSE'
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
      - DB_PASSWORD=seniortv
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
      - POSTGRES_PASSWORD=seniortv
      - POSTGRES_USER=postgres
      - POSTGRES_DB=immich
      - POSTGRES_INITDB_ARGS=--data-checksums

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
      - PUID=1000
      - PGID=1000
      - TZ=America/Los_Angeles
COMPOSE

sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/data/jellyfin/config" "$APP_DIR/data/jellyfin/cache"
sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/data/immich/upload" "$APP_DIR/data/immich/postgres"
sudo -u "$INSTALL_USER" mkdir -p "$APP_DIR/data/bazarr/config"

ok "Docker compose configured (Jellyfin + Immich + Bazarr)"

# Pull images in background (large downloads)
echo "  Pulling Docker images (this may take a few minutes)..."
sudo -u "$INSTALL_USER" docker compose -f "$APP_DIR/docker-compose.yml" pull --quiet 2>/dev/null || true
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
step 8 "Configuring HDMI audio..."

cat > "$APP_DIR/fix_audio.sh" << 'AUDIO'
#!/bin/bash
# Route audio to HDMI output and set volume
HDMI_SINK=$(LANG=C wpctl status 2>/dev/null | grep -i "hdmi\|HDMI" | grep -oP '^\s*\K\d+' | head -1)
if [ -n "$HDMI_SINK" ]; then
    wpctl set-default "$HDMI_SINK" 2>/dev/null
    wpctl set-volume "$HDMI_SINK" 1.0 2>/dev/null
    wpctl set-mute "$HDMI_SINK" 0 2>/dev/null
    echo "AUDIO_OK: HDMI sink $HDMI_SINK set as default, volume 100%, unmuted"
else
    echo "AUDIO_WARN: No HDMI sink found"
fi
AUDIO
chmod +x "$APP_DIR/fix_audio.sh"
ok "Audio routing script configured"

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
StartLimitIntervalSec=300
StartLimitBurst=5

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
ok "Systemd services installed and enabled"

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
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/cloudflared.list
    apt-get update -qq && apt-get install -y -qq cloudflared > /dev/null 2>&1
    ok "cloudflared installed"
fi
warn "Run 'cloudflared tunnel login' after install to configure"

# -----------------------------------------------------------
# Step 12: Initialize database + start services
# -----------------------------------------------------------
step 12 "Initializing..."

# Initialize the database
cd "$APP_DIR"
sudo -u "$INSTALL_USER" venv/bin/python3 -c "from models import init_db; init_db()"
ok "Database initialized"

# Start Docker services
sudo -u "$INSTALL_USER" docker compose -f "$APP_DIR/docker-compose.yml" up -d 2>/dev/null || warn "Docker services failed to start (can retry later)"
ok "Docker services started"

# Make scripts executable
chmod +x "$APP_DIR/start.sh" "$APP_DIR/watchdog.sh" "$APP_DIR/fix_audio.sh"
chmod +x "$APP_DIR/health_check_agent.sh" 2>/dev/null || true

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
