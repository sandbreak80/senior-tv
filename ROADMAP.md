# Senior TV — Product Roadmap

## Current State (March 2026)

Single-deployment system built for Don & Colleen in Sun City, CA. Runs on one GMKtec NucBox K11 (AMD Ryzen 5, 28GB RAM, 937GB NVMe) connected to a Samsung 65" TV via HDMI. Remote access via SSH + Tailscale + Cloudflare tunnel (`seniortv.riffyx.com`). Self-healing with local watchdog (3 min) and Claude AI health agent (hourly).

---

## Immediate Fixes (Pre-Deployment)

- [x] **BIOS: Power On after AC loss** — Set "Restore on AC Power Loss = Power On" in AMI BIOS. Requires one-time physical access to the NucBox.
- [x] **Cloudflare tunnel DNS** — Add CNAME record for `seniortv.riffyx.com` pointing to tunnel ID in Cloudflare dashboard.
- [x] **LAN access debugging** — Diagnose why `http://192.168.50.159:5000` isn't accessible from other LAN computers. Server binds to `0.0.0.0:5000`, firewall is off. Likely router client isolation or VLAN issue.
- [x] **Delete fasting reminder** — Pill ID 4 ("No Food or Drink") was for one-time doctor visit. Remove via `/admin/pills`.

---

## Phase A: Care Feature Completion

### Classical Music (Doctor's Orders: 1 Hour Daily)
- [x] Add `get_music_items(genre, limit)` to `jellyfin_api.py` — search Audio type items
- [x] Create `/tv/music` route with dedicated music player page (shows album art, track name, progress)
- [x] Scheduler already triggers at 10 AM — connect to Jellyfin music library; fall back to HALIDONMUSIC YouTube channel if no classical found
- [x] Add `classical_music_enabled` and `classical_music_time` to admin settings form
- [x] Move hardcoded HALIDONMUSIC channel ID from `scheduler.py` to a setting
- **Files:** `jellyfin_api.py`, `server.py`, `scheduler.py`, `templates/admin/settings.html`, new `templates/tv/music.html`

### Presence Inference
- [x] Display "Last activity: X minutes ago" on admin dashboard with green/yellow/red indicator
- [x] `get_last_activity_time()` and `get_remote_log_count()` already exist in `models.py` and are passed to dashboard template
- [ ] Add to health check: flag if no activity for 4+ hours during daytime
- **Files:** `templates/admin/dashboard.html`, `server.py` (health endpoint)

### Admin Settings Gaps
- [x] Add to admin settings form: `classical_music_enabled`, `classical_music_time`, `admin_password`
- [ ] Expose stretch break configuration (currently created as pills via admin)
- **Files:** `templates/admin/settings.html`

---

## Phase B: UI Polish & Stability

### Notification Audit
- [x] Audit every overlay (pill, shower, stretch, birthday, doorbell, show alert, family message) for 90-year-old clarity
- [x] Only use "Press OK" and "Press BACK" — no "Press Down", no technical terms
- [x] Show alerts: "Press OK to Watch" / "Press BACK to close" — DONE
- **Files:** `static/js/tv.js`

### Test Suite
- [x] Run `python3 test_ui.py` and fix broken tests after refactors (`jf_recommendations` → `jf_movies`/`jf_shows`, etc.)
- [x] Add tests for new features: activity logging, remote auth, show alert actions
- **Files:** `test_ui.py`

### Hardcoded Values Cleanup
- [x] `scheduler.py`: Move HALIDONMUSIC channel ID to setting
- [x] `cec_bridge.py`: Move `localhost:5000` to constant
- [ ] `server.py`: LAN IP ranges in auth check are fine (standard RFC 1918 ranges)
- [ ] `config.py`: Defaults are acceptable — overridden via admin panel
- **Files:** `scheduler.py`, `cec_bridge.py`

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

