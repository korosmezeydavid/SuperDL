# -*- coding: utf-8 -*-
"""LETÖLTŐ-MOTOR MK1 — a torrent kérdés nélkül folytatódik.

A kérés: ha egy torrent le- vagy feltöltése nem lett kitörölve, a program
indításkor NE kérdezzen — folytassa a letöltést, vagy végezze a seed-
kötelezettséget, törlésig vagy KÉZI leállításig.

Négy külön ponton akadt meg, és mind a négyre külön teszt van itt.
A legfontosabb tanulság a kódból: a SZÁNDÉKOT nem szabad a státuszszóból
visszakövetkeztetni, mert a kilépés és a kézi leállítás UGYANAZT írja be,
és a kettőnek ellentétes a jelentése.
"""
import time
import types

from superdl import manager as M
from superdl import retrypolicy as R
from superdl import torrent as T


def _mgr(tmp_path, **kw):
    return M.DownloadManager(str(tmp_path), persist=False, **kw)


def _rec(status="seedelés", **kw):
    r = {"url": "magnet:?xt=urn:btih:abc", "kind": "torrent",
         "status": status, "verify": False, "overwrite": False}
    r.update(kw)
    return r


def _restore_hivasok(monkeypatch, tmp_path, rec, **mgr_kw):
    """A restore() melyik paraméterekkel hívja az add()-et?"""
    monkeypatch.setattr(M.store, "load_queue", lambda: [rec])
    m = _mgr(tmp_path, **mgr_kw)
    hivasok = []

    def fake_add(url, **kw):
        hivasok.append(kw)
        return types.SimpleNamespace(
            progress=types.SimpleNamespace(filename=""), user_stopped=False)

    monkeypatch.setattr(m, "add", fake_add)
    m.restore()
    return hivasok


# ---- 1. pont: a „nem" válasz NE törölje a torrenteket ------------------
# (a GUI-oldali szétválasztás; itt azt rögzítjük, amire a GUI épül)

def test_a_torrent_kulon_kezelendo_a_folytatas_kerdesnel():
    """A mentett sorból a torrentek és a többiek szétválaszthatók: a kérdés
    csak az utóbbiakra vonatkozhat."""
    sor = [_rec(status="seedelés"),
           {"url": "http://a.hu/x.iso", "kind": "file", "status": "letöltés"}]
    torrentek = [r for r in sor if r.get("kind") == "torrent"]
    egyeb = [r for r in sor if r.get("kind") != "torrent"]
    assert len(torrentek) == 1 and len(egyeb) == 1


# ---- 2. pont: a „leállítva" torrent MÉGIS elindul ----------------------

def test_leallitva_mentett_torrent_megis_elindul(monkeypatch, tmp_path):
    """A kilépéskori stop_all() „leállítva"-t ír. Ha ezt szándéknak vennénk,
    a torrent SOHA többé nem indulna el magától."""
    h = _restore_hivasok(monkeypatch, tmp_path,
                         _rec(status="leállítva", user_stopped=False))
    assert h and h[0]["autostart"] is True


def test_kezzel_leallitott_torrent_NEM_indul_el(monkeypatch, tmp_path):
    h = _restore_hivasok(monkeypatch, tmp_path,
                         _rec(status="leállítva", user_stopped=True))
    assert h and h[0]["autostart"] is False


def test_a_kilepes_nem_szandek_a_kezi_leallitas_igen(tmp_path):
    """A 3. pont (versenyhelyzet) gyökér-fixe: a szándék külön mezőben van,
    nem a státuszszóban."""
    m = _mgr(tmp_path)
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    m.jobs.append(job)

    m.stop_all(felhasznaloi=False)          # kilépés
    assert job.user_stopped is False

    m.stop(job)                             # kézi leállítás
    assert job.user_stopped is True


def test_a_kezi_ujrainditas_visszavonja_a_leallitast(tmp_path, monkeypatch):
    m = _mgr(tmp_path)
    monkeypatch.setattr(m, "_launch", lambda job: None)
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.user_stopped = True
    job.retries = 3
    m.jobs.append(job)
    m.start(job)
    assert job.user_stopped is False and job.retries == 0


# ---- 4. pont: a hibára futott torrent a sorban marad -------------------

def test_a_hibas_torrent_a_sorban_marad(tmp_path):
    m = _mgr(tmp_path)
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.progress.status = "hiba"
    assert m._persistable(job) is True, \
        "hálózatkimaradás után eddig nyomtalanul eltűnt a sorból"


