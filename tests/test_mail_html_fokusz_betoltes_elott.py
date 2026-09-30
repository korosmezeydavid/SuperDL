"""Super Mail 1.6.4 – Schibik Miklós (2026-09-30): a HTML nézet
megnyitásakor OK-gombos „Error running JavaScript" ablak ugrott fel, és a
fókusz a fejlécen maradt. Ok: a _html_fokusz a lap betöltése ELŐTT hívta a
RunScript-et; a wx ilyenkor figyelmeztetést naplóz (GUI-ban ablak)."""
import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parents[1]
MAIL = GYOKER / "modules_src" / "mail"
MAILWIN = MAIL / "mail_mod" / "mailwin.py"
if not MAILWIN.exists():
    pytest.skip("a Super Mail forrása nincs itt", allow_module_level=True)


def _fuggveny(nev):
    fa = ast.parse(MAILWIN.read_text(encoding="utf-8"))
    for n in ast.walk(fa):
        if isinstance(n, ast.FunctionDef) and n.name == nev:
            return ast.get_source_segment(MAILWIN.read_text(encoding="utf-8"), n)
    raise AssertionError(nev + " nincs meg")


def test_fokusz_csak_betoltes_utan_futtat_szkriptet():
    src = _fuggveny("_html_fokusz")
    assert "_html_kesz" in src
    assert src.index("_html_kesz") < src.index("self._html.RunScript(")
    assert "LogNull" in src


def test_betoltes_jelzi_hogy_kesz():
    assert "self._html_kesz = True" in _fuggveny("_html_betoltodott")


ELO = textwrap.dedent(r'''
    import sys
    sys.path.insert(0, r"%s")
    import wx
    import wx.html2 as h2
    from mail_mod import mail_core as MC
    if not h2.WebView.IsBackendAvailable(h2.WebViewBackendEdge):
        print("NINCS-EDGE"); sys.exit(0)
    app = wx.App(False)
    wx.Log.SetActiveTarget(wx.LogStderr())
    f = wx.Frame(None); wv = h2.WebView.New(f, backend=h2.WebViewBackendEdge)
    wv.SetPage(MC.html_megjeleniteshez("<p>szia</p>"), "")
    print("ELOTTE", wv.RunScript(MC.HTML_FOKUSZ_JS)[0], flush=True)
    def betolt(e):
        print("UTANA", wv.RunScript(MC.HTML_FOKUSZ_JS)[0], flush=True)
        wx.CallAfter(app.ExitMainLoop)
    wv.Bind(h2.EVT_WEBVIEW_LOADED, betolt)
    f.Show(); wx.CallLater(15000, app.ExitMainLoop); app.MainLoop()
''') % MAIL


def test_elo_webview_betoltes_elott_hibazik_utana_nem():
    """Igazolja a feltevést: betöltés előtt a RunScript hibát naplóz, utána
    lefut – ezért kell a _html_kesz őr."""
    r = subprocess.run([sys.executable, "-c", ELO], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    ki = r.stdout + r.stderr
    if "NINCS-EDGE" in ki or "No module named 'wx" in ki:
        pytest.skip("nincs wx.html2 Edge ezen a gépen")
    assert "ELOTTE False" in ki, ki[-800:]
    assert "UTANA True" in ki, ki[-800:]
