# -*- coding: utf-8 -*-
"""Herman Tibi 2. auditcsomag KV4 köre: P2P titok/valódi siker, PIN-maszkolás,
alapértelmezett felvevő eszköz."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "p2p"))
from p2p_mod import p2p                                   # noqa: E402


def _src(rel: str) -> str:
    return (ROOT / "modules_src" / rel).read_text(encoding="utf-8")


# ---- P2P-P0-03: a nullás kilépési kód ÖNMAGÁBAN nem siker ------------------

class _FakeRecv(p2p.ReceiveSession):
    def __init__(self, out_dir, filename=""):
        super().__init__("1-teszt-kod", str(out_dir))
        self.filename = filename
        self._started_at = 0.0        # minden fájl „újnak" számít


def test_hianyzo_fajl_eseten_nincs_hamis_siker(tmp_path):
    s = _FakeRecv(tmp_path, "nincs_ilyen.bin")
    ok, _, _ = s._verify_received()
    assert ok is False


def test_ures_fajl_eseten_nincs_hamis_siker(tmp_path):
    (tmp_path / "ures.bin").write_bytes(b"")
    s = _FakeRecv(tmp_path, "ures.bin")
    ok, _, _ = s._verify_received()
    assert ok is False


def test_valodi_fajl_eseten_siker_es_meret(tmp_path):
    (tmp_path / "jo.bin").write_bytes(b"x" * 4096)
    s = _FakeRecv(tmp_path, "jo.bin")
    ok, where, size = s._verify_received()
    assert ok is True and size == 4096 and where.endswith("jo.bin")


def test_nev_nelkul_a_legfrissebb_fajlt_ismeri_fel(tmp_path):
    (tmp_path / "erkezett.bin").write_bytes(b"y" * 100)
    s = _FakeRecv(tmp_path, "")           # a CLI-kimenetből nem jött név
    ok, where, size = s._verify_received()
    assert ok is True and size == 100 and where.endswith("erkezett.bin")


def test_ures_celmappa_nem_ad_sikert(tmp_path):
    s = _FakeRecv(tmp_path, "")
    ok, _, _ = s._verify_received()
    assert ok is False


def test_human_size_magyarul():
    assert p2p._human_size(512) == "512 bájt"
    assert "kilobájt" in p2p._human_size(2048)
    assert "megabájt" in p2p._human_size(5 * 1024 ** 2)


# ---- P2P-P0-02: a kód titok – elhangzik és nem marad a vágólapon -----------

def test_a_kod_aktivan_elhangzik():
    src = _src("p2p/p2p_mod/p2pwin.py")
    assert "_spell_code" in src, "a kód nincs tagoltan bemondva"
    i = src.index("def _send_code")
    assert "self._speak(" in src[i:i + 1400], "a _send_code nem mondja be a kódot"


def test_a_kod_torlodik_a_vagolaprol():
    src = _src("p2p/p2p_mod/p2pwin.py")
    assert "_clear_clipboard_code" in src
    assert src.count("self._clear_clipboard_code()") >= 2, \
        "a vágólap-törlés nincs bekötve az átvitel végére ÉS a zárásra"


# ---- P2P-P0-01: a súgó ne állítson valótlant -------------------------------

def test_sugo_nem_allit_valotlant_a_kulso_szerverrol():
    src = _src("p2p/p2p_mod/p2pwin.py")
    assert "NEM megy át külső szerveren" not in src, \
        "a súgó továbbra is abszolút módon tagadja a külső szervert"
    assert "VÉGPONTOK KÖZÖTT TITKOSÍTVA" in src
    assert "továbbító szerveren" in src, "nincs említve a relay-lehetőség"


# ---- ORG-P0-03: az ÚJ PIN maszkolt mezőben -------------------------------

def test_uj_pin_maszkolt_mezoben():
    src = _src("szervezes/szervezes_mod/organizerwin.py")
    assert "wx.PasswordEntryDialog" in src, "az új PIN nem maszkolt mezőben megy"


# ---- VC-P0-02 / REC / SM: az alapértelmezett felvevő eszköz ---------------

def test_nincs_tobbe_kezi_nullas_eszkozvaltas():
    for rel in ("supermedia/supermedia_mod/supervoicechanger.py",
                "supermedia/supermedia_mod/superrec.py",
                "supermedia/supermedia_mod/superm_audio.py"):
        src = _src(rel)
        assert "if self.device >= 0 else 0)" not in src, f"{rel}: régi 0-ra váltás"
        assert "if self.in_device >= 0 else 0)" not in src, f"{rel}: régi 0-ra váltás"


def test_kozos_eszkozvalaszto_letezik_es_hasznaljak():
    a = _src("supermedia/supermedia_mod/superm_audio.py")
    assert "def select_record_device" in a
    for rel in ("supermedia/supermedia_mod/superrec.py",
                "supermedia/supermedia_mod/supervoicechanger.py"):
        assert "select_record_device" in _src(rel), f"{rel}: nem használja"


# ---- SM-P0-01: az élő adás kritikus állapotai HALLHATÓK -------------------

def test_super_m_kritikus_allapotai_bemondasra_kerulnek():
    src = _src("supermedia/supermedia_mod/supermwin.py")
    assert "def _announce_live" in src, "nincs kritikus (bemondó) állapot-út"
    assert "sv.speak(text, force=True)" in src
    # az élő adás és a mikrofon állapota nem maradhat néma
    for kulcs in ("ÉLŐ ADÁS megy!", "Mikrofon ÉLŐ", "Mikrofon KI.",
                  "Az élő adás leállítva.", "Az adás nem indult: "):
        i = src.index(kulcs)
        elozo = src.rfind("self._announce", 0, i)
        assert src[elozo:elozo + 20].startswith("self._announce_live"), \
            f"NÉMA marad: {kulcs}"


def test_rutin_allapot_nem_fecseg_bele_a_musorba():
    """A sima _announce SZÁNDÉKOSAN néma marad (nem beszél minden számváltásnál)."""
    src = _src("supermedia/supermedia_mod/supermwin.py")
    i = src.index("    def _announce(self, text):")
    torzs = src[i:src.index("    def _announce_live")]
    assert "speak" not in torzs, "a rutin _announce beszél – adás közben fecsegne"


# ---- SM-P0-02: nincs HAMIS élő adás --------------------------------------

def test_caster_valodi_elo_ellenorzest_ad():
    src = _src("supermedia/supermedia_mod/superm_stream.py")
    assert "def check_live" in src, "nincs valódi adás-állapot ellenőrzés"
    assert "BASS_Encode_IsActive" in src


def test_a_bontast_a_felulet_eszreveszi_es_bemondja():
    src = _src("supermedia/supermedia_mod/supermwin.py")
    i = src.index("    def _tick(self):")
    torzs = src[i:i + 1200]
    assert "check_live()" in torzs, "a _tick nem figyeli az adás valódi állapotát"
    assert "MEGSZAKADT" in torzs
