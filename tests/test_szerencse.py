"""Szerencsesüti (2026-09-27): érkezés 15 percenként, legfeljebb 3,
éjszakai csend, büntetés, bónusz, az üzenetfájl formája."""
import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "szerencse"))

from szerencse_mod import suti as S   # noqa: E402

MAPPA = Path(__file__).resolve().parents[1] / "modules_src" / "szerencse" \
    / "szerencse_mod"
NAP = dt.datetime(2026, 9, 27, 12, 0)
T0 = 1_000_000.0


def _uj(**kw):
    a = S.Allapot(**kw)
    u = S.uzenetek_betolt((MAPPA / "uzenetek.txt").read_text(encoding="utf-8"))
    return S.Suti(a, u, random.Random(1))


def test_uzenetfajl_minden_fajta_es_buntetes_ora():
    u = S.uzenetek_betolt((MAPPA / "uzenetek.txt").read_text(encoding="utf-8"))
    for fajta in S.SULYOK:
        assert len(u[fajta]) >= 10, fajta
    assert {x.orak for x in u["buntetes"]} == {1, 2, 10, 24}
    assert all(x.hang in ("",) + S.HANGOK for v in u.values() for x in v)


def test_formatum():
    u = S.uzenetek_betolt("[vicc]\nhaha |punch\n[buntetes]\n2: sztrájk\n"
                          "7: rossz óra\nnincs óra\n# megjegyzés\n[ismeretlen]\nx")
    assert u["vicc"][0].szoveg == "haha" and u["vicc"][0].hang == "punch"
    assert [(x.orak, x.szoveg) for x in u["buntetes"]] == [(2, "sztrájk")]


def test_erkezes_15_percenkent_max_3():
    s = _uj()
    assert s.lepes(T0, NAP) == 0                     # első: csak időzít
    assert s.lepes(T0 + 14 * 60, NAP) == 0
    assert s.lepes(T0 + 15 * 60, NAP) == 1 and s.a.varo == 1
    # a program két órára zárva volt: legfeljebb 3 gyűlik
    assert s.lepes(T0 + 3 * 3600, NAP) == 2 and s.a.varo == 3
    assert s.lepes(T0 + 4 * 3600, NAP) == 0 and s.a.varo == 3


def test_ejszakai_csend():
    assert S.csendben(dt.datetime(2026, 9, 27, 23, 10), "22:00", "08:00")
    assert S.csendben(dt.datetime(2026, 9, 27, 3, 0), "22:00", "08:00")
    assert not S.csendben(dt.datetime(2026, 9, 27, 8, 0), "22:00", "08:00")
    assert S.csendben(dt.datetime(2026, 9, 27, 13, 0), "12:30", "14:00")
    s = _uj()
    s.lepes(T0, NAP)
    assert s.lepes(T0 + 900, dt.datetime(2026, 9, 27, 23, 0)) == 0


def test_kibontas_buntetes_bonusz():
    s = _uj(varo=1)
    s.u["buntetes"] = [S.Uzenet("buntetes", "Mohó vagy!", "", 1)]
    s.rnd = random.Random()
    s.rnd.choices = lambda pop, weights=None: ["buntetes"] if "vicc" in pop else [1]
    u = s.kibont(T0)
    assert u.fajta == "buntetes" and s.a.varo == 0
    assert s.a.buntetes_ig == T0 + 3600
    assert "egy órára nincs süti" in s.teljes_szoveg(u)
    # büntetés alatt nem jön süti, és a várakozó szöveg megmondja
    s.a.kovetkezo = T0
    assert s.lepes(T0 + 1800, NAP) == 0
    assert "Büntetésben vagy" in s.varakozo_szoveg(T0 + 1800)
    assert s.kibont(T0 + 1800) is None
    # bónusz: még egy süti
    s2 = _uj(varo=1)
    s2.rnd.choices = lambda pop, weights=None: ["bonusz"]
    u2 = s2.kibont(T0)
    assert u2.fajta == "bonusz" and s2.a.varo == 1
    assert "Ctrl+Alt+S" in s2.teljes_szoveg(u2)


def test_nincs_suti_szoveg_es_allapot_mentes():
    s = _uj()
    s.lepes(T0, NAP)
    assert "perc" in s.varakozo_szoveg(T0 + 60)
    a = S.Allapot.szotarbol({"varo": 2, "csend_tol": "21:00", "ismeretlen": 1})
    assert a.varo == 2 and a.csend_tol == "21:00"
    assert S.Allapot.szotarbol(a.szotar()) == a
    assert S.perc_szoveg(3600 * 10) == "10 óra"
    assert S.ido_perc("25:00") is None and S.ido_perc("7") == 420


def test_hangfajl_ures_mappa_nem_hiba(tmp_path):
    assert S.hangfajl(tmp_path, "nyitas") is None
    (tmp_path / "punch").mkdir()
    assert S.hangfajl(tmp_path, "punch") is None


# --- süticsomagok a netről ---------------------------------------------------
TAROLO_CSOMAG = Path(__file__).resolve().parents[1] / "szerencse" \
    / "csomagok.txt"


def test_tarolo_csomagfajl_ervenyes_es_naptar():
    cs = S.csomagok_betolt(TAROLO_CSOMAG.read_text(encoding="utf-8"))
    assert len(cs) >= 4
    for c in cs:
        for v in c.uzenetek.values():
            for x in v:
                assert x.hang in ("",) + S.HANGOK
    nev = lambda d: (S.aktiv_csomag(cs, d) or S.Csomag("-", {})).nev  # noqa
    assert "adventi" in nev(dt.date(2026, 12, 5))
    assert "karácsonyi" in nev(dt.date(2027, 12, 25))
    assert "szilveszteri" in nev(dt.date(2026, 12, 31))
    assert "szilveszteri" in nev(dt.date(2027, 1, 1))
    assert "húsvéti" in nev(dt.date(2027, 3, 29))
    assert nev(dt.date(2026, 9, 27)) == "-"


def test_csomag_keveres_csere_es_bejelentes():
    szoveg = ("leírás, nem csomag\n[vicc]\nez se\n"
              "@nev: próba\n@mod: csere\n@udvozles: Hahó!\n[vicc]\nCSOMAGVICC\n"
              "@nev: üres\n")
    cs = S.csomagok_betolt(szoveg)
    assert [c.nev for c in cs] == ["próba"] and cs[0].csere
    s = _uj(varo=3)
    s.csomagok = cs
    s.ma = dt.date(2026, 9, 27)
    s.rnd.choices = lambda pop, weights=None: ["vicc"]
    assert s.kibont(T0).szoveg == "CSOMAGVICC"
    assert s.csomag_hir() == "Hahó!" and s.csomag_hir() == ""
    # a nem szereplő fajta a rendes sütikből jön
    s.rnd.choices = lambda pop, weights=None: ["bolcsesseg"]
    assert s.kibont(T0).szoveg != "CSOMAGVICC"
    # kikapcsolva: nincs csomag
    s.a.csomagok = False
    s.rnd.choices = lambda pop, weights=None: ["vicc"]
    assert s.kibont(T0).szoveg != "CSOMAGVICC"
    assert s.csomag_hir() == ""
