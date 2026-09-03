# -*- coding: utf-8 -*-
"""MK3 – a célfájl épsége: szabad hely, folytatás, ellenőrző összeg, takarítás.

A tesztek NEM a lemezt mérik: a `szabad()` kicserélhető, így a döntési logika
valódi teli lemez nélkül is végigjárható. Ami valódi fájlt igényel (a
SHA-256 és a takarítás), az a pytest ideiglenes mappájában dolgozik.
"""

import json

import pytest

from superdl import lemezhely
from superdl import segment


# ---- emberi méret -----------------------------------------------------

def test_emberi_meret_tizedesvesszo():
    # a felolvasó a tizedespontot mondatvégi pontnak mondja
    assert "," in lemezhely.emberi_meret(int(4.2 * 1024 ** 3))
    assert "." not in lemezhely.emberi_meret(int(4.2 * 1024 ** 3))


def test_emberi_meret_egysegek():
    assert lemezhely.emberi_meret(0) == "0 bájt"
    assert lemezhely.emberi_meret(512) == "512 bájt"
    assert "kilobájt" in lemezhely.emberi_meret(2048)
    assert "megabájt" in lemezhely.emberi_meret(5 * 1024 ** 2)
    assert "gigabájt" in lemezhely.emberi_meret(5 * 1024 ** 3)


def test_emberi_meret_negativ_nem_szall_el():
    assert lemezhely.emberi_meret(-1) == "0 bájt"


# ---- eleg_hely --------------------------------------------------------

@pytest.fixture
def hely(monkeypatch):
    """Beállítja a „szabad hely" válaszát, és visszakapcsolja az ellenőrzést."""
    monkeypatch.setattr(lemezhely, "BEKAPCSOLVA", True)

    def allit(bajt):
        monkeypatch.setattr(lemezhely, "szabad", lambda ut: bajt)
    return allit


def test_belefer(hely):
    hely(10 * 1024 ** 3)
    fer, sz, hianyzik = lemezhely.eleg_hely("C:/x", 4 * 1024 ** 3)
    assert fer and hianyzik == 0


def test_nem_fer_bele(hely):
    hely(1 * 1024 ** 3)
    fer, sz, hianyzik = lemezhely.eleg_hely("C:/x", 4 * 1024 ** 3)
    assert not fer
    assert hianyzik > 3 * 1024 ** 3


def test_a_tartalek_is_szamit(hely):
    """Pontosan a fájl méretét szabad helyen NEM indítunk: a tartalék a
    program naplóinak és a rendszernek kell."""
    hely(1000)
    fer, _, _ = lemezhely.eleg_hely("C:/x", 1000, tartalek=64)
    assert not fer
    fer, _, _ = lemezhely.eleg_hely("C:/x", 1000, tartalek=0)
    assert fer


def test_ismeretlen_meret_nem_akadaly(hely):
    """A szerver nem mindig mondja meg a méretet – ez nem ok a megtagadásra."""
    hely(1)
    fer, _, _ = lemezhely.eleg_hely("C:/x", 0)
    assert fer


def test_meghatarozhatatlan_hely_nem_akadaly(hely):
    """Hálózati meghajtón a szabad hely lekérdezése hibázhat. Egy HAMIS
    „nincs hely" rosszabb, mint egy meg nem akadályozott letöltés."""
    hely(-1)
    fer, sz, _ = lemezhely.eleg_hely("C:/x", 4 * 1024 ** 3)
    assert fer and sz == -1


def test_kikapcsolva(monkeypatch, hely):
    hely(1)
    monkeypatch.setattr(lemezhely, "BEKAPCSOLVA", False)
    fer, _, _ = lemezhely.eleg_hely("C:/x", 4 * 1024 ** 3)
    assert fer
    assert lemezhely.alacsony("C:/x") == (False, -1)


def test_alacsony_kuszob(hely):
    hely(100 * 1024 ** 2)
    keves, _ = lemezhely.alacsony("C:/x")
    assert keves
    hely(10 * 1024 ** 3)
    keves, _ = lemezhely.alacsony("C:/x")
    assert not keves


def test_hiba_szoveg_harom_szamot_mond():
    """Vakon egyik szám sem látszik: kell, van, hiányzik – mindhárom hangozzon el."""
    sz = lemezhely.hiba_szoveg("film.mkv", 4 * 1024 ** 3, 1 * 1024 ** 3,
                               3 * 1024 ** 3)
    assert "film.mkv" in sz
    assert sz.count("gigabájt") >= 3
    assert "hiányzik" in sz


def test_letezo_szulo_nem_letezo_mappara(tmp_path):
    """A célmappát a letöltő hozza létre – a `disk_usage` viszont létező utat
    kér. A szülő ugyanazon a köteten van, tehát a válasz ugyanaz."""
    p = tmp_path / "nincs" / "meg" / "ilyen"
    assert lemezhely.letezo_szulo(p) == tmp_path


