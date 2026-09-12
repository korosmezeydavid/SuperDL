# -*- coding: utf-8 -*-
"""Az összeomlás-nyom NE legyen félbevágva a hibajelentésben.

Dr. Kiss István 4.6.4-es jelentésében a natív összeomlás verme benne volt,
de a FEJLÉCE nem – pedig abban van a hiba kódja (`Windows fatal exception:
code 0x...`). Ok: a jelentés a napló utolsó 80 SORÁT csatolta, a nyom pedig
hosszabb ennél. Így úgy tűnt, van bizonyítékunk, valójában az ok hiányzott.
"""
import inspect

from superdl import diagnostics, osszeomlas

NAPLO_MINTA = """
=== SuperDL indult: 2026-09-09 10:00:00 (verzió: 4.6.1) ===

=== SuperDL indult: 2026-09-10 22:34:54 (verzió: 4.6.2) ===
Windows fatal exception: code 0x8001010d

Thread 0x00003314 [Thread-5 (work)] (most recent call first):
  File "ssl.py", line 717 in create_default_context
{toltelek}
Current thread 0x0000358c (most recent call first):
  File "bookwin.py", line 361 in _on_pick_book
  File "wx\\core.py", line 2254 in MainLoop

=== SuperDL indult: 2026-09-11 17:41:39 (verzió: 4.6.4) ===
"""


def _naplot_ir(tmp_path, toltelek_sorok=0):
    toltelek = "\n".join("  File \"x.py\", line %d in f" % i
                         for i in range(toltelek_sorok))
    p = tmp_path / "osszeomlas.log"
    p.write_text(NAPLO_MINTA.format(toltelek=toltelek), encoding="utf-8")
    return p


def test_a_fejlec_benne_van_hosszu_naplonal_is(tmp_path, monkeypatch):
    """EZ a lényeg: 80 sornál jóval hosszabb nyomnál is meglegyen a KÓD."""
    monkeypatch.setattr(osszeomlas, "NAPLO", _naplot_ir(tmp_path, 200))
    nyom = osszeomlas.utolso_osszeomlas()
    assert "Windows fatal exception: code 0x8001010d" in nyom
    assert "_on_pick_book" in nyom


def test_a_regi_sorfark_epp_ezt_vagta_le(tmp_path, monkeypatch):
    """Kontroll: a régi módszerrel a fejléc TÉNYLEG lemaradt."""
    monkeypatch.setattr(osszeomlas, "NAPLO", _naplot_ir(tmp_path, 200))
    regi = osszeomlas.naplo_szoveg(80)
    assert "Windows fatal exception" not in regi
    assert "_on_pick_book" in regi          # a verem látszott, az ok nem


def test_a_verzio_is_kideruljon(tmp_path, monkeypatch):
    """A blokkot nyitó „SuperDL indult" sor mondja meg, MELYIK verzió halt."""
    monkeypatch.setattr(osszeomlas, "NAPLO", _naplot_ir(tmp_path, 20))
    nyom = osszeomlas.utolso_osszeomlas()
    assert "verzió: 4.6.2" in nyom
    assert "verzió: 4.6.1" not in nyom      # a KORÁBBI indulás nem kell


def test_tul_hosszu_nyomnal_az_ELEJET_tartjuk_meg(tmp_path, monkeypatch):
    monkeypatch.setattr(osszeomlas, "NAPLO", _naplot_ir(tmp_path, 5000))
    nyom = osszeomlas.utolso_osszeomlas(max_sorok=50)
    assert "Windows fatal exception" in nyom     # az ok megmarad
    assert len(nyom.splitlines()) <= 51
    assert "a jelentés az ELEJÉT tartotta meg" in nyom


def test_nyom_nelkul_ures(tmp_path, monkeypatch):
    p = tmp_path / "osszeomlas.log"
    p.write_text("=== SuperDL indult: 2026-09-11 (verzió: 4.6.7) ===\n",
                 encoding="utf-8")
    monkeypatch.setattr(osszeomlas, "NAPLO", p)
    assert osszeomlas.utolso_osszeomlas() == ""


def test_hianyzo_fajl_nem_hal_meg(tmp_path, monkeypatch):
    monkeypatch.setattr(osszeomlas, "NAPLO", tmp_path / "nincs.log")
    assert osszeomlas.utolso_osszeomlas() == ""


def test_a_diagnosztika_a_teljes_nyomot_kotti_be():
    f = inspect.getsource(diagnostics.build_report)
    assert "utolso_osszeomlas()" in f
    assert "naplo_szoveg(80)" not in f


# ---- a natív fájlválasztó nyomot hagy ---------------------------------

def test_a_fajlvalaszto_figyeles_be_van_kotve():
    import pathlib
    gyoker = pathlib.Path(__file__).resolve().parents[1]
    forras = (gyoker / "superdl_gui.py").read_text(encoding="utf-8")
    assert "osszeomlas.fajlvalaszto_figyelese()" in forras


def test_a_figyeles_jegyzetel_es_tovabbenged(monkeypatch):
    wx = __import__("wx")
    naplo = []
    monkeypatch.setattr(osszeomlas, "jegyzet", naplo.append)
    monkeypatch.setattr(wx.FileDialog, "_superdl_figyelt", False,
                        raising=False)
    eredeti = wx.FileDialog.ShowModal
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda self: 5100)
    monkeypatch.setattr(wx.DirDialog, "_superdl_figyelt", True,
                        raising=False)
    try:
        osszeomlas.fajlvalaszto_figyelese()

        class _Hamis:
            def GetDirectory(self):
                return r"C:\Zene"

            def GetPath(self):
                return ""
        # a burok az OSZTÁLYRA került; hívjuk a hamis példányunkkal
        assert wx.FileDialog.ShowModal(_Hamis()) == 5100
    finally:
        wx.FileDialog.ShowModal = eredeti
        wx.FileDialog._superdl_figyelt = False
    assert any("megnyitása" in s and "Zene" in s for s in naplo)
    assert any("bezárva" in s for s in naplo)
