# -*- coding: utf-8 -*-
"""Super Mail – TÉRTIVEVÉNY (MDN).

„Tértivevény-kérés lehetősége az e-mail olvasottságáról.” A szabvány szerint ez
KÉRÉS: a címzett programja megkérdezi őt, és ő nemet is mondhat.
"""

import email
import sys
import time

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mdn as MDN                  # noqa: E402


def _level(azonosito="<eredeti@sajat.hu>", kerest=True):
    nyers = ("From: Én <en@sajat.hu>\r\nTo: Mari <mari@masik.hu>\r\n"
             "Subject: Szerződés\r\nMessage-ID: %s\r\n" % azonosito)
    if kerest:
        nyers += "Disposition-Notification-To: en@sajat.hu\r\n"
    return email.message_from_string(nyers + "\r\nSzia!\r\n")


# ---------------------------------------------------- kérés

def test_a_keres_bekerul_a_fejlecbe():
    from email.message import EmailMessage
    m = EmailMessage()
    m["To"] = "mari@masik.hu"
    MDN.keres_beallit(m, "en@sajat.hu")
    assert m["Disposition-Notification-To"] == "en@sajat.hu"
    # kétszer beállítva se duplázódjon
    MDN.keres_beallit(m, "en@sajat.hu")
    assert len(m.get_all("Disposition-Notification-To")) == 1


def test_felismerjuk_ha_tolunk_kernek():
    assert MDN.kertunk_e(_level()) == "en@sajat.hu"
    assert MDN.kertunk_e(_level(kerest=False)) == ""


# ---------------------------------------------------- MDN összeállítás

def test_az_mdn_level_szabalyos():
    valasz = MDN.mdn_level(_level(), "mari@masik.hu")
    assert valasz["To"] == "en@sajat.hu"
    assert "Szerződés" in valasz["Subject"]
    assert valasz["Auto-Submitted"] == "auto-replied", \
        "enélkül két automata egymásnak eshet (levél-lavina)"
    assert MDN.mdn_e(valasz) is True
    assert MDN.mdn_eredeti_azonosito(valasz) == "<eredeti@sajat.hu>"


def test_az_mdn_emberi_resze_is_erthető():
    valasz = MDN.mdn_level(_level(), "mari@masik.hu")
    szoveg = ""
    for r in valasz.walk():
        if r.get_content_type() == "text/plain":
            szoveg = r.get_payload(decode=True).decode("utf-8", "replace")
            break
    assert "megjelenítette" in szoveg
    assert "nem" in szoveg and "olvasták" in szoveg, \
        "ki kell mondani, hogy a megnyitás nem egyenlő az elolvasással"


def test_a_sima_level_nem_mdn():
    assert MDN.mdn_e(_level()) is False


# ---------------------------------------------------- nyilvántartás

def test_keres_rogzitese_es_visszaigazolas(tmp_path):
    m = str(tmp_path)
    MDN.kerest_rogzit("<eredeti@sajat.hu>", "mari@masik.hu", "Szerződés", m)
    assert "kérve" in MDN.allapot("<eredeti@sajat.hu>", m)

    valasz = MDN.mdn_level(_level(), "mari@masik.hu")
    azon = MDN.mdn_eredeti_azonosito(valasz)
    assert MDN.megjott(azon, time.time(), m) is True
    assert "Visszaigazolva" in MDN.allapot("<eredeti@sajat.hu>", m)


def test_idegen_visszaigazolast_nem_konyvelunk_el(tmp_path):
    """Csak arra a levélre fogadunk el visszaigazolást, amire mi kértünk."""
    assert MDN.megjott("<idegen@valahol.hu>", mappa=str(tmp_path)) is False


def test_osszesito_felolvashato(tmp_path):
    m = str(tmp_path)
    MDN.kerest_rogzit("<a@b>", "mari@masik.hu", "Szerződés", m)
    MDN.kerest_rogzit("<c@d>", "bela@masik.hu", "Ajánlat", m)
    MDN.megjott("<c@d>", time.time(), m)
    sorok = MDN.osszesito(m)
    assert len(sorok) == 2
    assert any("MEGNYITOTTA" in s for s in sorok)
    assert any("még nincs visszajelzés" in s for s in sorok)


def test_ures_es_serult_fajl(tmp_path):
    assert MDN.betolt(str(tmp_path)) == {}
    (tmp_path / MDN.FAJL).write_text("{nem json", encoding="utf-8")
    assert MDN.betolt(str(tmp_path)) == {}
    assert MDN.allapot("<akarmi>", str(tmp_path)) == ""


def test_a_figyelmeztetes_szovege_oszinte():
    assert "KÉRÉS" in MDN.FIGYELMEZTETES
    assert "nem következik" in MDN.FIGYELMEZTETES
