# -*- coding: utf-8 -*-
"""TELJES MENTÉS ÉS VISSZAÁLLÍTÁS.

Felhasználói kérés: „teljes mentés… amiből minden is visszatölthető! e-mailek,
kulcsok, minden!… hogy ha új gépre költözik a felhasználó, egy mozdulat legyen
visszaállítani mindent.”

A LEGFONTOSABB, AMIT ŐRIZNI KELL:
  • a jelszavak és kulcsok SOHA ne legyenek olvashatók a mentés-fájlban;
  • hibás jelszóval ne lehessen kinyitni;
  • a csomagban elrejtett „../” útvonal ne írhasson a mappán kívülre;
  • a nagy, újratölthető adatok (fordítómodellek, gyorsítótár) ne kerüljenek bele.
"""

import json
import zipfile

import pytest

from superdl import mentes as M


@pytest.fixture
def gyoker(tmp_path, monkeypatch):
    """Egy teljes .superdl mappát utánzunk – valódi adatokhoz nem nyúlunk."""
    (tmp_path / "subscriptions.json").write_text('[{"csatorna": "teszt"}]',
                                                 encoding="utf-8")
    (tmp_path / "organizer_events.json").write_text('[{"title": "szülinap"}]',
                                                    encoding="utf-8")
    (tmp_path / "book_bookmarks.json").write_text('{"konyv": 42}',
                                                  encoding="utf-8")
    (tmp_path / "queue.json.bak").write_text("[]", encoding="utf-8")   # kihagyandó
    (tmp_path / "osszeomlas.log").write_text("napló", encoding="utf-8")
    (tmp_path / "tvmusor_epg.xml").write_text("<tv/>", encoding="utf-8")
    for mappa in ("forditomodellek", "gyorsitotar", "bin"):
        (tmp_path / mappa).mkdir()
        (tmp_path / mappa / "nagy.bin").write_bytes(b"x" * 1000)
    # a titkos fájlok a valóságban DPAPI-blobot tartalmaznak; itt a tartalmuk
    # lényegtelen (a `hamis_titkos` adja vissza a „visszafejtett" adatot), de
    # LÉTEZNIÜK kell, különben nincs mit visszafejteni
    (tmp_path / "ai.json").write_text('{"__dpapi__": "…"}', encoding="utf-8")
    (tmp_path / "mail_accounts.dat").write_text('{"__dpapi__": "…"}',
                                                encoding="utf-8")
    (tmp_path / "modules_data").mkdir()
    (tmp_path / "modules_data" / "mail.json").write_text('{"x": 1}',
                                                         encoding="utf-8")
    modul = tmp_path / "modules" / "mail"
    modul.mkdir(parents=True)
    (modul / "manifest.json").write_text(
        '{"id": "mail", "name": "Super Mail", "version": "1.1.2"}',
        encoding="utf-8")
    monkeypatch.setattr(M, "_config_dir", lambda: tmp_path)
    beallitas = tmp_path / "sajat_beallitas.json"
    beallitas.write_text('{"theme": "dark"}', encoding="utf-8")
    monkeypatch.setattr(M, "_beallitas_fajl", lambda: beallitas)
    return tmp_path


@pytest.fixture
def hamis_titkos(monkeypatch):
    """A DPAPI helyett memóriában tartjuk a titkokat – a teszt nem nyúl a
    valódi kulcstárolóhoz."""
    from superdl import store
    tarolo = {"ai.json": {"openai": "SK-TITKOS-KULCS"},
              "mail_accounts.dat": {"fiokok": [
                  {"email": "en@sajat.hu", "jelszo": "SZUPERTITKOS"}]}}
    monkeypatch.setattr(store, "_load_secret_config",
                        lambda ut: dict(tarolo.get(getattr(ut, "name", ""), {})))
    mentett = {}
    monkeypatch.setattr(store, "save_secret_json",
                        lambda ut, adat: mentett.__setitem__(
                            getattr(ut, "name", str(ut)), adat))
    return tarolo, mentett


# ---------------------------------------------------- gyűjtés

def test_a_nagy_ujratoltheto_adatok_kimaradnak(gyoker, hamis_titkos):
    sima, titkos, hibak = M.gyujtes(gyoker)
    nevek = set(sima)
    assert "subscriptions.json" in nevek
    assert "modules_data/mail.json" in nevek
    assert not any(n.startswith(("forditomodellek", "gyorsitotar", "bin",
                                 "modules/")) for n in nevek), \
        "ezek bármikor újratölthetők – ne hizlalják a mentést"
    assert "queue.json.bak" not in nevek
    assert "osszeomlas.log" not in nevek and "tvmusor_epg.xml" not in nevek
    assert hibak == []


def test_a_titkos_fajlok_visszafejtve_kerulnek_be(gyoker, hamis_titkos):
    _sima, titkos, _h = M.gyujtes(gyoker)
    assert "ai.json" in titkos and "mail_accounts.dat" in titkos
    assert titkos["ai.json"]["openai"] == "SK-TITKOS-KULCS"


def test_a_telepitett_modulok_listaja(gyoker):
    modulok = M.telepitett_modulok()
    assert modulok and modulok[0]["id"] == "mail"
    assert modulok[0]["verzio"] == "1.1.2"


# ---------------------------------------------------- mentés

def test_jelszo_nelkul_nincs_mentes(tmp_path, gyoker, hamis_titkos):
    with pytest.raises(ValueError):
        M.keszit(str(tmp_path / "x.sdlmentes"), "rövid")


