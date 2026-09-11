# -*- coding: utf-8 -*-
"""EGY figyelő szál az összes torrentre (4.6.6).

Eddig minden torrent SAJÁT szála kérdezte a motort, másodpercenként, közös
záron át. szakember83-nál (2026-09-10) öt torrent halt meg egy percen belül —
a letöltésekkel semmi baj nem volt, csak nem tudtuk megkérdezni őket.

⚠️ **Ez nem a gyökérok javítása.** Megmértem: a régi felépítés hat torrenttel
egyetlen hibát sem produkált. Amit ad, az szerkezeti tartalék — egy torrent
baja ne vihesse el a többit, bármi is okozza.

Amit ezek a tesztek védenek, és mind NÉMÁN tudna elromlani:

1. a `gid` benne van a lekérdezett mezőkben (enélkül a figyelő üres marad);
2. egy kör MINDEN torrentet felvesz, három hívásból;
3. a kiszolgált állapot mellé MINDIG jár a kora — elavultat sosem adunk
   frissként;
4. a motor némasága nem állítja le a figyelőt;
5. a befejezett torrentet elengedjük (különben örökké kérdeznénk).
"""

import time

import pytest

from superdl import torrent
from superdl.torrent import Figyelo, TorrentDownloader


# ---- 1. a gid nélkül az egész működésképtelen --------------------------

def test_a_gid_benne_van_a_kert_mezokben():
    """⚠️ A `tellActive`/`tellWaiting` CSAK a kért mezőket adja vissza. A
    `gid` nélkül a figyelő nem tudná, melyik állapot melyik torrenté — és
    NÉMÁN üres maradna: a program minden torrentre „nem tudom" állapotba
    kerülne, holott a motor szépen felel."""
    assert "gid" in TorrentDownloader.KEYS
    assert TorrentDownloader.KEYS[0] == "gid"


# ---- 2. egy kör, minden torrent ----------------------------------------

class _Kliens:
    """Motor-utánzat: három listát ad vissza, és számolja a hívásokat."""

    def __init__(self, aktiv=(), varo=(), leallt=(), hiba=None):
        self.aktiv, self.varo, self.leallt = aktiv, varo, leallt
        self.hiba = hiba
        self.hivasok = []

    def call(self, method, *params):
        self.hivasok.append(method)
        if self.hiba:
            raise RuntimeError(self.hiba)
        return {"aria2.tellActive": list(self.aktiv),
                "aria2.tellWaiting": list(self.varo),
                "aria2.tellStopped": list(self.leallt)}[method]


@pytest.fixture
def fig(monkeypatch):
    """Figyelő ELINDÍTOTT szál nélkül: a kört kézzel hívjuk, hogy a teszt
    determinisztikus legyen (időzítésre alapozott teszt hamis zöldet ad)."""
    monkeypatch.setattr(Figyelo, "__init__", _csendes_init)
    f = Figyelo()
    yield f


def _csendes_init(self):
    import threading
    self._lock = threading.Lock()
    self._gidek = set()
    self._adat = {}
    self._mikor = {}
    self._allj = threading.Event()
    self.utolso_siker = time.monotonic()
    self.utolso_hiba = ""


def _allit(monkeypatch, kliens):
    monkeypatch.setattr(torrent.Aria2Client, "get",
                        classmethod(lambda cls: kliens))


def test_egy_kor_minden_torrentet_felvesz(fig, monkeypatch):
    k = _Kliens(aktiv=[{"gid": "a", "status": "active"}],
                varo=[{"gid": "b", "status": "waiting"}],
                leallt=[{"gid": "c", "status": "complete"}])
    _allit(monkeypatch, k)
    fig._egy_kor()
    for g in ("a", "b", "c"):
        st, kor = fig.allapot(g)
        assert st is not None, g
        assert kor < 1.0


def test_harom_hivas_torrentszamtol_fuggetlenul(fig, monkeypatch):
    """EZ A LÉNYEG: tíz torrentnél is három hívás, nem tíz."""
    sok = [{"gid": "g%d" % i, "status": "active"} for i in range(10)]
    k = _Kliens(aktiv=sok)
    _allit(monkeypatch, k)
    fig._egy_kor()
    assert len(k.hivasok) == 3
    assert len(fig._adat) == 10


# ---- 3. az elavult adat SOHA nem friss ---------------------------------

def test_az_allapot_melle_mindig_jar_a_kora(fig, monkeypatch):
    """⚠️ Enélkül a program magabiztosan mutatná az utolsó ismert sebességet,
    miközben percek óta nem tud semmit. Ez a „fut, de halott" tükörképe."""
    _allit(monkeypatch, _Kliens(aktiv=[{"gid": "a", "status": "active"}]))
    fig._egy_kor()
    with fig._lock:
        fig._mikor["a"] = time.monotonic() - 42.0      # öregítjük
    st, kor = fig.allapot("a")
    assert st is not None
    assert kor >= 42.0


def test_az_ismeretlen_gid_nem_ad_hamis_adatot(fig):
    st, kor = fig.allapot("nincsilyen")
    assert st is None


def test_a_frissesseg_hatar_ertelmes():
    """A figyelő másodpercenként kérdez; tíz másodperc után már baj van.
    Ha ez túl nagyra nőne, elavult adatot mutatnánk frissként."""
    assert 2.0 <= TorrentDownloader.FRISSESSEG_MP <= 30.0
    assert TorrentDownloader.FRISSESSEG_MP < TorrentDownloader.VEZERLES_TURES_MP


# ---- 4. a némaság nem állítja le a figyelőt ----------------------------

def test_a_motor_nemasaga_nem_dobja_el_a_regi_adatot(fig, monkeypatch):
    """A régi adat megmarad (a kora árulkodik), a figyelő pedig megy tovább —
    a türelmet a letöltők végzik, mert ők tudják, mikor lesz baj belőle."""
    _allit(monkeypatch, _Kliens(aktiv=[{"gid": "a", "status": "active"}]))
    fig._egy_kor()
    _allit(monkeypatch, _Kliens(hiba="Read timed out"))
    with pytest.raises(RuntimeError):
        fig._egy_kor()
    st, _ = fig.allapot("a")
    assert st is not None          # NEM dobtuk el


def test_a_hiba_szovege_megmarad_a_jelenteshez(fig, monkeypatch):
    _allit(monkeypatch, _Kliens(hiba="Read timed out"))
    try:
        fig._egy_kor()
    except RuntimeError:
        pass
    fig.utolso_hiba = "Read timed out"      # a szál teszi, itt kézzel
    assert "timed out" in fig.utolso_hiba


# ---- 5. a leiratkozás ---------------------------------------------------

def test_az_elengedes_kiveszi_a_gidet(fig, monkeypatch):
    _allit(monkeypatch, _Kliens(aktiv=[{"gid": "a", "status": "active"}]))
    fig.regisztral("a")
    fig._egy_kor()
    assert fig.allapot("a")[0] is not None
    fig.elenged("a")
    assert fig.allapot("a")[0] is None
    with fig._lock:
        assert "a" not in fig._gidek


def test_az_ures_gid_nem_kerul_be(fig):
    fig.regisztral("")
    fig.regisztral(None)
    with fig._lock:
        assert not fig._gidek