# ---- ellenőrző összeg -------------------------------------------------

def test_ujjlenyomat_url_toredekbol():
    h = "a" * 64
    assert segment.vart_ujjlenyomat(f"http://p/f.zip#sha256={h}") == h
    assert segment.vart_ujjlenyomat(f"http://p/f.zip#sha-256={h}") == h


def test_ujjlenyomat_nagybetus_hexet_kisbetusit():
    h = "A" * 64
    assert segment.vart_ujjlenyomat(f"http://p/f.zip#sha256={h}") == "a" * 64


def test_ujjlenyomat_nincs():
    assert segment.vart_ujjlenyomat("http://p/f.zip") == ""
    assert segment.vart_ujjlenyomat("http://p/f.zip#valami=mas") == ""


def test_ujjlenyomat_md5_es_sha1_NEM_szamit():
    """Egy törött ellenőrzés rosszabb a semminél: biztonságérzetet ad."""
    assert segment.vart_ujjlenyomat("http://p/f.zip#md5=" + "a" * 32) == ""
    assert segment.vart_ujjlenyomat("http://p/f.zip#sha1=" + "a" * 40) == ""


def test_ujjlenyomat_fejlecbol_base64():
    import base64
    nyers = bytes(range(32))
    b64 = base64.b64encode(nyers).decode()
    kapott = segment.vart_ujjlenyomat(
        "http://p/f.zip", {"digest": f"sha-256=:{b64}:"})
    assert kapott == nyers.hex()
    kapott = segment.vart_ujjlenyomat(
        "http://p/f.zip", {"repr-digest": f"sha-256={b64}"})
    assert kapott == nyers.hex()


def test_ujjlenyomat_rossz_hosszu_base64_kimarad():
    import base64
    b64 = base64.b64encode(b"rovid").decode()
    assert segment.vart_ujjlenyomat(
        "http://p/f.zip", {"digest": f"sha-256={b64}"}) == ""


def test_fajl_sha256(tmp_path):
    import hashlib
    f = tmp_path / "a.bin"
    adat = b"x" * (1024 * 1024 + 7)          # egy blokknál nagyobb
    f.write_bytes(adat)
    assert segment.fajl_sha256(f) == hashlib.sha256(adat).hexdigest()


# ---- az egyszálú folytatás két lyuka ----------------------------------

def test_allapotfajl_modja_elvalik(tmp_path):
    """A szegmentált ág NEM veheti fel az egyszálú állapotot: annak üres a
    szegmenslistája, amiből az következne, hogy minden kész."""
    d = SegmentDownloaderProba(tmp_path)
    cel = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(b"x" * 10)
    d._save_state(cel, 100, [], "egyszalu")
    assert d._load_state(cel, 100, "egyszalu") == []
    assert d._load_state(cel, 100, "szegmentalt") is None


def test_regi_allapotfajl_szegmentaltnak_szamit(tmp_path):
    """A MK3 előtt írt állapotfájlokban nincs `mode` – azok szegmentáltak
    voltak, és folytathatónak kell maradniuk frissítés után is."""
    d = SegmentDownloaderProba(tmp_path)
    cel = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(b"x" * 10)
    (tmp_path / "f.bin.sdlstate").write_text(json.dumps(
        {"url": d.url, "size": 100, "segments": [[10, 99]],
         "etag": "", "lastmod": ""}))
    assert d._load_state(cel, 100, "szegmentalt") == [[10, 99]]


def test_arva_part_megtalalhato_allapotfajllal(tmp_path):
    """Ha a kész fájl már foglalja a célnevet, az `unique_path` új nevet ad.
    Az egyszálú .part csak akkor található meg, ha hagyott állapotfájlt –
    ez volt az MK3 előtti lyuk."""
    d = SegmentDownloaderProba(tmp_path)
    (tmp_path / "f.bin").write_bytes(b"kesz")          # foglalja a nevet
    cel = tmp_path / "f (1).bin"
    (tmp_path / "f (1).bin.part").write_bytes(b"x" * 10)
    d._save_state(cel, 100, [], "egyszalu")
    assert d._find_resumable_target("f.bin", 100, "egyszalu") == cel


def SegmentDownloaderProba(mappa):
    return segment.SegmentDownloader("http://pelda/f.bin", str(mappa))


class _HamisValasz:
    """Egy `requests` válasz annyija, amennyit a `_download_single` használ."""

    def __init__(self, adat: bytes, status: int = 206):
        self._adat = adat
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, meret):
        yield self._adat


class _HamisSession:
    def __init__(self, adat: bytes, status: int = 206):
        self._adat, self._status = adat, status
        self.headers = {}
        self.kapott_fejlecek = None

    def get(self, url, stream=False, timeout=None, headers=None):
        self.kapott_fejlecek = dict(headers or {})
        return _HamisValasz(self._adat, self._status)


