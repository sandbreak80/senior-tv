# Senior TV — Feature Tour

**A complete entertainment, care, and communication system for seniors**

Built for a 65" Samsung TV connected to a mini PC. Designed for elderly viewers with dementia and Alzheimer's — every feature prioritizes simplicity, large text, and minimal cognitive load.

---

## 🏠 Home Screen

The home screen is a hotel-TV-style welcome page that adapts throughout the day.

**What you see:**
- Large clock, personalized greeting ("Good Morning!")
- Current weather for your configured location
- Next pill reminder and upcoming calendar event
- Menu on the left, live LA news stream on the right (morning only — hidden after 3 PM per care plan)
- After 3 PM: calming ambient video from Wind Down channels (Bob Ross, BBC Earth, nature, fireplace)
- Family photo from Immich in the left panel (clickable to open full slideshow)
- Below: full-width navigation + content recommendations that change by time of day

**Time-of-day intelligence:**
- **Morning (before 2 PM):** Game shows, morning TV, news
- **Afternoon (2–5 PM):** Westerns, classic sitcoms, comedy, music
- **Evening (after 5 PM):** Wind-down content — Bob Ross, nature, ambient, gentle shows

*Screenshot: `01_home_screen.png`*

---

## 📺 Live TV — 421 Free Channels

Powered by Pluto TV. Browse by category with big channel cards.

**Categories include:** News, Classic TV, Westerns, Comedy, Drama, Game Shows, True Crime, Movies, Music, Nature, and more.

**How it works:**
1. Select "Live TV" from home
2. Browse channels or filter by category tabs at the top
3. Select a channel → plays instantly in our built-in HLS player
4. Persistent title bar always shows what's playing (they forget!)
5. Press Back → returns to channel guide

**Notable channels:** CBS News 24/7, Law & Order, Criminal Minds, CSI (3 channels), Dateline 24/7, Murder She Wrote, Bonanza, Comedy Central, America's Funniest Home Videos, Jeopardy reruns, and hundreds more.

*Screenshot: `02_live_tv_channels.png`*

---

## 🎬 Movies & Shows — 5,112 Movies + 108 TV Shows

Powered by Jellyfin media server. Full library browsing with poster art.

**Features:**
- **Continue Watching** — picks up where they left off
- **Daily 20 Movies** — 20 different movies every day, auto-rotated from the full library
- **Genre Filtering** — 19 genres: Western, Comedy, Drama, Family, Romance, War, etc.
- **Sort Options** — A-Z, Recently Added, Top Rated, Newest, Oldest, Surprise Me
- **Pagination** — 40 items per page, Next/Previous buttons
- **TV Shows** — Season/episode picker with full metadata
- **Shuffle Play** — random episode button on every show (perfect for sitcoms)
- **Subtitles** — enabled by default on all content

