"""Programajánló: ellenőrizhető, dátumos eseményadatok két szolgáltatótól.

A Jegy.hu helyszínoldalainak Schema.org/Event adatait és a Budapest Park
nyilvános naptáradatait olvassuk. Jegyet nem vásárolunk.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from superdl import urlpolicy


BUDAPEST = ZoneInfo("Europe/Budapest")


@dataclass(frozen=True)
class ProgramForras:
    nev: str
    varos: str
    url: str
    mufaj: str
    fajta: str = "jegy"
    kod: str = ""


# Két város, két szolgáltató. A források neve nem jelent teljes országos lefedettséget.
ELSO_FORRASOK = (
    ProgramForras("Müpa", "Budapest",
                  "https://www.jegy.hu/venue/mupa", "Kulturális program"),
    ProgramForras("Móricz Zsigmond Színház", "Nyíregyháza",
                  "https://www.jegy.hu/venue/moricz-zsigmond-szinhaz", "Színház"),
    ProgramForras("Budapest Park", "Budapest",
                  "https://www.budapestpark.hu/", "Koncert és zene", "park"),
    ProgramForras("ARTMozi", "Budapest",
                  "https://artmozi.hu/api/schedule/week", "Mozi", "artmozi"),
    ProgramForras("Cinema City Arena", "Budapest",
                  "https://www.cinemacity.hu/cinemas/arena/1132", "Mozi", "cinemacity", "1132"),
    ProgramForras("Cinema City Nyíregyháza", "Nyíregyháza",
                  "https://www.cinemacity.hu/cinemas/nyiregyhaza/1143", "Mozi", "cinemacity", "1143"),
)


@dataclass(frozen=True)
class Program:
    cim: str
    kezdet: datetime
    varos: str
    helyszin: str
    mufaj: str
    forras: str
    url: str

    def felolvasas(self) -> str:
        ido = self.kezdet.strftime("%Y. %m. %d. %H:%M")
        return (f"{self.cim.rstrip(' .')}. {ido}. {self.varos}, "
                f"{self.helyszin.rstrip(' .')}. "
                f"{self.mufaj}. Forrás: {self.forras}.")


@dataclass(frozen=True)
class ProgramGyujtemeny:
    programok: tuple[Program, ...]
    hibak: tuple[tuple[str, str], ...]


class _JsonLd(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._inside = False
        self._pieces: list[str] = []
        self.documents: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self._inside = True
            self._pieces = []

    def handle_data(self, data):
        if self._inside:
            self._pieces.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._inside:
            self.documents.append("".join(self._pieces))
            self._inside = False


class _ParkNaptar(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.days: list[object] = []
        self.found = False

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "data-days":
                self.found = True
                try:
                    parsed = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(parsed, list):
                    self.days.extend(parsed)


def _szoveg(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _kezdet(value: object) -> datetime | None:
    if not isinstance(value, str) or "T" not in value and " " not in value:
        return None  # csak napot közlő adatot nem mondunk pontos előadásnak
    try:
        parsed = datetime.fromisoformat(value.replace(" ", "T", 1))
    except ValueError:
        return None
    return parsed.replace(tzinfo=BUDAPEST) if parsed.tzinfo is None else parsed.astimezone(BUDAPEST)


def feldolgoz_jegy_helyszin(html_szoveg: str, forras: ProgramForras,
                            most: datetime | None = None) -> list[Program]:
    """Csak jövőbeli, megnevezett és ellenőrizhető URL-ű eseményeket ad."""
    if urlsplit(forras.url).hostname not in ("jegy.hu", "www.jegy.hu"):
        raise ValueError("A forrás nem Jegy.hu helyszínoldal.")
    most = most or datetime.now(BUDAPEST)
    if most.tzinfo is None:
        raise ValueError("Az aktuális időnek időzónát kell tartalmaznia.")
    parser = _JsonLd()
    parser.feed(html_szoveg)
    if not parser.documents:
        raise ValueError("A helyszínoldalon nincs strukturált eseményadat.")
    programok: list[Program] = []
    latott: set[tuple[str, datetime]] = set()
    events_found = False
    for document in parser.documents:
        try:
            data = json.loads(document)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            places = [node] if node.get("@type") == "Place" else []
            if node.get("@type") == "Event":
                places = [{"event": [node]}]
            for place in places:
                events = place.get("event", [])
                if isinstance(events, dict):
                    events = [events]
                if not isinstance(events, list):
                    continue
                events_found = events_found or bool(events)
                for event in events:
                    if not isinstance(event, dict) or event.get("@type") != "Event":
                        continue
                    if "EventCancelled" in str(event.get("eventStatus", "")):
                        continue
                    kezdet = _kezdet(event.get("startDate"))
                    cim = _szoveg(event.get("name"))
                    url = str(event.get("url") or "").strip()
                    if not kezdet or kezdet < most or not cim:
                        continue
                    if urlsplit(url).hostname not in ("jegy.hu", "www.jegy.hu"):
                        continue
                    location = event.get("location") or {}
                    if not isinstance(location, dict):
                        continue
                    address = location.get("address") or {}
                    if not isinstance(address, dict):
                        continue
                    city = _szoveg(address.get("addressLocality"))
                    if city.casefold() != forras.varos.casefold():
                        continue
                    venue = _szoveg(location.get("name") or place.get("name") or forras.nev)
                    key = (url, kezdet)
                    if key in latott:
                        continue
                    latott.add(key)
                    programok.append(Program(cim, kezdet, city, venue,
                                              forras.mufaj, forras.nev, url))
    if not events_found:
        raise ValueError("A helyszínoldalon nincs eseménylista.")
    return sorted(programok, key=lambda p: (p.kezdet, p.cim))


def feldolgoz_park(html_szoveg: str, forras: ProgramForras,
                   most: datetime | None = None) -> list[Program]:
    """A Budapest Park naptárának beágyazott, nyilvános JSON-listája."""
    if urlsplit(forras.url).hostname not in ("budapestpark.hu", "www.budapestpark.hu"):
        raise ValueError("A forrás nem Budapest Park-oldal.")
    most = most or datetime.now(BUDAPEST)
    if most.tzinfo is None:
        raise ValueError("Az aktuális időnek időzónát kell tartalmaznia.")
    parser = _ParkNaptar()
    parser.feed(html_szoveg)
    if not parser.found or not parser.days:
        raise ValueError("A Budapest Park naptáradata nem érhető el.")
    out: list[Program] = []
    latott: set[tuple[str, datetime]] = set()
    for day in parser.days:
        if not isinstance(day, dict) or not isinstance(day.get("events"), list):
            continue
        try:
            nap = datetime.strptime(str(day["number"]), "%Y%m%d").date()
        except (KeyError, TypeError, ValueError):
            continue
        for event in day["events"]:
            if not isinstance(event, dict) or event.get("is_past") or event.get("is_cancelled"):
                continue
            ido = str(event.get("time") or "")
            try:
                parsed = datetime.strptime(ido, "%H:%M").time()
            except ValueError:
                continue
            kezdet = datetime.combine(nap, parsed, BUDAPEST)
            cim = _szoveg(event.get("title"))
            url = str(event.get("frontend_url") or "").strip()
            if not cim or kezdet < most or urlsplit(url).hostname not in (
                    "budapestpark.hu", "www.budapestpark.hu"):
                continue
            key = (url, kezdet)
            if key in latott:
                continue
            latott.add(key)
            out.append(Program(cim, kezdet, forras.varos, forras.nev,
                               forras.mufaj, forras.nev, url))
    return sorted(out, key=lambda p: (p.kezdet, p.cim))


def feldolgoz_artmozi(adat: dict, mozik: dict, forras: ProgramForras,
                      most: datetime | None = None) -> list[Program]:
    """Az ARTMozi heti JSON-műsorából egy vetítés = egy találat."""
    if urlsplit(forras.url).hostname not in ("artmozi.hu", "www.artmozi.hu"):
        raise ValueError("A forrás nem ARTMozi-oldal.")
    most = most or datetime.now(BUDAPEST)
    if most.tzinfo is None:
        raise ValueError("Az aktuális időnek időzónát kell tartalmaznia.")
    if not isinstance(adat, dict) or not isinstance(adat.get("movies"), dict) or not isinstance(adat.get("schedule"), dict):
        raise ValueError("Hiányos ARTMozi műsoradat.")
    out: list[Program] = []
    seen: set[tuple[str, datetime]] = set()
    for day, films in adat["schedule"].items():
        try:
            nap = datetime.strptime(day, "%Y%m%d").date()
        except (TypeError, ValueError):
            continue
        if not isinstance(films, dict):
            continue
        for film_id, times in films.items():
            film = adat["movies"].get(str(film_id))
            if not isinstance(film, dict) or not isinstance(times, dict):
                continue
            title = _szoveg(film.get("title"))
            if not title:
                continue
            for time_text, screenings in times.items():
                try:
                    clock = datetime.strptime(time_text, "%H:%M").time()
                except (TypeError, ValueError):
                    continue
                start = datetime.combine(nap, clock, BUDAPEST)
                if start < most or not isinstance(screenings, dict):
                    continue
                for screening in screenings.values():
                    if not isinstance(screening, dict):
                        continue
                    cinema = mozik.get(str(screening.get("cinema")))
                    if not isinstance(cinema, dict):
                        continue
                    cinema_name = _szoveg(cinema.get("name"))
                    room = _szoveg(screening.get("cinema_room"))
                    link = str(screening.get("link") or "")
                    host = urlsplit(link).hostname or ""
                    if not cinema_name or not (host == "bpfilm.hu" or host.endswith(".bpfilm.hu")):
                        continue
                    venue = cinema_name + (" – " + room if room else "")
                    key = (link, start)
                    if key not in seen:
                        seen.add(key)
                        out.append(Program(title, start, forras.varos, venue,
                                           forras.mufaj, forras.nev, link))
    return sorted(out, key=lambda p: (p.kezdet, p.cim, p.helyszin))


def lekerdez_artmozi(forras: ProgramForras,
                     most: datetime | None = None) -> list[Program]:
    """Csak a következő 30 nap heti adatait kérjük le a nyilvános API-ból."""
    most = most or datetime.now(BUDAPEST)
    if most.tzinfo is None:
        raise ValueError("Az aktuális időnek időzónát kell tartalmaznia.")
    base = forras.url.rstrip("/")
    index = json.loads(urlpolicy.safe_read_text(base, max_bytes=300_000, timeout=15))
    if not isinstance(index, dict) or not isinstance(index.get("weeks"), list) or not isinstance(index.get("cinemas"), dict):
        raise ValueError("Hiányos ARTMozi heti index.")
    out: list[Program] = []
    limit = most.date() + timedelta(days=29)
    for week in index["weeks"]:
        if not isinstance(week, int):
            continue
        try:
            monday = date.fromisocalendar(week // 100, week % 100, 1)
        except ValueError:
            continue
        if monday + timedelta(days=6) < most.date() or monday > limit:
            continue
        data = json.loads(urlpolicy.safe_read_text(
            f"{base}/{week}", max_bytes=2_000_000, timeout=15))
        out.extend(feldolgoz_artmozi(data, index["cinemas"], forras, most))
    return sorted(out, key=lambda p: (p.kezdet, p.cim, p.helyszin))


def feldolgoz_cinemacity(adat: dict, forras: ProgramForras,
                         most: datetime | None = None) -> list[Program]:
    """Cinema City nyilvános napi JSON-adatai: film és konkrét vetítés."""
    most = most or datetime.now(BUDAPEST)
    if most.tzinfo is None:
        raise ValueError("Az aktuális időnek időzónát kell tartalmaznia.")
    body = adat.get("body") if isinstance(adat, dict) else None
    if not isinstance(body, dict) or not isinstance(body.get("films"), list) or not isinstance(body.get("events"), list):
        raise ValueError("Hiányos Cinema City műsoradat.")
    films = {str(film.get("id")): film for film in body["films"] if isinstance(film, dict)}
    out: list[Program] = []
    seen: set[str] = set()
    for event in body["events"]:
        if not isinstance(event, dict) or str(event.get("cinemaId")) != forras.kod:
            continue
        film = films.get(str(event.get("filmId")))
        if not film:
            continue
        title = _szoveg(film.get("name"))
        start = _kezdet(event.get("eventDateTime"))
        event_id = str(event.get("id") or "")
        if not title or not start or start < most or not event_id or event_id in seen:
            continue
        link = str(event.get("bookingRouterLaunchLink") or "")
        if urlsplit(link).hostname not in ("cinemacity.hu", "www.cinemacity.hu"):
            continue
        room = _szoveg(event.get("auditorium"))
        venue = forras.nev + (" – " + room if room else "")
        seen.add(event_id)
        out.append(Program(title, start, forras.varos, venue,
                           forras.mufaj, forras.nev, link))
    return sorted(out, key=lambda p: (p.kezdet, p.cim))


def lekerdez_cinemacity(forras: ProgramForras,
                       most: datetime | None = None) -> list[Program]:
    """A közzétett napokat kérjük le; a lánc jellemzően csak egy hetet ad."""
    if urlsplit(forras.url).hostname not in ("cinemacity.hu", "www.cinemacity.hu") or not forras.kod.isdecimal():
        raise ValueError("Érvénytelen Cinema City forrás.")
    most = most or datetime.now(BUDAPEST)
    if most.tzinfo is None:
        raise ValueError("Az aktuális időnek időzónát kell tartalmaznia.")
    base = "https://www.cinemacity.hu/hu/data-api-service/v1/quickbook/10102"
    limit = (most.date() + timedelta(days=29)).isoformat()
    index = json.loads(urlpolicy.safe_read_text(
        f"{base}/dates/in-cinema/{forras.kod}/until/{limit}?attr=",
        max_bytes=200_000, timeout=15))
    dates = index.get("body", {}).get("dates") if isinstance(index, dict) else None
    if not isinstance(dates, list):
        raise ValueError("A Cinema City nem adott vetítési dátumokat.")
    out: list[Program] = []
    for day in dates:
        try:
            parsed = date.fromisoformat(day)
        except (TypeError, ValueError):
            continue
        if not most.date() <= parsed <= most.date() + timedelta(days=29):
            continue
        data = json.loads(urlpolicy.safe_read_text(
            f"{base}/film-events/in-cinema/{forras.kod}/at-date/{day}?attr=",
            max_bytes=2_000_000, timeout=15))
        out.extend(feldolgoz_cinemacity(data, forras, most))
    return sorted(out, key=lambda p: (p.kezdet, p.cim))


def szur_programok(programok: list[Program], *, varos: str = "",
                   ettol: date | None = None, eddig: date | None = None,
                   mufaj: str = "", kereses: str = "") -> list[Program]:
    """Idő és hely szerint szűr; a dátumhatárok mindkét vége beleértendő."""
    if ettol and eddig and ettol > eddig:
        raise ValueError("A kezdő dátum későbbi a záró dátumnál.")
    needle = " ".join(kereses.casefold().split())
    return [p for p in sorted(programok, key=lambda p: (p.kezdet, p.cim))
            if (not varos or p.varos.casefold() == varos.casefold())
            and (not ettol or p.kezdet.date() >= ettol)
            and (not eddig or p.kezdet.date() <= eddig)
            and (not mufaj or p.mufaj.casefold() == mufaj.casefold())
            and (not needle or needle in (p.cim + " " + p.helyszin).casefold())]


def lekerdez_forras(forras: ProgramForras,
                    most: datetime | None = None) -> list[Program]:
    if forras.fajta not in ("jegy", "park", "artmozi", "cinemacity"):
        raise ValueError("Ismeretlen programforrás-típus.")
    if forras.fajta == "artmozi":
        return lekerdez_artmozi(forras, most)
    if forras.fajta == "cinemacity":
        return lekerdez_cinemacity(forras, most)
    oldal = urlpolicy.safe_read_text(forras.url, max_bytes=2_000_000,
                                     timeout=20)
    if forras.fajta == "jegy":
        return feldolgoz_jegy_helyszin(oldal, forras, most)
    return feldolgoz_park(oldal, forras, most)


def osszegyujt(forrasok: tuple[ProgramForras, ...] = ELSO_FORRASOK,
               most: datetime | None = None, fetcher=None) -> ProgramGyujtemeny:
    """Egy hibás oldal nem rejti el a többi forrás eseményeit."""
    fetcher = fetcher or lekerdez_forras
    events: list[Program] = []
    errors: list[tuple[str, str]] = []
    seen: set[tuple[str, datetime]] = set()
    for source in forrasok:
        try:
            items = fetcher(source, most)
        except Exception as ex:
            errors.append((source.nev, str(ex) or type(ex).__name__))
            continue
        for item in items:
            key = (item.url, item.kezdet)
            if key not in seen:
                seen.add(key)
                events.append(item)
    events.sort(key=lambda p: (p.kezdet, p.cim))
    return ProgramGyujtemeny(tuple(events), tuple(errors))
