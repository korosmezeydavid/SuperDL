# -*- coding: utf-8 -*-
"""Szerencsekerék (SAJÁT, kerék-és-szó játék) tesztjei. A tiszta segéd-
függvényeket közvetlenül ellenőrizzük; a teljes partit egy-egy bot játssza:
egy „megfejtő" ember (ismert rejtvényre), és egy passzív ember a gép ellen."""
import importlib
import random

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
S = importlib.import_module(BASE + ".jatekok.sajat")
KAT = importlib.import_module(BASE + ".katalogus")


# ---- tiszta segédfüggvények

def test_szk_maganhangzo():
    assert S._szk_maganhangzo("a") and S._szk_maganhangzo("á")
    assert S._szk_maganhangzo("ő") and S._szk_maganhangzo("ü")
    assert not S._szk_maganhangzo("b")
    assert not S._szk_maganhangzo("sz")      # nem egy betű


def test_szk_elofordul_es_egyezik():
    assert S._szk_elofordul("Lecsó", "l") == 1     # kis/nagybetű nem számít
    assert S._szk_elofordul("Lecsó", "c") == 1
    assert S._szk_elofordul("Lecsó", "ó") == 1
    assert S._szk_elofordul("Lecsó", "o") == 0     # ékezet SZÁMÍT a magánhangzónál
    assert S._szk_egyezik("lecso", "Lecsó")        # megfejtés: laza (ékezet/kis-nagy)
    assert S._szk_egyezik("  Ki korán kel aranyat lel ", "Ki korán kel aranyat lel")
    assert not S._szk_egyezik("valami más", "Lecsó")


def test_szk_tabla_es_kerek():
    assert "üres" in S._szk_tabla("Ló", set())
    t = S._szk_tabla("Ló", {"l"})
    assert "L" in t and "üres" in t              # az L felfedve, az Ó még rejtve
    # a kerék érvényes mezőt ad
    for _ in range(50):
        m = S._szk_porget()
        assert m[0] in ("penz", "csod", "passz")
        if m[0] == "penz":
            assert m[1] in S._SZK_MEZOK
    # a gép BÁRMILYEN betűt tippelhet (magánhangzót is) – a leggyakoribb az „e"
    assert S._szk_gep_betu(set()) == "e"
    assert S._szk_gep_betu({"e", "a"}) == "t"      # a következő gyakori


# ---- teljes parti: ember megfejti (ismert rejtvény)

def test_szerencsekerek_ember_megfejt(monkeypatch):
    monkeypatch.setattr(S, "_szk_valaszt", lambda r: ("Étel és ital", "Lecsó"))

    def bot(k, ki):
        kl = k.lower()
        if "hány ember" in kl:
            return "1"
        if "hány gép" in kl:
            return "0"
        if "játékos neve" in kl:
            return "Anna"
        if "mit lépsz" in kl:
            return "M"
        if "teljes megfejtést" in kl:
            return "Lecsó"
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=200000)
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "SZERENCSEKERÉK" in txt.upper()
    assert "Anna megfejtette a rejtvényt: Lecsó" in txt
    assert "győztes: Anna" in txt
    # szólt-e hang (a főcím + effektek „effekt" parancsként jelennek meg)
    assert any(t == "effekt" for t, _ in ki)


# ---- teljes parti: passzív ember a gép ellen (a gép old meg)

def test_szerencsekerek_gep_ellen_lezarul():
    random.seed(20260802)

    def bot(k, ki):
        kl = k.lower()
        if "hány ember" in kl:
            return "1"
        if "hány gép" in kl:
            return "1"                       # egy gép-ellenfél szálljon be
        if "okosak" in kl:
            return "3"                       # profi gép – gyorsan megold
        if "játékos neve" in kl:
            return "Én"
        if "mit lépsz" in kl:
            return "P"
        if "mondj egy betűt" in kl:
            return "s"
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=400000)
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "Vége a játéknak!" in txt and "győztes" in txt.lower()


def test_szerencsekerek_maganhangzo_is_tippelheto(monkeypatch):
    """ÚJ mechanika: pörgetésnél BÁRMILYEN betű mondható (magánhangzó is), és
    találatra pénzt hoz."""
    monkeypatch.setattr(S, "_szk_valaszt", lambda r: ("Étel és ital", "Lecsó"))

    lepesek = {"i": 0}

    def bot(k, ki):
        kl = k.lower()
        if "hány ember" in kl:
            return "2"                       # 2 ember
        if "hány gép" in kl:
            return "0"                       # nincs gép
        if "játékos neve" in kl:
            return "Béla" if "2." in k else "Anna"
        if "mit lépsz" in kl:
            return "P"                       # pörgetés
        if "mondj egy betűt" in kl:
            lepesek["i"] += 1
            return "e"                       # MAGÁNHANGZÓT tippel! (Lecsó → 1 db e)
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=400000)
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    # a magánhangzó találatot ér és pénzt hoz (nem utasítja el)
    assert "Van benne 1 darab E! Kaptál" in txt