**Built-in video player:**
- Persistent title bar (always shows what's playing)
- Play/Pause (Enter), Skip 30s (Left/Right), Volume (Up/Down)
- Back key returns to browse

*Screenshots: `03_movies_and_shows.png`, `04_daily_20_movies.png`, `12_library_browse.png`*

---

## ▶️ YouTube — 36 Curated Channels

Hand-picked channels organized by category for seniors' interests.

**Categories:**
- **Westerns:** Bonanza, The Rifleman, Death Valley Days
- **Classic TV:** Carol Burnett, I Love Lucy, Andy Griffith
- **Comedy:** Whose Line, Comedy Central, Netflix Is A Joke, AFV
- **Game Shows:** Jeopardy, Wheel of Fortune
- **Music & Variety:** Lawrence Welk, Ed Sullivan, Johnny Carson
- **Crime & Drama:** Law & Order, Dateline, Criminal Minds
- **Wind Down:** Bob Ross, BBC Earth, nature, ambient
- **News, Local LA/SD, Cooking, Travel, Nature**

**Plus auto-detected local live stations** — ABC 7 LA, FOX 11 LA, CBS 8 San Diego (when live).

*Screenshot: `05_youtube.png`*

---

## 💌 Family Messages

**You and Cheryl can send messages, photos, and videos directly to their TV.**

**How it works:**
1. Go to the admin panel from your phone: `http://<device-ip>:5000/admin/messages/send`
2. Type a message, optionally attach a photo or video
3. Hit "Send to TV Now"
4. A notification pops up on the TV immediately: "💌 New Message from Brad!"
5. They press OK → full-screen view of your message with the photo/video
6. All messages saved in the "Messages" section of the TV menu

**Great for:** "We love you!", family photos, video greetings, daily check-ins.

*Screenshots: `06_messages.png`, `15_admin_send_message.png`*

---

## 📰 News

**Three layers of news:**
1. **🔴 Live YouTube News** — ABC News, NBC News, CBS News streams
2. **📡 Pluto TV News Channels** — CBS News 24/7, CNN Headlines, and more
3. **📋 Headlines** — scrollable RSS text headlines

News is hidden from the home screen after 3 PM (care plan — reduces evening agitation).

*Screenshot: `07_news.png`*

---

## 🌤️ Weather

Full weather display for your configured location.
- Current temperature, conditions, humidity, wind
- 5-day forecast with daily highs/lows
- Weather summary always visible on the home screen

*Screenshot: `08_weather.png`*

---

## 📅 Calendar — Three Views

**Daily View:** Hourly timeline for today, events highlighted
**Monthly View:** Grid calendar with today highlighted, dots on event days
**Upcoming View:** List of all upcoming events

**Pre-loaded with US holidays** through 2027 (Memorial Day, Independence Day, Thanksgiving, Christmas, etc.)

**Birthdays:** Full-screen birthday greetings at 9 AM with a Happy Birthday melody and age display.

*Screenshots: `09_calendar_daily.png`, `10_calendar_monthly.png`, `11_calendar_upcoming.png`*

---

## 💊 Reminders

**Three types of reminders, all full-screen:**

| Reminder | Schedule | Behavior |
|----------|----------|----------|
| Morning Pills | 11:00 AM daily | Full-screen popup + chime. Press OK to dismiss. |
| Evening Pills | 8:30 PM daily | Full-screen popup + chime. Press OK to dismiss. |
| Shower Time | Tue & Thu at 8am, 12pm, 4pm, 8pm | **Blocks TV for 15 minutes.** Countdown timer. Cannot dismiss early. |

Reminders support custom text, photos, or video messages. Shower reminders repeat every 4 hours on shower days until it gets done.

*Screenshot: `16_admin_pills.png`*

---

## 📺 Show Alerts

**9 favorite shows monitored on Pluto TV:**
Jeopardy, Two and a Half Men, Law & Order, Criminal Minds, CSI, Dateline, Murder She Wrote, Bonanza, Gunsmoke

When a favorite show is currently playing on any Pluto TV channel, a notification pops up:
> "📺 Jeopardy is on now! Channel: Jeopardy"

Auto-dismisses after 20 seconds. Checked every 10 minutes.

*Screenshot: `18_admin_favorite_shows.png`*

---

## 🚪 Doorbell / Security Alerts

**Frigate integration** — monitors the front door camera for person detection.

When someone is detected at the front door:
- Full-screen alert: "🚪 Someone is at the Front Door!"
- Camera snapshot displayed
- Ding-dong doorbell sound
- Auto-dismisses after 30 seconds, or press OK

Cameras monitored: `front_door` (configurable to add `back_patio`, `garage`, etc.)

---

## 📷 Photo Frame / Screensaver

**Three photo sources:**
1. **Immich** — 143,350 family photos from the Immich server, fetched in random batches
2. **Uploaded** — photos uploaded via the admin panel
3. **NAS** — photos from a mounted NAS folder

**Features:**
- Full-screen slideshow with crossfade transitions between two preloaded images
- Dynamic fetching: loads 20 random Immich photos at a time, fetches more as needed
- Clock overlay (top-right)
- After 10 minutes of inactivity on the home screen, auto-activates as screensaver
- Any key press returns to home instantly (kills in-flight image downloads for fast exit)
- Family photo widget on home page shows a random photo from Immich

---

## 🎂 Birthdays

Add family birthdays via admin. On their birthday at 9 AM:
- Full-screen greeting with Happy Birthday melody
- Shows their name and age (if birth year provided)
- Add family birthdays with birth year for age display

*Screenshot: `17_admin_birthdays.png`*

---

## 📱 Admin Panel

Accessible from any device on the network at **http://<device-ip>:5000/admin**

**Sections:**
| Page | What it does |
|------|-------------|
| Dashboard | Overview of pills, events, stats |
| Messages | Send text, photos, videos to the TV |
| Pills | Manage pill and shower reminders |
| Birthdays | Family birthdays with age calculation |
| Shows | Favorite show alerts (Pluto TV monitoring) |
| Calendar | Add events |
| YouTube | Curate YouTube channels by category |
| Photos | Upload family photos for the slideshow |
| Jellyfin | Media server connection setup |
| Settings | Weather location, Frigate cameras, Home Assistant, NAS path, everything |

*Screenshots: `14_admin_dashboard.png` through `20_admin_settings.png`*

---

## 🔧 Technical Details

- **Hardware:** Mini PC, Ubuntu 24.04, 4K display
- **TV:** Samsung 65" connected via HDMI
- **Browser:** Google Chrome kiosk mode (dedicated profile, uBlock Origin ad blocker)
- **Backend:** Python/Flask, SQLite, APScheduler
- **Media:** Jellyfin (local Docker on localhost:8096 — public domain movies, classical music, classic TV shows from Archive.org)
- **Live TV:** Pluto TV (421 channels with logos, HLS proxy for CORS bypass)
- **Photos:** Immich (local Docker on localhost:2283 — family photo library, ML disabled for RAM savings)
- **Smart Home:** Frigate (doorbell camera), Home Assistant (TV control)
- **Remote:** Samsung TV remote via HDMI-CEC → keyboard events via xdotool
- **Auto-start:** systemd service with process supervision (Flask + Chrome + CEC bridge)
- **Self-healing:** Local watchdog (3 min) + Claude AI health agent (hourly) + HDMI audio persistence
- **Remote access:** SSH + Tailscale mesh VPN
- **Navigation:** 6 buttons only — Up, Down, Left, Right, OK, Back
- **YouTube security:** Sandboxed iframes, click-blocking overlays, no popups, disabled keyboard/annotations

---

## 💡 Design Philosophy

> **Remove complexity. Give choice. Inform. Remind. Entertain.**

- Everything navigable with just arrow keys
- Persistent title bar so they never forget what's playing
- Time-of-day content adapted to cognitive needs
- No high-stimulation content in the evening (sundowning prevention)
- Music content prioritized for Alzheimer's care (music memory preserved longest)
- Structured content for dementia care (game shows, sports, procedurals)
- Shower reminders that block the TV — because that's what it takes
- Family stays connected through messages, photos, and video
- Doorbell alerts keep them aware of visitors

**Built with love for seniors everywhere.**
