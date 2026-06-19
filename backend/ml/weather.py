"""Match-day weather + a 'conditions severity' score.

Harsh heat/humidity/altitude compresses play and levels the field (more upset
risk). This module derives a 0..1 severity per venue from June climatology, and
can refresh from Open-Meteo (free, no API key) when the match is inside the
forecast window. Severity feeds a transparent conditions adjustment in the
ensemble and a plain-language note.
"""
from __future__ import annotations

import json
from functools import lru_cache

from config import RAW
from venues import VENUES, climate

WEATHER_CACHE = RAW / "weather.json"


def severity(temp_c: float, humidity: float, altitude_m: float) -> float:
    """0 (benign) .. 1 (extreme). Heat+humidity and/or altitude."""
    sev_heat = max(0.0, (temp_c - 24) / 14.0) * (0.7 + 0.3 * humidity / 100)
    sev_alt = max(0.0, (altitude_m - 1000) / 2000.0)
    return round(min(1.0, 0.8 * sev_heat + 0.6 * sev_alt), 3)


def _summary(temp_c, humidity, altitude_m, sev) -> str:
    bits = []
    if altitude_m >= 1500:
        bits.append(f"high altitude ({altitude_m} m)")
    if temp_c >= 30:
        bits.append(f"hot {round(temp_c)}°C")
    if humidity >= 70:
        bits.append("humid")
    if not bits:
        return f"mild {round(temp_c)}°C"
    tag = "extreme" if sev >= 0.55 else "demanding" if sev >= 0.3 else "notable"
    return f"{tag} conditions — " + ", ".join(bits)


@lru_cache
def _overrides() -> dict:
    if WEATHER_CACHE.exists():
        return json.loads(WEATHER_CACHE.read_text())
    return {}


def reload_cache():
    _overrides.cache_clear()


def conditions(city: str, date_iso: str = "") -> dict:
    """Weather + severity for a venue. Uses live cache override if present."""
    key = f"{city}|{date_iso[:10]}"
    ov = _overrides().get(key) or _overrides().get(city)
    base = climate(city)
    temp = (ov or {}).get("temp_c", base["temp_c"])
    hum = (ov or {}).get("humidity", base["humidity"])
    alt = base["altitude_m"]
    sev = severity(temp, hum, alt)
    return {"temp_c": temp, "humidity": hum, "altitude_m": alt,
            "severity": sev, "summary": _summary(temp, hum, alt, sev),
            "source": "live" if ov else "climatology"}


def fetch_open_meteo(city: str, date_iso: str) -> dict | None:
    """Live forecast (no key). Returns None if outside window / offline."""
    if city not in VENUES:
        return None
    lat, lon = VENUES[city][0], VENUES[city][1]
    try:
        import requests
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=20,
                         params={"latitude": lat, "longitude": lon,
                                 "daily": "temperature_2m_max,relative_humidity_2m_mean",
                                 "start_date": date_iso[:10], "end_date": date_iso[:10]})
        r.raise_for_status()
        d = r.json().get("daily", {})
        if not d.get("temperature_2m_max"):
            return None
        rec = {"temp_c": d["temperature_2m_max"][0],
               "humidity": d.get("relative_humidity_2m_mean", [None])[0] or 60}
        cache = _overrides()
        cache[f"{city}|{date_iso[:10]}"] = rec
        WEATHER_CACHE.write_text(json.dumps(cache, indent=2))
        reload_cache()
        return rec
    except Exception:
        return None
