# -*- coding: utf-8 -*-
"""A zenetár: mappabejárás, a számok listája, és a szám hossza.

Tudatosan NEM olvas címkéket (előadó, cím). 550 mappánál az több ezer fájl
megnyitását jelentené, és ez a program azért van, hogy AZONNAL induljon. A
sorok a fájlnévből és a mappanévből állnak — az a név, amit a felhasználó
adott nekik, tehát ő is arra emlékszik.
"""

import json
import os
import subprocess
from pathlib import Path

KITERJESZTESEK = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav",
                  ".flac", ".wma", ".mp2", ".mka", ".m4b", ".aif", ".aiff",
                  ".ape", ".wv", ".alac")

BEALLITAS = Path.home() / ".superdl" / "zene.json"


class Szam:
    """Egy szám a listában. Szándékosan könnyű: csak az út és két név."""

    __slots__ = ("ut", "cim", "mappa")

    def __init__(self, ut: str, cim: str, mappa: str):
        self.ut = ut
        self.cim = cim
        self.mappa = mappa

    def felirat(self) -> str:
        return f"{self.cim} – {self.mappa}" if self.mappa else self.cim


def zenei_fajl(nev: str) -> bool:
    return os.path.splitext(nev)[1].lower() in KITERJESZTESEK


def beolvas(gyoker, megall=None) -> tuple[list, int]:
    """A gyökér ALATT MINDEN almappa, tetszőleges mélységig.

    Visszaad: (számok listája, bejárt mappák száma). A `megall` egy
    `threading.Event`; ha beáll, a bejárás félbehagyható — az ablak bezárása
    ne várjon egy fél percet egy hálózati meghajtón.

    A rejtett és a hozzáférhetetlen mappákat csendben kihagyjuk: egy
    rendszermappa miatt ne álljon meg az egész beolvasás.
    """
    gyoker = str(gyoker or "").strip()
    if not gyoker or not os.path.isdir(gyoker):
        return [], 0
    tovek = Path(gyoker)
    szamok, mappak = [], 0
    for to, alkonyvtarak, fajlok in os.walk(gyoker, onerror=lambda e: None):
        if megall is not None and megall.is_set():
            break
        alkonyvtarak[:] = [d for d in alkonyvtarak if not d.startswith(".")]
        mappak += 1
        try:
            rel = str(Path(to).relative_to(tovek))
        except ValueError:
            rel = os.path.basename(to)
        mappanev = "" if rel == "." else rel.replace(os.sep, " / ")
        for f in fajlok:
            if zenei_fajl(f):
                szamok.append(Szam(os.path.join(to, f),
                                   os.path.splitext(f)[0], mappanev))
    szamok.sort(key=lambda s: (s.mappa.lower(), s.cim.lower()))
    return szamok, mappak


# ---- a szám hossza (az áttűnéshez kell) --------------------------------

