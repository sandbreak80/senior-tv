# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Senior TV is a full-screen kiosk-style entertainment, communication, and care system for Don & Colleen (both 95, born 1931). Don has mid-stage dementia; Colleen has advanced Alzheimer's. TV is their primary daily activity. The system runs on a GMKtec NucBox K11 mini PC (Ubuntu 24.04, 4K) connected to a Samsung 65" TV via HDMI in Sun City, CA.

## Architecture

- **Flask app** (`server.py`) — serves TV UI + admin panel on port 5000
- **Chrome kiosk mode** — full-screen browser, uBlock Origin ad blocker via Chrome policy
- **HDMI-CEC bridge** (`cec_bridge.py`) — tries kernel CEC (`cec-ctl`), falls back to libCEC (`cec-client`), exits gracefully if no CEC hardware
- **CEC TV control** (`cec_control.py`) — power on/off, input switching; tier 1: kernel CEC, tier 2: Home Assistant Samsung TV API
- **SQLite** (`senior_tv.db`) — pills, calendar, birthdays, messages, favorites, settings; WAL mode for concurrent reads
- **APScheduler** (`scheduler.py`) — pill reminders (1 min), birthday checks (1 hr), show alerts (10 min)
- **SSE** (`/events`) — pushes pill reminders, doorbell alerts, show notifications, family messages to TV
- **Jellyfin API** (`jellyfin_api.py`) — media library at `localhost:8096` (local Docker)
- **Pluto TV** (`pluto_tv.py`) — 421 free live TV channels via HLS, logos via `path` key (not `url`)
- **Immich API** (`immich_api.py`) — family photos from Immich at `localhost:2283` (local Docker, ML disabled); photos proxied through `/api/immich-photo/<id>` to hide API key
- **Smart Home** (`smart_home.py`) — Frigate person detection on front_door camera, HA integration, room presence tracking
- **Display** — forced to 1920x1080 (no 4K content); `monitors.xml` covers both HDMI ports, `start.sh` enforces via Mutter DBus API
- **HDMI audio** (`fix_audio.sh`) — finds any HDMI sink via PipeWire `object.path`, works with either HDMI port; called by `start.sh` and `watchdog.sh`
- **Process supervision** (`start.sh`) — monitors Flask + Chrome + CEC bridge every 10s, restarts any that die
- **systemd** (`senior-tv.service`) — auto-start on boot, `Restart=always`
- **Watchdog** (`watchdog.sh`) — runs every 3 min via systemd timer; checks/repairs Flask, Chrome, audio, network, Tailscale, disk, memory
- **Health agent** (`health_check_agent.sh`) — hourly cron runs Claude CLI to diagnose and fix issues, takes desktop screenshot

## Code Style

- **Python:** Standard library + Flask. No ORMs. SQLite via `get_db_safe()`. Lint with `ruff check *.py --select E,F,W`.
- **JavaScript:** Vanilla JS only. No frameworks, no build step, no npm. ES5-compatible where possible.
- **CSS:** Vanilla CSS only. No preprocessors. TV styles in `tv.css`, admin in `admin.css`.
- **Templates:** Jinja2. TV templates are standalone HTML. Admin templates extend `admin/base.html`.

## Key Design Constraints

These are hard constraints, not suggestions. They're driven by the users' medical conditions.

- **Don** can follow structured content: game shows, sports, sitcoms, westerns
- **Colleen** needs low/no-plot: music, ambient, familiar visuals (music memory preserved longest)
- **6-button navigation only** — Arrow keys, Enter, Escape. No mouse, no touch, no scroll. Everything reachable with these 6 inputs (Samsung remote → CEC → xdotool)
- **36px minimum text** — Readable from 8 feet away on a 65" TV. When in doubt, make it bigger
- **Dark theme, high contrast** — Light text on dark backgrounds. No thin fonts. No low-contrast decorative elements
- **No cognitive load** — If a feature requires a decision, it should make that decision automatically
- **Fail silently** — If a service is down, show what's available. Never expose technical errors to the TV screen
- **Instant response** — `window.quickNav()` kills iframes/videos/images before navigating. Back button must feel instant
- Persistent title bar on all players — they forget what's watching
- No news/high-stimulation content after 3 PM (sundowning); wind-down ambient video plays instead
- Shower reminders (Tue/Thu) block TV for 15 minutes — can't dismiss (safety timeout auto-unlocks after 2x duration)
- Time-of-day content: morning (game shows, news), afternoon (westerns, comedy), evening (wind down)
- YouTube iframes are fully locked: `sandbox` without `allow-popups`, transparent click-blocking overlays, `disablekb=1`, `iv_load_policy=3`, `fs=0`, `playlist+loop` to prevent end screens

