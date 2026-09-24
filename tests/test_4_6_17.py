"""4.6.17 – négy javítás a 09-23-i levelekből. MINDEGYIKHEZ MÉRÉS tartozik.

1. ÁRVA TORRENT ÁTVÉTELE (Tóth László naplója). A motor a duplikátumra új
   gid-et ad `error / 12 / InfoHash … is already registered` állapotban; az
   első példány a `tellActive` `infoHash` mezőjén megtalálható (mérve).
2. HIÁNYZÓ .torrent (Nagy Károly: „No URI to download."). Mérve: egy nem
   létező helyi út az `addUri`-nek pontosan ezt adja, azonnal, 400-zal.
3. 32 BITES SAPI (Tóth László: „a belső hangok nem mennek"). Mérve: 64 biten
   11 hangból 9 elbukik (0x80045001), 32 biten 18-ból 18 megy.
4. MEGHAJTÓK ÉRINTÉS NÉLKÜL (Tóth László megakadás-naplója kétszer a
   `meghajtok()`-ban). + a beszélő óra köszöntő hangjai (Lukács László).
"""
import inspect
from pathlib import Path

import pytest

from superdl import torrent as T
from superdl import hibaszoveg as H
from superdl import tts
from superdl import orahang as O
from superdl import fajlvalaszto as F

GYOKER = Path(__file__).resolve().parents[1]


# ======================================================================
# 1. árva torrent átvétele
# ======================================================================

MERT = ("InfoHash b3fa29fa5e15b8dc06a964286e17192e3e463187 is already "
        "registered.")


def test_az_infohash_kinyerheto_a_mert_uzenetbol():
    assert T.mar_regisztralt_infohash(MERT) == \
        "b3fa29fa5e15b8dc06a964286e17192e3e463187"


@pytest.mark.parametrize("szoveg", ["", None, "valami más", "InfoHash xyz"])
def test_mas_uzenetbol_nincs_infohash(szoveg):
    assert T.mar_regisztralt_infohash(szoveg) == ""


class _Kliens:
    """A motor válaszai a MÉRT alakban."""

    def __init__(self, aktiv=(), varo=()):
        self.aktiv = list(aktiv)
        self.varo = list(varo)
        self.hivasok = []

    def call(self, modszer, *param):
        self.hivasok.append(modszer)
        if modszer == "aria2.tellActive":
            return self.aktiv
        if modszer == "aria2.tellWaiting":
            return self.varo
        return "OK"


class _Figyelo:
    def __init__(self, figyelt=()):
        self.figyelt = set(figyelt)
        self.regisztralt, self.elengedett = [], []

    def figyelt_e(self, gid):
        return gid in self.figyelt

    def regisztral(self, gid):
        self.regisztralt.append(gid)

    def elenged(self, gid):
        self.elengedett.append(gid)


IH = "b3fa29fa5e15b8dc06a964286e17192e3e463187"


def _letolto(kliens, figyelo, gid="52b3ea893e457b19"):
    d = T.TorrentDownloader("x.torrent", ".")
    d.client, d.figyelo, d.gid = kliens, figyelo, gid
    return d


def test_az_arva_futo_peldanyt_atvesszuk():
    k = _Kliens(aktiv=[{"gid": "ad0fc14f7f705613", "status": "active",
                        "infoHash": IH}])
    f = _Figyelo()
    d = _letolto(k, f)
    p = d.progress
    p.status, p.error = "hiba", "régi"
    assert d._atvesz(MERT, p) is True
    assert d.gid == "ad0fc14f7f705613"
    assert f.regisztralt == ["ad0fc14f7f705613"]
    assert f.elengedett == ["52b3ea893e457b19"]
    assert "aria2.removeDownloadResult" in k.hivasok
    assert p.status == "letöltés" and p.error == ""


def test_a_varakozo_peldany_is_atveheto():
    k = _Kliens(varo=[{"gid": "g1", "status": "paused", "infoHash": IH}])
    d = _letolto(k, _Figyelo())
    assert d._atvesz(MERT, d.progress) is True
    assert d.gid == "g1"


