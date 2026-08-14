"""Internet-teszt: a mérőmotor őrei.

Egy felhasználói ötletből született funkció: egy gombnyomásra derüljön ki az
internet MINDEN fontos paramétere – sebesség, késleltetés, IP, wifi –, és az,
hogy MIRE ELÉG. A tesztek EGYETLEN valódi hálózati kérést sem küldenek: minden
hálózati réteg helyettesítve van (a CI-ban sincs kiszámítható net).

Amit külön őrzünk, mert élesben ezek buktak volna el:
  • a fix bájtcélos mérés helyett IDŐALAPÚ mérés, mediánnal (a mérő-végpont
    élesben visszafogta a nagy adagot, és a sebesség töredékét mutatta);
  • a bemelegítés (TCP lassú indítás) kihagyása;
  • az akadozó vonal FELISMERÉSE (csúcs a medián többszöröse);
  • a publikus IP MASZKOLÁSA alapból;
  • a mérő-forrás átváltása, ha az első nem ad adatot.
"""

import json
import threading
import time

import pytest

from superdl import nettest as N


# ------------------------------------------------------------ maszkolás

def test_ip_maszkolas():
    assert N.maszkol_ip("176.63.11.10") == "176.63.xxx.xxx"
    assert N.maszkol_ip("") == ""
    assert N.maszkol_ip("2001:db8:1234::1").startswith("2001:db8:")
    assert "1234" not in N.maszkol_ip("2001:db8:1234::1")


def test_a_jelentes_alapbol_maszkol():
    e = N.Eredmeny(mod="gyors")
    e.publikus.ip = "176.63.11.10"
    szoveg = N.jelentes(e)
    assert "176.63.11.10" not in szoveg, "a teljes IP nem kerülhet bele kérés nélkül"
    assert "176.63.xxx.xxx" in szoveg
    assert "176.63.11.10" in N.jelentes(e, teljes_ip=True)


# ------------------------------------------------------- számolás, szöveg

def test_mbps_es_idoszamitas():
    assert N._mbps(1_000_000, 8.0) == 1.0          # 1 MB 8 mp alatt = 1 Mbit/s
    assert N._mbps(0, 0) == 0.0
    assert N.ido_szoveg(30) == "30 másodperc"
    assert N.ido_szoveg(90) == "1 perc 30 másodperc"
    assert "óra" in N.ido_szoveg(7000)
    assert N.egy_giga_ideje(0) == "nem mérhető"
    # 100 Mbit/s → 1 GB ≈ 82 másodperc
    assert "perc" in N.egy_giga_ideje(100)


def test_szamlalo_kihagyja_a_bemelegitest(monkeypatch):
    """A TCP lassú indítás miatt az első szakasz mindig lassabb – azt nem
    számoljuk bele. Itt: 1 mp „lassú" (1 MB), utána 1 mp gyors (10 MB)."""
    ora = {"t": 100.0}
    monkeypatch.setattr(N.time, "monotonic", lambda: ora["t"])
    sz = N._Szamlalo(bemelegites=1.0)
    sz.hozzaad(1_000_000)             # bemelegítés alatt
    ora["t"] = 101.0
    sz.hozzaad(1)                     # itt zárul a bemelegítés
    ora["t"] = 102.0
    sz.hozzaad(10_000_000)            # a mért szakasz: 10 MB / 1 mp = 80 Mbit/s
    mbps, bajt = sz.eredmeny()
    assert bajt == 11_000_001, "a FORGALOM a teljes átvitel"
    assert 79 < mbps < 81, "a SEBESSÉG csak a bemelegítés utáni szakaszból jön"


def test_szamlalo_rovid_meresnel_a_teljes_szakaszt_szamolja(monkeypatch):
    ora = {"t": 0.0}
    monkeypatch.setattr(N.time, "monotonic", lambda: ora["t"])
    sz = N._Szamlalo(bemelegites=5.0)
    sz.hozzaad(1_000_000)
    ora["t"] = 1.0
    sz.hozzaad(1_000_000)
    mbps, bajt = sz.eredmeny()
    assert bajt == 2_000_000
    assert mbps > 0, "rövid mérésnél is adjon értéket, ne nullát"


def test_ingadozo_vonal_felismerese():
    # tipikus akadozás: 104, 4, 1, 2 → a csúcs a medián sokszorosa
    assert N.ingadozo(3.0, 104.0, [104, 4, 1, 2]) is True
    assert N.ingadozo(40.0, 45.0, [40, 42, 45, 39]) is False
    assert N.ingadozo(0.0, 0.0, []) is False
    assert N.ingadozo(3.0, 104.0, [104, 3]) is False, "kevés mintából ne ítéljünk"


