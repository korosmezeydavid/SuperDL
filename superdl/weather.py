"""Aktuális időjárás az Open-Meteo ingyenes, KULCS NÉLKÜLI API-járól.

Két lépés: a város nevét a geokódoló végpont koordinátává alakítja, majd a
forecast végpont adja az aktuális hőmérsékletet és az időjárás-kódot. A WMO
időjárás-kódot magyar leírássá fordítjuk.

Hálózat kell hozzá; hiba esetén kivételt dob, amit a hívó elnyel (offline
módban a napi infó időjárás nélkül is összeáll).
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
UA = {"User-Agent": "SuperDL-weather"}

# WMO időjárás-kódok magyar leírása
WEATHER_CODES = {
    0: "tiszta, derült idő", 1: "többnyire tiszta", 2: "közepesen felhős",
    3: "borult", 45: "ködös", 48: "zúzmarás köd",
    51: "gyenge szitálás", 53: "szitálás", 55: "erős szitálás",
    56: "fagyos szitálás", 57: "erős fagyos szitálás",
    61: "gyenge eső", 63: "eső", 65: "erős eső",
    66: "fagyos eső", 67: "erős fagyos eső",
    71: "gyenge havazás", 73: "havazás", 75: "erős havazás",
    77: "hószállingózás",
    80: "gyenge zápor", 81: "zápor", 82: "heves zápor",
    85: "gyenge hózápor", 86: "erős hózápor",
    95: "zivatar", 96: "zivatar jégesővel", 99: "erős zivatar jégesővel",
}


@dataclass
class Weather:
    city: str
    temp_c: float
    description: str
    wind_kmh: float = 0.0

    def sentence(self) -> str:
        """Felolvasható magyar mondat (ragozás nélkül, helyesen olvastatható)."""
        t = round(self.temp_c)
        return f"{self.city} időjárása: {t} fok, {self.description}"


def _get_json(url: str, params: dict):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def geocode(city: str) -> tuple[float, float, str]:
    """A város neve → (szélesség, hosszúság, hivatalos név). Hiba, ha nincs."""
    data = _get_json(GEO_URL, {"name": city.strip(), "count": 1,
                               "language": "hu", "format": "json"})
    results = data.get("results") or []
    if not results:
        raise ValueError(f"nem található ilyen város: {city}")
    r = results[0]
    return float(r["latitude"]), float(r["longitude"]), r.get("name", city)


def current(city: str) -> Weather:
    """Az adott város aktuális időjárása. Hálózat/keresési hiba esetén kivétel."""
    lat, lon, name = geocode(city)
    data = _get_json(FORECAST_URL, {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "timezone": "auto"})
    cur = data.get("current") or {}
    code = int(cur.get("weather_code", -1))
    return Weather(
        city=name,
        temp_c=float(cur.get("temperature_2m", 0.0)),
        description=WEATHER_CODES.get(code, "ismeretlen időjárás"),
        wind_kmh=float(cur.get("wind_speed_10m", 0.0)))
