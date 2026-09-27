"""szakember83 jelentése (2026-09-26): a 4.6.20→4.6.21 frissítés megszakadt,
a program „megakadt", és a hibajelentésből pont a megakadás nyoma maradt ki
– helyette egy túlélt COM-jelzést nevezett „összeomlásnak"."""
import io
from pathlib import Path

import pytest

from superdl import osszeomlas as O
from superdl import selfupdate as S

NAPLO = """
=== SuperDL indult: 2026-09-26 18:28:27 (verzió: 4.6.20) ===

=== SuperDL MEGAKADÁS: a fő szál több mint 20 másodperce nem válaszol (2026-09-26 20:29:10) ===
Thread 0x0001 [Thread-9 (work)] (most recent call first):
  File "superdl\\selfupdate.py", line 190 in _download_to_file
Current thread 0x0002 (most recent call first):
  File "wx\\core.py", line 2254 in MainLoop
=== a megakadás nyomának vége ===

=== SuperDL indult: 2026-09-26 20:31:40 (verzió: 4.6.21) ===
Windows fatal exception: code 0x8001010d

Thread 0x000005e4 [Thread-5 (work)] (most recent call first):
  File "superdl\\feeds.py", line 61 in parse_feed
Current thread 0x00002a48 (most recent call first):
  File "wx\\core.py", line 2254 in MainLoop
"""


@pytest.fixture
def naplo(tmp_path, monkeypatch):
    p = tmp_path / "osszeomlas.log"
    p.write_text(NAPLO, encoding="utf-8")
    monkeypatch.setattr(O, "NAPLO", p)
    return p


def test_mindket_nyom_bekerul(naplo, monkeypatch):
    monkeypatch.setattr(O, "_fajl", None)
    b = O.jelentes_blokkok()
    assert [x["fajta"] for x in b] == ["megakadas", "osszeomlas"]
    assert any("_download_to_file" in s for s in b[0]["sorok"])
    assert b[0]["verzio"] == "4.6.20" and b[0]["ota"] == 1
    assert b[1]["verzio"] == "4.6.21" and b[1]["ota"] == 0
    assert "0x8001010d" in "\n".join(b[1]["sorok"])


def test_a_futo_programban_tulelt_jelzes(naplo, monkeypatch):
    monkeypatch.setattr(O, "_fajl", io.StringIO())    # a program most fut
    b = O.jelentes_blokkok()
    assert b[-1]["fajta"] == "tulelt"


def test_rendben_kilepett_futas_nem_osszeomlas(naplo, monkeypatch):
    naplo.write_text(NAPLO + O.RENDBEN_JEL + ": 2026-09-26 21:00:00 ===\n",
                     encoding="utf-8")
    monkeypatch.setattr(O, "_fajl", None)
    assert O.jelentes_blokkok()[-1]["fajta"] == "tulelt"
    # az indulási figyelmeztetés se mondja, hogy „váratlanul bezárult"
    monkeypatch.setattr(O, "_uj_resz", naplo.read_text(encoding="utf-8"))
    assert O.uj_osszeomlas() is False
    assert O.uj_megakadas() is True


def test_rendes_kilepes_nelkul_marad_osszeomlas(naplo, monkeypatch):
    monkeypatch.setattr(O, "_uj_resz", NAPLO)
    assert O.uj_osszeomlas() is True


def test_rendben_kilep_ir(monkeypatch):
    f = io.StringIO()
    monkeypatch.setattr(O, "_fajl", f)
    O.rendben_kilep()
    assert O.RENDBEN_JEL in f.getvalue()


def test_jelentes_szovege(naplo, monkeypatch):
    from superdl import diagnostics as D
    monkeypatch.setattr(O, "_fajl", io.StringIO())
    lines = []
    b = O.jelentes_blokkok()
    for x in b:
        lines += [D._BLOKK_CIM[x["fajta"]]] + D._kor_sorok(x)
    t = "\n".join(lines)
    assert "MEGAKADÁS-NAPLÓ" in t and "TÚLÉLT" in t
    assert "ÖSSZEOMLÁS-NAPLÓ" not in t


# ---- letöltés: újrapróbálás, csonka fájl, folyamatjelző ------------------

def test_ujraprobal_es_naploz(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "update_log", lambda: tmp_path / "update.log")
    hivas = []

    def hamis(url, dest, progress=None):
        hivas.append(1)
        if len(hivas) < 3:
            raise S.FelbeszakadtLetoltes("a letöltés félbeszakadt (3 / 144 MB)")
        dest.write_bytes(b"x")
        return "abc"

    monkeypatch.setattr(S, "_download_to_file", hamis)
    got = S._letolt_ellenorizve("u", tmp_path / "Setup.exe", "abc",
                                varakozas=0)
    assert got == "abc" and len(hivas) == 3
    log = (tmp_path / "update.log").read_text(encoding="utf-8")
    assert "1. proba sikertelen" in log and "3. probara" in log


def test_vegleges_halozati_hiba_ertheto(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "update_log", lambda: tmp_path / "update.log")

    def hamis(url, dest, progress=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(S, "_download_to_file", hamis)
    with pytest.raises(RuntimeError) as e:
        S._letolt_ellenorizve("u", tmp_path / "Setup.exe", None, varakozas=0)
    assert "internetkapcsolat" in str(e.value)
    assert "manipulált" not in str(e.value)


def test_osszeg_hiba_marad_szigoru(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "update_log", lambda: tmp_path / "update.log")
    monkeypatch.setattr(S, "_download_to_file",
                        lambda url, dest, progress=None: "rossz")
    with pytest.raises(RuntimeError) as e:
        S._letolt_ellenorizve("u", tmp_path / "Setup.exe", "jo", varakozas=0)
    assert "manipulált" in str(e.value)
    assert not (tmp_path / "Setup.exe").exists()


class _Valasz(io.BytesIO):
    def __init__(self, adat, hossz):
        super().__init__(adat)
        self.headers = {"Content-Length": str(hossz)}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_csonka_letoltes_felismerese(tmp_path, monkeypatch):
    monkeypatch.setattr(S.urllib.request, "urlopen",
                        lambda req, timeout=60: _Valasz(b"a" * 1000, 5000))
    with pytest.raises(S.FelbeszakadtLetoltes):
        S._download_to_file("http://x", tmp_path / "f")


def test_folyamatjelzo_csak_szazalekvaltaskor(tmp_path, monkeypatch):
    adat = b"a" * (65536 * 300)                 # 300 darab
    monkeypatch.setattr(S.urllib.request, "urlopen",
                        lambda req, timeout=60: _Valasz(adat, len(adat)))
    hivasok = []
    S._download_to_file("http://x", tmp_path / "f", hivasok.append)
    assert len(hivasok) <= 101
    assert hivasok[-1] == 1.0
