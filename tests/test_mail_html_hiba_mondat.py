# -*- coding: utf-8 -*-
"""A Super Mail HTML nézete ne állítsa hamisan, hogy a GÉPEN nincs WebView2.

Schibik Miklós, 2026-09-28: a 4.6.25-ben a `wx.html2` kimaradt a csomagból,
a levelező pedig azt mondta, „az Edge WebView2 ezen a gépen nem érhető el" –
pedig telepítve volt, és a telepítője ezt meg is mondta. A felhasználó a
saját gépét kezdte javítgatni. A három okhoz három különböző mondat tartozik.
"""

import os
import sys

import pytest

GYOKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MAIL = os.path.join(GYOKER, "modules_src", "mail")
if not os.path.isdir(os.path.join(MAIL, "mail_mod")):
    pytest.skip("a Super Mail forrása itt nincs meg", allow_module_level=True)
sys.path.insert(0, MAIL)
pytest.importorskip("wx")

from mail_mod import mailwin  # noqa: E402


def test_hianyzo_csomagresz_nem_a_gep_hibaja():
    m = mailwin._html_hiba_mondat("csomag")
    assert "nem a gépeden" in m
    assert "frissítsd a SuperDL-t" in m
    assert "ezen a gépen nem" not in m


def test_hianyzo_webview2_a_gepen():
    assert "ezen a gépen nem érhető el" in mailwin._html_hiba_mondat("webview2")


def test_egyeb_hiba_a_naplora_mutat():
    m = mailwin._html_hiba_mondat("inditas")
    assert "Hibajelentés vágólapra" in m
    assert "WebView2" not in m
    assert mailwin._html_hiba_mondat("") == m
