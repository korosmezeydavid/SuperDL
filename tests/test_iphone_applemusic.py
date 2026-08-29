# -*- coding: utf-8 -*-
"""iPhone modul – a GYÁRI Zene alkalmazásba vezető út.

Felhasználói ötlet (2026-08-29): „nem kerülné meg semmi, hanem a meglévő
iPhone-kompatibilis eszközöket használná arra, hogy az akadálymentes felülettel
feltöltsd a zenéket” – vagyis a gépen lévő Apple Music és Apple Devices legyen a
motor, a SuperDL pedig a kezelőfelület.

Élesben végigmértük, és működik: a fájl a figyelt mappán át bekerül az Apple
Music könyvtárába, onnan az Apple Devices átviszi a telefon gyári Zene
alkalmazásába. Ezek a tesztek a törékeny pontokat őrzik – azokat, amikbe a
fejlesztés közben bele is futottunk:

  * a figyelt mappa nevét nem szabad kőbe vésni (verziónként/nyelvenként más);
  * ha az Apple Music nem olvassa be a fájlt, azt ÉSZRE kell venni, nem
    hazudhatunk sikert;
  * ha az Apple Devices nem látja a telefont, semmi nem történik – ezt ki kell
    mondani, mert órákig ez vezetett félre minket is;
  * a behozatal akkor is siker, ha a szinkron elakad: a zene a gépi könyvtárban
    már ott van, és kézzel is átvihető.
"""

import os
import sys

import pytest

sys.path.insert(0, "modules_src/iphone")
from iphone_mod import applemusic as AM          # noqa: E402


@pytest.fixture
def konyvtar(tmp_path, monkeypatch):
    """Egy kamu Apple Music könyvtár, figyelt mappával."""
    alap = tmp_path / "Apple Music"
    figyelt = alap / "Media" / "Automatically Add to Apple Music"
    figyelt.mkdir(parents=True)
    monkeypatch.setattr(AM, "konyvtar_mappa", lambda: str(alap))
    monkeypatch.setattr(AM, "_inditsd", lambda appid: None)
    return figyelt


def _dal(tmp_path, nev="dal.mp3", tartalom=b"ID3zene"):
    p = tmp_path / nev
    p.write_bytes(tartalom)
    return str(p)


# ------------------------------------------------------ a figyelt mappa

def test_a_figyelt_mappat_a_KEZDETE_alapjan_keressuk(konyvtar, tmp_path,
                                                     monkeypatch):
    """Az iTunes-nál „Automatically Add to Music”, az Apple Musicnál
    „…to Apple Music”. Ha a teljes nevet várnánk, az egyik gépen elhasalna."""
    assert AM.figyelt_mappa() == str(konyvtar)
    masik = tmp_path / "Apple Music" / "Media" / "Automatically Add to Music"
    konyvtar.rmdir()
    masik.mkdir()
    assert AM.figyelt_mappa() == str(masik)


def test_konyvtar_nelkul_nem_elerheto(tmp_path, monkeypatch):
    monkeypatch.setattr(AM, "konyvtar_mappa", lambda: "")
    assert AM.elerheto() is False
    with pytest.raises(AM.AppleHiba) as hiba:
        AM.behoz(["akarmi.mp3"])
    assert "Apple Music" in str(hiba.value)


# ---------------------------------------------------------- a behozatal

def test_a_behozatal_akkor_siker_ha_ELVITTEK_a_fajlt(konyvtar, tmp_path,
                                                     monkeypatch):
    """Az Apple Music a beolvasott fájlt elviszi a figyelt mappából – EZ a
    visszaigazolás. Enélkül csak reménykednénk."""
    p = _dal(tmp_path)

    def elnyeli(ut, mp, megszakit=None):
        os.remove(ut)                    # mintha az Apple Music vitte volna el
        return True
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek", elnyeli)
    assert AM.behoz([p]) == (1, [])


def test_ha_nem_olvassa_be_azt_MEGMONDJUK(konyvtar, tmp_path, monkeypatch):
    """Élesben ez történt, amikor az Apple Music könyvtára frissen jött létre.
    A felhasználó ilyenkor kapjon értelmes utasítást, ne néma sikert."""
    p = _dal(tmp_path)
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: False)
    ok, hibak = AM.behoz([p])
    assert ok == 0 and len(hibak) == 1
    assert "Nyisd meg egyszer az Apple Music" in hibak[0]
    assert str(konyvtar) in hibak[0], "mondjuk meg, HOL várakozik a fájl"


def test_a_meglevo_fajlt_nem_irjuk_felul(konyvtar, tmp_path, monkeypatch):
    (konyvtar / "dal.mp3").write_bytes(b"regi")
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: True)
    AM.behoz([_dal(tmp_path)])
    assert (konyvtar / "dal.mp3").read_bytes() == b"regi"
    assert (konyvtar / "dal (2).mp3").exists()