def test_masik_elo_listaelem_peldanyat_NEM_vesszuk_at():
    """⚠️ Ha tényleg kétszer adták hozzá, a régi üzenet az igaz, és két elem
    egy gid-en osztozva egymást állítaná le."""
    k = _Kliens(aktiv=[{"gid": "g1", "status": "active", "infoHash": IH}])
    d = _letolto(k, _Figyelo(figyelt={"g1"}))
    assert d._atvesz(MERT, d.progress) is False
    assert d.gid == "52b3ea893e457b19"


def test_ha_nincs_futo_peldany_marad_a_hiba():
    d = _letolto(_Kliens(), _Figyelo())
    assert d._atvesz(MERT, d.progress) is False


def test_leallt_peldanyt_nem_veszunk_at():
    k = _Kliens(aktiv=[{"gid": "g1", "status": "error", "infoHash": IH}])
    d = _letolto(k, _Figyelo())
    assert d._atvesz(MERT, d.progress) is False


def test_mas_hiba_eseten_nincs_atvetel():
    d = _letolto(_Kliens(aktiv=[{"gid": "g1", "status": "active",
                                 "infoHash": IH}]), _Figyelo())
    assert d._atvesz("No peers", d.progress) is False


def test_a_kovetes_elobb_atvesz_es_csak_utana_hibazik():
    src = inspect.getsource(T.TorrentDownloader._kovet)
    i_atv = src.index("self._atvesz(raw, p)")
    i_hiba = src.index('p.status = "hiba"', src.index('if status == "error"'))
    assert i_atv < i_hiba


def test_a_figyelo_tudja_ki_kovet_mit():
    f = T.Figyelo.__new__(T.Figyelo)
    import threading
    f._lock = threading.Lock()
    f._gidek = set()
    f._adat, f._mikor = {}, {}
    assert f.figyelt_e("a") is False
    T.Figyelo.regisztral(f, "a")
    assert f.figyelt_e("a") is True


# ======================================================================
# 2. hiányzó .torrent fájl
# ======================================================================

def test_hianyzo_helyi_torrent_felismerese(tmp_path):
    d = T.TorrentDownloader(str(tmp_path / "nincs.torrent"), str(tmp_path))
    assert d.hianyzo_fajl() is True
    megvan = tmp_path / "van.torrent"
    megvan.write_bytes(b"d4:infod4:name1:aee")
    assert T.TorrentDownloader(str(megvan), str(tmp_path)).hianyzo_fajl() \
        is False


@pytest.mark.parametrize("url", ["magnet:?xt=urn:btih:abc",
                                 "https://pelda.hu/x.torrent",
                                 "http://pelda.hu/x.torrent"])
def test_a_link_nem_hianyzo_fajl(url, tmp_path):
    assert T.TorrentDownloader(url, str(tmp_path)).hianyzo_fajl() is False


def test_a_hianyzo_fajl_magyar_hibat_ad_es_nem_hivja_a_motort(tmp_path):
    d = T.TorrentDownloader(str(tmp_path / "Olé Fradi.torrent"), str(tmp_path))
    d.client = _Kliens()
    with pytest.raises(T.HianyzoTorrentFajl) as e:
        d._add()
    assert "Olé Fradi.torrent" in str(e.value)
    assert d.client.hivasok == [], "a motornak nem szabad a halott utat adni"


def test_a_hianyzo_fajlt_nem_varjuk_ki(tmp_path, monkeypatch):
    """⚠️ Eddig ötször újrapróbálta, és közben azt mondta: „a motor
    elfoglalt, várok vele". Ez hazugság volt."""
    monkeypatch.setattr(T.time, "sleep", lambda s: pytest.fail("várt rá"))
    d = T.TorrentDownloader(str(tmp_path / "nincs.torrent"), str(tmp_path))
    d.client = _Kliens()
    with pytest.raises(T.HianyzoTorrentFajl):
        d._add_turelemmel()
    assert d.progress.figyelmeztetes in ("", None)


@pytest.mark.parametrize("uzenet", ["No URI to download.",
                                    "URI is not provided."])
def test_a_no_uri_valaszt_sem_varjuk_ki(uzenet, monkeypatch, tmp_path):
    monkeypatch.setattr(T.time, "sleep", lambda s: pytest.fail("várt rá"))
    d = T.TorrentDownloader("https://x/y.torrent", str(tmp_path))

    def rossz():
        raise RuntimeError(uzenet)
    monkeypatch.setattr(d, "_add", rossz)
    with pytest.raises(RuntimeError):
        d._add_turelemmel()


