# -*- coding: utf-8 -*-
"""Super Mail: EGYESÍTETT bejövő + a LISTA SZÉLE.

Felhasználói jelzés (2026-08-15):
  1. „az összes bejövő nem dob be egy egyesített mappába, ahol minden levelemet
     látom, ha 10 email cím van is beállítva";
  2. „ha a legtetején vagyok a listának, újra és újra bemondja a legfelső
     levelet – ne tegye; mondja, hogy nincs feljebb, vagy egy pici bling".

A hálózati és wx-részeket nem szimuláljuk: a MAG rendezését és az ál-mappa
logikáját őrizzük itt, a felületet élő próbában ellenőriztem.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mail_core as MC          # noqa: E402
from mail_mod import hangok as H              # noqa: E402


def _lev(datum, targy):
    return {"datum": datum, "targy": targy}


# --------------------------------------------------- időrendi egyesítés

def test_a_legfrissebb_kerul_elore():
    """Ez a hiba lényege: eddig fiókonként egymás UTÁN jöttek a levelek, tehát
    a második fiók friss levele a első fiók régi levelei ALÁ került."""
    a = [_lev("Fri, 15 Aug 2026 08:00:00 +0200", "A-régi"),
         _lev("Fri, 15 Aug 2026 09:00:00 +0200", "A-újabb"),
         _lev("Fri, 15 Aug 2026 19:30:00 +0200", "B-legfrissebb"),
         _lev("Thu, 14 Aug 2026 22:00:00 +0200", "B-tegnapi")]
    assert [x["targy"] for x in MC.rendez_ido_szerint(a)] == [
        "B-legfrissebb", "A-újabb", "A-régi", "B-tegnapi"]


def test_kulonbozo_idozonak_helyesen_hasonlitodnak():
    """08:00 +0200 és 07:30 +0100 – utóbbi KÉSŐBB van UTC-ben."""
    a = [_lev("Fri, 15 Aug 2026 08:00:00 +0200", "budapesti"),
         _lev("Fri, 15 Aug 2026 07:30:00 +0100", "londoni")]
    assert [x["targy"] for x in MC.rendez_ido_szerint(a)] == ["londoni",
                                                              "budapesti"]


def test_hianyzo_vagy_rossz_datum_a_lista_vegere_kerul():
    a = [_lev("", "nincs dátum"),
         _lev("ez nem dátum", "rossz dátum"),
         _lev("Fri, 15 Aug 2026 08:00:00 +0200", "jó")]
    sorrend = [x["targy"] for x in MC.rendez_ido_szerint(a)]
    assert sorrend[0] == "jó", "a dátum nélküli levél ne kerüljön a frissek elé"
    assert set(sorrend[1:]) == {"nincs dátum", "rossz dátum"}


def test_a_rendezes_nem_veszit_es_nem_dublikal_levelet():
    a = [_lev("Fri, 15 Aug 2026 %02d:00:00 +0200" % (h % 24), "l%d" % h)
         for h in range(30)]
    assert len(MC.rendez_ido_szerint(a)) == 30
    assert {x["targy"] for x in MC.rendez_ido_szerint(a)} == {x["targy"] for x in a}


def test_ures_es_none_bemenet():
    assert MC.rendez_ido_szerint([]) == []
    assert MC.rendez_ido_szerint(None) == []


def test_idozona_nelkuli_datum_sem_dob_hibat():
    assert MC.datum_kulcs({"datum": "15 Aug 2026 08:00:00"}) > 0
    assert MC.datum_kulcs({}) == 0.0
    assert MC.datum_kulcs(None) == 0.0


# ------------------------------------------------------- az ál-mappa

def test_az_osszes_bejovo_almappa_neve_nem_utkozhet_valodi_mappaval():
    """A jelölő nem lehet olyan, amit egy IMAP-kiszolgáló mappaneve lehetne –
    különben egy „Összes bejövő" nevű valódi mappa elnyelné a nézetet."""
    assert "\x00" in MC.OSSZES_MAPPA
    assert MC.OSSZES_NEV and MC.OSSZES_NEV != MC.OSSZES_MAPPA


def test_az_osszes_bejovo_csak_tobb_fioknal_jelenik_meg():
    """Egy fióknál értelmetlen (és zavaró) az „összes fiók" nézet.
    (A felhasználó kérésére ez már NEM a mappalistában, hanem a
    FIÓK-VÁLASZTÓBAN van – lásd tests/test_mail_osszes_a_valasztoban.py.)"""
    from mail_mod import mailwin as MW

    class Csak:
        _fiokok = []
        _osszes_a_valasztoban = MW.MailFrame._osszes_a_valasztoban

    cs = Csak()
    assert cs._osszes_a_valasztoban() is False
    cs._fiokok = [{"email": "a@x.hu"}]
    assert cs._osszes_a_valasztoban() is False
    cs._fiokok = [{"email": "a@x.hu"}, {"email": "b@y.hu"}]
    assert cs._osszes_a_valasztoban() is True


