# Changelog

All notable changes to Senior TV are documented here.

## [Unreleased] - 2026-04-13

### Added
- **Frigate-based presence detection** (`services/health.py` → `_check_presence()`): the health endpoint now verifies that `presence_logs` contains recent samples with `source=frigate` and flags degraded if the monitor has silently fallen back to HA sensors or USB webcam. Dementia-safety-critical: we must know if the system is blind to "who is watching TV".
- **Non-English audio filter** (`jellyfin_api.py`): new `_has_english_audio()` helper rejects any Jellyfin item that doesn't have an explicit `eng`/`en` audio track. Applied to every list method (`get_library_items`, `get_latest`, `get_resume`, `get_episodes`, `get_daily_picks`, `get_random_episode`, `search`) via `_filter_english()`. Strict mode — `und`-tagged items are also hidden since we can't verify they're English, and a dementia-friendly kiosk should never surface foreign-audio content.
- **Play-time English audio gate** (`server.py` → `/tv/plex/play/<id>`): even if a direct link / bookmark / auto-chain URL bypasses library filtering, the play route now calls `jf.is_english_audio_available(item_id)` first and silently redirects to `/tv/plex` on failure, logging a `skipped_non_english` activity entry. Silent skip per the "no cognitive load" design rule — the viewer never sees an error.

### Changed
- **Volume monitor** (`volume_monitor.py`): rewritten to pull `audio_rms` and `audio_dBFS` from Frigate's `/api/stats` endpoint instead of recording from a USB webcam mic via `arecord`. Configured via `frigate_volume_cameras` setting (default `dining_room,den` — deliberately NOT `living_room`, which sits next to the Sonos soundbar and reads the speaker output directly, not the room-level sound). Averages RMS linearly across cameras then converts to dBFS with the same `32768` reference as the old mic path, so existing `volume_logs` data and the `/admin/volume` dashboard baselines remain directly comparable. Polls at 1 Hz — the highest rate Frigate's stats endpoint usefully updates (verified empirically: 10 sub-second polls return identical cached values). Sub-second precision would require ffmpeg-from-RTSP, not shipped.

### Fixed
- **`jellyfin_api.get_english_audio_index()` and `.get_subtitle_url()`** were using the bare `/Items/{id}` endpoint which returns HTTP 400 on current Jellyfin. Both silently failed for an unknown period — this is why "River of No Return" (and likely others) have been playing non-English audio despite the "prefer English track" logic existing in the codebase. Switched both to the user-scoped `/Users/{user_id}/Items/{id}` path. `get_english_audio_index()` now actually works.

### Removed
- **CEC health check** (`services/health.py` → `_check_cec()`): the check was reporting `ok: true` regardless of state because the project doesn't actually use an HDMI-CEC adapter (the "USB device" detected earlier was a Flirc IR receiver, not a CEC dongle; HA fallback handles TV power/input). Removing the check eliminates a misleading "always-green" status.

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
