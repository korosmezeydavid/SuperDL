# -*- coding: utf-8 -*-
"""MK5 – a kimondott állapot: összefoglaló, emberi idő és méret.

A `report.py`-t eddig EGYETLEN teszt sem védte, pedig ez a modul gyártja azt a
mondatot, amit a vak felhasználó a leggyakrabban hall. Ezek a tesztek nem a
szövegek pontos betűit rögzítik (az béklyó lenne), hanem azt, amit KI KELL
mondani, és amit NEM szabad.
"""

from superdl import report


class _P:
    def __init__(self, status="letöltés", total=0, downloaded=0, speed=0.0,
                 filename=""):
        self.status = status
        self.total = total
        self.downloaded = downloaded
        self.speed = speed
        self.filename = filename


class _J:
    def __init__(self, p, url="http://p/x"):
        self.progress = p
        self.url = url


def _job(**kw):
    return _J(_P(**kw))


# ---- a kimondott méret és idő ----------------------------------------

def test_mondott_meret_nem_tartalmaz_tizedespontot():
    """A felolvasó a tizedespontot MONDATVÉGI PONTNAK mondja: „öt pont három
    megabájt" helyett „öt. Három megabájt". Ezért kell a vessző."""
    sz = report.mondott_meret(int(5.3 * 1024 ** 2))
    assert "," in sz and "." not in sz
    assert "megabájt" in sz


def test_human_bytes_a_szemnek_marad_rovid():
    """A lista oszlopába a rövid alak való – ezt NEM alakítjuk át."""
    assert report.human_bytes(5 * 1024 ** 2).endswith("MB")


def test_human_time_a_kozos_szokincset_hasznalja():
    """MK5: az újrapróba „negyed órát" mond; az összefoglaló nem mondhat
    „körülbelül 15 percet" ugyanarra."""
    assert "negyed óra" in report.human_time(15 * 60)
    assert "fél óra" in report.human_time(30 * 60)


def test_human_time_egy_perc_alatt():
    assert report.human_time(10) == "kevesebb mint egy perc"


# ---- az összefoglaló --------------------------------------------------

def test_ures_sor():
    assert report.build_summary([]) == "Nincs aktív letöltés."


def test_csak_kesz_es_hiba():
    sz = report.build_summary([_job(status="kész"), _job(status="hiba")])
    assert "Nincs aktív letöltés." in sz
    assert "1 letöltés elkészült." in sz
    assert "1 hibára futott." in sz


def test_futo_letoltes_szazalekot_es_sebesseget_mond():
    j = _job(total=1000, downloaded=420, speed=100.0)
    sz = report.build_summary([j])
    assert "1 letöltés fut" in sz
    assert "42 százalék" in sz
    assert "másodpercenként" in sz


def test_az_osszefoglaloban_sincs_tizedespont_a_sebessegnel():
    """Ugyanaz a csapda, mint a méretnél – csak itt a mondat KÖZEPÉN."""
    j = _job(total=10 ** 8, downloaded=1, speed=5.3 * 1024 ** 2)
    sz = report.build_summary([j])
    # a mondatvégi pontokat leszámítva ne legyen tizedespont
    assert "5.3" not in sz
    assert "5,3 megabájt" in sz


# ---- a leglassabb elem ------------------------------------------------

def test_leglassabb_egyetlen_letoltesnel_hallgat():
    """Egy letöltésnél a „leglassabb" mondat üresen járna, és a fölösleges
    szöveg vakon fárasztó."""
    assert report.leglassabb([_job(total=1000, downloaded=0, speed=10.0)]) is None


def test_leglassabb_a_kesobb_vegzot_valasztja():
    gyors = _job(total=100, downloaded=90, speed=10.0, filename="gyors.mp4")
    lassu = _job(total=10000, downloaded=0, speed=1.0, filename="lassu.mkv")
    nev, hatra = report.leglassabb([gyors, lassu])
    assert nev == "lassu.mkv"
    assert hatra > 1000


def test_leglassabb_kimarad_az_osszefoglalobol_ha_nincs_ertelme():
    sz = report.build_summary([_job(total=1000, downloaded=0, speed=10.0)])
    assert "leglassabb" not in sz


def test_leglassabb_bekerul_ha_tobb_fut():
    """Az EGYÜTTES hátralévő idő félrevezet: ha kettőből az egyik egy perc
    múlva végez, a másik egy óra múlva, az átlagból a felhasználó rosszul
    tervez – és vakon nem tudja szemmel végigfutni a listát."""
    gyors = _job(total=100, downloaded=90, speed=10.0, filename="gyors.mp4")
    lassu = _job(total=100000, downloaded=0, speed=10.0, filename="lassu.mkv")
    sz = report.build_summary([gyors, lassu])
    assert "leglassabb" in sz and "lassu.mkv" in sz


def test_leglassabb_nem_szamol_ismeretlen_merettel():
    a = _job(total=0, downloaded=50, speed=10.0, filename="ismeretlen.bin")
    b = _job(total=1000, downloaded=0, speed=10.0, filename="ismert.bin")
    assert report.leglassabb([a, b]) is None


# ---- a befejezés bemondása -------------------------------------------

def test_befejezes_mondja_a_meretet():
    """MK5: vakon a méret az EGYETLEN visszajelzés arról, hogy a várt fájl
    jött-e le, és nem egy néhány kilobájtos hibaoldal."""
    sz = report.befejezes_mondat("film.mkv", 3 * 1024 ** 3)
    assert "film.mkv" in sz
    assert "gigabájt" in sz


def test_befejezes_meret_nelkul_is_ep_mondat():
    sz = report.befejezes_mondat("film.mkv")
    assert sz == "Elkészült: film.mkv."


def test_befejezes_ures_nev_nem_szall_el():
    assert "a fájl" in report.befejezes_mondat("")


# ---- a seedelés saját hangja -----------------------------------------

def test_a_seedelesnek_sajat_earconja_van():
    """MK5: eddig a készre töltött torrent ugyanazt a „done" hangot szólaltatta
    meg, mint a lezárult letöltés – pedig az egyik VÉGET ért, a másik még fut
    és sávszélességet használ. Vakon a hang az egyetlen különbség."""
    from superdl import sounds
    assert "seed" in sounds.EARCONS
    assert sounds.EARCONS["seed"] != sounds.EARCONS["done"]


def test_a_seed_hang_nem_lezaro_felfuto():
    """A „done" felfut (lezárás). A seedelésé szándékosan visszatér a kiinduló
    hangra: nyitva hagyott, nem befejezett."""
    from superdl import sounds
    seed = [f for f, _ in sounds.EARCONS["seed"]]
    done = [f for f, _ in sounds.EARCONS["done"]]
    assert done[-1] > done[0], "a done felfutó"
    assert seed[-1] == seed[0], "a seed visszatér, nem zár le"
