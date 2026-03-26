# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Senior TV is a full-screen kiosk-style entertainment, communication, and care system for Don & Colleen (both 95, born 1931). Don has mid-stage dementia; Colleen has advanced Alzheimer's. TV is their primary daily activity. The system runs on a GMKtec NucBox K11 mini PC (Ubuntu 24.04, 4K) connected to a Samsung 65" TV via HDMI in Sun City, CA.

## Architecture

- **Flask app** (`server.py`) — serves TV UI + admin panel on port 5000
- **Chrome kiosk mode** — full-screen browser, uBlock Origin ad blocker via Chrome policy
- **HDMI-CEC bridge** (`cec_bridge.py`) — tries kernel CEC (`cec-ctl`), falls back to libCEC (`cec-client`), exits gracefully if no CEC hardware
- **CEC TV control** (`cec_control.py`) — power on/off, input switching; tier 1: kernel CEC, tier 2: Home Assistant Samsung TV API
- **SQLite** (`senior_tv.db`) — pills, calendar, birthdays, messages, favorites, settings
- **APScheduler** (`scheduler.py`) — pill reminders (1 min), birthday checks (1 hr), show alerts (10 min)
- **SSE** (`/events`) — pushes pill reminders, doorbell alerts, show notifications, family messages to TV
- **Jellyfin API** (`jellyfin_api.py`) — media library: 5,112 movies + 108 shows at `192.168.50.20:8096`
- **Pluto TV** (`pluto_tv.py`) — 421 free live TV channels via HLS, logos via `path` key (not `url`)
- **Immich API** (`immich_api.py`) — 143K family photos from Immich server at `192.168.50.165:2283`; photos proxied through `/api/immich-photo/<id>` to hide API key
- **Smart Home** (`smart_home.py`) — Frigate person detection on front_door camera, HA integration
- **Process supervision** (`start.sh`) — monitors Flask + Chrome + CEC bridge every 10s, restarts any that die
- **systemd** (`senior-tv.service`) — auto-start on boot, `Restart=always`
- **Watchdog** (`watchdog.sh`) — runs every 3 min via systemd timer; checks/repairs Flask, Chrome, audio, network, Tailscale, disk, memory
- **Health agent** (`health_check_agent.sh`) — hourly cron runs Claude CLI to diagnose and fix issues, takes desktop screenshot

## Key Design Constraints

- **Don** can follow structured content: game shows, sports, sitcoms, westerns
- **Colleen** needs low/no-plot: music, ambient, familiar visuals (music memory preserved longest)
- Persistent title bar on all players — they forget what's watching
- No news/high-stimulation content after 3 PM (sundowning); wind-down ambient video plays instead
- Shower reminders (Tue/Thu) block TV for 15 minutes — can't dismiss (safety timeout auto-unlocks after 2x)
- All text minimum 36px, high contrast dark theme
- Navigation: arrow keys + Enter + Escape only (6 buttons via Samsung remote → CEC → xdotool)
- Time-of-day content: morning (game shows, news), afternoon (westerns, comedy), evening (wind down)
- YouTube iframes are fully locked: `sandbox` without `allow-popups`, transparent click-blocking overlays, `disablekb=1`, `iv_load_policy=3`, `fs=0`, `playlist+loop` to prevent end screens
- All page exits use `window.quickNav()` which kills iframes/videos/images before navigating for instant response

## Navigation Architecture

`static/js/tv.js` implements row-aware navigation for the Samsung remote:
- All interactive elements have class `navigable`
- `getRowOf(el)` groups items by parent container (`home-poster-row`, `poster-row`, `home-quick-menu`, `menu-list`, `category-tabs`, etc.)
- **Left/Right** moves within a row; **Up/Down** jumps between rows, landing on the closest item by horizontal position (via `getBoundingClientRect`)
- `window.quickNav(url)` is a global function that kills all iframes/videos/images, fades to black, then navigates — used by every page for instant back-button response

## Connected Services

| Service | URL | Auth |
|---------|-----|------|
| Jellyfin | `http://192.168.50.20:8096` | API key in settings |
| Frigate | `https://192.168.50.114:8971` | Session cookie login |
| Home Assistant | `http://192.168.50.76:8123` | Long-lived token |
| Immich | `http://192.168.50.165:2283` | API key in settings |
| Pluto TV | Public API | No auth |
| Open-Meteo | Public API | No auth (Sun City, CA: 33.7083, -117.1972) |

## Deployment & Remote Access

- **SSH** via Tailscale: `ssh media@media-nucbox-k11` (key-only auth, no passwords)
- **Tailscale** mesh VPN with SSH enabled (`tailscale up --ssh`)
- **Health endpoint**: `GET /api/health` returns JSON status of all subsystems
- **BIOS**: Set "Restore on AC Power Loss = Power On" for power failure recovery

## Commands

