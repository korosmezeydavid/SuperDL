# -*- coding: utf-8 -*-
"""szakember83 jelentése (2026-09-10) — az ELSŐ jelentés az új naplóval.

Negyven perccel a 4.6.4 hírlevele után érkezett, és nem csak a felhasználó
hibáját mutatta meg, hanem KETTŐT a mieinkből is. Négy dolgot véd ez a fájl:

1. a már LEFORDÍTOTT hibaüzenetet nem minősítjük „ismeretlennek" (4.6.4-es
   visszalépés: a jó magyarázatot cseréltük le a „nem ismerjük fel" szövegre);
2. a saját gépen belüli (127.0.0.1) időtúllépésre NEM küldjük a felhasználót
   az internetkapcsolatát ellenőrizni;
3. a frissítés utáni ELSŐ induláskor nem riasztunk hetekkel korábbi
   összeomlásokra úgy, mintha „legutóbb" történtek volna;
4. a néma vezérlőcsatornából nem csinálunk VÉGLEGES letöltési hibát.
"""

import pytest

from superdl import hibaszoveg
from superdl.torrent import TorrentDownloader


# A szakember83 naplójából, szó szerint:
RPC_HIBA = ("HTTPConnectionPool(host='127.0.0.1', port=41142): "
            "Read timed out. (read timeout=15)")


# ---- 1. a lefordított üzenetet ne minősítsük ismeretlennek --------------

def test_a_mar_leforditott_uzenetet_nem_csereljuk_le():
    """⚠️ EZ A 4.6.4 VISSZALÉPÉSE. A `manager` a fordítás UTÁN tölti a
    `progress.error` mezőt; a felület ezt kapja. Ha újra megvizsgálja,
    „ismeretlennek" látszik — és pont a jó magyarázatot dobjuk el."""
    leforditott = hibaszoveg.emberi(RPC_HIBA)
    assert leforditott != RPC_HIBA               # tényleg lefordítottuk
    # a MENTETT válasszal: megmarad
    assert hibaszoveg.olvashato(leforditott, True) == leforditott
    # a mentett válasz NÉLKÜL viszont elveszne – ezért kell átadni
    assert hibaszoveg.olvashato(leforditott) == hibaszoveg.ISMERETLEN_MONDAT


def test_az_ismeretlen_uzenetnel_az_ismert_hamis_dont():
    nyers = "Xyz engine failure 0x8007005 QQQ"
    assert hibaszoveg.olvashato(nyers, False) == hibaszoveg.ISMERETLEN_MONDAT


def test_a_gond_mondat_is_atveszi_a_mentett_valaszt():
    leforditott = hibaszoveg.emberi(RPC_HIBA)
    m = hibaszoveg.gond_mondat("film.mkv", "hiba", leforditott, ismert=True)
    assert "nem ismerjük fel" not in m
    assert "torrent-motor" in m.lower()


def test_a_mentett_valasz_nelkul_a_regi_viselkedes_marad():
    """A `None` = „nem tudom" — ilyenkor a régi, találgató ág fut. Ez védi
    a régi hívókat (modulok), amelyek nem ismerik az új mezőt."""
    assert hibaszoveg.olvashato("aria2c.exe not found", None) != \
        hibaszoveg.ISMERETLEN_MONDAT


# ---- 2. a loopback-időtúllépés NEM internethiba ------------------------

def test_a_sajat_gepen_beluli_idotullepes_nem_internethiba():
    """⚠️ A felhasználó ezt hallotta: „HÁLÓZATI HIBA: az oldal nem érhető el.
    Ellenőrizd az internetkapcsolatot." Egy 127.0.0.1-es időtúllépésre.
    Elküldtük a routert bütykölni, miközben a netje kifogástalan volt."""
    m = hibaszoveg.emberi(RPC_HIBA)
    assert "internetkapcsolatoddal" in m or "nincs baj" in m
    # és NEM küldjük az internetet ellenőrizni
    assert "Ellenőrizd az internetkapcsolatot" not in m
    assert "az oldal nem érhető el" not in m


def test_a_loopback_minta_a_localhostot_is_erti():
    m = hibaszoveg.emberi("HTTPConnectionPool(host='localhost', port=9): "
                          "Read timed out.")
    assert "gépen BELÜLI" in m


def test_a_VALODI_halozati_hiba_tovabbra_is_halozati():
    """⚠️ A leggyakoribb rontás: egy új minta elnyeli a régi eseteket.
    A valódi, kifelé menő hálózati hiba üzenete NEM változhat."""
    m = hibaszoveg.emberi("Failed to establish a new connection: "
                          "[Errno 11001] getaddrinfo failed")
    assert "gépen BELÜLI" not in m


# ---- 3. a frissítés utáni első indulás nem hamis riasztás ---------------

NYOM = ("Windows fatal exception: code 0x8001010d\n"
        "Current thread 0x00002cfc (most recent call first):\n")


