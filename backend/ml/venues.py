"""Host-venue geography + June climatology for the 2026 World Cup.

Provides coordinates, altitude, and typical tournament-window weather for each
host city, plus a great-circle distance helper used to estimate team travel
fatigue between fixtures.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

# city -> (lat, lon, altitude_m, june_temp_c, june_humidity_pct)
VENUES: dict[str, tuple[float, float, int, float, int]] = {
    "New York/NJ":   (40.81, -74.07,   5, 25, 65),
    "Los Angeles":   (33.95, -118.34, 30, 24, 60),
    "Dallas":        (32.75, -97.09,  180, 33, 62),
    "Atlanta":       (33.76, -84.40,  320, 30, 68),
    "Houston":       (29.68, -95.41,   15, 33, 74),
    "Kansas City":   (39.05, -94.48,  270, 30, 64),
    "Philadelphia":  (39.90, -75.17,   12, 28, 66),
    "San Francisco": (37.40, -121.97, 10, 21, 60),
    "Seattle":       (47.60, -122.33, 45, 22, 62),
    "Miami":         (25.96, -80.24,    2, 31, 76),
    "Boston":        (42.09, -71.26,   45, 24, 64),
    "Mexico City":   (19.30, -99.15, 2240, 23, 55),   # altitude factor
    "Toronto":       (43.63, -79.42,   76, 23, 63),
    "Vancouver":     (49.28, -123.11,   5, 20, 64),
    "Guadalajara":   (20.68, -103.46, 1566, 24, 52),  # altitude factor
    "Monterrey":     (25.67, -100.24, 540, 32, 60),
}


def haversine_km(a: str, b: str) -> float:
    """Great-circle distance between two host cities (km). 0 if unknown."""
    if a == b or a not in VENUES or b not in VENUES:
        return 0.0
    lat1, lon1 = VENUES[a][0], VENUES[a][1]
    lat2, lon2 = VENUES[b][0], VENUES[b][1]
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    h = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * 6371.0 * asin(sqrt(h)), 1)


def climate(city: str) -> dict:
    if city not in VENUES:
        return {"temp_c": 24, "humidity": 60, "altitude_m": 50}
    _, _, alt, temp, hum = VENUES[city]
    return {"temp_c": temp, "humidity": hum, "altitude_m": alt}
