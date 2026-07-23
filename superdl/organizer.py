"""Naptár / teendők / jegyzetek + külső naptár (ICS-link) szinkron.

  * HELYI események (dátum+idő, jegyzet, emlékeztető X perccel előtte,
    egyszeri / minden nap / a hét adott napjain), opcionális AKCIÓVAL, ami a
    megadott időben magától lefut (hivatkozás/app/levél megnyitása, vagy egy
    egyéni szöveg felolvasása).
  * TEENDŐK (határidő, pipálható) és JEGYZETEK.
  * KÜLSŐ naptár: egy titkos iCal- (ICS-) link read-only feliratkozással; a
    program letölti és értelmezi (saját VEVENT-parser, külső függőség nélkül),
    és időnként frissíti.

BIZTONSÁG (FIX): automatizáció (akció) CSAK a SAJÁT, helyben felvett
eseményeknél fut le magától; a KÜLSŐ (ICS) eseményeknél SOHA – azoknál csak
emlékeztető/figyelmeztetés van (nehogy idegen naptár megnyithasson valamit).
"""

import logging
import threading
import urllib.request
import uuid as _uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date as _date

from . import store
from . import urlpolicy

_log = logging.getLogger(__name__)

ACTION_NONE, ACTION_OPEN, ACTION_SPEAK = "none", "open", "speak"
REPEAT_NONE, REPEAT_DAILY, REPEAT_WEEKLY = "none", "daily", "weekly"
WEEKDAYS = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat",
            "vasárnap"]
HORIZON_DAYS = 60                       # az ICS RRULE-t eddig bontjuk ki


def new_id() -> str:
    return _uuid.uuid4().hex[:12]


# ---- adatmodell -------------------------------------------------------

@dataclass
class Event:
    id: str
    title: str
    date: str                          # ÉÉÉÉ-HH-NN
    time: str                          # ÓÓ:PP
    note: str = ""
    reminder_min: int = 10             # X perccel előtte (-1 = nincs emlékeztető)
    repeat: str = "none"
    weekdays: list = field(default_factory=list)
    action_type: str = "none"          # none / open / speak
    action_data: str = ""              # URL/útvonal/mailto, vagy a felolvasandó szöveg
    source: str = "local"              # local / ics
    last_reminded: str = ""            # az emlékeztető elsütésének dátuma
    last_actioned: str = ""            # az akció elsütésének dátuma

    def when(self, on: _date) -> datetime | None:
        try:
            h, m = (int(x) for x in self.time.split(":"))
        except (ValueError, AttributeError):
            h, m = 0, 0
        return datetime(on.year, on.month, on.day, h, m)

    def occurs_on(self, day: _date) -> bool:
        # Az ismétlődés SOHA nem kezdődhet a megadott kezdődátum ELŐTT.
        # Enélkül egy jövő hónapra felvett napi/heti esemény MÁR MA elsülne
        # (hibás emlékeztető és automatikus akció). [Herman Tibi CAL-P0-01]
        if self.repeat in (REPEAT_DAILY, REPEAT_WEEKLY):
            try:
                if day < _date.fromisoformat(self.date):
                    return False
            except (TypeError, ValueError):
                pass          # hiányzó/hibás kezdődátum: a régi viselkedés marad
        if self.repeat == REPEAT_DAILY:
            return True
        if self.repeat == REPEAT_WEEKLY:
            return day.weekday() in (self.weekdays or [])
        return self.date == day.isoformat()      # egyszeri

    def describe(self) -> str:
        rep = ""
        if self.repeat == REPEAT_DAILY:
            rep = " (minden nap)"
        elif self.repeat == REPEAT_WEEKLY:
            rep = " (" + ", ".join(WEEKDAYS[d] for d in sorted(self.weekdays)) + ")"
        tag = " [külső naptár]" if self.source == "ics" else ""
        return f"{self.time} – {self.title}{rep}{tag}"


@dataclass
class Task:
    id: str
    title: str
    due: str = ""                      # ÉÉÉÉ-HH-NN vagy ""
    done: bool = False
    note: str = ""


@dataclass
class Note:
    id: str
    title: str
    body: str = ""
    created: str = ""


@dataclass
class IcsSub:
    id: str
    name: str
    url: str
    last_sync: str = ""

    def safe_label(self) -> str:
        """A naptár-cím MEGJELENÍTHETŐ alakja. Sok szolgáltatónál (Google,
        Outlook, iCloud) a privát ICS-cím maga a HOZZÁFÉRÉSI TITOK: aki látja,
        a teljes naptárat elolvashatja. Ezért a felületen csak a szolgáltató
        neve látszik, a titkos rész nem. [Herman Tibi CAL-P0-04]"""
        return safe_url_label(self.url)


