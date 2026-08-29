# -*- coding: utf-8 -*-
"""iPhone modul – a FELTÖLTÉS ellenőrzése élő telefon nélkül.

A feltöltés két helyre ír: a hangfájl a telefon zene-mappájába kerül, a cím és
az előadó pedig a zene-adatbázisba. Ha a kettő elcsúszik, vagy néma fájl marad
a telefonon, vagy névtelen sor a lejátszóban. Ezért itt azt méricskéljük, hogy
hiba esetén NE maradjon semmi nyom – és hogy a címkék tényleg átjöjjenek.
"""

import os
import struct
import sys

import pytest

sys.path.insert(0, "modules_src/iphone")
from iphone_mod import afc as A                        # noqa: E402
from iphone_mod import cimkek                          # noqa: E402
from test_iphone_core import KamuAfc, KamuTelefon, _epit_db   # noqa: E402
from iphone_mod import iphone_core as C                # noqa: E402


# ------------------------------------------------------------ címkeolvasás

def _mp3(ut, cim="", eloado="", album="", masodperc=2):
    """Egy szabályos, pici MP3 – ID3-fejléccel és egy valódi kerettel, hogy a
    hossz-becslés is dolgozhasson rajta."""
    keretek = []
    for azon, ertek in ((b"TIT2", cim), (b"TPE1", eloado), (b"TALB", album)):
        if not ertek:
            continue
        test = b"\x03" + ertek.encode("utf-8")         # 3 = UTF-8
        keretek.append(azon + struct.pack(">I", len(test)) + b"\x00\x00" + test)
    torzs = b"".join(keretek)
    n = len(torzs)
    meret = bytes([(n >> 21) & 127, (n >> 14) & 127, (n >> 7) & 127, n & 127])
    # 128 kbps, 44,1 kHz keret-fejléc (a 0x90 bájt EZT jelenti), utána néma
    # adat a kívánt hosszhoz – a hossz-becslés ebből dolgozik
    keret = b"\xff\xfb\x90\x00"
    hang = keret + b"\x00" * (128 * 1000 // 8 * masodperc - 4)
    with open(ut, "wb") as f:
        f.write(b"ID3\x03\x00\x00" + meret + torzs + hang)
    return ut


def test_a_cimke_atjon_a_fajlbol(tmp_path):
    p = _mp3(str(tmp_path / "akarmi.mp3"), "Szép cím", "Az Előadó", "Az Album")
    a = cimkek.beolvas(p)
    assert a["cim"] == "Szép cím"
    assert a["eloado"] == "Az Előadó"
    assert a["album"] == "Az Album"


def test_cimke_nelkul_a_fajlnev_a_tartalek(tmp_path):
    """Jobb egy értelmes fájlnév, mint egy üres sor a telefon lejátszójában."""
    p = _mp3(str(tmp_path / "Valami Dal.mp3"))
    assert cimkek.beolvas(p)["cim"] == "Valami Dal"


def test_a_hossz_becslese_hihetot_ad(tmp_path):
    p = _mp3(str(tmp_path / "x.mp3"), "c", masodperc=10)
    ms = cimkek.beolvas(p)["ms"]
    assert 9000 < ms < 11000, "128 kbps-nél a méretből ki kell jönnie"


def test_a_serult_fajl_nem_dont_el_semmit(tmp_path):
    """Rossz címke miatt egy szám ne maradjon ki a küldésből."""
    p = tmp_path / "romlott.mp3"
    p.write_bytes(b"ID3\x03\x00\x00\x7f\x7f\x7f\x7f" + b"\xff" * 50)
    assert cimkek.beolvas(str(p))["cim"] == "romlott"


# ------------------------------------------------------------- feltöltés

class FeltoltoAfc(KamuAfc):
    def letezik(self, ut):
        return ut in self.fajlok


@pytest.fixture
def telefon(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "mentes_mappa", lambda: str(tmp_path / "mentes"))
    db = tmp_path / "e.sqlitedb"
    _epit_db(str(db), darab=1)
    return KamuTelefon(FeltoltoAfc({C.DB_MAPPA + C.DB_NEV: db.read_bytes(),
                                    "/iTunes_Control/Music/F00/S000.mp3": b"ID3"}))


def test_a_feltoltes_a_fajlt_ES_a_bejegyzest_is_leteszi(telefon, tmp_path):
    p = _mp3(str(tmp_path / "uj.mp3"), "Új szám", "Új Előadó")
    ok, hibak, mentes = telefon.zene_feltolt([p])
    assert (ok, hibak) == (1, [])
    assert os.path.exists(os.path.join(mentes, C.DB_NEV)), "mentés készült"
    z = telefon.zenek()
    assert len(z) == 2
    uj = [x for x in z if x["cim"] == "Új szám"][0]
    assert uj["eloado"] == "Új Előadó"
    assert uj["ut"].startswith("/iTunes_Control/Music/F"), \
        "a telefon saját zene-mappájába kerül"
    assert uj["ut"] in telefon.afc.fajlok, "a hangfájl is fent van"


def test_ket_szam_ugyanattol_az_eloadotol_egy_bejegyzest_kap(telefon, tmp_path):
    """Különben a telefon lejátszójában ugyanaz az előadó kétszer jelenne meg."""
    a = _mp3(str(tmp_path / "a.mp3"), "A", "Közös Előadó")
    b = _mp3(str(tmp_path / "b.mp3"), "B", "Közös Előadó")
    telefon.zene_feltolt([a, b])
    z = {x["cim"]: x["eloado"] for x in telefon.zenek()}
    assert z["A"] == z["B"] == "Közös Előadó"


def test_hibas_adatbazisnal_a_HANGFAJL_SEM_marad_ott(telefon, tmp_path):
    """A legfontosabb: ha a bejegyzés nem megy át, ne maradjon néma, gazdátlan
    fájl a telefonon, amit senki nem lát és nem tud törölni."""
    telefon.afc.iras_rontas = b"nem adatbazis"
    p = _mp3(str(tmp_path / "arva.mp3"), "Árva")
    elotte = set(telefon.afc.fajlok)
    with pytest.raises(A.IPhoneHiba) as hiba:
        telefon.zene_feltolt([p])
    assert "érintetlen" in str(hiba.value) or "VISSZAÁLLÍTOTTAM" in str(hiba.value)
    # a zene-mappákban NEM maradhat gazdátlan hangfájl (az adatbázis melletti
    # napló-fájlok keletkezése rendben van, azok nem hangfájlok)
    maradt = {u for u in set(telefon.afc.fajlok) - elotte
              if u.startswith("/iTunes_Control/Music/")}
    assert not maradt, "nem maradhat gazdátlan hangfájl: %s" % maradt


def test_a_nem_letezo_fajlt_csendben_kihagyjuk(telefon):
    assert telefon.zene_feltolt([r"C:\nincs\ilyen.mp3"]) == (0, [], "")


def test_a_feltoltes_megszakithato(telefon, tmp_path):
    p = _mp3(str(tmp_path / "x.mp3"), "X")
    ok, _hibak, _m = telefon.zene_feltolt([p], megszakit=lambda: True)
    assert ok == 0
    assert len(telefon.zenek()) == 1, "a telefon érintetlen maradt"


# ------------------------------------- feltöltés lejátszó alkalmazásba

class KamuAppAfc(FeltoltoAfc):
    """Egy alkalmazás megosztott mappája."""


def test_az_app_feltoltes_leteszi_a_fajlt(tmp_path, monkeypatch):
    """Ez a MEGBÍZHATÓ út a telefonra: a gyári Zene alkalmazás könyvtárát a
    telefon szolgáltatása felülírja, egy lejátszó saját mappáját viszont nem."""
    from iphone_mod import afc as afc_modul
    kamu = KamuAppAfc({})
    monkeypatch.setattr(afc_modul, "alkalmazas_mappaja", lambda ld, b: kamu)
    t = KamuTelefon(KamuAppAfc({}))
    t.ld = None
    p = _mp3(str(tmp_path / "dal.mp3"), "Dal")
    ok, hibak = t.app_feltolt("valami.app", [p])
    assert (ok, hibak) == (1, [])
    assert "Documents/dal.mp3" in kamu.fajlok


def test_az_app_feltoltes_nem_ir_felul_meglevot(tmp_path, monkeypatch):
    from iphone_mod import afc as afc_modul
    kamu = KamuAppAfc({"Documents/dal.mp3": b"regi"})
    monkeypatch.setattr(afc_modul, "alkalmazas_mappaja", lambda ld, b: kamu)
    t = KamuTelefon(KamuAppAfc({}))
    t.ld = None
    p = _mp3(str(tmp_path / "dal.mp3"), "Dal")
    t.app_feltolt("valami.app", [p])
    assert kamu.fajlok["Documents/dal.mp3"] == b"regi", "a régi maradjon"
    assert "Documents/dal (2).mp3" in kamu.fajlok, "az új sorszámot kap"


def test_az_app_feltoltes_megszakithato(tmp_path, monkeypatch):
    from iphone_mod import afc as afc_modul
    kamu = KamuAppAfc({})
    monkeypatch.setattr(afc_modul, "alkalmazas_mappaja", lambda ld, b: kamu)
    t = KamuTelefon(KamuAppAfc({}))
    t.ld = None
    p = _mp3(str(tmp_path / "d.mp3"), "D")
    assert t.app_feltolt("valami.app", [p], megszakit=lambda: True) == (0, [])
    assert not kamu.fajlok