# --------------------------------------------------------- sávszélesség

def _hamis_szal(darab, szamlalo, stop, hibak, hatarido, korlat, url=""):
    """Hálózat helyett: egyenletesen „átvisz" adatot, amíg le nem jár az idő."""
    while time.monotonic() < hatarido and not (stop and stop.is_set()):
        if szamlalo.bajt >= korlat:
            return
        szamlalo.hozzaad(64 * 1024)
        time.sleep(0.01)


def test_savszelesseg_ido_alapu_es_korlatos(monkeypatch):
    monkeypatch.setattr(N, "_le_szal", _hamis_szal)
    t0 = time.monotonic()
    r = N._savszelesseg(False, 1.0, 2, None, [], korlat=10 * N._MB)
    eltelt = time.monotonic() - t0
    assert eltelt < 3.0, "a mérés az IDŐKERETET tartsa"
    assert r.bajt > 0 and r.mbps > 0
    assert r.bajt <= 12 * N._MB, "a bájtkorlátot ne lépje túl érdemben"


def test_savszelesseg_megszakithato(monkeypatch):
    monkeypatch.setattr(N, "_le_szal", _hamis_szal)
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    t0 = time.monotonic()
    N._savszelesseg(False, 10.0, 2, stop, [])
    assert time.monotonic() - t0 < 4.0, "megszakításkor azonnal álljon le"


def test_le_forras_atvalt_ha_az_elso_nem_ad_adatot(monkeypatch):
    """Élesben ez mentett meg: az egyik kiszolgáló fojtotta a klienst, és a
    mérés a valódi sebesség töredékét mutatta volna."""
    hivott = []

    def hamis(darab, szamlalo, stop, hibak, hatarido, korlat, url=""):
        hivott.append(url)
        if "elso" in url:
            return                       # néma kiszolgáló: nulla bájt
        szamlalo.hozzaad(2 * 1024 * 1024)

    monkeypatch.setattr(N, "_le_szal", hamis)
    monkeypatch.setattr(N, "LE_FORRASOK", ("https://elso.example/x",
                                           "https://masodik.example/y"))
    forras = N._le_forras(None, [])
    assert forras == "https://masodik.example/y"
    assert hivott[0] == "https://elso.example/x", "az elsőt is meg kell próbálni"


def test_le_forras_sajat_url_elsobbseget_kap(monkeypatch):
    monkeypatch.setattr(N, "_le_szal",
                        lambda *a, **kw: a[1].hozzaad(2 * 1024 * 1024))
    assert N._le_forras(None, [], sajat="https://sajat.example/f") \
        == "https://sajat.example/f"


# ------------------------------------------------------------ minősítés

def test_minosites_a_superdl_funkcioihoz_kotve():
    lassu = N.Sebesseg(le_mbps=0.6, fel_mbps=0.2, keses_atlag_ms=30)
    d = dict((nev, ok) for nev, ok, _ in N.minositesek(lassu))
    assert d["Zenehallgatás, internetes rádió"] is True
    assert d["Videónézés 4K-ban"] is False
    assert d["Élő multistream (Super Stream)"] is False

    gyors = N.Sebesseg(le_mbps=300, fel_mbps=100, keses_atlag_ms=12)
    assert all(ok for _, ok, _ in N.minositesek(gyors))

    # nagy sávszélesség, de nagy késleltetés (pl. műholdas net)
    lassu_valasz = N.Sebesseg(le_mbps=300, fel_mbps=100, keses_atlag_ms=600)
    d2 = dict((nev, ok) for nev, ok, _ in N.minositesek(lassu_valasz))
    assert d2["Hangkonferencia (Csevejcenter)"] is False
    assert d2["Videónézés 4K-ban"] is True, "a videózást a késleltetés nem rontja"


def test_osszefoglalo_elso_mondata_iteletet_mond():
    e = N.Eredmeny(mod="teljes",
                   sebesseg=N.Sebesseg(le_mbps=312, fel_mbps=42,
                                       keses_atlag_ms=12))
    sz = N.osszefoglalo(e)
    assert sz.startswith("Az interneted"), "elöl az emberi ítélet, ne a számok"
    assert "312" in sz and "42" in sz
    assert "Elég ehhez" in sz


def test_osszefoglalo_jelzi_az_akadozast_es_a_takarekos_modot():
    e = N.Eredmeny(mod="takarekos",
                   sebesseg=N.Sebesseg(le_mbps=3, le_csucs_mbps=104,
                                       le_mintak=[104, 4, 1, 2], fel_mbps=1,
                                       keses_atlag_ms=25))
    sz = N.osszefoglalo(e)
    assert "AKADOZIK" in sz
    assert "TAKARÉKOS" in sz, "a takarékos mérés tájékoztató jellegét ki kell mondani"