# Futtatható / parancsfájl kiterjesztések: ezeket AUTOMATIKUSAN SOHA nem
# indítjuk el. A naptár JSON-ja helyben módosítható vagy importálható, így egy
# rosszindulatú (vagy sérült) bejegyzés programot futtathatna a háttérben.
_VESZELYES_KITERJESZTESEK = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js",
    ".jse", ".wsf", ".wsh", ".scr", ".msi", ".msp", ".cpl", ".hta", ".jar",
    ".reg", ".lnk", ".pif", ".sct", ".inf", ".application",
}


def check_action_target(target: str) -> tuple[bool, str, str]:
    """Elindítható-e AUTOMATIKUSAN egy időzített esemény „megnyitás" akciója?

    Visszaad: (szabad-e, típus, magyar indoklás). A típus „url" vagy „fajl".

    Enélkül a `os.startfile()` bármilyen programot/parancsfájlt elindíthatott
    volna a felhasználó jelenléte nélkül. [Herman Tibi CAL-P0-05]"""
    t = (target or "").strip()
    if not t:
        return False, "", "Nincs megadva, mit kellene megnyitni."
    low = t.lower()
    if low.startswith(("http://", "https://", "mailto:")):
        return True, "url", ""
    if "://" in t.split("/", 1)[0] or low.startswith(("javascript:", "file:",
                                                      "data:", "vbscript:")):
        return False, "", ("Ez a hivatkozás nem webcím és nem levélcím, ezért "
                           "biztonsági okból nem nyitom meg magától.")
    from pathlib import Path as _P
    try:
        p = _P(t)
        if p.suffix.lower() in _VESZELYES_KITERJESZTESEK:
            return False, "", ("Ez futtatható program vagy parancsfájl. "
                               "Biztonsági okból NEM indítom el magától; "
                               "nyisd meg kézzel, ha tényleg ezt szeretnéd.")
        if not p.is_file():
            return False, "", "A megnyitandó fájl nem található."
    except OSError:
        return False, "", "A megadott útvonal nem értelmezhető."
    return True, "fajl", ""


def safe_url_label(url: str) -> str:
    """Csak a séma+kiszolgáló látszik; ha van útvonal/lekérdezés (tipikusan ez
    hordozza a titkot), azt „titkos link" jelöli."""
    u = (url or "").strip()
    if not u:
        return "(nincs cím)"
    try:
        from urllib.parse import urlsplit
        s = urlsplit(u)
        if not s.netloc:
            return "(ismeretlen cím)"
        titkos = bool((s.path or "").strip("/") or s.query)
        return f"{s.netloc} – titkos link" if titkos else s.netloc
    except Exception:
        return "(ismeretlen cím)"


# ---- ICS (iCalendar) feldolgozás --------------------------------------

def _unfold(text: str) -> list[str]:
    """A folytatósorok (RFC 5545: szóközzel/​tabbal kezdődő) összevonása."""
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def _unescape(v: str) -> str:
    return (v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def _tzid_of(params: str) -> str:
    """A DTSTART;TZID=Europe/Budapest:… paraméterből az időzóna neve."""
    for part in (params or "").split(";"):
        if part.strip().upper().startswith("TZID="):
            return part.split("=", 1)[1].strip().strip('"')
    return ""


def _zone(tzid: str):
    """IANA időzóna objektum, ha elérhető (zoneinfo/tzdata); különben None."""
    if not tzid:
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tzid)
    except Exception:
        return None          # nincs tzdata vagy ismeretlen zóna → naiv marad


def _parse_dt(val: str, params: str):
    """Egy DTSTART/DTEND érték -> (datetime, csak_dátum?). UTC (Z végű) ÉS a
    TZID=… szerinti zónás idő is HELYI időre vált. Hiba esetén None.

    A TZID figyelmen kívül hagyása miatt egy `DTSTART;TZID=America/New_York`
    esemény a gép helyi idejeként jelent meg → az emlékeztető ÓRÁKKAL
    tévedhetett (nyári/téli átállásnál különösen). [Herman Tibi CAL-P0-02]"""
    val = val.strip()
    is_date = "VALUE=DATE" in params.upper() or (len(val) == 8 and "T" not in val)
    try:
        if is_date:
            d = datetime.strptime(val[:8], "%Y%m%d")
            return d, True
        utc = val.endswith("Z")
        core = val[:-1] if utc else val
        dt = datetime.strptime(core, "%Y%m%dT%H%M%S")
        if utc:                         # UTC -> helyi idő
            dt = dt.replace(tzinfo=_tz_utc()).astimezone().replace(tzinfo=None)
        else:
            z = _zone(_tzid_of(params))
            if z is not None:           # TZID -> helyi idő (DST-helyesen)
                dt = dt.replace(tzinfo=z).astimezone().replace(tzinfo=None)
        return dt, False
    except (ValueError, TypeError):
        return None