## Important Patterns

### Configuration Precedence

Settings table in SQLite shadows `config.py` defaults — `get_setting_or_default()` in `server.py` checks DB first, falls back to `config.py`. When adding new settings, add a default in `config.py` and access via this function.

**Environment variables:**
- `SENIOR_TV_SECRET` — Flask session key
- `SENIOR_TV_DEBUG` — Flask debug mode (0/1)
- `SENIOR_TV_PORT` — HTTP port (default 5000)

### Database Access

Always use the `get_db_safe()` context manager from `models.py`. It ensures connections are closed, enables WAL mode, and sets `row_factory = sqlite3.Row` for dict-like access. Convert results with `[dict(r) for r in rows]` when returning from functions.

```python
with get_db_safe() as db:
    db.execute(query, (param,))
    db.commit()
```

### SSE Event System

Events flow: scheduler/smart_home → `reminder_queue` (bounded, maxsize=50) → SSE `/events` endpoint → `tv.js` handler.

**Event types handled in `tv.js`:** `pill_reminder`, `doorbell_alert`, `birthday_alert`, `show_alert`, `family_message`, `auto_play`, `presence_change`

**To add a new event type:**
1. Create event dict with `"type": "your_type"` and push via `reminder_queue.put_nowait(event_dict)`
2. Handle in `initSSE()` onmessage callback in `tv.js`
3. Implement display function with overlay

SSE reconnects with exponential backoff (5s → 60s max). Alert sounds use Web Audio API synthetic tones (no audio files). All alerts are spoken aloud via `speechSynthesis` API after the chime (configurable via `tts_enabled` setting, default on, rate 0.8 for elderly comprehension).

### Reminder Lifecycle

1. Scheduler triggers → `reminder_queue` + `active_reminders` dict
2. SSE delivers to TV → overlay displayed
3. User dismisses → `POST /api/acknowledge` with reminder_id
4. Unacked reminders garbage-collected as "missed" after 2 hours

### Thread Safety

- `smart_home.py`: presence state protected by `_presence_lock` (threading.Lock)
- `scheduler.py`: `active_reminders` dict protected by `_lock`
- SmartHomeMonitor: daemon thread polls every 5s, deduplicates via `_seen_events` set (auto-trimmed at 1000)

## Navigation Architecture

`static/js/tv.js` implements row-aware navigation for the Samsung remote:
- All interactive elements have class `navigable`
- `getRowOf(el)` groups items by parent container (`home-poster-row`, `poster-row`, `home-quick-menu`, `menu-list`, `category-tabs`, etc.)
- **Left/Right** moves within a row; **Up/Down** jumps between rows, landing on the closest item by horizontal position (via `getBoundingClientRect`)
- `window.quickNav(url)` is a global function that kills all iframes/videos/images, fades to black, then navigates — used by every page for instant back-button response

## Connected Services

| Service | Location | URL | Auth |
|---------|----------|-----|------|
| Jellyfin | Network server | `http://192.168.50.20:8096` | API key in settings DB |
| Immich | Network server | `http://192.168.50.165:2283` | API key in settings DB |
| Frigate | Network | `http://192.168.50.114:5000` | Session cookie login |
| Home Assistant | Network | `http://192.168.50.76:8123` | Long-lived token |
| Pluto TV | External | Public API | No auth |
| Open-Meteo | External | Public API | No auth (Sun City, CA: 33.7083, -117.1972) |

**Important:** All services run on dedicated network servers. Nothing runs in Docker on this box — no nginx, no Jellyfin, no Immich. Flask runs directly on the host. Cloudflare tunnel points directly at `localhost:5000`.

## Deployment & Remote Access

