# Senior TV — Product Roadmap

## Vision

Senior TV is an **open-source, self-hosted media kiosk with care integration**. Anyone can buy a mini PC, clone the repo, run `install.sh`, and have a supervised entertainment and care system running on their TV.

At its core, the system solves a universal problem: someone who **can't or shouldn't** have unrestricted media access, someone else who **curates and monitors** that access, a **care schedule** layered on top, and a **communication bridge** between them. That pattern serves:

- **Seniors with dementia/Alzheimer's** — simplified UI, time-of-day content rules, medication reminders, sundowning protection, family photo slideshows
- **Seniors living independently** — full media access with simplified UI, medication tracking, doorbell alerts, family communication
- **Children (young)** — allowlisted content only, screen time budgets, educational scheduling, reward-gated access
- **Children (older)** — broader content with time limits, parental controls, activity logging
- **People with intellectual disabilities** — predictable routines, visual schedules, routine reinforcement, simplified navigation
- **People with motor disabilities** — 6-button navigation already mirrors switch scanning; extensible to voice control, eye tracking
- **People with autism** — predictable routines, sensory-appropriate content filtering, transition warnings, low-stimulation modes
- **Assisted living facilities** — per-resident profiles, staff dashboard, medication compliance logs, facility-wide announcements
- **Recovery/rehabilitation** — exercise reminders, appointment scheduling, restricted content during recovery, caregiver monitoring

### Distribution Model

Not a SaaS platform. An open-source appliance:
- Family buys a mini PC ($150–300) + TV
- Clones the GitHub repo
- Runs `install.sh` on Ubuntu
- Completes a first-boot setup wizard in the browser
- Configures care plan and content through the admin panel — no code editing

Every external service (Jellyfin, Immich, Home Assistant, Frigate) is optional. The system works with **zero** external services — Pluto TV and YouTube are free and require no setup. Families add integrations as they want them.

---

## Current State (April 2026)

Single-deployment system built for Don & Colleen in Sun City, CA. Runs on one GMKtec NucBox K11 (AMD Ryzen 5, 28GB RAM, 937GB NVMe) connected to a Samsung 65" TV via HDMI. Remote access via SSH + Tailscale + Cloudflare tunnel (`seniortv.riffyx.com`). Self-healing with local watchdog (3 min) and Claude AI health agent (hourly).

**Fully automated deployment** — `install.sh` handles everything from bare Ubuntu to working kiosk: system packages, Chrome with uBlock Origin, Docker services (Jellyfin + Immich + Bazarr + Nginx), first-time wizard automation for both Jellyfin and Immich (user creation, API keys, library setup, VA-API transcoding), Cloudflare tunnel registration, systemd services, cron jobs, database initialization, and environment-based settings. Zero manual post-install steps.

**Media stack operational:**
- Jellyfin: 17 classic movies (6.9 GB), 39+ classical music collections (1.4 GB), 1 show series (149 MB) — all public domain from Archive.org. Content loader script (`scripts/load_jellyfin_content.py`) manages a 50 GB budget with rate limiting.
- Immich: running with ML disabled (RAM savings), API key auto-generated, photos proxied through Flask.
- Bazarr: configured for automatic subtitle downloads.
- Nginx: reverse proxy on port 80 for Cloudflare tunnel (routes to Flask, Jellyfin, Immich).

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

## Priority Matrix