def _tz_utc():
    from datetime import timezone
    return timezone.utc


def _expand_rrule(start: datetime, rrule: str, horizon_end: _date) -> list[datetime]:
    """ALAP RRULE-kibontás (FREQ=DAILY/WEEKLY, BYDAY, COUNT/UNTIL) a horizontig.
    Az összetettebb szabályokat egyszeri eseményként kezeli (csak a kezdet)."""
    parts = {}
    for kv in rrule.split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            parts[k.upper()] = v
    freq = parts.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY"):
        return [start]
    interval = int(parts.get("INTERVAL", "1") or 1)
    count = int(parts["COUNT"]) if parts.get("COUNT", "").isdigit() else None
    until = None
    if parts.get("UNTIL"):
        u = _parse_dt(parts["UNTIL"], "")
        if u:
            until = u[0]
    byday = parts.get("BYDAY", "")
    daymap = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
    wanted = [daymap[d] for d in byday.split(",") if d in daymap]

    out: list[datetime] = []
    end_dt = datetime(horizon_end.year, horizon_end.month, horizon_end.day,
                      23, 59)
    interval = max(1, interval)
    # A régi kód MINDIG 1 napot lépett, ezért az INTERVAL elveszett: a
    # kétnaponta/kéthetente ismétlődő esemény NAPONTA/HETENTE jelent meg.
    # [Herman Tibi CAL-P0-03]
    guard = 0
    if freq == "DAILY":
        step = timedelta(days=interval)
        cur = start
        while cur <= end_dt and guard < 20000:
            guard += 1
            if until and cur > until:
                break
            out.append(cur)
            if count and len(out) >= count:
                break
            cur += step
    else:                                   # WEEKLY
        # BYDAY nélkül a kezdés napja az ismétlődő nap
        days = sorted(wanted) if wanted else [start.weekday()]
        week0 = start - timedelta(days=start.weekday())     # a kezdés hete (hétfő)
        w = 0
        stop = False
        while not stop and guard < 20000:
            guard += 1
            base = week0 + timedelta(weeks=w * interval)    # az INTERVAL HETEK
            if base > end_dt + timedelta(days=7):
                break
            for wd in days:
                occ = base + timedelta(days=wd)
                if occ < start:             # a kezdés előtti napokat kihagyjuk
                    continue
                if occ > end_dt or (until and occ > until):
                    stop = True
                    break
                out.append(occ)
                if count and len(out) >= count:
                    stop = True
                    break
            w += 1
    return out or [start]


def parse_ics(text: str, horizon_end: _date) -> list[Event]:
    """ICS szöveg -> Event-lista (a SAJÁT modellünkben, source='ics'). A DAILY/
    WEEKLY ismétlődéseket a horizontig kibontja külön eseményekre."""
    events: list[Event] = []
    cur: dict | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                events.extend(_vevent_to_events(cur, horizon_end))
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name = key.split(";", 1)[0].upper()
            cur[name] = (key, val)
    return events


def _vevent_to_events(ve: dict, horizon_end: _date) -> list[Event]:
    if "DTSTART" not in ve:
        return []
    key, val = ve["DTSTART"]
    params = key[len("DTSTART"):]
    parsed = _parse_dt(val, params)
    if not parsed:
        return []
    start, all_day = parsed
    title = _unescape(ve.get("SUMMARY", ("", "(névtelen esemény)"))[1])
    note = _unescape(ve.get("DESCRIPTION", ("", ""))[1])
    rrule = ve.get("RRULE", ("", ""))[1]
    starts = _expand_rrule(start, rrule, horizon_end) if rrule else [start]

    out: list[Event] = []
    for dt in starts:
        out.append(Event(
            id="ics-" + new_id(), title=title or "(névtelen esemény)",
            date=dt.date().isoformat(),
            time=("egész nap" if all_day else dt.strftime("%H:%M")),
            note=note, reminder_min=-1 if all_day else 10,
            repeat=REPEAT_NONE, action_type=ACTION_NONE, source="ics"))
    return out


# ---- tár --------------------------------------------------------------