# ------------------------------------------------------ szél-jelzőhang

def test_a_ket_szel_hang_kulonbozik(monkeypatch, tmp_path):
    """A teteje és az alja NE ugyanaz legyen: hallás után tudni kell, melyik
    végén állsz."""
    import wave
    monkeypatch.setattr(H, "_MAPPA", tmp_path)
    fent, lent = H.hang_fajl(True), H.hang_fajl(False)
    assert fent != lent and fent.read_bytes() != lent.read_bytes()
    for f in (fent, lent):
        with wave.open(str(f), "rb") as w:
            assert w.getnchannels() == 1
            # RÖVID legyen: a szélt gyors nyilazásnál sokszor eléri az ember
            assert w.getnframes() / w.getframerate() < 0.25


def test_a_bling_sosem_dob_hibat(monkeypatch):
    monkeypatch.setattr(H, "hang_fajl",
                        lambda teteje: (_ for _ in ()).throw(OSError("nincs")))
    assert H.bling(True) is False


# ------------------------------------------------ REGRESSZIÓ: a navigáció

class _HamisLista:
    """A levéllista LB_EXTENDED (többszörös kijelölés): ott a `GetSelection()`
    MÍNUSZ EGYET ad, akkor is, ha a felhasználó épp a lista közepén áll."""

    def __init__(self, n, kijelolt=(), extended=True):
        self._n, self._sel, self._ext = n, list(kijelolt), extended

    def GetCount(self):
        return self._n

    def GetSelections(self):
        return tuple(self._sel)

    def GetSelection(self):
        if self._ext:
            return -1                     # a wx pontosan így viselkedik
        return self._sel[0] if self._sel else -1


class _HamisBillentyu:
    def __init__(self, kod):
        self.kod, self.tovabb = kod, False

    def GetKeyCode(self):
        return self.kod

    def ShiftDown(self):
        return False

    def ControlDown(self):
        return False

    def Skip(self):
        self.tovabb = True


def test_lista_index_tobbszoros_kijelolesu_listan_is_helyes():
    from mail_mod import mailwin as MW
    ix = MW.MailFrame._lista_index
    assert ix(_HamisLista(5, [2])) == 2, "egy kijelölt sor: tudjuk, hol állunk"
    assert ix(_HamisLista(5, [])) == -1, "semmi kijelölve: NEM tudjuk"
    assert ix(_HamisLista(5, [1, 2])) == -1, "több kijelölt: NEM tudjuk"
    assert ix(_HamisLista(5, [3], extended=False)) == 3, "egyszerű lista is jó"


@pytest.mark.parametrize("kijelolt", [(), (0, 1)])
def test_ha_nem_tudjuk_hol_allunk_SOHA_nem_nyeljuk_el_a_nyilat(kijelolt):
    """EZ A REGRESSZIÓ: egy kiadásban a felfelé nyíl elnyelődött a levéllistán,
    mert a `GetSelection()` mínusz egyet adott – a navigáció megbénult."""
    import wx
    from mail_mod import mailwin as MW

    class Onallo:
        _lista_index = staticmethod(MW.MailFrame._lista_index)
        _lista_szel = MW.MailFrame._lista_szel
        jelzesek = []

        def _szel_jelzes(self, teteje, fajta):
            self.jelzesek.append(teteje)

    o = Onallo()
    for kod in (wx.WXK_UP, wx.WXK_DOWN):
        e = _HamisBillentyu(kod)
        o._lista_szel(e, _HamisLista(5, kijelolt), "level")
        assert e.tovabb is True, "a billentyűnek TOVÁBB kell mennie"
    assert not o.jelzesek, "és jelzés sem járhat ilyenkor"


def test_a_valodi_szeleken_viszont_elnyeljuk():
    import wx
    from mail_mod import mailwin as MW

    class Onallo:
        _lista_index = staticmethod(MW.MailFrame._lista_index)
        _lista_szel = MW.MailFrame._lista_szel

        def __init__(self):
            self.jelzesek = []

        def _szel_jelzes(self, teteje, fajta):
            self.jelzesek.append(teteje)

    o = Onallo()
    e = _HamisBillentyu(wx.WXK_UP)
    o._lista_szel(e, _HamisLista(5, [0]), "level")
    assert e.tovabb is False and o.jelzesek == [True]

    o = Onallo()
    e = _HamisBillentyu(wx.WXK_DOWN)
    o._lista_szel(e, _HamisLista(5, [4]), "level")
    assert e.tovabb is False and o.jelzesek == [False]

    # középen mindkét irány szabad
    for kod in (wx.WXK_UP, wx.WXK_DOWN):
        o = Onallo()
        e = _HamisBillentyu(kod)
        o._lista_szel(e, _HamisLista(5, [2]), "level")
        assert e.tovabb is True and not o.jelzesek
