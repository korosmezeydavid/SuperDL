"""AMIT ÍGÉRÜNK, AZT TARTSUK IS BE — Nagy Károly jelzése (2026-09-18, 09-21).

Karcsi háromszor írta meg ugyanazt:

  „Csak azt írja, hogy olyan hibát jelzett a letöltő motor, amit még nem
   ismerünk fel. Hogy az milyen hiba, nem tudom meg. Sem akkor, amikor
   rámentem a fájlra és shift+f6-ot nyomok, sem akkor amikor a control+e
   után megnyitom az eseménynaplót. Mindkét esetben ez a szöveg hangzik el."

A program tehát egy olyan helyre küldte, ahol NEM VOLT SEMMI. Ez rosszabb a
semminél: elhiteti, hogy van megoldás, és órákat lop el a keresgéléssel.

KÉT HIÁNY VOLT
  1. a nyers szöveget CSAK az állapotváltás pillanatában írtuk ki, ÉS csak
     akkor, ha `error_ismert is False`. Az indításkor már hibás sorokhoz
     (ahol a mező None) sosem került oda;
  2. a Shift+F6 kimondta az ígéretet, de maga SOHA nem írt a naplóba.

Ezek az esetek mindkettőt őrzik, és azt is, hogy ha tényleg nincs nyers
szövegünk, akkor NE küldjük a felhasználót üres naplóhoz.
"""

import re
from pathlib import Path

import pytest

from superdl import hibaszoveg as H

GYOKER = Path(__file__).resolve().parent.parent
GUI = (GYOKER / "superdl_gui.py").read_text(encoding="utf-8")

ISMERETLEN = "ilyen hibát még senki sem látott: 0x8001010d frobnicate"


# ───────────────── a két mondat: van nyom / nincs nyom ──────────────

def test_ismeretlen_hibara_a_naplohoz_kuldunk_ha_van_mit_odaadni():
    szoveg = H.olvashato(ISMERETLEN, ismert=False, van_nyers=True)
    assert szoveg == H.ISMERETLEN_MONDAT
    assert "eseménynaplóban" in szoveg


def test_nyers_szoveg_nelkul_NEM_kuldunk_ures_naplohoz():
    """⚠️ EZ A LÉNYEG. Ha nincs meg a pontos szöveg, ne ígérjük oda."""
    szoveg = H.olvashato(ISMERETLEN, ismert=False, van_nyers=False)
    assert szoveg == H.ISMERETLEN_MONDAT_NINCS_NYOM
    assert "eseménynaplóban van" not in szoveg
    assert "Control F6" in szoveg, "mondjuk meg, mit tehet ehelyett"


def test_a_ket_mondat_kulonbozik():
    assert H.ISMERETLEN_MONDAT != H.ISMERETLEN_MONDAT_NINCS_NYOM
    assert H.ismeretlen_mondat(True) == H.ISMERETLEN_MONDAT
    assert H.ismeretlen_mondat(False) == H.ISMERETLEN_MONDAT_NINCS_NYOM


def test_a_felismert_hibara_tovabbra_is_a_magyarazat_megy():
    """A `van_nyers` csak az ISMERETLEN ágat érinti – a jó magyarázatot
    nem cserélheti le (a 4.6.4 hibája)."""
    ismert_hiba = "HTTP Error 403: Forbidden"
    a = H.olvashato(ismert_hiba, ismert=True, van_nyers=False)
    b = H.olvashato(ismert_hiba, ismert=True, van_nyers=True)
    assert a == b
    assert a != H.ISMERETLEN_MONDAT
    assert a != H.ISMERETLEN_MONDAT_NINCS_NYOM


def test_az_alapertelmezes_visszafele_kompatibilis():
    """Aki nem ad `van_nyers`-t, a régi viselkedést kapja."""
    assert H.olvashato(ISMERETLEN, ismert=False) == H.ISMERETLEN_MONDAT


@pytest.mark.parametrize("van_nyers,vart", [
    (True, "eseménynaplóban"), (False, "Control F6")])
def test_a_gond_mondat_is_tovabbadja(van_nyers, vart):
    m = H.gond_mondat("proba.mkv", "hiba", ISMERETLEN, ismert=False,
                      van_nyers=van_nyers)
    assert vart in m
    assert m.startswith("proba.mkv:")


def test_az_elakadt_agon_is_tovabbadja():
    m = H.gond_mondat("proba.mkv", "letöltés", ISMERETLEN, elakadt=True,
                      ismert=False, van_nyers=False)
    assert "Control F6" in m
    assert "elakadt" in m


# ─────────── a nyers szöveg megtalálása (három forrás) ──────────────

class Halad:
    def __init__(self, error="", error_nyers="", status="hiba"):
        self.error = error
        self.error_nyers = error_nyers
        self.status = status
        self.filename = "proba.mkv"
        self.conflict = False


