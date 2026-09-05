# -*- coding: utf-8 -*-
"""Laci hibajelentése (2026-09-05): a torrent áll, a program hallgat.

Három dolgot védenek ezek a tesztek, és mindhárom NÉMÁN tudna elromlani:

1. a peer-felderítés kapcsolói tényleg ott vannak az aria2 parancssorában;
2. az elakadt letöltés BEKERÜL a figyelmet igénylők közé — de a hálózatra
   várakozó továbbra sem (az MK2 nem csinálható vissza);
3. az elakadás oka valódi mondat, nem állapotszó.
"""

import time

import pytest

from superdl import hibaszoveg, torrent
from superdl.manager import DownloadManager, Job
from superdl.segment import Progress


# ---- 1. peer-felderítés ------------------------------------------------

def test_a_dht_belepesi_pont_ott_van(tmp_path):
    """EZ a hibajelentés lényege. A DHT az aria2-ben alapból „be van
    kapcsolva", de belépési pont nélkül üres marad az útválasztó tábla —
    vagyis papíron megy, valójában nem hoz egyetlen peert sem."""
    k = torrent.halozati_kapcsolok(tmp_path / "dht.dat")
    assert "--enable-dht=true" in k
    belepok = [x for x in k if x.startswith("--dht-entry-point=")]
    assert len(belepok) == 1
    assert ":" in belepok[0].split("=", 1)[1]


def test_a_dht_tabla_mentodik(tmp_path):
    """A megtanult tábla két indítás között is megmarad — enélkül minden
    indulás nulláról bootstrapel."""
    ut = tmp_path / "almappa" / "dht.dat"
    k = torrent.halozati_kapcsolok(ut)
    assert f"--dht-file-path={ut}" in k
    assert ut.parent.is_dir()          # a mappát létre is hozza


def test_a_tobbi_felderitesi_csatorna_is_be_van_kapcsolva(tmp_path):
    k = torrent.halozati_kapcsolok(tmp_path / "dht.dat")
    assert "--enable-peer-exchange=true" in k
    assert "--bt-enable-lpd=true" in k
    # magnetnél a metaadat mentése: enélkül minden újraindítás elölről kezdi
    assert "--bt-save-metadata=true" in k


def test_a_kiegeszito_trackerek_egyetlen_kapcsoloban_mennek(tmp_path):
    """Az aria2 vesszővel elválasztva várja őket. Ha külön kapcsolókként
    adnánk át, csak az UTOLSÓ érvényesülne — és ezt semmi nem jelezné."""
    k = torrent.halozati_kapcsolok(tmp_path / "dht.dat")
    tr = [x for x in k if x.startswith("--bt-tracker=")]
    assert len(tr) == 1
    lista = tr[0].split("=", 1)[1].split(",")
    assert len(lista) >= 3
    assert all(x.startswith(("udp://", "http://", "https://")) for x in lista)


def test_egyetlen_kapcsolo_sem_ures(tmp_path):
    k = torrent.halozati_kapcsolok(tmp_path / "dht.dat")
    assert all(x.startswith("--") and "=" in x for x in k)
    assert all(x.split("=", 1)[1] != "" for x in k)


# ---- 2. az elakadt elem figyelmet igényel ------------------------------

def _job(status="letöltés", kind="torrent", **kw):
    j = Job(url="magnet:?xt=urn:btih:abc", kind=kind)
    j.progress.status = status
    for k, v in kw.items():
        setattr(j.progress, k, v)
    return j


def test_az_elakadt_letoltes_figyelmet_igenyel():
    j = _job(elakadt=True)
    assert DownloadManager.figyelmet_igenyel(j) is True


def test_a_haladó_letoltes_nem_igenyel_figyelmet():
    assert DownloadManager.figyelmet_igenyel(_job()) is False


def test_a_halozatra_varo_akkor_sem_ha_elakadtnak_jeloltek():
    """⚠️ AZ MK2 VÉDELME. Az MK6-ban és az MK8-ban is előfordult, hogy egy új
    szabály csendben átengedte a hálózatra várakozót — mindkétszer a teszt
    fogta meg. A kizárásnak EGY helyen, LEGELÖL kell állnia, és az új ágnak
    utána."""
    j = _job(status=DownloadManager.HALOZATRA_VAR, elakadt=True)
    assert DownloadManager.figyelmet_igenyel(j) is False