Every item scored on two axes, then combined for execution order:
- **D&C** = Impact on Don & Colleen's daily experience (1–5). They're 95, dementia/Alzheimer's, watching TV 8+ hours/day. A 5 means "they'd notice this immediately and it materially improves their day."
- **Project** = Impact on making this usable by other families (1–5). A 5 means "blocks anyone else from deploying this" or "the killer differentiating feature."
- **Combined** = D&C + Project. Tiebreakers favor D&C (they're real people, today).

### Executive Priority: Audio Quality & Subtitles First

Audio quality and subtitles are the highest combined-priority items because they score 5/5 for Don & Colleen (they're hearing-impaired and watching 8+ hours/day) AND 4/5 for the project (every elderly deployment needs this). These four items — voice boost EQ, cross-content volume normalization, commercial loudness taming, and auto-subtitles — should be the first work done. They improve the experience for the two real users we have today while simultaneously being table-stakes features that every future deployment will need. The project infrastructure items (`install.sh`, profiles, hardcoded values) are also P0 but are blocking prerequisites for other families, not quality-of-life improvements for Don & Colleen.

### P0 — Do Now (Combined 9–10)

These are high-impact for both Don & Colleen AND the project. Work on these first.

| Item | D&C | Project | Combined | Why |
|------|-----|---------|----------|-----|
| ~~**Voice boost / parametric EQ**~~ | 5 | 4 | 9 | DONE — 3-band EQ chain (highpass, presence boost, mud cut), configurable off/mild/strong in admin. |
| ~~**Broadcast-style volume normalization**~~ | 5 | 4 | 9 | DONE — Replaced feedback-loop design with broadcast chain: slow AGC → fixed makeup gain → fast limiter. No oscillation. Configurable target level in admin. |
| ~~**Commercial loudness taming**~~ | 5 | 4 | 9 | DONE — Fast limiter (1ms attack, -3dB ceiling) catches all peaks. AGC compressor evens levels. |
| **Auto-subtitles (Bazarr + Whisper)** | 5 | 4 | 9 | Both are hearing-impaired. Subtitles on all 5K+ movies/shows = transformative. Bazarr is the one *Arr tool that's P0. |
| **Audio/video sync fix** | 5 | 4 | 9 | Web Audio API processing chain adds latency that desynchronizes audio from video. Lips don't match words. Must compensate with `ctx.baseLatency` + `ctx.outputLatency` or use `delayNode` on video. |
| ~~**`install.sh`**~~ | 1 | 5 | 6* | DONE — Fully automated: Jellyfin wizard, Immich wizard, Cloudflare tunnel, VA-API transcoding, systemd, cron, all via REST APIs. Zero manual post-install steps. |
| **Remove hardcoded values** | 1 | 5 | 6* | "Don & Colleen" baked into templates, Sun City coordinates, specific IPs. Blocks all other deployments. Elevated to P0. |
| **Profiles table** | 1 | 5 | 6* | Foundation for everything — care templates, content engine, setup wizard all depend on this. Elevated to P0. |

*Elevated from raw score because they're project-blocking prerequisites.

### P1 — Do Next (Combined 7–8)

High impact on one axis, solid on the other. The "after P0" queue.

| Item | D&C | Project | Combined | Why |
|------|-----|---------|----------|-----|
| **Bedtime auto-off** | 4 | 3 | 7 | TV stays on all night if they fall asleep. Wastes power, disrupts sleep with light/sound. |
| **Night mode audio** | 4 | 3 | 7 | Tighter compression after 9 PM. Prevents loud moments from waking Colleen if Don's still watching. |
| **Silence detection (microphone)** | 4 | 3 | 7 | They sit in front of a dead stream for hours without noticing. Mic detects silence, auto-repairs. |
| **Source-specific gain presets** | 4 | 3 | 7 | Jellyfin movies are cinema-level quiet, Pluto is broadcast-loud. Pre-learned offsets per source. |
| **Immich "Who is this?" overlay** | 4 | 3 | 7 | Name overlay on family photos during slideshow. Reinforces recognition — therapeutic for dementia. |
| **Immich "On this day" photos** | 4 | 3 | 7 | "15 years ago — Christmas 2011." Morning nostalgia. Powerful memory stimulation. |
| **4-hour inactivity health check** | 4 | 2 | 6 | Flag if TV on but no interaction for 4+ hours during daytime. Could indicate a fall or medical event. |
| **Content rules in DB** | 2 | 5 | 7 | Move time-of-day rules, sundowning, content filtering from hardcoded logic to editable DB. Required for other deployments. |
| **First-boot setup wizard** | 1 | 5 | 6 | After install.sh, this is the second thing a new user sees. Must be smooth. |
| **Graceful degradation** | 1 | 5 | 6 | Most families won't have Jellyfin/Immich/HA. System must work with zero external services. |
| **Streaming service launcher** | 3 | 4 | 7 | Many families already pay for Netflix/HBO. Opening their web player in the kiosk = instant content library. |

### P2 — Important (Combined 5–6)

Meaningful improvements, but either less urgent for D&C or dependent on P0/P1 work.

| Item | D&C | Project | Combined | Why |
|------|-----|---------|----------|-----|
| **AI content engine** | 2 | 5 | 7* | The killer differentiator. But complex, and depends on profiles table + content rules in DB. *Demoted to P2 for dependency reasons. |
| **Internet Archive integration** | 2 | 5 | 7* | Free legal content library out of the box. Makes "zero external services" promise real. Old Time Radio is a goldmine for seniors. *Depends on AI content engine but is the #1 enabler for new deployments without Jellyfin. |
| **Immich album selection** | 3 | 3 | 6 | Choose which albums appear on TV. Currently 143K random photos includes irrelevant ones. |
| **Immich recent photos priority** | 3 | 3 | 6 | New family uploads should appear quickly. Encourages family engagement. |
| **Black screen detection** | 3 | 3 | 6 | Some streams deliver valid HLS with black frames. CDP screenshot + pixel analysis catches these. |
| **PipeWire session persistence** | 3 | 3 | 6 | Stop re-routing audio every 3 minutes. WirePlumber rules instead of `wpctl` commands. |
| **HDMI hotplug handling** | 3 | 3 | 6 | TV power cycle loses audio until next watchdog cycle (up to 3 min of silence). |
| **YouTube playlist integration** | 3 | 3 | 6 | Paste a Lawrence Welk playlist URL → browsable show in our UI. Easy content addition. |
| **Installation documentation** | 1 | 5 | 6 | Step-by-step guide. Critical for project but zero D&C impact. |
| **Care profile templates** | 1 | 4 | 5 | Pre-built starting points (dementia, independent, child, accessibility). Depends on profiles table. |
| **Generalized reminders** | 1 | 4 | 5 | Beyond pills/showers: exercise, meals, hydration, screen time. Depends on profiles. |
| **Stretch break admin config** | 2 | 3 | 5 | Currently managed as pills. Minor admin UX improvement. |
| **Keyboard nav mapping for streaming** | 3 | 4 | 7* | Netflix/HBO keyboard nav testing and JS injection. *Depends on streaming launcher (P1). |
| **A/V sync monitoring** | 3 | 3 | 6 | Detect audio playing but video frozen (or vice versa). Auto-recover. |

### P3 — Later (Combined ≤4, or high dependency depth)

Nice-to-have, complex, or dependent on multiple P1/P2 items being done first.

| Item | D&C | Project | Combined | Why |
|------|-----|---------|----------|-----|
| **Dynamic voice detection** | 3 | 2 | 5 | Complex DSP. Static parametric EQ (P0) gets 80% of the benefit. |
| **Sibilance control / hearing aid mode** | 2 | 2 | 4 | Niche. Only matters if they use hearing aids with the TV. |
| **Room loudness metering** | 3 | 2 | 5 | Cool but complex. Mic calibration, feedback loops, ambient noise filtering. |
| **Ambient noise awareness** | 2 | 2 | 4 | Auto-boost when visitors talking. Edge case. |
| **Stream health dashboard** | 2 | 3 | 5 | Admin polish. Current logging is sufficient for now. |
| **Predictive channel avoidance** | 2 | 2 | 4 | Track unreliable Pluto channels. Low frequency issue. |
| **Jellyfin transcode health** | 2 | 2 | 4 | Proactive bitrate switching. Rare failure mode. |
| **Immich video playback** | 2 | 2 | 4 | Home movies in slideshow. Small content library for most users. |
| **Memory montages** | 2 | 2 | 4 | Auto-generated slideshows with music. Requires Immich video + album selection first. |
| **YouTube Premium support** | 2 | 2 | 4 | Ad-free playback. Requires login which risks sandbox security. |
| **Deeper YouTube curation** | 2 | 3 | 5 | Unlimited channels. Current 36 is sufficient; AI engine (P2) handles this better. |
| **Cached YouTube metadata** | 2 | 3 | 5 | Pre-fetch titles/thumbnails. Reduces YouTube UI exposure. Depends on deeper curation. |
| **Multi-output audio (soundbar/BT)** | 1 | 3 | 4 | Soundbar/Bluetooth hearing aid support. Niche hardware configurations. |
| **Recovery logging & analytics** | 2 | 3 | 5 | Log all auto-recovery actions. Polish for admin. |
| **Immich exclude albums** | 2 | 2 | 4 | Blacklist albums. Depends on album selection (P2). |
| **Per-slideshow album assignment** | 2 | 2 | 4 | Different albums for different contexts. Depends on album selection. |
| **Birthday photo slideshow** | 3 | 2 | 5 | Auto-show photos of birthday person. Depends on Immich people integration. |
| **Era slideshows** | 2 | 2 | 4 | "Photos from the 1970s." Depends on AI content engine + Immich date queries. |
| ***Arr stack integration** | 2 | 3 | 5 | Wishlist → Radarr/Sonarr closes "recommended but not available" gap. Depends on AI content engine. Integration only — Senior TV never ships acquisition tools. |

### Tier 2–4 Priority (Project-focused)

Items in Tiers 2–4 are primarily project-focused (making Senior TV usable by 100–1000+ homes). They're listed in dependency order within each tier — see those sections for details. They become relevant after most P0–P2 Open Items and Tier 1 work is complete.

**Tier 2 highest-priority items:**
1. Admin UI overhaul (biggest barrier to non-technical users after installation)
2. Family notification system (pill not taken → alert to phone)
3. Touch mode (enables tablets as secondary displays)
4. Localization (Spanish = large caregiver market)

**Tier 3 highest-priority items:**
1. Docker container (simplest deployment path for technical users)
2. Raspberry Pi image (cheapest hardware = most accessible)
3. Photo sharing without Immich (phone browser upload → TV)
4. GitHub community setup (issue templates, contributing guide)

---

## Open Items

### Care Improvements
- [ ] Add to health check: flag if no activity for 4+ hours during daytime
- [ ] Expose stretch break configuration in admin settings (currently managed as pills)
- [x] ~~Text-to-speech for pill reminders and messages~~ — Done (all alert types spoken aloud)

### Automation
- [ ] **Bedtime auto-off** — After 10 PM, if USB camera shows room empty for 30+ minutes, power off TV via CEC. Re-enable TV power automation with correct 65" Samsung entity. Morning auto-on when presence detected.

### Accessibility
- [ ] **Auto-subtitle all media (Bazarr — P0)** — Deploy Bazarr via Docker (the one *Arr tool that's P0 priority). Bazarr watches the Jellyfin library, auto-downloads English subtitles from OpenSubtitles/Subscene for all 5,000+ movies and 108 shows. Use Whisper (local AI) as fallback for files with no online subs. Enable captions by default in the player for hearing-impaired viewers. This is the single most impactful accessibility improvement for Don & Colleen.

### Immich Integration

Current integration is minimal: `get_random_photos()` pulls random images from the entire library (143K photos). No album selection, no people filtering, no date ranges, no video support. For a family photo system, we need much more control over what appears on the TV.

#### Album & Library Selection
- [ ] **Album browser in admin** — Fetch album list from Immich API (`/api/albums`), let caregiver select which albums appear in the slideshow. Store selected album IDs in settings. "Show photos from 'Family Holidays' and 'Grandkids' only."
- [ ] **Per-slideshow album assignment** — Different slideshows for different contexts:
  - Home screen widget: curated "best of" album
  - Idle screensaver: broad family photos
  - Morning slideshow: recent family photos (keep them connected)
  - Wind-down slideshow: calming nature/landscape album
- [ ] **Exclude albums** — Some albums shouldn't appear on the TV (sensitive photos, duplicates, screenshots). Blacklist by album ID.

#### People & Face Recognition
- [ ] **People browser in admin** — Immich has face recognition built in. Fetch recognized people from `/api/people`, let caregiver select whose photos to show. "Only show photos with family members, not strangers from events."
- [ ] **"Who is this?" overlay** — Display recognized person's name on photos during slideshow. Powerful for dementia care — reinforces recognition of family members.
- [ ] **Birthday slideshow** — On a family member's birthday, auto-show photos of that person all day. Cross-reference Immich people with the birthdays table.

#### Date & Memory Features
- [ ] **"On this day" photos** — Immich API supports date-range queries. Pull photos from this date in previous years. Show during morning routine: "15 years ago today — Christmas 2011."
- [ ] **Era slideshows** — For the AI content engine: "Show photos from the 1970s" during nostalgia programming. Filter by EXIF date ranges.
- [ ] **Recent photos priority** — Weight recently uploaded photos higher in random selection. When a family member uploads new photos, they appear on the TV within the hour — immediate feedback loop that encourages sharing.

#### Video Support
- [ ] **Immich video playback** — Immich stores videos too (home movies, family clips). Currently we only pull `type: IMAGE`. Add video asset support:
  - Short clips (<2 min): play inline during slideshow
  - Longer videos: show as browsable items in a "Family Videos" section
  - Transcode via Immich if needed (Immich supports video transcoding)
- [ ] **Memory montages** — Auto-generate slideshows with music for special occasions: anniversary compilations, year-in-review, "photos of grandma" for Mother's Day.

### Streaming Services (Netflix, HBO, Amazon, Disney+)

These services work in Chrome (Widevine DRM is supported). The challenges are navigation (these UIs aren't designed for 6-button remotes) and account management. Worth doing because many families already pay for these services and their content libraries are huge.

#### Approach: Managed Browser Tabs
The system doesn't need to reverse-engineer streaming APIs. It opens their web players in a controlled browser context within the kiosk, with navigation assistance.

- [ ] **Streaming service launcher** — New TV UI section: "Streaming." Shows configured services (Netflix, HBO Max, Amazon Prime, Disney+, Hulu, Apple TV+, PBS, YouTube TV) as large icons. Selecting one opens the service's web player.
- [ ] **Account setup in admin** — Caregiver logs into each streaming service once via the admin panel. Chrome stores session cookies in the kiosk profile. No credentials stored in our DB — just browser session persistence.
- [ ] **Supervised navigation wrapper** — Overlay on top of streaming web players:
  - Persistent "Back to Senior TV" button (Escape key always returns home via `quickNav()`)
  - Optional: semi-transparent title bar showing current service name
  - Hide distracting UI elements via CSS injection (upsell banners, profile switchers, social features)
- [ ] **Keyboard navigation mapping** — Most streaming web players support basic keyboard nav:
  - Netflix: arrow keys + Enter work for browsing and playback controls
  - Amazon Prime: similar keyboard support
  - HBO Max/Disney+: varying levels of keyboard nav
  - Document which services work well with 6-button remote, which need enhancement
  - For services with poor keyboard nav: inject JavaScript to add arrow-key browsing
- [ ] **AI content engine integration** — The content engine recommends shows; the system checks which of the user's streaming services carry them:
  - "Perry Mason (2020) is on HBO Max" → deep link to the show page
  - "Gunsmoke is on Paramount+" → note it in recommendations even if not subscribed
  - Uses JustWatch-style availability data or manual mapping
- [ ] **Profile lock** — Streaming services have multiple profiles. Admin selects which profile to use (e.g., "Dad's profile" on Netflix). Inject CSS/JS to skip profile selection on launch.
- [ ] **Content filtering gap** — We lose content filtering control inside streaming apps. Their built-in parental controls must be configured separately. Document this clearly in setup: "Set up Netflix parental controls for [name]'s profile before enabling."

#### What NOT to Build
- No scraping or API hacking — just open the official web player in Chrome
- No credential storage — browser handles sessions like any normal user
- No DRM circumvention — Chrome Widevine handles this natively
- No content proxying — streams play directly from the service

### YouTube Strategy

YouTube login for personalized recommendations is **the wrong approach** for this use case. Here's why, and what to do instead:

#### Why NOT YouTube Login
- YouTube's algorithm optimizes for engagement (watch time), not appropriateness. It will recommend clickbait, political content, and rage-bait to a dementia patient.
- Logged-in YouTube breaks our sandbox security — the user could navigate to any video, see comments, follow links to external sites.
- YouTube recommendations get more extreme over time (filter bubble effect). A senior who watches one war documentary gets recommended conspiracy content.
- For children: YouTube's algorithm is notoriously bad at keeping kids in age-appropriate content despite "restricted mode."
- Our AI content engine curating specific channels is *more appropriate* than YouTube's algorithm for every target audience.

#### What to Build Instead
- [ ] **YouTube Premium support** — If the family has YouTube Premium, detect it (logged-in session) and skip ads. This is the one legitimate reason to consider login. Configure via admin: "Log into YouTube for ad-free playback." Session stored in Chrome profile, not our DB.
- [ ] **Deeper channel curation** — Instead of 36 channels, support unlimited channels organized by the AI content engine. Auto-populate based on content profile: era-appropriate music, nature, nostalgia, educational.
- [ ] **YouTube playlist integration** — Allow caregivers to paste YouTube playlist URLs in admin. System extracts videos and adds to the viewing schedule. "Here's a playlist of Lawrence Welk episodes" → becomes a browsable show.
- [ ] **YouTube TV / YouTube Live** — For families subscribing to YouTube TV (live TV service): integrate as a streaming service (see above). Live sports, local news, cable channels — all through the managed browser tab approach.
- [ ] **Cached video metadata** — Pre-fetch video titles, thumbnails, and durations for all curated channels. Show them in our UI with our navigation (not YouTube's). Only open YouTube when actually playing. Reduces exposure to YouTube's interface.

### Audio & Video Intelligence

Current system uses a broadcast-style Web Audio API chain in `audio-normalizer.js`: Voice EQ → Slow AGC Compressor → Fixed Makeup Gain → Fast Limiter. No feedback loops. Configurable voice boost (off/mild/strong) and target volume level (-20 to -8 LUFS) in admin settings. Sonos soundbar on optical output from the TV.

#### Audio/Video Sync (P0 — BROKEN)

**Root cause (measured):** `createMediaElementSource()` takes Chrome's audio path away from its internal A/V sync engine. Chrome can no longer compensate for output buffer latency. Measured on live system:
- `AudioContext.baseLatency`: ~11ms (our processing chain — 7 nodes)
- `AudioContext.outputLatency`: ~40-48ms (PipeWire/ALSA system buffer)
- **Total Web Audio latency: ~51-59ms** (above 40ms perceptible threshold)
- Sonos optical processing: ~30-75ms additional (unmeasured, typical for soundbars)
- **Estimated total: 80-130ms** — clearly visible lip desync

Current `latencyHint: 'interactive'` and `video.currentTime += totalLatency` compensation are insufficient. The video seek is a one-time band-aid that doesn't account for variable latency and doesn't work for live streams.

**Proper fix: Move audio processing to PipeWire (system-level)**

The correct architecture is to keep audio processing OUTSIDE the browser so Chrome retains its internal A/V sync:

```
Chrome (no Web Audio) → HDMI/optical → PipeWire filter chain → Sonos
                                         ↑
                              EQ + AGC + Limiter (LADSPA/LV2 plugins)
```

- [ ] **PipeWire filter chain** — Move the entire audio processing chain (voice EQ, AGC compressor, makeup gain, fast limiter) to PipeWire using LADSPA or LV2 plugins:
  - **EQ**: `ladspa-plugin-calf` Calf Parametric EQ (highpass, presence boost, mud cut — same bands as current Web Audio EQ)
  - **Compressor/AGC**: Calf Compressor or Steve Harris SC4 compressor (threshold, ratio, attack, release — same settings as current AGC)
  - **Limiter**: Calf Limiter or Fast Lookahead Limiter (brick-wall ceiling at -3dB)
  - Configure via WirePlumber filter rules applied to Chrome's audio output
  - **Result**: Chrome plays audio normally with full A/V sync. PipeWire processes it before it hits the Sonos. Zero browser latency. System-wide (covers alerts, chimes, everything).
- [ ] **WirePlumber configuration** — Create persistent filter rules in `~/.config/wireplumber/`:
  - Match Chrome's audio sink by application name
  - Insert LADSPA/LV2 plugin chain between Chrome and HDMI output
  - Survives reboots — no `fix_audio.sh` workaround needed
  - Parameters (EQ bands, compression ratio, makeup gain) configurable via files that admin panel can write
- [ ] **Admin settings bridge** — When voice_boost or audio_target changes in admin panel, write new PipeWire filter parameters and reload the filter chain. Same admin UI, different backend.
- [ ] **Remove Web Audio chain** — Once PipeWire processing is validated, remove `audio-normalizer.js` entirely. Chrome plays raw audio, PipeWire handles all processing. `createMediaElementSource()` is never called, Chrome keeps full A/V sync control.
- [ ] **Fallback for non-PipeWire systems** — If PipeWire is not available (older Ubuntu, PulseAudio), fall back to the Web Audio chain with a warning in admin: "Audio processing may cause slight lip sync delay. Configure your soundbar's lip sync offset to compensate."

**Interim fixes (before PipeWire migration):**
- [x] ~~Measure actual latency~~ — Done: 51-59ms total (11ms processing + 40ms system buffer)
- [ ] **Sonos lip sync calibration** — Run Sonos app's auto-calibration (Settings > System > [room] > TV Dialog Sync) while Senior TV is playing. May compensate for combined Web Audio + optical delay.
- [ ] **Admin audio delay offset** — Configurable ±200ms setting. Applied as `video.currentTime` adjustment. Band-aid but helps while PipeWire migration is in progress.
- [ ] **Jellyfin server-side normalization** — For Jellyfin content (majority of viewing), apply `ffmpeg loudnorm` + EQ filters during transcoding. No Web Audio needed for VOD. Only use Web Audio chain for Pluto TV live streams (where sync is less critical and content is already broadcast-normalized).

#### Consistent Volume Across Everything
Implemented: broadcast-style chain (slow AGC compressor → fixed makeup gain → fast limiter). No feedback loops, no oscillation. Configurable target level in admin. Remaining work:

- [x] ~~Cross-content volume normalization~~ — Done: broadcast-style chain with fixed makeup gain
- [x] ~~Commercial loudness taming~~ — Done: fast limiter catches peaks, AGC compressor evens levels
- [x] ~~Voice boost / parametric EQ~~ — Done: 3-band EQ (highpass, presence boost, mud cut), configurable off/mild/strong

- [ ] **Night mode** — Reduced maximum volume after configurable evening hour (e.g., 9 PM). Lower makeup gain value in the broadcast chain. Prevents TV from waking someone in another room.
- [ ] **Source-specific gain presets** — Different sources have different baseline levels. Learn and store per-source makeup gain offsets in DB (Jellyfin, Pluto, YouTube, alerts), apply on source switch.

#### Voice Boost & Dialogue Clarity
- [x] ~~Parametric EQ for voice frequencies~~ — Done: 3-band EQ chain (80/120Hz highpass, 3kHz presence boost, 300Hz mud cut). Configurable off/mild/strong in admin settings.
- [ ] **Dynamic voice detection** — Use Web Audio `AnalyserNode` to detect speech-frequency energy vs. broadband energy. When speech is detected, temporarily boost speech band and duck background. Simplified hearing aid approach. (P3 — static EQ gets 80% of the benefit.)
- [ ] **Sibilance control** — Optional de-esser: gentle high-shelf reduction above 6kHz when "hearing aid mode" is enabled in admin. (P3 — niche.)

#### Microphone-Based Room Audio Monitoring
The USB webcam (Logitech C920) has a built-in microphone. We use it to measure what's actually coming out of the TV speakers in the room — the ground truth of what they're hearing.

- [x] **Room loudness metering** — `volume_monitor.py` daemon records 1-second mic samples every 10 seconds via `arecord`. Stores RMS + dB level to `volume_logs` table. Supervised by `start.sh` alongside Flask/Chrome/CEC.
- [x] **Sonos volume correlation** — Each mic reading also records the current Sonos volume % (via Home Assistant `media_player.family_room` entity). Admin chart at `/admin/volume` shows both lines overlaid.
- [x] **Admin volume dashboard** — `/admin/volume` with Chart.js: dual-axis chart (room dB + Sonos %), 1h/6h/24h/3d/7d range selectors, current readings, min/avg/max stats, 30s auto-refresh.
- [x] **Baseline calibration (March 2026)** — Initial measurements: Sonos 66% = too loud upper limit (room -7 to -15 dB), Sonos 36-38% = can't hear dialog (room -19 to -29 dB). Comfortable range appears to be ~40-65% Sonos.
- [ ] **Audibility threshold enforcement** — Once thresholds are confirmed, auto-alert caregiver (or auto-adjust Sonos via HA) when room volume is outside the audible range for extended periods. Requires defining "too quiet for too long" and "too loud for too long" thresholds in admin settings.
- [ ] **Volume-per-content-source tracking** — Log which content source (Pluto, Jellyfin, YouTube) is playing alongside each volume reading. Build per-source volume profiles: "Pluto news channels are consistently 8dB louder than Jellyfin movies." Use this to pre-adjust Sonos volume when switching sources.
- [ ] **Silence detection (content)** — If room microphone detects silence for >30 seconds while content should be playing:
  - Could indicate: dead stream, audio routing failure, muted by accident, HDMI handshake lost
  - Trigger: check player state via CDP, check HDMI sink, run `fix_audio.sh` if needed
  - Alert caregiver if silence persists after auto-repair
- [ ] **Ambient noise awareness** — If microphone detects high ambient noise (visitors talking, vacuum cleaner):
  - Optionally auto-boost TV volume slightly
  - Or: pause/lower content and show "Room is busy" state
  - Resume normal volume when ambient drops
- [ ] **Feedback loop prevention** — Microphone monitoring must not create audio feedback loops. Use echo cancellation or only sample during known-quiet moments (between content transitions).

#### Environmental Sensors (SensorPush / BLE)
The room environment directly affects comfort and safety for elderly residents. Temperature and humidity matter: seniors are more vulnerable to heat stress, dehydration, and respiratory issues from dry air. The TV system is already the always-on brain in the room — it should monitor the room itself, not just what's on screen.

**Target hardware:** SensorPush HT.w (or similar BLE temperature/humidity sensor, ~$50). Water-resistant, long battery life, BLE range covers a room easily. The NucBox K11 has built-in Bluetooth.

- [ ] **BLE sensor polling** — Background daemon reads SensorPush (or any BLE temp/humidity sensor) via `bleak` Python library. Poll every 60 seconds. Store readings in `environment_logs` table (temperature, humidity, timestamp).
- [ ] **Admin environment dashboard** — `/admin/environment` with temp + humidity charts, daily min/max/avg, trend over days/weeks. Combine with volume data for a full "room status" view.
- [ ] **Comfort range alerts** — Configurable thresholds (e.g., temp > 82F or < 65F, humidity > 60% or < 25%). Push SSE alert to TV ("It's getting warm — is the AC on?") and/or notify caregiver.
- [ ] **Home Assistant integration** — If HA is configured, also read temp/humidity from any HA climate sensors. This covers both BLE-direct and HA-bridged sensors without requiring both.
- [ ] **Correlation with presence** — Cross-reference room temperature trends with presence detection. Room occupied + rising temperature = potential HVAC issue worth flagging.
- [ ] **Home screen widget** — Show current room temp/humidity on the TV home screen. Simple, glanceable — like a wall thermometer but on the TV.
- [ ] **Historical health signals** — Over weeks/months, temperature and humidity patterns become health-relevant data. "Room was 84F for 6 hours on Tuesday" is information a caregiver or doctor would want. Export-friendly format.

#### Dead Stream & Playback Health
Current detection: stall check every 10s in `player.js`, HLS retry with channel switch in `live_player.html`, `dead_stream` activity logging. Needs to be more proactive and comprehensive.

- [ ] **Proactive stream health dashboard** — Admin page showing:
  - Current playback state (playing/paused/stalled/error)
  - Current audio level (from normalizer stats)
  - Stream bitrate and buffer health (from HLS.js stats)
  - Time since last successful frame / audio decode
  - Historical dead stream events with patterns ("Pluto channel X dies every 4 hours")
- [ ] **Black screen detection** — Use CDP to capture a small screenshot periodically (already done for health checks). Analyze: if frame is >95% single color (black/frozen), flag as potential dead stream even if HLS reports healthy. Some streams deliver valid HLS segments with black frames.
- [ ] **Audio-video sync monitoring** — If Web Audio normalizer reports audio energy but video `currentTime` isn't advancing (or vice versa), flag as A/V desync. Auto-seek to live edge for live streams, or reload for VOD.
- [ ] **Predictive channel avoidance** — Track which Pluto TV channels frequently die. After N dead stream events on the same channel within a time window, deprioritize or warn in the channel list. Store reliability scores per channel in DB.
- [ ] **Jellyfin transcode health** — Monitor Jellyfin transcode sessions. If transcode falls behind (buffer underrun), proactively switch to lower bitrate or different audio codec before the player stalls.
- [ ] **Recovery logging & analytics** — Log every auto-recovery action (retry, codec switch, channel switch, audio re-route) with timestamps and success/failure. Surface in admin: "Last 24h: 3 dead streams recovered, 1 audio re-route, 0 unrecovered failures."

#### System Audio Pipeline Hardening
- [ ] **PipeWire session persistence** — Current `fix_audio.sh` re-routes on every watchdog cycle. Instead, configure PipeWire to persist HDMI as default sink across reboots and Chrome restarts via WirePlumber rules (not just `wpctl` commands that reset).
- [ ] **Audio device hotplug handling** — If HDMI is disconnected/reconnected (TV power cycle, cable reseat), auto-detect and re-route within seconds, not on the next 3-minute watchdog cycle.
- [ ] **Multi-output support** — For setups with external speakers or soundbars: detect and configure the correct output device during install wizard. Some seniors use Bluetooth hearing aid streaming — detect and prioritize.

### Stability
- [ ] Remaining hardcoded service IPs in admin services page (`server.py:1276-1286`) — 8 IPs, acceptable for single deployment but brittle if network changes
- [ ] 1 flaky Playwright test (`Any key returns home` on Photo Frame) — headless browser timing issue
- [ ] Pre-existing lint warning: unused `random` import in `server.py:1903`

---

## Tier 1: Make It Installable (10 homes)

Goal: Any technically-savvy family member can clone the repo and set this up for their loved one without editing code.

### Hardware

#### Reference Hardware: GMKtec Nucbox G3S ($220)

The system is designed to run on a **$220 mini PC**. The reference target is the [GMKtec Nucbox G3S](https://www.amazon.com/dp/B0GFCMGHJT) (Intel N95, 8GB DDR4, 256GB SSD). This is the box we'd hand to someone's nephew who "knows computers" and say "plug this in behind the TV."

Measured resource usage on production system (March 2026): Flask + Chrome kiosk + all daemons = **~3.3GB RAM** total (Ubuntu + GNOME + Chrome + Flask + person detection + volume monitor). CPU load average **0.22** (essentially idle — video decode is hardware-accelerated via Intel Quick Sync). App + venv = **~500MB disk**.

**What you need:**
- Any x86 mini PC with Intel Quick Sync or AMD VCN (hardware video decode)
- 8GB RAM minimum (measured 3.3GB usage = ~4.7GB headroom)
- 128GB+ SSD (app is 500MB; rest is OS + photos + logs)
- HDMI out to the TV
- 1 USB port for a webcam (presence detection + volume monitoring)
- WiFi or Ethernet

**What you do NOT need:**
- Home Assistant, Docker, Sonos, Samsung SmartThings, or any smart home platform
- A media server (Pluto TV + YouTube are free, no setup)
- More than 8GB RAM, a dedicated GPU, NVMe, Thunderbolt, or any gaming hardware
- A specific TV brand — any TV with HDMI works

**Recommended hardware list (March 2026 Amazon pricing):**

| # | Pick | Specs | Price | Who it's for |
|---|------|-------|-------|-------------|
| 1 | **GMKtec Nucbox G3S** | N95, 8GB, 256GB SSD | **~$220** | **The default recommendation.** This is what we test against. 8GB is enough for Senior TV standalone. Dual HDMI, 3x USB 3.2, WiFi 5, BT 5.0. Low power, quiet, cheap. If you're buying one box for one TV, this is it. |
| 2 | **DreamQuest Mini Plus** | N95, 12GB DDR5, 512GB SSD | ~$230 | **$10 more, 50% more RAM.** 12GB gives Chrome more breathing room for weeks of uptime. WiFi 6, BT 5.3. Best value if you can find it in stock. |
| 3 | **Beelink Mini S12** | N95, 16GB, 500GB SSD | ~$319 | **"Never think about it" pick.** 16GB means Chrome can run for months without memory pressure. 500GB for years of photos and logs. 2.5G ethernet. For families who want zero maintenance. |
| 4 | **GMKtec G3 Pro** | i3-10110U, 16GB, 512GB NVMe | ~$290 | **Runs local Jellyfin too.** If the family has a movie collection on a USB drive, this box can serve it locally alongside Senior TV. The i3 can handle one transcode stream. |
| 5 | **KAMRUI Pinova P1** | Ryzen 4300U, 16GB, 256GB | ~$320 | **Future-proof.** Way more power than needed, but if someone wants to add Home Assistant, Immich, or other services later, this can handle it without buying a second box. |

**Add a USB webcam (~$30-80):** Any USB webcam works for presence detection. A webcam with good low-light performance is ideal since TV rooms are often dim. The webcam serves triple duty: person detection (is someone watching?), room volume monitoring (via the built-in mic), and visual check-ins (caregiver can see a snapshot remotely). Recommended: Logitech C922 (~$80) for low-light, or any budget 720p+ USB cam for basic detection.

**Optional: USB PIR motion sensor (~$15-40):** For families who don't want a camera pointed at their loved one, a USB PIR sensor (like Tokyo Devices IWS600) provides reliable motion detection without video. It acts as a virtual keyboard — sends a keypress when motion is detected, which Senior TV can use for presence tracking. No software needed. Works in complete darkness. Drawback: no visual check-ins, no volume monitoring.

**BIOS setting (critical):** Set "Restore on AC Power Loss = Power On" so the system auto-recovers from power outages. Every mini PC brand has this in the BIOS/UEFI, but the menu location varies. The install guide should document this per-brand.

#### Embedded Services (installed by `install.sh`)

These run locally on the mini PC alongside Senior TV. The installer sets them up automatically:

| Service | RAM | What it does | User-facing |
|---------|-----|-------------|-------------|
| **Jellyfin** | ~300MB | Personal movie/show library. Family copies media to a folder or USB drive. | "Watch your movies and shows" |
| **Immich** (ML disabled) | ~600MB | Family photo portal. Anyone with the link can upload photos from their phone. Photos appear on the TV slideshow. | "See family photos on the TV" |
| **Bazarr** | ~100MB | Automatic subtitle downloads for Jellyfin content. Critical for hearing-impaired users. | Invisible — subtitles just work |
| **Cloudflare Tunnel** | ~30MB | Secure remote access to admin panel. No port forwarding needed. | Caregiver accesses admin from anywhere |
| **Tailscale** | ~20MB | SSH access for the family tech person. Mesh VPN, no config. | Invisible — remote maintenance |

Total embedded services overhead: **~1.05GB**. Combined with Senior TV (~0.9GB) and Ubuntu (~1.0GB) = **~2.95GB on an 8GB box.** Comfortable.

#### Camera Support: IP Cameras Only

Senior TV works with **standard IP cameras** — any camera that exposes an HTTP snapshot URL or RTSP stream on your local network. This includes most cameras from Amcrest, Reolink, Hikvision, Dahua, Wyze (with RTSP firmware), and generic ONVIF-compatible cameras.

**Closed ecosystems (Ring, Nest, Arlo, Blink) are not supported.** These cameras lock their feeds behind proprietary cloud APIs that require paid subscriptions and can change or break at any time. We will not build integrations that depend on a corporation's cloud staying available and affordable.

How it works:
- Setup wizard asks: "Do you have a front door camera? Enter its IP address."
- Senior TV grabs a frame every 5 seconds via HTTP snapshot
- MobileNet SSD runs person detection (~30ms, same model used for the webcam)
- Person detected → doorbell alert on TV with camera snapshot, spoken aloud via TTS
- No Frigate, no Docker, no NVR platform. ~100MB total for the detection model.
- Snapshot saved so caregiver can review who was at the door via admin panel

#### Other Optional Integrations

These are for families who already have the infrastructure — **none are required:**

| Service | What it adds | Requires |
|---------|-------------|----------|
| **Home Assistant** | Smart home control (smart speaker volume, TV power, sensors, automations) | HA instance on LAN |

#### Zero-Service Baseline

Even with nothing connected — no Jellyfin, no Immich, no camera, no HA — Senior TV still works:
- **Pluto TV** — 400+ free live channels (no account needed)
- **YouTube** — curated channels (no login needed)
- **HDMI-CEC** — TV power and volume control through the HDMI cable
- **Local webcam** — presence detection + room volume monitoring (MobileNet SSD, ~100MB RAM)
- **Weather** — Open-Meteo (free, no API key)
- **Photo upload** — admin panel has built-in photo upload (no Immich needed)
- **Pill reminders, calendar, messages** — all local, all work offline

#### Development System

Our deployment runs on a GMKtec NucBox K11 (Ryzen 9 8945HS, 32GB DDR5, 1TB NVMe, ~$817) — but that machine also runs Jellyfin, Immich, Home Assistant, and other services. Senior TV alone uses <5% of its capacity. We replaced Frigate (2.7GB RAM, Docker) with local MobileNet SSD person detection (~100MB RAM, pure Python) in March 2026, proving the system can run on minimal hardware.

### Installation
- [ ] **`install.sh` script** — One-command setup on fresh Ubuntu 22.04/24.04:
  - System packages: Chrome, CEC tools, PipeWire, ffmpeg, OpenCV
  - Python venv + dependencies
  - Chrome kiosk policies (uBlock Origin ad blocker)
  - systemd service (senior-tv) + watchdog timer
  - Audio routing (HDMI default)
  - Docker + embedded services: Jellyfin, Immich (ML disabled), Bazarr
  - Tailscale install (user runs `tailscale up` during wizard)
  - Cloudflare tunnel setup (user provides tunnel token during wizard)
  - MobileNet SSD model download (23MB, person detection)
  - BIOS reminder: "Set Restore on AC Power Loss = Power On"
- [ ] **Hardware compatibility matrix** — Test on GMKtec G3S (reference), Beelink S12, DreamQuest Mini Plus. Document BIOS auto-power-on setting for each.
- [ ] **Installation documentation** — Step-by-step: hardware purchase guide, Ubuntu install, `git clone && ./install.sh`, first-boot wizard, TV connection, remote pairing.

### First-Run Experience
- [ ] **First-boot setup wizard** — On first launch, admin panel shows onboarding flow instead of dashboard:
  1. "Who is this TV for?" — Name(s), photo, relationship
  2. "What's their situation?" — Pick a care profile template (see below)
  3. "Tell me about them" — Conversational AI profile builder (see Content Engine below)
  4. "Where are they?" — City/zip for weather
  5. "Set up reminders" — Medications, times, days, blocking behavior
  6. "Got movies?" — Point Jellyfin at a folder or USB drive. Skip if no personal media.
  7. "Got a front door camera?" — Enter IP address. Must be a standard IP camera (not Ring/Nest/Arlo). Skip if none.
  8. "Remote access" — Paste Cloudflare tunnel token for remote admin. `tailscale up` for SSH.
  7. "Here's your plan" — Claude presents the generated content profile, viewing schedule, and curated channels for review
  8. Writes everything to settings DB — no config files to edit

### AI Content Engine (Claude-Powered)

The content engine is the intelligence layer that turns "my 89-year-old mom likes westerns" into a fully programmed TV experience. It runs during the setup wizard and can be re-invoked anytime from admin settings.

#### Profile Builder (Wizard Step 3)
- [ ] **Conversational intake** — Claude asks natural questions in the admin wizard chat interface:
  - "When was [name] born?" → birth year drives era-appropriate recommendations
  - "What do they enjoy watching?" → genres, specific shows, interests
  - "What did they do for a living? Hobbies?" → informs content beyond obvious TV preferences (a retired nurse might love medical dramas, a WWII veteran might enjoy war documentaries)
  - "Any cognitive or sensory considerations?" → drives complexity filtering, subtitle defaults, TTS, stimulation limits
  - "What should we avoid?" → violence thresholds, upsetting topics, specific triggers
  - "Do they follow any sports teams?" → live sports scheduling
  - "What music do they like?" → background music, music channels
- [ ] **Era-aware recommendation engine** — Birth year maps to cultural touchstones:
  - Born 1930s → Golden Age TV (I Love Lucy, Gunsmoke, Perry Mason), big band/swing music, WWII documentaries, classic westerns, Lawrence Welk
  - Born 1940s → variety shows (Ed Sullivan), early sitcoms (Dick Van Dyke, Andy Griffith), Motown, Elvis, classic country
  - Born 1950s → All in the Family, M\*A\*S\*H, Johnny Carson, classic rock, early game shows
  - Born 1960s → Cheers, Seinfeld, MTV era music, action movies, 80s nostalgia
  - Born 2010s+ (children) → age-appropriate animation, educational content, nature documentaries
  - Modern shows that recreate their era: All Creatures Great and Small (1930s), Call the Midwife (1950s), The Crown, Poirot
- [ ] **Cognitive-level adaptation** — Claude adjusts recommendations based on cognitive assessment:
  - **Full cognition** → complex dramas, mysteries, documentaries with narrative
  - **Mild impairment** → familiar formats (game shows, sitcoms), episodic (no season arcs), clear dialogue
  - **Moderate impairment** → music, nature, variety shows, familiar comfort shows on repeat, short segments
  - **Severe impairment** → music (memory preserved longest), ambient nature, family photos, simple visual content
- [ ] **Generated content profile** — Claude outputs a structured JSON profile:
  ```json
  {
    "name": "Margaret",
    "birth_year": 1936,
    "era_preferences": ["1950s", "1960s", "1930s_period"],
    "genres": ["western", "game_show", "mystery", "period_drama", "variety"],
    "specific_shows": ["Gunsmoke", "Jeopardy", "Perry Mason", "All Creatures Great and Small"],
    "music_preferences": ["big_band", "classical", "oldies_1950s"],
    "sports": {"teams": ["Dodgers"], "types": ["baseball"]},
    "avoid": ["graphic_violence", "horror", "heavy_news"],
    "cognitive_level": "mild_impairment",
    "complexity_max": "episodic",
    "stimulation_limit_hour": 15,
    "tts_enabled": true,
    "subtitle_default": true
  }
  ```

#### Media Source Matching
- [ ] **Jellyfin library scan** — After profile is built, scan the connected Jellyfin library and match against the content profile:
  - Cross-reference profile genres/eras against Jellyfin movie metadata (genre, year, rating)
  - Identify specific shows from the profile that exist in the library
  - Score every item: era match + genre match + cognitive appropriateness + user-specific keywords
  - Flag items to exclude (too violent, too complex, wrong era)
  - Result: a ranked content library tailored to this person, stored in DB
- [ ] **Pluto TV channel matching** — Map profile against 421 Pluto channels:
  - Auto-favorite channels that match: western channels for western fans, game show channels, classic TV channels
  - Identify live sports channels matching their teams
  - Flag news channels with time-of-day rules (available mornings only if stimulation limits set)
  - Auto-populate the favorite channels list
- [ ] **YouTube channel curation** — Claude recommends YouTube channels based on profile:
  - Era-specific music compilations (1950s hits, big band collections, Lawrence Welk episodes)
  - Nature/ambient channels (for wind-down, low-cognition periods)
  - Nostalgia channels (classic TV clips, old commercials, historical footage)
  - Sports highlights for their teams
  - Auto-populate the 36-channel YouTube grid with profile-matched channels
- [ ] **Free content discovery** — For users without Jellyfin, find free sources:
  - Internet Archive (see below — first-class integration)
  - Pluto TV: identify all channels matching their profile
  - YouTube: deep curation of free full-length content (classic TV episodes, concerts, documentaries)
  - Tubi/other free streaming: surface compatible free content

#### Internet Archive Integration (First-Class Free Media Source)

The Internet Archive (archive.org) is the best source of free, legal media for Jellyfin libraries. Millions of public domain and openly licensed films, music, radio shows, and audio — with a bulk-friendly API designed for exactly this use case. Unlike the Library of Congress (streaming-only audio, no bulk downloads, unclear rights), the Internet Archive clearly marks rights per item and encourages downloading.

**Key collections for Senior TV profiles:**
- **Prelinger Archives** — 10,000+ educational and industrial films (1930s–1970s)
- **Feature Films** — public domain movies (classic westerns, mysteries, comedies, noir)
- **Old Time Radio** — thousands of classic radio dramas, comedies, mysteries (The Shadow, Dragnet, Gunsmoke radio, Jack Benny). Perfect for 1930s-era births — radio was their primary entertainment growing up
- **78rpm & Cylinder Audio** — music recordings from 1900s–1950s (big band, swing, jazz, early country)
- **Live Music Archive** — concert recordings (Grateful Dead, jazz, folk)
- **Newsreels & Documentaries** — historical footage from their lifetime
- **Government Films** — NASA, military, educational (US government works = no copyright)
- **Classic TV** — some public domain television episodes

**What to build:**
- [ ] **Internet Archive search API integration** — IA provides a well-documented API (`archive.org/advancedsearch.php` and item metadata at `archive.org/metadata/{id}`). The AI content engine queries IA based on the content profile:
  - Birth year 1931 → search for 1930s–1960s films, big band music, old time radio
  - Genre "western" → search IA's Feature Films for westerns
  - Music preference "classical" → search audio collections for classical recordings
  - Returns: title, year, description, duration, format, download URLs
- [ ] **Automated download to Jellyfin** — When the content engine finds matching IA content:
  - Download media files directly via IA's S3-like download URLs (no API key needed)
  - Rename and organize into Jellyfin-compatible directory structure (`/movies/Title (Year)/`, `/music/Artist/Album/`)
  - Trigger Jellyfin library scan to pick up new content
  - Track what's been downloaded to avoid duplicates
  - Configurable storage limit: "Download up to 50GB of free content" (prevent filling disk)
- [ ] **Curated starter packs** — Pre-built download lists for common profiles, maintained in the repo:
  - "1930s Senior Starter" — 50 classic films, 200 old time radio episodes, 100 big band albums
  - "1940s Senior Starter" — WWII documentaries, film noir, swing music, variety shows
  - "Children's Starter" — public domain animation (Fleischer, early Disney expired copyrights), educational films
  - These download during initial setup if user opts in. Instant content library, zero cost, fully legal.
- [ ] **Old Time Radio as a content type** — OTR is a goldmine for seniors born in the 1920s–1940s. These 20–30 minute radio episodes are:
  - Perfect for dementia care: short, self-contained, familiar voices and formats
  - Low cognitive load: audio-only, can pair with family photo slideshow on screen
  - Massive library: thousands of episodes across dozens of shows on IA
  - New TV UI section: "Radio Shows" with show posters, episode lists, audio player with slideshow background
- [ ] **Quality and format selection** — IA offers multiple formats per item. Auto-select:
  - Video: MP4 (H.264) preferred for Chrome/Jellyfin compatibility, fallback to MPEG-4
  - Audio: MP3 for music/radio (smaller), FLAC if storage allows
  - Resolution: prefer highest available, but cap at 1080p (sufficient for TV viewing)
  - Skip items with no suitable format available
- [ ] **Rights verification** — Only download items with clear public domain or open license markers:
  - `licenseurl` field contains creativecommons.org or publicdomain
  - `rights` field indicates public domain
  - Collection is known-PD (Prelinger, US government films)
  - Skip items with unclear rights — conservative approach, legal safety
- [ ] **Content scoring against profile** — IA metadata includes title, year, description, subject tags, and sometimes reviews. AI content engine scores each result:
  - Era match (year vs. birth year preferences)
  - Genre/subject match against profile
  - Quality score (resolution, audio quality, file completeness)
  - Community rating (IA has download counts and reviews)
  - Only download items scoring above threshold

**What this enables:**
A family installs Senior TV, runs the setup wizard, and without owning a single movie or having any streaming subscription, the system downloads 50+ classic films, hundreds of radio shows, and era-appropriate music — all free, all legal. The TV has a full content library within hours of first boot. This is the "zero external services" promise made real.

**Library of Congress — NOT a primary source:**
The LOC was evaluated and rejected as a primary media source because: National Jukebox audio is streaming-only (Sony contract), no bulk download support (TOS prohibits scraping), rights determination burden falls on the user, limited AV content available for download, and most National Film Registry titles are still under copyright. Individual LOC items that are clearly public domain (pre-1929 films, government works) may appear in Internet Archive collections anyway.

#### *Arr Integration (4 of 26 tools only)

The *Arr suite has 26+ tools. Senior TV integrates with exactly 4 at the API level — the ones that directly serve content to viewers. Everything else (Prowlarr, download clients, VPN, cleanup tools, cross-seed, etc.) is the user's own infrastructure. We don't touch it, don't configure it, don't know about it.

**The 4 tools we integrate with:**

| Tool | What it does | Senior TV integration | Priority |
|------|-------------|----------------------|----------|
| **Bazarr** | Auto-downloads subtitles for Sonarr/Radarr libraries | **P0** — directly enables auto-subtitles for hearing-impaired viewers. Deploy via Docker, point at Jellyfin library, subtitles appear automatically. | P0 |
| **Radarr** | Movie management | Content engine pushes "missing movie" wishlists to Radarr API | P3 |
| **Sonarr** | TV show management | Content engine pushes "missing show" wishlists to Sonarr API | P3 |
| **Lidarr** | Music management | Content engine acquires era-appropriate albums for background music | P3 |

**Architectural boundary:** Senior TV is the presentation and care layer. Jellyfin serves media. *Arr acquires media. They are separate systems with separate concerns. Senior TV never ships content acquisition tools — it integrates with them at the API level if they're present.

**Why not bundle it:**
- The *Arr stack is almost exclusively used for acquiring copyrighted content
- An open-source care project shipping piracy automation = GitHub takedowns, zero care facility adoption, legal exposure
- Senior TV must remain clean — a caregiver system, not a download tool
- Users who want *Arr already know how to run it; users who don't shouldn't be nudged toward it

**What to build (Radarr/Sonarr/Lidarr — P3, depends on AI content engine):**
- [ ] **Detect *Arr services** — In admin settings, optional fields for Radarr/Sonarr/Lidarr URLs and API keys. Connection test like Jellyfin/Immich. If not configured, the content engine simply skips acquisition features — no impact on anything else.
- [ ] **Content gap report** — When the AI content engine builds a profile, it identifies recommended content that isn't available in Jellyfin or any free source. Display as a "wishlist" in admin: "The content engine recommends these 23 shows for Margaret, but 8 aren't in your library." Useful even without *Arr — tells the caregiver what DVDs to buy or streaming services to subscribe to.
- [ ] **Wishlist → Radarr/Sonarr** — If *Arr is configured, the content gap report gets an "Add to Radarr/Sonarr" button per item. One click adds the movie/show to the *Arr wishlist with the user's configured quality profile. *Arr handles the rest — search, download, import, Jellyfin notification.
- [ ] **Bulk acquisition mode** — During initial setup, after the AI content engine generates a profile with 50+ recommended titles, offer "Add all missing to download queue" button. Populates Radarr/Sonarr wishlists in batch. The library fills up over days/weeks as content downloads.
- [ ] **Auto-scan trigger** — When Radarr/Sonarr finishes importing new content, trigger a Jellyfin library scan, then re-run the content engine's media matching to incorporate new items into the viewing schedule. Radarr/Sonarr support webhooks for this.
- [ ] **Lidarr for music** — If profile includes music preferences (big band, classical, oldies), Lidarr can acquire full albums. Background music playlists built from actually-owned music files rather than YouTube streams.
- [ ] **Quality profile recommendations** — Based on care profile, suggest *Arr quality settings: 1080p is plenty for a 65" TV at senior viewing distance, audio should prefer stereo AAC over surround (simpler for TV speakers), prefer pre-subtitled releases.

**What NOT to build:**
- No built-in torrent/Usenet client — that's *Arr's job
- No VPN configuration — that's the user's infrastructure responsibility
- No download progress UI — Radarr/Sonarr have their own dashboards
- No default indexer configuration — user sets up Prowlarr themselves
- Senior TV's README/docs should mention *Arr as an optional companion tool for users who want automated library building, with a link to *Arr documentation, and nothing more

#### Viewing Schedule Builder
- [ ] **Daily schedule generation** — Claude builds a time-of-day viewing schedule from the matched content:
  ```
  7:00 AM  — Morning music (big band playlist via YouTube)
  8:00 AM  — Breakfast TV (Today Show or morning game shows on Pluto)
  10:00 AM — Classical music block (doctor configurable)
  11:00 AM — Morning movie (Jellyfin: era-matched western or mystery)
  1:00 PM  — Afternoon show (Jellyfin: Perry Mason, Gunsmoke episodes)
  3:00 PM  — [stimulation limit kicks in]
  3:00 PM  — Afternoon music & photos (oldies playlist + family slideshow)
  5:00 PM  — Wind-down (nature/ambient YouTube channels)
  7:00 PM  — Evening comfort (familiar sitcom episodes, Pluto classic TV)
  9:00 PM  — Bedtime wind-down (ambient video, soft music)
  ```
- [ ] **Schedule stored in DB** — `viewing_schedule` table with time slots, content source, content ID/query, fallback content. Editable in admin.
- [ ] **Auto-play integration** — Schedule drives what auto-plays when the TV is on but idle. Currently we auto-play wind-down video after 3 PM; this generalizes to any time slot playing appropriate content.
- [ ] **Schedule respects care events** — Pill reminders, shower blocks, and stretch breaks interrupt the schedule. Content resumes after dismissal.
- [ ] **Weekend/weekday variants** — Different schedules for different days (sports on game days, church music on Sundays, etc.)
- [ ] **Seasonal awareness** — Baseball season → sports in afternoon slots. Holiday seasons → themed content. Summer → lighter viewing.

#### Profile Refinement (Ongoing)
- [ ] **Admin "Ask Claude" button** — Anytime in admin, caregiver can chat with Claude to refine the profile: "She's been really enjoying the nature videos, add more of those" or "The mysteries are too complex, switch to simpler shows"
- [ ] **Activity-informed suggestions** — System tracks what's watched and for how long. Claude periodically reviews activity logs and suggests adjustments: "Margaret watched All Creatures for 3 hours but skipped past the mystery movies — consider swapping mystery slots for more period dramas"
- [ ] **Family input** — Family members can suggest content via the message system or admin: "Mom used to love Lawrence Welk" → Claude adds to profile and finds sources
- [ ] **Re-scan on library changes** — When new content is added to Jellyfin, re-run the matching engine to incorporate new items into the schedule

### Profiles & Configuration
- [ ] **Profiles table** — `name`, `birth_year`, `greeting`, `photo`, `cognitive_level`, `care_template`, `content_profile` (JSON from AI engine), `viewing_schedule` (JSON), `custom_rules` (JSON). Replaces all hardcoded names/greetings in templates.
- [ ] **Care profile templates** — Pre-built starting points users pick and customize:
  - **Senior with dementia** — current Don & Colleen setup: time-of-day content, sundowning protection, simplified UI, medication reminders, blocking hygiene reminders
  - **Senior, independent** — full content access, simplified UI, medication reminders (non-blocking), family communication, doorbell alerts
  - **Child (young, under 8)** — allowlisted content only, screen time budget, educational content scheduling, big picture tiles, reward-gated access
  - **Child (older, 8-16)** — broader content with parental approval, daily time limits, activity logging, bedtime auto-off
  - **Accessibility** — simplified UI, large text, reminders and routines, configurable navigation speed, TTS always on
  - **Custom** — blank slate, configure everything manually
- [ ] **Content rules in DB** — Move all time-of-day rules, content filtering, and stimulation limits from hardcoded `server.py` logic into a `content_rules` table editable via admin. Each care template pre-populates rules. AI content engine can generate and modify rules.
- [ ] **Remove all hardcoded values** — Every IP, name, coordinate, and care preference comes from settings DB or setup wizard. Zero code editing to deploy.

### Graceful Degradation
- [ ] **Every external service optional** — System works with zero integrations out of the box:
  - No Jellyfin → hide movies/shows sections, Pluto TV + YouTube still work
  - No Immich → photo slideshow uses local uploads only (`static/photos/`)
  - No Frigate/HA → no doorbell alerts, no presence detection; use keyboard idle timer for screensaver
  - No CEC hardware → keyboard or IR remote still works (already handled)
  - No internet → offline banner, local media still plays, reminders still fire
- [ ] **Progressive feature unlock** — As users connect services in admin settings, new sections appear automatically on the TV UI

### Generalized Reminders
- [ ] **Configurable reminder types** — Beyond pills and showers: exercise, meals, hydration, appointments, position changes (pressure sore prevention), screen time warnings, bedtime routine
- [ ] **Per-reminder settings** — Schedule (time, days, recurrence), blocking vs. dismissable, duration, escalation (re-remind after X minutes), custom message, custom audio
- [ ] **Screen time budgets** (for child profiles) — Daily limit in minutes, warning at 10 min remaining, TV locks when budget spent, resets daily

---

## Tier 2: Input, Accessibility & Admin (100 homes)

Goal: Broaden who can use it (more input methods, accessibility) and make remote management practical.

### Input & Accessibility
- [ ] **Input abstraction layer** — Define actions (select, back, up, down, scroll, volume) mapped from configurable input sources. Current 6-button CEC remote is one input profile; others plug in without changing navigation logic.
- [ ] **Touch mode** — For tablets and touchscreens. Tap-to-select, swipe to scroll, back button. Enables bedside tablets, kitchen displays.
- [ ] **Voice control** — "Play my music," "What time is it," "Show photos." Web Speech API (already in browser, no dependencies). Useful for motor disabilities, visually impaired, or hands-busy situations.
- [ ] **Switch scanning mode** — Auto-highlight items sequentially, single button to select. Standard assistive technology for motor disabilities.
- [ ] **Configurable UI density** — Font size slider (36px–72px), spacing, animation reduction, high contrast themes, color blindness modes. Editable in admin.
- [ ] **Full ARIA accessibility** — Screen reader support, focus management, landmark roles. Benefits visually impaired users.
- [ ] **Transition warnings** — "Your show ends in 5 minutes" for users who need predictability (autism, cognitive disabilities, children's bedtime).

### Admin & Remote Management
- [ ] **Admin UI overhaul** — Mobile-friendly design for non-technical family members. Care profile editor, activity charts, friendly reminder management. Visual schedule builder. This is a big standalone project.
- [ ] **Remote admin via Tailscale/Cloudflare** — Document setup for remote access without LAN. Current Cloudflare tunnel works; add Tailscale Funnel as alternative.
- [ ] **Family notification system** — Push alerts to phones: pill not acknowledged in 30 min, TV offline 1 hour, person at door. Email or Telegram (no app store dependency).
- [ ] **Caregiver activity log** — Exportable reports: what was watched, reminder compliance, activity patterns. Foundation exists (`activity_logs` and `remote_logs` tables).
- [ ] **Multi-resident support** — Per-resident profiles with profile switching (PIN or face). Greeting rotation, personalized content. Useful for couples, group homes, children sharing a TV.
- [ ] **OTA updates** — `git pull`, run migrations, restart. Triggered from admin panel. No SSH required.

### Content & Community
- [ ] **Shareable content profiles** — Export/import AI-generated profiles as YAML/JSON. Community shares them on GitHub: "My 1940s-born dad's profile," "Autism-friendly children's lineup," "Post-stroke recovery viewing." Others import as a starting point, then Claude adapts to their person.
- [ ] **Content complexity scoring** — Tag content as low/medium/high cognitive load. Care profiles auto-filter based on cognitive level setting. AI engine scores new content automatically.
- [ ] **Community content curations** — Curated channel packs: "best YouTube channels for toddlers," "calming ambient for sundowning," "classic westerns playlist." Community contributions via GitHub, installable via admin panel.
- [ ] **Localization** — i18n support. Spanish first (large caregiver population), then community-contributed translations. AI content engine generates era-appropriate recommendations in any language/culture.

---

## Tier 3: Make It a Product (1,000+ homes)

Goal: Non-technical families can buy a box, plug it in, and it works. The project has a sustainable open-source community.

### Packaging & Distribution
- [ ] **Docker container** — `docker-compose up` with single config file. Bundles Chrome, Flask, CEC tools, PipeWire. Alternative to bare-metal `install.sh`.
- [ ] **Raspberry Pi image** — Pre-built SD card image. Cheapest hardware path (~$80 total: Pi 5 + case + SD card + power). Download, flash, boot, wizard.
- [ ] **Pre-configured hardware kit** — Partner with mini PC seller. Ship ready: mini PC, HDMI cable, simple remote, quick start card. $150–300.
- [ ] **Reliable HDMI-CEC** — Curate hardware with known-good CEC. Include USB CEC adapter (Pulse-Eight) as fallback. Document what works.

### Content & Media
- [ ] **Free content out of the box** — Pluto TV (421 channels), YouTube (curated), Internet Archive (public domain movies, music). AI content engine finds all free sources matching the profile — no Jellyfin or subscriptions needed.
- [ ] **Spotify/Apple Music integration** — OAuth flow, Web Playback SDK. AI engine builds era-appropriate playlists: big band for 1930s births, Motown for 1940s, classic rock for 1950s. Replaces YouTube for music.
- [ ] **AI content engine at scale** — Aggregate anonymized profile patterns across deployments (opt-in). "People with similar profiles to yours also enjoyed..." Community-maintained "dementia-friendly" and "kid-safe" content ratings enriched by AI scoring.
- [ ] **Plugin system for media sources** — Abstract media provider interface so the AI engine can match content across any source. Community can add: Netflix (via browser), Disney+, local NAS, IPTV, podcast feeds, Tubi, PBS.
- [ ] **Streaming availability lookup** — AI engine recommends shows; system checks which streaming services carry them and surfaces options: "Perry Mason is on Pluto TV channel 'Perry Mason', or available on your Jellyfin library, or free on Internet Archive."

### Family Connection
- [ ] **Photo sharing** — Simple web upload (phone browser) → appears on TV slideshow. No app install, no Immich required. Works over Tailscale or Cloudflare tunnel.
- [ ] **Video calling** — One-tap call from phone to TV. User presses OK to answer. WebRTC peer-to-peer.
- [ ] **Two-way communication** — Pre-set response buttons on TV: "I'm fine," "Call me," "Yes/No." Sends to family via notification system.
- [ ] **Family activity feed** — "Sarah sent a photo," "Mom took her pills," "Dad watched a movie." Visible in admin.

### Facility / Group Home Support
- [ ] **Multi-TV management** — One admin panel controls multiple boxes. Per-room profiles, facility-wide announcements via SSE.
- [ ] **Staff dashboard** — Shift view: who took meds, who missed, activity summary, alerts. Role-based access (admin, nurse, family).
- [ ] **Compliance reporting** — Medication acknowledgment logs, activity reports, exportable for regulatory review.
- [ ] **Facility announcements** — "Lunch in 15 minutes" pushed to all TVs. Leverages existing SSE infrastructure.

### Sustainability
- [ ] **GitHub community** — Issue templates for bug reports, feature requests, hardware compatibility reports. Contributing guide. Community content curations.
- [ ] **Documentation site** — Setup guides, hardware recommendations, care profile examples, FAQ, troubleshooting.
- [ ] **YouTube ToS compliance** — Clarify kiosk embedding legality or migrate to YouTube Data API.
- [ ] **Privacy & compliance** — Privacy policy template for deployments handling health data. HIPAA guidance for care facilities. All data stays local by default.

---

## Tier 4: Optional Cloud Services & Business Model

The core product is free and open-source forever. Optional paid services for families who want managed convenience:

### Cloud Services (Optional, Never Required)
- [ ] **Cloud admin dashboard** — Web app to manage box remotely without Tailscale/VPN setup. View health, send messages, update settings.
- [ ] **Managed notifications** — Push alerts to phones without self-hosting: pill not taken, TV offline, person at door.
- [ ] **Remote provisioning** — QR code setup: scan with phone, enter info, box auto-configures. No SSH.
- [ ] **Managed OTA updates** — Automatic updates with rollback. Currently manual `git pull`.
- [ ] **Telemetry & analytics** — Opt-in usage insights: what content works, reminder effectiveness, activity patterns.

### Revenue Model
- **Hardware kit** — $150–300 one-time (mini PC + remote + cables + quick start card). Margin on assembly/support.
- **Cloud subscription** — $10–20/month (remote dashboard, managed notifications, OTA updates, phone support). Entirely optional — everything works locally without it.
- **Care facility tier** — Per-room pricing for assisted living. Bulk management, staff dashboard, compliance reports, priority support.
- **The pitch** — "Your parent's TV becomes a care system. $200 once, works forever. Cloud dashboard optional."

### Why Open Source Wins Here
- Families trust it more — they can see exactly what runs on their loved one's TV
- Community contributions — content curations, translations, hardware guides, care templates
- No vendor lock-in — if the company disappears, the boxes keep working
- Care facilities can self-host everything, satisfying IT/security requirements

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
| Immich photo frame (143K photos, 10s auto-advance, EXIF display, random only — no album/people/date filtering) | Done |
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
