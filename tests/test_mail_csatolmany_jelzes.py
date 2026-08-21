# -*- coding: utf-8 -*-
"""Super Mail – CSATOLMÁNY-JELZÉS a levéllistában.

Hibajelentés (István, 2026-08-20): „Ha csatolvány van a levélhez fűzve, akár
külső, akár belső levelezőből érkezik, nincs róla jelzés a levél érkezésekor.
Sajnos, így elsikkad a melléklet.”

GYÖKÉROK: a listához CSAK a fejléceket töltjük le (gyors, kevés forgalom), a
csatolmány viszont a levél TESTÉBEN van – így a `level_fejlec_info` mindig
False-t adott a `csatolmany` mezőre, és a listasor „csatolmány” jelzése soha
nem jelent meg. A megoldás: a lekérésbe bekerül a levél SZERKEZETE
(BODYSTRUCTURE), amiből a melléklet a levél letöltése nélkül is látszik.

Az alábbi minták VALÓS szerverek (Gmail, Outlook, Dovecot) válaszainak
formátumát követik.
"""

import email
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mail_core as MC          # noqa: E402


CSATOLMANNYAL = (
    b'1 (UID 42 RFC822.SIZE 51234 FLAGS (\\Seen) BODYSTRUCTURE '
    b'(("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 120 5 NIL NIL NIL)'
    b'("APPLICATION" "PDF" ("NAME" "szerzodes.pdf") NIL NIL "BASE64" 40960 '
    b'NIL ("ATTACHMENT" ("FILENAME" "szerzodes.pdf")) NIL) "MIXED") '
    b'BODY[HEADER.FIELDS (FROM SUBJECT)] {40}')

CSATOLMANY_NELKUL = (
    b'2 (UID 43 RFC822.SIZE 3120 FLAGS () BODYSTRUCTURE '
    b'(("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 100 4 NIL NIL NIL)'
    b'("TEXT" "HTML" ("CHARSET" "utf-8") NIL NIL "7BIT" 300 8 NIL NIL NIL) '
    b'"ALTERNATIVE") BODY[HEADER.FIELDS (FROM SUBJECT)] {40}')

BEAGYAZOTT_KEPPEL = (
    b'3 (UID 44 BODYSTRUCTURE (("TEXT" "HTML" ("CHARSET" "utf-8") NIL NIL '
    b'"7BIT" 900 20 NIL NIL NIL)("IMAGE" "PNG" ("NAME" "logo.png") '
    b'"<kep1@superdl>" NIL "BASE64" 5000 NIL ("INLINE" ("FILENAME" '
    b'"logo.png")) NIL) "RELATED") BODY[HEADER.FIELDS (FROM)] {20}')

ALAIRT_LEVEL = (
    b'4 (UID 45 BODYSTRUCTURE (("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL '
    b'"7BIT" 100 4 NIL NIL NIL)("APPLICATION" "PKCS7-SIGNATURE" ("NAME" '
    b'"smime.p7s") NIL NIL "BASE64" 3000 NIL NIL NIL) "SIGNED") '
    b'BODY[HEADER.FIELDS (FROM)] {20}')

WORD_NEV_NELKULI_ELHELYEZESSEL = (
    b'5 (UID 46 BODYSTRUCTURE (("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL '
    b'"7BIT" 50 2 NIL NIL NIL)("APPLICATION" "VND.OPENXMLFORMATS-'
    b'OFFICEDOCUMENT.WORDPROCESSINGML.DOCUMENT" ("NAME" "beadvany.docx") NIL '
    b'NIL "BASE64" 20000 NIL NIL NIL) "MIXED") BODY[HEADER.FIELDS (FROM)] {20}')


def test_csatolmanyos_levelet_felismerjuk():
    assert MC.csatolmany_a_szerkezetbol(CSATOLMANNYAL) is True


def test_csatolmany_nelkuli_levelnel_nincs_jelzes():
    assert MC.csatolmany_a_szerkezetbol(CSATOLMANY_NELKUL) is False


def test_a_levelbe_agyazott_kep_nem_csatolmany():
    """A hírlevelek testébe ágyazott képek (cid:) nem mellékletek. Ha ezeket is
    jeleznénk, a jelzés elértéktelenedne – és pont az igazi melléklet sikkadna
    el, amit István hiányolt."""
    assert MC.csatolmany_a_szerkezetbol(BEAGYAZOTT_KEPPEL) is False


def test_a_digitalis_alairas_nem_csatolmany():
    assert MC.csatolmany_a_szerkezetbol(ALAIRT_LEVEL) is False


def test_elhelyezes_jeloles_nelkuli_word_dokumentum_is_csatolmany():
    """Több szerver nem küld „attachment” jelölést, csak fájlnevet."""
    assert MC.csatolmany_a_szerkezetbol(WORD_NEV_NELKULI_ELHELYEZESSEL) is True


def test_hianyzo_vagy_ertelmetlen_bemenet():
    assert MC.csatolmany_a_szerkezetbol(b"") is False
    assert MC.csatolmany_a_szerkezetbol(None) is False
    assert MC.csatolmany_a_szerkezetbol(b"1 (UID 9 FLAGS ())") is False


def test_szoveges_bemenettel_is_mukodik():
    assert MC.csatolmany_a_szerkezetbol(
        CSATOLMANNYAL.decode("utf-8")) is True


def test_a_lekeres_kéri_a_szerkezetet():
    """Ha ez kimarad a lekérésből, a jelzés némán eltűnik – pontosan ez volt a
    hiba."""
    assert "BODYSTRUCTURE" in MC.ImapKliens._FEJLEC_FETCH


def test_a_teljes_level_utjan_valtozatlanul_mukodik():
    """A megnyitott levélnél továbbra is a tényleges részekből dolgozunk."""
    from email.message import EmailMessage
    m = EmailMessage()
    m["From"] = "mari@x.hu"
    m["Subject"] = "Szerződés"
    m.set_content("szia")
    m.add_attachment(b"PDF", maintype="application", subtype="pdf",
                     filename="szerzodes.pdf")
    assert MC.level_fejlec_info(m)["csatolmany"] is True
    sima = email.message_from_string("From: a@b.hu\r\nSubject: x\r\n\r\nszia")
    assert MC.level_fejlec_info(sima)["csatolmany"] is False


# ---------------------------------------------------- érkezéskori bemondás

sys.path.insert(0, "modules_src/mail")
from mail_mod import mailwin as MW              # noqa: E402


@pytest.mark.parametrize("db,resz", [
    (0, ""), (1, "Csatolmány van benne."), (3, "3 levélben csatolmány is van.")])
def test_a_jelzes_szovege(db, resz):
    """István kérése: az ÉRKEZÉSKOR derüljön ki, hogy melléklet is jött."""
    assert MW.MailFrame._csat_szoveg(db) == resz


def test_nulla_es_hibas_ertekre_nincs_mondat():
    assert MW.MailFrame._csat_szoveg(None) == ""
    assert MW.MailFrame._csat_szoveg(-2) == ""


def test_a_listasor_kiirja_a_csatolmanyt():
    """A sor végén ott a szó – a képernyőolvasó így felolvassa."""
    class _Keret:
        _osszesitett = False
        _sor_szoveg = MW.MailFrame._sor_szoveg
    info = {"felado": "Mari <mari@x.hu>", "targy": "Szerződés",
            "datum": "ma 10:00", "olvasott": True, "csatolmany": True}
    sor = _Keret()._sor_szoveg(info)
    assert sor.endswith("csatolmány")
    info["csatolmany"] = False
    assert not _Keret()._sor_szoveg(info).endswith("csatolmány")
