# -*- coding: utf-8 -*-
"""Célmappa-SZÓKÖZ elleni védelem (WinError 123) + hangoskönyv záró szöveg.

Bug (felhasználó, saját super-dl.com podcast): a beállított célmappa VEZETŐ
szóközzel mentődött (" C:\\Users\\...\\Documents"), és Windowson az így kezdődő
útvonal ÉRVÉNYTELEN → [WinError 123] → MINDEN letöltés (így a podcast-epizódoké
is) elhasal. Korábban ez okozta a „feltámadást" is: a hibás letöltés sosem lett
kész → a figyelő újra meg újra próbálta. A javítás a szóközt a letöltő-rétegben
levágja (Downloader + a közös menedzser-csomópont), a GUI pedig a beállítást is
kitisztítja betöltéskor/mentéskor."""
import inspect

import pytest

md_mod = pytest.importorskip("superdl.media")


@pytest.mark.parametrize("nyers, tiszta", [
    (" C:\\Users\\msn\\Documents", "C:\\Users\\msn\\Documents"),
    ("C:\\Users\\msn\\Documents ", "C:\\Users\\msn\\Documents"),
    ("  C:\\zene  ", "C:\\zene"),
    ("C:\\rendes\\ut", "C:\\rendes\\ut"),   # ép útvonal változatlan
])
def test_mediadownloader_levagja_a_szokozt(nyers, tiszta):
    md = md_mod.MediaDownloader("http://példa/videó", nyers)
    assert md.out_dir == tiszta


def test_outtmpl_nem_kezdodik_szokozzel(tmp_path):
    """A tényleges path-építés: a base a stripelt mappa, így az outtmpl nem
    kezdődhet szóközzel (ez törte el WinError 123-mal)."""
    md = md_mod.MediaDownloader("http://példa/videó", "  " + str(tmp_path))
    base = str(md.out_dir)
    assert not base.startswith(" ")
    # az outtmpl a base + "/..." – szóköz nélkül indul
    assert (base + "/%(title)s.%(ext)s").lstrip() == base + "/%(title)s.%(ext)s"


def test_manager_kozos_csomopont_stripel():
    """A közös menedzser-csomópont (_run_job) a job.out_dir/self.out_dir értéket
    stripeli, mielőtt bármelyik letöltőnek átadná (torrent/média/szegmens)."""
    mgr_mod = pytest.importorskip("superdl.manager")
    src = inspect.getsource(mgr_mod.DownloadManager._run_job)
    assert ".strip()" in src
    assert "out_dir = str(job.out_dir or self.out_dir).strip()" in src


def test_audiobook_zaro_szoveg():
    """A hangoskönyv záró mondata a felhasználó által választott, szebb
    változat, és a jogi nyilatkozat is megmarad."""
    ab = pytest.importorskip("superdl.audiobook")
    assert ab.OUTRO.startswith("A hangoskönyv végéhez értünk.")
    # a régi, faramuci „A hangoskönyv vége." már nem szerepel önálló mondatként
    assert "hangoskönyv vége." not in ab.OUTRO
    # a jogi nyilatkozat érintetlen
    assert "terjesztése vagy" in ab.OUTRO
    assert "engedélye nélkül tilos" in ab.OUTRO
