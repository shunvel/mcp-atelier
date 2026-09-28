"""Weather lookup tools using Open-Meteo (no API key required)."""

from __future__ import annotations

import json

import httpx

# Curated city coordinates for demos
CITY_COORDS: dict[str, tuple[float, float]] = {
    "bangalore": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "chennai": (13.0827, 80.2707),
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "tokyo": (35.6762, 139.6503),
    "paris": (48.8566, 2.3522),
    "sydney": (-33.8688, 151.2093),
}


def _resolve_coords(city: str) -> tuple[float, float] | None:
    key = city.strip().lower()
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    return None


def get_weather(city: str) -> str:
    """Get current weather for a city using Open-Meteo API.

    Args:
        city: City name (e.g. Bangalore, Mumbai, London).
    """
    coords = _resolve_coords(city)
    if coords is None:
        available = ", ".join(sorted(CITY_COORDS.keys()))
        return json.dumps(
            {
                "error": f"City '{city}' not in curated list.",
                "available_cities": available,
                "hint": "Use one of the available cities or check weather://cities resource.",
            },
            indent=2,
        )

    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&timezone=auto"
    )

    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        return json.dumps(
            {
                "city": city.title(),
                "latitude": lat,
                "longitude": lon,
                "temperature_c": current.get("temperature_2m"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code"),
                "time": current.get("time"),
            },
            indent=2,
        )
    except httpx.HTTPError as exc:
        return json.dumps({"error": f"Weather API request failed: {exc}"})
