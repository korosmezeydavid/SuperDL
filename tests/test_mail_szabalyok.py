# -*- coding: utf-8 -*-
"""Super Mail – SZABÁLYOK (MK1).

Felhasználói kérés: „szabályok, külön mappákba csoportosítsa pl. a
levelezőlistás, a marketinges blabla e-maileket, szépen beállíthatóan,
mindenki a saját szabályai szerint”.
"""

import email
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mail_core as MC          # noqa: E402
from mail_mod import szabalyok as SZ          # noqa: E402


def _level(**mezok):
    alap = {"felado": "Hírlevél <info@bolt.hu>", "targy": "Akció",
            "cimzett": "en@sajat.hu", "masolat": "", "torzs": "",
            "lista_id": "", "marketing": False, "csatolmany": False,
            "meret": 0, "fejlecek": {}}
    alap.update(mezok)
    return alap


# ------------------------------------------------- illeszkedés

def test_ekezet_es_kisbetu_nem_szamit():
    """A felhasználó „hirlevel"-t gépel, a tárgyban „Hírlevél" van – ha ez nem
    illeszkedne, a szabály NÉMÁN nem működne."""
    f = SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "hirlevel")
    assert SZ.feltetel_illeszkedik(_level(targy="Heti HÍRLEVÉL"), f)


def test_a_viszonyok_mind_mukodnek():
    lv = _level(felado="Nagy Béla <bela@ceg.hu>")
    p = SZ.MEZO_FELADO
    assert SZ.feltetel_illeszkedik(lv, SZ.Feltetel(p, SZ.VISZ_TARTALMAZZA, "ceg.hu"))
    assert SZ.feltetel_illeszkedik(lv, SZ.Feltetel(p, SZ.VISZ_KEZDODIK, "nagy"))
    assert SZ.feltetel_illeszkedik(lv, SZ.Feltetel(p, SZ.VISZ_VEGZODIK, ">"))
    assert SZ.feltetel_illeszkedik(lv, SZ.Feltetel(p, SZ.VISZ_NEM_TARTALMAZZA, "kiss"))
    assert not SZ.feltetel_illeszkedik(lv, SZ.Feltetel(p, SZ.VISZ_PONTOSAN, "bela"))


def test_meret_kilobajtban_ertendo():
    f = SZ.Feltetel(SZ.MEZO_MERET, SZ.VISZ_NAGYOBB, "100")
    assert SZ.feltetel_illeszkedik(_level(meret=200 * 1024), f)
    assert not SZ.feltetel_illeszkedik(_level(meret=50 * 1024), f)
    # ismeretlen méret (a szerver nem adta meg): NE illeszkedjen
    assert not SZ.feltetel_illeszkedik(_level(meret=0), f)


def test_masolatban_szereplo_cim_is_cimzett():
    f = SZ.Feltetel(SZ.MEZO_CIMZETT, SZ.VISZ_TARTALMAZZA, "titkos@sajat.hu")
    assert SZ.feltetel_illeszkedik(_level(masolat="titkos@sajat.hu"), f)


def test_feltetel_nelkuli_szabaly_soha_nem_illeszkedik():
    """Védelem: egy üres szabály különben az EGÉSZ postaládát elmozgatná."""
    sz = SZ.Szabaly(nev="üres", muveletek={SZ.MUV_TOROL: True})
    assert not SZ.illeszkedik(_level(), sz)


def test_kikapcsolt_szabaly_nem_fut():
    sz = SZ.Szabaly(be=False, feltetelek=[
        SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "akció")])
    assert not SZ.illeszkedik(_level(targy="Akció"), sz)


def test_mind_es_barmelyik():
    feltetelek = [SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "akció"),
                  SZ.Feltetel(SZ.MEZO_FELADO, SZ.VISZ_TARTALMAZZA, "nemletezik")]
    mind = SZ.Szabaly(feltetelek=feltetelek, mind=True)
    barmely = SZ.Szabaly(feltetelek=feltetelek, mind=False)
    lv = _level(targy="Akció")
    assert not SZ.illeszkedik(lv, mind)
    assert SZ.illeszkedik(lv, barmely)


