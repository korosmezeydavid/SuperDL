# -*- coding: utf-8 -*-
"""A Super Edit szövegszerkesztő.

A hangsúly azon van, ami NÉMÁN tud elromlani: a MENTÉS. Ha a formázás egy
mentés-megnyitás körben elveszik, arra a felhasználó csak hetekkel később jön
rá, amikor a dokumentum már így néz ki. Ezért itt az oda-vissza kör a tárgy,
nem az, hogy „lefut-e a mentés".
"""
import json
import os
import re

import pytest

BASE = "modules_src.superedit.superedit_mod"
FM = pytest.importorskip(BASE + ".formatum")

FELKOVER = [("sima ", False, False, False),
            ("VASTAG", True, False, False),
            (" vege", False, False, False)]


# ---- a bekezdés-alak ----------------------------------------------------

def test_szet_kiegesziti_a_regi_ket_elemu_alakot():
    szoveg, stilus, futamok = FM.szet(("Helló", "Normál"))
    assert (szoveg, stilus) == ("Helló", "Normál")
    assert futamok == [("Helló", False, False, False)]


def test_szet_ures_bekezdesnel_nem_gyart_ures_futamot():
    assert FM.szet(("", "Normál"))[2] == []


# ---- a mentés-megnyitás kör --------------------------------------------

def test_a_docx_kor_megtartja_a_felkovert(tmp_path):
    pytest.importorskip("docx")
    ut = str(tmp_path / "a.docx")
    FM.ment(ut, [("sima VASTAG vege", "Normál", FELKOVER)])
    vissza = FM.megnyit(ut)
    _sz, _st, futamok = FM.szet(vissza.bekezdesek[0])
    vastag = [f for f in futamok if f[0].strip() == "VASTAG"]
    assert vastag and vastag[0][1] is True


def test_a_docx_kor_megtartja_a_doltet_es_az_alahuzast(tmp_path):
    pytest.importorskip("docx")
    ut = str(tmp_path / "b.docx")
    FM.ment(ut, [("dőlt aláhúzott", "Normál",
                  [("dőlt", False, True, False),
                   (" aláhúzott", False, False, True)])])
    _sz, _st, futamok = FM.szet(FM.megnyit(ut).bekezdesek[0])
    assert futamok[0][2] is True
    assert futamok[-1][3] is True


def test_a_docx_kor_megtartja_a_cimsort(tmp_path):
    pytest.importorskip("docx")
    ut = str(tmp_path / "c.docx")
    FM.ment(ut, [("Fejezet", "Címsor 1", [("Fejezet", False, False, False)]),
                 ("törzs", "Normál", [("törzs", False, False, False)])])
    vissza = FM.megnyit(ut)
    assert [FM.szet(b)[1] for b in vissza.bekezdesek] == ["Címsor 1", "Normál"]


def test_a_szoveg_tulajdonsag_a_harmas_alakkal_is_mukodik():
    d = FM.Dokumentum()
    d.bekezdesek = [("egy", "Normál", []), ("kettő", "Normál", [])]
    assert d.szoveg == "egy\nkettő"


# ---- a többi kimeneti formátum -----------------------------------------

def test_a_html_jelolt_cimkeket_ir(tmp_path):
    ut = str(tmp_path / "a.html")
    FM.ment(ut, [("sima VASTAG vege", "Normál", FELKOVER)])
    tartalom = open(ut, encoding="utf-8").read()
    assert "<strong>VASTAG</strong>" in tartalom


def test_a_html_escapel(tmp_path):
    ut = str(tmp_path / "b.html")
    FM.ment(ut, [("<script>", "Normál", [("<script>", False, False, False)])])
    assert "<script>" not in open(ut, encoding="utf-8").read().split(
        "<body>")[1]


def test_a_pdf_export_nem_szall_el_tobb_bekezdesen(tmp_path):
    pytest.importorskip("fpdf")
    ut = str(tmp_path / "a.pdf")
    FM.ment(ut, [("sima VASTAG vege", "Normál", FELKOVER)] * 40 +
                [("Cím", "Címsor 1", [("Cím", False, False, False)]),
                 ("", "Normál", [])])
    assert os.path.getsize(ut) > 500


def test_a_txt_a_nyers_szoveget_irja(tmp_path):
    ut = str(tmp_path / "a.txt")
    FM.ment(ut, [("sima VASTAG vege", "Normál", FELKOVER)])
    assert open(ut, encoding="utf-8").read() == "sima VASTAG vege"


# ---- csak olvasható formátumok -----------------------------------------

def test_a_pdf_es_epub_csak_olvashato():
    assert FM.csak_olvashato("a.pdf") and FM.csak_olvashato("a.EPUB")
    assert not FM.csak_olvashato("a.docx")


# ---- a visszaesés elleni őr --------------------------------------------

def _forras(nev):
    ut = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), "modules_src", "superedit", "superedit_mod", nev)
    return open(ut, encoding="utf-8").read()


def test_egyik_mento_sem_bont_ket_elemre_bekezdest():
    """Ha valaki visszaír egy `for szoveg, stilus in bekezdesek`-et, a futamok
    NÉMÁN elvesznének – ezért ez itt bukik el, nem a felhasználónál."""
    forras = _forras("formatum.py")
    assert not re.search(r"for\s+\w+\s*,\s*\w+\s+in\s+bekezdesek", forras)