def test_a_kesz_torrent_is_a_sorban_marad(tmp_path):
    """A döntés szerint kézi leállításig seedel – tehát nem dobható el."""
    m = _mgr(tmp_path)
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.progress.status = "kész"
    assert m._persistable(job) is True


def test_a_hibas_NEM_torrent_tovabbra_sem_marad(tmp_path):
    m = _mgr(tmp_path)
    job = M.Job(url="http://a.hu/x.iso", kind="file")
    job.progress.status = "hiba"
    assert m._persistable(job) is False


def test_a_restore_sem_dobja_el_a_hibas_torrentet(monkeypatch, tmp_path):
    """A `_persistable()` TESTVÉR-szűrője. Ha csak az egyiket javítjuk, a
    mentés megtörténik, a visszatöltés viszont némán eldobja."""
    h = _restore_hivasok(monkeypatch, tmp_path, _rec(status="hiba"))
    assert h, "a hibás torrentnek vissza kell jönnie a sorba"


def test_a_hibas_NEM_torrentet_tovabbra_sem_tolti_vissza(monkeypatch, tmp_path):
    h = _restore_hivasok(monkeypatch, tmp_path,
                         {"url": "http://a.hu/x.iso", "kind": "file",
                          "status": "hiba"})
    assert h == []


def test_a_kesz_torrent_verify_modban_jon_vissza(monkeypatch, tmp_path):
    """Vezérlőfájl nélkül az aria2 „már létezik"-et dobna; a check-integrity
    validál és folytatja a seedelést."""
    h = _restore_hivasok(monkeypatch, tmp_path, _rec(status="kész"))
    assert h and h[0]["verify"] is True


def test_kesz_torrent_orok_seedelesnel_ujraindul(monkeypatch, tmp_path):
    h = _restore_hivasok(monkeypatch, tmp_path, _rec(status="kész"),
                         seed_forever=True)
    assert h and h[0]["autostart"] is True


def test_kesz_torrent_arany_modban_NEM_kezd_ujra_seedelni(monkeypatch, tmp_path):
    """Ha a felhasználó arányig kérte a seedelést, a „kész" azt jelenti, hogy
    az arány teljesült. Ilyenkor minden programindítás újraindítaná a
    megosztást – szemben a beállításával. A sorban marad, de nem indul."""
    h = _restore_hivasok(monkeypatch, tmp_path, _rec(status="kész"),
                         seed_forever=False)
    assert h and h[0]["autostart"] is False


# ---- a folytatás EGY MONDATA ------------------------------------------

def test_a_folytatas_egy_mondatban_szol(tmp_path):
    m = _mgr(tmp_path)
    tolto = M.Job(url="magnet:?xt=urn:btih:a", kind="torrent")
    tolto.progress.status = "letöltés"
    seedelo = M.Job(url="magnet:?xt=urn:btih:b", kind="torrent")
    seedelo.progress.status = "seedelés"
    sz = m.resume_summary([tolto, seedelo])
    assert "2 torrent folytatódik" in sz
    assert "1 letöltés" in sz and "1 megosztás" in sz


def test_torrent_nelkul_nincs_mondat(tmp_path):
    m = _mgr(tmp_path)
    job = M.Job(url="http://a.hu/x.iso", kind="file")
    assert m.resume_summary([job]) == ""


# ---- seed_forever ≠ seed_ratio 0 --------------------------------------

def test_seed_forever_nem_ugyanaz_mint_a_nulla_arany(tmp_path):
    """A CSAPDA: az aria2-nél a seed-ratio 0.0 = ÖRÖKKÉ, nálunk a 0 eddig azt
    jelentette, hogy EGYÁLTALÁN NE seedeljen. A két jelentés egymás
    ellentéte – ezért kell külön kapcsoló."""
    orok = T.TorrentDownloader("magnet:?x", str(tmp_path), seed_forever=True)
    o = orok.aria2_opciok()
    assert o["seed-ratio"] == "0.0"
    assert "seed-time" not in o, "a seed-time=0 pont megölné az örök seedelést"

    soha = T.TorrentDownloader("magnet:?x", str(tmp_path),
                               seed_ratio=0, seed_forever=False)
    s = soha.aria2_opciok()
    assert s["seed-time"] == "0", "a ne-seedelj jelentés nem sérülhet"


