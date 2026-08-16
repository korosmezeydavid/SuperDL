# -*- coding: utf-8 -*-
"""Super Mail: PISZKOZAT, küldés-megerősítés és ALÁÍRÁS.

Felhasználói kérés (2026-08-16):
  1. kilépéskor kérdezze meg, elmentse-e piszkozatként (a szolgáltató
     Piszkozatok mappájába, vagy ha az nem megy, helyben);
  2. a küldés-kérdésben legyen „ne mutassa többé" pipa;
  3. legyen szerkeszthető aláírás, de a levél alján MINDIG ott legyen egy
     „Super Mail-lel küldve." sor.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mail_core as MC          # noqa: E402


# ----------------------------------------------------------- aláírás

def test_a_zarosor_mindig_felkerul():
    ki = MC.torzs_zarosorral("Szia!")
    assert ki.rstrip().endswith(MC.FIX_ZAROSOR)
    assert ki.startswith("Szia!")


def test_a_zarosort_nem_duplazzuk():
    egy = MC.torzs_zarosorral("Szia!")
    ketto = MC.torzs_zarosorral(egy)
    assert ketto.count(MC.FIX_ZAROSOR) == 1


def test_a_kuldes_nem_teszi_be_masodszor_az_alairast():
    """REGRESSZIÓ: az első változatom küldéskor ÚJRA hozzáfűzte a beállított
    aláírást, pedig az már a szerkesztőben volt – kétszer szerepelt volna."""
    torzs = "Szia!\n\n-- \n" + MC.ALAP_ALAIRAS
    ki = MC.torzs_zarosorral(torzs)
    assert ki.count("super-dl.com") == 1


def test_ures_alairassal_is_megy_es_akkor_is_van_zarosor():
    ki = MC.torzs_alairassal("Szia!", "")
    assert MC.FIX_ZAROSOR in ki and "-- " not in ki


def test_az_alap_alairas_nem_ismetli_a_zarosort():
    """A zárósor („Super Mail-lel küldve.") a levél alján van, ezért az
    alapértelmezett aláírásban NEM szerepelhet még egyszer."""
    assert "küldve" not in MC.ALAP_ALAIRAS.lower()
    assert "super-dl.com" in MC.ALAP_ALAIRAS


def test_az_alairas_beallitasa_ervenyesul():
    assert MC.torzs_alairassal("Szia!", "Üdv: Dávid").count("Üdv: Dávid") == 1
    # ha a szövegben MÁR ott az aláírás, nem tesszük be újra
    torzs = "Szia!\n\n-- \nÜdv: Dávid"
    assert MC.torzs_alairassal(torzs, "Üdv: Dávid").count("Üdv: Dávid") == 1


# ------------------------------------------------------- beállítások

def test_az_uj_beallitasok_alapertekei():
    cfg = MC.altalanos_betolt()
    assert cfg["kuldes_kerdes"] is True, "alapból KÉRDEZZEN küldés előtt"
    assert cfg["alairas"] == MC.ALAP_ALAIRAS
    assert cfg["lista_szel"] in ("bling", "beszed")


# --------------------------------------------------------- piszkozat

class _HamisImap:
    """A szerver LIST-válaszát utánozza (RFC 6154 jelölésekkel)."""

    def __init__(self, sorok, append_ok=True):
        self.sorok = sorok
        self.append_ok = append_ok
        self.hivas = []

    def list(self):
        return "OK", [s.encode() if isinstance(s, str) else s
                      for s in self.sorok]

    def append(self, mappa, jelzok, ido, nyers):
        self.hivas.append((mappa, jelzok, len(nyers)))
        return ("OK" if self.append_ok else "NO"), [b""]


def _kliens(imap):
    k = MC.ImapKliens.__new__(MC.ImapKliens)
    k.M = imap
    k._mappa = None
    return k


def test_a_szerver_sajat_jelolese_szerint_talalja_meg_a_piszkozatokat():
    """Ne a nevet találgassuk: a Gmail „[Gmail]/Vázlatok", egy német szerver
    „Entwürfe" – de MINDEGYIK jelöli magát `\\Drafts`-szal."""
    imap = _HamisImap([
        r'(\HasNoChildren) "/" "INBOX"',
        r'(\HasNoChildren \Drafts) "/" "[Gmail]/V&AOE-zlatok"',
        r'(\HasNoChildren \Sent) "/" "[Gmail]/Elk&APw-ld&APY-tt"'])
    assert "zlatok" in _kliens(imap).piszkozat_mappa()


def test_jeloles_nelkul_a_szokasos_nevek_alapjan_talal():
    imap = _HamisImap([r'(\HasNoChildren) "/" "INBOX"',
                       r'(\HasNoChildren) "/" "Piszkozatok"'])
    assert _kliens(imap).piszkozat_mappa() == "Piszkozatok"


def test_ha_nincs_piszkozat_mappa_ures_a_valasz():
    imap = _HamisImap([r'(\HasNoChildren) "/" "INBOX"'])
    assert _kliens(imap).piszkozat_mappa() == ""


def test_a_piszkozat_draft_jelzessel_kerul_fel():
    imap = _HamisImap([r'(\HasNoChildren \Drafts) "/" "Drafts"'])
    msg = MC.level_epit("en@x.hu", "te@y.hu", "Tárgy", "Szöveg")
    assert _kliens(imap).piszkozat_ment(msg) == "Drafts"
    mappa, jelzok, meret = imap.hivas[0]
    assert jelzok == r"\Draft", "e nélkül nem piszkozatként jelenne meg"
    assert meret > 50


def test_sikertelen_feltoltes_ures_valasz_nem_kivetel():
    """Ilyenkor a hívó a HELYI mentésre vált – de csak akkor, ha ezt megtudja."""
    imap = _HamisImap([r'(\HasNoChildren \Drafts) "/" "Drafts"'], append_ok=False)
    msg = MC.level_epit("en@x.hu", "te@y.hu", "T", "Sz")
    assert _kliens(imap).piszkozat_ment(msg) == ""


def test_helyi_piszkozat_valodi_eml_fajlt_ir(tmp_path, monkeypatch):
    from mail_mod import mailwin as MW
    monkeypatch.setattr(MW.Path, "home", staticmethod(lambda: tmp_path))
    msg = MC.level_epit("en@x.hu", "te@y.hu", "Tárgy", "Szöveg")
    ut = MW._helyi_piszkozat(msg)
    adat = open(ut, "rb").read()
    assert ut.endswith(".eml") and b"Subject:" in adat and b"te@y.hu" in adat