def test_szunet_es_effekt_var_parancsok():
    """Új ctx-parancsok mindkét Ctx-ben: `szunet` (várakozás) és `effekt_var`
    (effekt + a végének kivárása). A hang-hossz mérése a KONZOLban van (a játék-
    modul nem használ subprocess-t)."""
    assert U.Ctx().szunet(500) == ("szunet", 500)
    assert U.Ctx().effekt_var("csod") == ("effekt_var", "csod")
    JK = importlib.import_module(BASE + ".jatekkonzol")
    assert hasattr(JK, "_KonzolCtx")
    assert JK._KonzolCtx().effekt_var("csod") == ("effekt_var", "csod")
    import inspect
    # a pump kezeli mindkettőt (nem-blokkoló wx.CallLater-rel)
    pump = inspect.getsource(JK.JatekKonzol._pump)
    assert "szunet" in pump and "effekt_var" in pump
    # a mérés a konzolban (WAV-hang hossza a wave modullal)
    assert "def _hang_hossz_ms" in inspect.getsource(JK.JatekKonzol)


def test_gep_nehezseg_valaszthato():
    """A gépek okossága a játék elején választható (1 kezdő … 3 profi), és a
    KEZDŐ gép csak a legvégén old meg (kicsi küszöb, nincs korai megfejtés)."""
    import inspect
    assert "okosak legyenek a gépek" in inspect.getsource(S.jatek_szerencsekerek)
    gsrc = inspect.getsource(S._szk_gep_kor)
    assert "szint" in gsrc and "kuszob" in gsrc
    # az üdvözlő üzenetet kimondjuk ÉS megvárjuk (nem olvad rá a főcím-zene)
    jsrc = inspect.getsource(S.jatek_szerencsekerek)
    assert "_szk_mond(ctx, \"SZERENCSEKERÉK" in jsrc


def test_szerencsekerek_a_katalogusban_sajat():
    assert JR.van("szerencsekerek")
    j = KAT.keres("szerencsekerek")
    assert j is not None and j.retro is False
    assert "Szerencsekerék" == j.nev


def test_szerencsekerek_lekerdezesek(monkeypatch):
    """A „pénzem" és „többiek" beírás bármikor lekérdezi a pénzeket (nem lép)."""
    monkeypatch.setattr(S, "_szk_valaszt", lambda r: ("Étel és ital", "Lecsó"))
    allapot = {"n": 0}

    def bot(k, ki):
        kl = k.lower()
        if "hány ember" in kl:
            return "1"
        if "hány gép" in kl:
            return "0"
        if "játékos neve" in kl:
            return "Anna"
        if "mit lépsz" in kl:
            allapot["n"] += 1
            if allapot["n"] == 1:
                return "pénzem"
            if allapot["n"] == 2:
                return "többiek"
            return "M"
        if "teljes megfejtést" in kl:
            return "Lecsó"
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=200000)
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "a bankodban eddig" in txt
    assert "Mindenki pénze" in txt


def test_szerencsekerek_gep_beszol(monkeypatch):
    """A gép be is szól a többieknek (emberhez és géphez is)."""
    random.seed(3)
    monkeypatch.setattr(S, "_szk_valaszt",
                        lambda r: ("Étel és ital", "Gulyásleves"))

    def bot(k, ki):
        kl = k.lower()
        if "hány ember" in kl:
            return "1"
        if "hány gép" in kl:
            return "2"                       # két gép, hogy egymásnak is szólhassanak
        if "okosak" in kl:
            return "2"                       # közepes – sok kör, sok beszólás
        if "játékos neve" in kl:
            return "Te"
        if "mit lépsz" in kl:
            return "P"
        if "mondj egy betűt" in kl:
            return "x"                       # az ember mindig mellétippel → a gépeké a szó
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=400000)
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    fragmensek = ("bundázol", "csőd lesz", "izzadj", "malmomra", "ünnepelnék",
                  "kölcsön", "versz meg", "fordul a kocka", "súgtok össze",
                  "rád férne")
    assert any(f in txt for f in fragmensek)
    # a hangokat effekt_var-ral játsszuk (lejátszik + megvárja a végét)
    # a poénhoz nevetés (nevetes1/nevetes2)
    assert any(t == "effekt_var" and p in ("nevetes1", "nevetes2") for t, p in ki)
    # a játék végén taps
    assert any(t == "effekt_var" and p == "taps" for t, p in ki)
    # rossz tipp / csőd után csalódott közönség-hang (boo/awww/ooo)
    assert any(t == "effekt_var" and p in ("boo", "awww", "ooo") for t, p in ki)


def test_effekt_a_szerencsekerek_hang_mappat_is_nezi():
    """A konzol a bekötött szerencsekerek_hang mappát is keresi (WAV/MP3), nem csak
    a milliomos_hang-ot – a fájlkeresés a _hang_fajl segédben."""
    import inspect
    JK = importlib.import_module(BASE + ".jatekkonzol")
    src = inspect.getsource(JK.JatekKonzol._hang_fajl)
    assert "szerencsekerek_hang" in src
    assert ".mp3" in src
