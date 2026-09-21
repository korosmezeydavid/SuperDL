# -*- coding: utf-8 -*-
"""A hangoskönyv-készítés hibája legyen MEGFEJTHETŐ.

Dr. Kiss István, 2026-09-16: „hibaüzenettel megszakadt a könyvkészítés" —
és a hozzá csatolt diagnosztikai jelentésben SEMMI nyoma nem volt. Két ok:

1. a `bookwin` hibaága nem naplózott, csak a felhasználónak szólt;
2. minden ffmpeg-hívás `-loglevel quiet` volt, tehát maga az ffmpeg sem
   mondta meg, mi a baja — a kivétel szövege ennyi lett volna:
   „Command '[...]' returned non-zero exit status 1."
"""
import subprocess
from pathlib import Path

import pytest

from superdl import audiobook

GYOKER = Path(__file__).resolve().parent.parent


class _Eredmeny:
    def __init__(self, kod, err=b""):
        self.returncode = kod
        self.stdout = b""
        self.stderr = err


def test_sikeres_hivas_nem_dob(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _Eredmeny(0))
    audiobook._ffmpeg(["ffmpeg"], 0, "Próba")      # nem dobhat


def test_a_hiba_tartalmazza_az_ffmpeg_indoklasat(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _Eredmeny(
            1, "valami zaj\nNo space left on device\n".encode("utf-8")))
    with pytest.raises(RuntimeError) as hiba:
        audiobook._ffmpeg(["ffmpeg"], 0, "A hangoskönyv összefűzése")
    szoveg = str(hiba.value)
    assert "A hangoskönyv összefűzése" in szoveg
    assert "No space left on device" in szoveg


def test_nema_ffmpeg_eseten_is_ertelmes(monkeypatch):
    """Ha az ffmpeg tényleg nem mond semmit, azt MONDJUK KI — ne úgy nézzen
    ki, mintha elfelejtettük volna megkérdezni."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Eredmeny(1))
    with pytest.raises(RuntimeError) as hiba:
        audiobook._ffmpeg(["ffmpeg"], 0, "Próba")
    assert "nem mondta meg" in str(hiba.value)


def test_csak_az_utolso_sorokat_tartja_meg(monkeypatch):
    """Az ffmpeg fecseg; a jelentésbe ne kerüljön be ötven sor."""
    sok = "\n".join("sor %d" % i for i in range(50)).encode("utf-8")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Eredmeny(1, sok))
    with pytest.raises(RuntimeError) as hiba:
        audiobook._ffmpeg(["ffmpeg"], 0, "Próba")
    szoveg = str(hiba.value)
    assert "sor 49" in szoveg
    assert "sor 0" not in szoveg


# --- a néma ffmpeg nem térhet vissza -----------------------------------

_FORRAS = (GYOKER / "superdl" / "audiobook.py").read_text(encoding="utf-8")


def test_egyetlen_ffmpeg_hivas_sem_nema():
    """`-loglevel quiet` + `check=True` együtt: ez volt a megfejthetetlen
    hiba receptje. Ha valaha visszakerül, ez a teszt megbukik."""
    assert '"quiet"' not in _FORRAS, (
        "Maradt néma ffmpeg-hívás az audiobook.py-ban.")


def test_minden_ffmpeg_hivas_a_burkolaton_megy():
    """Közvetlen `subprocess.run([ff, …])` megkerülné a hibakezelést."""
    rossz = [s.strip() for s in _FORRAS.splitlines()
             if "subprocess.run(" in s and "def _ffmpeg" not in s]
    # a burkolaton belüli EGYETLEN hívás megengedett
    assert len(rossz) == 1, "Burkolat nélküli ffmpeg-hívás: %r" % rossz


# --- a modul naplózza a hibát ------------------------------------------

_BOOKWIN = (GYOKER / "modules_src" / "konyvek" / "konyvek_mod"
            / "bookwin.py").read_text(encoding="utf-8")


def _keszites_blokk() -> str:
    """A KÉSZÍTÉS háttérszála. ⚠️ Több `def work():` van a fájlban (a hangok
    betöltése is így hívja a sajátját) — ezért a `audiobook.build` hívásához
    kötjük, nem a függvény nevéhez. Az első változat a hanglistát vizsgálta,
    és ettől úgy nézett ki, mintha a javítás nem is lenne benne."""
    return _BOOKWIN.split("audiobook.build(", 1)[1].split(
        "threading.Thread", 1)[0]


def test_a_keszites_hibaja_a_naploba_kerul():
    assert "_log = logging.getLogger" in _BOOKWIN
    assert "_log.exception" in _keszites_blokk(), (
        "A hangoskönyv-készítés hibaága megint csak a felhasználónak szól.")


def test_a_naploba_a_darabolas_modja_is_bekerul():
    """A jelentésből eddig nem derült ki, fejezetenként vagy percenként
    darabolt-e — pedig pont ez a különbség számít."""
    resz = _keszites_blokk()
    assert "fejezetenkent" in resz and "split" in resz
