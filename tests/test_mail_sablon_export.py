# -*- coding: utf-8 -*-
"""Super Mail – sablonok, okos mappák és postafiók-mentés (mbox)."""

import email
import mailbox
import sys
import time
from email.message import EmailMessage

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import export as EXP                # noqa: E402
from mail_mod import sablonok as SAB              # noqa: E402
from mail_mod import szabalyok as SZ              # noqa: E402


# ---------------------------------------------------- sablonok

def test_kitoltendo_helyek_felismerese():
    sz = "Kedves {nev}!\n\nA {datum} napon kelt levelére válaszolva {targy}."
    assert SAB.helyettesitok(sz) == ["nev", "targy"], \
        "a beépítettek (datum) nem kérdés, azokat tudjuk"


def test_beepitett_helyettesitok_kitoltese():
    most = time.mktime((2026, 7, 11, 9, 30, 0, 0, 0, -1))
    ki = SAB.kitolt("Ma {datum} van, {ido}. Én: {sajat_cim}", {},
                    "en@sajat.hu", most=most)
    assert "2026. 07. 11." in ki and "09:30" in ki and "en@sajat.hu" in ki


def test_sajat_ertek_kitoltese():
    ki = SAB.kitolt("Kedves {nev}!", {"nev": "Mari"})
    assert ki == "Kedves Mari!"


def test_ismeretlen_helyet_meghagyjuk():
    """Ha valamit elfelejtettünk megadni, LÁTSZÓDJON – a néma üresség rosszabb."""
    assert SAB.kitolt("Kedves {nev}!", {}) == "Kedves {nev}!"


def test_sablon_mentes_visszatoltes(tmp_path):
    s = SAB.Sablon(nev="Köszönet", targy="Köszönöm", torzs="Kedves {nev}!")
    SAB.sablonok_ment([s], str(tmp_path))
    vissza = SAB.sablonok_betolt(str(tmp_path))
    assert len(vissza) == 1 and vissza[0].nev == "Köszönet"
    assert vissza[0].id == s.id


def test_serult_sablonfajl(tmp_path):
    (tmp_path / SAB.SABLON_FAJL).write_text("{nem json", encoding="utf-8")
    assert SAB.sablonok_betolt(str(tmp_path)) == []


# ---------------------------------------------------- okos mappák

def _level(**m):
    alap = {"felado": "a@b.hu", "targy": "x", "cimzett": "", "masolat": "",
            "torzs": "", "lista_id": "", "marketing": False,
            "csatolmany": False, "meret": 0, "fejlecek": {}}
    alap.update(m)
    return alap


def test_okos_mappa_szures():
    n = SAB.Nezet(nev="Csatolmányos",
                  feltetelek=[SZ.Feltetel(SZ.MEZO_CSATOLMANY, SZ.VISZ_IGAZ)])
    levelek = [_level(csatolmany=True), _level(), _level(csatolmany=True)]
    assert len(SAB.szur(levelek, n)) == 2


def test_ures_nezet_mindent_visszaad():
    levelek = [_level(), _level()]
    assert len(SAB.szur(levelek, SAB.Nezet(nev="Minden"))) == 2


def test_alap_nezetek_ertelmesek():
    nevek = [n.nev for n in SAB.alap_nezetek()]
    assert "Hírlevelek és reklámok" in nevek and "Számlák" in nevek
    szamla = [n for n in SAB.alap_nezetek() if n.nev == "Számlák"][0]
    assert SAB.szur([_level(targy="Havi számla")], szamla)
    assert not SAB.szur([_level(targy="Szia")], szamla)


def test_nezetek_mentese_es_visszatoltese(tmp_path):
    n = SAB.Nezet(nev="Sajátom",
                  feltetelek=[SZ.Feltetel(SZ.MEZO_FELADO,
                                          SZ.VISZ_TARTALMAZZA, "bolt.hu")])
    SAB.nezetek_ment([n], str(tmp_path))
    vissza = SAB.nezetek_betolt(str(tmp_path))
    assert len(vissza) == 1 and vissza[0].nev == "Sajátom"
    assert vissza[0].feltetelek[0].ertek == "bolt.hu"
    assert SAB.szur([_level(felado="x@bolt.hu")], vissza[0])


def test_hianyzo_nezetfajl_eseten_az_alapok_jonnek(tmp_path):
    assert len(SAB.nezetek_betolt(str(tmp_path))) == len(SAB.alap_nezetek())


# ---------------------------------------------------- mbox export

def _msg(targy="Teszt", torzs="szia"):
    m = EmailMessage()
    m["From"] = "Mari <mari@masik.hu>"
    m["To"] = "en@sajat.hu"
    m["Subject"] = targy
    m["Date"] = "Tue, 11 Aug 2026 09:30:00 +0200"
    m.set_content(torzs)
    return m


def test_az_mbox_fajlt_mas_program_is_beolvassa(tmp_path):
    """A lényeg: NE a mi saját formátumunk legyen – a felhasználó adata az övé."""
    ut = str(tmp_path / "mentes.mbox")
    with EXP.MboxIro(ut) as iro:
        iro.ir(_msg("Első", "egy"))
        iro.ir(_msg("Második", "kettő"))
        assert iro.darab == 2
    doboz = mailbox.mbox(ut)
    assert len(doboz) == 2
    # a tárgy szabvány szerint kódolva van a fájlban (RFC 2047) – dekódolva
    # kell egyeznie, ahogy bármelyik levelezőprogram is olvassa
    from email.header import decode_header, make_header
    assert str(make_header(decode_header(doboz[0]["Subject"]))) == "Első"
    assert "kettő" in doboz[1].get_payload(decode=True).decode("utf-8")


def test_a_from_szoval_kezdodo_sor_nem_vagja_el_a_levelet(tmp_path):
    """Klasszikus mbox-csapda: egy „From ” kezdetű sor a szövegben."""
    ut = str(tmp_path / "m.mbox")
    with EXP.MboxIro(ut) as iro:
        iro.ir(_msg("Idézet", "From Monday to Friday dolgozom.\nÜdv"))
        iro.ir(_msg("Másik", "rendben"))
    doboz = mailbox.mbox(ut)
    assert len(doboz) == 2, "a From-sor nem hasíthatja ketté a levelet"
    torzs = doboz[0].get_payload(decode=True).decode("utf-8")
    assert "From Monday" in torzs.replace(">From Monday", "From Monday")


def test_fajlnev_biztonsagos():
    nev = EXP.fajlnev("en@sajat.hu", "[Gmail]/Összes levél")
    for rossz in '<>:"/\\|?*':
        assert rossz not in nev
    assert nev.endswith(".mbox") and "en@sajat.hu" in nev


@pytest.mark.parametrize("bajt,resz", [
    (512, "512 bájt"), (2048, "kilobájt"), (5 * 1024 ** 2, "megabájt"),
    (3 * 1024 ** 3, "gigabájt")])
def test_meret_szoveg(bajt, resz):
    assert resz in EXP.meret_szoveg(bajt)