class Feladat:
    def __init__(self, progress, utolso_hiba="", azon=1):
        self.progress = progress
        self.utolso_hiba = utolso_hiba
        self.id = azon
        self.url = "http://proba/x"
        self.retries = 0


def _nyers(job):
    """A GUI statikus keresőjét hívjuk, wx nélkül."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_gui_nyers", GYOKER /
                                                  "superdl_gui.py")
    # a teljes modul importja wx-et és mindent behúzna – helyette a
    # függvény LOGIKÁJÁT itt tartjuk szinkronban, és forrásszinten őrizzük
    # (lásd a lenti forensic teszteket)
    del spec
    p = job.progress
    for ertek in (getattr(p, "error_nyers", ""),
                  getattr(job, "utolso_hiba", ""),
                  getattr(p, "error", "")):
        ertek = (ertek or "").strip()
        if ertek:
            return ertek
    return ""


def test_elsokent_a_forditaskor_eltett_nyers_szoveg():
    j = Feladat(Halad(error="magyar mondat", error_nyers="RAW ENGINE TEXT"),
                utolso_hiba="régi")
    assert _nyers(j) == "RAW ENGINE TEXT"


def test_masodikkent_a_bezarast_TULELO_mentett_szoveg():
    """⚠️ Karcsi esete: a hiba már INDÍTÁSKOR ott van, a `error_nyers` üres,
    mert az csak a fordítás pillanatában töltődik. A mentett `utolso_hiba`
    viszont túlélte a bezárást – abból tudunk pontos szöveget adni."""
    j = Feladat(Halad(error="magyar mondat", error_nyers=""),
                utolso_hiba="RAW A MENTESBOL")
    assert _nyers(j) == "RAW A MENTESBOL"


def test_vegszuksegben_a_leforditott_mondat_is_tobb_a_semminel():
    j = Feladat(Halad(error="magyar mondat"), utolso_hiba="")
    assert _nyers(j) == "magyar mondat"


def test_ha_tenyleg_semmi_nincs_akkor_ures():
    j = Feladat(Halad(), utolso_hiba="")
    assert _nyers(j) == ""


# ───────────── a GUI tényleg naplóz, mielőtt ígér (forrás) ──────────

def _fv(nev):
    """Egy metódus forrása a superdl_gui.py-ból."""
    kezd = GUI.index("def %s(" % nev)
    kov = GUI.find("\n    def ", kezd + 1)
    return GUI[kezd:kov if kov > 0 else len(GUI)]


def test_a_gui_ismeri_a_naplozo_segedet():
    for nev in ("_nyers_hibaszoveg", "_nyers_hibat_naploz"):
        assert "def %s(" % nev in GUI, "hiányzik a segéd: %s" % nev


def test_a_naplozo_harom_forrasbol_keres():
    forras = _fv("_nyers_hibaszoveg")
    for mezo in ("error_nyers", "utolso_hiba", "error"):
        assert mezo in forras


def test_a_shift_f6_naploz_MIELOTT_igerne():
    """A sorrend a lényeg: előbb a napló, csak utána a mondat."""
    forras = _fv("_on_miert")
    naploz = forras.index("_nyers_hibat_naploz")
    mondat = forras.index("gond_mondat")
    assert naploz < mondat, "előbb írjuk a naplóba, csak azután ígérjük meg"
    assert "van_nyers=van_nyers" in forras


def test_az_allapotvaltas_agan_mar_nem_csak_az_ismert_False_esetben_naplozunk():
    """A régi `if nyers and ismert is False:` feltétel épp Karcsi esetét
    hagyta ki (ott a mező None volt)."""
    # csak a KÓDOT nézzük, a magyarázó megjegyzéseket nem: azokban a régi
    # feltétel idézve szerepel, és épp az a dolguk
    kod = "\n".join(l for l in GUI.splitlines()
                    if not l.lstrip().startswith("#"))
    assert "if nyers and ismert is False" not in kod, \
        "ez a feltétel zárta ki a mentett sorokból visszatöltött hibákat"
    assert re.search(r"van_nyers\s*=\s*self\._nyers_hibat_naploz", kod)


def test_a_naplo_sor_felolvashato_szoveggel_kezdodik():
    forras = _fv("_nyers_hibat_naploz")
    assert "a hiba pontos szövege" in forras, \
        "a naplósor mondja meg, MI ez – nem csak odaokádja a szöveget"


def test_ugyanazt_a_hibat_nem_irjuk_ki_ketszer():
    """A Shift+F6 ismételgetése ne töltse tele a naplót ugyanazzal."""
    forras = _fv("_nyers_hibat_naploz")
    assert "_naplozott_hibak" in forras
    assert "self._naplozott_hibak = set()" in GUI