def test_fiokra_szukitett_szabaly():
    sz = SZ.Szabaly(fiok="en@sajat.hu", feltetelek=[
        SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "akció")])
    assert SZ.illeszkedik(_level(targy="Akció"), sz, "en@sajat.hu")
    assert not SZ.illeszkedik(_level(targy="Akció"), sz, "masik@sajat.hu")


# ------------------------------------------------- alkalmazás

def test_a_megall_utan_nem_futnak_tovabbi_szabalyok():
    elso = SZ.Szabaly(nev="egy", muveletek={SZ.MUV_ATHELYEZ: "Lista",
                                            SZ.MUV_MEGALL: True},
                      feltetelek=[SZ.Feltetel(SZ.MEZO_TARGY,
                                              SZ.VISZ_TARTALMAZZA, "hír")])
    masodik = SZ.Szabaly(nev="kettő", muveletek={SZ.MUV_TOROL: True},
                         feltetelek=[SZ.Feltetel(SZ.MEZO_TARGY,
                                                 SZ.VISZ_TARTALMAZZA, "hír")])
    terv = SZ.alkalmaz([_level(targy="Hírek")], [elso, masodik])
    assert len(terv) == 1
    muveletek = terv[0][1]
    assert muveletek[SZ.MUV_ATHELYEZ] == "Lista"
    assert SZ.MUV_TOROL not in muveletek, "a megállás után nem futhat tovább"


def test_az_elso_szabaly_nyer_utkozeskor():
    a = SZ.Szabaly(muveletek={SZ.MUV_ATHELYEZ: "Egy"}, feltetelek=[
        SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "x")])
    b = SZ.Szabaly(muveletek={SZ.MUV_ATHELYEZ: "Kettő"}, feltetelek=[
        SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "x")])
    terv = SZ.alkalmaz([_level(targy="x")], [a, b])
    assert terv[0][1][SZ.MUV_ATHELYEZ] == "Egy"


def test_nem_illeszkedo_level_nem_kerul_a_tervbe():
    sz = SZ.Szabaly(muveletek={SZ.MUV_TOROL: True}, feltetelek=[
        SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA, "soha")])
    assert SZ.alkalmaz([_level(), _level()], [sz]) == []


# ------------------------------------------------- levelezőlista, hírlevél

def test_a_levelezolistat_es_a_hirlevelet_a_fejlecbol_ismerjuk_fel():
    """A küldő SAJÁT jelölésére hagyatkozunk (List-Id, List-Unsubscribe,
    Precedence) – szavakra vadászni („reklám") téves találatokat adna."""
    nyers = ("From: Lista <lista@peldalista.hu>\r\n"
             "Subject: Havi levél\r\n"
             "List-Id: Vak felhasznalok <vakok.peldalista.hu>\r\n"
             "List-Unsubscribe: <mailto:le@peldalista.hu>\r\n\r\ntörzs\r\n")
    info = MC.level_fejlec_info(email.message_from_string(nyers))
    assert "vakok.peldalista.hu" in info["lista_id"]
    assert info["marketing"] is True
    assert SZ.feltetel_illeszkedik(
        info, SZ.Feltetel(SZ.MEZO_LISTA, SZ.VISZ_TARTALMAZZA, "vakok"))
    assert SZ.feltetel_illeszkedik(
        info, SZ.Feltetel(SZ.MEZO_MARKETING, SZ.VISZ_IGAZ))


def test_a_sima_level_nem_marketing():
    nyers = "From: Anyu <anyu@sajat.hu>\r\nSubject: Hívj fel\r\n\r\nszia\r\n"
    info = MC.level_fejlec_info(email.message_from_string(nyers))
    assert info["marketing"] is False
    assert info["lista_id"] == ""


def test_precedence_bulk_is_marketing():
    nyers = ("From: Bolt <info@bolt.hu>\r\nSubject: Akció\r\n"
             "Precedence: bulk\r\n\r\nvegyél\r\n")
    info = MC.level_fejlec_info(email.message_from_string(nyers))
    assert info["marketing"] is True