def test_a_behozatal_megszakithato(konyvtar, tmp_path):
    assert AM.behoz([_dal(tmp_path)], megszakit=lambda: True) == (0, [])


def test_a_nem_letezo_fajlt_kihagyjuk(konyvtar):
    assert AM.behoz([r"C:\nincs\ilyen.mp3"]) == (0, [])


# ------------------------------------------------------------ a szinkron

def test_eszkoz_nelkul_beszedes_hibat_adunk(konyvtar, tmp_path, monkeypatch):
    """EZ fogott ki rajtunk a legtovább: amíg az Apple Devices nem látja a
    telefont, a beállítás sem marad meg, és szinkron sem indul. A felhasználó
    ne álljon értetlenül – és tudja meg, hogy a zenéje NEM veszett el."""
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: True)
    monkeypatch.setattr(AM, "szinkron_allapot",
                        lambda *a, **k: {"ok": True, "van_eszkoz": False})
    r = AM.teljes_lanc([_dal(tmp_path)])
    assert r["behozva"] == 1, "a behozatal ettől még sikerült"
    assert "nem látja a telefont" in r["szinkron"]
    assert "nem veszett el" in r["szinkron"]


def test_a_lanc_bekapcsolja_a_szinkront_ha_kell(konyvtar, tmp_path, monkeypatch):
    hivasok = []
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: True)
    monkeypatch.setattr(AM, "szinkron_allapot",
                        lambda *a, **k: {"ok": True, "van_eszkoz": True,
                                         "bekapcsolva": False})
    monkeypatch.setattr(AM, "szinkron_bekapcsol",
                        lambda: hivasok.append("bekapcsol"))
    monkeypatch.setattr(AM, "szinkron_megerosit",
                        lambda: hivasok.append("megerosit"))
    monkeypatch.setattr(AM, "szinkronizal", lambda: hivasok.append("szinkron"))
    r = AM.teljes_lanc([_dal(tmp_path)])
    assert hivasok == ["bekapcsol", "megerosit", "szinkron"], \
        "bekapcsolás, majd az Apple megerősítő kérdése, végül az indítás"
    assert r["szinkron"] == "elindult"


def test_bekapcsolt_szinkronnal_nem_kapcsolgatunk(konyvtar, tmp_path,
                                                  monkeypatch):
    """Ha már be van kapcsolva, ne nyúljunk a felhasználó beállításához."""
    hivasok = []
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: True)
    monkeypatch.setattr(AM, "szinkron_allapot",
                        lambda *a, **k: {"ok": True, "van_eszkoz": True,
                                         "bekapcsolva": True})
    monkeypatch.setattr(AM, "szinkron_bekapcsol",
                        lambda: hivasok.append("bekapcsol"))
    monkeypatch.setattr(AM, "szinkronizal", lambda: hivasok.append("szinkron"))
    AM.teljes_lanc([_dal(tmp_path)])
    assert hivasok == ["szinkron"]


def test_a_szinkron_hibaja_nem_teszi_tonkre_a_behozatalt(konyvtar, tmp_path,
                                                         monkeypatch):
    """A zene a gépi könyvtárban már ott van – ezt nem szabad kudarcnak
    mondani csak azért, mert az átvitel elakadt."""
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: True)
    monkeypatch.setattr(AM, "szinkron_allapot",
                        lambda *a, **k: {"ok": True, "van_eszkoz": True,
                                         "bekapcsolva": True})

    def elakad():
        raise AM.AppleHiba("nem találom a gombot")
    monkeypatch.setattr(AM, "szinkronizal", elakad)
    r = AM.teljes_lanc([_dal(tmp_path)])
    assert r["behozva"] == 1
    assert "nem találom a gombot" in r["szinkron"]


def test_szinkron_nelkul_is_kerhetunk_behozatalt(konyvtar, tmp_path,
                                                 monkeypatch):
    monkeypatch.setattr(AM, "_megvarja_hogy_elnyeljek",
                        lambda ut, mp, megszakit=None: True)
    r = AM.teljes_lanc([_dal(tmp_path)], szinkronizaljon=False)
    assert r == {"behozva": 1, "hibak": [], "szinkron": ""}


# ------------------------------------------------- a felület-vezérlő minták

@pytest.mark.parametrize("nev", ["Szinkronizálás", "Alkalmazás", "Sync", "Apply"])
def test_a_muvelet_gomb_MINDKET_nevet_ismerjuk(nev):
    """A gomb felirata állapotfüggő: „Szinkronizálás”, ha nincs függő
    változás, és „Alkalmazás”, ha van – ezen csúsztunk el először."""
    import re
    assert re.match(AM._SZINKRON_GOMB, nev), nev


@pytest.mark.parametrize("nev", [
    "Zenék szinkronizálása ide: dávid iPhone-ja",
    "Sync music onto iPhone",
])
def test_a_kapcsolo_magyarul_es_angolul_is_megvan(nev):
    """A feliratok a Windows nyelvét követik."""
    import re
    assert re.search(AM._SZINKRON_BE, nev), nev
