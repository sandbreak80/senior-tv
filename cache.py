"""Simple in-memory cache with TTL and circuit breakers for Senior TV.
Prevents repeated API calls to Pluto TV, weather, YouTube, etc.
Circuit breakers prevent hammering down services with requests that will timeout."""

import time
import threading

_cache = {}
_lock = threading.Lock()

# Circuit breaker state: {service_name: {"failures": int, "open_until": float}}
_breakers = {}
_breaker_lock = threading.Lock()

# Circuit breaker defaults
BREAKER_FAILURE_THRESHOLD = 3   # consecutive failures before opening
BREAKER_RECOVERY_SECONDS = 120  # how long to stay open (2 minutes)


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
    """Record a successful call — resets the circuit breaker."""
    with _breaker_lock:
        _breakers.pop(service, None)


def record_failure(service):
    """Record a failed call. Opens breaker after threshold."""
    with _breaker_lock:
        state = _breakers.get(
            service, {"failures": 0, "open_until": 0}
        )
        state["failures"] += 1
        if state["failures"] >= BREAKER_FAILURE_THRESHOLD:
            state["open_until"] = (
                time.time() + BREAKER_RECOVERY_SECONDS
            )
        _breakers[service] = state


def breaker_status():
    """Return circuit breaker status for all services."""
    with _breaker_lock:
        now = time.time()
        result = {}
        for svc, s in _breakers.items():
            is_open = (
                s["failures"] >= BREAKER_FAILURE_THRESHOLD
                and now < s["open_until"]
            )
            recover = 0
            if s["failures"] >= BREAKER_FAILURE_THRESHOLD:
                recover = max(0, int(s["open_until"] - now))
            result[svc] = {
                "failures": s["failures"],
                "open": is_open,
                "recovers_in": recover,
            }
        return result