- **Fully automated install**: `git clone <repo> && cd senior-tv && sudo ./install.sh` — configures everything including Jellyfin, Immich, and Cloudflare tunnel
- **Standardized credentials**: Jellyfin user `seniortv`/`seniortv`, Immich admin `bstoner@gmail.com`/`seniortv` (configurable via `.env`)
- **Cloudflare Tunnel** for remote admin access (set `CLOUDFLARE_TUNNEL_TOKEN` in `.env`)
- **SSH** via Tailscale: `ssh seniortv@<hostname>` (key-only auth)
- **Tailscale** mesh VPN with SSH enabled (`tailscale up --ssh`)
- **Health endpoint**: `GET /api/health` returns JSON status of all subsystems
- **BIOS**: Set "Restore on AC Power Loss = Power On" for power failure recovery

## Jellyfin Setup & Content Population

### How install.sh configures Jellyfin (fully automated)
1. Starts Jellyfin Docker container, waits for it to respond on port 8096
2. Runs first-time setup wizard via REST API: sets locale (en-US), creates admin user (`seniortv`/`seniortv`), enables remote access, completes wizard
3. Authenticates via `/Users/AuthenticateByName` to get a session token
4. Creates three libraries via `/Library/VirtualFolders`: Movies (`/media/movies`), Shows (`/media/shows`), Music (`/media/music`) — all with `EnableRealtimeMonitor: true` so new files are auto-detected
5. Creates a permanent API key via `/Auth/Keys?app=SeniorTV` and stores it in `senior_tv.db` settings table
6. Enables Intel VA-API hardware transcoding if `/dev/dri/renderD128` exists (Intel N95 supports H.264/HEVC/VP9/AV1 decode)

### Content population
Media lives in `~/media/{movies,shows,music}/` (mounted read-only into the Jellyfin container). Two loader scripts:

- **`scripts/load_jellyfin_content.py`** (primary) — Downloads public domain content from Archive.org. 50 GB budget, rate limiting (auto-waits 60s on 429), resumes partial downloads, triggers Jellyfin library scan on completion. Categories: music (classical for Colleen), movies (westerns/comedy/drama), shows (game shows/sitcoms), ambient (fireplace/aquarium for wind-down).
- **`scripts/load_jellyfin.sh`** (legacy) — Bash-based alternative, same Archive.org sources.

```bash
# Preview what will download
python3 scripts/load_jellyfin_content.py --list

# Download all categories (50 GB budget)
python3 scripts/load_jellyfin_content.py

# Single category
python3 scripts/load_jellyfin_content.py --category music

# Just trigger a library scan
python3 scripts/load_jellyfin_content.py --scan
```

### Key Jellyfin API patterns
- Auth header: `X-Emby-Token: <api_key>` (not Bearer)
- Library scan: `POST /Library/Refresh` (returns 204)
- Create library: `POST /Library/VirtualFolders?name=X&collectionType=Y&refreshLibrary=false` with `PathInfos` in body
- First-time wizard endpoints: `/Startup/Configuration`, `/Startup/User`, `/Startup/RemoteAccess`, `/Startup/Complete`
- Hardware transcoding config: `POST /System/Configuration/encoding` with VA-API device path

## Immich Setup

### How install.sh configures Immich (fully automated)
1. Starts Immich stack (server + Redis + PostgreSQL with pgvecto-rs), waits for port 2283
2. Creates admin account via `/api/auth/admin-sign-up` (only works on first run, silently fails if admin exists)
3. Authenticates via `/api/auth/login` to get a Bearer token
4. Creates permanent API key via `/api/api-keys` with `permissions: ["all"]`
5. Disables ML via `/api/system-config` PUT (saves ~400 MB RAM — face recognition is nice-to-have, not essential)
6. Tunes job concurrency for 8 GB RAM: thumbnail/metadata at 2, video/search/background/migration at 1
7. Enables VA-API video transcoding in ffmpeg config
8. Stores API key in `senior_tv.db` settings table

### Immich architecture notes
- Uses `tensorchord/pgvecto-rs:pg14-v0.2.0` for PostgreSQL (vector search extension)
- ML container intentionally omitted from docker-compose — saves RAM, face recognition not needed for photo slideshow use case
- Photos proxied through Flask (`/api/immich-photo/<id>`) to hide API key from browser
- Upload path: `./data/immich/upload` → mapped to `/usr/src/app/upload` in container