def test_a_kesz_es_a_leallitott_sem_lesz_elakadt():
    for allapot in ("kész", "leállítva"):
        j = _job(status=allapot, elakadt=True)
        assert DownloadManager.figyelmet_igenyel(j) is False, allapot


# ---- 3. az elakadás OKA mondat, nem állapotszó -------------------------

def test_az_ok_harom_esetet_kulonboztet_meg():
    nincs = torrent.TorrentDownloader.elakadas_oka(0, 0)
    csak_reszlet = torrent.TorrentDownloader.elakadas_oka(0, 5)
    van_de_all = torrent.TorrentDownloader.elakadas_oka(3, 5)
    assert nincs != csak_reszlet != van_de_all
    assert nincs != van_de_all
    for mondat in (nincs, csak_reszlet, van_de_all):
        assert mondat.endswith(".") and len(mondat.split()) > 5


def test_a_gond_mondat_nem_azt_mondja_hogy_minden_rendben():
    """A hiba lényege ez volt: a program azt állította, hogy „letöltés" —
    vagyis megnyugtatta a felhasználót, miközben egy órája állt."""
    mondat = hibaszoveg.gond_mondat(
        "sorozat.torrent", "letöltés", "", elakadt=True,
        elakadas_oka="Nem találok seedert.")
    assert "elakadt" in mondat
    assert "sorozat.torrent" in mondat
    assert "Nem találok seedert." in mondat
    # a puszta állapotszó NEM lehet a válasz
    assert "állapota: letöltés" not in mondat


def test_a_gond_mondat_elakadas_nelkul_valtozatlan():
    """Regresszió: az ÚJ ág nem írhatja felül a régi viselkedést."""
    mondat = hibaszoveg.gond_mondat("a.mp4", "hiba", "HTTP Error 403")
    assert "a.mp4" in mondat
    assert "elakadt" not in mondat


# ---- 4. a kényszerített újraindítás ------------------------------------

class _Hamis:
    """Letöltő-utánzat: annyit tud, hogy leállítható."""

    def __init__(self, progress):
        self.progress = progress
        self._stop = type("E", (), {"_v": False,
                                    "set": lambda s: setattr(s, "_v", True),
                                    "is_set": lambda s: s._v})()

    def stop(self):
        self._stop.set()
        self.progress.status = "leállítva"


@pytest.fixture
def mgr(tmp_path):
    m = DownloadManager(str(tmp_path), persist=False)
    yield m
    m.close()


def test_a_kenyszeritett_ujrainditas_csak_torrentre_szol(mgr, tmp_path):
    j = _job(kind="file")
    assert mgr.kenyszeritett_ujrainditas(j) is False


def test_a_kenyszeritett_ujrainditas_egyszeri_ellenorzest_ker(mgr,
                                                              monkeypatch):
    """A `verify` MENTŐDIK, tehát ha azt írnánk át, minden későbbi indulás is
    ellenőrizne — nagy torrentnél ez percek. Ezért átmeneti jelző."""
    j = _job(elakadt=True)
    j.downloader = _Hamis(j.progress)
    inditva = []
    monkeypatch.setattr(mgr, "start", lambda job: inditva.append(job))
    assert mgr.kenyszeritett_ujrainditas(j, varakozas=0.5) is True
    assert inditva == [j]
    assert j.kenyszer_ujra is True         # egyszeri kérés
    assert j.verify is False               # a MENTETT mező érintetlen
    assert j.progress.elakadt is False     # a jelzést visszavontuk
    assert j.downloader._stop.is_set()     # a régi munkát leállítottuk


def test_az_ujrainditas_megvarja_a_regi_szalat(mgr, monkeypatch):
    """Ha az új indítás ráfutna a még futó régire, két szál kezelné ugyanazt
    a jobot — és a mentés sorrendje eldönthetetlenné válna (MK8 tanulsága)."""
    j = _job(elakadt=True)
    j.downloader = _Hamis(j.progress)

    def lassu_stop():
        # a szál csak késve áll meg
        j.downloader._stop.set()

    j.downloader.stop = lassu_stop
    monkeypatch.setattr(mgr, "start", lambda job: None)
    kezdet = time.monotonic()
    mgr.kenyszeritett_ujrainditas(j, varakozas=0.6)
    # a státusz végig „letöltés" maradt, tehát KIVÁRTA a határidőt
    assert time.monotonic() - kezdet >= 0.5
