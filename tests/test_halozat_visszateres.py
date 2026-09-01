# -*- coding: utf-8 -*-
"""LETÖLTŐ-MOTOR MK2 — a letöltés túléli a kapcsolatkimaradást.

Ha elmegy a net, a letöltés eddig „hiba" lett és ott ragadt. Ez vakon a
legnehezebben észrevehető helyzet: a program megáll, semmi nem szól érte, és a
felhasználó órákkal később veszi észre, hogy nem történt semmi.

A „hiba" és a „várakozik a hálózatra" közti különbség nem szóhasználat:
a hiba azt üzeni, hogy TENNED KELL valamit; a várakozás azt, hogy nem kell.
"""
import time

from superdl import manager as M
from superdl import netcheck


def _mgr(tmp_path, **kw):
    return M.DownloadManager(str(tmp_path), persist=False, **kw)


def _job(kind="file", status="letöltés"):
    j = M.Job(url="http://a.hu/x.iso", kind=kind)
    j.progress.status = status
    return j


# ---- a besorolás: mikor várakozás, és mikor valódi hiba ---------------

def test_halozati_hibanal_varakozas(monkeypatch):
    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    assert M.DownloadManager.halozati_eredetu(
        "urlopen error [Errno 11001] getaddrinfo failed") is True


def test_ha_van_net_akkor_VALODI_hiba(monkeypatch):
    """A `looks_like_offline` mintái közt ott az »ssl« és a »timeout« is, amit
    egy lassú szerver is kivált – közben a net tökéletes. Ilyenkor HIBÁT kell
    mondani, különben a felhasználó olyasmire várna, ami nem jön el."""
    monkeypatch.setattr(netcheck, "online", lambda **kw: True)
    assert M.DownloadManager.halozati_eredetu("read operation timed out") is False


def test_nem_halozati_szoveg_soha_nem_varakozas(monkeypatch):
    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    assert M.DownloadManager.halozati_eredetu(
        "A cél fájl már létezik ebben a mappában.") is False


def test_ures_uzenet(monkeypatch):
    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    assert M.DownloadManager.halozati_eredetu("") is False


# ---- a várakozó elem MEGMARAD a sorban --------------------------------

def test_a_varakozo_elem_mentodik(tmp_path):
    m = _mgr(tmp_path)
    j = _job(status=M.DownloadManager.HALOZATRA_VAR)
    assert m._persistable(j) is True, \
        "különben újraindítás után nyomtalanul eltűnne"


def test_a_varakozo_allapot_resumable():
    assert M.DownloadManager.HALOZATRA_VAR in M.DownloadManager.RESUMABLE


# ---- a figyelő -------------------------------------------------------

def test_offline_jelzes_egyszer_szol(tmp_path, monkeypatch):
    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    m = _mgr(tmp_path)
    m.jobs = [_job(status=M.DownloadManager.HALOZATRA_VAR),
              _job(status=M.DownloadManager.HALOZATRA_VAR)]
    kapott = []
    m.on_notice = lambda sz, job: kapott.append(sz)

    m._halozat_tick(time.time())
    assert len(kapott) == 1
    assert "Megszakadt az internetkapcsolat" in kapott[0]
    assert "2 letöltés" in kapott[0]

    m._halozat_tick(time.time())          # nem ismételgeti
    assert len(kapott) == 1


def test_a_jelzes_megnyugtat_nem_ijeszt():
    sz = M.DownloadManager.halozat_elment_uzenet(3)
    assert "Nem kell tenned semmit" in sz, \
        "a felhasználó ne kezdjen keresni valamit, amit nem tud megjavítani"