@pytest.fixture
def omlas(tmp_path, monkeypatch):
    from superdl import osszeomlas
    monkeypatch.setattr(osszeomlas, "NAPLO", tmp_path / "osszeomlas.log")
    monkeypatch.setattr(osszeomlas, "_OLVASVA", tmp_path / "olvasva.txt")
    monkeypatch.setattr(osszeomlas, "_uj_resz", "")
    monkeypatch.setattr(osszeomlas, "_fajl", None)
    return osszeomlas


def test_a_frissites_utani_ELSO_indulas_nem_riaszt(omlas):
    """⚠️ szakember83-nál pontosan ez történt: a 4.6.4 első indulásakor a
    program közölte, hogy „legutóbb váratlanul bezárult" — holott nem. A
    jelölő még nem létezett, tehát az EGÉSZ eddigi napló újnak látszott.
    Egy hetekkel korábbi összeomlásra azt mondani, hogy „legutóbb", hazugság
    — és a felhasználó egy nem létező mai hibát kezd keresni."""
    omlas.NAPLO.parent.mkdir(parents=True, exist_ok=True)
    omlas.NAPLO.write_text("regi naplo\n" + NYOM, encoding="utf-8")
    assert not omlas._OLVASVA.exists()          # nincs jelölő: első indulás
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False
    # de a jelölő létrejött, tehát a KÖVETKEZŐ összeomlást már észrevesszük
    assert omlas._OLVASVA.exists()
    with open(omlas.NAPLO, "a", encoding="utf-8") as f:
        f.write(NYOM)
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is True


def test_a_torolt_naplo_sem_riaszt(omlas):
    """A törölt napló nem összeomlás. Korábban itt nulláztunk, és ezzel az
    egész maradék történetet újnak vettük volna."""
    omlas.NAPLO.parent.mkdir(parents=True, exist_ok=True)
    omlas.NAPLO.write_text("x" * 5000, encoding="utf-8")
    omlas._olvasatlan_beolvas()
    omlas.NAPLO.write_text(NYOM, encoding="utf-8")     # rövidebb lett
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False


# ---- 4. a néma vezérlés nem VÉGLEGES hiba -------------------------------

class _NemaKliens:
    """Motor-utánzat, amely nem válaszol a vezérlésre."""

    def __init__(self, hibak: int):
        self.hatra = hibak
        self.hivasok = 0

    def call(self, method, *params):
        self.hivasok += 1
        if method == "aria2.addTorrent" or method == "aria2.addUri":
            if self.hatra > 0:
                self.hatra -= 1
                raise RuntimeError(
                    "HTTPConnectionPool(host='127.0.0.1', port=41142): "
                    "Read timed out. (read timeout=15)")
            return "gid123"
        raise RuntimeError("nem válaszol")


def _letolto(tmp_path, kliens):
    d = TorrentDownloader("magnet:?xt=urn:btih:abc", str(tmp_path))
    d.client = kliens
    return d


def test_az_elfoglalt_motor_miatt_nem_bukik_el_a_hozzaadas(tmp_path,
                                                           monkeypatch):
    """Ha a motor épp egy nagy fájlt ellenőriz, a hozzáadás időtúllépésre
    fut. Ez MÚLIK — kivárjuk."""
    monkeypatch.setattr("time.sleep", lambda s: None)
    kliens = _NemaKliens(hibak=2)
    d = _letolto(tmp_path, kliens)
    assert d._add_turelemmel() == "gid123"
    assert d.progress.figyelmeztetes                  # szóltunk is róla


def test_a_duplikatum_hiban_NEM_probalkozunk_tovabb(tmp_path, monkeypatch):
    """⚠️ A megkülönböztetés lényege: a „nem válaszolsz" múlik, a „ezt az
    infohasht már ismerem" NEM. Az utóbbin várni merő időpocsékolás, és a
    felhasználó addig sem tudja meg, mi a baj."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    class _Duplikatum:
        def __init__(self):
            self.hivasok = 0

        def call(self, method, *params):
            self.hivasok += 1
            raise RuntimeError("InfoHash abc123 is already registered.")

    kliens = _Duplikatum()
    d = _letolto(tmp_path, kliens)
    with pytest.raises(RuntimeError, match="already registered"):
        d._add_turelemmel()
    assert kliens.hivasok == 1                # EGYETLEN próba, nem öt


def test_a_leallitas_megszakitja_a_varakozast(tmp_path, monkeypatch):
    """A türelem nem mehet a leállítás rovására: a felhasználó parancsa
    előbbre való, mint a mi kivárásunk."""
    monkeypatch.setattr("time.sleep", lambda s: None)
    d = _letolto(tmp_path, _NemaKliens(hibak=99))
    d.stop()
    with pytest.raises(RuntimeError, match="leállították"):
        d._add_turelemmel()


def test_a_tureshatar_valodi_percekben_merve():
    """Öt perc: egy több gigabájtos torrent hash-ellenőrzése ennyit bőven
    kitölthet. Ha ez túl rövid, visszajön az eredeti hiba — ezért teszt védi."""
    assert TorrentDownloader.VEZERLES_TURES_MP >= 180.0
