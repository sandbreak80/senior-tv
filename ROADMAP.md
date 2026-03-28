# Senior TV — Product Roadmap

## Current State (March 2026)

Single-deployment system built for Don & Colleen in Sun City, CA. Runs on one GMKtec NucBox K11 (AMD Ryzen 5, 28GB RAM, 937GB NVMe) connected to a Samsung 65" TV via HDMI. Remote access via SSH + Tailscale + Cloudflare tunnel (`seniortv.riffyx.com`). Self-healing with local watchdog (3 min) and Claude AI health agent (hourly).

---

## Recently Fixed (March 2026)

- [x] **Pluto TV show alert streams never played** — `get_channel_by_id()` applied `_is_active()` EPG filter, removing channels between scheduler detection and user click. Fixed: direct lookups bypass active filter.
- [x] **Pluto TV session race conditions** — `SESSION_CACHE` was unprotected global dict accessed from multiple Flask threads. Fixed: `_session_lock`, `invalidate_session()`, proactive 4-hour token refresh, UUID4 client IDs.
- [x] **Pluto TV proxy created unnecessary sessions** — `pluto_stream_master()` cleared token on every request. Fixed: reuses existing session, only refreshes on 401/403/5xx.
- [x] **HLS proxy swallowed errors** — `pluto_proxy()` returned 502 for all failures. Fixed: passes through upstream status codes, invalidates session on 403.
- [x] **HLS.js recovery incomplete** — Missing `swapAudioCodec()` step. Fixed: escalating recovery (startLoad → swapAudioCodec → destroy/recreate, 5 retries).
- [x] **Scheduler reminder dedup broken for shows/birthdays** — Stored `{"triggered": True}` but GC expected `"triggered_at"`. GC deleted entries immediately, causing duplicate alerts every 10 min / every hour. Fixed: stores `triggered_at` ISO timestamp.
- [x] **Silent exception handlers in daemon threads** — 13 bare `except: pass` in scheduler, smart_home, cec_control. Fixed: all now print to stderr.
- [x] **CDN domain whitelist too restrictive** — Pluto TV proxy only allowed 4 domain patterns. Fixed: added `akamaized.net`, `cloudfront.net`, `dai.google.com`.
- [x] **Show alerts too frequent** — 6 shows on 24/7 Pluto channels fired alerts every hour (6 popups/hour). Fixed: disabled all except Jeopardy (auto-tune, no popup).
- [x] **Text-to-speech for reminders** — All popup alerts (pills, doorbell, birthday, show, family message) now spoken aloud after chime via browser `speechSynthesis` API. Rate 0.8 (slow for elderly). Global on/off toggle in admin settings. Speech cancels on dismiss. Zero external dependencies.

---

## Open Items

### Care Improvements
- [ ] Add to health check: flag if no activity for 4+ hours during daytime
- [ ] Expose stretch break configuration in admin settings (currently managed as pills)
- [x] ~~Text-to-speech for pill reminders and messages~~ — Done (all alert types spoken aloud)

### Automation
- [ ] **Bedtime auto-off** — After 10 PM, if USB camera shows room empty for 30+ minutes, power off TV via CEC. Re-enable TV power automation with correct 65" Samsung entity. Morning auto-on when presence detected.

### Accessibility
- [ ] **Auto-subtitle all media** — Deploy Bazarr (Docker) to bulk-download English subtitles from OpenSubtitles/Subscene for all 9,000+ items. Use Whisper (local AI) as fallback for files with no online subs. Enable captions by default in the player for hearing-impaired viewers.

### Stability
- [ ] Remaining hardcoded service IPs in admin services page (`server.py:1276-1286`) — 8 IPs, acceptable for single deployment but brittle if network changes
- [ ] 1 flaky Playwright test (`Any key returns home` on Photo Frame) — headless browser timing issue
- [ ] Pre-existing lint warning: unused `random` import in `server.py:1903`

---

## Tier 1: Make It Installable (10 homes)

Goal: Any technically-savvy family member can set this up for their loved one without editing code.

- [ ] **First-boot setup wizard** — Web UI on first launch. Asks: resident names, city/zip (weather), interests (checkboxes), sundowning time, shower days, connected services (Jellyfin, Immich URLs). Writes to settings DB.
- [ ] **Remove all hardcoded values** — Every IP, name, coordinate, and care plan preference comes from settings DB or setup wizard.
- [ ] **Docker container** — `docker-compose up` with single config file. Bundle Chrome, Flask, CEC tools, PipeWire. Eliminate manual Ubuntu setup.
- [ ] **Hardware compatibility matrix** — Test on 3-4 mini PCs (Intel NUC, Beelink, GMKtec). Document BIOS auto-power-on for each. Test CEC on Intel vs AMD GPUs.
- [ ] **Care profile system** — Configurable profiles: dementia stage (early/mid/advanced), interests (checkboxes), sundowning cutoff time, shower schedule, blocking duration.
- [ ] **Installation documentation** — Step-by-step: hardware purchase, Ubuntu install, Docker setup, first-boot wizard, TV connection, remote pairing.

