# -*- coding: utf-8 -*-
"""GÉPI ÉNEK – a SuperDL saját formáns-szintetizátora (Core: retrospeech)
dallamra énekel. Minden szótagot a saját hangmagasságán (F0) szólaltatunk meg,
a hangjegy hosszára igazítva, majd egymás után fűzzük. Semmi idegen hangminta.

A dal egy soraiból áll: (szótag, hangnév, hossz_másodperc). A hangnév pl. „c4",
„g4", „c5"; a 4. oktáv a középső. A hossz másodpercben (vagy „egész/fél/negyed/
nyolcad")."""
import dataclasses

_FELHANG = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "h": 11, "b": 11}
_HOSSZ_SZO = {"egesz": 1.0, "egész": 1.0, "fel": 0.5, "fél": 0.5,
              "negyed": 0.25, "nyolcad": 0.125, "ketnegyed": 0.5,
              "haromnegyed": 0.75}


def frekv(hangnev: str) -> float:
    """Hangnév → frekvencia (Hz). Pl. 'c4'→261,63; 'a4'→440; 'c5'→523,25.
    Ismeretlen névre a középső C-t adja."""
    if not hangnev:
        return 261.63
    s = hangnev.strip().lower()
    betu = s[0]
    if betu not in _FELHANG:
        return 261.63
    try:
        okt = int(s[1:]) if len(s) > 1 and s[1:].lstrip("-").isdigit() else 4
    except ValueError:
        okt = 4
    felhang = _FELHANG[betu] + (okt - 4) * 12         # C4-hez képest
    return 261.63 * (2 ** (felhang / 12.0))


def hossz_ertek(v) -> float:
    """Hossz értelmezése: szám (másodperc) vagy szó (egész/fél/negyed/…)."""
    if isinstance(v, (int, float)):
        return max(0.1, min(4.0, float(v)))
    s = str(v).strip().lower().replace(",", ".")
    if s in _HOSSZ_SZO:
        return _HOSSZ_SZO[s]
    try:
        return max(0.1, min(4.0, float(s)))
    except ValueError:
        return 0.4


def parse_sor(szoveg: str):
    """Egy beírt sor → (szótag, hangnév, hossz_mp) vagy None. Formátum:
    „szótag hangnév hossz", pl. „bo g4 0.4" vagy „lá a4 fél". A szótag üres is
    lehet (csak dallam, szünet-jelleg): „- c4 0.5"."""
    reszek = szoveg.strip().split()
    if len(reszek) < 2:
        return None
    # az utolsó elem a hossz, az utolsó előtti a hangnév, a többi a szótag
    hossz = hossz_ertek(reszek[-1])
    hangnev = reszek[-2]
    szotag = " ".join(reszek[:-2]) if len(reszek) > 2 else ""
    if szotag in ("-", "_"):
        szotag = ""
    if not hangnev or hangnev[0].lower() not in _FELHANG:
        return None
    return (szotag, hangnev, hossz)


def _enekhang(szotag, hz, hossz_mp, gepkulcs, RS, np):
    g = RS.gep(gepkulcs)
    if not (szotag or "").strip():                    # üres = dúdolás („m")
        szotag = "m"
    hangok = RS.szoveg_hangokra(szotag)
    termeszetes = sum(RS.TABLA[n].hossz for n, _ in hangok
                      if n in RS.TABLA) / 1000.0 or 0.2
    tempo = max(0.35, min(4.5, hossz_mp / termeszetes))
    g2 = dataclasses.replace(g, alaphang=float(hz), deklinacio=0.0,
                             hangsuly=0.04, szotag_hangsuly=0.0, tempo=tempo)
    x, fs = RS.szintetizal(szotag, g2)
    x = np.asarray(x, dtype=float)
    cel = int(fs * hossz_mp)
    if len(x) < cel:
        x = np.concatenate([x, np.zeros(cel - len(x))])
    else:
        x = x[:cel]
    el = min(int(fs * 0.01), len(x) // 4)
    if el > 0:
        x[:el] *= np.linspace(0, 1, el)
        x[-el:] *= np.linspace(1, 0, el)
    return x, fs


def enekel(sorok, gepkulcs="brailab"):
    """A dal (sorok = [(szótag, hangnév, hossz_mp), …]) megszólaltatása.
    Visszaad: (minta-tömb float −1..1, mintavétel). Üres dalra (None, 11025)."""
    import numpy as np
    from superdl import retrospeech as RS
    darabok = []
    fs = 11025
    for szotag, hangnev, hossz in sorok:
        x, fs = _enekhang(szotag, frekv(hangnev), hossz_ertek(hossz),
                          gepkulcs, RS, np)
        darabok.append(x)
    if not darabok:
        return None, fs
    y = np.concatenate(darabok)
    m = float(np.max(np.abs(y))) or 1.0
    return (y / m * 0.9).astype(float), fs


# --- beépített példadalok (közismert magyar népdalok / közkincs) -----------
PELDAK = {
    "skála": [("dó", "c4", 0.5), ("ré", "d4", 0.5), ("mi", "e4", 0.5),
              ("fá", "f4", 0.5), ("szó", "g4", 0.5), ("lá", "a4", 0.5),
              ("ti", "h4", 0.5), ("dó", "c5", 0.7)],
    "boci": [("bo", "g4", 0.4), ("ci", "g4", 0.4), ("bo", "e4", 0.4),
             ("ci", "e4", 0.4), ("tar", "g4", 0.4), ("ka", "g4", 0.4),
             ("", "e4", 0.2), ("se", "f4", 0.4), ("fü", "f4", 0.4),
             ("le", "d4", 0.4), ("se", "d4", 0.4), ("far", "f4", 0.4),
             ("ka", "f4", 0.4), ("", "c4", 0.5)],
}