class OrganizerManager:
    """Az események/teendők/jegyzetek és az ICS-feliratkozások központja, a
    háttér emlékeztető-ütemezővel. A GUI-tól független (a program futása alatt
    sülnek el az emlékeztetők)."""

    def __init__(self, on_remind=None):
        self.on_remind = on_remind          # on_remind(event, kind) – kind: remind/action
        self._lock = threading.Lock()
        self.events: list[Event] = [self._mk(Event, r)
                                    for r in store.load_organizer_events()]
        self.tasks: list[Task] = [self._mk(Task, r)
                                  for r in store.load_organizer_tasks()]
        self.notes: list[Note] = [self._mk(Note, r)
                                  for r in store.load_organizer_notes()]
        self.secret_warning = ""      # ha a titkosított mentés nem sikerült
        self.ics_subs: list[IcsSub] = [self._mk(IcsSub, r)
                                       for r in store.load_ics_subs()]
        # A címeket a TITKOSÍTOTT tárolóból pótoljuk; a régi telepítéseknél a
        # nyílt fájlban lévő cím MIGRÁLÓDIK (a save() írja vissza titkosítva).
        try:
            _urls = store.load_ics_urls()
        except Exception:
            _urls = {}
        _migralando = False
        for s in self.ics_subs:
            if not s.url and _urls.get(s.id):
                s.url = _urls[s.id]
            elif s.url:
                _migralando = True    # régi, nyílt cím → titkosítva mentjük
        self.ics_events: list[Event] = []
        # ütemező-egészség (CAL-P0-06): a hibák nem tűnhetnek el némán
        self.last_tick_ok: datetime | None = None
        self.tick_errors = 0
        self.last_error = ""
        self._stop = threading.Event()
        if _migralando:
            # a nyílt fájlban talált címek AZONNAL titkosítva íródnak vissza
            try:
                self.save()
            except Exception:
                pass
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        threading.Thread(target=self.sync_ics, daemon=True).start()

    @staticmethod
    def _mk(cls, rec: dict):
        flds = cls.__dataclass_fields__
        return cls(**{k: v for k, v in rec.items() if k in flds})

    # ---- mentés -------------------------------------------------------

    def save(self):
        store.save_organizer_events([asdict(e) for e in self.events])
        store.save_organizer_tasks([asdict(t) for t in self.tasks])
        store.save_organizer_notes([asdict(n) for n in self.notes])
        # Az ICS-CÍMEK titkosítva, a nem bizalmas mezőktől KÜLÖN mennek: a privát
        # naptár címe maga a hozzáférési titok. [Herman Tibi CAL-P0-04]
        urls = {s.id: s.url for s in self.ics_subs if s.url}
        titkositva = store.save_ics_urls(urls) if urls else True
        rekordok = []
        for s in self.ics_subs:
            r = asdict(s)
            if titkositva:
                r["url"] = ""        # a nyílt fájlban NEM marad cím
            rekordok.append(r)
        if not titkositva and not self.secret_warning:
            self.secret_warning = (
                "A naptár-címeket nem sikerült titkosítva menteni (a Windows "
                "DPAPI nem érhető el), ezért olvashatóan tárolódnak.")
        store.save_ics_subs(rekordok)

    # ---- események ----------------------------------------------------

    def add_event(self, e: Event):
        with self._lock:
            self.events.append(e)
        self.save()

    def update_event(self, e: Event):
        self.save()

    def remove_event(self, eid: str):
        with self._lock:
            self.events = [e for e in self.events if e.id != eid]
        self.save()

    # ---- teendők / jegyzetek -----------------------------------------

    def add_task(self, t: Task):
        with self._lock:
            self.tasks.append(t)
        self.save()

    def remove_task(self, tid: str):
        with self._lock:
            self.tasks = [t for t in self.tasks if t.id != tid]
        self.save()

    def toggle_task(self, tid: str):
        for t in self.tasks:
            if t.id == tid:
                t.done = not t.done
        self.save()

    def add_note(self, n: Note):
        with self._lock:
            self.notes.append(n)
        self.save()

    def remove_note(self, nid: str):
        with self._lock:
            self.notes = [n for n in self.notes if n.id != nid]
        self.save()

    # ---- agenda (helyi + ICS, idő szerint) ----------------------------

    def upcoming(self, days: int = 30) -> list[tuple[datetime, Event]]:
        today = datetime.now().date()
        end = today + timedelta(days=days)
        out: list[tuple[datetime, Event]] = []
        with self._lock:
            locals_ = list(self.events)
            ics = list(self.ics_events)
        for ev in locals_:
            d = today
            while d <= end:
                if ev.occurs_on(d):
                    w = ev.when(d)
                    if w:
                        out.append((w, ev))
                    if ev.repeat == REPEAT_NONE:
                        break
                d += timedelta(days=1)
        for ev in ics:
            try:
                d = _date.fromisoformat(ev.date)
            except ValueError:
                continue
            if today <= d <= end:
                w = ev.when(d) or datetime(d.year, d.month, d.day)
                out.append((w, ev))
        out.sort(key=lambda x: x[0])
        return out

    # ---- ICS-feliratkozások ------------------------------------------

    def add_ics(self, name: str, url: str) -> IcsSub:
        sub = IcsSub(id=new_id(), name=name or url, url=url)
        with self._lock:
            self.ics_subs.append(sub)
        self.save()
        threading.Thread(target=self.sync_ics, daemon=True).start()
        return sub

    def remove_ics(self, sid: str):
        with self._lock:
            self.ics_subs = [s for s in self.ics_subs if s.id != sid]
        self.save()
        self.sync_ics()

    def sync_ics(self) -> str:
        """Az összes ICS-feliratkozás letöltése és értelmezése. Visszaad egy
        rövid összefoglalót (a GUI-nak)."""
        horizon = datetime.now().date() + timedelta(days=HORIZON_DAYS)
        all_events: list[Event] = []
        errors = 0
        with self._lock:
            subs = list(self.ics_subs)
        for sub in subs:
            try:
                # ELLENŐRZÖTT letöltés: csak http/https, nem mutathat a saját
                # gépre/házi hálózatra (átirányítás után sem), és van
                # méretkorlát. [Herman Tibi CAL-P0-07]
                raw = urlpolicy.safe_read_text(sub.url, timeout=25)
                evs = parse_ics(raw, horizon)
                all_events.extend(evs)
                sub.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M")
            except Exception:
                errors += 1
        with self._lock:
            self.ics_events = all_events
        self.save()
        return f"{len(all_events)} külső esemény{' (' + str(errors) + ' hiba)' if errors else ''}"

    # ---- emlékeztető-ütemező -----------------------------------------

    def _loop(self):
        while not self._stop.wait(20):
            try:
                self._tick()
                self.last_tick_ok = datetime.now()
            except Exception as e:
                # NE tűnjön el némán: e nélkül egyetlen hibás rekord után az
                # ÖSSZES emlékeztető csendben kimaradhat, és nem derül ki, miért.
                # [Herman Tibi CAL-P0-06]
                self.tick_errors += 1
                self.last_error = f"{type(e).__name__}: {e}"
                _log.exception("Az emlékeztető-ütemező hibája (%d. alkalom)",
                               self.tick_errors)

    def scheduler_health(self) -> dict:
        """Az ütemező állapota a diagnosztikához (F8): mikor futott le utoljára
        hibátlanul, hány hiba volt, és mi volt az utolsó."""
        return {"utolso_sikeres": (self.last_tick_ok.isoformat(timespec="seconds")
                                   if self.last_tick_ok else "még nem futott"),
                "hibak_szama": self.tick_errors,
                "utolso_hiba": self.last_error or "nincs"}

    def _tick(self):
        now = datetime.now()
        today = now.date().isoformat()
        for ev in list(self.events) + list(self.ics_events):
            occ = self._today_occurrence(ev, now)
            if not occ:
                continue
            # emlékeztető X perccel előtte (ablak: emlékeztetőtől az eseményig+1p)
            if ev.reminder_min is not None and ev.reminder_min >= 0 \
                    and ev.last_reminded != today:
                remind_at = occ - timedelta(minutes=ev.reminder_min)
                if remind_at <= now < occ + timedelta(minutes=1):
                    ev.last_reminded = today
                    self._fire(ev, "remind")
            # akció PONTBAN – CSAK saját (local) eseménynél!
            if (ev.source == "local" and ev.action_type not in ("", ACTION_NONE)
                    and ev.last_actioned != today):
                if occ <= now < occ + timedelta(minutes=2):
                    ev.last_actioned = today
                    self._fire(ev, "action")
        # a futás közbeni állapotot ritkán mentjük (last_reminded/last_actioned)
        self.save()

    def _today_occurrence(self, ev: Event, now: datetime) -> datetime | None:
        day = now.date()
        if ev.source == "ics":
            if ev.date != day.isoformat() or ev.time == "egész nap":
                return None
            return ev.when(day)
        if not ev.occurs_on(day):
            return None
        return ev.when(day)

    def _fire(self, ev: Event, kind: str):
        if self.on_remind:
            try:
                self.on_remind(ev, kind)
            except Exception:
                pass

    def shutdown(self):
        self._stop.set()
        self.save()
