# -*- coding: utf-8 -*-
"""Karcsi hibajelentése (2026-09-09): „nem tudod meg, hogy a hiba miért
keletkezett, és mi a hiba egyáltalán".

A jelentés nem egy hibáról szólt, hanem arról, hogy a hibáról NEM LEHET
MEGTUDNI SEMMIT. Ezek a tesztek négy külön néma romlást fognak meg:

1. a hiba oka TÚLÉLI a program bezárását (eddig nyomtalanul eltűnt);
2. a FELOLVASOTT mondat sosem nyers angol motorüzenet — vakon negyven hexa
   karakter felolvasása pontosan annyit ér, mint a csend;
3. a naplóba viszont a NYERS szöveg kerül, mert azt lehet továbbküldeni;
4. ugyanaz a torrent nem indulhat kétszer, mert az aria2 egy másodpercen
   belül hibára futtatja — és a felhasználó egy örökre hibás sort kap.
"""

import time

import pytest

from superdl import hibaszoveg
from superdl.manager import DownloadManager, Job


INFOHASH_HIBA = ("InfoHash 802c237839fdd4e17b8610a1a290012dcf3cbde5 "
                 "is already registered.")


# ---- 1. a hiba oka megmarad --------------------------------------------

def test_a_hiba_szovege_bekerul_a_mentett_rekordba():
    """EZ Karcsi panasza. A `to_record()` eddig az állapotot mentette, az
    okot nem — újraindítás után a magyarázat végleg elveszett."""
    j = Job(url="x.torrent", kind="torrent")
    j.hibat_rogzit(INFOHASH_HIBA)
    r = j.to_record()
    assert r["utolso_hiba"] == INFOHASH_HIBA
    assert r["utolso_hiba_ideje"] is not None


def test_az_ures_hibaszoveg_NEM_felejteti_el_a_korabbit():
    """Egy újabb, sikeres indítás nem törölheti el az előző magyarázatát:
    a felhasználó épp azt keresné."""
    j = Job(url="x.torrent", kind="torrent")
    j.hibat_rogzit(INFOHASH_HIBA)
    j.hibat_rogzit("")
    j.hibat_rogzit("   ")
    assert j.utolso_hiba == INFOHASH_HIBA


def test_a_nyers_szoveget_tesszuk_el_nem_a_forditast():
    """Ha holnap felismerünk egy mintát, a RÉGI bejegyzés is értelmet nyer.
    Fordítva sosem: egy lefordított szövegből nem lesz vissza a nyers."""
    j = Job(url="x.torrent", kind="torrent")
    j.hibat_rogzit(INFOHASH_HIBA)
    assert "InfoHash" in j.utolso_hiba


def test_a_visszatoltott_hiba_NEM_teszi_hibassa_a_sort(tmp_path, monkeypatch):
    """⚠️ A visszatöltött magyarázat az élő hibamezőbe írva azt jelentené,
    hogy a sor MOST hibás — akkor is, ha épp szépen fut. Az ilyen hamis
    riasztás ugyanaz a kár, mint a hallgatás, csak fordítva."""
    from superdl import store

    rekord = [{"url": "x.torrent", "kind": "torrent", "status": "leállítva",
               "user_stopped": True, "utolso_hiba": INFOHASH_HIBA,
               "utolso_hiba_ideje": time.time()}]
    monkeypatch.setattr(store, "load_queue", lambda: rekord)
    m = DownloadManager(str(tmp_path), persist=False)
    try:
        visszaallt = m.restore()
        assert len(visszaallt) == 1
        j = visszaallt[0]
        assert j.utolso_hiba == INFOHASH_HIBA      # a magyarázat megvan
        assert j.progress.error == ""              # de a sor NEM hibás
        assert j.progress.status != "hiba"
    finally:
        m.close()


# ---- 2. a felolvasott mondat sosem nyers angol --------------------------

def test_az_ismeretlen_uzenetbol_NEM_lesz_felolvasott_angol_szoveg():
    """A hash felolvasva nem információ, hanem zaj: a felhasználó utána
    pontosan annyit tud, mint előtte, csak fáradtabb."""
    mondat = hibaszoveg.olvashato("Xyz engine failure 0x8007005 QQQ")
    assert "Xyz engine failure" not in mondat
    assert mondat == hibaszoveg.ISMERETLEN_MONDAT
    # és MEGMONDJA, hol a pontos szöveg – enélkül csak udvarias csend volna
    assert "napló" in mondat.lower()


def test_az_infohash_hibabol_magyar_mondat_lesz_hash_nelkul():
    mondat = hibaszoveg.olvashato(INFOHASH_HIBA)
    assert "802c2378" not in mondat            # a hash nem hangzik el
    assert "már fut" in mondat.lower()
    assert "control d" in mondat.lower()       # meg is mondja, mit tegyen


def test_a_sajat_magyar_mondatunkat_nem_csereli_le():
    """⚠️ Enélkül a saját, jó magyar mondatunkat az `olvashato()`
    ismeretlennek hinné, és a „nem ismerjük fel" szövegre cserélné — vagyis
    pont azt a magyarázatot dobnánk el, amit beletettünk."""
    sajat = ("Ez a torrent már fut a listában (film.mkv) – ugyanazt kétszer "
             "nem lehet elindítani.")
    assert hibaszoveg.olvashato(sajat) == sajat


