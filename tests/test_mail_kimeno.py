# -*- coding: utf-8 -*-
"""Super Mail – KIMENŐ: küldés visszavonása, időzített és évente ismétlődő levél.

„Elküldött levelet visszahívni nem lehet” – ezért a levél NÁLUNK vár egy
darabig, és addig visszavonható. Ugyanez a várakoztatás adja az időzített
küldést is.
"""

import sys
import time
from datetime import datetime
from email.message import EmailMessage

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import kimeno as KM              # noqa: E402


def _msg(targy="Teszt", torzs="szia"):
    m = EmailMessage()
    m["From"] = "en@sajat.hu"
    m["To"] = "mari@sajat.hu"
    m["Subject"] = targy
    m.set_content(torzs)
    return m


def test_a_level_lemezre_kerul_es_visszaolvashato(tmp_path):
    """Áramszünet ne nyeljen el egy várakozó levelet."""
    azon = KM.betesz("en@sajat.hu", _msg("Születésnap", "Boldog szülinapot!"),
                     time.time() + 60, cimzett="mari@sajat.hu",
                     targy="Születésnap", mappa=str(tmp_path))
    vissza = KM.uzenet(azon, str(tmp_path))
    assert vissza["Subject"] == "Születésnap"
    assert "Boldog szülinapot" in vissza.get_content()


def test_esedekes_es_varakozo_elvalik(tmp_path):
    most = time.time()
    kesz = KM.betesz("a@b.hu", _msg(), most - 5, mappa=str(tmp_path))
    var = KM.betesz("a@b.hu", _msg(), most + 600, mappa=str(tmp_path))
    assert [s["id"] for s in KM.esedekes(most, str(tmp_path))] == [kesz]
    assert [s["id"] for s in KM.varakozo(most, str(tmp_path))] == [var]


def test_a_visszavonas_torli_a_tetelt_es_a_fajlt(tmp_path):
    azon = KM.betesz("a@b.hu", _msg(), time.time() + 30, mappa=str(tmp_path))
    KM.torol(azon, str(tmp_path))
    assert KM.tetelek(str(tmp_path)) == []
    with pytest.raises(OSError):
        KM.uzenet(azon, str(tmp_path))


def test_hatra_van_es_felolvashato_szoveg(tmp_path):
    most = time.time()
    azon = KM.betesz("a@b.hu", _msg(), most + 12, cimzett="mari@sajat.hu",
                     targy="Szia", mappa=str(tmp_path))
    sor = KM.tetelek(str(tmp_path))[0]
    assert sor["id"] == azon
    assert 10 <= KM.hatra_van(sor, most) <= 12
    mondat = KM.tetel_szoveg(sor, most)
    assert "mari@sajat.hu" in mondat and "Szia" in mondat
    assert "másodperc múlva" in mondat


@pytest.mark.parametrize("mp,vart", [
    (0, "most"), (12, "12 másodperc múlva"), (180, "3 perc múlva"),
    (7200, "2 óra múlva"), (3 * 86400, "3 nap múlva")])
def test_idoszoveg_emberi(mp, vart):
    assert KM.ido_szoveg(mp) == vart


# ---------------------------------------------- évente ismétlődő

def test_kovetkezo_ev_ugyanaz_a_nap():
    t = datetime(2026, 7, 11, 8, 0).timestamp()
    kov = datetime.fromtimestamp(KM.kovetkezo_ev(t))
    assert (kov.year, kov.month, kov.day, kov.hour) == (2027, 7, 11, 8)


def test_februar_29_nem_marad_el_negy_evig():
    t = datetime(2028, 2, 29, 9, 0).timestamp()
    kov = datetime.fromtimestamp(KM.kovetkezo_ev(t))
    assert (kov.year, kov.month, kov.day) == (2029, 2, 28)


def test_az_evente_ismetlodo_levelnel_a_kuldes_elotti_napon_kerdezunk(tmp_path):
    """Egy év alatt sok minden történhet – ne menjen el gépiesen egy köszöntő."""
    most = time.time()
    azon = KM.betesz("a@b.hu", _msg(), most + 3600, KM.ISM_EVENTE,
                     mappa=str(tmp_path))
    sor = KM.tetelek(str(tmp_path))[0]
    assert KM.kerdezni_kell(sor, most) is True

    # egy évben csak EGYSZER kérdezünk
    KM.megkerdezve(azon, most, str(tmp_path))
    sor = KM.tetelek(str(tmp_path))[0]
    assert KM.kerdezni_kell(sor, most) is False


def test_tavoli_es_nem_ismetlodo_levelnel_nem_kerdezunk(tmp_path):
    most = time.time()
    KM.betesz("a@b.hu", _msg(), most + 10 * 86400, KM.ISM_EVENTE,
              mappa=str(tmp_path))                       # még messze van
    KM.betesz("a@b.hu", _msg(), most + 60, KM.ISM_NINCS,
              mappa=str(tmp_path))                       # nem ismétlődik
    assert not [s for s in KM.tetelek(str(tmp_path))
                if KM.kerdezni_kell(s, most)]


def test_serult_adatfajl_nem_szall_el(tmp_path):
    (tmp_path / KM.FAJL).write_text("{nem json", encoding="utf-8")
    assert KM.tetelek(str(tmp_path)) == []