| Component | Status |
|-----------|--------|
| TV UI with time-of-day content | Done |
| Pill, shower, & stretch break reminders | Done |
| Jellyfin integration (5,112 movies + 108 shows, split rows) | Done |
| Pluto TV (421 live channels with logos) | Done |
| YouTube (50 verified channels in 11 categories, sandboxed) | Done |
| Immich photo integration (143K photos, slideshow + home widget) | Done |
| Family messages (text, photo, video) | Done |
| Doorbell alerts (Frigate) | Done |
| Weather, calendar, birthdays | Done |
| Admin panel (LAN + remote via Cloudflare with password) | Done |
| Row-aware arrow key navigation | Done |
| Process supervision & auto-restart (start.sh) | Done |
| Local watchdog (3 min self-repair via systemd timer) | Done |
| Claude AI health agent (hourly cron with desktop screenshots) | Done |
| SSH + Tailscale remote access | Done |
| Cloudflare tunnel (seniortv.riffyx.com) | Done (DNS pending) |
| HDMI audio persistence (WirePlumber + fix_audio.sh) | Done |
| CEC TV control with Home Assistant fallback | Done |
| YouTube lockdown (sandbox, overlays, no popups, loops) | Done |
| Fast navigation (quickNav kills iframes/videos/images) | Done |
| Health API (/api/health — 11 subsystem checks) | Done |
| Activity logging (playback, page visits, durations) | Done |
| Remote button logging (CEC presses) | Done |
| Classical music auto-play at 10 AM | Done (YouTube fallback, Jellyfin integration pending) |
| Content rotation (quotes 5min, photos 30s, movies daily) | Done |
| Poster system (consistent 2:3 ratio, full names, no truncation) | Done |
| Show alerts with Watch Now / BACK to close | Done |
| Stream error auto-recovery (retry + auto-return to guide) | Done |
| OS auto-updates with 3 AM reboot | Done |
| Video player retry on error | Done |
| DB connection leak prevention (get_db_safe everywhere) | Done |
| Cache cleanup (expired entries pruned every 30 min) | Done |
| SSE exponential backoff reconnection | Done |
| Music player (/tv/music — genre tabs, 40K tracks, auto-play next) | Done |
| Classical music admin settings (enable/disable, time picker) | Done |
| Presence tracking via USB webcam (mediamtx + Frigate) | Done |
| Smart content (screensaver when empty, wake on presence) | Done |
| Check on Loved Ones (saved camera snapshots every 15 min) | Done |
| Auto-play next video when movie ends | Done |
| Jeopardy auto-tune when on Pluto TV | Done |
| Pluto TV EPG (Now Playing titles, filter dead channels) | Done |
| Jellyfin image + stream proxy (works remotely via Cloudflare) | Done |
| Nginx reverse proxy (all services on port 80) | Done |
| Remote auth (Flask login form, LAN bypasses) | Done |
| Admin: Services page with container stats | Done |
| Admin: Cameras page with live feeds + saved snapshots | Done |
| Admin: TV View with scaled iframe + screenshot history | Done |
| Docker: Jellyfin, Immich, HA, Frigate all running locally | Done |
| 10 cameras (9 IP + 1 USB webcam with person detection) | Done |
| BIOS auto-power-on after AC loss | Done |
| TV input control via Home Assistant | Done (see known limitations) |
| 152/154 Playwright tests passing | Done |

---

## Known Limitations

- **Samsung TV HDMI input switching** — The HA Samsung integration for older models (MU6100) exposes a single "HDMI" source that maps to Samsung's smart hub, not individual HDMI ports. The watchdog sends `select_source: HDMI` every 3 minutes which briefly lands on HDMI2 (NucBox) but CEC-enabled devices like Roku can steal the input back. **Fix for deployment:** Unplug Roku or disable CEC on it (Roku Settings → System → Control other devices → uncheck "1-touch play"). Senior TV replaces Roku entirely.
- **Immich remote access** — Immich's SPA doesn't support subpath proxying (`/immich/`). Works on LAN via direct port (:2283). For remote access, needs its own subdomain (e.g., `photos.riffyx.com`).
- **Home Assistant remote access** — Similar subpath limitation. Works on LAN (:8123), needs own subdomain for remote.
- **USB webcam resolution** — Logitech C920 outputs YUYV at max 640x480 to Frigate (via mediamtx H.264 transcode). Higher resolutions available but increase CPU load.
- **AMD GPU CEC** — NucBox K11 AMD Phoenix GPU has kernel CEC module loaded but doesn't expose `/dev/cec0`. No native HDMI-CEC without USB adapter. TV control uses Home Assistant fallback.
