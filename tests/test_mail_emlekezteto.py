# -*- coding: utf-8 -*-
"""Super Mail – halasztás, „nem válaszoltak”, dátum a levélben."""

import sys
import time
from datetime import date, datetime

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import emlekezteto as EM            # noqa: E402


# ---------------------------------------------------- halasztás

def test_egy_ora_mulva():
    most = datetime(2026, 8, 19, 10, 0).timestamp()
    assert EM.halasztas_ideje(0, most) == most + 3600


def test_ma_este_hatkor_mar_elmult_ma_akkor_holnap():
    delelott = datetime(2026, 8, 19, 10, 0).timestamp()
    d = datetime.fromtimestamp(EM.halasztas_ideje(1, delelott))
    assert (d.day, d.hour) == (19, 18)

    keso = datetime(2026, 8, 19, 20, 0).timestamp()      # este 8: már elmúlt
    d2 = datetime.fromtimestamp(EM.halasztas_ideje(1, keso))
    assert (d2.day, d2.hour) == (20, 18), "a múltba nem halaszthatunk"


def test_holnap_reggel_es_hetfo_reggel():
    szerda = datetime(2026, 8, 19, 15, 0).timestamp()    # 2026-08-19 = szerda
    holnap = datetime.fromtimestamp(EM.halasztas_ideje(2, szerda))
    assert (holnap.day, holnap.hour) == (20, 8)
    hetfo = datetime.fromtimestamp(EM.halasztas_ideje(3, szerda))
    assert hetfo.weekday() == 0 and hetfo.hour == 8
    assert hetfo > datetime.fromtimestamp(szerda)


def test_ha_ma_hetfo_a_kovetkezo_hetfore_halaszt():
    hetfo = datetime(2026, 8, 17, 9, 0).timestamp()      # hétfő
    cel = datetime.fromtimestamp(EM.halasztas_ideje(3, hetfo))
    assert cel.day == 24, "ne ma reggelre tegye, az már elmúlt"


def test_halasztas_mentese_es_esedekesseg(tmp_path):
    m = str(tmp_path)
    most = time.time()
    EM.halaszt("<a@b>", "en@sajat.hu", "Számla", "bolt@x.hu", most - 1, m)
    tetelek = EM.esedekes(most, m)
    assert len(tetelek) == 1
    assert "Számla" in EM.tetel_szoveg(tetelek[0])
    EM.levesz(tetelek[0], m)
    assert EM.esedekes(most, m) == []


def test_ugyanarra_a_levelre_csak_egy_halasztas(tmp_path):
    m = str(tmp_path)
    EM.halaszt("<a@b>", "f", "t", "f", time.time() + 100, m)
    EM.halaszt("<a@b>", "f", "t", "f", time.time() + 200, m)
    assert len(EM.betolt(m)) == 1


# ---------------------------------------------------- nem válaszoltak

def test_valaszvaras_es_a_valasz_felismerese(tmp_path):
    m = str(tmp_path)
    EM.valaszt_var("<sajat@id>", "en@sajat.hu", "mari@masik.hu", "Kérdés",
                   5, m)
    # egy levél, ami erre válaszol (a szabvány szerinti hivatkozással)
    lezart = EM.valasz_erkezett(
        [{"valasz_erre": "<sajat@id>", "hivatkozasok": ""}], m)
    assert len(lezart) == 1
    assert EM.betolt(m) == [], "a megválaszolt tétel lezárul"


def test_mas_level_nem_zarja_le(tmp_path):
    m = str(tmp_path)
    EM.valaszt_var("<sajat@id>", "f", "c", "t", 5, m)
    assert EM.valasz_erkezett(
        [{"valasz_erre": "<masik@id>", "hivatkozasok": ""}], m) == []
    assert len(EM.betolt(m)) == 1


def test_valaszvaras_hatarideje(tmp_path):
    m = str(tmp_path)
    EM.valaszt_var("<a@b>", "f", "c", "Ajánlat", 5, m)
    t = EM.betolt(m)[0]
    assert 4.9 * 86400 < t["mikor"] - time.time() < 5.1 * 86400
    assert "Nem érkezett válasz" in EM.tetel_szoveg(t)


# ---------------------------------------------------- dátum a szövegben

MA = date(2026, 8, 19)          # szerda


def test_teljes_datum_orával():
    d = EM.datumok("Találkozzunk 2026-09-03 14:30-kor a hivatalban.", MA)
    assert d and d[0][0] == datetime(2026, 9, 3, 14, 30)


def test_magyar_datum_pontokkal():
    d = EM.datumok("Az időpont: 2026. 09. 03. 10 óra", MA)
    assert d and d[0][0].date() == date(2026, 9, 3) and d[0][0].hour == 10


def test_honap_nev_ev_nelkul_a_kovetkezo_ilyen_nap():
    d = EM.datumok("A szülinapja július 11-én van.", MA)
    assert d and d[0][0].date() == date(2027, 7, 11), \
        "július 11. idén már elmúlt, tehát jövőre"
    d2 = EM.datumok("Szeptember 3-án jövök.", MA)
    assert d2[0][0].date() == date(2026, 9, 3)


def test_hetkoznap_a_kovetkezo_ilyen_nap():
    d = EM.datumok("Találkozzunk kedden 14 órakor.", MA)
    assert d and d[0][0].weekday() == 1 and d[0][0].hour == 14
    assert d[0][0].date() == date(2026, 8, 25)


def test_holnap_es_holnaputan():
    assert EM.datumok("Holnap 9:00", MA)[0][0].date() == date(2026, 8, 20)
    assert EM.datumok("Holnapután megyek", MA)[0][0].date() == date(2026, 8, 21)


def test_ora_nelkul_alapertelmezett_kilenc():
    d = EM.datumok("2026. 09. 03.", MA)
    assert d[0][0].hour == 9


def test_datum_nelkuli_szovegben_nincs_talalat():
    assert EM.datumok("Szia, minden rendben, köszönöm a segítséget!", MA) == []


def test_ket_datum_idorendben_es_ismetles_nelkul():
    d = EM.datumok("Kedden 10-kor, vagy 2026-09-03 14:00-kor. Kedden 10-kor!",
                   MA)
    assert len(d) == 2
    assert d[0][0] < d[1][0]


def test_hibas_datum_nem_szall_el():
    assert EM.datumok("2026-13-45 valami", MA) == []
    assert EM.datumok("február 30-án", MA) == []
