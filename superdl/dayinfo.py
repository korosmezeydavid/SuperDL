"""A napi infó magyar mondattá fűzése: dátum + névnap + (opcionális)
időjárás + (opcionális) letöltési állapot.

A modul SZÁNDÉKOSAN nem hálózatozik: az időjárást a hívó kéri le (külön
szálon, hogy ne lassítsa az indulást), és kész `Weather`-ként adja át. Így a
mondat hálózat nélkül is összeáll (csak dátum + névnap).
"""

from datetime import date, datetime

from . import namedays

WEEKDAYS = ["hétfő", "kedd", "szerda", "csütörtök", "péntek",
            "szombat", "vasárnap"]
MONTHS = ["január", "február", "március", "április", "május", "június",
          "július", "augusztus", "szeptember", "október", "november",
          "december"]


def date_phrase(d: date | None = None) -> str:
    """Pl.: „2026. június 14., vasárnap”."""
    d = d or date.today()
    return (f"{d.year}. {MONTHS[d.month - 1]} {d.day}., "
            f"{WEEKDAYS[d.weekday()]}")


def nameday_phrase(d: date | None = None) -> str:
    """Pl.: „Vazul napja” – üres, ha nincs adat."""
    names = namedays.for_date(d)
    return f"{names} napja" if names else ""


def build_greeting(weather=None, download_status: str = "",
                   when: datetime | None = None) -> str:
    """A teljes üdvözlőmondat. `weather` egy weather.Weather vagy None;
    `download_status` a hívótól (pl. „Jelenleg nincs aktív letöltésed.”)."""
    when = when or datetime.now()
    d = when.date()
    parts = [f"Üdvözöl a SuperDL! Ma {date_phrase(d)} van"]
    nd = nameday_phrase(d)
    if nd:
        parts.append(nd)
    head = ", ".join(parts) + "."
    out = [head]
    if weather is not None:
        out.append(weather.sentence() + ".")
    if download_status:
        out.append(download_status)
    return " ".join(out)