def test_osszefoglalo_szol_a_gyenge_wifirol_es_a_vpnrol():
    e = N.Eredmeny(sebesseg=N.Sebesseg(le_mbps=8, fel_mbps=2,
                                       keses_atlag_ms=30))
    e.halozat.kapcsolat = "vezeték nélküli (Wi-Fi)"
    e.halozat.wifi_jel = 35
    e.halozat.vpn = "Proton VPN"
    sz = N.osszefoglalo(e)
    assert "wifi jele gyenge" in sz
    assert "VPN" in sz


def test_osszefoglalo_kulon_kezeli_a_nem_elerheto_szolgaltatast():
    e = N.Eredmeny(sebesseg=N.Sebesseg(le_mbps=100, fel_mbps=50,
                                       keses_atlag_ms=15))
    e.szolgaltatasok = [("Modulok és frissítés (GitHub)", False, 3000.0),
                        ("YouTube (letöltés, keresés)", True, 20.0)]
    sz = N.osszefoglalo(e)
    assert "Nem érhető el" in sz and "GitHub" in sz
    assert "nem az internet sebességének a hibája" in sz


# ------------------------------------------------------------- sorok

def test_minden_sor_onmagaban_ertelmes():
    """A képernyőolvasó SORONKÉNT olvas: nem lehet magában álló „igen"/„nem"."""
    e = N.Eredmeny(sebesseg=N.Sebesseg(le_mbps=50, fel_mbps=10,
                                       keses_atlag_ms=20))
    e.szolgaltatasok = [("YouTube (letöltés, keresés)", True, 20.0)]
    for sor in N.sorok(e):
        assert len(sor) > 3
        if not sor.startswith("—") and not sor.startswith("("):
            assert ":" in sor, "minden adatsorban legyen CÍMKE is: %r" % sor


def test_sorok_jelzik_az_ingadozast_a_mintakkal():
    e = N.Eredmeny(sebesseg=N.Sebesseg(le_mbps=3, le_csucs_mbps=104,
                                       le_mintak=[104, 4, 1, 2]))
    egyben = "\n".join(N.sorok(e))
    assert "erősen ingadozott" in egyben
    assert "104" in egyben, "a másodpercenkénti minták is legyenek ott"


# -------------------------------------------------------------- napló

def test_naplo_ment_es_maszkol(tmp_path, monkeypatch):
    fajl = tmp_path / "naplo.json"
    monkeypatch.setattr(N, "_naplo_fajl", lambda: fajl)
    e = N.Eredmeny(ido="2026-08-14 21:00:00",
                   sebesseg=N.Sebesseg(le_mbps=40, fel_mbps=10,
                                       keses_atlag_ms=20))
    e.publikus.ip = "176.63.11.10"
    N.naplo_ment(e)
    nyers = fajl.read_text(encoding="utf-8")
    assert "176.63.11.10" not in nyers, "a naplóba se kerüljön teljes IP"
    assert json.loads(nyers)[0]["publikus"]["ip"] == "176.63.xxx.xxx"
    assert "40" in N.naplo_sorok()[0]
    assert "átlaga" in N.naplo_atlag()


def test_naplo_nem_no_a_vegtelensegig(tmp_path, monkeypatch):
    fajl = tmp_path / "naplo.json"
    monkeypatch.setattr(N, "_naplo_fajl", lambda: fajl)
    monkeypatch.setattr(N, "_NAPLO_MAX", 5)
    for i in range(9):
        N.naplo_ment(N.Eredmeny(ido="nap-%d" % i))
    d = json.loads(fajl.read_text(encoding="utf-8"))
    assert len(d) == 5 and d[-1]["ido"] == "nap-8"


def test_serult_naplo_nem_dob_hibat(tmp_path, monkeypatch):
    fajl = tmp_path / "naplo.json"
    fajl.write_text("{ez nem json", encoding="utf-8")
    monkeypatch.setattr(N, "_naplo_fajl", lambda: fajl)
    assert N.naplo_betolt() == []
    N.naplo_ment(N.Eredmeny(ido="x"))            # nem dobhat kivételt
    assert len(N.naplo_betolt()) == 1


# ------------------------------------------------------- a teljes mérés