---

## Tier 2: Make It Manageable (100 homes)

Goal: A family member or care facility can manage multiple deployed boxes remotely.

- [ ] **Admin UI overhaul** — Mobile-friendly design for non-technical family members. Care profile editor, activity charts, friendly pill management. This is a big standalone project.
- [ ] **Cloud admin dashboard** — Web app to manage all deployed boxes. View health status, send messages, update settings remotely. Current admin is LAN-only (Cloudflare tunnel is interim solution).
- [ ] **Remote provisioning** — Ship a box with QR code. Family scans, enters info, box auto-configures. No SSH required.
- [ ] **OTA updates** — Pull latest code, run migrations, restart. Triggered from cloud dashboard.
- [ ] **Telemetry & analytics** — Usage data: what's watched, how long, pill acknowledgment times, reminder effectiveness.
- [ ] **Multi-resident support** — Per-resident care profiles, greeting rotation, personalized content.
- [ ] **Family notification system** — Push alerts to phones: pill not acknowledged in 30 min, TV offline 1 hour, person at door.
- [ ] **Caregiver activity log** — Exportable reports for care team review. (Foundation exists: `activity_logs` and `remote_logs` tables.)

---

## Tier 3: Make It a Product (1,000+ homes)

Goal: Non-technical families can buy a box, plug it in, and it works.

### Accounts & Platform
- [ ] **Account system** — Family creates account, links box, invites members. Roles: primary caregiver, family member, care facility admin.
- [ ] **Managed cloud infrastructure** — Centralized health checks, log aggregation, alerting, remote management, OTA updates.

### Content
- [ ] **Managed media library** — Most families won't run Jellyfin. Curated free content (YouTube, Pluto TV, Internet Archive) as default. Streaming partnerships optional.
- [ ] **Spotify integration** — OAuth flow, Spotify Web Playback SDK, background music playlists (classical, oldies, ambient). Requires Spotify Premium. Would replace YouTube for music.
- [ ] **Content curation engine** — Auto-recommend based on care profile. "Dementia-friendly" ratings.
- [ ] **YouTube ToS compliance** — Clarify kiosk embedding legality or use YouTube Data API.

### Family Connection
- [ ] **Photo sharing mobile app** — Take photo → appears on TV slideshow. Private family Instagram for the TV. (Replaces self-hosted Immich.)
- [ ] **Video calling** — One-tap call from phone to TV. Senior presses OK to answer. WebRTC.
- [ ] **Family activity feed** — "Brad sent a photo" visible in admin and TV inbox.

### Hardware
- [ ] **Pre-configured hardware kit** — Partner with mini PC manufacturer. Ship ready: HDMI cable, power adapter, simple remote, quick start card.
- [ ] **Reliable HDMI-CEC** — Select hardware with native CEC, or include USB CEC adapter, or ship custom Bluetooth 6-button remote.
- [ ] **Plug-and-play setup** — "Plug HDMI into TV, plug in power, scan QR code, done."

### Single-System Hosting
- [ ] **Run Immich locally** — Docker on NucBox. Currently on separate Proxmox server (192.168.50.165).
- [ ] **Run Jellyfin locally** — Docker on NucBox. Currently on separate server (192.168.50.20). Needs external storage for 5K+ movies.
- [ ] **Replace Frigate** — Current Frigate (192.168.50.114) is heavy. Replace with lightweight agent that connects directly to PTZ IP cameras.
- [ ] **Storage expansion** — NVMe has 900GB free (sufficient for Immich photos). Movies need external USB SSD or NAS mount.

### Accessibility
- [ ] **Localization** — Spanish, other languages. Translation files.
- [ ] **Text-to-speech** — Read pill reminders, messages, weather aloud for residents who can't read.
- [ ] **Font size preferences** — Configurable from admin. Default 36px, may need larger.
- [ ] **Color blindness modes** — High contrast alternatives.

### Compliance
- [ ] **HIPAA assessment** — If storing health data. Encrypted storage, audit trails, BAAs.
- [ ] **Privacy policy** — Camera snapshots, photos, usage telemetry.
- [ ] **Terms of service** — Platform and content.

---

## Tier 4: Business Model

- **Hardware kit** — $200-300 one-time (mini PC + remote + cables + quick start guide)
- **SaaS subscription** — $20-40/month (cloud dashboard, OTA updates, health monitoring, family app, support)
- **Care facility tier** — Per-room pricing for assisted living, bulk management, staff dashboard
- **The real value** — Family connection (messages, photos, video calls) and caregiver peace of mind (health monitoring, pill tracking, remote management, activity logs)

