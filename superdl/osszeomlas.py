# -*- coding: utf-8 -*-
"""ÖSSZEOMLÁS-NAPLÓ: ha a program „csak úgy kilép”, maradjon nyoma.

Miért kell: egy felhasználó azt jelezte, hogy a médiakonvertálóban, amikor a
fájlválasztóban megnyit egy könyvtárat, a program KILÉP. Ilyenkor nem Python-
hiba történik (azt elkapnánk és kimondanánk), hanem a folyamat natívan
összeomlik – tipikusan egy külső, a Windows fájlválasztójába beépülő
bővítmény (kodek-csomag, felhő-szinkron, vírusirtó) miatt. Ezt eddig
semmiből nem lehetett kideríteni: a program eltűnt, és kész.

A `faulthandler` pont ilyenkor segít: a natív összeomlás pillanatában kiírja,
melyik Python-sornál járt a program. Ebből kiderül, hogy a saját kódunkban
vagy egy külső rétegben (pl. a fájlválasztó megnyitásában) történt-e a baj.

A napló a felhasználó gépén marad, és NEM tartalmaz személyes adatot: csak
függvény- és fájlneveket a mi kódunkból.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

NAPLO = Path.home() / ".superdl" / "osszeomlas.log"
# Meddig olvastuk el a naplót a LEGUTÓBBI indulásunkkor. Enélkül nem lehet
# megkülönböztetni a tegnapi összeomlást a mostanitól: a napló hozzáfűzős,
# tehát ha csak azt néznénk, van-e benne összeomlás-nyom, a program élete
# végéig minden indulásnál riasztana ugyanarra az egy esetre. Az a
# figyelmeztetés pedig, ami mindig szól, ugyanannyit ér, mint a néma program.
_OLVASVA = Path.home() / ".superdl" / "osszeomlas_olvasva.txt"
_fajl = None
_uj_resz = ""          # ami a legutóbbi indulásunk ÓTA került a naplóba


def bekapcsol() -> bool:
    """Indításkor hívjuk. Igaz, ha sikerült bekapcsolni."""
    global _fajl
    if _fajl is not None:
        return True
    try:
        import faulthandler
        NAPLO.parent.mkdir(parents=True, exist_ok=True)
        _olvasatlan_beolvas()
        # „a" mód: a korábbi összeomlások is megmaradnak, hogy össze lehessen
        # hasonlítani őket
        _fajl = open(NAPLO, "a", encoding="utf-8", errors="replace")
        _fajl.write("\n=== SuperDL indult: %s (verzió: %s) ===\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), _verzio()))
        _fajl.flush()
        faulthandler.enable(file=_fajl, all_threads=True)
        return True
    except Exception:
        _fajl = None
        return False


def _olvasatlan_beolvas() -> None:
    """A napló ÚJ részének beolvasása, és a jelölő előretolása.

    A jelölőt MÉG A FEJLÉC KIÍRÁSA ELŐTT toljuk a fájl végére: a saját
    „SuperDL indult" sorunk nem újdonság, és ha benne maradna az új részben,
    a következő induláskor is „történt valami" látszatát keltené."""
    global _uj_resz
    try:
        meret = NAPLO.stat().st_size
    except OSError:
        _uj_resz = ""
        _jelolo_ir(0)
        return
    try:
        eddig = int(_OLVASVA.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        # ⚠️ NINCS JELÖLŐ: ez az ELSŐ indulás a frissítés után. Ilyenkor az
        # egész eddigi napló „újnak" látszana, és a hetekkel ezelőtti
        # összeomlásokra azt állítanánk, hogy „a LEGUTÓBBI futáskor" történt.
        # Ez hazugság, méghozzá pont az a fajta, ami ellen az egész funkció
        # készült: a felhasználó egy nem létező mai hibát kezdene keresni.
        # (szakember83 jelentése, 2026-09-10: nála pontosan ez történt.)
        # A régi nyomok NEM vesznek el – a hibajelentés továbbra is csatolja
        # őket –, csak nem riasztunk rájuk.
        _uj_resz = ""
        _jelolo_ir(meret)
        return
    # Ha a fájl ZSUGORODOTT (a felhasználó törölte), NE kezdjük elölről: a
    # törölt napló nem összeomlás. Csak a jelölőt igazítjuk a fájl végéhez.
    if eddig > meret:
        _uj_resz = ""
        _jelolo_ir(meret)
        return
    try:
        with open(NAPLO, encoding="utf-8", errors="replace") as f:
            f.seek(eddig)
            _uj_resz = f.read()
    except OSError:
        _uj_resz = ""
    _jelolo_ir(meret)


def _jelolo_ir(hol: int) -> None:
    try:
        _OLVASVA.parent.mkdir(parents=True, exist_ok=True)
        _OLVASVA.write_text(str(int(hol)), encoding="utf-8")
    except OSError:
        pass


def uj_osszeomlas() -> bool:
    """Történt-e összeomlás a program LEGUTÓBBI indulása óta?

    Erre azért van szükség, mert aki azt látja, hogy „csak bezáródott a
    program", annak eszébe sem jut hibajelentést írni — tehát a nyom, amit
    gondosan feljegyeztünk, örökre a gépén marad. Egyszer szólunk róla, és
    csak akkor, ha tényleg új."""
    return _osszeomlas_nyom(_uj_resz)


def _osszeomlas_nyom(szoveg: str) -> bool:
    return ("Windows fatal exception" in szoveg
            or "Fatal Python error" in szoveg
            or "Current thread" in szoveg)


def _verzio() -> str:
    try:
        from . import __version__
        return str(__version__)
    except Exception:
        return "ismeretlen"


def jegyzet(szoveg: str) -> None:
    """Nyom hagyása a naplóban KOCKÁZATOS művelet előtt.

    Így ha a program pont ott omlik össze, a napló utolsó sorából kiderül,
    mit csinált éppen – akkor is, ha a natív hiba nem hagy Python-vermet."""
    if _fajl is None:
        return
    try:
        _fajl.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), szoveg))
        _fajl.flush()
        os.fsync(_fajl.fileno())        # összeomláskor is legyen kiírva
    except Exception:
        pass