def test_merj_gyors_mod_nem_meri_a_sebesseget(monkeypatch):
    """A „gyors" mód sebességet NEM mér (nincs adatforgalom), de mindent mást
    igen – ez a mobilnetes felhasználó biztonságos választása."""
    monkeypatch.setattr(N, "halozat_adatok", lambda: N.Halozat(helyi_ip="10.0.0.2"))
    monkeypatch.setattr(N, "publikus_adatok", lambda *a, **kw: N.Publikus(ip="1.2.3.4"))
    monkeypatch.setattr(N, "keslekedes", lambda **kw: (10.0, 12.0, 2.0, 100.0))
    monkeypatch.setattr(N, "dns_ido", lambda *a, **kw: 5.0)
    monkeypatch.setattr(N, "szolgaltatas_probak", lambda **kw: [("X", True, 1.0)])
    hivas = []
    monkeypatch.setattr(N, "_savszelesseg",
                        lambda *a, **kw: hivas.append(1) or N.SavEredmeny())
    fazisok = []
    e = N.merj("gyors", halad=lambda f, p: fazisok.append((f, p)))
    assert not hivas, "gyors módban NEM lehet sávszélesség-mérés"
    assert e.sebesseg.keses_atlag_ms == 12.0
    assert e.szolgaltatasok == [("X", True, 1.0)]
    assert fazisok[-1][1] == 100 and [p for _, p in fazisok] == sorted(
        p for _, p in fazisok), "a haladás monoton nőjön"


def test_merj_megszakithato_a_meres_kozben(monkeypatch):
    monkeypatch.setattr(N, "halozat_adatok", lambda: N.Halozat())
    stop = threading.Event()
    stop.set()
    e = N.merj("teljes", stop=stop)
    assert e.megszakitva is True
    assert "megszakítva" in N.osszefoglalo(e)


def test_merj_hibatur_ha_egy_reteg_elszall(monkeypatch):
    """Egy elszálló részfeladat NEM viheti el az egész mérést – a többi adat
    attól még hasznos."""
    def rossz():
        raise OSError("nincs adapter")
    monkeypatch.setattr(N, "halozat_adatok", rossz)
    monkeypatch.setattr(N, "publikus_adatok", lambda *a, **kw: N.Publikus())
    monkeypatch.setattr(N, "keslekedes", lambda **kw: (0.0, 0.0, 0.0, 0.0))
    monkeypatch.setattr(N, "dns_ido", lambda *a, **kw: 0.0)
    monkeypatch.setattr(N, "szolgaltatas_probak", lambda **kw: [])
    e = N.merj("gyors")
    assert any("helyi hálózat" in h for h in e.hibak)
    assert N.osszefoglalo(e), "az összefoglaló ilyenkor is szülessen meg"


# ------------------------------------------------- szolgáltatás-lista

def test_a_wormhole_szerverek_a_csomagbol_jonnek():
    """A P2P-szerverek portját NE találgassuk: rossz porton mérve hamis „NEM
    érhető el" jelenne meg (ez élesben meg is történt a fejlesztés közben)."""
    lista = N.szolgaltatas_lista()
    nevek = [n for n, _, _ in lista]
    assert "P2P kódszerver (wormhole)" in nevek
    for nev, host, port in lista:
        assert host and 1 <= port <= 65535, "%s: érvénytelen végpont" % nev


def test_keslekedes_azonnal_all_ha_megszakitjak():
    stop = threading.Event()
    stop.set()
    assert N.keslekedes(minta=50, stop=stop) == (0.0, 0.0, 0.0, 0.0)


def test_forgalom_becsles_minden_modra():
    for mod in ("teljes", "takarekos", "gyors"):
        assert N.becsult_forgalom(mod)


def test_az_ablak_bemondasa_a_helyes_sorrendben_van():
    """A KÖTELEZŐ sorrend az Internet-teszt ablakban is: ELŐBB a képernyőolvasó,
    UTÁNA a némítás-vizsgálat. Fordítva képernyőolvasó-módban NÉMA maradna,
    mert a Core ilyenkor szándékosan némítja a saját hangját (ez okozta korábban
    a P2P-nél a néma F8-at). A modulokat a tests/test_bemondas_sorrend.py őrzi,
    ezt a MAGBELI ablakot ez a teszt."""
    import pathlib
    forras = (pathlib.Path(__file__).resolve().parent.parent / "superdl"
              / "nettestwin.py").read_text(encoding="utf-8")
    torzs = forras[forras.index("def _mondd"):]
    torzs = torzs[:torzs.index("def _pittyeg")]
    assert torzs.index("_sr") < torzs.index('getattr(sv, "muted"'), \
        "a némítás-vizsgálat MEGELŐZI a képernyőolvasót – így néma maradna"
