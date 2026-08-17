# -*- coding: utf-8 -*-
"""Super Mail: IDEGEN NYELVŰ LEVÉL FORDÍTÁSA és a LEVELEZŐLISTÁS VÁLASZ.

Felhasználói kérés (2026-08-16):
  1. „ha egy levelet lengyelül kapok meg, azt egy gombbal tudjam gyorsan
     lefordíttatni – létezik olyan megoldás, ami nem igényel API-kulcsot?”
  2. „ha levelezőlistára írok… megoldható, hogy automatikusan azt töltse ki
     címzettnek? Karcsi küldött nekem levelet a listáról, és nem neki direktben
     akarok válaszolni, hanem a levelezőlistára.”

A tesztek egyetlen valódi hálózati kérést sem küldenek.
"""

import email
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import forditas as F              # noqa: E402
from mail_mod import mail_core as MC            # noqa: E402


def _lev(**fejlecek):
    m = email.message.EmailMessage()
    for k, v in fejlecek.items():
        m[k.replace("_", "-")] = v
    return m


# ------------------------------------------------------- levelezőlista

def test_a_lista_cimet_a_szabvanyos_fejlecbol_vesszuk():
    """A listamotorok a `List-Post` fejlécben megadják a lista címét (RFC 2369)
    – nem kell találgatni, és nem a feladónak megy a válasz."""
    m = _lev(From="Karcsi <karcsi@pelda.hu>",
             List_Post="<mailto:jaws-lista@lev-lista.hu>",
             List_Id="Jaws-lista <jaws-lista.lev-lista.hu>")
    assert MC.lista_cim(m) == "jaws-lista@lev-lista.hu"
    assert MC.lista_neve(m) == "Jaws-lista"
    assert MC.listas_level(m) is True


def test_reply_to_a_tartalek_ha_nincs_list_post():
    m = _lev(From="karcsi@pelda.hu", List_Id="<valami.lista.hu>",
             Reply_To="lista@lista.hu")
    assert MC.lista_cim(m) == "lista@lista.hu"


def test_a_sima_level_nem_listas():
    m = _lev(From="anna@pelda.hu", Subject="Szia")
    assert MC.lista_cim(m) == "" and MC.listas_level(m) is False


def test_a_tiltott_listas_valaszt_tiszteletben_tartjuk():
    """`List-Post: NO` = a lista nem fogad válaszokat (csak hírlevél). Ilyenkor
    NEM ajánlunk listás választ."""
    m = _lev(From="hirlevel@pelda.hu", List_Post="NO", List_Id="<hir.pelda.hu>")
    assert MC.lista_cim(m) == ""


def test_a_reply_to_nem_lesz_lista_ha_a_feladoval_egyezik():
    m = _lev(From="anna@pelda.hu", List_Id="<x.lista.hu>",
             Reply_To="anna@pelda.hu")
    assert MC.lista_cim(m) == ""


def test_a_lista_neve_akkor_is_megvan_ha_nincs_szep_cimke():
    m = _lev(From="a@b.hu", List_Post="<mailto:hobbi@lev-lista.hu>",
             List_Id="<hobbi.lev-lista.hu>")
    assert MC.lista_neve(m) == "hobbi"


# ------------------------------------------------------------ fordítás

@pytest.mark.parametrize("nyelv,szoveg", [
    ("pl", "Dzień dobry! Przesyłam raport. Proszę o potwierdzenie. Pozdrawiam"),
    ("en", "Hello, could you please confirm the meeting tomorrow? Thanks"),
    ("de", "Sehr geehrte Damen und Herren, bitte senden Sie mir die Rechnung"),
    ("hu", "Szia! Kérlek, erősítsd meg a holnapi találkozót. Köszönöm"),
    ("ro", "Bună ziua, vă mulțumesc pentru mesaj. Cu salutări"),
])
def test_nyelvfelismeres(nyelv, szoveg):
    kod, biztos = F.nyelv_felismer(szoveg)
    assert kod == nyelv and biztos is True


def test_rovid_vagy_ertelmezhetetlen_szovegnel_bevallja_hogy_nem_tudja():
    """Inkább kérdezzen rá a felhasználónál, mint hogy rosszul tippeljen."""
    assert F.nyelv_felismer("Hi") == ("", False)
    assert F.nyelv_felismer("") == ("", False)
    assert F.nyelv_felismer("12345 67890 !!!") == ("", False)


