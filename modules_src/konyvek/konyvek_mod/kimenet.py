# -*- coding: utf-8 -*-
"""A hangoskönyv KIMENETÉNEK helye és a végi HANGJELZÉS.

Felhasználói kérés (2026-08-15):
  • a kész hangoskönyv kerülhessen ODA, AHONNAN a könyvet betallózta;
  • DARABOLÁSNÁL mindig ALMAPPA – ne szóródjon szét húsz MP3;
  • a készítés végén szóljon egy rövid FANFÁR, hiba esetén pedig egy
    jól megkülönböztethető, másik jelzés (hosszú könyvnél a gép mellől el
    lehessen menni).

Ez a fájl SZÁNDÉKOSAN wx-mentes, hogy tesztelhető legyen. A hangot a MODUL
állítja elő (nem a Core), így ez modul-frissítésként kiadható.
"""

from __future__ import annotations

import math
import os
import struct
import threading
import wave
from pathlib import Path

# a fájlnévben nem használható karakterek Windowson
_TILTOTT = '<>:"/\\|?*'


def biztonsagos_nev(cim: str, alap: str = "hangoskonyv") -> str:
    """Fájl- és mappanévvé szelídített cím (a Windows tiltott karakterei nélkül,
    záró pont és szóköz nélkül – azokkal a mappa létrehozása elhasalna)."""
    nev = "".join(("_" if c in _TILTOTT else c) for c in (cim or ""))
    nev = "".join(c for c in nev if c.isprintable()).strip().rstrip(". ")
    return nev[:120] or alap


def irhato(mappa) -> bool:
    """Tényleg tudunk-e ide írni? Nem elég a létezés: egy csak olvasható
    meghajtón (pl. CD, írásvédett hálózati mappa) a készítés a MUNKA VÉGÉN
    hasalna el – azt pedig egy többórás felolvasás után elviselhetetlen."""
    mappa = Path(mappa)
    try:
        mappa.mkdir(parents=True, exist_ok=True)
        proba = mappa / (".superdl_iras_proba_%d" % os.getpid())
        proba.write_bytes(b"x")
        proba.unlink()
        return True
    except Exception:
        return False


def celmappa(forras_fajl: str, alap_mappa: str, konyv_melle: bool) -> tuple:
    """HOVÁ mentsünk? Visszaad: (mappa, üzenet). Az üzenet akkor nem üres, ha
    NEM az lett, amit a felhasználó kért – ilyenkor a hívó KIMONDJA az okot,
    mert a néma „máshová került" a legrosszabb fajta meglepetés."""
    alap = Path(alap_mappa or Path.home() / "Downloads")
    if not konyv_melle:
        return alap, ""
    if not forras_fajl:
        return alap, ("Beillesztett szövegnél nincs „a könyv mellé”, mert nincs "
                      "eredeti fájl – a célmappába kerül.")
    szulo = Path(forras_fajl).expanduser().parent
    if not irhato(szulo):
        return alap, ("A könyv mappájába nem lehet írni (írásvédett vagy nincs "
                      "jogosultság), ezért a célmappába kerül.")
    return szulo, ""


def kimeneti_ut(mappa, cim: str, darabolva: bool) -> Path:
    """A `build`-nek átadandó kimeneti útvonal.

    DARABOLÁSNÁL a könyv címéről elnevezett ALMAPPÁBA megy – mindig, akár a
    könyv mellé, akár a célmappába mentünk. Egyetlen fájlnál nincs almappa.
    ÜTKÖZÉS esetén nem írunk felül semmit: „(2)", „(3)" utótagot kap."""
    mappa = Path(mappa)
    nev = biztonsagos_nev(cim)
    if darabolva:
        cel_mappa = _szabad_nev(mappa / nev, mappa_e=True)
        return cel_mappa / (nev + ".mp3")
    return _szabad_nev(mappa / (nev + ".mp3"), mappa_e=False)


def _szabad_nev(ut: Path, mappa_e: bool) -> Path:
    """Szabad (még nem létező) név keresése. Mappánál akkor is szabadnak
    tekintjük, ha LÉTEZIK, de ÜRES – így a másodszori próbálkozás nem gyárt
    „Cím (2)" mappákat feleslegesen."""
    if not ut.exists():
        return ut
    if mappa_e and ut.is_dir() and not any(ut.iterdir()):
        return ut
    torzs = ut.stem if not mappa_e else ut.name
    utotag = ut.suffix if not mappa_e else ""
    for i in range(2, 100):
        jelolt = ut.with_name("%s (%d)%s" % (torzs, i, utotag))
        if not jelolt.exists():
            return jelolt
    return ut


# ------------------------------------------------------------- hangjelzés

_HANG_MAPPA = Path.home() / ".superdl" / "konyvek_hangok"
_MINTAVETEL = 22050

# FANFÁR (siker): rövid, felfelé futó dúr hármas + oktáv – barátságos, és
# semmi máshoz nem hasonlít a programban.
_SIKER = [(523, 0.10), (659, 0.10), (784, 0.10), (1047, 0.26)]
# HIBA: lefelé tartó, tompább kétszólam – hallás után AZONNAL megkülönböztethető
# a sikertől (ez a lényeg: ne kelljen a képernyőt megnézni).
_HIBA = [(392, 0.16), (311, 0.16), (233, 0.34)]


def _hullam(frekvencia: float, hossz: float, amplitudo: float = 0.32) -> bytes:
    n = int(_MINTAVETEL * hossz)
    fel, le = int(0.01 * _MINTAVETEL), int(0.05 * _MINTAVETEL)
    ki = bytearray()
    for i in range(n):
        burok = 1.0
        if i < fel:
            burok = i / fel
        elif i > n - le:
            burok = max(0.0, (n - i) / le)
        ertek = int(32767 * amplitudo * burok
                    * math.sin(2 * math.pi * frekvencia * i / _MINTAVETEL))
        ki += struct.pack("<h", ertek)
    return bytes(ki)


def hang_fajl(siker: bool) -> Path:
    """A jelzőhang WAV-ja (első használatkor legenerálva). Azért állítjuk elő
    magunk, hogy ne kelljen külön fájlt szállítani a modullal."""
    _HANG_MAPPA.mkdir(parents=True, exist_ok=True)
    ut = _HANG_MAPPA / ("kesz.wav" if siker else "hiba.wav")
    if not ut.is_file() or ut.stat().st_size < 1000:
        adat = b"".join(_hullam(f, h) for f, h in (_SIKER if siker else _HIBA))
        with wave.open(str(ut), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_MINTAVETEL)
            w.writeframes(adat)
    return ut


def jelzes(siker: bool) -> bool:
    """Lejátssza a jelzőhangot (háttérben, a felületet nem blokkolva).
    A képernyőolvasó beszédét NEM helyettesíti, csak kiegészíti – ezért is
    rövid. Hiba esetén csendben False (a hang sosem viheti el a munkát)."""
    try:
        ut = hang_fajl(siker)
    except Exception:
        return False
    try:
        import winsound
    except Exception:
        return False

    def jatszd():
        try:
            winsound.PlaySound(str(ut), winsound.SND_FILENAME)
        except Exception:
            pass

    threading.Thread(target=jatszd, daemon=True).start()
    return True
