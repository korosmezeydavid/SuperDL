"""Hangoskönyv: HOVA kerül a kész fájl, és a végi HANGJELZÉS.

Felhasználói kérés (2026-08-15):
  • a kész hangoskönyv kerülhessen oda, AHONNAN a könyvet betallózta;
  • DARABOLÁSNÁL mindig ALMAPPA (ne szóródjon szét húsz MP3);
  • a végén szóljon fanfár – és HIBA esetén is jelzés, mert hosszú könyvnél a
    felhasználó rég nem a gép előtt ül.

Amit külön őrzünk: meglévő fájlt/mappát SOHA nem írunk felül, és ha a kért hely
nem használható (beillesztett szöveg, írásvédett mappa), akkor NEM némán térünk
ki, hanem indoklással.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/konyvek")
from konyvek_mod import kimenet as K            # noqa: E402


# ------------------------------------------------------------- fájlnév

def test_a_cimbol_biztonsagos_nev_lesz():
    assert K.biztonsagos_nev("Egri csillagok") == "Egri csillagok"
    assert "/" not in K.biztonsagos_nev("A/B: c?d*e")
    assert ":" not in K.biztonsagos_nev("A/B: c?d*e")
    assert K.biztonsagos_nev("   ") == "hangoskonyv", "üres címre is legyen név"
    assert not K.biztonsagos_nev("Vége...").endswith("."), \
        "a záró pont Windowson elrontja a mappa létrehozását"
    assert len(K.biztonsagos_nev("x" * 300)) <= 120


# -------------------------------------------------------- melyik mappa

def test_a_konyv_melle_a_forras_mappajaba_megy(tmp_path):
    konyv = tmp_path / "konyvek" / "Egri csillagok.epub"
    konyv.parent.mkdir(parents=True)
    konyv.write_text("x", encoding="utf-8")
    mappa, uzenet = K.celmappa(str(konyv), str(tmp_path / "Letoltesek"), True)
    assert mappa == konyv.parent
    assert uzenet == "", "ha sikerült, ne magyarázkodjon"


def test_kikapcsolva_a_celmappa_marad(tmp_path):
    konyv = tmp_path / "k.epub"
    konyv.write_text("x", encoding="utf-8")
    cel = tmp_path / "Letoltesek"
    mappa, uzenet = K.celmappa(str(konyv), str(cel), False)
    assert mappa == cel and uzenet == ""


def test_beillesztett_szovegnel_indokkal_ter_ki(tmp_path):
    """Nincs forrásfájl → nincs „mellé”. Ezt KI KELL MONDANI, különben a
    felhasználó máshol keresné a kész könyvet."""
    mappa, uzenet = K.celmappa("", str(tmp_path / "Letoltesek"), True)
    assert mappa == tmp_path / "Letoltesek"
    assert "beillesztett" in uzenet.lower() and uzenet.endswith("kerül.")


def test_irasvedett_forrasmappanal_indokkal_ter_ki(tmp_path, monkeypatch):
    konyv = tmp_path / "cd" / "k.epub"
    konyv.parent.mkdir(parents=True)
    konyv.write_text("x", encoding="utf-8")
    monkeypatch.setattr(K, "irhato", lambda m: False)
    mappa, uzenet = K.celmappa(str(konyv), str(tmp_path / "Letoltesek"), True)
    assert mappa == tmp_path / "Letoltesek"
    assert "írni" in uzenet


def test_irhato_valoban_probal_irni(tmp_path):
    assert K.irhato(tmp_path) is True
    assert not any(tmp_path.iterdir()), "a próbafájl NE maradjon ott"


# ----------------------------------------------------- kimeneti útvonal

def test_egyben_nincs_almappa(tmp_path):
    ut = K.kimeneti_ut(tmp_path, "Egri csillagok", darabolva=False)
    assert ut == tmp_path / "Egri csillagok.mp3"


def test_darabolasnal_mindig_almappa(tmp_path):
    ut = K.kimeneti_ut(tmp_path, "Egri csillagok", darabolva=True)
    assert ut.parent == tmp_path / "Egri csillagok", \
        "darabolásnál a részek almappába kerülnek"
    assert ut.name == "Egri csillagok.mp3"


def test_meglevo_fajlt_nem_ir_felul(tmp_path):
    (tmp_path / "Egri csillagok.mp3").write_bytes(b"regi")
    ut = K.kimeneti_ut(tmp_path, "Egri csillagok", darabolva=False)
    assert ut.name == "Egri csillagok (2).mp3"
    assert (tmp_path / "Egri csillagok.mp3").read_bytes() == b"regi"


def test_teli_almappat_nem_ir_felul_de_az_ureset_ujrahasznalja(tmp_path):
    teli = tmp_path / "Egri csillagok"
    teli.mkdir()
    (teli / "resz_001.mp3").write_bytes(b"x")
    assert K.kimeneti_ut(tmp_path, "Egri csillagok", True).parent \
        == tmp_path / "Egri csillagok (2)"
    ures = tmp_path / "Üres könyv"
    ures.mkdir()
    assert K.kimeneti_ut(tmp_path, "Üres könyv", True).parent == ures, \
        "üres mappát fölösleges duplázni"


def test_a_kimenet_mindig_mp3_es_a_mappan_belul_van(tmp_path):
    for cim, darab in (("A: b/c", True), ("A: b/c", False), ("", True)):
        ut = K.kimeneti_ut(tmp_path, cim, darab)
        assert ut.suffix == ".mp3"
        assert tmp_path in ut.parents


# ------------------------------------------------------------ hangjelzés

def test_a_ket_jelzohang_kulonbozik_es_ervenyes_wav(monkeypatch, tmp_path):
    """A siker és a hiba hangja NEM lehet összetéveszthető – ez a funkció
    lényege: hallás után tudni kell, mi történt."""
    import wave
    monkeypatch.setattr(K, "_HANG_MAPPA", tmp_path)
    kesz, hiba = K.hang_fajl(True), K.hang_fajl(False)
    assert kesz != hiba and kesz.is_file() and hiba.is_file()
    assert kesz.read_bytes() != hiba.read_bytes()
    for f in (kesz, hiba):
        with wave.open(str(f), "rb") as w:
            assert w.getnchannels() == 1 and w.getsampwidth() == 2
            assert w.getnframes() > 1000, "ne legyen kattanásnyi rövid"


def test_a_hangfajl_masodszor_mar_nem_keszul_ujra(monkeypatch, tmp_path):
    monkeypatch.setattr(K, "_HANG_MAPPA", tmp_path)
    elso = K.hang_fajl(True)
    ido = elso.stat().st_mtime_ns
    assert K.hang_fajl(True).stat().st_mtime_ns == ido


def test_a_jelzes_sosem_dobhat_hibat(monkeypatch):
    """A hang SOHA nem viheti el a kész munkát: ha bármi elszáll, csendben
    False a válasz."""
    monkeypatch.setattr(K, "hang_fajl",
                        lambda siker: (_ for _ in ()).throw(OSError("nincs")))
    assert K.jelzes(True) is False