def test_a_megadott_arany_ervenyes_marad(tmp_path):
    d = T.TorrentDownloader("magnet:?x", str(tmp_path), seed_ratio=2.5,
                            seed_forever=False)
    assert d.aria2_opciok()["seed-ratio"] == "2.5"


# ---- MK8: feltöltési sávkorlát ----------------------------------------

def test_feltoltesi_savkorlat(tmp_path):
    """Eddig CSAK letöltési korlát volt: a seedelés megehette a teljes
    feltöltési sávot, amitől a saját letöltéseid is belassulnak."""
    d = T.TorrentDownloader("magnet:?x", str(tmp_path),
                            limit_bps=1000, upload_limit_bps=500)
    o = d.aria2_opciok()
    assert o["max-download-limit"] == "1000"
    assert o["max-upload-limit"] == "500"


def test_savkorlat_nelkul_nincs_kulcs(tmp_path):
    o = T.TorrentDownloader("magnet:?x", str(tmp_path)).aria2_opciok()
    assert "max-upload-limit" not in o and "max-download-limit" not in o


# ---- MK4: az újrapróba ütemezése és a mondat --------------------------

def test_novekvo_szunetek():
    assert [R.szunet(i) for i in range(6)] == [60, 120, 300, 600, 900, 900]


def test_emberi_ido_nem_orajel():
    assert R.emberi_ido(900) == "negyed óra"
    assert R.emberi_ido(60) == "egy perc"
    assert R.emberi_ido(300) == "5 perc"
    assert ":" not in R.emberi_ido(3600), "felolvasva a 01:00:00 használhatatlan"


def test_az_uzenet_megmondja_hanyadik_es_mikor():
    sz = R.uzenet(1)
    assert sz.startswith("Második")
    assert "2 perc" in sz


def test_az_ujraproba_utemezese(tmp_path, monkeypatch):
    m = _mgr(tmp_path)
    inditasok = []
    monkeypatch.setattr(m, "_launch", lambda job: inditasok.append(job))
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.progress.status = "hiba"
    m.jobs.append(job)

    most = time.time()
    m._retry_tick(job, most)                     # elsőre csak ÜTEMEZ
    assert job.next_retry_at == most + 60
    assert inditasok == []

    m._retry_tick(job, most + 30)                # még nincs itt az ideje
    assert inditasok == []

    m._retry_tick(job, most + 61)                # most indul
    assert inditasok == [job]
    assert job.retries == 1 and job.next_retry_at is None


def test_a_kezzel_leallitott_nem_probalkozik_ujra(tmp_path, monkeypatch):
    m = _mgr(tmp_path)
    inditasok = []
    monkeypatch.setattr(m, "_launch", lambda job: inditasok.append(job))
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.progress.status = "hiba"
    job.user_stopped = True
    m._retry_tick(job, time.time())
    assert job.next_retry_at is None and inditasok == []


def test_a_fajl_mar_letezik_dontest_var_nem_ujraprobat(tmp_path):
    """Az ütközés a felhasználó döntésére vár (kihagyom/felülírom/ellenőrzöm).
    Ha újrapróbálnánk, ugyanabba a falba futnánk 15 percenként, örökké."""
    m = _mgr(tmp_path)
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.progress.status = "hiba"
    job.progress.conflict = True
    m._retry_tick(job, time.time())
    assert job.next_retry_at is None


def test_a_nem_torrent_nem_kap_automatikus_ujraprobat(tmp_path):
    """Ebben a körben CSAK a torrentre kötjük be (MK1); a másik két motor
    az MK2/MK4 körben jön."""
    m = _mgr(tmp_path)
    job = M.Job(url="http://a.hu/x.iso", kind="file")
    job.progress.status = "hiba"
    m._retry_tick(job, time.time())
    assert job.next_retry_at is None


def test_a_jelzes_felolvashato(tmp_path):
    m = _mgr(tmp_path)
    kapott = []
    m.on_notice = lambda sz, job: kapott.append(sz)
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.progress.status = "hiba"
    m._retry_tick(job, time.time())
    assert kapott and "próbálkozás" in kapott[0]


# ---- a mentett rekord ------------------------------------------------

def test_a_szandek_bekerul_a_mentett_rekordba():
    job = M.Job(url="magnet:?xt=urn:btih:abc", kind="torrent")
    job.user_stopped = True
    assert job.to_record()["user_stopped"] is True
