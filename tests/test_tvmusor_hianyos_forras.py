"""TV újság: HIÁNYOS FORRÁS – Turai László jelzése, 2026-09-21.

„A csatornák lapfülre lépve csak 3 db csatornát látok…"

AMIT LEMÉRTÜNK. Az akkori elsődleges forrás (epgshare01 HU1) 193
`<channel>` elemet hirdetett, de MŰSORT csak HÁROMHOZ adott. A régi
`betolt_okosan` az ELSŐ nem-üres forrást fogadta el, tehát ezt sikernek
vette, elmentette a gyorsítótárba, és ezzel FELÜLÍRTA a korábbi, 164
csatornás jó adatot. A felhasználó ezután hat órán át három csatornát
látott – magyarázat nélkül. A tartalék forrás közben HTTP 523-mal elhalt.

A hiba tehát NEM az volt, hogy három csatorna jött, hanem hogy
  (a) a hiányos adat kiszorította a jót, és
  (b) a program erről hallgatott.
Ezek az esetek mind a kettőt őrzik.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/tvmusor")
from tvmusor_mod import epgmotor as EM            # noqa: E402


def _xml(csatornak, musorosak=()):
    """Kis XMLTV: `csatornak` a deklarált nevek, `musorosak` azok, amikhez
    TÉNYLEG van műsor. Pont ez a kettő vált szét élesben."""
    ki = ['<?xml version="1.0" encoding="UTF-8"?><tv>']
    for nev in csatornak:
        ki.append('<channel id="%s.hu"><display-name>%s</display-name>'
                  "</channel>" % (nev, nev))
    for nev in musorosak:
        ki.append('<programme channel="%s.hu" start="20260921080000 +0200" '
                  'stop="20260921090000 +0200"><title>Műsor</title>'
                  "</programme>" % nev)
    ki.append("</tv>")
    return "".join(ki)


BO = _xml(["A%d" % i for i in range(40)], ["A%d" % i for i in range(40)])
SZEGENY = _xml(["A%d" % i for i in range(40)], ["A0", "A1", "A2"])


@pytest.fixture
def kornyezet(tmp_path, monkeypatch):
    """Saját gyorsítótár-útvonal és letöltés-helyettes."""
    gyt = tmp_path / "tvmusor_epg.xml"
    monkeypatch.setattr(EM, "_gyorsitotar_ut", lambda: str(gyt))
    valaszok = {}

    def hamis_letolt(url, idokorlat=120):
        if url in valaszok:
            v = valaszok[url]
            if isinstance(v, Exception):
                raise v
            return v
        raise OSError("nincs ilyen forrás: %s" % url)

    monkeypatch.setattr(EM, "_letolt_szoveg", hamis_letolt)
    return {"gyt": gyt, "valaszok": valaszok, "monkeypatch": monkeypatch}


def _forrasok(kornyezet, parok):
    kornyezet["monkeypatch"].setattr(EM, "TARTALEK_URLEK",
                                     [u for u, _ in parok])
    for u, v in parok:
        kornyezet["valaszok"][u] = v


# ─────────────── a deklarált és a MŰSOROS csatorna nem ugyanaz ──────

def test_a_csatorna_lista_csak_a_musorosakat_adja():
    """Ez a hiba gyökere: 193 csatorna volt hirdetve, műsor háromhoz."""
    tv = EM.TvMusor.ertelmez(SZEGENY)
    assert len(tv.csatornak) == 40
    assert len(tv.csatorna_lista()) == 3


# ───────────────── a legtöbb csatornát adó forrás nyer ──────────────

def test_nem_az_elso_hanem_a_legbovebb_forras_nyer(kornyezet):
    """⚠️ A régi kód itt a három csatornás forrást fogadta volna el, mert
    az volt az első nem-üres."""
    _forrasok(kornyezet, [("http://a/szegeny.xml", SZEGENY),
                          ("http://b/bo.xml", BO)])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "halozat"
    assert len(tv.csatorna_lista()) == 40


def test_bo_forrasnal_a_tobbit_meg_sem_probaljuk(kornyezet):
    """Ha az első forrás bőséges, nem terheljük feleslegesen a többit."""
    hivott = []
    _forrasok(kornyezet, [("http://a/bo.xml", BO),
                          ("http://b/masik.xml", BO)])
    eredeti = EM._letolt_szoveg

    def figyelo(url, idokorlat=120):
        hivott.append(url)
        return eredeti(url, idokorlat)
    kornyezet["monkeypatch"].setattr(EM, "_letolt_szoveg", figyelo)
    EM.TvMusor.betolt_okosan()
    assert hivott == ["http://a/bo.xml"]


def test_halott_forras_atugorva(kornyezet):
    """A tartalék forrás élesben HTTP 523-mal halt el."""
    _forrasok(kornyezet, [("http://halott/", OSError("523")),
                          ("http://b/bo.xml", BO)])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "halozat"
    assert len(tv.csatorna_lista()) == 40


# ─────────── a hiányos adat nem szoríthatja ki a jót ────────────────

def test_hianyos_letoltes_nem_irja_felul_a_bovebb_gyorsitotarat(kornyezet):
    """⚠️ EZ A LÉNYEG. Ez a sor tette tönkre Laci adatát.

    A gyorsítótárat RÉGIVÉ tesszük, hogy tényleg a hálózati ágon menjen
    végig – különben a friss gyorsítótár már az első lépésben nyerne, és
    a teszt nem azt mérné, amit akarunk."""
    import os
    import time
    kornyezet["gyt"].write_text(BO, encoding="utf-8")
    regen = time.time() - 48 * 3600
    os.utime(kornyezet["gyt"], (regen, regen))
    _forrasok(kornyezet, [("http://a/szegeny.xml", SZEGENY)])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "regi"
    assert len(tv.csatorna_lista()) == 40
    # és a mentett adat érintetlen maradt
    assert len(EM.TvMusor.ertelmez(
        kornyezet["gyt"].read_text(encoding="utf-8")).csatorna_lista()) == 40


def test_hianyos_letoltest_egyaltalan_nem_mentunk(kornyezet):
    """Gyorsítótár nélkül sem mentjük el: különben a következő indulás is
    a hiányos adatot kapná, hat órán át."""
    _forrasok(kornyezet, [("http://a/szegeny.xml", SZEGENY)])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "hianyos"
    assert len(tv.csatorna_lista()) == 3
    assert not kornyezet["gyt"].exists(), "a hiányos adatot nem mentjük"


def test_a_friss_de_hianyos_gyorsitotarat_sem_fogadjuk_el(kornyezet):
    """A csapda másik fele: ha a hiányos adat MÉGIS bekerült (régi verzió,
    kézi másolás), a friss gyorsítótár ne zárja ki a hálózatot."""
    kornyezet["gyt"].write_text(SZEGENY, encoding="utf-8")
    _forrasok(kornyezet, [("http://a/bo.xml", BO)])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "halozat"
    assert len(tv.csatorna_lista()) == 40


def test_bo_es_friss_gyorsitotar_eseten_nincs_halozat(kornyezet):
    """Ami jó volt, az jó marad: a bőséges friss gyorsítótár azonnal nyer."""
    kornyezet["gyt"].write_text(BO, encoding="utf-8")
    _forrasok(kornyezet, [("http://a/bo.xml", OSError("ide nem jutunk"))])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "gyorsitotar"
    assert len(tv.csatorna_lista()) == 40


def test_semmi_sincs_ures_musort_ad(kornyezet):
    _forrasok(kornyezet, [("http://a/", OSError("nincs"))])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == ""
    assert tv.csatorna_lista() == []


# ─────────────────────── felolvasható csatornanév ───────────────────

@pytest.mark.parametrize("nyers,var", [
    ("AMC (HD).hu", "AMC (HD)"),
    ("RTL.hu", "RTL"),
    ("HU - Auto Motor Sport TV", "Auto Motor Sport TV"),
    ("HU  -  ATV Spirit", "ATV Spirit"),
    ("  Duna  World .hu ", "Duna World"),
    ("M3", "M3"),
    ("Mezzo", "Mezzo"),
    ("", ""),
])
def test_a_csatornanevbol_eltunnek_a_technikai_toldalekok(nyers, var):
    """⚠️ Nem szépészet: felolvasva a „.hu" minden sor végén „pont hu"-ként
    szólal meg, 175 csatornánál ez 175 felesleges szótag."""
    assert EM.szep_nev(nyers) == var


def test_a_nevtisztitas_az_ertelmezesben_is_megtortenik():
    tv = EM.TvMusor.ertelmez(
        '<?xml version="1.0"?><tv>'
        '<channel id="amc.hu"><display-name>AMC (HD).hu</display-name>'
        "</channel>"
        '<programme channel="amc.hu" start="20260921080000 +0200" '
        'stop="20260921090000 +0200"><title>Film</title></programme>'
        "</tv>")
    assert tv.csatorna_lista() == [("amc.hu", "AMC (HD)")]


def test_a_tisztitas_nem_eszi_meg_a_teljes_nevet():
    """Egy csupa-toldalék névből se legyen üres sor a listában."""
    assert EM.szep_nev(".hu") == ".hu"
    assert EM.szep_nev("HU - ") == "HU -"


# ───────── a „hiányos" ARÁNY kérdése, nem darabszámé ────────────────

def test_a_kicsi_de_TELJES_forras_nem_hianyos():
    """⚠️ Ezen bukott el az első megoldásom. Aki SZÁNDÉKOSAN ad meg egy
    ötcsatornás saját forrást, annak az teljes – nem szabad „hiányos"-nak
    minősíteni csak azért, mert kicsi."""
    tv = EM.TvMusor.ertelmez(_xml(["A", "B", "C", "D", "E"],
                                  ["A", "B", "C", "D", "E"]))
    assert not EM.hianyos_e(tv)


def test_a_sok_csatornat_hirdeto_de_harmat_ado_forras_hianyos():
    """Pontosan Laci esete: 193 hirdetett, 3 műsoros."""
    tv = EM.TvMusor.ertelmez(SZEGENY)
    assert EM.hianyos_e(tv)


def test_az_ures_musorujsag_hianyos():
    assert EM.hianyos_e(EM.TvMusor.ertelmez(_xml(["A", "B"], [])))


def test_a_kicsi_teljes_forrast_el_is_fogadjuk(kornyezet):
    """A motor is így viselkedjen, ne csak a `hianyos_e`."""
    kicsi = _xml(["A", "B", "C"], ["A", "B", "C"])
    _forrasok(kornyezet, [("http://a/kicsi.xml", kicsi)])
    tv, honnan = EM.TvMusor.betolt_okosan()
    assert honnan == "halozat"
    assert len(tv.csatorna_lista()) == 3
    assert kornyezet["gyt"].exists(), "a teljes forrást el KELL menteni"