def naplo_szoveg(sorok: int = 200) -> str:
    """A napló vége – a diagnosztikai ablakhoz és a hibajelentéshez."""
    try:
        with open(NAPLO, encoding="utf-8", errors="replace") as f:
            tartalom = f.readlines()
    except OSError:
        return ""
    return "".join(tartalom[-int(sorok):])


_FEJLECEK = ("Windows fatal exception", "Fatal Python error",
             "Current thread", "Thread 0x")


def utolso_osszeomlas(max_sorok: int = 300) -> str:
    """A LEGUTÓBBI összeomlás TELJES nyoma – a fejlécétől a végéig.

    MIÉRT NEM ELÉG A SORFARK: a hibajelentés eddig `naplo_szoveg(80)`-at
    csatolt, vagyis a napló utolsó 80 sorát. Egy natív összeomlás nyoma
    viszont ennél hosszabb (minden szál verme), így a jelentésbe a nyom
    KÖZEPE került – pont az a fejléc maradt le róla, amiben a hiba KÓDJA van
    (`Windows fatal exception: code 0x...`). Dr. Kiss István 4.6.4-es
    jelentésében emiatt nem lehetett megmondani, mi ölte meg a programot:
    a verem látszott, az ok nem. Egy féllel elvágott bizonyíték rosszabb,
    mint a semmi, mert azt hisszük, hogy van bizonyítékunk.

    Ezért itt a napló VÉGÉTŐL visszafelé megkeressük a legutóbbi
    összeomlás-blokk kezdetét (az azt megelőző „SuperDL indult" sortól), és
    azt adjuk vissza egészben. Ha így is túl hosszú, az ELEJÉT tartjuk meg –
    ott van az ok –, és jelezzük, hogy rövidítettünk."""
    try:
        with open(NAPLO, encoding="utf-8", errors="replace") as f:
            sorok = f.read().splitlines()
    except OSError:
        return ""
    # hol kezdődik az utolsó összeomlás-nyom?
    kezdet = None
    for i in range(len(sorok) - 1, -1, -1):
        if any(j in sorok[i] for j in _FEJLECEK):
            kezdet = i
            break
    if kezdet is None:
        return ""
    # onnan még visszalépünk a blokkot nyitó „SuperDL indult" sorra, hogy
    # kiderüljön, MELYIK verzió omlott össze
    for i in range(kezdet, -1, -1):
        if "SuperDL indult" in sorok[i]:
            kezdet = i
            break
    blokk = sorok[kezdet:]
    if len(blokk) > max_sorok:
        blokk = blokk[:max_sorok] + [
            "… (a nyom hosszabb; a jelentés az ELEJÉT tartotta meg, "
            "mert az ok ott van)"]
    return "\n".join(blokk)


def fajlvalaszto_figyelese() -> None:
    """Minden NATÍV fájl-/mappaválasztó nyisson nyomot a naplóban.

    A `jegyzet()` évek óta megvan erre a célra, de SOHA nem hívta senki –
    ugyanaz a minta, mint magánál az összeomlás-naplónál. Pedig pont ez a
    hiányzó láncszem: a natív összeomlás vermében látszik, hogy a program a
    fájlválasztóban járt, de nem látszik, MELYIK mappában – márpedig ezeket a
    kilépéseket tipikusan a rendszer fájlválasztójába épülő idegen bővítmény
    okozza (bélyegkép-készítő, felhő-szinkron, vírusirtó), és az mappafüggő.

    Egyetlen helyen kötjük be, a `wx.FileDialog`/`wx.DirDialog` osztály
    `ShowModal`-jára – így a program mind a hetven hívási helye nyomot hagy,
    anélkül hogy hetven helyen kellene módosítani."""
    try:
        import wx
    except Exception:
        return
    for osztaly, nev in ((wx.FileDialog, "fájlválasztó"),
                         (wx.DirDialog, "mappaválasztó")):
        if getattr(osztaly, "_superdl_figyelt", False):
            continue
        eredeti = osztaly.ShowModal

        def burok(self, _eredeti=eredeti, _nev=nev):
            try:
                hol = self.GetDirectory() or self.GetPath() or ""
            except Exception:
                hol = ""
            jegyzet(f"NATÍV {_nev} megnyitása ({hol})")
            try:
                return _eredeti(self)
            finally:
                jegyzet(f"NATÍV {_nev} bezárva")

        try:
            osztaly.ShowModal = burok
            osztaly._superdl_figyelt = True
        except Exception:
            pass


def volt_osszeomlas() -> bool:
    """Van-e a naplóban natív összeomlás nyoma? (A faulthandler ezt a fejlécet
    írja ki.) BÁRMIKORI – a hibajelentéshez ez a jó kérdés; az indulási
    figyelmeztetéshez viszont az `uj_osszeomlas()`."""
    return _osszeomlas_nyom(naplo_szoveg(400))
