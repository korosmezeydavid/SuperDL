# -*- coding: utf-8 -*-
"""Super Mail – POP3: miért csak egy mappa van, és mely mezők kellenek.

DÁVID JELEZTE (2026-08-30): „a pop3 fiókoknál csak a bejövő leveleket listázza,
a többit nem, a többi mappát. Több szolgáltatónál is teszteltem. Továbbá ha
bejelölöd, hogy pop3, akkor az imap adat bekérések tűnjenek el.”

Az első fele NEM a mi hibánk: a POP3 protokoll nem ismer mappákat, egyetlen
postaláda van benne – az Elküldött/Piszkozatok/Kuka IMAP-fogalmak. A hiba az
volt, hogy a program ezt nem MONDTA, csak megjelent egyetlen sor; ezért ment el
a felhasználó több szolgáltatót végigpróbálni. A második fele valódi hiányosság.
"""
import importlib

MC = importlib.import_module("modules_src.mail.mail_mod.mail_core")


# --- 1. a magyarázat --------------------------------------------------

def test_kimondja_hogy_a_pop3_nem_ismer_mappakat():
    sz = MC.pop3_mappa_magyarazat({"email": "a@freemail.hu"})
    assert "POP3" in sz
    assert "nem ismeri a mappákat" in sz
    assert "nem hiba" in sz, "a felhasználó ne magát vagy a szolgáltatót hibáztassa"


def test_ha_tudjuk_az_imap_szervert_megmondjuk():
    sz = MC.pop3_mappa_magyarazat(
        {"email": "a@gmail.com", "imap_host": "imap.gmail.com"})
    assert "imap.gmail.com" in sz
    assert "IMAP" in sz


def test_imap_szerver_nelkul_is_ad_utat():
    sz = MC.pop3_mappa_magyarazat({"email": "a@sajatceg.hu"})
    assert "IMAP" in sz
    assert "None" not in sz and "imap_host" not in sz


def test_ures_fiok_sem_szall_el():
    assert MC.pop3_mappa_magyarazat({})
    assert MC.pop3_mappa_magyarazat(None)


def test_a_mappa_neve_megmondja_hogy_ez_az_egy_van():
    assert "POP3" in MC.POP3_MAPPA_NEV
    assert "Beérkezett" in MC.POP3_MAPPA_NEV


# --- 2. a protokoll-függő mezők ---------------------------------------

def _mezok(pop):
    """A FiokDialog wx-mentes döntése arról, mely mezők kellenek."""
    W = importlib.import_module("modules_src.mail.mail_mod.mailwin")
    return W.FiokDialog.mezok_protokollhoz(pop)


def test_pop3_nal_nem_kell_imap_mezo():
    m = _mezok(pop=True)
    assert m["pop_host"] and m["pop_port"]
    assert not m["imap_host"] and not m["imap_port"]


def test_imapnal_nem_kell_pop3_mezo():
    m = _mezok(pop=False)
    assert m["imap_host"] and m["imap_port"]
    assert not m["pop_host"] and not m["pop_port"]


def test_az_smtp_mindig_kell():
    """A küldés MINDKÉT protokollnál SMTP-vel megy – ezt sosem rejtjük el."""
    for pop in (True, False):
        m = _mezok(pop)
        assert m["smtp_host"] and m["smtp_port"]
