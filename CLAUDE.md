# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Senior TV is a full-screen kiosk-style entertainment, communication, and care system for Don & Colleen (both 95, born 1931). Don has mid-stage dementia; Colleen has advanced Alzheimer's. TV is their primary daily activity. The system runs on a GMKtec NucBox K11 mini PC (Ubuntu 24.04, 4K) connected to a Samsung 65" TV via HDMI in Sun City, CA.

## Architecture

- **Flask app** (`server.py`) — serves TV UI + admin panel on port 5000
- **Chrome kiosk mode** — full-screen browser, uBlock Origin ad blocker via Chrome policy
- **HDMI-CEC bridge** (`cec_bridge.py`) — Samsung remote → keyboard events via `xdotool`
- **SQLite** (`senior_tv.db`) — pills, calendar, birthdays, messages, favorites, settings
- **APScheduler** (`scheduler.py`) — pill reminders (1 min), birthday checks (1 hr), show alerts (10 min)
- **SSE** (`/events`) — pushes pill reminders, doorbell alerts, show notifications, family messages to TV
- **Jellyfin API** (`jellyfin_api.py`) — media library: 5,112 movies + 108 shows at `192.168.50.20:8096`
- **Pluto TV** (`pluto_tv.py`) — 421 free live TV channels via HLS
- **Smart Home** (`smart_home.py`) — Frigate person detection on front_door camera, HA integration
- **systemd** (`senior-tv.service`) — auto-start on boot

## Key Design Constraints

- **Don** can follow structured content: game shows, sports, sitcoms, westerns
- **Colleen** needs low/no-plot: music, ambient, familiar visuals (music memory preserved longest)
- Persistent title bar on all players — they forget what's watching
- No news/high-stimulation content after 3 PM (sundowning)
- Shower reminders (Tue/Thu) block TV for 15 minutes — can't dismiss
- All text minimum 36px, high contrast dark theme
- Navigation: arrow keys + Enter + Escape only (6 buttons)
- Time-of-day content: morning (game shows, news), afternoon (westerns, comedy), evening (wind down)

## Connected Services

| Service | URL | Auth |
|---------|-----|------|
| Jellyfin | `http://192.168.50.20:8096` | API key in settings |
| Frigate | `https://192.168.50.114:8971` | Session cookie login |
| Home Assistant | `http://192.168.50.76:8123` | Long-lived token |
| Pluto TV | Public API | No auth |
| Open-Meteo | Public API | No auth (Sun City, CA: 33.7083, -117.1972) |

## Commands

```bash
# Development
source venv/bin/activate
python3 server.py                    # http://localhost:5000

# Production (auto-start on boot)
sudo systemctl enable senior-tv      # Already done
sudo systemctl start senior-tv       # Or just reboot

# Manual kiosk launch
google-chrome --kiosk http://localhost:5000

# Lint
source venv/bin/activate && ruff check *.py

# UI tests
source venv/bin/activate && python3 test_ui.py
```

## TV UI Routes

- `/` — Hotel TV home screen (time-aware content, weather, greeting, recommendations)
- `/tv/live` — Pluto TV channels (421), category tabs, HLS player
- `/tv/plex` — Jellyfin library browser (continue watching, recently added, daily movies)
- `/tv/plex/daily` — 20 random movies that rotate daily
- `/tv/plex/library/<id>` — Browse with genre filters, sort options, pagination
- `/tv/plex/show/<id>` — Season/episode picker with shuffle play
- `/tv/plex/play/<id>` — Built-in HTML5 video player (persistent title, skip, volume)
- `/tv/plex/shuffle/<id>` — Random episode playback
- `/tv/youtube` — 36 curated channels in 12 categories
- `/tv/youtube/channel/<id>` — Channel video browser
- `/tv/youtube/watch/<id>` — YouTube player (iframe embed)
- `/tv/messages` — Family message inbox
- `/tv/messages/<id>` — Full-screen message view (text, photo, video)
- `/tv/news` — Live YouTube news + Pluto news + RSS headlines
- `/tv/weather` — 5-day forecast
- `/tv/calendar` — Daily/monthly/upcoming views (holidays pre-loaded)
- `/tv/photos` — Photo frame slideshow (also idle screensaver after 10 min)

## Admin Panel Routes (`/admin`)

Accessible from any device on LAN at `http://192.168.50.159:5000/admin`

- `/admin` — Dashboard
- `/admin/messages` — Send text, photos, videos to the TV
- `/admin/pills` — Manage reminders (morning 11am, evening 8:30pm, shower Tue/Thu)
- `/admin/birthdays` — Birthday greetings with age calculation
- `/admin/shows` — Favorite show alerts (9 shows monitored on Pluto TV)
- `/admin/calendar` — Events
- `/admin/youtube` — Curate YouTube channels
- `/admin/photos` — Upload family photos
- `/admin/plex-setup` — Jellyfin connection
- `/admin/settings` — Weather, Frigate, HA, photo NAS path, all config

## File Layout

- `server.py` — Flask app, all routes
- `config.py` — defaults and connected service URLs
- `models.py` — SQLite schema, CRUD helpers with `get_db_safe()` context manager
- `scheduler.py` — APScheduler: pills (1 min), birthdays (1 hr), show alerts (10 min)
- `smart_home.py` — Frigate polling thread, HA API helpers, doorbell alerts
- `jellyfin_api.py` — Jellyfin REST client (libraries, items, seasons, episodes, streams)
- `pluto_tv.py` — Pluto TV boot/channels API, HLS stream URLs
- `cec_bridge.py` — HDMI-CEC to keyboard event daemon
- `static/js/tv.js` — Navigation, SSE handler, idle screensaver, all alert types
- `static/js/player.js` — Video player controls (play/pause, skip, volume)
- `static/js/hls.min.js` — HLS.js for Pluto TV live streams
- `static/css/tv.css` — TV UI (hotel TV layout, poster grids, player, channels)
- `static/css/admin.css` — Admin panel (mobile-friendly)
- `templates/tv/` — 20 TV-facing templates
- `templates/admin/` — 15 admin templates (extend `base.html`)
- `test_ui.py` — Playwright test suite (93 tests)
