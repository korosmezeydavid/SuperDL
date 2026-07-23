# -*- coding: utf-8 -*-
"""Közös URL-biztonság (SSRF + méretkorlát) – Herman Tibi CAL-P0-07 /
NEWS-P0-02 / POD-P0-02. A hírolvasó, a podcast és a külső naptár TETSZŐLEGES,
idegen forrásból származó címet tölt le."""
import pathlib

import pytest

from superdl import urlpolicy as U

ROOT = pathlib.Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("url", [
    "http://localhost:8080/admin",
    "http://127.0.0.1/",
    "http://[::1]/",
    "http://192.168.0.1/setup",
    "http://10.0.0.5/",
    "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data/",   # felhő-metaadat végpont
    "http://0.0.0.0/",
])
def test_belso_cimek_blokkolva(url):
    with pytest.raises(U.UrlNotAllowed):
        U.check_url(url)


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/win.ini",
    "javascript:alert(1)",
    "ftp://pelda.hu/x",
    "data:text/html,<b>x</b>",
    "",
])
def test_nem_webes_semak_blokkolva(url):
    with pytest.raises(U.UrlNotAllowed):
        U.check_url(url)


def test_nyilvanos_cim_atmegy():
    assert U.check_url("https://example.com/feed.xml").startswith("https://")


def test_is_web_url():
    assert U.is_web_url("http://a.hu") and U.is_web_url("https://a.hu")
    assert not U.is_web_url("file:///c:/x")
    assert not U.is_web_url("custom://x")
    assert not U.is_web_url("")


def test_meretkorlat_letezik():
    assert U.DEFAULT_MAX_BYTES > 0
    assert "Content-Length" in _src("superdl/urlpolicy.py")


def test_atiranyitas_ujraellenorzese():
    """A támadó ártalmatlan címről irányíthatna át a belső hálózatra."""
    src = _src("superdl/urlpolicy.py")
    assert "_SafeRedirectHandler" in src
    assert "redirect_request" in src and "check_url(newurl)" in src


# ---- a tényleges bekötések ------------------------------------------------

def test_ics_letoltes_vedve():
    src = _src("superdl/organizer.py")
    assert "urlpolicy.safe_read_text" in src, "az ICS-sync nem védett"


def test_hirolvaso_cikkletoltes_vedve():
    src = _src("modules_src/szervezes/szervezes_mod/news.py")
    assert "urlpolicy.safe_open" in src, "a cikkletöltés nem védett"
    assert "DEFAULT_MAX_BYTES" in src, "nincs méretkorlát a cikkletöltésen"


def test_bongeszo_megnyitas_csak_webcimre():
    for rel in ("modules_src/szervezes/szervezes_mod/newswin.py",
                "modules_src/szervezes/szervezes_mod/podcastwin.py"):
        src = _src(rel)
        assert "urlpolicy.is_web_url" in src, f"{rel}: őrizetlen webbrowser.open"


# ---- CAL-P0-05: az automatikus naptár-akció engedélyezési listája ----------

from superdl.organizer import check_action_target      # noqa: E402


@pytest.mark.parametrize("t", [
    "C:/Windows/System32/cmd.exe", "x.bat", "x.cmd", "x.ps1", "x.vbs",
    "x.js", "x.scr", "x.msi", "x.hta", "x.reg", "x.lnk",
])
def test_futtathato_soha_nem_indul_automatikusan(t):
    ok, _, indok = check_action_target(t)
    assert ok is False and indok


@pytest.mark.parametrize("t", [
    "javascript:alert(1)", "file:///C:/x", "data:text/html,x", "vbscript:x",
    "custom://x", "",
])
def test_veszelyes_semak_blokkolva(t):
    assert check_action_target(t)[0] is False


@pytest.mark.parametrize("t", [
    "https://pelda.hu/talalkozo", "http://pelda.hu", "mailto:a@b.hu",
])
def test_webcim_es_levelcim_szabad(t):
    ok, tipus, _ = check_action_target(t)
    assert ok is True and tipus == "url"


def test_letezo_artalmatlan_fajl_szabad(tmp_path):
    p = tmp_path / "jegyzet.txt"
    p.write_text("szia", encoding="utf-8")
    ok, tipus, _ = check_action_target(str(p))
    assert ok is True and tipus == "fajl"


def test_nem_letezo_fajl_nem_indul():
    assert check_action_target("C:/nincs/ilyen/fajl.txt")[0] is False


def test_gui_hasznalja_az_engedelyezesi_listat():
    src = _src("superdl_gui.py")
    assert "check_action_target" in src, "a GUI őrizetlenül indít akciót"
    i = src.index("check_action_target")
    assert "os.startfile" in src[i:i + 900]
