# -*- coding: utf-8 -*-
"""iPhone modul – a mag ellenőrzése ÉLŐ TELEFON NÉLKÜL.

A törlés a modul legkényesebb művelete: beleír a telefon zene-adatbázisába.
Egyszer már láttuk, mi történik, ha egy elbukott lépés után mégis lefut az írás
(a könyvtár egy pillanatra kiürült), ezért a `zene_torol` szigorú rendet követ:
mentés → módosítás másolaton → ellenőrzés → írás → visszaolvasás → szükség
esetén AUTOMATIKUS visszaállítás.

Ezek a tesztek pont ezt az őrszemet feszegetik: sérült eredménynél,
téves darabszámnál és romlott visszaolvasásnál is a telefon épségének kell
győznie. A hálózat helyett egy kamu-AFC réteg áll, ami fájlokat tart a memóriában.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, "modules_src/iphone")
from iphone_mod import afc as A                      # noqa: E402
from iphone_mod import iphone_core as C             # noqa: E402


# ------------------------------------------------------------ kamu telefon

def _epit_db(ut, darab=3):
    """Egy pici, de a valódival egyező szerkezetű zene-adatbázis."""
    c = sqlite3.connect(ut)
    c.executescript("""
        create table item (item_pid integer primary key, item_artist_pid integer,
                           album_pid integer, base_location_id integer);
        create table item_extra (item_pid integer primary key, title text,
                                 total_time_ms real, location text,
                                 file_size integer);
        create table item_artist (item_artist_pid integer primary key,
                                  item_artist text);
        create table album (album_pid integer primary key, album text);
        create table base_location (base_location_id integer primary key,
                                    path text);
        insert into base_location values (3840, 'iTunes_Control/Music/F00');
        insert into item_artist values (1, 'Teszt Előadó');
        insert into album values (1, 'Teszt Album');
    """)
    for i in range(darab):
        c.execute("insert into item values (?,1,1,3840)", (100 + i,))
        c.execute("insert into item_extra values (?,?,?,?,?)",
                  (100 + i, "Szám %d" % i, 60000.0, "S%03d.mp3" % i, 1000))
    c.commit()
    c.close()


class KamuAfc:
    """A telefon fájljai egy szótárban.

    Az `iras_rontas` azt hazudja, hogy az írás sikerült, közben mást tesz le –
    így tesztelhető az őrszem. CSAK AZ ELSŐ adatbázis-írást rontja el, mert a
    valóságban is az a kockázatos lépés (ott versenyzünk a telefon saját
    szolgáltatásával); a visszaállításnak sikerülnie kell, különben nem azt
    mérnénk, amit akarunk."""

    def __init__(self, fajlok, iras_rontas=None):
        self.fajlok = dict(fajlok)
        self.iras_rontas = iras_rontas
        self.torolt = []

    def letolt(self, ut, cel, on_progress=None, darab=1 << 20, megszakit=None):
        if ut not in self.fajlok:
            raise A.IPhoneHiba("nincs ilyen fájl: " + ut)
        if megszakit is not None and megszakit():
            raise A.Megszakitva("A művelet megszakítva.")
        adat = self.fajlok[ut]
        with open(cel, "wb") as f:
            f.write(adat)
        if on_progress:
            on_progress(len(adat), len(adat))
        return len(adat)

    def ir(self, ut, adat):
        if self.iras_rontas is not None and ut.endswith("MediaLibrary.sqlitedb"):
            adat, self.iras_rontas = self.iras_rontas, None
        self.fajlok[ut] = adat

    def torol(self, ut):
        if ut not in self.fajlok:
            raise A.IPhoneHiba("nincs ilyen fájl: " + ut)
        del self.fajlok[ut]
        self.torolt.append(ut)

    def meret(self, ut):
        return len(self.fajlok.get(ut, b""))

    def bezar(self):
        pass


class KamuTelefon(C.Telefon):
    """A `Telefon`, de kapcsolat nélkül – csak a logikát futtatjuk."""

    def __init__(self, afc):
        self._afc = afc
        self.nev, self.ios, self.modell = "Teszt", "26.0", "iPhone16,1"

    @property
    def afc(self):
        return self._afc

    def bezar(self):
        pass


@pytest.fixture
def telefon(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "mentes_mappa", lambda: str(tmp_path / "mentes"))
    db = tmp_path / "eredeti.sqlitedb"
    _epit_db(str(db))
    fajlok = {C.DB_MAPPA + C.DB_NEV: db.read_bytes()}
    for i in range(3):
        fajlok["/iTunes_Control/Music/F00/S%03d.mp3" % i] = b"ID3" + bytes(100)
    return KamuTelefon(KamuAfc(fajlok))


# ------------------------------------------------------------- fájlnevek

@pytest.mark.parametrize("be,ki", [
    ('AC/DC: Thunder?', "AC-DC- Thunder-"),
    ("  sok    szóköz  ", "sok szóköz"),
    ("pont a végén...", "pont a végén"),
    ("", "névtelen"),
    (None, "névtelen"),
])
def test_a_fajlnev_windowson_is_hasznalhato(be, ki):
    """A tiltott jeleket CSERÉLJÜK, nem dobjuk el a nevet – a felhasználó
    zenéiben bőven van „?”, „:” és „/”."""
    assert C._tiszta_nev(be) == ki


def test_a_fajlnev_nem_lesz_veget_nem_ero():
    assert len(C._tiszta_nev("a" * 400)) <= 120


def test_a_letezo_fajlt_soha_nem_irjuk_felul(tmp_path):
    p = tmp_path / "dal.mp3"
    p.write_bytes(b"x")
    masodik = C._egyedi(str(p))
    assert masodik != str(p) and masodik.endswith("dal (2).mp3")


# ------------------------------------------------------------- listázás

def test_a_zenek_cimmel_es_eloadoval_jonnek(telefon):
    z = telefon.zenek()
    assert len(z) == 3
    assert z[0]["cim"].startswith("Szám")
    assert z[0]["eloado"] == "Teszt Előadó"
    assert z[0]["album"] == "Teszt Album"
    assert z[0]["ut"] == "/iTunes_Control/Music/F00/S000.mp3", \
        "a lista a base_location tábla útját ragasztja a fájlnév elé"
    assert z[0]["mp"] == 60


def test_a_mentes_rendes_neven_es_mappakba_ir(telefon, tmp_path):
    cel = tmp_path / "kimenet"
    ok, hibak = telefon.zene_ment(telefon.zenek(), str(cel), mappakba=True)
    assert (ok, hibak) == (3, [])
    vart = cel / "Teszt Előadó" / "Teszt Album" / "Szám 0.mp3"
    assert vart.exists(), "előadó/album mappába, a szám CÍMÉVEL"
    assert vart.read_bytes().startswith(b"ID3")


def test_mappak_nelkul_az_eloado_a_nevbe_kerul(telefon, tmp_path):
    cel = tmp_path / "lapos"
    telefon.zene_ment(telefon.zenek()[:1], str(cel), mappakba=False)
    assert (cel / "Teszt Előadó - Szám 0.mp3").exists()


# --------------------------------------------------- a törlés őrszemei

def test_a_torles_mukodik_es_mentest_hagy(telefon):
    z = telefon.zenek()
    db, mentes = telefon.zene_torol(z[:1])
    assert db == 1
    assert os.path.exists(os.path.join(mentes, C.DB_NEV)), \
        "a biztonsági mentésnek meg kell maradnia a lemezen"
    assert len(telefon.zenek()) == 2, "a bejegyzés eltűnt"
    assert "/iTunes_Control/Music/F00/S000.mp3" in telefon.afc.torolt, \
        "a hangfájl is törlődött, nem csak a bejegyzés"


def test_ures_lista_eseten_nem_tortenik_semmi(telefon):
    assert telefon.zene_torol([]) == (0, "")
    assert len(telefon.zenek()) == 3


def test_romlott_visszaolvasasnal_MAGATOL_visszaall(telefon, tmp_path):
    """Ha a telefonra kiírt adatbázis nem az, aminek lennie kellene, a modul
    NEM hagyhatja ott: vissza kell állítania a mentést."""
    telefon.afc.iras_rontas = b"ez nem egy adatbazis"
    z = telefon.zenek()
    with pytest.raises(A.IPhoneHiba) as hiba:
        telefon.zene_torol(z[:1])
    assert "VISSZAÁLLÍTOTTAM" in str(hiba.value)
    assert len(telefon.zenek()) == 3, "mind a három szám megvan"


def test_romlott_visszaolvasasnal_a_hangfajl_is_megmarad(telefon):
    telefon.afc.iras_rontas = b"szemet"
    with pytest.raises(A.IPhoneHiba):
        telefon.zene_torol(telefon.zenek()[:1])
    assert telefon.afc.torolt == [], \
        "ha az adatbázis-írás elbukott, a hangfájlhoz hozzá sem nyúlunk"


def test_ismeretlen_szam_torlese_nem_ir_vissza_semmit(telefon):
    """Ha a törlendő nincs is bent, a darabszám nem stimmel – ilyenkor a modul
    inkább nem nyúl a telefonhoz."""
    hamis = [{"pid": 999999, "ut": "/nincs.mp3", "cim": "nincs ilyen"}]
    with pytest.raises(A.IPhoneHiba) as hiba:
        telefon.zene_torol(hamis)
    assert "nem írok vissza semmit" in str(hiba.value)
    assert len(telefon.zenek()) == 3


def test_a_visszaallitas_kulon_is_hivhato(telefon, tmp_path):
    z = telefon.zenek()
    _db, mentes = telefon.zene_torol(z[:1])
    assert len(telefon.zenek()) == 2
    telefon.visszaallit(mentes)
    assert len(telefon.zenek()) == 3, "a mentésből minden visszajön"


def test_a_visszaallitas_ures_mappara_beszedes_hibat_ad(telefon, tmp_path):
    with pytest.raises(A.IPhoneHiba) as hiba:
        telefon.visszaallit(str(tmp_path / "sehol"))
    assert "nincs menthető adatbázis" in str(hiba.value)


# ------------------------------------------------------------- kényelem

@pytest.mark.parametrize("b,sz", [(0, "0 bájt"), (1500, "1.5 KB"),
                                  (5 << 20, "5.0 MB"), (3 << 30, "3.0 GB")])
def test_a_meret_olvashato(b, sz):
    assert C.meret_szoveg(b) == sz


@pytest.mark.parametrize("mp,sz", [(0, ""), (59, "0:59"), (75, "1:15"),
                                   (3600, "60:00")])
def test_az_idotartam_olvashato(mp, sz):
    assert C.ido_szoveg(mp) == sz


# --------------------------------------------------------- protokoll-alap

def test_az_afc_utvonal_mindig_perjellel_es_lezarva():
    assert A.Afc._ut("DCIM/x.jpg") == b"/DCIM/x.jpg\x00"
    assert A.Afc._ut("/DCIM") == b"/DCIM\x00"


def test_a_hianyzo_szolgaltatas_beszedes_hibat_ad(monkeypatch):
    """Ha nincs telepítve az Apple Devices, a felhasználó ne egy nyers
    hálózati hibát kapjon, hanem azt, hogy MIT tegyen."""
    def nincs(*a, **k):
        raise OSError("nincs kapcsolat")
    monkeypatch.setattr(A.socket, "create_connection", nincs)
    with pytest.raises(A.NincsSzolgaltatas) as hiba:
        A.keszulekek()
    assert "Apple Devices" in str(hiba.value)


# ------------------------------------------------- párhuzamosság (regresszió)

class KamuSocket:
    """Egy „vonal”, ami NAPLÓZZA, ki mikor küld és ki mikor olvas.

    Így kiderül, ha két szál egymásba lóg – az élő telefonnál pontosan ez
    történt: a három lapfül egyszerre kezdett tölteni, a kérések összeakadtak,
    és a TLS „wrong version number” hibával állt meg.
    """

    def __init__(self):
        self.naplo = []
        self.valasz = bytearray()
        self._belso = __import__("threading").Lock()

    def sendall(self, adat):
        import time
        azon = __import__("threading").current_thread().name
        self.naplo.append(("küld", azon))
        time.sleep(0.002)                      # hogy legyen esély összeakadni
        with self._belso:
            # OK-státusz válasz: fejléc + 8 bájt nulla hibakód
            fej = A._AFC_FEJ.pack(A._AFC_MAGIC, A._AFC_FEJ.size + 8,
                                  A._AFC_FEJ.size + 8, 0, A.OP_STATUS)
            self.valasz += fej + b"\x00" * 8

    def recv(self, n):
        import time
        azon = __import__("threading").current_thread().name
        self.naplo.append(("olvas", azon))
        time.sleep(0.002)
        with self._belso:
            d = bytes(self.valasz[:n])
            del self.valasz[:n]
        return d

    def close(self):
        pass


def test_a_keresek_nem_lognak_egymasba_tobb_szalon():
    """Egy kapcsolat, több szál: minden kérdés-felelet párnak oszthatatlannak
    kell lennie. Ha nem az, a telefonnal való kommunikáció összeomlik."""
    import threading
    s = KamuSocket()
    afc = A.Afc(s)
    szalak = [threading.Thread(target=afc.torol, args=("/proba%d" % i,),
                               name="szal%d" % i) for i in range(6)]
    for t in szalak:
        t.start()
    for t in szalak:
        t.join()

    # Egy szál eseményeinek EGYBEFÜGGŐNEK kell lenniük a naplóban. Ha a
    # naplóból összevont „futamok” száma több, mint ahány szál van, akkor
    # valaki közbevágott egy másik köre közben.
    futamok = []
    for _muvelet, ki in s.naplo:
        if not futamok or futamok[-1] != ki:
            futamok.append(ki)
    assert len(futamok) == len(szalak), (
        "a szálak egymásba lógtak – a futamok: %s" % futamok)
    assert len(set(futamok)) == len(szalak), "mindegyik szál lefutott"
    assert len(s.naplo) > len(szalak), "tényleg volt küldés és olvasás is"


def test_a_mentes_megszakithato(telefon, tmp_path):
    """A felhasználónak bármikor le kell tudnia állítani egy hosszú mentést –
    691 szám vagy egy 800 MB-os videó közben ez nem luxus."""
    cel = tmp_path / "megszakitva"
    ok, hibak = telefon.zene_ment(telefon.zenek(), str(cel),
                                  megszakit=lambda: True)
    assert ok == 0, "azonnali megszakításnál egy fájl sem készül el"
    assert hibak == [], "a megszakítás nem HIBA, nem is kell jelenteni"


def test_a_megszakitas_a_mar_kesz_fajlokat_megtartja(telefon, tmp_path):
    """Aki félúton áll le, ne veszítse el azt, ami már megvan."""
    allapot = {"db": 0}

    def stop():
        allapot["db"] += 1
        return allapot["db"] > 2          # a második fájl után állj le

    cel = tmp_path / "felig"
    ok, _hibak = telefon.zene_ment(telefon.zenek(), str(cel), megszakit=stop)
    assert ok == 2
    assert len(list(cel.rglob("*.mp3"))) == 2
