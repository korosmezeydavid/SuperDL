# -*- coding: utf-8 -*-
"""Távsegítség – az esemény-modell és a VEZÉRLÉS biztonsági kapujának tesztjei.

Valódi input-injektálás NÉLKÜL (nem mozgatjuk a kurzort, és nem-Windowson is
lefut): a Vezerlo alapból INAKTÍV, és inaktívan MINDENT figyelmen kívül hagy –
ez a legfontosabb biztonsági garancia."""
import importlib

BASE = "modules_src.tavsegitseg.tavsegitseg_mod"
V = importlib.import_module(BASE + ".vezerles")
SZ = importlib.import_module(BASE + ".szovegek")


def test_esemeny_epitok():
    assert V.e_mozog(0.5, 0.25) == {"t": "mozog", "x": 0.5, "y": 0.25}
    assert V.e_katt("jobb") == {"t": "katt", "gomb": "jobb"}
    assert V.e_katt("bal", le=True) == {"t": "katt", "gomb": "bal", "le": True}
    assert V.e_gorget(120) == {"t": "gorget", "d": 120}
    assert V.e_bill(65, le=False) == {"t": "bill", "vk": 65, "le": False}
    assert V.e_char("á") == {"t": "char", "ch": "á"}


def test_vezerlo_alapbol_inaktiv():
    vez = V.Vezerlo()
    assert vez.aktiv is False


def test_inaktiv_vezerlo_semmit_nem_csinal():
    # a legfontosabb garancia: inaktívan MINDEN eseményt eldob (nincs injektálás)
    vez = V.Vezerlo()
    vez.aktiv = False
    assert vez.alkalmaz(V.e_mozog(0.5, 0.5)) is False
    assert vez.alkalmaz(V.e_katt("bal")) is False
    assert vez.alkalmaz(V.e_bill(65)) is False
    assert vez.alkalmaz(V.e_char("a")) is False


def test_rossz_bemenet_biztonsagos():
    vez = V.Vezerlo()
    vez.aktiv = True                       # aktív, de rossz/ismeretlen bemenet
    assert vez.alkalmaz(None) is False
    assert vez.alkalmaz("nem dict") is False
    assert vez.alkalmaz({"t": "ismeretlen"}) is False


def test_biztonsagi_szovegek_megvannak():
    # a beleegyező szövegek tartalmazzák a kulcs-üzeneteket
    assert "MEGBÍZHATÓ" in SZ.BELEEGYEZO_SEGITETT
    assert "pánik" in SZ.BELEEGYEZO_SEGITETT.lower() \
        or "leállításról" in SZ.BELEEGYEZO_SEGITETT.lower() \
        or "leáll" in SZ.BELEEGYEZO_SEGITETT.lower()
    assert "vissza" in SZ.BELEEGYEZO_IRANYITO.lower()   # „ne élj vissza”
    assert "{ki}" in SZ.IRANYITAS_AKTIV                 # a felület behelyettesíti


# ----------------------- munkamenet (vezérlő-hurok) -----------------------
SESSION = importlib.import_module(BASE + ".session")


class _LokalisTranszport:
    """Két végpontot köt össze memóriában (a.kuld → b.fogado, szinkron)."""
    def __init__(self):
        self._fogado = None
        self.tars = None
    def set_fogado(self, cb):
        self._fogado = cb
    def kuld(self, uzenet):
        if self.tars and self.tars._fogado:
            self.tars._fogado(dict(uzenet))
    @staticmethod
    def par():
        a, b = _LokalisTranszport(), _LokalisTranszport()
        a.tars, b.tars = b, a
        return a, b


class _MockVezerlo:
    def __init__(self):
        self.aktiv = False
        self.alkalmazott = []
    def alkalmaz(self, esemeny):
        if not self.aktiv:
            return False
        self.alkalmazott.append(esemeny)
        return True


def _par():
    ta, tb = _LokalisTranszport.par()
    mv = _MockVezerlo()
    segitett = SESSION.Munkamenet(ta, "segitett", "Segitett", vezerlo=mv)
    iranyito = SESSION.Munkamenet(tb, "iranyito", "Iranyito")
    return segitett, iranyito, mv


def test_esemeny_csak_engedely_utan_hajtodik_vegre():
    seg, ir, mv = _par()
    # engedély ELŐTT: az irányító küldése nem megy át (nincs jogosultság)
    assert ir.esemeny_kuld(V.e_char("x")) is False
    assert mv.alkalmazott == []
    # a SEGÍTETT engedélyez (beleegyezés után)
    seg.iranyitas_engedelyez()
    assert seg.iranyit and mv.aktiv is True and ir.iranyit is True
    # most már átmegy és VÉGREHAJTÓDIK
    assert ir.esemeny_kuld(V.e_char("x")) is True
    assert mv.alkalmazott == [{"t": "char", "ch": "x"}]


def test_panik_azonnal_lezar():
    seg, ir, mv = _par()
    seg.iranyitas_engedelyez()
    ir.esemeny_kuld(V.e_bill(65))
    assert len(mv.alkalmazott) == 1
    # PÁNIK a segített oldalán → a kapu becsukódik mindkét félnél
    seg.iranyitas_leallit(panik=True)
    assert seg.iranyit is False and mv.aktiv is False and ir.iranyit is False
    # ezután az irányító küldése már nem hajtódik végre
    assert ir.esemeny_kuld(V.e_bill(66)) is False
    assert len(mv.alkalmazott) == 1        # nem nőtt


def test_iranyito_oldali_panik_is_lezar():
    seg, ir, mv = _par()
    seg.iranyitas_engedelyez()
    ir.iranyitas_leallit(panik=True)       # az IRÁNYÍTÓ áll le
    assert mv.aktiv is False and seg.iranyit is False


def test_segitett_soha_nem_kuld_esemenyt():
    seg, ir, mv = _par()
    seg.iranyitas_engedelyez()
    # a segített szerep NEM küldhet vezérlést (csak fogad)
    assert seg.esemeny_kuld(V.e_char("z")) is False


def test_csevej_atmegy():
    seg, ir, mv = _par()
    kapott = {}
    ir._on_allapot = lambda k, a: kapott.update({k: a})
    seg.csevej_kuld("Szia, segítek!")
    assert kapott.get("csevej", {}).get("szoveg") == "Szia, segítek!"


# ----------------------- irányító-oldali elkapás (wx→VK) -----------------------
def test_wx_vk_leekepezes():
    wx = pytest_importorskip_wx()
    EK = importlib.import_module(BASE + ".elkapas")
    assert EK.wx_vk(wx.WXK_RETURN) == 0x0D
    assert EK.wx_vk(wx.WXK_ESCAPE) == 0x1B
    assert EK.wx_vk(wx.WXK_LEFT) == 0x25 and EK.wx_vk(wx.WXK_DOWN) == 0x28
    assert EK.wx_vk(wx.WXK_INSERT) == 0x2D          # képernyőolvasó-módosító
    assert EK.wx_vk(wx.WXK_CONTROL) == 0x11
    assert EK.wx_vk(wx.WXK_F1) == 0x70 and EK.wx_vk(wx.WXK_F12) == 0x7B
    assert EK.wx_vk(ord("A")) == 0x41 and EK.wx_vk(ord("9")) == 0x39
    assert EK.wx_vk(9999) is None


def pytest_importorskip_wx():
    import pytest
    return pytest.importorskip("wx")
