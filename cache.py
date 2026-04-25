"""Simple in-memory cache with TTL and circuit breakers for Senior TV.
Prevents repeated API calls to Pluto TV, weather, YouTube, etc.
Circuit breakers prevent hammering down services with requests that will timeout.
Throttled logging collapses duplicate errors so one broken service can't flood the journal."""

import sys
import time
import threading

_cache = {}
_lock = threading.Lock()

# Circuit breaker state per service:
#   {"failures", "open_until", "last_failure_at", "last_success_at", "last_error"}
_breakers = {}
_breaker_lock = threading.Lock()

# Throttled log state: {key: {"last_emit": float, "count": int, "last_msg": str}}
_log_state = {}
_log_lock = threading.Lock()

# Circuit breaker defaults
BREAKER_FAILURE_THRESHOLD = 3  # consecutive failures before opening
BREAKER_RECOVERY_SECONDS = 120  # how long to stay open (2 minutes)

# Default window for throttled log suppression
LOG_THROTTLE_WINDOW_SECONDS = 300  # 5 minutes


def get(key):
    """Get a cached value. Returns None if expired or missing."""
    with _lock:
        entry = _cache.get(key)
        if entry:
            if time.time() < entry["expires"]:
                return entry["value"]
            del _cache[key]
    return None


def set(key, value, ttl=300):
    """Cache a value with TTL in seconds. Default 5 minutes."""
    with _lock:
        _cache[key] = {"value": value, "expires": time.time() + ttl}


def clear(key=None):
    """Clear one key or all."""
    with _lock:
        if key:
            _cache.pop(key, None)
        else:
            _cache.clear()


def cleanup():
    """Remove all expired entries. Called periodically to prevent unbounded growth."""
    now = time.time()
    with _lock:
        expired = [k for k, v in _cache.items() if now >= v["expires"]]
        for k in expired:
            del _cache[k]
    return len(expired)


# --- Circuit Breaker ---


def is_circuit_open(service):
    """Check if a service's circuit breaker is open (should skip calls).
    Returns True if the service has failed too many times recently."""
    with _breaker_lock:
        state = _breakers.get(service)
        if not state:
            return False
        if state["failures"] >= BREAKER_FAILURE_THRESHOLD:
            if time.time() < state["open_until"]:
                return True
            # Recovery period elapsed — allow a probe request
            state["failures"] = BREAKER_FAILURE_THRESHOLD - 1
        return False


def record_success(service):
    """Record a successful call. Closes the breaker and stamps last_success_at.

    Keeps the entry around (with zero failures) so breaker_status / health checks
    can report the last known good time for each service.
    """
    now = time.time()
    with _breaker_lock:
        state = _breakers.get(service) or {}
        was_open = (
            state.get("failures", 0) >= BREAKER_FAILURE_THRESHOLD
            and now < state.get("open_until", 0)
        )
        state.update({
            "failures": 0,
            "open_until": 0,
            "last_success_at": now,
            "last_error": None,
        })
        _breakers[service] = state
    if was_open:
        _emit(f"breaker:{service}:recovered",
              f"[breaker] {service} recovered")


def record_failure(service, error=None):
    """Record a failed call. Opens breaker after threshold.

    `error` is an optional short string describing the failure; stored for
    health reporting. The message is NOT logged from here — callers should use
    log_throttled(key, message) so the suppression key is under their control.
    """
    now = time.time()
    with _breaker_lock:
        state = _breakers.get(
            service,
            {"failures": 0, "open_until": 0,
             "last_success_at": None, "last_error": None},
        )
        state["failures"] = state.get("failures", 0) + 1
        state["last_failure_at"] = now
        if error is not None:
            state["last_error"] = str(error)[:200]
        if state["failures"] >= BREAKER_FAILURE_THRESHOLD:
            state["open_until"] = now + BREAKER_RECOVERY_SECONDS
        _breakers[service] = state


def breaker_status():
    """Return circuit breaker status for all services.

    Shape per service:
      {failures, open, recovers_in, last_failure_at, last_success_at, last_error}
    """
    with _breaker_lock:
        now = time.time()
        result = {}
        for svc, s in _breakers.items():
            is_open = (
                s.get("failures", 0) >= BREAKER_FAILURE_THRESHOLD
                and now < s.get("open_until", 0)
            )
            recover = 0
            if s.get("failures", 0) >= BREAKER_FAILURE_THRESHOLD:
                recover = max(0, int(s.get("open_until", 0) - now))
            result[svc] = {
                "failures": s.get("failures", 0),
                "open": is_open,
                "recovers_in": recover,
                "last_failure_at": s.get("last_failure_at"),
                "last_success_at": s.get("last_success_at"),
                "last_error": s.get("last_error"),
            }
        return result


# --- Throttled logging ---


def _emit(key, message, file=None):
    """Internal: write a line now and reset the throttle counter for key."""
    if file is None:
        file = sys.stderr
    with _log_lock:
        state = _log_state.get(key) or {}
        suppressed = state.get("count", 0)
        state["last_emit"] = time.time()
        state["count"] = 0
        state["last_msg"] = message
        _log_state[key] = state
    if suppressed > 0:
        print(f"{message} [suppressed {suppressed} prior]", file=file)
    else:
        print(message, file=file)


def log_throttled(key, message, file=None, window=LOG_THROTTLE_WINDOW_SECONDS):
    """Print `message` at most once per `window` seconds per `key`.

    Additional calls within the window bump a suppressed counter. When the
    window elapses and the next call fires, the emitted line is suffixed with
    "[suppressed N prior]" so the reader knows how many were collapsed.

    Use one distinct key per failure *class*, not per message text — e.g.
    "frigate:events" not the exception string itself. Keeping the key stable
    is what lets suppression actually collapse bursts.
    """
    now = time.time()
    with _log_lock:
        state = _log_state.get(key)
        if state is None:
            state = {"last_emit": 0.0, "count": 0, "last_msg": message}
            _log_state[key] = state
        elapsed = now - state["last_emit"]
        if elapsed < window:
            state["count"] += 1
            state["last_msg"] = message
            return
    _emit(key, message, file=file)


def log_recovery(key, message, file=None):
    """Force-emit a recovery/state-change message and reset the throttle.

    Use this to announce "service X is back" — it bypasses the window so the
    good news lands immediately, and clears the suppressed counter.
    """
    _emit(key, message, file=file)