def test_a_kulcsok_nem_olvashatok_a_fajlban(tmp_path, gyoker, hamis_titkos):
    """EZ a legfontosabb teszt: a mentés jelszavakat tartalmaz, tehát a
    fájlban SEMMI nem lehet olvasható."""
    ut = tmp_path / ("m" + M.KITERJESZTES)
    M.keszit(str(ut), "eleg-hosszu-jelszo")
    nyers = ut.read_bytes()
    assert b"SZUPERTITKOS" not in nyers
    assert b"SK-TITKOS-KULCS" not in nyers
    assert b"subscriptions" not in nyers, "még a fájlnevek sem látszanak"
    assert nyers.startswith(M.MAGIC)


def test_teljes_kor_visszaallitassal(tmp_path, gyoker, hamis_titkos):
    _tarolo, mentett = hamis_titkos
    ut = tmp_path / ("m" + M.KITERJESZTES)
    ossz = M.keszit(str(ut), "eleg-hosszu-jelszo")
    assert ossz["fajlok"] >= 3 and ossz["titkos"] == 2 and ossz["modulok"] == 1

    # töröljük a felhasználó adatait, mintha új gép volna
    for p in list(gyoker.glob("*.json")):
        p.unlink()

    eredmeny = M.visszaallit(str(ut), "eleg-hosszu-jelszo", gyoker,
                             biztonsagi_masolat=False)
    assert eredmeny["hibak"] == []
    assert (gyoker / "subscriptions.json").read_text(encoding="utf-8") \
        == '[{"csatorna": "teszt"}]'
    assert (gyoker / "organizer_events.json").is_file()
    assert (gyoker / "modules_data" / "mail.json").is_file()
    # a titkok az ÚJ gép saját titkosításával kerültek vissza
    assert mentett["ai.json"]["openai"] == "SK-TITKOS-KULCS"
    assert mentett["mail_accounts.dat"]["fiokok"][0]["jelszo"] == "SZUPERTITKOS"
    # és tudjuk, mely modulokat kell újratelepíteni
    assert eredmeny["modulok"][0]["id"] == "mail"


def test_a_beallitasok_is_visszajonnek(tmp_path, gyoker, hamis_titkos):
    ut = tmp_path / ("m" + M.KITERJESZTES)
    M.keszit(str(ut), "eleg-hosszu-jelszo")
    M._beallitas_fajl().unlink()
    M.visszaallit(str(ut), "eleg-hosszu-jelszo", gyoker,
                  biztonsagi_masolat=False)
    assert json.loads(M._beallitas_fajl().read_text(
        encoding="utf-8"))["theme"] == "dark"


# ---------------------------------------------------- védelem

def test_hibas_jelszoval_nem_nyilik(tmp_path, gyoker, hamis_titkos):
    ut = tmp_path / ("m" + M.KITERJESZTES)
    M.keszit(str(ut), "eleg-hosszu-jelszo")
    with pytest.raises(ValueError):
        M.olvas(str(ut), "masik-jelszo")


def test_serult_vagy_idegen_fajl(tmp_path):
    idegen = tmp_path / ("x" + M.KITERJESZTES)
    idegen.write_bytes(b"ez nem a mi fajlunk")
    with pytest.raises(ValueError):
        M.olvas(str(idegen), "akarmi")


def test_modositott_fajlt_eszrevesszuk(tmp_path, gyoker, hamis_titkos):
    """A titkosítás hitelesít is: egyetlen bájt átírása után nem nyílik ki."""
    ut = tmp_path / ("m" + M.KITERJESZTES)
    M.keszit(str(ut), "eleg-hosszu-jelszo")
    nyers = bytearray(ut.read_bytes())
    nyers[-1] ^= 0xFF
    ut.write_bytes(bytes(nyers))
    with pytest.raises(ValueError):
        M.olvas(str(ut), "eleg-hosszu-jelszo")


def test_a_csomagban_elrejtett_utvonal_nem_ir_kifele(tmp_path, gyoker,
                                                     hamis_titkos):
    """Kézzel gyártott, rosszindulatú csomag: „../” a fájlnévben."""
    import io as _io
    puffer = _io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("mentes.json", json.dumps({"formatum": 1}))
        z.writestr("adatok/../../kiszokott.txt", "rossz")
    ut = tmp_path / ("rossz" + M.KITERJESZTES)
    ut.write_bytes(M._titkosit(puffer.getvalue(), "eleg-hosszu-jelszo"))
    eredmeny = M.visszaallit(str(ut), "eleg-hosszu-jelszo", gyoker,
                             biztonsagi_masolat=False)
    assert any("gyanús útvonal" in h for h in eredmeny["hibak"])
    assert not (tmp_path.parent / "kiszokott.txt").exists()


# ---------------------------------------------------- felület-szövegek

def test_elonezet_elmondja_mi_van_a_mentesben(tmp_path, gyoker, hamis_titkos):
    ut = tmp_path / ("m" + M.KITERJESZTES)
    M.keszit(str(ut), "eleg-hosszu-jelszo")
    sz = M.elonezet(str(ut), "eleg-hosszu-jelszo")
    assert "Mentés készült" in sz
    assert "bizalmas" in sz
    assert "Super Mail" in sz


def test_alap_fajlnev_es_meret_szoveg():
    assert M.alap_fajlnev().endswith(M.KITERJESZTES)
    assert "megabájt" in M.meret_szoveg(3 * 1024 ** 2)
    assert "bájt" in M.meret_szoveg(12)