# ------------------------------------------------- szabály egy levélből

@pytest.mark.parametrize("tipus,vart_mezo", [
    ("felado", SZ.MEZO_FELADO),
    ("domain", SZ.MEZO_FELADO),
    ("lista", SZ.MEZO_LISTA),
    ("targy", SZ.MEZO_TARGY),
    ("marketing", SZ.MEZO_MARKETING),
])
def test_szabaly_a_kijelolt_levelbol(tipus, vart_mezo):
    lv = _level(felado="Bolt <info@bolt.hu>", targy="Akció",
                lista_id="hirek.bolt.hu", marketing=True)
    sz = SZ.szabaly_levelbol(lv, tipus, "Hírlevelek")
    assert sz.feltetelek[0].mezo == vart_mezo
    assert sz.muveletek[SZ.MUV_ATHELYEZ] == "Hírlevelek"
    assert SZ.illeszkedik(lv, sz), "a szabálynak a forrás-levélre illenie KELL"


def test_a_domain_szabaly_a_ceg_minden_cimere_illik():
    lv = SZ.szabaly_levelbol(_level(felado="Bolt <info@bolt.hu>"), "domain")
    assert SZ.illeszkedik(_level(felado="Más <ugyfel@bolt.hu>"), lv)
    assert not SZ.illeszkedik(_level(felado="Idegen <a@masbolt.hu>"), lv)


def test_cim_es_domain_kiszedese():
    assert SZ.cim_resz("Nagy Béla <bela@ceg.hu>") == "bela@ceg.hu"
    assert SZ.cim_resz("bela@ceg.hu") == "bela@ceg.hu"
    assert SZ.domain_resz("Nagy Béla <bela@ceg.hu>") == "ceg.hu"


# ------------------------------------------------- javaslatok

def test_javaslat_csak_sok_levelnel_es_csak_ujra():
    levelek = [_level(lista_id="vakok.lista.hu") for _ in range(7)]
    levelek += [_level(felado="Bolt <info@bolt.hu>", marketing=True)
                for _ in range(6)]
    levelek += [_level(lista_id="ritka.lista.hu")]        # csak 1 – ne javasolja
    j = SZ.javaslatok(levelek)
    mik = {mi for _, mi, _ in j}
    assert "vakok.lista.hu" in mik and "info@bolt.hu" in mik
    assert "ritka.lista.hu" not in mik

    # amire MÁR van szabály, arra ne javasoljon újra
    meglevo = [SZ.szabaly_levelbol(_level(lista_id="vakok.lista.hu"), "lista")]
    mik2 = {mi for _, mi, _ in SZ.javaslatok(levelek, meglevo)}
    assert "vakok.lista.hu" not in mik2


# ------------------------------------------------- felolvasható leírás

def test_a_szabaly_egy_mondatban_elmondhato():
    sz = SZ.Szabaly(nev="Hírlevelek", muveletek={SZ.MUV_ATHELYEZ: "Hírlevelek",
                                                 SZ.MUV_OLVASOTT: True},
                    feltetelek=[SZ.Feltetel(SZ.MEZO_MARKETING, SZ.VISZ_IGAZ)])
    mondat = sz.leiras()
    assert "hírlevél" in mondat.lower() and "Hírlevelek" in mondat
    assert "olvasottnak" in mondat
    ki = SZ.Szabaly(be=False, feltetelek=[SZ.Feltetel()])
    assert "kikapcsolva" in ki.leiras()


# ------------------------------------------------- mentés/betöltés

def test_mentes_es_visszatoltes_megorzi_a_szabalyt(tmp_path):
    sz = SZ.szabaly_levelbol(_level(felado="Bolt <info@bolt.hu>"), "felado",
                             "Bolt")
    SZ.ment(str(tmp_path), [sz])
    vissza = SZ.betolt(str(tmp_path))
    assert len(vissza) == 1
    assert vissza[0].id == sz.id
    assert vissza[0].feltetelek[0].ertek == "info@bolt.hu"
    assert vissza[0].muveletek[SZ.MUV_ATHELYEZ] == "Bolt"


