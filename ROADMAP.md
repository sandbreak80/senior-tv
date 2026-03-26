# Senior TV — Product Roadmap

## Current State

Single-deployment system built for Don & Colleen in Sun City, CA. Runs on one GMKtec NucBox K11 connected to a Samsung 65" TV. All configuration is done via admin panel + SSH. Hardcoded defaults assume one household.

---

## Tier 1: Make It Installable (10 homes)

Goal: Any technically-savvy family member can set this up for their loved one without editing code.

- [ ] **First-boot setup wizard** — Web UI on first launch that asks: resident names, location (for weather), content preferences (dementia stage, interests), sundowning time, shower days, connected services (Jellyfin, Immich, etc.). Writes to settings DB.
- [ ] **Remove all hardcoded values** — Every IP, name, coordinate, and care plan preference must come from the settings DB or setup wizard. No more "Colleen & Don" in code.
- [ ] **Docker container** — `docker-compose up` with a single config file. Bundle Chrome, Flask, CEC tools, PipeWire. Eliminate manual Ubuntu setup.
- [ ] **Hardware compatibility matrix** — Test on 3-4 common mini PCs (Intel NUC, Beelink, GMKtec). Document BIOS auto-power-on for each. Test CEC on Intel vs AMD GPUs.
- [ ] **Care profile system** — Replace hardcoded content rules with configurable profiles: dementia stage (early/mid/advanced), interests (checkboxes), sundowning cutoff time, shower schedule, blocking duration.
- [ ] **Installation documentation** — Step-by-step guide: hardware purchase, Ubuntu install, Docker setup, first-boot wizard, TV connection, remote pairing.

---

## Tier 2: Make It Manageable (100 homes)

Goal: A family member or care facility can manage multiple deployed boxes remotely.

- [ ] **Cloud admin dashboard** — Web app to manage all deployed boxes. View health status, send messages, update settings, push content. Replace LAN-only admin panel for remote use.
- [ ] **Remote provisioning** — Ship a box with a QR code. Family scans it, enters their info on a web form, box auto-configures via API. No SSH required.
- [ ] **OTA updates** — Triggered from cloud dashboard: pull latest code, run migrations, restart services. Currently requires SSH + manual commands.
- [ ] **Telemetry & analytics** — Usage data: what content is watched, how long, pill acknowledgment times, reminder effectiveness. Helps caregivers understand behavior patterns and improve care.
- [ ] **Multi-resident support** — Some homes have a couple, some have one person. Per-resident care profiles, greeting rotation, personalized content.
- [ ] **Family notification system** — Push alerts to family members' phones: pill not acknowledged in 30 minutes, TV offline for 1 hour, person detected at door, system health degraded. Email, SMS, or app notifications.
- [ ] **Caregiver activity log** — Record when pills were acknowledged, what content was watched, how long the TV was active. Exportable for care team review.

---

## Tier 3: Make It a Product (1,000+ homes)

Goal: Non-technical families can buy a box, plug it in, and it works.

### Accounts & Platform
- [ ] **Account system** — Family creates account, links their box, invites members. Roles: primary caregiver, family member, care facility admin.
- [ ] **Managed cloud infrastructure** — Centralized health checks, log aggregation, alerting, remote management, OTA updates.

### Content
- [ ] **Managed media library** — Most families won't run Jellyfin. Options: (a) curated free content (YouTube, Pluto TV, Internet Archive), (b) streaming service partnerships, (c) licensed content library.
- [ ] **Content curation engine** — Auto-recommend channels and shows based on care profile. "Dementia-friendly" content ratings.
- [ ] **YouTube ToS compliance** — Clarify kiosk embedding legality or build native integrations via YouTube Data API.

### Family Connection
- [ ] **Photo sharing mobile app** — Take a photo on your phone → it appears on the TV slideshow within minutes. Like a private family Instagram for the TV. (Replaces self-hosted Immich dependency.)
- [ ] **Video calling** — One-tap video call from phone to the TV. Senior presses OK to answer. WebRTC.
- [ ] **Family activity feed** — "Brad sent a photo", "Cheryl sent a message" — visible in the admin dashboard and TV inbox.

### Hardware
- [ ] **Pre-configured hardware kit** — Partner with mini PC manufacturer. Ship ready to plug in: HDMI cable, power adapter, simple remote, quick start card.
- [ ] **Reliable HDMI-CEC** — Select hardware where CEC works natively, or include a USB CEC adapter, or ship a custom Bluetooth 6-button remote.
- [ ] **Plug-and-play setup** — "Plug the HDMI into your TV, plug in power, scan the QR code with your phone, done."

### Accessibility
- [ ] **Localization** — Spanish, other languages. All UI text from translation files.
- [ ] **Text-to-speech** — For residents who can't read but can hear. Read pill reminders, messages, weather aloud.
- [ ] **Font size preferences** — Configurable from admin. Default 36px may need to be larger for some users.
- [ ] **Color blindness modes** — High contrast alternatives.

### Compliance
- [ ] **HIPAA assessment** — If storing health data (pill schedules, care plans, acknowledgment logs). May need encrypted storage, audit trails, BAAs.
- [ ] **Privacy policy** — For camera snapshots, photos, usage telemetry.
- [ ] **Terms of service** — For the platform and content.

---

## Tier 4: Business Model

- **Hardware kit** — $200-300 one-time (mini PC + remote + cables + quick start guide)
- **SaaS subscription** — $20-40/month covers cloud dashboard, OTA updates, health monitoring, family app, support
- **Care facility tier** — Per-room pricing for assisted living, bulk management, staff dashboard
- **The real value** — Not the TV itself, but family connection (messages, photos, video calls) and caregiver peace of mind (health monitoring, pill tracking, remote management, activity logs)

---

## What Exists Today

| Component | Status |
|-----------|--------|
| TV UI with time-of-day content | Done |
| Pill & shower reminders | Done |
| Jellyfin integration (movies/shows) | Done |
| Pluto TV (421 live channels) | Done |
| YouTube (36 curated channels, sandboxed) | Done |
| Immich photo integration (143K photos) | Done |
| Family messages (text, photo, video) | Done |
| Doorbell alerts (Frigate) | Done |
| Weather & calendar | Done |
| Admin panel (LAN) | Done |
| Row-aware arrow key navigation | Done |
| Process supervision & auto-restart | Done |
| Local watchdog (3 min self-repair) | Done |
| Claude AI health agent (hourly) | Done |
| SSH + Tailscale remote access | Done |
| HDMI audio persistence | Done |
| CEC TV control with HA fallback | Done |
| YouTube lockdown (sandbox + overlays) | Done |
| Fast navigation (quickNav) | Done |
| Health API endpoint | Done |
