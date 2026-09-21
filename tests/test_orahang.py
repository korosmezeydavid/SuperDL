"""A beszélő óra hangrétege: változat-ellenőrzés és a BEMONDÁSI SOR.

A legfontosabb itt az, amit a `selfvoice` szándékosan NEM tud: a bemondások
NEM vágják félbe egymást. Két egyszerre lejáró időzítő mindkét üzenete
elhangzik – ezen áll vagy bukik a párhuzamos időzítés.
"""

import time

import pytest

from superdl import orahang as H


# ───────────────── változat-ellenőrzés (néma visszaesés ellen) ──────

DAVID_KESZLETE = ["robert", "rob", "max", "Michael", "Denis", "Diogo",
                  "michel", "boris", "klatt2",
                  "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8",
                  "f1", "f2", "f3", "f4", "f5"]


def test_a_keszlet_pontosan_a_kijelolt_22_valtozat_plusz_az_alap():
    nevek = [n for n, _ in H.keszlet()]
    assert nevek[0] == ""                       # az alaphang az első
    assert nevek[1:] == DAVID_KESZLETE
    assert len(nevek) == 23


def test_minden_kijelolt_valtozat_tenylegesen_megvan():
    """⚠️ Ha egy név elgépelt, az eSpeak NÉMÁN az alaphangra esne vissza –
    a hiba csak fülre derülne ki. Ezért itt ellenőrizzük."""
    van = H.letezo_valtozatok()
    if not van:
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    hianyzik = [n for n in DAVID_KESZLETE if n.lower() not in van]
    assert hianyzik == []


def test_nem_letezo_valtozat_nem_ervenyes():
    van = H.letezo_valtozatok()
    if not van:
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    assert not H.ervenyes("nincsilyenhang")
    assert H.ervenyes("f2")
    assert H.ervenyes("")                       # alaphang


def test_a_mind_kapcsolo_tobb_hangot_ad():
    van = H.letezo_valtozatok()
    if not van:
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    assert len(H.keszlet(mind=True)) > len(H.keszlet())


def test_a_cimkek_felolvashatoak():
    assert H.cimke("f2") == "Női 2"
    assert H.cimke("boris") == "Boris (férfi)"
    assert H.cimke("") == "eSpeak magyar – alap"
    assert H.cimke("ismeretlen") == "ismeretlen"


# ─────────────────────────── a bemondási SOR ────────────────────────

class Proba(H.Beszelo):
    """Bemondó, ami nem beszél, csak jegyzetel – és IDŐT VESZ IGÉNYBE,
    mint a valódi eSpeak (egy bemondás ~2,5 mp; itt 0,15 mp)."""

    HOSSZ = 0.15

    def __init__(self, **kw):
        self.naplo = []
        self.egyszerre = 0
        self.max_egyszerre = 0
        super().__init__(**kw)

    def _egy(self, b):
        self.egyszerre += 1
        self.max_egyszerre = max(self.max_egyszerre, self.egyszerre)
        time.sleep(self.HOSSZ)
        self.naplo.append((b.szoveg, b.valtozat, b.surgos))
        self.egyszerre -= 1


def _megvar(b, db, hatarido=5.0):
    vege = time.monotonic() + hatarido
    while time.monotonic() < vege:
        if len(b.naplo) >= db and b.varakozok == 0:
            return True
        time.sleep(0.02)
    return False


def test_ket_egyidejü_bemondas_mindketto_teljesen_elhangzik():
    """⚠️ EZ A LÉNYEG. A `selfvoice` itt levágná az elsőt."""
    b = Proba()
    try:
        b.mond("munkaidő: letelt az idő.", "m3", surgos=True)
        b.mond("ebédszünet: letelt az idő.", "f2", surgos=True)
        assert _megvar(b, 2)
        assert [sz for sz, _, _ in b.naplo] == [
            "munkaidő: letelt az idő.", "ebédszünet: letelt az idő."]
    finally:
        b.kikapcsol()


def test_egyszerre_mindig_csak_egy_bemondas_szol():
    b = Proba()
    try:
        for i in range(4):
            b.mond("szöveg %d" % i, surgos=True)
        assert _megvar(b, 4)
        assert b.max_egyszerre == 1
    finally:
        b.kikapcsol()


