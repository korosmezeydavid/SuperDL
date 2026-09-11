# -*- coding: utf-8 -*-
"""„Mi a fene történik ott a háttérben?" — Dávid kérdése, 2026-09-10.

A válasz az volt, hogy SEMMI: a `logging`-hoz egyetlen kezelő sem tartozott,
tehát minden `_log.exception(...)` a semmibe íródott — köztük az is, amelyik
a letöltés elhasalásakor fut. A hibajelentés nem azért volt hiányos, mert nem
küldtük el a naplót, hanem mert nem is készült.

Ezek a tesztek négy dolgot védenek, és mind a négy NÉMÁN tudna elromlani —
ami itt különösen veszélyes, mert egy néma naplózás pontosan úgy néz ki,
mint egy működő:

1. a napló tényleg FÁJLBA ír, és a `superdl` logger üzenetei odaérnek;
2. az ELKAPATLAN kivétel is bekerül — a háttérszálaké is;
3. a diagnosztikai jelentés tartalmazza a LETÖLTÉSI SORT és a hibaokokat;
4. a maszkolás ezek után is működik (a napló nem szivárogtathat titkot).
"""

import logging
import sys
import threading

import pytest

from superdl import diagnostics, naplo
from superdl.manager import Job


@pytest.fixture
def naplo_fajl(tmp_path, monkeypatch):
    """Külön naplófájl a teszthez, és a globális állapot visszaállítása.

    ⚠️ A `bekapcsol()` a GYÖKÉR loggerre tesz kezelőt: ha nem szedjük le,
    az összes többi teszt is ebbe a fájlba írna, és a pytest kimenete
    kiszámíthatatlanná válna."""
    ut = tmp_path / "naplo.txt"
    monkeypatch.setattr(naplo, "FAJL", ut)
    monkeypatch.setattr(naplo, "_bekapcsolva", False)
    gyoker = logging.getLogger()
    regi_kezelok = list(gyoker.handlers)
    regi_szint = gyoker.level
    regi_sys = sys.excepthook
    regi_szal = threading.excepthook
    yield ut
    for h in list(gyoker.handlers):
        if h not in regi_kezelok:
            gyoker.removeHandler(h)
            h.close()
    gyoker.setLevel(regi_szint)
    sys.excepthook = regi_sys
    threading.excepthook = regi_szal
    naplo._bekapcsolva = False


# ---- 1. a napló tényleg ír ---------------------------------------------

def test_a_naplo_letrejon_es_ir(naplo_fajl):
    assert naplo.bekapcsol() is True
    naplo.jegyez("proba-bejegyzes-42")
    szoveg = naplo_fajl.read_text(encoding="utf-8")
    assert "proba-bejegyzes-42" in szoveg
    # a fejléc is ott van: enélkül nem lehet megmondani, melyik munkamenet
    assert "SuperDL" in szoveg and "indult" in szoveg


def test_a_letoltokezelo_hibai_is_odaernek(naplo_fajl):
    """EZ a lényeg. A `manager._run_job` a `superdl` névtér alatt naplóz;
    ha ez elromlik, a hibák megint a semmibe mennek — és semmi nem jelzi."""
    naplo.bekapcsol()
    logging.getLogger("superdl.manager").error("teszt-hiba a kezelobol")
    logging.getLogger("superdl.torrent").error("aria2 hiba: valami")
    szoveg = naplo_fajl.read_text(encoding="utf-8")
    assert "teszt-hiba a kezelobol" in szoveg
    assert "aria2 hiba: valami" in szoveg


def test_a_ketszeri_bekapcsolas_nem_duplaz(naplo_fajl):
    """Két kezelő mindent kétszer írna le, és a napló feleannyi időt fogna
    át — észrevétlenül."""
    naplo.bekapcsol()
    naplo.bekapcsol()
    naplo.jegyez("egyszer-latszodjon")
    szoveg = naplo_fajl.read_text(encoding="utf-8")
    assert szoveg.count("egyszer-latszodjon") == 1


# ---- 2. az elkapatlan kivétel is bekerül --------------------------------