def test_visszateresnel_ujraindul_minden_varakozo(tmp_path, monkeypatch):
    m = _mgr(tmp_path)
    inditasok = []
    monkeypatch.setattr(m, "_launch", lambda job: inditasok.append(job))
    a = _job(status=M.DownloadManager.HALOZATRA_VAR)
    b = _job(kind="torrent", status=M.DownloadManager.HALOZATRA_VAR)
    m.jobs = [a, b]
    kapott = []
    m.on_notice = lambda sz, job: kapott.append(sz)

    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    most = time.time()
    m._halozat_tick(most)                       # offline: jelez, nem indít
    assert inditasok == []

    monkeypatch.setattr(netcheck, "online", lambda **kw: True)
    m._halozat_tick(most + M.DownloadManager.HALO_ELLENORZES_SEC + 1)
    assert inditasok == [a, b]
    assert a.progress.status == "várakozik" and b.progress.status == "várakozik"
    assert M.DownloadManager.HALOZAT_VISSZAJOTT in kapott


def test_nem_ellenoriz_masodpercenkent(tmp_path, monkeypatch):
    """A netcheck TCP-kapcsolatot nyit; másodpercenként próbálgatni pazarlás."""
    hivasok = []
    monkeypatch.setattr(netcheck, "online",
                        lambda **kw: hivasok.append(1) or False)
    m = _mgr(tmp_path)
    m.jobs = [_job(status=M.DownloadManager.HALOZATRA_VAR)]
    most = time.time()
    for i in range(5):
        m._halozat_tick(most + i)
    assert len(hivasok) == 1


def test_varakozo_nelkul_nincs_halozat_ellenorzes(tmp_path, monkeypatch):
    hivasok = []
    monkeypatch.setattr(netcheck, "online",
                        lambda **kw: hivasok.append(1) or True)
    m = _mgr(tmp_path)
    m.jobs = [_job(status="letöltés")]
    m._halozat_tick(time.time())
    assert hivasok == [], "ne mérjük a netet, ha senki nem vár rá"


# ---- a két gépezet nem lép egymásra -----------------------------------

def test_a_halozatra_varo_torrent_nem_kap_ujraproba_utemezest(tmp_path):
    """A hálózatfigyelő és az újrapróba ugyanazt az elemet nem indíthatja
    kétszer. Az újrapróba csak »hiba« állapotra fut."""
    m = _mgr(tmp_path)
    j = _job(kind="torrent", status=M.DownloadManager.HALOZATRA_VAR)
    m._retry_tick(j, time.time())
    assert j.next_retry_at is None


def test_a_run_job_halozati_hibanal_varakozasra_valt(tmp_path, monkeypatch):
    """Végponttól végpontig: a letöltő hálózati hibát dob → a job nem »hiba«
    lesz, hanem várakozás, ÜRES hibaszöveggel (nincs mit elolvasni rajta)."""
    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    m = _mgr(tmp_path)
    j = _job()
    m.jobs = [j]

    class Halott:
        def run(self):
            raise OSError("[Errno 11001] getaddrinfo failed")

    monkeypatch.setattr(M, "SegmentDownloader",
                        lambda *a, **k: Halott())
    m._run_job(j)
    assert j.progress.status == M.DownloadManager.HALOZATRA_VAR
    assert j.progress.error == ""


def test_a_run_job_valodi_hibanal_hibat_mond(tmp_path, monkeypatch):
    monkeypatch.setattr(netcheck, "online", lambda **kw: True)
    m = _mgr(tmp_path)
    j = _job()
    m.jobs = [j]

    class Halott:
        def run(self):
            raise RuntimeError("a lemez megtelt")

    monkeypatch.setattr(M, "SegmentDownloader", lambda *a, **k: Halott())
    m._run_job(j)
    assert j.progress.status == "hiba"
    assert "lemez" in j.progress.error


def test_a_kezi_leallitas_nem_valik_varakozassa(tmp_path, monkeypatch):
    monkeypatch.setattr(netcheck, "online", lambda **kw: False)
    m = _mgr(tmp_path)
    j = _job(status="leállítva")
    m.jobs = [j]

    class Halott:
        def run(self):
            raise OSError("connection reset")

    monkeypatch.setattr(M, "SegmentDownloader", lambda *a, **k: Halott())
    m._run_job(j)
    assert j.progress.status == "leállítva"