def test_a_darabolas_a_korlat_ala_visz_es_nem_veszit_szoveget():
    """Az ingyenes szolgáltatás 500 karakteres kérést enged – hosszú levélnél
    darabolni kell, de úgy, hogy semmi ne vesszen el."""
    hosszu = ("Ez egy hosszú mondat a levélben. " * 40).strip()
    darabok = F.darabol(hosszu)
    assert len(darabok) > 1
    assert all(len(d.encode("utf-8")) <= 480 for d in darabok)
    assert "".join(darabok).replace(" ", "") == hosszu.replace(" ", "")


def test_a_darabolas_mondathataron_vag():
    d = F.darabol("Első mondat. Második mondat. Harmadik mondat.", meret=30)
    assert all(x.strip().endswith((".", "!", "?")) or len(x) < 30 for x in d)


def test_nagyon_hosszu_mondat_sem_akad_be():
    egy = "szó " * 400
    darabok = F.darabol(egy)
    assert darabok and all(len(d.encode("utf-8")) <= 480 for d in darabok)


def test_ures_szoveg_nem_dob_vegtelen_ciklust():
    assert F.darabol("") == [] and F.darabol(None) == []


def test_a_magyar_levelet_nem_forditjuk_magyarra():
    with pytest.raises(ValueError):
        F.fordit("Szia! Kérlek, erősítsd meg a találkozót. Köszönöm", "hu")


def test_ismeretlen_nyelvnel_erthetoen_szol():
    with pytest.raises(ValueError):
        F.fordit("xy", "hu")


def test_a_napi_korlat_ertheto_magyar_mondatot_ad(monkeypatch):
    """Nyers hibakód helyett elmondjuk, mi történt és mit lehet tenni."""
    monkeypatch.setattr(F, "_lekerdez", lambda url, timeout=30: {
        "responseStatus": 403,
        "responseDetails": "QUERY LENGTH LIMIT EXCEEDED / DAILY LIMIT"})
    with pytest.raises(RuntimeError) as hiba:
        F.mymemory_fordit("Hello world", "en", "hu")
    assert "kereté" in str(hiba.value).lower() or "keret" in str(hiba.value)
    assert "AI" in str(hiba.value), "adjunk kiutat is, ne csak hibát"


def test_a_forditas_osszefuzi_a_darabokat(monkeypatch):
    valaszok = iter([{"responseStatus": 200,
                      "responseData": {"translatedText": "Első."}},
                     {"responseStatus": 200,
                      "responseData": {"translatedText": "Második."}}])
    monkeypatch.setattr(F, "_lekerdez", lambda url, timeout=30: next(valaszok))
    monkeypatch.setattr(F, "darabol", lambda sz, meret=480: ["a", "b"])
    assert F.mymemory_fordit("akármi", "en", "hu") == "Első.\nMásodik."


def test_a_megjelenites_megtartja_az_eredetit():
    """A fordítás a szöveg FÖLÉ kerül, de az eredeti is ott marad – nevek,
    számok, linkek miatt azt is látni kell."""
    ki = F.megjelenites("Dzień dobry!", {"szoveg": "Jó napot!", "motor": "mymemory",
                                         "honnan": "pl", "hova": "hu"})
    assert ki.index("Jó napot!") < ki.index("Dzień dobry!")
    assert "lengyel" in ki and "magyar" in ki
    assert "EREDETI" in ki


def test_a_megjelenites_kimondja_melyik_motor_forditott():
    ai = F.megjelenites("x", {"szoveg": "y", "motor": "ai", "honnan": "en",
                              "hova": "hu"})
    ingyenes = F.megjelenites("x", {"szoveg": "y", "motor": "mymemory",
                                    "honnan": "en", "hova": "hu"})
    assert "AI" in ai and "saját kulcsod" in ai
    assert "ingyenes" in ingyenes


def test_a_motorok_es_nyelvek_listaja_ep():
    assert [k for k, _n in F.MOTOROK] == ["mymemory", "ai"]
    kodok = [k for k, _n in F.NYELVEK]
    assert "hu" in kodok and "pl" in kodok and len(kodok) == len(set(kodok))
