"""Strukturált API-k és cikkolvasó közös vezérlője."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from .models import ContentBlock, ReaderContent, ResearchError, ResearchProgress, ResearchQuery, ResearchResult
from .network import FetchError, HttpClient
from .reader import extract_article


class ResearchService:
    def __init__(self, http=None):
        self.http = http or HttpClient()

    def run(self, query: ResearchQuery, *, progress=None, cancelled=None) -> ResearchResult:
        def emit(phase, message):
            if progress:
                progress(ResearchProgress(query.request_id, phase, message))

        try:
            emit("validating", "Lekérdezés előkészítése…")
            value = query.input.strip()
            if not value:
                raise FetchError("invalid_input", "Írj be keresőszót vagy webcímet.")
            if cancelled and cancelled():
                return ResearchResult(query.request_id, query.kind, "cancelled")
            emit("fetching", "Lekérdezés folyamatban…")
            handlers = {
                "wikipedia_search": self._wikipedia,
                "article_url": self._article,
                "weather": self._weather,
                "exchange_rate": self._rate,
                "dictionary": self._dictionary,
            }
            if query.kind not in handlers:
                raise FetchError("invalid_input", "Ismeretlen kutatási mód.")
            content, name, source, warnings = handlers[query.kind](value, query, emit)
            if cancelled and cancelled():
                return ResearchResult(query.request_id, query.kind, "cancelled")
            emit("rendering", "Tartalom megjelenítése…")
            return ResearchResult(query.request_id, query.kind, "success",
                                  content.title, content, name, source,
                                  datetime.now(timezone.utc), warnings=warnings)
        except FetchError as error:
            status = "empty" if error.code == "no_content" else "error"
            return ResearchResult(query.request_id, query.kind, status,
                                  error=ResearchError(error.code, str(error), error.retryable))
        except (TypeError, ValueError, KeyError, AttributeError):
            return ResearchResult(query.request_id, query.kind, "error",
                                  error=ResearchError("invalid_response", "A forrás hibás vagy hiányos adatot küldött."))

    def _wikipedia(self, value, query, emit):
        language = query.language.lower().split("-")[0]
        if language not in ("hu", "en"):
            language = "hu"
        base = f"https://{language}.wikipedia.org"
        search = base + "/w/rest.php/v1/search/page?" + urlencode({"q": value, "limit": 3})
        data, _ = self.http.json(search)
        pages = data.get("pages", []) if isinstance(data, dict) else []
        if not pages:
            raise FetchError("no_content", "Nem találtunk Wikipédia-cikket erre a keresésre.")
        title = pages[0].get("title")
        if not isinstance(title, str) or not title:
            raise FetchError("invalid_response", "A Wikipédia hibás találati adatot küldött.")
        emit("extracting", "Wikipédia-összefoglaló feldolgozása…")
        summary_url = base + "/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"), safe="")
        summary, _ = self.http.json(summary_url)
        if not isinstance(summary, dict) or not isinstance(summary.get("extract"), str) or not summary["extract"].strip():
            raise FetchError("no_content", "Ehhez a Wikipédia-találathoz nincs olvasható összefoglaló.")
        canonical = summary.get("content_urls", {}).get("desktop", {}).get("page") or base + "/wiki/" + quote(title.replace(" ", "_"))
        text = summary["extract"].strip()
        content = ReaderContent(summary.get("title") or title,
                                (ContentBlock("paragraph", text),), canonical_url=canonical)
        warnings = ("A legelső találat összefoglalója; ellenőrizd a címet.",) if len(pages) > 1 else ()
        return content, "Wikipédia", canonical, warnings

    def _article(self, value, query, emit):
        html, final = self.http.html(value)
        emit("extracting", "Cikk tartalmának feldolgozása…")
        content = extract_article(html, final)
        return content, "Cikkoldal", final, ()

    def _weather(self, value, query, emit):
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode(
            {"name": value, "count": 1, "language": "hu", "format": "json"})
        geo, _ = self.http.json(geo_url)
        places = geo.get("results", []) if isinstance(geo, dict) else []
        if not places:
            raise FetchError("no_content", "Nem található ilyen település.")
        place = places[0]
        try:
            lat, lon = float(place["latitude"]), float(place["longitude"])
            name = str(place["name"])
        except (KeyError, ValueError, TypeError):
            raise FetchError("invalid_response", "A helyadat hiányos.") from None
        url = "https://api.open-meteo.com/v1/forecast?" + urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "timezone": "auto"})
        data, _ = self.http.json(url)
        current = data.get("current", {}) if isinstance(data, dict) else {}
        units = data.get("current_units", {}) if isinstance(data, dict) else {}
        if "temperature_2m" not in current:
            raise FetchError("invalid_response", "Az időjárás-forrás nem adott aktuális adatot.")
        lines = []
        for key, label in (("temperature_2m", "Hőmérséklet"),
                           ("apparent_temperature", "Hőérzet"),
                           ("relative_humidity_2m", "Páratartalom"),
                           ("precipitation", "Csapadék"),
                           ("wind_speed_10m", "Szélsebesség")):
            if current.get(key) is not None:
                lines.append(ContentBlock("paragraph", f"{label}: {current[key]} {units.get(key, '')}".strip()))
        title = f"Aktuális időjárás: {name}, {place.get('country', '')}".rstrip(", ")
        content = ReaderContent(title, tuple(lines), canonical_url=url)
        return content, "Open-Meteo", url, ()

    def _rate(self, value, query, emit):
        parts = value.upper().replace("/", " ").split()
        if len(parts) != 2 or not all(re.fullmatch(r"[A-Z]{3}", p) for p in parts):
            raise FetchError("invalid_input", "Két hárombetűs pénznemet írj be, például EUR HUF.")
        base, target = parts
        if base == target:
            raise FetchError("invalid_input", "Két különböző pénznemet adj meg.")
        url = "https://api.frankfurter.dev/v1/latest?" + urlencode({"base": base, "symbols": target})
        data, _ = self.http.json(url)
        rates = data.get("rates", {}) if isinstance(data, dict) else {}
        rate = rates.get(target)
        if not isinstance(rate, (int, float)) or rate <= 0:
            raise FetchError("no_content", "Ehhez a pénznempárhoz nincs árfolyam.")
        date = str(data.get("date", ""))
        title = f"Árfolyam: 1 {base} = {rate:g} {target}"
        content = ReaderContent(title, (ContentBlock("paragraph", f"Forrás szerinti árfolyamnap: {date}."),), canonical_url=url)
        return content, "Frankfurter", url, ("Tájékoztató, nem valós idejű banki árfolyam.",)

    def _dictionary(self, value, query, emit):
        # Az ingyenes szolgáltató az angol szavakat fedi le; ezt a UI kimondja.
        if len(value) > 80 or any(c in value for c in "/?#"):
            raise FetchError("invalid_input", "Egy angol szót adj meg.")
        url = "https://api.dictionaryapi.dev/api/v2/entries/en/" + quote(value)
        data, _ = self.http.json(url)
        if not isinstance(data, list) or not data:
            raise FetchError("no_content", "Nem található angol szótári címszó.")
        entry = data[0]
        title = str(entry.get("word") or value)
        blocks = []
        origin = entry.get("origin")
        if origin:
            blocks.append(ContentBlock("paragraph", "Etimológia: " + str(origin)))
        for meaning in entry.get("meanings", [])[:8]:
            part = meaning.get("partOfSpeech")
            if part:
                blocks.append(ContentBlock("heading", str(part), level=2))
            for definition in meaning.get("definitions", [])[:8]:
                text = definition.get("definition")
                if text:
                    blocks.append(ContentBlock("paragraph", str(text)))
        if not blocks:
            raise FetchError("no_content", "Ehhez a szóhoz nincs meghatározás.")
        content = ReaderContent(title, tuple(blocks), canonical_url=url)
        return content, "Free Dictionary API", url, ("A szótár jelenleg angol nyelvű.",)
