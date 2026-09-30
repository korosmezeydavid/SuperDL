"""Super Mail 1.6.3 – Schibik Miklós (2026-09-29): a HTML nézetben az Esc nem
zárt, a fókusz a fejlécre esett. A híd: a lapba tett szkript visszaküldi a
nekünk szóló billentyűket; a fókusz a betöltés UTÁN a levél törzsére kerül."""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parents[1]
MAIL = GYOKER / "modules_src" / "mail"
if not (MAIL / "mail_mod" / "mail_core.py").exists():
    pytest.skip("a Super Mail forrása nincs itt", allow_module_level=True)
sys.path.insert(0, str(MAIL))
from mail_mod import mail_core as MC          # noqa: E402

if not hasattr(MC, "html_billentyu_ertelmez"):
    pytest.skip("mail 1.6.3 előtti forrás", allow_module_level=True)


def test_uzenet_ertelmezes():
    f = MC.html_billentyu_ertelmez
    assert f('{"key":"Escape","ctrl":false,"shift":false}') == ("Escape", False, False)
    assert f('{"key":"h","ctrl":true}') == ("h", True, False)
    assert f('{"key":"R","shift":true}') == ("r", False, True)
    assert f('{"key":"F9"}') == ("F9", False, False)
    # nem nekünk szóló / rossz
    assert f('{"key":"Tab"}') is None
    assert f('{"key":"ArrowDown"}') is None
    assert f('{"key":"é"}') is None
    assert f("nem json") is None and f("") is None and f(None) is None
    assert f('["Escape"]') is None and f('{"key": 27}') is None


def test_szkript_lenyege():
    js = MC.HTML_BILLENTYU_JS
    assert "Escape" in js and "keydown" in js and "postMessage" in js
    assert "window.%s.postMessage" % MC.HTML_HID_NEV in js
    assert "preventDefault" in js
    assert "document.body.focus" in js and "document.body.focus" in MC.HTML_FOKUSZ_JS


ELO = textwrap.dedent(r'''
    import sys, json
    sys.path.insert(0, r"%s")
    import wx
    import wx.html2 as h2
    from mail_mod import mail_core as MC
    if not h2.WebView.IsBackendAvailable(h2.WebViewBackendEdge):
        print("NINCS-EDGE"); sys.exit(0)
    app = wx.App(False)
    f = wx.Frame(None); wv = h2.WebView.New(f, backend=h2.WebViewBackendEdge)
    kapott = []
    wv.AddScriptMessageHandler(MC.HTML_HID_NEV)
    wv.AddUserScript(MC.HTML_BILLENTYU_JS)
    wv.Bind(h2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, lambda e: kapott.append(e.GetString()))
    def betolt(e):
        wv.RunScript("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));"
                     "document.dispatchEvent(new KeyboardEvent('keydown',{key:'h',ctrlKey:true,bubbles:true}));"
                     "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));")
        wx.CallLater(1500, lambda: (print("KAPOTT", json.dumps(kapott)), app.ExitMainLoop()))
    wv.Bind(h2.EVT_WEBVIEW_LOADED, betolt)
    wv.SetPage(MC.html_megjeleniteshez("<p>szia <b>levél</b></p>"), "")
    f.Show(); wx.CallLater(15000, app.ExitMainLoop); app.MainLoop()
''') % MAIL


def test_elo_webview_hid_visszaszol():
    """Igazi WebView2-ben: az Escape és a Ctrl+H visszajön, a Tab nem."""
    r = subprocess.run([sys.executable, "-c", ELO], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    ki = r.stdout + r.stderr
    if "NINCS-EDGE" in ki or "No module named 'wx" in ki:
        pytest.skip("nincs wx.html2 Edge ezen a gépen")
    assert r.returncode == 0, ki[-800:]
    sor = next((s for s in ki.splitlines() if s.startswith("KAPOTT")), "")
    assert sor, ki[-800:]
    import json
    uzenetek = [MC.html_billentyu_ertelmez(u) for u in json.loads(sor[len("KAPOTT "):])]
    assert ("Escape", False, False) in uzenetek, uzenetek
    assert ("h", True, False) in uzenetek, uzenetek
    assert all(u is not None for u in uzenetek), uzenetek     # a Tab nem jött át