```bash
# Development
source venv/bin/activate
python3 server.py                    # http://localhost:5000

# Production
sudo systemctl restart senior-tv     # Restart app + Chrome + CEC bridge
sudo systemctl status senior-tv      # Check status
journalctl -u senior-tv -f           # Tail logs

# Health check
curl -s http://localhost:5000/api/health | python3 -m json.tool

# Watchdog logs
cat /var/log/senior-tv-watchdog.log
cat /var/log/senior-tv-repairs.log
cat /var/log/senior-tv-claude-check.log

# Fix audio manually
bash fix_audio.sh

# Lint
source venv/bin/activate && ruff check *.py

# UI tests
source venv/bin/activate && python3 test_ui.py

# Desktop screenshot (Wayland)
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus DISPLAY=:0 gnome-screenshot -f screenshot.png
```

## TV UI Routes

- `/` — Hotel TV home screen (time-aware content, weather, greeting, wind-down video after 3PM, Immich photo widget, Jellyfin recommendations)
- `/tv/live` — Pluto TV channels (421), category tabs, channel logos, HLS player
- `/tv/plex` — Jellyfin library browser (continue watching, recently added, daily movies)
- `/tv/plex/daily` — 20 random movies that rotate daily
- `/tv/plex/library/<id>` — Browse with genre filters, sort options, pagination
- `/tv/plex/show/<id>` — Season/episode picker with shuffle play
- `/tv/plex/play/<id>` — Built-in HTML5 video player (persistent title, skip, volume)
- `/tv/youtube` — 36 curated channels in 12 categories (thumbnails with letter-initial fallback)
- `/tv/youtube/channel/<id>` — Channel video browser (via RSS feed)
- `/tv/youtube/watch/<id>` — YouTube player (sandboxed iframe, click-blocking overlay, loops)
- `/tv/messages` — Family message inbox
- `/tv/messages/<id>` — Full-screen message view (text, photo, video)
- `/tv/news` — Live YouTube news + Pluto news channels
- `/tv/weather` — Current + 5-day forecast
- `/tv/calendar` — Daily/monthly/upcoming views (holidays pre-loaded)
- `/tv/photos` — Photo frame slideshow (Immich + uploaded + NAS photos; also idle screensaver after 10 min)

## Admin Panel Routes (`/admin`)

Accessible from any device on LAN at `http://192.168.50.159:5000/admin`

- `/admin` — Dashboard (pill status, upcoming events)
- `/admin/messages` — Send text, photos, videos to the TV
- `/admin/pills` — Manage reminders (morning 11am, evening 8:30pm, shower Tue/Thu)
- `/admin/birthdays` — Birthday greetings with age calculation
- `/admin/shows` — Favorite show alerts (monitored on Pluto TV)
- `/admin/calendar` — Events
- `/admin/youtube` — Curate YouTube channels
- `/admin/photos` — Upload family photos
- `/admin/plex-setup` — Jellyfin connection
- `/admin/settings` — Weather, Frigate, HA, Immich, photo NAS path, TV entity ID, all config

## API Endpoints

- `GET /api/health` — System health (disk, memory, Chrome, CEC, audio, Jellyfin, Immich, internet, Tailscale, scheduler, watchdog)
- `GET /api/immich-photo/<id>` — Proxy Immich photos (hides API key)
- `GET /api/immich-slideshow?count=N` — Random Immich photos for slideshow
- `GET /api/home-data` — Auto-refresh data for home screen
- `GET /api/daily-digest` — Quote and "on this day" history
- `GET /api/has-photos` — Check if any photos available (for screensaver guard)
- `POST /api/acknowledge` — Dismiss pill/shower reminder

## File Layout

- `server.py` — Flask app, all routes, health endpoint
- `config.py` — defaults and connected service URLs
- `models.py` — SQLite schema, CRUD helpers with `get_db_safe()` context manager
- `scheduler.py` — APScheduler: pills (1 min), birthdays (1 hr), show alerts (10 min)
- `smart_home.py` — Frigate polling thread, HA API helpers, doorbell alerts
- `jellyfin_api.py` — Jellyfin REST client (libraries, items, seasons, episodes, streams)
- `pluto_tv.py` — Pluto TV boot/channels API, HLS stream URLs, session token refresh on 401
- `immich_api.py` — Immich REST client (random photos, photo proxy, connection test)
- `cec_bridge.py` — HDMI-CEC listener: kernel CEC → libCEC → graceful idle
- `cec_control.py` — TV power/input control: kernel CEC → Home Assistant fallback
- `cache.py` — Simple TTL cache (in-memory dict)
- `start.sh` — Boot script with process supervision loop (Flask + Chrome + CEC)
- `watchdog.sh` — Local self-repair (3 min interval via systemd timer)
- `fix_audio.sh` — HDMI audio routing fix (wpctl)
- `health_check_agent.sh` — Hourly Claude CLI health check (cron)
- `static/js/tv.js` — Row-aware navigation, `quickNav()`, SSE handler, idle screensaver, all alert types, offline banner
- `static/js/player.js` — Video player controls (play/pause, skip, volume)
- `static/js/hls.min.js` — HLS.js for Pluto TV live streams
- `static/css/tv.css` — TV UI (hotel TV layout, poster grids, player, channels)
- `static/css/admin.css` — Admin panel (mobile-friendly)
- `templates/tv/` — 20 TV-facing templates
- `templates/admin/` — 15 admin templates (extend `base.html`)
- `test_ui.py` — Playwright test suite (93 tests)
