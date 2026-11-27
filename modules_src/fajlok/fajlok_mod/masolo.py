"""Egyenkénti másolás és áthelyezés.

A Windows fájlművelete a teljes listát és a folyamatot a memóriában tartja,
ezért sok vagy nagy fájlnál megdagad. Itt a számlálás csak két számot őriz
(darabszám és bájt), a másolás pedig egyetlen, újrahasznált egy megabájtos
darabbal megy, fájlonként. Áthelyezéskor ugyanazon a meghajtón a fájl a helyén
marad, csak a neve költözik. Másik meghajtóra előbb másol, és a forrást csak
a kész, ellenőrzött fájl után törli.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

DARAB = 1024 * 1024
_UJRA = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT


class Megszakitva(Exception):
    """A felhasználó megállította a műveletet."""


@dataclass
class Jelentes:
    fajlok: int = 0
    bajtok: int = 0
    kesz_fajlok: int = 0
    kesz_bajtok: int = 0
    most: str = ""
    uzenet: str = ""
    hibak: list = field(default_factory=list)
    kesz: bool = False
    megszakitva: bool = False
    fazis: str = ""
    hatra_mp: float | None = None
    kezdet: float = 0.0

    def szazalek(self) -> int:
        if self.bajtok:
            return min(100, int(self.kesz_bajtok * 100 / self.bajtok))
        if self.fajlok:
            return min(100, int(self.kesz_fajlok * 100 / self.fajlok))
        return 0

    def helyzet(self) -> str:
        """Egy mondat: mit csinál, hány százalék, mennyi van hátra."""
        if self.fazis in ("vege", "terv"):
            return self.uzenet
        if self.fazis == "szamol":
            return "Számlálás. Eddig %d fájl." % self.fajlok
        hatra = ido_szoveg(self.hatra_mp)
        most = self.most or "a következő fájl"
        return "%d százalék, %s. Most: %s. %d a %d fájlból." % (
            self.szazalek(), hatra, most, self.kesz_fajlok, self.fajlok)


def futtat(forrasok, cel, muvelet, utkozes, jelents, cancel,
          keszek=None, mentes=None, folytat=False, jovahagy=None) -> Jelentes:
    """forrasok: fájl- vagy mappaútvonalak. muvelet: masol vagy athelyez.
    utkozes: felulir, kihagy vagy ujnev. jelents(Jelentes) a fő szálra vihető.
    cancel() igaz, ha meg kell állni."""
    jel = Jelentes()
    keszek = {_norm(u) for u in (keszek or [])}
    cel = os.path.abspath(cel)
    try:
        os.makedirs(cel, exist_ok=True)
    except OSError as exc:
        jel.uzenet = "A célmappa nem készíthető el: %s" % exc
        jel.hibak.append(jel.uzenet)
        jel.kesz = True
        jelents(jel)
        return jel
    tiszta = []
    for nyers in forrasok:
        ut = os.path.abspath(nyers)
        if not os.path.exists(ut):
            jel.hibak.append("Nincs meg: %s" % ut)
            continue
        nev = os.path.basename(ut.rstrip("\\/"))
        cel_ut = os.path.join(cel, nev)
        if (_azonos(ut, cel_ut) or _belul(ut, cel)
                or (os.path.isdir(ut) and _belul(ut, cel_ut))):
            jel.hibak.append("A cél a forrás belsejében van, ezt kihagytam: %s" % ut)
            continue
        tiszta.append(ut)
    jel.fazis = "szamol"
    _szol(jel, jelents)
    try:
        if folytat and keszek and muvelet == "masol":
            jel.uzenet = "A korábban késznek jelölt fájlok ellenőrzése."
            _szol(jel, jelents)
            keszek = _ellenorzott_keszek(tiszta, cel, keszek, cancel)
        for ut in tiszta:
            _szamol(ut, jel, cancel, keszek, jelents)
    except Megszakitva:
        jel.kesz = jel.megszakitva = True
        jel.fazis = "vege"
        jel.uzenet = "Megszakítva. Az átvitel nem indult el."
        jelents(jel)
        return jel
    jel.fazis = "terv"
    jel.uzenet = "A terv: %d fájl, %s." % (jel.fajlok, meret_szoveg(jel.bajtok))
    _szol(jel, jelents)
    if jovahagy is not None and not jovahagy(jel.uzenet):
        jel.kesz = True
        jel.fazis = "vege"
        jel.uzenet = "Mégsem. Nem indult el."
        jelents(jel)
        return jel
    jel.fazis = "visz"
    jel.kezdet = time.monotonic()
    jel.uzenet = "Indul: %d fájl." % jel.fajlok
    _szol(jel, jelents)
    try:
        for ut in tiszta:
            _egy_gyoker(ut, cel, muvelet, utkozes, jel, jelents, cancel,
                        keszek, mentes, folytat)
            if muvelet == "athelyez" and os.path.isdir(ut):
                _ures_mappak(ut)
    except Megszakitva:
        jel.megszakitva = True
        jel.kesz = True
        jel.fazis = "vege"
        jel.uzenet = "Megszakítva. %d fájl átment. A többi folytatható." % jel.kesz_fajlok
        jelents(jel)
        return jel
    jel.kesz = True
    jel.fazis = "vege"
    jel.megszakitva = False
    if jel.hibak:
        jel.uzenet = "Kész, %d hibával. %d fájl átment." % (
            len(jel.hibak), jel.kesz_fajlok)
    else:
        ige = "átmásolva" if muvelet == "masol" else "áthelyezve"
        jel.uzenet = "Kész. %d fájl %s." % (jel.kesz_fajlok, ige)
    jelents(jel)
    return jel


def _szol(jel: Jelentes, jelents) -> None:
    if jel.fazis == "visz" and jel.kezdet and jel.kesz_bajtok and jel.bajtok > jel.kesz_bajtok:
        eltelt = time.monotonic() - jel.kezdet
        if eltelt >= 1:
            jel.hatra_mp = (jel.bajtok - jel.kesz_bajtok) / (jel.kesz_bajtok / eltelt)
    if jel.fazis != "vege":
        jel.uzenet = jel.helyzet()
    jelents(jel)


def _keszult(forras, keszek, mentes) -> None:
    if keszek is None:
        return
    keszek.add(_norm(forras))
    if mentes:
        mentes(sorted(keszek))


def _szamol(ut, jel: Jelentes, cancel, keszek, jelents) -> None:
    if cancel():
        raise Megszakitva()
    if os.path.isfile(ut):
        if _norm(ut) not in keszek:
            jel.fajlok += 1
            jel.bajtok += _meret(ut)
        return
    for gyoker, mappak, fajlok in os.walk(ut):
        if cancel():
            raise Megszakitva()
        mappak[:] = [m for m in mappak if not _csatolas(os.path.join(gyoker, m))]
        for nev in fajlok:
            teljes = os.path.join(gyoker, nev)
            if _csatolas(teljes) or _norm(teljes) in keszek:
                continue
            jel.fajlok += 1
            jel.bajtok += _meret(teljes)
            if jel.fajlok % 200 == 0:
                _szol(jel, jelents)


def _egy_gyoker(ut, cel, muvelet, utkozes, jel, jelents, cancel,
                keszek, mentes, folytat) -> None:
    if cancel():
        raise Megszakitva()
    nev = os.path.basename(ut.rstrip("\\/"))
    cel_ut = os.path.join(cel, nev)
    if os.path.isfile(ut):
        _fajl(ut, cel_ut, muvelet, utkozes, jel, jelents, cancel,
              keszek, mentes, folytat)
        return
    if (muvelet == "athelyez" and not os.path.exists(cel_ut)
            and _azonos_meghajto(ut, cel)):
        if cancel():
            raise Megszakitva()
        try:
            os.rename(ut, cel_ut)
        except OSError as exc:
            jel.hibak.append("%s: %s" % (ut, exc))
            _szol(jel, jelents)
            return
        n, b = _fa(ut if os.path.exists(ut) else cel_ut)
        jel.kesz_fajlok += n
        jel.kesz_bajtok += b
        jel.most = nev
        jel.uzenet = "Áthelyezve a helyén: %s" % nev
        _szol(jel, jelents)
        return
    os.makedirs(cel_ut, exist_ok=True)
    for gyoker, mappak, fajlok in os.walk(ut):
        if cancel():
            raise Megszakitva()
        bent = [m for m in mappak if not _csatolas(os.path.join(gyoker, m))]
        for m in mappak:
            if m not in bent:
                jel.hibak.append("Átugorva, mert csatolás: %s" % os.path.join(gyoker, m))
        mappak[:] = bent
        rel = os.path.relpath(gyoker, ut)
        ide = cel_ut if rel == "." else os.path.join(cel_ut, rel)
        os.makedirs(ide, exist_ok=True)
        for fajlnev in fajlok:
            forras = os.path.join(gyoker, fajlnev)
            if _csatolas(forras):
                jel.hibak.append("Átugorva, mert csatolás: %s" % forras)
                continue
            _fajl(forras, os.path.join(ide, fajlnev), muvelet, utkozes,
                  jel, jelents, cancel, keszek, mentes, folytat)


def _fajl(forras, cel, muvelet, utkozes, jel, jelents, cancel,
         keszek, mentes, folytat) -> None:
    if cancel():
        raise Megszakitva()
    if _norm(forras) in keszek:
        return
    cel = _utkozes(cel, utkozes)
    if cel is None:
        jel.kesz_fajlok += 1
        jel.kesz_bajtok += _meret(forras)
        jel.most = os.path.basename(forras)
        jel.uzenet = "Kihagyva, mert már megvan: %s" % jel.most
        _keszult(forras, keszek, mentes)
        _szol(jel, jelents)
        return
    jel.most = os.path.basename(forras)
    _szol(jel, jelents)
    if (muvelet == "athelyez" and not os.path.exists(cel)
            and _azonos_meghajto(forras, os.path.dirname(cel) or cel)):
        try:
            os.makedirs(os.path.dirname(cel), exist_ok=True)
            os.rename(forras, cel)
        except OSError as exc:
            jel.hibak.append("%s: %s" % (forras, exc))
        else:
            meret = _meret(cel)
            jel.kesz_fajlok += 1
            jel.kesz_bajtok += meret
            _keszult(forras, keszek, mentes)
        _szol(jel, jelents)
        return
    resz = cel + ".superdl-resz"
    elotte = jel.kesz_bajtok
    try:
        _masol_darabonkent(forras, resz, jel, jelents, cancel, folytat)
        _atiras(resz, cel)
        _ido(forras, cel)
        if muvelet == "athelyez":
            os.remove(forras)
    except Megszakitva:
        jel.kesz_bajtok = elotte
        raise
    except OSError as exc:
        jel.kesz_bajtok = elotte
        _torol(resz)
        jel.hibak.append("%s: %s" % (forras, exc))
        _szol(jel, jelents)
        return
    jel.kesz_fajlok += 1
    _keszult(forras, keszek, mentes)
    _szol(jel, jelents)


def _ellenorzott_keszek(gyokerek, cel, keszek, cancel):
    ellenorzott = set()
    for gyoker in gyokerek:
        for forras in keszek:
            if cancel():
                raise Megszakitva()
            if forras == _norm(gyoker):
                rel = os.path.basename(gyoker)
            elif os.path.isdir(gyoker) and _belul(forras, gyoker):
                rel = os.path.join(os.path.basename(gyoker), os.path.relpath(forras, gyoker))
            else:
                continue
            target = os.path.join(cel, rel)
            try:
                meret = os.path.getsize(forras)
                if (not _csatolas(target) and os.path.getsize(target) == meret
                        and _resz_egyezik(forras, target, meret, cancel)):
                    ellenorzott.add(forras)
            except OSError:
                continue
    return ellenorzott


def _resz_egyezik(forras, resz, hossz, cancel) -> bool:
    """Csak a jelenlegi forrással egyező részfájlt szabad folytatni."""
    with open(forras, "rb") as be, open(resz, "rb") as ellen:
        while hossz:
            if cancel():
                raise Megszakitva()
            meret = min(DARAB, hossz)
            darab = be.read(meret)
            if len(darab) != meret or darab != ellen.read(meret):
                return False
            hossz -= meret
    return True


def _masol_darabonkent(forras, cel, jel, jelents, cancel, folytat) -> None:
    os.makedirs(os.path.dirname(cel), exist_ok=True)
    varhato = _meret(forras)
    megvan = 0
    if os.path.exists(cel):
        megvan = os.path.getsize(cel)
        if (not folytat or megvan > varhato
                or not _resz_egyezik(forras, cel, megvan, cancel)):
            os.remove(cel)
            megvan = 0
        elif megvan == varhato:
            jel.kesz_bajtok += megvan
            return
    mod = "ab" if megvan else "wb"
    jel.kesz_bajtok += megvan
    with open(forras, "rb") as be, open(cel, mod) as ki:
        if megvan:
            be.seek(megvan)
        while True:
            if cancel():
                raise Megszakitva()
            darab = be.read(DARAB)
            if not darab:
                break
            ki.write(darab)
            megvan += len(darab)
            jel.kesz_bajtok += len(darab)
            if megvan == len(darab) or megvan == varhato or megvan % (DARAB * 8) < DARAB:
                _szol(jel, jelents)
    if megvan != varhato:
        raise OSError("A másolat mérete nem egyezik a forráséval.")


def _utkozes(cel, utkozes):
    if not os.path.exists(cel):
        return cel
    if utkozes == "kihagy":
        return None
    if utkozes == "felulir":
        return cel
    torzs, kit = os.path.splitext(cel)
    n = 2
    while True:
        jelolt = "%s (%d)%s" % (torzs, n, kit)
        if not os.path.exists(jelolt):
            return jelolt
        n += 1
        if n > 9999:
            raise OSError("Nincs szabad név: %s" % cel)


def _atiras(resz, cel) -> None:
    if os.path.exists(cel):
        _irhato(cel)
    os.replace(resz, cel)


def _irhato(ut) -> None:
    try:
        os.chmod(ut, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _ido(forras, cel) -> None:
    try:
        shutil.copystat(forras, cel, follow_symlinks=False)
    except OSError:
        pass


def _azonos_meghajto(a, b) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def _fa(ut) -> tuple[int, int]:
    if os.path.isfile(ut):
        return 1, _meret(ut)
    n = b = 0
    for gyoker, _mappak, fajlok in os.walk(ut):
        for nev in fajlok:
            n += 1
            b += _meret(os.path.join(gyoker, nev))
    return n, b


def _meret(ut) -> int:
    try:
        return os.path.getsize(ut)
    except OSError:
        return 0


def _csatolas(ut) -> bool:
    try:
        adat = os.lstat(ut)
    except OSError:
        return False
    if stat.S_ISLNK(adat.st_mode):
        return True
    return bool(getattr(adat, "st_file_attributes", 0) & _UJRA)


def beillesztes_oka(forrasok, cel) -> str:
    """Üres szöveg, ha a másik ág célja biztonságos. Különben egy mondat."""
    if not forrasok:
        return "A vágólap üres. A Ctrl+C másol, a Ctrl+X kivág."
    if not cel:
        return "A másik ágon előbb lépj be egy mappába."
    cel_abs = os.path.abspath(cel)
    for nyers in forrasok:
        if not os.path.exists(nyers):
            return "A vágólapon lévő elem már nincs meg."
        ut = os.path.abspath(nyers)
        cel_ut = os.path.join(cel_abs, os.path.basename(ut.rstrip("\\/")))
        if _azonos(ut, cel_ut):
            return ("A cél ugyanaz a mappa, mint a forrás: %s. "
                    "A beillesztés a másik ág mappájába megy." % cel_abs)
        if _belul(ut, cel_abs) or (os.path.isdir(ut) and _belul(ut, cel_ut)):
            return "A cél a forrás belsejében van. Ezt nem viszem át."
    return ""


def folyamat_szoveg(muvelet: str, jel: Jelentes) -> str:
    """Kimondható mondat: másolás vagy áthelyezés, és hogy hol tart."""
    ige = "Áthelyezés" if muvelet == "athelyez" else "Másolás"
    if jel.kesz:
        return jel.uzenet or jel.helyzet()
    if jel.fazis == "szamol":
        return "Számlálás. %s folyik. Eddig %d fájl." % (ige, jel.fajlok)
    if jel.fazis == "terv":
        return jel.uzenet or jel.helyzet()
    return "%s folyik. %s" % (ige, jel.helyzet())


def vagolap_mondat(muvelet: str, oldal: str, mappa_nev: str, darab: int = 1) -> str:
    """A kijelölt elemek a másik ág mappájába mennek. oldal: bal vagy jobb."""
    elem = "%d elem" % darab
    if muvelet == "athelyez":
        return ("Kivágás. %s a vágólapon. Áthelyezés lesz, a forrás csak "
                "a kész másolat után törlődik. A cél a %s oldal: %s."
                % (elem, oldal, mappa_nev))
    return "Másolás. %s a vágólapon. A cél a %s oldal: %s." % (elem, oldal, mappa_nev)


def _azonos(a, b) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _belul(szulo, gyerek) -> bool:
    szulo = os.path.normcase(os.path.abspath(szulo))
    gyerek = os.path.normcase(os.path.abspath(gyerek))
    if szulo == gyerek:
        return True
    try:
        return os.path.commonpath([szulo, gyerek]) == szulo
    except ValueError:
        return False


def _ures_mappak(ut) -> None:
    for gyoker, mappak, fajlok in os.walk(ut, topdown=False):
        if not mappak and not fajlok:
            try:
                os.rmdir(gyoker)
            except OSError:
                pass


def meret_szoveg(bajt: int) -> str:
    if bajt < 1024 * 1024:
        return "%d kilobájt" % max(1, bajt // 1024) if bajt else "0 bájt"
    if bajt < 1024 * 1024 * 1024:
        return "%.1f megabájt" % (bajt / (1024 * 1024))
    return "%.1f gigabájt" % (bajt / (1024 * 1024 * 1024))


def ido_szoveg(mp: float | None) -> str:
    if mp is None:
        return "a hátralévő idő még nem becsülhető"
    mp = max(0, int(mp))
    if mp < 45:
        return "kevesebb mint egy perc van hátra"
    perc = max(1, round(mp / 60))
    if perc < 60:
        return "körülbelül %d perc van hátra" % perc
    ora, maradek = divmod(perc, 60)
    return "körülbelül %d óra %d perc van hátra" % (ora, maradek)


def _norm(ut: str) -> str:
    return os.path.normcase(os.path.abspath(ut))


def menet_fajl() -> Path:
    return Path.home() / ".superdl" / "fajlok" / "menet.json"


def menet_olvas() -> dict | None:
    ut = menet_fajl()
    if not ut.is_file():
        return None
    try:
        return json.loads(ut.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def menet_ir(forrasok, cel, muvelet, utkozes, keszek) -> None:
    ut = menet_fajl()
    ut.parent.mkdir(parents=True, exist_ok=True)
    adat = {
        "forrasok": [_norm(u) for u in forrasok],
        "cel": _norm(cel),
        "muvelet": muvelet,
        "utkozes": utkozes,
        "keszek": list(keszek),
    }
    ut.write_text(json.dumps(adat, ensure_ascii=False, indent=2), encoding="utf-8")


def menet_torol() -> None:
    try:
        menet_fajl().unlink()
    except OSError:
        pass


def menet_ugyanaz(adat, forrasok, cel, muvelet) -> bool:
    if not adat:
        return False
    return (adat.get("muvelet") == muvelet
            and adat.get("cel") == _norm(cel)
            and adat.get("forrasok") == [_norm(u) for u in forrasok])


def _torol(ut) -> None:
    try:
        if os.path.exists(ut):
            os.remove(ut)
    except OSError:
        pass
