"""Schibik Miklós (2026-09-28): HTML nézet a levélolvasóban, e-mail címre
Enter új levelet nyit. A HTML-t megtisztítjuk, semmit nem tölt le."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "mail"))

from mail_mod import mail_core as MC     # noqa: E402


def test_emailcimek_a_szovegbol():
    assert MC.emailcimek_szovegbol(
        "írj: schibik@gmail.com. vagy x.y+z@a-b.co.uk, de ne: @nem, foo@bar, "
        "SCHIBIK@gmail.com") == ["schibik@gmail.com", "x.y+z@a-b.co.uk"]
    assert MC.emailcimek_szovegbol("") == []


def test_html_tisztitas():
    h = MC.html_megjeleniteshez(
        '<html><head><script>alert(1)</script><style>a{color:red}</style></head>'
        '<body onload="x()"><p style="background:url(http://t/x.png)">Szia '
        '<a href="javascript:alert(1)">rossz</a> '
        '<a href="https://a.hu/x" onclick="y()">jó</a> '
        '<a href="mailto:a@b.hu">levél</a>'
        '<img src="http://t.rack/p.gif" alt="logó"><form><input></form>'
        '<iframe src="http://x"></iframe><!-- titok --></p></body></html>')
    for tilos in ("<script", "alert(1)</script", "onload", "onclick", "<form",
                  "<input", "<iframe", "javascript:", "t.rack", "titok",
                  ":url(http", "mailto:"):
        assert tilos not in h, tilos
    assert '<a href="https://a.hu/x">jó</a>' in h
    assert "[kép: logó]" in h
    assert 'href="%sa@b.hu"' % MC.MAILTO_ELOTAG in h
    assert "Content-Security-Policy" in h and "default-src 'none'" in h


def test_sima_szoveg_linkesitve():
    h = MC.szoveg_megjeleniteshez("Nézd: https://x.hu/a, és <írj>: a@b.hu.")
    assert '<a href="https://x.hu/a">https://x.hu/a</a>,' in h
    assert '<a href="%sa@b.hu">a@b.hu</a>.' % MC.MAILTO_ELOTAG in h
    assert "&lt;írj&gt;" in h                       # a szöveg nem HTML


def test_mailto_cim():
    assert MC.mailto_cim(MC.MAILTO_ELOTAG + "a%40b.hu?subject=x") == "a@b.hu"
    assert MC.mailto_cim("mailto:c@d.hu") == "c@d.hu"
    assert MC.mailto_cim("https://x.hu/") == ""
    assert MC.mailto_cim("") == ""


def test_az_olvaso_ablak_tudja_a_html_nezetet():
    src = (Path(__file__).resolve().parents[1] / "modules_src" / "mail"
           / "mail_mod" / "mailwin.py").read_text(encoding="utf-8")
    assert "def _nezet_valt(self" in src and "def _html_navigal(self" in src
    assert "def _uj_level_cimre(self" in src
    assert '"levelnezet"' in src                    # beállítás mentve
    assert 'ch == "h"' in src                       # Ctrl+H