@pytest.mark.parametrize("uzenet, vart", [
    ("A torrentfájl már nincs meg ott, ahonnan…", True),
    ("No URI to download.", True),
    ("A letöltés forrása már nincs meg: …", True),
    ("InfoHash x is already registered.", False),
    ("Read timed out", False),
])
def test_nem_mulo_hiba(uzenet, vart):
    assert T.nem_mulo_hiba(uzenet) is vart


def test_a_hianyzo_forrast_nem_probaljuk_ujra_negyedorankent():
    src = (GYOKER / "superdl" / "manager.py").read_text(encoding="utf-8")
    i = src.index("def _retry_tick")
    blokk = src[i:src.index("def _jelez", i)]
    assert "nem_mulo_hiba" in blokk
    assert blokk.index("nem_mulo_hiba") < blokk.index("job.retries += 1")


def test_a_no_uri_magyarul_szol():
    m = H.emberi("No URI to download.")
    assert "nincs meg" in m and "URI" not in m


def test_a_sajat_mondatunkhoz_nem_nyulunk():
    assert H.sajat_uzenet("A torrentfájl már nincs meg ott, ahonnan…")


# ======================================================================
# 3. 32 bites SAPI
# ======================================================================

def test_hangmagassag_nelkul_sima_szoveg_megy():
    """⚠️ MÉRVE (BraiLab): a pitch-jelölés alapjelzővel ÜRES hangot adott."""
    sz, jel = tts.SapiEngine.szoveg_es_jelzo("Tűz & víz <x>", 0)
    assert sz == "Tűz & víz <x>"
    assert jel == tts.SVSF_IS_NOT_XML


def test_hangmagassaggal_kifejezetten_xml_megy_escapelve():
    sz, jel = tts.SapiEngine.szoveg_es_jelzo("Tűz & víz", 4)
    assert jel == tts.SVSF_IS_XML
    assert sz.startswith("<pitch absmiddle='4'/>")
    assert "&amp;" in sz


def test_a_hangmagassag_be_van_szoritva():
    sz, _ = tts.SapiEngine.szoveg_es_jelzo("a", 99)
    assert "absmiddle='10'" in sz


def test_a_32_bites_segedet_encodedcommanddal_inditjuk():
    """⚠️ -File helyett -EncodedCommand: céges gépen az AllSigned házirend a
    szkriptfájlt elutasítaná."""
    src = inspect.getsource(tts._Sapi32._indit)
    assert "-EncodedCommand" in src and "-File" not in src
    assert "SysWOW64" in inspect.getsource(tts._Sapi32.powershell32)


def test_ha_nincs_32_bites_seged_a_64_bites_ut_jon(monkeypatch, tmp_path):
    hivas = []

    def nincs(*a, **k):
        raise tts._Sapi32Nincs("teszt")
    monkeypatch.setattr(tts._SAPI32, "mond", nincs)
    monkeypatch.setattr(tts.SapiEngine, "_synth64",
                        lambda self, *a: hivas.append(a) or "x.wav")
    assert tts.ENGINES["sapi"].synth("a", "h", str(tmp_path / "o")) == "x.wav"
    assert hivas


def test_ures_hangnal_hangmagassag_nelkul_ujraprobal(monkeypatch, tmp_path):
    """⚠️ MÉRVE: a BraiLab hangmagasság-kérésre 46 bájtos (néma) WAV-ot ad."""
    kert = []

    def mond(szoveg, hang, rate, jelzo, ut):
        kert.append(jelzo)
        return 46 if jelzo == tts.SVSF_IS_XML else 50000
    monkeypatch.setattr(tts._SAPI32, "mond", mond)
    tts.ENGINES["sapi"].synth("a", "BraiLab PC", str(tmp_path / "o"), pitch=3)
    assert kert == [tts.SVSF_IS_XML, tts.SVSF_IS_NOT_XML]


def test_ha_semmit_nem_mondott_az_hiba_nem_csend(monkeypatch, tmp_path):
    monkeypatch.setattr(tts._SAPI32, "mond", lambda *a: 46)
    with pytest.raises(RuntimeError, match="nem mondott semmit"):
        tts.ENGINES["sapi"].synth("a", "X", str(tmp_path / "o"))


