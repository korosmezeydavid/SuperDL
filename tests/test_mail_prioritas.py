# -*- coding: utf-8 -*-
"""Super Mail – LEVÉL-FONTOSSÁG (prioritás).

Felhasználói kérés (2026-08-24): „legyen a levélen belül egy prioritás-választó
– alacsony, közepes, magas, nagyon sürgős. A leveleknél mondja is be, és az
általunk küldött levélnél látszódjon is valahogy. A beállításokban legyen
ki-be kapcsolási lehetőség, hogy mondja-e a sürgősséget.”

MIÉRT HÁROM FEJLÉC? Egyetlen szabvány nincs rá: az X-Priority, az Importance és
a Priority fejléc él egymás mellett, és a levelezőprogramok mást-mást néznek.
Küldéskor tehát MINDET kitesszük, olvasáskor pedig MINDET elfogadjuk.
"""

import email
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mail_core as MC          # noqa: E402
from mail_mod import mailwin as MW            # noqa: E402


def _level(**fejlecek):
    nyers = "From: mari@x.hu\r\nSubject: Teszt\r\n"
    for k, v in fejlecek.items():
        nyers += "%s: %s\r\n" % (k.replace("_", "-"), v)
    return email.message_from_string(nyers + "\r\ntörzs")


# ---------------------------------------------------- küldés

@pytest.mark.parametrize("szint", [MC.PRIO_ALACSONY, MC.PRIO_MAGAS,
                                   MC.PRIO_SURGOS])
def test_a_kimeno_level_mind_a_harom_fejlecet_megkapja(szint):
    m = MC.level_epit("En <en@sajat.hu>", "mari@x.hu", "Tárgy", "szöveg")
    MC.prioritas_beallit(m, szint)
    assert m["X-Priority"] and m["Importance"] and m["Priority"]
    # az Outlook a sajátját nézi elsőként
    assert m["X-MSMail-Priority"]


def test_a_kozepes_nem_tesz_ki_fejlecet():
    """A normál levél az ALAPESET: fölösleges fejléceket nem gyártunk, és a
    címzett programja sem fogja kiemelni."""
    m = MC.level_epit("En <en@sajat.hu>", "mari@x.hu", "Tárgy", "szöveg")
    MC.prioritas_beallit(m, MC.PRIO_NORMAL)
    assert m["X-Priority"] is None and m["Importance"] is None


def test_a_szint_valtoztatasa_nem_duplaz_fejlecet():
    m = MC.level_epit("En <en@sajat.hu>", "mari@x.hu", "Tárgy", "szöveg")
    MC.prioritas_beallit(m, MC.PRIO_SURGOS)
    MC.prioritas_beallit(m, MC.PRIO_MAGAS)
    assert len(m.get_all("X-Priority") or []) == 1
    assert m["X-Priority"].startswith("2")


def test_a_surgos_es_a_magas_kulonbozik():
    a = MC.level_epit("e@n.hu", "m@x.hu", "t", "sz")
    b = MC.level_epit("e@n.hu", "m@x.hu", "t", "sz")
    MC.prioritas_beallit(a, MC.PRIO_SURGOS)
    MC.prioritas_beallit(b, MC.PRIO_MAGAS)
    assert a["X-Priority"].startswith("1") and b["X-Priority"].startswith("2")


# ---------------------------------------------------- olvasás

@pytest.mark.parametrize("fejlecek,vart", [
    ({"X_Priority": "1 (Highest)"}, MC.PRIO_SURGOS),
    ({"X_Priority": "2 (High)"}, MC.PRIO_MAGAS),
    ({"X_Priority": "3"}, MC.PRIO_NORMAL),
    ({"X_Priority": "5 (Lowest)"}, MC.PRIO_ALACSONY),
    ({"Importance": "High"}, MC.PRIO_MAGAS),
    ({"Importance": "high"}, MC.PRIO_MAGAS),
    ({"Importance": "Low"}, MC.PRIO_ALACSONY),
    ({"Priority": "urgent"}, MC.PRIO_MAGAS),
    ({"Priority": "non-urgent"}, MC.PRIO_ALACSONY),
    ({}, MC.PRIO_NORMAL),
])
def test_barmelyik_szabvanyt_megertjuk(fejlecek, vart):
    assert MC.prioritas_a_fejlecbol(_level(**fejlecek)) == vart