def test_hianyzo_vagy_serult_fajl_nem_szall_el(tmp_path):
    assert SZ.betolt(str(tmp_path)) == []
    (tmp_path / SZ.FAJL).write_text("{ez nem json", encoding="utf-8")
    assert SZ.betolt(str(tmp_path)) == []


# ------------------------------------------------- IMAP mappa létrehozása

class _HamisImap:
    """A minimum, amit a `mappa_letrehoz` használ."""

    def __init__(self, mappak, create_valasz=("OK", [b"kesz"])):
        self._mappak = list(mappak)
        self._valasz = create_valasz
        self.hivasok = []

    def list(self):
        return "OK", [(r'(\HasNoChildren) "/" "%s"' % m).encode()
                      for m in self._mappak]

    def create(self, nev):
        self.hivasok.append(("create", nev))
        if self._valasz[0] == "OK":
            self._mappak.append(nev.strip('"'))
        return self._valasz

    def subscribe(self, nev):
        self.hivasok.append(("subscribe", nev))
        return "OK", [b""]


def _kliens_hamis_imappal(imap):
    k = MC.ImapKliens.__new__(MC.ImapKliens)
    k.M = imap
    return k


def test_meglevo_mappat_nem_hozunk_letre_ujra():
    imap = _HamisImap(["INBOX", "Hírlevelek"])
    k = _kliens_hamis_imappal(imap)
    assert k.mappa_letrehoz("Hírlevelek") == "Hírlevelek"
    assert not [h for h in imap.hivasok if h[0] == "create"]


def test_uj_mappa_letrejon_es_feliratkozunk_ra():
    imap = _HamisImap(["INBOX"])
    k = _kliens_hamis_imappal(imap)
    assert k.mappa_letrehoz("Hírlevelek") == "Hírlevelek"
    assert ("create", "Hírlevelek") in imap.hivasok
    assert any(h[0] == "subscribe" for h in imap.hivasok), \
        "a Gmail csak feliratkozás után mutatja az új mappát"


def test_sikertelen_letrehozas_hibat_dob():
    imap = _HamisImap(["INBOX"], create_valasz=("NO", [b"tiltva"]))
    k = _kliens_hamis_imappal(imap)
    with pytest.raises(RuntimeError):
        k.mappa_letrehoz("Bármi")


def test_ures_mappanev_nem_megy_at():
    k = _kliens_hamis_imappal(_HamisImap(["INBOX"]))
    with pytest.raises(ValueError):
        k.mappa_letrehoz("   ")


# ------------------------------------------------- címjegyzék becenevek

def test_becenev_beallithato_es_kereshetok(tmp_path, monkeypatch):
    """„anyu”, „doki”, „lista” – vakon sokkal gyorsabb, mint a teljes cím."""
    tarolo = []
    monkeypatch.setattr(MC, "cimjegyzek_betolt", lambda: tarolo)
    monkeypatch.setattr(MC, "cimjegyzek_ment", lambda lista: None)
    tarolo.extend([
        {"email": "anya.kovacs@example.hu", "nev": "Kovács Anna", "db": 1},
        {"email": "hirlevel@bolt.hu", "nev": "Bolt", "db": 50},
    ])
    assert MC.cimjegyzek_becenev("anya.kovacs@example.hu", "anyu") is True
    talalt = MC.cimjegyzek_kereses("anyu")
    assert talalt and talalt[0]["email"] == "anya.kovacs@example.hu", \
        "a becenévvel PONTOSAN egyező találat akkor is elöl van, ha ritkább"


def test_ismeretlen_cimhez_nem_lehet_becenevet_adni(monkeypatch):
    monkeypatch.setattr(MC, "cimjegyzek_betolt", lambda: [])
    monkeypatch.setattr(MC, "cimjegyzek_ment", lambda lista: None)
    assert MC.cimjegyzek_becenev("nincs@ilyen.hu", "x") is False