def test_a_sorrend_megmarad():
    b = Proba()
    try:
        for i in range(4):
            b.mond("szöveg %d" % i, surgos=True)
        assert _megvar(b, 4)
        assert [sz for sz, _, _ in b.naplo] == ["szöveg %d" % i
                                                for i in range(4)]
    finally:
        b.kikapcsol()


def test_a_valtozat_bemondasonkent_kulon_megy():
    b = Proba()
    try:
        b.mond("egy", "m3", surgos=True)
        b.mond("kettő", "f2", surgos=True)
        assert _megvar(b, 2)
        assert [v for _, v, _ in b.naplo] == ["m3", "f2"]
    finally:
        b.kikapcsol()


def test_tele_sornal_a_nem_surgos_bemondast_eldobjuk():
    """Öt bemondás ~12 mp beszéd; ennél hosszabb torlódás már nem
    információ, hanem zaj. Az időzítő LEJÁRATA viszont sürgős: bemegy."""
    b = Proba()
    b.HOSSZ = 2.0                     # a szál sokáig elvan az elsővel
    try:
        assert b.mond("első", surgos=True)
        time.sleep(0.1)               # az első már a szálon van, a sor üres
        elfogadott = [b.mond("p%d" % i) for i in range(H.SOR_MAX + 3)]
        assert elfogadott[:H.SOR_MAX] == [True] * H.SOR_MAX
        assert elfogadott[H.SOR_MAX:] == [False] * 3
        assert b.mond("LEJÁRT", surgos=True) is True
    finally:
        b.kikapcsol()


def test_ures_szoveget_nem_mond_be():
    b = Proba()
    try:
        assert b.mond("") is False
        assert b.mond(None) is False
    finally:
        b.kikapcsol()


def test_a_leallitas_uriti_a_sort():
    b = Proba()
    b.HOSSZ = 1.0
    try:
        b.mond("első", surgos=True)
        time.sleep(0.05)
        for i in range(3):
            b.mond("p%d" % i, surgos=True)
        assert b.varakozok == 3
        b.leallit()
        assert b.varakozok == 0
    finally:
        b.kikapcsol()


def test_kikapcsolas_utan_nem_fogad_el_tobbet():
    b = Proba()
    b.kikapcsol()
    assert b.mond("ez már nem megy", surgos=True) is False


# ───────────── néma visszaesés helyett naplózott visszaesés ─────────

def test_ismeretlen_valtozatnal_alaphang_es_figyelmeztetes(monkeypatch,
                                                           caplog):
    """⚠️ Az eSpeak ilyenkor rc=0-t ad és NÉMÁN az alaphangot használja –
    élőben lemérve. Ezért MI naplózunk, hogy a hiba előkerüljön."""
    if not H.letezo_valtozatok():
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    hivasok = []

    class ProcBab:
        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

    def hamis_popen(cmd, **kw):
        hivasok.append(cmd)
        return ProcBab()

    monkeypatch.setattr(H.subprocess, "Popen", hamis_popen)
    b = H.Beszelo()
    try:
        with caplog.at_level("WARNING", logger="superdl.orahang"):
            b.mond("próba", "nincsilyenhang", surgos=True)
            vege = time.monotonic() + 5
            while time.monotonic() < vege and not hivasok:
                time.sleep(0.02)
        assert hivasok, "az eSpeak-et el kellett volna indítani"
        cmd = hivasok[0]
        assert cmd[cmd.index("-v") + 1] == "hu"      # alaphangra esett vissza
        assert any("nincsilyenhang" in r.getMessage()
                   for r in caplog.records)
    finally:
        b.kikapcsol()


def test_letezo_valtozatnal_a_hu_plusz_valtozat_megy(monkeypatch):
    if not H.letezo_valtozatok():
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    hivasok = []

    class ProcBab:
        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr(H.subprocess, "Popen",
                        lambda cmd, **kw: (hivasok.append(cmd), ProcBab())[1])
    b = H.Beszelo()
    try:
        b.mond("próba", "f2", surgos=True)
        vege = time.monotonic() + 5
        while time.monotonic() < vege and not hivasok:
            time.sleep(0.02)
        assert hivasok
        cmd = hivasok[0]
        assert cmd[cmd.index("-v") + 1] == "hu+f2"
    finally:
        b.kikapcsol()