### Immich API patterns
- Auth header: `x-api-key: <key>` (lowercase) or `Authorization: Bearer <token>` for session auth
- Random photos: `GET /api/search/random` (used for slideshow)
- System config: `GET/PUT /api/system-config` (disable ML, tune jobs, set ffmpeg config)
- Admin signup: `POST /api/auth/admin-sign-up` (first-run only, returns 400 if admin exists)

## Commands

```bash
# Fresh install (fully automated)
git clone <repo> && cd senior-tv
cp .env.example .env                 # Edit with your tokens
sudo ./install.sh                    # Installs everything, configures services

# Development (Docker/Jellyfin/Immich not required — system degrades gracefully)
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

# Lint (CI uses --select E,F,W)
source venv/bin/activate && ruff check *.py --select E,F,W

# Syntax check (what CI runs)
python3 -m py_compile server.py models.py config.py scheduler.py smart_home.py jellyfin_api.py pluto_tv.py immich_api.py

# Template validation
python3 -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); [env.get_template(f.replace('templates/','')) for f in __import__('glob').glob('templates/**/*.html', recursive=True)]"

# UI tests (requires Flask running at localhost:5000)
source venv/bin/activate && python3 test_ui.py

# Single test sections cannot be run individually — test_ui.py runs all 93 tests sequentially
# To skip sections, comment out specific test function calls in run_tests()

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

Accessible from any device on LAN at `http://<host-ip>:5000/admin`

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

## Nginx Reverse Proxy & Immich Subpath Fix

Nginx (`nginx.conf`) runs in Docker on port 80, fronting all services for the Cloudflare tunnel. The Cloudflare tunnel points to `localhost:80` and Nginx routes:

- `/` → Flask (port 5000) — Senior TV app
- `/jellyfin/` → Jellyfin (port 8096) — works natively, Jellyfin supports base URL config
- `/immich/` → Immich (port 2283) — **requires extensive workarounds** (see below)

### Why Immich on a subpath is hard

Immich does not support running under a subpath. It's a SvelteKit SPA that assumes it's served from `/`. Unlike Jellyfin (which has a `BaseUrl` config), Immich has no `IMMICH_BASE_PATH` environment variable. Running it under `/immich/` requires Nginx `sub_filter` rewriting of HTML, CSS, and JavaScript responses.

### The three problems and their fixes

**Problem 1: SvelteKit client-side routing**

Immich's HTML contains a SvelteKit bootstrap block:
```javascript
__sveltekit_5ubkur = { base: "", env: null };
```
With `base: ""`, the SPA router navigates to `/auth/login`, `/photos`, etc. — all without the `/immich/` prefix, which hit Flask and 404.

**Fix:** `sub_filter 'base: "",' 'base: "/immich",';` rewrites the SvelteKit base path so all client-side navigation goes to `/immich/auth/login`, `/immich/photos`, etc.

**Problem 2: API SDK base URL uses backtick template literals**