def test_ertelmetlen_ertek_eseten_normal():
    """Tévesen sürgetni rosszabb, mint nem jelezni."""
    assert MC.prioritas_a_fejlecbol(_level(X_Priority="sürgős!")) == \
        MC.PRIO_NORMAL
    assert MC.prioritas_a_fejlecbol(_level(Importance="közepes")) == \
        MC.PRIO_NORMAL


def test_a_lista_info_is_tartalmazza():
    info = MC.level_fejlec_info(_level(X_Priority="1 (Highest)"))
    assert info["prioritas"] == MC.PRIO_SURGOS


def test_a_korbe_megy_kuldestol_olvasasig():
    m = MC.level_epit("En <en@sajat.hu>", "mari@x.hu", "Tárgy", "szöveg")
    MC.prioritas_beallit(m, MC.PRIO_SURGOS)
    vissza = email.message_from_string(m.as_string())
    assert MC.level_fejlec_info(vissza)["prioritas"] == MC.PRIO_SURGOS


# ---------------------------------------------------- megjelenítés

def test_a_felolvasott_jelzes():
    assert MC.prioritas_szoveg(MC.PRIO_SURGOS) == "NAGYON SÜRGŐS"
    assert MC.prioritas_szoveg(MC.PRIO_MAGAS) == "fontos"
    assert MC.prioritas_szoveg(MC.PRIO_NORMAL) == "", \
        "a közepes az alapeset – azt NEM mondjuk be"
    assert MC.prioritas_szoveg("") == ""


def _sor(info, prio_jelzes=True, monkeypatch=None):
    class _Keret:
        _osszesitett = False
        _sor_szoveg = MW.MailFrame._sor_szoveg
    alap = dict(MC._ALTALANOS_ALAP)
    alap["prioritas_jelzes"] = prio_jelzes
    monkeypatch.setattr(MC, "altalanos_betolt", lambda: alap)
    return _Keret()._sor_szoveg(info)


def test_a_listasor_ELEJEN_van_a_jelzes(monkeypatch):
    """Vakon az számít, ami ELŐSZÖR elhangzik – a sor végén a hosszú tárgy
    után elsikkadna."""
    info = {"felado": "Mari <mari@x.hu>", "targy": "Szerződés",
            "datum": "ma 10:00", "olvasott": True, "prioritas": MC.PRIO_SURGOS}
    sor = _sor(info, True, monkeypatch)
    assert sor.startswith("NAGYON SÜRGŐS")


def test_a_kozepes_nem_jelenik_meg_a_sorban(monkeypatch):
    info = {"felado": "Mari", "targy": "Szia", "datum": "ma", "olvasott": True,
            "prioritas": MC.PRIO_NORMAL}
    assert not _sor(info, True, monkeypatch).startswith("NAGYON")


def test_kikapcsolva_semmilyen_jelzes_nincs(monkeypatch):
    info = {"felado": "Mari", "targy": "Szia", "datum": "ma", "olvasott": True,
            "prioritas": MC.PRIO_SURGOS}
    sor = _sor(info, False, monkeypatch)
    assert "SÜRGŐS" not in sor


# ---------------------------------------------------- érkezéskori bemondás

def test_az_erkezesi_jelzes_szovege(monkeypatch):
    alap = dict(MC._ALTALANOS_ALAP)
    alap["prioritas_jelzes"] = True
    monkeypatch.setattr(MC, "altalanos_betolt", lambda: alap)
    assert MW.MailFrame._surgos_szoveg(1) == "SÜRGŐS levél!"
    assert MW.MailFrame._surgos_szoveg(3) == "3 SÜRGŐS levél!"
    assert MW.MailFrame._surgos_szoveg(0) == ""


def test_kikapcsolva_az_erkezeskor_sem_mondjuk(monkeypatch):
    alap = dict(MC._ALTALANOS_ALAP)
    alap["prioritas_jelzes"] = False
    monkeypatch.setattr(MC, "altalanos_betolt", lambda: alap)
    assert MW.MailFrame._surgos_szoveg(2) == ""


def test_az_alapertelmezes_bekapcsolt():
    assert MC._ALTALANOS_ALAP["prioritas_jelzes"] is True


def test_a_lekeres_keri_a_fontossag_fejleceket():
    fetch = MC.ImapKliens._FEJLEC_FETCH
    for f in ("X-PRIORITY", "IMPORTANCE", "PRIORITY"):
        assert f in fetch