def test_egyszalu_folytatas_ISMERETLEN_meretnel_is(tmp_path):
    """AZ MK3 LÉNYEGE. A régi feltétel `existing and self.progress.total` volt:
    ismeretlen méretnél (chunked válasz) hamis lett, a meglévő .part-ot pedig
    NÉMÁN felülírta – nem csak elölről kezdett, hanem eldobta az adatot is."""
    d = segment.SegmentDownloader("http://pelda/f.bin", str(tmp_path))
    d.session = _HamisSession(b"uj")
    part = tmp_path / "f.bin.part"
    part.write_bytes(b"x" * 10)
    d.progress.total = 0                     # ISMERETLEN méret
    d._download_single(tmp_path / "f.bin", part, 0)
    assert d.session.kapott_fejlecek.get("Range") == "bytes=10-"
    assert part.read_bytes() == b"x" * 10 + b"uj"      # hozzáfűzött, nem törölt


def test_egyszalu_visszaesik_ha_a_szerver_nem_206(tmp_path):
    """Ha a szerver figyelmen kívül hagyja a Range-et, elölről kell kezdeni –
    és a számlálót is nullázni, különben a százalék hazudik."""
    d = segment.SegmentDownloader("http://pelda/f.bin", str(tmp_path))
    d.session = _HamisSession(b"teljes", status=200)
    part = tmp_path / "f.bin.part"
    part.write_bytes(b"x" * 10)
    d._download_single(tmp_path / "f.bin", part, 0)
    assert part.read_bytes() == b"teljes"
    assert d.progress.downloaded == len(b"teljes")


def test_egyszalu_allapotfajlt_hagy(tmp_path):
    d = segment.SegmentDownloader("http://pelda/f.bin", str(tmp_path))
    d.session = _HamisSession(b"adat")
    d._download_single(tmp_path / "f.bin", tmp_path / "f.bin.part", 4)
    allapot = json.loads((tmp_path / "f.bin.sdlstate").read_text())
    assert allapot["mode"] == "egyszalu"


def test_progress_nullaz_zar_alatt():
    p = segment.Progress()
    p.add(100)
    p.nullaz()
    assert p.downloaded == 0


# ---- takarítás a sorból törléskor -------------------------------------

class _ProbaJob:
    """Annyi egy jobból, amennyit a `takarithato()` használ – így a teszt nem
    indít valódi letöltéskezelőt."""

    def __init__(self, url, out_dir, filename=""):
        self.url = url
        self.out_dir = str(out_dir)
        self.progress = segment.Progress()
        self.progress.filename = filename


def _takarithato(job):
    from superdl.manager import DownloadManager
    return DownloadManager.takarithato(None, job)


def test_takarithato_az_URL_alapjan_valogat(tmp_path):
    """A NÉV nem azonosít: `video.mp4` mindenhol van. Ha névre törölnénk, egy
    MÁSIK letöltés félkész fájlát semmisítenénk meg – visszavonhatatlanul."""
    mienk = tmp_path / "a.bin"
    mase = tmp_path / "b.bin"
    for cel, url in ((mienk, "http://mienk/a.bin"), (mase, "http://mase/b.bin")):
        (tmp_path / (cel.name + ".part")).write_bytes(b"x")
        (tmp_path / (cel.name + ".sdlstate")).write_text(json.dumps(
            {"url": url, "size": 1, "segments": [], "mode": "egyszalu"}))

    job = _ProbaJob("http://mienk/a.bin", tmp_path)
    nevek = {p.name for p in _takarithato(job)}
    assert nevek == {"a.bin.part", "a.bin.sdlstate"}
    assert not any(n.startswith("b.bin") for n in nevek)


def test_takarithato_allapotfajl_nelkuli_part_csak_pontos_nevre(tmp_path):
    """A MK3 előtti egyszálú letöltések nem hagytak állapotfájlt – nekik ez
    az egyetlen esélyük, de csak pontos névegyezéssel."""
    (tmp_path / "regi.bin.part").write_bytes(b"x")
    (tmp_path / "masik.bin.part").write_bytes(b"x")
    job = _ProbaJob("http://pelda/regi.bin", tmp_path, filename="regi.bin")
    nevek = {p.name for p in _takarithato(job)}
    assert nevek == {"regi.bin.part"}


def test_takarithato_ures_ha_nincs_mit(tmp_path):
    job = _ProbaJob("http://pelda/a.bin", tmp_path, filename="a.bin")
    assert _takarithato(job) == []


def test_takarithato_nem_letezo_mappa(tmp_path):
    job = _ProbaJob("http://pelda/a.bin", tmp_path / "nincs", filename="a.bin")
    assert _takarithato(job) == []