@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_a_hatterszal_elkapatlan_kivetele_is_a_naploba_kerul(naplo_fajl):
    """⚠️ A `sys.excepthook` CSAK a fő szálra vonatkozik. A letöltéseink
    mind háttérszálon futnak, tehát enélkül pont az a hiba maradna néma,
    amiért az egészet csináljuk."""
    naplo.bekapcsol()

    def robban():
        raise ValueError("hatterszal-robbanas-777")

    t = threading.Thread(target=robban, name="teszt-szal")
    t.start()
    t.join()
    szoveg = naplo_fajl.read_text(encoding="utf-8")
    assert "hatterszal-robbanas-777" in szoveg
    assert "ELKAPATLAN" in szoveg
    assert "Traceback" in szoveg          # a teljes verem is, nem csak a szöveg


# ---- 3. a jelentés végre szól a letöltésekről ---------------------------

class _Kezelo:
    def __init__(self, jobs):
        self.jobs = jobs


def test_a_jelentes_tartalmazza_a_sort_es_a_hibaokot():
    """Eddig a jelentésben EGYETLEN SZÓ sem volt a letöltésekről. A
    felhasználó elküldte, mi meg megtudtuk belőle a wxPython verzióját."""
    j = Job(url="film.torrent", kind="torrent")
    j.progress.filename = "A.film.2024.mkv"
    j.progress.status = "hiba"
    j.progress.error = "InfoHash 802c2378 is already registered."
    j.hibat_rogzit("InfoHash 802c2378 is already registered.")
    r = diagnostics.build_report(settings={}, manager=_Kezelo([j]))
    assert "Letöltési sor:" in r
    assert "A.film.2024.mkv" in r
    assert "InfoHash 802c2378" in r       # a NYERS ok, nem a fordítás
    assert "Torrent-motor:" in r


def test_a_korabbi_hiba_idoponttal_szerepel():
    """Ez az, ami TÚLÉLI a program bezárását: a felhasználó másnap is el
    tudja küldeni azt, ami tegnap történt."""
    j = Job(url="film.torrent", kind="torrent")
    j.progress.status = "letöltés"
    j.hibat_rogzit("valami regi baj")
    r = diagnostics.build_report(settings={}, manager=_Kezelo([j]))
    assert "korábbi hiba" in r
    assert "valami regi baj" in r


def test_a_jelentes_kezeli_ha_nincs_kezelo_vagy_ures_a_sor():
    """Egy hibajelentés összeállítása nem hasalhat el azon, amiről jelentést
    írna — és a „nincs adat" is válasz, nem üresen hagyott hely."""
    r = diagnostics.build_report(settings={}, manager=None)
    assert "Letöltési sor:" in r
    assert "nem érhető el" in r
    r2 = diagnostics.build_report(settings={}, manager=_Kezelo([]))
    assert "a sor üres" in r2


def test_a_motor_szakasz_akkor_is_van_ha_nem_fut():
    """Ha a motor nem fut, az is válasz — sőt, épp az a válasz."""
    r = diagnostics.build_report(settings={}, manager=None)
    assert "Torrent-motor:" in r
    assert "fut:" in r


# ---- 4. a maszkolás a napló után is működik -----------------------------

def test_a_naplo_nem_szivarogtathat_titkot(naplo_fajl, monkeypatch):
    """A napló bekerül a jelentésbe, tehát a maszkolásnak ŐRÁ IS vonatkoznia
    kell. Enélkül a javítás, ami a hibakeresést segíti, titkot küldene ki."""
    naplo.bekapcsol()
    titok = "sk-titkos-kulcs-1234567890"
    naplo.jegyez("a hiba szovege: %s", titok)

    class _Store:
        @staticmethod
        def load_ai_config():
            return {"key": titok}

        @staticmethod
        def load_tts_keys():
            return {}

    monkeypatch.setattr(diagnostics, "store", _Store, raising=False)
    import superdl.store as valodi
    monkeypatch.setattr(valodi, "load_ai_config", _Store.load_ai_config)
    monkeypatch.setattr(valodi, "load_tts_keys", _Store.load_tts_keys)
    r = diagnostics.build_report(settings={}, manager=None)
    assert titok not in r
    assert "KULCS-MASZKOLVA" in r


# ---- 5. összeomlás után SZÓLUNK, de csak egyszer ------------------------

@pytest.fixture
def omlas(tmp_path, monkeypatch):
    """Külön összeomlás-napló és jelölő a teszthez."""
    from superdl import osszeomlas
    monkeypatch.setattr(osszeomlas, "NAPLO", tmp_path / "osszeomlas.log")
    monkeypatch.setattr(osszeomlas, "_OLVASVA", tmp_path / "olvasva.txt")
    monkeypatch.setattr(osszeomlas, "_uj_resz", "")
    monkeypatch.setattr(osszeomlas, "_fajl", None)
    return osszeomlas


