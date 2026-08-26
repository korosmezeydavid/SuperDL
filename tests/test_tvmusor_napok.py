# -*- coding: utf-8 -*-
"""TV műsor – NAPRA BONTÁS.

Laci kérdése (2026-08-24): „A műsorújság forrása hány napra előre tudná
megjeleníteni egy csatorna műsorát?… Lehetne napot állítani a csatornalistában,
ha nem az aktuálisra kíváncsi az ember.”

Méréssel: a magyar forrás (epgshare01 HU1) 166 csatornára 20 922 műsort ad, és
az adat MA + 3–4 naptári napra szól – csatornánként eltérően. Ezért a
nap-választót csatornánként kell feltölteni.
"""

import datetime as dt
import sys

import pytest

sys.path.insert(0, "modules_src/tvmusor")
from tvmusor_mod import epgmotor as E          # noqa: E402


def _musor(kezd, veg, cim, cid="c1"):
    return E.Musor(kezd=kezd, veg=veg, cim=cim, leiras="", csatorna=cid)


@pytest.fixture
def tv():
    ma = dt.date.today()
    t = E.TvMusor()
    t.csatornak = {"c1": "Egyes", "c2": "Kettes"}

    def d(nap, ora, perc=0):
        return dt.datetime.combine(ma + dt.timedelta(days=nap),
                                   dt.time(ora, perc))
    t.musorok = {
        "c1": [_musor(d(0, 6), d(0, 20), "Ma reggeltől"),
               _musor(d(0, 20), d(0, 22), "Ma esti film"),
               _musor(d(0, 23), d(1, 1, 30), "Éjszakai film"),
               _musor(d(1, 8), d(1, 10), "Holnapi műsor"),
               _musor(d(3, 9), d(3, 11), "Három nap múlva")],
        "c2": [_musor(d(0, 10), d(0, 12), "Csak ma")],
    }
    return t


# ---------------------------------------------------- elérhető napok

def test_csatornankent_mas_es_mas_nap_erheto_el(tv):
    ma = dt.date.today()
    assert tv.elerheto_napok("c1") == [ma, ma + dt.timedelta(days=1),
                                       ma + dt.timedelta(days=3)]
    assert tv.elerheto_napok("c2") == [ma], \
        "van csatorna, amire csak mára van adat – ezt látnia kell a felületnek"


def test_csatorna_nelkul_az_osszes_nap(tv):
    assert len(tv.elerheto_napok()) == 3


def test_ures_musornal_nincs_nap():
    assert E.TvMusor().elerheto_napok() == []


# ---------------------------------------------------- egy nap műsora

def test_egy_nap_teljes_musora_nem_csak_mostantol(tv):
    """A lényeg: a REGGELI műsor is látszik, akkor is, ha már délután van."""
    ma = dt.date.today()
    cimek = [m.cim for m in tv.nap_musora("c1", ma)]
    assert "Ma reggeltől" in cimek


def test_a_hajnali_film_meg_az_elozo_naphoz_tartozik(tv):
    """A tévénéző fejében a nap nem éjfélkor ér véget: a 23:00-kor kezdődő,
    hajnalig tartó film MÉG a mai műsor."""
    ma = dt.date.today()
    mai = [m.cim for m in tv.nap_musora("c1", ma)]
    holnapi = [m.cim for m in tv.nap_musora("c1", ma + dt.timedelta(days=1))]
    assert "Éjszakai film" in mai
    assert "Éjszakai film" not in holnapi
    assert "Holnapi műsor" in holnapi


def test_adat_nelkuli_napra_ures_lista(tv):
    ma = dt.date.today()
    assert tv.nap_musora("c1", ma + dt.timedelta(days=2)) == []
    assert tv.nap_musora("nincs_ilyen", ma) == []


def test_a_mostantol_nezet_valtozatlan(tv):
    """A régi viselkedés nem veszhet el: a „mostantól" lista továbbra is a
    még nem véget ért műsorokat adja."""
    kesobb = dt.datetime.combine(dt.date.today(), dt.time(21, 0))
    cimek = [m.cim for m in tv.naprend("c1", kesobb)]
    assert "Ma reggeltől" not in cimek
    assert "Ma esti film" in cimek


# ---------------------------------------------------- felolvasható napnevek

def test_a_napok_neve_emberi():
    ma = dt.date(2026, 8, 24)          # hétfő
    assert E.TvMusor.nap_neve(ma, ma).startswith("ma – hétfő")
    assert E.TvMusor.nap_neve(ma + dt.timedelta(days=1), ma).startswith("holnap")
    assert E.TvMusor.nap_neve(ma + dt.timedelta(days=2), ma).startswith(
        "holnapután")
    tavoli = E.TvMusor.nap_neve(ma + dt.timedelta(days=4), ma)
    assert tavoli.startswith("péntek") and "08. 28." in tavoli
    assert E.TvMusor.nap_neve(ma - dt.timedelta(days=1), ma).startswith("tegnap")