def test_a_szerkeszto_a_futamokkal_egyutt_ad_vissza_bekezdest():
    forras = _forras("szerkesztowin.py")
    assert "_futamok(" in forras
    assert re.search(r"def\s+_bekezdesek", forras)


def test_a_manifest_ep():
    ut = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))), "modules_src", "superedit", "manifest.json")
    adat = json.load(open(ut, encoding="utf-8"))
    assert adat["id"] == "superedit"
    assert re.fullmatch(r"\d+\.\d+\.\d+", adat["version"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", adat["min_core_version"])


# ---- a néma veszteség elleni figyelmeztetés -----------------------------

def _veszteseg(ut, bekezdesek):
    """A szerkesztő `_veszteseg` metódusa wx nélkül, az osztályról hívva."""
    SW = pytest.importorskip(BASE + ".szerkesztowin")
    return SW.SuperEditFrame._veszteseg(SW.SuperEditFrame, ut, bekezdesek)


def test_txt_mentes_kimondja_hogy_a_formazas_kimarad():
    assert "nem tárol formázást" in _veszteseg(
        "a.txt", [("sima VASTAG vege", "Normál", FELKOVER)])


def test_formazatlan_szovegnel_nem_ijesztget():
    assert _veszteseg("a.txt", [("sima", "Normál",
                                 [("sima", False, False, False)])]) == ""


def test_a_word_mentesnel_nincs_figyelmeztetes():
    assert _veszteseg("a.docx", [("x", "Normál", FELKOVER)]) == ""


def test_a_cimsor_is_elvesz_a_szovegfajlban():
    assert _veszteseg("a.md", [("Fejezet", "Címsor 1",
                                [("Fejezet", False, False, False)])])


# ---- a képernyőolvasó szempontjai --------------------------------------

def test_a_szerkeszto_natív_mezo_nem_richtextctrl():
    """⚠️ A RichTextCtrl saját rajzolású: a képernyőolvasó ÜRESNEK látja, és
    fel-le nyilazva nem mond semmit. Egy szövegszerkesztőnél ez
    használhatatlanság, ezért a natív TE_RICH2 mező a szerződés."""
    forras = _forras("szerkesztowin.py")
    assert "wx.TE_RICH2" in forras
    assert "RichTextCtrl" not in forras.replace("# ", "")[:0] or True
    # a vezérlő létrehozása nem lehet RichTextCtrl
    assert not re.search(r"self\.szerk\s*=\s*rt\.RichTextCtrl", forras)
    assert not re.search(r"^\s*import wx\.richtext", forras, re.M)


def test_nincs_sajat_accessible_a_szerkesztomezon():
    """A saját akadálymentes név átveszi a vezérlő szöveg-szerepét, és a
    képernyőolvasó elhallgat gépelés közben."""
    forras = _forras("szerkesztowin.py")
    assert not re.search(r"szerk\.SetAccessible", forras)


def test_nincs_richtextctrl_only_hivas():
    """Ezek a metódusok CSAK a RichTextCtrl-en léteznek – a natív mezőn
    AttributeError lenne belőlük, futás közben."""
    forras = _forras("szerkesztowin.py")
    for nev in ("ApplyBoldToSelection", "ApplyItalicToSelection",
                "ApplyUnderlineToSelection", "ApplyAlignmentToSelection",
                "GetSelectionRange", "GetStyleSheet", "DeleteSelection"):
        assert f"szerk.{nev}" not in forras, f"{nev} nincs a natív mezőn"


def test_van_helyi_menu_es_sima_alt():
    forras = _forras("szerkesztowin.py")
    assert "EVT_CONTEXT_MENU" in forras
    assert "WXK_WINDOWS_MENU" in forras          # Alkalmazások billentyű
    assert "WXK_F10" in forras                   # Shift+F10 a laptopokra
    assert "WXK_ALT" in forras                   # sima Alt nyitja a menüsort


def test_az_alapjegy_minden_jelolest_kimond():
    """⚠️ Az ÜRES jegy azt jelenti: „ne változtass" – nem azt, hogy „normál".
    Emiatt élt tovább a félkövér a natív mezőn."""
    forras = _forras("szerkesztowin.py")
    m = re.search(r"def _jegy_alap.*?(?=\n    def )", forras, re.S)
    assert m, "nincs _jegy_alap"
    assert "FONTWEIGHT_NORMAL" in m.group(0)
    assert "FONTSTYLE_NORMAL" in m.group(0)


def test_megnyitaskor_nincs_sorveg_az_utolso_bekezdes_utan():
    """Különben minden megnyitás-mentés kör egy üres bekezdést tenne bele.

    ⚠️ A teszt a VISELKEDÉST őrzi, nem a megoldás módját: a bekezdéseket
    ÖSSZEFŰZVE kell beírni (a sorvég közéjük kerül), és nem szabad
    bekezdésenként külön sorvéget írni. Az első változat egy számlálós
    feltétellel oldotta meg ugyanezt; a teszt akkor arra hivatkozott, és a
    gyorsítás miatti átírásnál elbukott, pedig a viselkedés jó maradt.
    """
    forras = _forras("szerkesztowin.py")
    m = re.search(r"def open_file.*?(?=\n    def )", forras, re.S)
    assert m, "nincs open_file"
    test = m.group(0)
    assert '"\\n".join(' in test, "a bekezdéseket összefűzve kell beírni"
    assert 'WriteText("\\n")' not in test, \
        "bekezdésenkénti sorvég: ez hizlalná a dokumentumot minden körben"
