# Changelog

All notable changes to Senior TV are documented here.

## [0.1.0-beta] - 2026-04-04

### First Public Beta

The first public release of Senior TV. A fully functional kiosk entertainment, care, and communication system for seniors, deployed and battle-tested on a live system.

### Entertainment
- 421 live TV channels via Pluto TV with category filters and HLS streaming
- Jellyfin integration for personal movie, TV show, and music libraries
- 36 curated YouTube channels across 12 categories with fully sandboxed player
- Free movie discovery from Archive.org public domain content
- Classical music library curated for Alzheimer's music therapy
- Auto-play system with time-of-day content scheduling
- Daily movie rotation (20 random movies, refreshed daily)
- Wind-down ambient video after 3 PM (fireplace, nature, Bob Ross)

### Care & Health
- Pill reminders with full-screen overlay + audio chime + TTS voice announcement
- Shower reminders that block the TV for 15 minutes (safety auto-unlock)
- Stretch break reminders (configurable schedule)
- Time-of-day content rules (no news after 3 PM for sundowning protection)
- Presence detection via local camera with MobileNet SSD person detection
- Activity logging with configurable levels (minimal/normal/verbose)
- "Now Playing" indicator on activity page

### Communication
- Family messages (text, photos, videos) sent from any device on the network
- Doorbell alerts with Frigate camera snapshots and doorbell chime
- Birthday greetings with auto-play at 9 AM and Happy Birthday melody
- Favorite show alerts ("Jeopardy is on now!" with one-press tune-in)
- All alerts spoken aloud via browser TTS (rate 0.8 for elderly comprehension)

### Admin Panel
- Mobile-friendly dashboard with system health, pill status, TV presence
- 15 admin pages: messages, pills, calendar, birthdays, shows, YouTube, photos, cameras, activity, settings, and more
- Family/Admin mode toggle (simplified view for non-technical family members)
- Remote access via Cloudflare tunnel with password authentication

### Smart Home
- HDMI-CEC bridge translating Samsung remote to keyboard navigation
- Home Assistant integration for TV power/input control
- Frigate integration for person detection and doorbell alerts
- Weather display via Open-Meteo (no API key required)

### Infrastructure
- Fully automated `install.sh` — bare Ubuntu to working kiosk in one command
- Docker stack: Jellyfin + Immich + Bazarr + Nginx reverse proxy
- Process supervision with 10-second restart loop
- Watchdog monitoring 8 subsystems every 3 minutes
- AI health agent (hourly Claude CLI diagnosis with auto-repair)
- HDMI audio auto-routing via PipeWire
- systemd service with crash recovery
- Health API endpoint (`GET /api/health`)
- SQLite database with WAL mode
- SSE for real-time TV alerts with exponential backoff reconnect

### Known Issues
- Hardcoded names and location throughout templates
- No first-boot setup wizard
- YouTube iframe duration tracking is estimate-based
- CEC support varies by hardware
- English only