def test_a_hanglista_elobb_a_32_bitest_kerdezi(monkeypatch):
    monkeypatch.setattr(tts._SAPI32, "hangok",
                        lambda: [("BME-TMIT Eszter", "40E")])
    vs = tts.ENGINES["sapi"].voices()
    assert [v.id for v in vs] == ["BME-TMIT Eszter"]
    assert vs[0].lang == "40E"


def test_az_inditaskori_felolvaso_nem_kerdez_hanglistat():
    """⚠️ A 32 bites segéd indulása ~5 mp (mérve). A `VoiceSpeaker` a program
    indulásakor, a FŐ SZÁLON jön létre – ott nem szabad hanglistát kérni."""
    from superdl import speech
    src = inspect.getsource(speech.VoiceSpeaker.__init__)
    assert "_pick_sapi_voice()" not in src
    assert "_sapi_voice_cache = None" in src


@pytest.mark.skipif(not tts._Sapi32.powershell32(),
                    reason="nincs 32 bites PowerShell (nem Windows)")
def test_a_32_bites_seged_valoban_elindul_es_hangot_ad(tmp_path):
    """ÉLES PRÓBA a gépen: legalább egy hang, és abból tényleg WAV lesz."""
    lista = tts._SAPI32.hangok()
    assert lista, "a 32 bites SAPI egyetlen hangot sem látott"
    meret = tts._SAPI32.mond("próba", lista[0][0], 0, tts.SVSF_IS_NOT_XML,
                             str(tmp_path / "p.wav"))
    assert meret > tts.URES_WAV_BAJT


# ======================================================================
# 4. meghajtók érintés nélkül + az óra köszöntő hangjai
# ======================================================================

def test_a_merevlemezt_es_a_halozatit_nem_erintjuk(monkeypatch):
    erintett = []
    monkeypatch.setattr(F, "_meghajto_betuk",
                        lambda: [("C", 3), ("J", 3), ("N", 4), ("E", 2),
                                 ("D", 5), ("X", 1)])
    monkeypatch.setattr(F.os, "name", "nt")
    monkeypatch.setattr(F.os.path, "isdir",
                        lambda p: erintett.append(p) or p == "E:\\")
    ki = F.meghajtok()
    assert ki == ["C:\\", "J:\\", "N:\\", "E:\\"]
    assert sorted(erintett) == ["D:\\", "E:\\"], \
        "csak a cserélhetőt és az optikait szabad megnézni"


def test_ha_a_bitterkep_nem_megy_a_regi_ut_jon(monkeypatch):
    monkeypatch.setattr(F, "_meghajto_betuk", lambda: None)
    monkeypatch.setattr(F.os, "name", "nt")
    monkeypatch.setattr(F.os.path, "isdir", lambda p: p == "C:\\")
    assert F.meghajtok() == ["C:\\"]


def test_az_ora_listajaban_elol_vannak_a_koszonto_hangok():
    nevek = [n for n, _ in O.keszlet()]
    assert nevek[1:3] == ["edge:hu-HU-TamasNeural", "edge:hu-HU-NoemiNeural"]
    assert nevek[0] == ""


def test_a_koszonto_hang_ervenyes_a_kitalalt_nem():
    assert O.ervenyes("edge:hu-HU-TamasNeural")
    assert not O.ervenyes("edge:xx-Kamu")


def test_a_koszonto_hang_cimkeje_mondja_hogy_net_kell():
    assert "internet" in O.cimke("edge:hu-HU-NoemiNeural")


def test_net_nelkul_az_ora_nem_nemul_el(monkeypatch):
    """⚠️ Ha az Edge nem elérhető, az eSpeak alaphangja mond be."""
    b = O.Beszelo.__new__(O.Beszelo)
    b.kepernyoolvaso = False
    mondott = []
    monkeypatch.setattr(b, "_edge", lambda x: False, raising=False)
    monkeypatch.setattr(b, "_espeak", lambda x: mondott.append(x.valtozat),
                        raising=False)
    O.Beszelo._egy(b, O.Bemondas("idő", "edge:hu-HU-TamasNeural"))
    assert mondott == [""]