Immich's OpenAPI SDK has: `` baseUrl:`/api` `` (backtick string, not quotes). The sub_filter rules for `"/api/` and `'/api/` didn't match because JavaScript template literals use backticks.

Also: Immich serves JavaScript as `Content-Type: text/javascript`, not `application/javascript`. Nginx's `sub_filter_types` must include both.

**Fix:** Two changes:
- `sub_filter '`/api`' '`/immich/api`';` — catches backtick template literals
- `sub_filter_types text/html text/css application/javascript text/javascript;` — processes both JS MIME types

**Problem 3: Dynamically-loaded CSS/JS uses relative paths**

Immich's app.js loads CSS like `"_app/immutable/assets/0.DKfpaXlb.css"` (relative path, no leading `/`). When the browser is at `/immich/auth/login`, the relative path resolves to `/immich/auth/_app/...` — wrong. It should be `/immich/_app/...` or `/_app/...`.

**Fix:** A separate Nginx location block proxies `/_app/*` directly to Immich:
```nginx
location /_app/ {
    proxy_pass http://host.docker.internal:2283/_app/;
}
```
This catches any `_app/` request that resolved relative to a deep SPA route.

**Bonus fix: SPA route redirects**

Even with the SvelteKit base set, some navigation still hits bare paths (`/auth/login` instead of `/immich/auth/login`). A regex location block catches all known Immich routes and redirects:
```nginx
location ~ ^/(auth|photos|albums|people|explore|sharing|user-settings|search|partners|trash|map|memory)(.*) {
    return 302 /immich/$1$2$is_args$args;
}
```
Note: `/admin` is intentionally excluded — that's the Senior TV admin panel.

### Full list of sub_filter rules (order matters)

| Rule | What it catches |
|------|----------------|
| `base: "",` → `base: "/immich",` | SvelteKit bootstrap config |
| `href="/` → `href="/immich/` | HTML link tags (favicons, preloads) |
| `src="/` → `src="/immich/` | HTML script/image tags |
| `action="/` → `action="/immich/` | HTML form actions |
| `url(/` → `url(/immich/` | CSS url() references |
| `"/api/` → `"/immich/api/` | JS API calls with double quotes |
| `'/api/` → `'/immich/api/` | JS API calls with single quotes |
| `` `/api` `` → `` `/immich/api` `` | JS API calls with backtick template literals |
| `fetch("/` → `fetch("/immich/` | JS fetch() calls |
| `import("/_app/` → `import("/immich/_app/` | SvelteKit dynamic imports |

### Key requirement: disable response compression

`proxy_set_header Accept-Encoding "";` is critical — without it, Immich returns gzip/brotli compressed responses that `sub_filter` cannot parse. This header tells upstream to send uncompressed responses.

### Contrast with Jellyfin

Jellyfin supports this natively: set `BaseUrl` to `/jellyfin` in Jellyfin's Network config (or via the `JELLYFIN_PublishedServerUrl` env var). No sub_filter needed. The Nginx `location /jellyfin` block is a simple pass-through proxy.

### If Immich updates break this

Immich updates may change SvelteKit chunk hashes, variable names, or the bootstrap format. If `/immich/` breaks after an Immich update:
1. Check `curl -sf http://localhost:2283/ | grep sveltekit` — look for the `base:` format
2. Check JS MIME type: `curl -sI http://localhost:80/immich/_app/immutable/chunks/<any>.js | grep content-type`
3. Check SDK baseUrl: `curl -sf http://localhost:2283/_app/immutable/chunks/<sdk-chunk>.js | tr ',' '\n' | grep baseUrl`
4. Verify sub_filter is processing: compare `curl localhost:2283/` vs `curl localhost:80/immich/` — all paths should have `/immich/` prefix in the proxied version

## File Layout

- `server.py` — Flask app, all routes, health endpoint
- `config.py` — defaults and connected service URLs
- `models.py` — SQLite schema, CRUD helpers with `get_db_safe()` context manager
- `scheduler.py` — APScheduler: pills (1 min), birthdays (1 hr), show alerts (10 min), reminder GC (5 min)
- `smart_home.py` — Frigate polling thread, HA API helpers, doorbell alerts, presence tracking
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
- `install.sh` — Fully automated installer (system packages, Chrome, Docker, Jellyfin, Immich, Cloudflare, systemd, cron)
- `docker-compose.yml` — Not used in this deployment (Jellyfin/Immich on network servers)
- `nginx.conf` — Not used in this deployment (Cloudflare tunnel points directly at Flask)
- `seed_content.sh` — Downloads sample photos for screensaver on first install
- `scripts/load_jellyfin_content.py` — Archive.org content downloader (movies, shows, music, ambient)
- `scripts/load_jellyfin.sh` — Legacy bash-based content loader
- `scripts/load_music.py` — Classical music downloader (curated for Alzheimer's care)
- `scripts/load_photos.py` — Photo import helper
- `scripts/load_images.py` — Image download utility
- `static/js/tv.js` — Row-aware navigation, `quickNav()`, SSE handler, idle screensaver, all alert types, offline banner
- `static/js/player.js` — Video player controls (play/pause, skip, volume)
- `static/js/hls.min.js` — HLS.js for Pluto TV live streams
- `static/css/tv.css` — TV UI (hotel TV layout, poster grids, player, channels)
- `static/css/admin.css` — Admin panel (mobile-friendly)
- `templates/tv/` — 20 TV-facing templates
- `templates/admin/` — 15 admin templates (extend `base.html`)
- `test_ui.py` — Playwright test suite (93 tests, requires `pip install playwright`)
- `.env.example` — Template for environment variables (credentials, tokens, service config)
- `data/` — Persistent Docker volumes (Jellyfin config/cache, Immich uploads/postgres, Bazarr config)