NYOM = ("Windows fatal exception: code 0x8001010d\n"
        "Current thread 0x00002cfc (most recent call first):\n"
        '  File "wx\\core.py", line 2254 in MainLoop\n')


def _volt_mar_indulas(omlas):
    """Egy korábbi indulás szimulálása: a jelölő a napló végére kerül.

    ⚠️ 4.6.5 óta EZ KELL az összeomlás-tesztekhez. A frissítés utáni ELSŐ
    indulásnál ugyanis SZÁNDÉKOSAN nem riasztunk (szakember83 jelentése):
    jelölő híján az egész eddigi napló újnak látszana, és hetekkel korábbi
    összeomlásokra állítanánk, hogy „legutóbb" történtek."""
    omlas.NAPLO.parent.mkdir(parents=True, exist_ok=True)
    if not omlas.NAPLO.exists():
        omlas.NAPLO.write_text("", encoding="utf-8")
    omlas._olvasatlan_beolvas()


def _omlast_ir(omlas, szoveg):
    with open(omlas.NAPLO, "a", encoding="utf-8") as f:
        f.write(szoveg)
    omlas._olvasatlan_beolvas()


def test_az_uj_osszeomlast_eszrevesszuk(omlas):
    _volt_mar_indulas(omlas)
    _omlast_ir(omlas, "=== SuperDL indult ===\n" + NYOM)
    assert omlas.uj_osszeomlas() is True


def test_ugyanARRA_masodszor_MAR_NEM_szolunk(omlas):
    """⚠️ Ez a teszt védi meg a funkciót önmagától. Egy figyelmeztetés, ami
    minden induláskor megszólal ugyanarra a régi esetre, pontosan annyit ér,
    mint a néma program – a felhasználó egy hét alatt megtanulja elengedni."""
    _volt_mar_indulas(omlas)
    _omlast_ir(omlas, "=== SuperDL indult ===\n" + NYOM)
    assert omlas.uj_osszeomlas() is True
    # következő indulás: a napló nem változott
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False


def test_az_UJABB_osszeomlasra_megint_szolunk(omlas):
    _volt_mar_indulas(omlas)
    _omlast_ir(omlas, "=== SuperDL indult ===\n" + NYOM)
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False
    # új összeomlás kerül a napló végére
    _omlast_ir(omlas, "\n=== SuperDL indult ===\n" + NYOM)
    assert omlas.uj_osszeomlas() is True


def test_a_sima_indulas_nem_osszeomlas(omlas):
    """A saját „SuperDL indult" sorunk nem újdonság. Ha ez riasztana, minden
    második indulás hamis riasztás lenne."""
    omlas.NAPLO.parent.mkdir(parents=True, exist_ok=True)
    omlas.NAPLO.write_text("=== SuperDL indult: 2026-09-10 ===\n",
                           encoding="utf-8")
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False


def test_a_torolt_naplo_nem_riaszt_de_utana_megint_figyelunk(omlas):
    """⚠️ EZ A TESZT 4.6.5-BEN MEGFORDULT, és ez tudatos döntés.

    Korábban a zsugorodott naplónál nulláztuk a jelölőt, tehát a maradék
    tartalmat újnak vettük — vagyis a napló TÖRLÉSE riasztást váltott ki.
    A törölt napló azonban nem összeomlás. Most csak a jelölőt igazítjuk a
    végéhez: nem riasztunk, de a KÖVETKEZŐ igazi összeomlást észrevesszük —
    tehát nem is némulunk el örökre, ami az eredeti félelem volt."""
    omlas.NAPLO.parent.mkdir(parents=True, exist_ok=True)
    omlas.NAPLO.write_text("x" * 5000, encoding="utf-8")
    omlas._olvasatlan_beolvas()
    omlas.NAPLO.write_text(NYOM, encoding="utf-8")     # rövidebb lett
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False
    _omlast_ir(omlas, NYOM)                            # egy IGAZI, új omlás
    assert omlas.uj_osszeomlas() is True


def test_a_hianyzo_naplo_nem_okoz_hibat(omlas):
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is False