---

## What Exists Today

### Core System
| Component | Status |
|-----------|--------|
| Full-screen Chrome kiosk on 65" Samsung TV (4K, Ubuntu 24.04) | Done |
| 6-button navigation (arrows + OK + Back via Samsung remote → CEC → xdotool) | Done |
| Row-aware 2D keyboard navigation across all pages | Done |
| All text min 36px, high-contrast dark theme | Done |
| Persistent title bar on all players (they forget what's watching) | Done |
| `quickNav()` kills media before navigating for instant response | Done |
| SSE event stream with exponential backoff reconnection (5s→60s) | Done |
| Offline detection banner when network drops | Done |
| 153/154 Playwright UI tests passing | Done |

### Entertainment
| Component | Status |
|-----------|--------|
| Jellyfin (5,112 movies + 108 shows, genre filters, continue watching) | Done |
| Jellyfin daily random 20 movies, shuffle play for TV shows | Done |
| Jellyfin image + stream proxy (works remotely via Cloudflare) | Done |
| Pluto TV (421 live channels, category tabs, channel logos, EPG) | Done |
| Pluto TV HLS proxy with m3u8 rewriting (CORS bypass) | Done |
| Pluto TV thread-safe sessions (4-hour proactive refresh, UUID4 clients) | Done |
| YouTube (36 curated channels in 12 categories) | Done |
| YouTube lockdown (sandbox, click-blocking overlay, no popups, loops) | Done |
| Immich photo frame (143K photos, 10s auto-advance, EXIF display) | Done |
| Photo frame also serves as idle screensaver (10 min timeout) | Done |
| Music player (/tv/music — genre tabs, 40K tracks, auto-play next) | Done |
| Auto-play next video when movie ends | Done |
| Poster system (consistent 2:3 ratio, full names, no truncation) | Done |
| HLS.js with escalating error recovery (5 retries, swapAudioCodec) | Done |

### Care & Safety
| Component | Status |
|-----------|--------|
| Pill reminders — Morning 11 AM + Evening 8:30 PM, full-screen popup | Done |
| Shower reminders — Tue/Thu, blocks TV 15 min, cannot dismiss | Done |
| Stretch breaks — Daily 9 AM/1 PM/5 PM/9 PM, blocks TV 15 min | Done |
| Safety auto-unlock at 2x duration if not dismissed | Done |
| Missed pill logging after 2 hours unacknowledged | Done |
| Sundowning protection — no news after 3 PM, wind-down video instead | Done |
| Time-of-day content (morning: game shows, afternoon: westerns, evening: wind down) | Done |
| Classical music auto-play at 10 AM (doctor's orders, YouTube) | Done |
| Classical music admin settings (enable/disable, time picker) | Done |
| Text-to-speech — all alerts spoken aloud (speechSynthesis API, rate 0.8) | Done |
| TTS admin toggle (global on/off in settings page) | Done |

### Communication
| Component | Status |
|-----------|--------|
| Family messages (text, photo, video) sent from admin panel | Done |
| Full-screen message popup on TV with chime, inbox with unread count | Done |
| Doorbell alerts — Frigate person detection, camera snapshot on TV | Done |
| Birthday greetings — 9 AM popup with name and age, auto-dismiss 60s | Done |
| Jeopardy auto-tune (navigates directly, no popup) | Done |
| Favorite show alerts on Pluto TV (hourly dedup, 30s auto-dismiss) | Done |

### Presence & Automation
| Component | Status |
|-----------|--------|
| Room presence tracking — Frigate polls living_room + tv_room cameras every 10s | Done |
| Screensaver — idle 10 min → Immich slideshow, room empty → 2 min timer | Done |
| Auto-play gating — classical music and auto-tune only if room occupied | Done |
| Presence SSE events — TV reacts to room empty/occupied in real time | Done |

### Home Screen
| Component | Status |
|-----------|--------|
| Time, date, personalized greeting (Don & Colleen) | Done |
| Current weather + 5-day forecast (Open-Meteo, Sun City CA) | Done |
| Next pill status, next calendar event, unread message count | Done |
| Daily quote + "on this day" history | Done |
| Family photo widget (random Immich photo) | Done |
| Live news stream (before 3 PM) or wind-down video (after 3 PM) | Done |
| Content rows (movies, TV shows) — time-of-day aware | Done |
| Content rotation (quotes 5 min, photos 30s, daily movies) | Done |

### Admin Panel (LAN + remote via Cloudflare)
| Component | Status |
|-----------|--------|
| Dashboard with system status, CPU/RAM, active pills, upcoming events | Done |
| Pill management (CRUD, schedule times/days, custom reminder media) | Done |
| Calendar events (CRUD, recurring daily/weekly/monthly/yearly) | Done |
| Family message sending (text/photo/video) | Done |
| Birthday management with age calculation | Done |
| Favorite show management (search terms, enable/disable) | Done |
| YouTube channel curation (categories, sort order) | Done |
| Photo uploads for slideshow | Done |
| Jellyfin/Plex connection setup | Done |
| Immich, Home Assistant, Frigate configuration | Done |
| Settings page (all service URLs, API keys, admin password) | Done |
| Activity log viewer (7 days of page visits, playback, remote presses) | Done |
| Camera feeds page (Frigate snapshots) | Done |
| Remote TV view (see what's on screen) | Done |
| Services status page with connection tests | Done |

### Security & Access
| Component | Status |
|-----------|--------|
| LAN users bypass auth (RFC 1918 ranges) | Done |
| Remote access via Cloudflare tunnel requires password | Done |
| Tailscale VPN for SSH remote management | Done |
| API routes exempt from auth (streaming proxies) | Done |
| YouTube fully sandboxed (no popups, no keyboard, no fullscreen) | Done |
| Remote auth (Flask login form, session cookies) | Done |

### Reliability & Self-Healing
| Component | Status |
|-----------|--------|
| Process supervision (start.sh) — Flask + Chrome + CEC every 10s | Done |
| systemd — Restart=always, auto-start on boot | Done |
| Watchdog (3 min) — Flask, Chrome, audio, disk, memory, network, Tailscale, TV power | Done |
| Claude AI health agent (hourly) — diagnosis, screenshots, autonomous fixes | Done |
| HDMI audio persistence (WirePlumber + fix_audio.sh) | Done |
| BIOS auto-power-on after AC loss | Done |
| Health API (/api/health — 10+ subsystem checks) | Done |
| Daily maintenance — 3:15 AM prune logs (activity 30d, remote 7d) | Done |
| Bounded SSE queue (maxsize=50) prevents memory growth | Done |
| Thread safety — locks on presence, reminders, Pluto sessions, cache | Done |
| DB connection leak prevention (get_db_safe context manager, WAL mode) | Done |
| Cache cleanup (expired entries pruned every 30 min) | Done |
| OS auto-updates with 3 AM reboot | Done |

### Infrastructure
| Component | Status |
|-----------|--------|
| Nginx reverse proxy (all services on port 80) | Done |
| Docker: Jellyfin, Immich, HA, Frigate all running locally | Done |
| 10 cameras (9 IP + 1 USB webcam with person detection) | Done |
| CEC TV control with Home Assistant fallback | Done |
| TV input control via Home Assistant | Done (see known limitations) |
| Cloudflare tunnel (seniortv.riffyx.com) | Done |
| SSH + Tailscale remote access | Done |
| Check on Loved Ones (saved camera snapshots every 15 min) | Done |

### Database
| Component | Status |
|-----------|--------|
| SQLite with WAL mode, get_db_safe() context manager | Done |
| 11 tables: settings, pills, pill_logs, messages, birthdays, shows, youtube, favorites, calendar, activity, remote | Done |
| Automatic log pruning (activity 30d, remote 7d) | Done |

---

## Known Limitations

### Hardware (cannot fix in software)
- **Samsung TV HDMI input switching** — The HA Samsung integration for older models (MU6100) exposes a single "HDMI" source that maps to Samsung's smart hub, not individual HDMI ports. CEC-enabled devices like Roku can steal the input. **Workaround:** Unplug Roku — Senior TV replaces it entirely. Input switching is disabled in watchdog.
- **AMD GPU CEC** — NucBox K11 AMD Phoenix GPU has kernel CEC module loaded but doesn't expose `/dev/cec0`. No native HDMI-CEC without USB adapter. TV control uses Home Assistant fallback.
- **USB webcam resolution** — Logitech C920 outputs YUYV at max 640x480 to Frigate (via mediamtx H.264 transcode). Higher resolutions available but increase CPU load.

### Infrastructure
- **Immich remote access** — Immich's SPA doesn't support subpath proxying (`/immich/`). Works on LAN via direct port (:2283). For remote access, needs its own subdomain (e.g., `photos.riffyx.com`).
- **Home Assistant remote access** — Similar subpath limitation. Works on LAN (:8123), needs own subdomain for remote.

### Resolved (March 2026)
- ~~Pluto TV show alert streams never available~~ — Fixed: `get_channel_by_id()` bypasses EPG filter
- ~~Pluto TV session thread-safety~~ — Fixed: `_session_lock`, proactive refresh, UUID4 clients
- ~~Duplicate show/birthday alerts~~ — Fixed: `triggered_at` timestamp in `active_reminders`
- ~~Silent daemon thread failures~~ — Fixed: 13 handlers now print to stderr
- ~~HLS proxy error swallowing~~ — Fixed: status code passthrough, session invalidation on 403
