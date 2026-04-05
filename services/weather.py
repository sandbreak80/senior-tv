"""Weather data from Open-Meteo API for Senior TV."""

from datetime import datetime

import requests

import cache
from models import get_setting_or_default


_CODE_TEXT = {
    0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy",
    3: "Overcast", 45: "Foggy", 48: "Foggy",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    80: "Rain Showers", 81: "Rain Showers", 82: "Heavy Showers",
    95: "Thunderstorm",
}


def code_to_text(code):
    """Convert WMO weather code to text description."""
    return _CODE_TEXT.get(code, "Unknown")


def code_to_icon(code):
    """Convert WMO weather code to emoji icon."""
    if code <= 1:
        return "\u2600\ufe0f"
    elif code <= 3:
        return "\u26c5"
    elif code <= 48:
        return "\U0001f32b\ufe0f"
    elif code <= 55:
        return "\U0001f326\ufe0f"
    elif code <= 65:
        return "\U0001f327\ufe0f"
    elif code <= 75:
        return "\u2744\ufe0f"
    elif code <= 82:
        return "\U0001f327\ufe0f"
    elif code >= 95:
        return "\u26c8\ufe0f"
    return "\U0001f321\ufe0f"


def _get_weather_params():
    """Get lat/lon/unit settings for API calls."""
    lat = get_setting_or_default("weather_lat")
    lon = get_setting_or_default("weather_lon")
    unit = get_setting_or_default("weather_unit")
    temp_unit = "fahrenheit" if unit == "fahrenheit" else "celsius"
    symbol = "\u00b0F" if unit == "fahrenheit" else "\u00b0C"
    return lat, lon, temp_unit, symbol


def get_summary():
    """Current temperature + condition. Cached 10 min."""
    cached = cache.get("weather_summary")
    if cached:
        return cached
    try:
        lat, lon, temp_unit, symbol = _get_weather_params()
        if not lat or not lon:
            return {
                "temp": "--",
                "condition": "Not configured",
                "code": 0,
            }
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code",
                "temperature_unit": temp_unit,
            },
            timeout=5,
        )
        data = resp.json()
        current = data["current"]
        temp = round(current["temperature_2m"])
        code = current["weather_code"]
        result = {
            "temp": f"{temp}{symbol}",
            "condition": code_to_text(code),
            "code": code,
        }
        cache.set("weather_summary", result, ttl=600)
        return result
    except Exception:
        return {"temp": "--", "condition": "Unavailable", "code": -1}


def get_forecast(days=5):
    """N-day forecast. Cached 30 min."""
    cached = cache.get("forecast_5day")
    if cached:
        return cached
    try:
        lat, lon, temp_unit, _ = _get_weather_params()
        if not lat or not lon:
            return []
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min"
                ),
                "temperature_unit": temp_unit,
                "timezone": "auto",
                "forecast_days": days,
            },
            timeout=5,
        )
        data = resp.json()
        forecast = []
        for i in range(days):
            day_name = datetime.strptime(
                data["daily"]["time"][i], "%Y-%m-%d"
            ).strftime("%a")
            if i == 0:
                day_name = "Today"
            forecast.append({
                "day": day_name,
                "high": round(data["daily"]["temperature_2m_max"][i]),
                "low": round(data["daily"]["temperature_2m_min"][i]),
                "icon": code_to_icon(
                    data["daily"]["weather_code"][i]
                ),
            })
        cache.set("forecast_5day", forecast, ttl=1800)
        return forecast
    except Exception:
        return []


def get_detailed():
    """Full weather for the weather page (current + forecast).
    Returns (current_dict, forecast_list)."""
    try:
        lat, lon, temp_unit, symbol = _get_weather_params()
        if not lat or not lon:
            return None, []
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": (
                    "temperature_2m,weather_code,"
                    "relative_humidity_2m,wind_speed_10m"
                ),
                "daily": (
                    "weather_code,"
                    "temperature_2m_max,"
                    "temperature_2m_min"
                ),
                "temperature_unit": temp_unit,
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 5,
            },
            timeout=10,
        )
        data = resp.json()
        c = data["current"]
        current = {
            "temp": round(c["temperature_2m"]),
            "condition": code_to_text(c["weather_code"]),
            "icon": code_to_icon(c["weather_code"]),
            "humidity": c["relative_humidity_2m"],
            "wind": round(c["wind_speed_10m"]),
            "symbol": symbol,
        }
        forecast = []
        for i in range(5):
            day_name = datetime.strptime(
                data["daily"]["time"][i], "%Y-%m-%d"
            ).strftime("%A")
            if i == 0:
                day_name = "Today"
            wc = data["daily"]["weather_code"][i]
            forecast.append({
                "day": day_name,
                "high": round(data["daily"]["temperature_2m_max"][i]),
                "low": round(data["daily"]["temperature_2m_min"][i]),
                "icon": code_to_icon(wc),
                "condition": code_to_text(wc),
                "symbol": symbol,
            })
        return current, forecast
    except Exception:
        return None, []
