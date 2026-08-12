# -*- coding: utf-8 -*-
"""TV műsor – az EPG-motor tesztjei (szintetikus XMLTV, hálózat nélkül)."""
import datetime as dt
import importlib

BASE = "modules_src.tvmusor.tvmusor_mod"
E = importlib.import_module(BASE + ".epgmotor")


NAP = dt.date(2026, 8, 11)


def _helyi(ora, perc=0):
    """Egy HELYI idejű datetime a teszt-napon."""
    return dt.datetime.combine(NAP, dt.time(ora, perc))


def _xmltv(ora, perc=0):
    """A helyi időt XMLTV-időbélyeggé alakítja a HELYI eltolással.

    FONTOS: a teszt így IDŐZÓNA-FÜGGETLEN – a CI-futtató (UTC) és a fejlesztői
    gép (CET/CEST) is ugyanazt a helyi órát kapja vissza. Korábban be volt égetve
    a '+0200', ezért a CI-n a 20:00 18:00-ként jött vissza, és elhasalt."""
    t = _helyi(ora, perc)
    off = E._local_offset(t)
    percek = int(off.total_seconds() // 60)
    jel = "+" if percek >= 0 else "-"
    percek = abs(percek)
    return "%s %s%02d%02d" % (t.strftime("%Y%m%d%H%M%S"), jel,
                              percek // 60, percek % 60)


XML = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="rtl.hu"><display-name>RTL</display-name></channel>
  <channel id="tv2.hu"><display-name>TV2</display-name></channel>
  <channel id="m1.hu"><display-name>M1</display-name></channel>
  <programme channel="rtl.hu" start="{t1830}" stop="{t2000}">
    <title>Híradó</title><desc>Esti hírek</desc>
  </programme>
  <programme channel="rtl.hu" start="{t2000}" stop="{t2200}">
    <title>Reszkessetek, betörők!</title>
    <desc>Kevin egyedül marad otthon karácsonykor.</desc>
  </programme>
  <programme channel="tv2.hu" start="{t2000}" stop="{t2130}">
    <title>Mokka este</title><desc>Magazin</desc>
  </programme>
  <programme channel="m1.hu" start="{t2100}" stop="{t2200}">
    <title>Kékfény</title><desc>Bűnügyi magazin</desc>
  </programme>
</tv>
""".format(t1830=_xmltv(18, 30), t2000=_xmltv(20), t2130=_xmltv(21, 30),
           t2100=_xmltv(21), t2200=_xmltv(22))


def _tv():
    return E.TvMusor.ertelmez(XML)


def test_xmltv_ido_ertelmezes():
    t = E.xmltv_ido("20260811200000 +0200")
    assert isinstance(t, dt.datetime)
    assert E.xmltv_ido("") is None
    assert E.xmltv_ido("hulladék") is None


def test_csatornak_es_nevek():
    tv = _tv()
    # a csatorna NEVE az XMLTV-ből jön → nem kell m3u/Xtream
    assert tv.csatorna_nev("rtl.hu") == "RTL"
    assert tv.csatorna_nev("tv2.hu") == "TV2"
    nevek = [n for _cid, n in tv.csatorna_lista()]
    assert nevek == ["M1", "RTL", "TV2"]        # név szerint rendezve


def test_most_es_kovetkezo():
    tv = _tv()
    mikor = _helyi(19)     # 19:00 – Híradó megy
    futo, kov = tv.most_kovetkezo("rtl.hu", mikor)
    assert futo.cim == "Híradó"
    assert kov.cim == "Reszkessetek, betörők!"


def test_mi_megy_most_minden_csatornan():
    tv = _tv()
    mikor = _helyi(20, 30)     # 20:30
    sorok = tv.mi_megy_most(mikor)
    cimek = {nev: m.cim for nev, m in sorok}
    assert cimek["RTL"] == "Reszkessetek, betörők!"
    assert cimek["TV2"] == "Mokka este"
    assert "M1" not in cimek                       # az M1 csak 21:00-kor kezd


def test_ma_este_fomusoridő():
    tv = _tv()
    mikor = _helyi(12)     # dél
    este = tv.ma_este(mikor)
    # kezdés szerint rendezve: 20:00 RTL, 20:00 TV2, 21:00 M1
    assert [m.cim for _n, m in este] == ["Reszkessetek, betörők!", "Mokka este",
                                         "Kékfény"]


def test_kereses_ekezet_es_kisbetu_erzeketlen():
    tv = _tv()
    mikor = _helyi(12)
    # "reszkessetek betorok" – ékezet és vessző nélkül is megtalálja
    tal = tv.keres("reszkessetek", mikortol=mikor)
    assert len(tal) == 1
    nev, m = tal[0]
    assert nev == "RTL" and m.cim == "Reszkessetek, betörők!"
    assert m.idopont == "20:00"
    # a LEÍRÁSBAN is keres: „Kevin”
    assert tv.keres("kevin", mikortol=mikor)[0][1].cim == "Reszkessetek, betörők!"


def test_kereses_mult_kihagyva():
    tv = _tv()
    kesobb = _helyi(23)    # 23:00 – minden lement
    assert tv.keres("reszkessetek", mikortol=kesobb) == []


def test_naprend_es_felolvasas():
    tv = _tv()
    mikor = _helyi(12)
    nap = tv.naprend("rtl.hu", mikor)
    assert [m.cim for m in nap] == ["Híradó", "Reszkessetek, betörők!"]
    sor = nap[1].felolvasva("RTL")
    assert "20:00" in sor and "RTL" in sor and "120 perc" in sor


def test_ures_es_hibas_xml_biztonsagos():
    assert E.TvMusor.ertelmez("").csatorna_lista() == []
    assert E.TvMusor.ertelmez("<tv><badly></tv>").csatorna_lista() == []


# ----------------- betöltés: gyorsítótár + tartalék-lánc -----------------
def test_betolt_okosan_tartalek_es_gyorsitotar(tmp_path, monkeypatch):
    gyt = tmp_path / "epg.xml"
    monkeypatch.setattr(E, "_gyorsitotar_ut", lambda: str(gyt))
    hivas = {"n": 0}

    def hamis_letolt(url, idokorlat=120):
        hivas["n"] += 1
        if "elso" in url:
            raise OSError("nem elérhető")     # az első forrás néma
        return XML                            # a tartalék válaszol

    monkeypatch.setattr(E, "_letolt_szoveg", hamis_letolt)
    monkeypatch.setattr(E, "TARTALEK_URLEK",
                        ["https://elso.pelda/epg.xml", "https://masodik.pelda/epg.xml"])

    tv, honnan = E.TvMusor.betolt_okosan()
    assert honnan == "halozat" and tv.csatorna_nev("rtl.hu") == "RTL"
    assert hivas["n"] == 2                    # elsőt megpróbálta, másodikkal sikerült
    assert gyt.exists()                       # elmentette a gyorsítótárba

    # másodszor: a FRISS gyorsítótárból jön, hálózat nélkül
    tv2, honnan2 = E.TvMusor.betolt_okosan()
    assert honnan2 == "gyorsitotar" and hivas["n"] == 2      # nem hívott hálózatot


def test_betolt_okosan_offline_regi_adatot_ad(tmp_path, monkeypatch):
    gyt = tmp_path / "epg.xml"
    gyt.write_text(XML, encoding="utf-8")
    monkeypatch.setattr(E, "_gyorsitotar_ut", lambda: str(gyt))
    monkeypatch.setattr(E, "_friss_e", lambda ut, ora: False)   # elavult
    monkeypatch.setattr(E, "_letolt_szoveg",
                        lambda url, idokorlat=120: (_ for _ in ()).throw(OSError("nincs net")))
    tv, honnan = E.TvMusor.betolt_okosan()
    assert honnan == "regi" and tv.csatorna_nev("tv2.hu") == "TV2"
