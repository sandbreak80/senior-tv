# Contributing to Senior TV

Thanks for your interest in making Senior TV better. This project helps real people — every improvement matters.

## Getting Started

1. Fork the repo and clone locally
2. `cp .env.example .env` and edit with your details
3. `python3 -m venv venv && source venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python3 server.py` — opens at http://localhost:5000

You don't need Docker, Jellyfin, or Immich for basic development. The system degrades gracefully — everything optional stays optional.

## Design Principles

These aren't suggestions. They're hard constraints driven by the users.

1. **6-button navigation only** — Arrow keys, Enter, Escape. No mouse, no touch, no scroll wheel. Everything must be reachable with these 6 inputs.

2. **36px minimum text** — Readable from a couch 8 feet away on a 65" TV. When in doubt, make it bigger.

3. **No cognitive load** — Don has mid-stage dementia. Colleen has advanced Alzheimer's. If a feature requires a decision, it should make that decision automatically.

4. **Dark theme, high contrast** — Light text on dark backgrounds. No thin fonts. No low-contrast decorative elements.

5. **Instant response** — `window.quickNav()` kills iframes/videos/images before navigating. Back button must feel instant. No loading spinners.

6. **Fail silently** — If Jellyfin is down, don't show an error. Show what's available. Never expose technical errors to the TV screen.

7. **No news after 3 PM** — Sundowning care. Wind-down content only in the evening. This is a medical consideration.

## What to Work On

### Good First Issues

- **Remove a hardcoded value** — Search for "Don", "Colleen", "Sun City", or hardcoded IPs. Make it configurable via the Settings admin page.
- **Improve an admin page** — Better mobile layout, clearer labels, inline help text.
- **Add a YouTube channel category** — Edit the seed data in `models.py`.
- **Improve test coverage** — `test_ui.py` has 93 tests but many features are untested.

### Bigger Projects

- **Profile system** — Replace hardcoded care rules with a profiles table. Different presets for dementia, Alzheimer's, independent seniors, children.
- **First-boot setup wizard** — Interactive browser-based setup on first run.
- **i18n** — Extract all UI strings for translation.
- **Voice control** — Add wake-word or push-to-talk integration.

## Code Style

- **Python:** Standard library + Flask. No ORMs. SQLite via `get_db_safe()` context manager. Type hints welcome but not required.
- **JavaScript:** Vanilla JS. No frameworks, no build step, no npm. ES5-compatible where possible (some templates still use `var`).
- **CSS:** Vanilla CSS. No preprocessors. TV styles in `tv.css`, admin styles in `admin.css`.
- **Templates:** Jinja2. TV templates are standalone HTML. Admin templates extend `admin/base.html`.

## Pull Request Process

1. Create a branch from `main`
2. Make your changes
3. Test locally (`python3 server.py` + manual testing)
4. Run `python3 test_ui.py` if you have Playwright installed
5. Open a PR with a clear description of what and why

## Testing

```bash
# Full test suite (requires Flask running at localhost:5000)
source venv/bin/activate
python3 test_ui.py

# Quick syntax check
python3 -m py_compile server.py
python3 -m py_compile models.py
```

## Database

Always use `get_db_safe()` from `models.py`:

```python
with get_db_safe() as db:
    db.execute(query, (param,))
    db.commit()
```

When adding new settings, add a default in `config.py` DEFAULTS dict and access via `get_setting_or_default()` in `server.py`.

## SSE Events

To add a new real-time event type:

1. Push event via `reminder_queue.put_nowait({"type": "your_type", ...})`
2. Handle in `initSSE()` in `static/js/tv.js`
3. Build display function in tv.js
4. Log the event via `window.logActivity()`

## Questions?

Open an issue. We're happy to help.
