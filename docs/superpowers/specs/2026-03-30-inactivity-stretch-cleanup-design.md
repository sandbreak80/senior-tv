# Design: Inactivity Alert, Stretch Break Config, Import Cleanup

**Date:** 2026-03-30
**Scope:** Three small roadmap items — all isolated, no architectural changes.

---

## 1. Inactivity Health Check

**Goal:** Flag in `/api/health` when the TV has had no activity for 4+ hours during daytime.

**How it works:**
- Add an `"inactivity"` entry to the `checks` dict in `api_health()` (server.py ~line 2216)
- Call `models.get_last_activity_time()` (already exists) to get the most recent activity timestamp
- If last activity was 4+ hours ago AND current time is between 8 AM and 10 PM, set `"ok": false`
- Include `hours_idle` (float, rounded to 1 decimal) and `last_activity` (ISO timestamp) in the response
- The threshold is read from settings via `get_setting_or_default("inactivity_alert_hours", "4")`
- Add `"inactivity_alert_hours": "4"` default to `config.py`

**Response shape:**
```json
"inactivity": {
    "ok": true,
    "hours_idle": 1.3,
    "last_activity": "2026-03-30T09:15:00",
    "threshold_hours": 4
}
```

**Edge cases:**
- No activity records at all: report `"ok": false` with `hours_idle: null` and `last_activity: null`
- Outside daytime window (before 8 AM or after 10 PM): always report `"ok": true`

**Files changed:** `server.py` (health endpoint), `config.py` (default)

---

## 2. Stretch Break Admin Settings

**Goal:** Expose stretch break configuration in admin settings instead of requiring manual pill creation.

**Settings keys and defaults (added to `config.py`):**
- `stretch_enabled` — `"1"` (enabled by default)
- `stretch_times` — `"09:00,13:00,17:00,21:00"`
- `stretch_duration` — `"15"` (minutes)

**Admin UI (templates/admin/settings.html):**
Add a "Stretch Breaks" section following the classical music pattern:
- Toggle: enable/disable
- Text input: comma-separated times (e.g., `09:00,13:00,17:00,21:00`)
- Number input: block duration in minutes
- Hint text explaining the feature

**Backend sync logic (server.py, settings POST handler):**
On settings save:
1. Read `stretch_enabled`, `stretch_times`, `stretch_duration` from form
2. Save to settings DB
3. Find existing pill where name is "Stretch Break" (case-insensitive)
4. If enabled and no pill exists: create one with name "Stretch Break", schedule_times from the times setting, all 7 days, enabled=1
5. If enabled and pill exists: update its schedule_times and enabled=1
6. If disabled and pill exists: set enabled=0
7. The scheduler already handles stretch breaks by name detection — no scheduler changes needed

**Files changed:** `config.py` (defaults), `server.py` (settings save handler), `templates/admin/settings.html` (UI section)

---

## 3. Random Import Cleanup

**Goal:** Fix lint warning about `import random` placement.

**Current state (server.py ~line 2175):**
```python
if events:
    import random              # inside conditional
    event = random.choice(events[:10])
```

**Fix:** Move `import random` to the top of the `api_daily_digest()` function, consistent with how other functions in the file handle local imports (e.g., `import random as _random` in `trigger_classical_music()`).

**Files changed:** `server.py` (one import moved)

---

## Files Changed Summary

| File | Changes |
|------|---------|
| `server.py` | Inactivity check in health endpoint, stretch break sync in settings handler, random import move |
| `config.py` | 4 new defaults: `inactivity_alert_hours`, `stretch_enabled`, `stretch_times`, `stretch_duration` |
| `templates/admin/settings.html` | New "Stretch Breaks" section |

## Testing

- Verify `/api/health` includes `inactivity` check with correct ok/idle values
- Verify stretch break settings appear in admin, save correctly, and create/update/disable the pill
- Verify no lint warnings on the random import
