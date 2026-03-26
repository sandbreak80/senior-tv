# Senior TV

A full-screen kiosk entertainment, communication, and care system for seniors with dementia and Alzheimer's.

Built for a 65" Samsung TV connected to a mini PC running Ubuntu. Designed for two 95-year-olds — every feature prioritizes simplicity, large text, and minimal cognitive load. Navigation uses only 6 buttons (arrow keys + OK + Back) via a standard TV remote over HDMI-CEC.

## What It Does

**Entertainment** — 5,100+ movies and 100+ TV shows via Jellyfin, 421 live TV channels via Pluto TV, 36 curated YouTube channels, and 143K family photos from Immich.

**Care** — Pill reminders that pop up full-screen, shower reminders that block the TV for 15 minutes, time-of-day content scheduling (no news after 3 PM to prevent sundowning agitation), and a wind-down ambient video slot in the evening.

**Communication** — Family members send messages, photos, and videos to the TV from any phone on the LAN. Doorbell alerts show camera snapshots when someone's at the front door. Birthday greetings play at 9 AM.

**Self-Healing** — Local watchdog auto-repairs crashed services every 3 minutes. Hourly Claude AI agent diagnoses issues, takes desktop screenshots, and fixes problems autonomously. SSH + Tailscale for remote management.

## Screenshots

| Home Screen | Live TV | Movies |
|-------------|---------|--------|
| Time-aware greeting, weather, wind-down video, family photo, content rows | 421 channels with logos, category filters | Jellyfin library with genre filters, continue watching |

| YouTube | Photo Frame | Admin Panel |
|---------|-------------|-------------|
| 36 curated channels, sandbox-locked player | Immich-powered slideshow, idle screensaver | Mobile-friendly management for pills, messages, photos |

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Samsung 65" TV                                  │
│  ┌───────────────────────────────────────────┐  │
│  │  Chrome Kiosk (full-screen)                │  │
│  │  ← HDMI-CEC remote (6 buttons) →          │  │
│  └───────────────────┬───────────────────────┘  │
│                      │ HDMI                      │
├──────────────────────┼──────────────────────────┤
│  GMKtec NucBox K11   │ Ubuntu 24.04             │
│  ┌───────────────────┴───────────────────────┐  │
│  │  Flask (server.py:5000)                    │  │
│  │  ├── TV UI (templates/tv/)                 │  │
│  │  ├── Admin Panel (templates/admin/)        │  │
│  │  ├── SSE (/events) → pill/doorbell alerts  │  │
│  │  └── Health API (/api/health)              │  │
│  ├────────────────────────────────────────────┤  │
│  │  start.sh — process supervisor             │  │
│  │  ├── Flask server                          │  │
│  │  ├── Chrome kiosk                          │  │
│  │  └── CEC bridge (remote → keyboard)        │  │
│  ├────────────────────────────────────────────┤  │
│  │  Watchdog (3 min) + Claude Agent (1 hr)    │  │
│  └────────────────────────────────────────────┘  │
│         │            │           │                │
│    Jellyfin     Pluto TV     Immich              │
│   (movies)    (live TV)    (photos)              │
│  192.168.50.20  public    192.168.50.165         │
│         │                                        │
│    Frigate ──── Home Assistant                   │
│  (doorbell)     (TV control)                     │
│  .50.114         .50.76                          │
└──────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and setup
git clone https://github.com/sandbreak80/senior-tv.git
cd senior-tv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure (edit settings via admin panel after first launch)
python3 server.py    # http://localhost:5000

# Production (systemd)
sudo cp senior-tv.service /etc/systemd/system/
sudo systemctl enable senior-tv
sudo systemctl start senior-tv

# Full kiosk
google-chrome --kiosk http://localhost:5000
```

## Admin Panel

Accessible from any device on the LAN at `http://<device-ip>:5000/admin`

| Page | Purpose |
|------|---------|
| Dashboard | System overview, active pills, upcoming events |
| Messages | Send text, photos, videos directly to the TV |
| Pills | Pill reminders + shower time blocks |
| Calendar | Events, pre-loaded with US holidays through 2027 |
| Birthdays | Full-screen birthday greetings with age |
| Shows | Monitor favorite shows on Pluto TV |
| YouTube | Curate channels by category |
| Photos | Upload family photos for slideshow |
| Jellyfin | Media server connection |
| Settings | Weather, Frigate, Home Assistant, Immich, audio, everything |

## Deployment Resilience

This system is designed to run indefinitely without physical intervention:

- **Process supervision** — `start.sh` monitors Flask, Chrome, and CEC bridge every 10 seconds; restarts any that die
- **systemd** — `Restart=always` with rate limiting
- **Local watchdog** — Checks Flask, Chrome, HDMI audio, disk, memory, network, Tailscale every 3 minutes; auto-repairs
- **Claude AI health agent** — Hourly cron runs Claude CLI to diagnose issues, read logs, take desktop screenshots, and attempt fixes
- **HDMI audio persistence** — WirePlumber config + `fix_audio.sh` ensures audio stays on HDMI
- **Remote access** — SSH + Tailscale for remote management from anywhere
- **Health endpoint** — `GET /api/health` returns JSON status of all 10+ subsystems

## Key Design Decisions

- **No mouse, no touchscreen** — Samsung TV remote only (6 buttons via HDMI-CEC)
- **Minimum 36px text** — readable from couch distance on 65" 4K TV
- **No news after 3 PM** — sundowning care; wind-down ambient video plays instead
- **Shower reminders block the TV** — 15-minute countdown, can't dismiss early (safety auto-unlock at 2x)
- **YouTube fully sandboxed** — no `allow-popups`, click-blocking overlays, disabled keyboard/annotations/fullscreen, video loops to prevent end screens
- **`window.quickNav()`** — global fast navigation kills iframes/videos/images before navigating; back button feels instant
- **Row-aware navigation** — arrow keys understand horizontal poster rows vs vertical lists; Up/Down jumps between rows by screen position

## Connected Services

| Service | Purpose | Required |
|---------|---------|----------|
| [Jellyfin](https://jellyfin.org/) | Movie & TV show library | Optional |
| [Pluto TV](https://pluto.tv/) | Free live TV (421 channels) | Optional |
| [Immich](https://immich.app/) | Family photo library | Optional |
| [Frigate](https://frigate.video/) | Doorbell camera alerts | Optional |
| [Home Assistant](https://www.home-assistant.io/) | TV power/input control | Optional |
| [Open-Meteo](https://open-meteo.com/) | Weather data | Built-in |

All services are optional — the system degrades gracefully. With no services configured, you still get weather, calendar, pill reminders, messages, and the admin panel.

## Tech Stack

- **Backend:** Python 3.12, Flask, SQLite, APScheduler
- **Frontend:** Vanilla JS, CSS (no frameworks), Jinja2 templates
- **Streaming:** HLS.js for live TV, HTML5 video for Jellyfin
- **Hardware:** Any x86 mini PC + HDMI TV. Tested on GMKtec NucBox K11 (AMD Ryzen 5, 28GB RAM)
- **OS:** Ubuntu 24.04 with GNOME Wayland + Xwayland

## License

Private project. Built with love for Don & Colleen.