def test_az_ismert_hibak_forditasa_valtozatlan():
    """A meglévő fordítások nem sérülhettek: az `olvashato()` csak az
    ISMERETLEN ágat változtatja meg."""
    m = "aria2c.exe not found"
    assert hibaszoveg.olvashato(m) == hibaszoveg.emberi(m)
    assert "aria2" in hibaszoveg.olvashato(m)


# ---- 3. a napló a nyers szöveget kapja ----------------------------------

def test_az_emberi_TOVABBRA_IS_a_nyerset_adja_vissza_ismeretlenre():
    """SZÁNDÉKOS különbség az `olvashato()`-hoz képest. A naplóba a pontos
    szöveg való: abból derül ki utólag, mi történt, és azt lehet elküldeni
    nekünk. Ha az `emberi()` is elnyelné, a hibát soha nem javítanánk ki."""
    m = "Xyz engine failure 0x8007005 QQQ"
    assert hibaszoveg.emberi(m) == m


# ---- 4. az elakadás-mondat kimondja a hibát is --------------------------

def test_az_elakadas_mondat_elmondja_a_legutobbi_hibat_is():
    """Aki elakadt sorban ragadt, eddig SOHA nem tudta meg, hogy a motor
    jelzett-e közben valamit — pedig épp az árulná el, miért nem indul."""
    mondat = hibaszoveg.gond_mondat(
        "film.mkv", "letöltés", INFOHASH_HIBA, elakadt=True,
        elakadas_oka="Vannak forrásaim, mégsem érkezik adat.")
    assert "elakadt" in mondat
    assert "Vannak forrásaim" in mondat
    assert "már fut" in mondat.lower()          # a hiba is elhangzik
    assert "802c2378" not in mondat             # de hash nélkül


def test_hibaszoveg_nelkul_az_elakadas_mondat_valtozatlan():
    """Ha nincs mit hozzátenni, ne toldjunk oda üres mondatot."""
    mondat = hibaszoveg.gond_mondat(
        "film.mkv", "letöltés", "", elakadt=True,
        elakadas_oka="Nem találok senkit, akitől tölthetnék.")
    assert mondat.endswith("Nem találok senkit, akitől tölthetnék.")
    assert "legutóbbi" not in mondat


# ---- 5. ugyanaz a torrent nem indulhat kétszer --------------------------

@pytest.fixture
def mgr(tmp_path):
    m = DownloadManager(str(tmp_path), persist=False)
    yield m
    m.close()


def _torrent(mgr, url="film.torrent", status="letöltés"):
    j = Job(url=url, kind="torrent")
    j.progress.status = status
    mgr.jobs.append(j)
    return j


def test_az_elo_iker_torrentet_megtalaljuk(mgr):
    """Mérve 2026-09-10 (aria2c 1.37.0): amíg a régi példány él, a második
    hozzáadás egy másodpercen belül hibára fut."""
    elso = _torrent(mgr)
    masodik = Job(url="film.torrent", kind="torrent")
    assert mgr._mar_fut_e(masodik) is elso


@pytest.mark.parametrize("status", ["hiba", "kész", "leállítva",
                                    DownloadManager.HALOZATRA_VAR])
def test_a_mar_NEM_elo_iker_nem_akadaly(mgr, status):
    """⚠️ Ezek az állapotok már ELENGEDTÉK a motort — és épp ilyenkor akar a
    felhasználó újraindítani. Ha ezeket is ütközésnek vennénk, a javítást
    tennénk lehetetlenné azzal a szabállyal, ami segíteni akart."""
    _torrent(mgr, status=status)
    masodik = Job(url="film.torrent", kind="torrent")
    assert mgr._mar_fut_e(masodik) is None


def test_a_mas_url_es_a_sajat_maga_nem_utkozik(mgr):
    elso = _torrent(mgr)
    assert mgr._mar_fut_e(elso) is None                     # önmagával nem
    masik = Job(url="masik.torrent", kind="torrent")
    assert mgr._mar_fut_e(masik) is None


# ---- 6. a Ctrl+F6 nem gyárthat hibát ------------------------------------

class _MegEl:
    """Letöltő-utánzat, ami szerint a motor MÉG NEM engedte el a torrentet."""

    def __init__(self, progress):
        self.progress = progress
        self._stop = type("E", (), {"_v": False,
                                    "set": lambda s: setattr(s, "_v", True),
                                    "is_set": lambda s: s._v})()

    def stop(self):
        self._stop.set()
        self.progress.status = "leállítva"

    def regisztralt(self):
        return True


def test_a_kenyszeritett_ujrainditas_NEM_indit_ha_a_motor_meg_tartja(
        mgr, monkeypatch):
    """EZ Karcsi „kb. 1 másodperc, majd hiba" élménye. Ha vakon újraindítunk,
    az aria2 elutasítja, és az addig csak ELAKADT letöltésből VÉGLEG HIBÁS
    lesz — vagyis a javítás rontana."""
    j = _torrent(mgr)
    j.progress.elakadt = True
    j.downloader = _MegEl(j.progress)
    inditva = []
    monkeypatch.setattr(mgr, "start", lambda job: inditva.append(job))
    assert mgr.kenyszeritett_ujrainditas(j, varakozas=0.4) is False
    assert inditva == []                     # NEM indítottunk újra
    assert j.progress.elakadt is True        # és nem hazudtuk, hogy megoldva