def hossz(ut: str) -> float:
    """A szám hossza másodpercben, vagy 0.0, ha nem deríthető ki.

    Az ffprobe-bal kérdezzük le (mérve: ~66 ezredmásodperc fájlonként), és
    CSAK az éppen szóló meg a következő számra — több ezer fájlra ez percekbe
    kerülne. Ha nincs ffprobe vagy nem ad számot, 0.0 megy vissza: olyankor
    nincs áttűnés, de a következő szám AKKOR IS elindul, mert a lejátszó a
    „vége” jelzésre is lép.
    """
    exe = _ffprobe()
    if not exe or not ut:
        return 0.0
    try:
        r = subprocess.run(
            [exe, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(ut)],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return max(0.0, float((r.stdout or "").strip()))
    except Exception:
        return 0.0


def _ffprobe() -> str:
    try:
        from superdl.ffmpeg import find_ffmpeg
        p = find_ffmpeg()
    except Exception:
        p = None
    if not p:
        return ""
    p = Path(p)
    jelolt = p.with_name("ffprobe.exe") if p.suffix else p / "ffprobe.exe"
    try:
        return str(jelolt) if jelolt.exists() else ""
    except OSError:
        return ""


def szam_utbol(ut: str) -> "Szam":
    """Egy szám az útjából – a kedvencek listájához.

    ⚠️ A kedvenc egy ÚT, nem egy listaindex. Ha a felhasználó másik
    zenemappára vált vagy átrendezi a fájljait, az index elcsúszna, és a
    kedvencek csendben MÁS számokra mutatnának. Az út ezt kizárja: ami
    elveszett, az hiányzóként látszik, nem rossz számként szól.
    """
    ut = str(ut or "")
    return Szam(ut, os.path.splitext(os.path.basename(ut))[0],
                os.path.basename(os.path.dirname(ut)))


# ---- beállítások (gyökérmappa, kedvencek, keverés, hangkimenet) ---------

def beallitasok() -> dict:
    try:
        d = json.loads(BEALLITAS.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def beallit(**kv) -> None:
    """Egy-egy beállítás módosítása a TÖBBI MEGTARTÁSÁVAL.

    ⚠️ A korábbi mentés az egész fájlt felülírta a gyökérmappával. Egy új
    beállítás bevezetése így a régieket némán kitörölte volna.
    """
    d = beallitasok()
    d.update(kv)
    try:
        BEALLITAS.parent.mkdir(parents=True, exist_ok=True)
        BEALLITAS.write_text(json.dumps(d, ensure_ascii=False),
                             encoding="utf-8")
    except OSError:
        pass


def gyoker_betolt() -> str:
    return str(beallitasok().get("gyoker") or "")


def gyoker_ment(ut: str) -> None:
    beallit(gyoker=str(ut or ""))


def kedvencek_betolt() -> list:
    """A kedvencek ÚTJAI, a felvétel sorrendjében, ismétlés nélkül."""
    nyers = beallitasok().get("kedvencek")
    ki, latott = [], set()
    if isinstance(nyers, list):
        for u in nyers:
            u = str(u or "").strip()
            k = u.lower()
            if u and k not in latott:
                latott.add(k)
                ki.append(u)
    return ki


def kedvencek_ment(utak) -> None:
    beallit(kedvencek=[str(u) for u in (utak or [])])


def keveres_betolt() -> bool:
    return bool(beallitasok().get("keveres"))


def keveres_ment(be: bool) -> None:
    beallit(keveres=bool(be))


def kimenet_betolt() -> str:
    return str(beallitasok().get("kimenet") or "")


def kimenet_ment(nev: str) -> None:
    beallit(kimenet=str(nev or ""))


def hangero_betolt() -> float:
    """A megjegyzett hangerő 0 és 1 között; alapból teljes.

    ⚠️ Szabó László kérése (2026-09-23): „megoldható-e, hogy a program
    megjegyezze az előzőleg beállított hangerőt? Minden újbóli bekapcsoláskor
    100%-kal indul." Aki halkan hallgat, annak minden indítás egy ijesztő
    hangrobbanás volt."""
    try:
        v = float(beallitasok().get("hangero", 1.0))
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, v))


def hangero_ment(v: float) -> None:
    beallit(hangero=max(0.0, min(1.0, float(v))))


def hangszin_betolt() -> tuple:
    """A megjegyzett hangszín: (profil-azonosító, erősség százalékban).

    ⚠️ Az alapértelmezés az „eredeti", 100 százalékkal. Aki nem nyúl hozzá,
    pontosan azt hallja, amit eddig — egy hangszín-szabályzó bevezetése nem
    változtathatja meg senkinek a hangját magától."""
    d = beallitasok()
    profil = str(d.get("hangszin", "eredeti") or "eredeti")
    try:
        eros = int(d.get("hangszin_erosseg", 100))
    except (TypeError, ValueError):
        eros = 100
    return profil, max(0, min(100, eros))


def hangszin_ment(profil: str, erosseg: int) -> None:
    beallit(hangszin=str(profil or "eredeti"),
            hangszin_erosseg=max(0, min(100, int(erosseg))))


def ido_szoveg(mp: float) -> str:
    """Másodperc → „3 perc 25 másodperc” (felolvasásra, nem 3:25-re)."""
    mp = max(0, int(mp))
    perc, masodperc = divmod(mp, 60)
    if perc and masodperc:
        return f"{perc} perc {masodperc} másodperc"
    if perc:
        return f"{perc} perc"
    return f"{masodperc} másodperc"
