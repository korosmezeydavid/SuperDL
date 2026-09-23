# -*- coding: utf-8 -*-
"""Három javítás a 4.6.12 utáni jelentésekből.

1. AZ ÚJRAINDÍTÁS, ami soha nem működött (Nagy Károly, Tóth Zoltán).
2. A HANGOSKÖNYV-LEJÁTSZÓ befagyása mappa megnyitásakor (Turai László).
3. A KIMONDHATATLAN SZÖVEGDARAB, ami az egész hangoskönyvet elbuktatta
   (Dr. Kiss István).

Mindhárom mérésből született, nem találgatásból – a méréseket a
`claude/windows-*.md` naplók őrzik.
"""

import inspect
import re

import pytest

from superdl import audiobook as AB
from superdl import coremod


# ======================================================================
# 1. AZ ÚJRAINDÍTÓ KÖTEGFÁJL
# ======================================================================

def _script(exe=r"C:\Program Files (x86)\SuperDL\SuperDL.exe", pid=4321):
    from pathlib import Path
    return coremod._restart_script(Path(exe), pid, Path(r"C:\tmp\u.log"))


def test_nincs_benne_csovezetek():
    """⚠️ Konzol nélküli cmd-ben a `tasklist | find` BERAGAD – a kötegfájl
    soha nem jut el az indításig."""
    sz = _script()
    assert "|" not in sz, "csővezeték maradt a kötegfájlban"


def test_a_varakozas_findstr_rel_megy():
    assert "findstr.exe" in _script()


def test_nincs_zarojeles_blok():
    """A `cmd` az `if … ( … )` blokkot egyben értelmezi, és a program útjában
    lévő zárójel (`Program Files (x86)`) elvágná."""
    sz = _script()
    for sor in sz.splitlines():
        s = sor.strip()
        assert not s.endswith("("), sor
        assert s != ")", sor


def test_naplot_ir_minden_fontos_pontrol():
    sz = _script()
    for kulcs in ("INDUL", "INDITAS", "KESZ", "HIBA", "IDOTULLEPES"):
        assert kulcs in sz, kulcs


def test_megnezi_hogy_megvan_e_a_program():
    assert "if exist" in _script().lower()


def test_a_zaszlopar_nem_kerulhet_vissza():
    """⚠️ MÉRVE: NO_WINDOW|DETACHED -> nem indult el 25 mp alatt;
    NO_WINDOW egyedül -> 6,8 mp alatt elindult."""
    src = inspect.getsource(coremod.restart_app)
    m = re.search(r"creationflags=([^)]+)\)", src)
    assert m, "nem találom a creationflags-et"
    assert "0x00000008" not in m.group(1), \
        "DETACHED_PROCESS visszakerült – ettől a cmd konzol nélkül marad"
    assert "0x08000000" in m.group(1)


def test_az_ujraindito_naplo_a_superdl_mappaban_van():
    assert coremod.ujraindit_naplo().name == "ujraindit.log"


# ======================================================================
# 2. A HANGOSKÖNYV-LEJÁTSZÓ MAPPA-BEJÁRÁSA
# ======================================================================

@pytest.fixture
def abwin():
    import sys
    sys.path.insert(0, "modules_src/konyvek")
    return pytest.importorskip("konyvek_mod.audiobookwin")


@pytest.fixture
def abplayer():
    import sys
    sys.path.insert(0, "modules_src/konyvek")
    return pytest.importorskip("konyvek_mod.audiobook_player")


def test_a_mappabejaras_nem_a_fo_szalon_megy(abwin):
    """⚠️ Turai László gépén a megakadás-figyelő verme pontosan ezt mutatta:
    `os.walk` ← `mappa_savok` ← `_open_any` ← a gomb lambdája ← MainLoop."""
    src = inspect.getsource(abwin.AudioBookFrame._open_any)
    assert "threading.Thread" in src
    assert "wx.CallAfter" in src
    # a magyarázó szöveget elhagyjuk, csak a KÓD számít
    kod = re.sub(r'""".*?"""', "", src, flags=re.S)
    # és a hívás a HÁTTÉRFÜGGVÉNYEN BELÜL van, nem előtte
    assert kod.count("mappa_savok(") == 1
    assert kod.index("def munka") < kod.index("mappa_savok(")


def test_a_bejaras_azonnal_visszajelez(abwin):
    """Vakon a néma várakozás megkülönböztethetetlen a lefagyástól."""
    src = inspect.getsource(abwin.AudioBookFrame._open_any)
    assert "keresése" in src.lower()


def test_a_bejaras_megallithato(abwin, abplayer):
    src = inspect.getsource(abplayer.mappa_savok)
    assert "megall" in src
    zaras = inspect.getsource(abwin.AudioBookFrame._on_close)
    assert "_bejaras_megall" in zaras


def test_a_megallitott_bejaras_uresen_ter_vissza(abplayer, tmp_path):
    import threading
    (tmp_path / "a.mp3").write_bytes(b"\0")
    e = threading.Event()
    e.set()
    assert abplayer.mappa_savok(str(tmp_path), e) == []


def test_bejaras_nelkul_ugyanugy_mukodik(abplayer, tmp_path):
    """A `megall` nem kötelező – a régi hívási alak nem törhet el."""
    (tmp_path / "b.mp3").write_bytes(b"\0")
    (tmp_path / "kotet").mkdir()
    (tmp_path / "kotet" / "a.mp3").write_bytes(b"\0")
    assert len(abplayer.mappa_savok(str(tmp_path))) == 2


def test_ket_bejaras_nem_indul_egyszerre(abwin):
    src = inspect.getsource(abwin.AudioBookFrame._open_any)
    assert "_bejaras_fut" in src


# ======================================================================
# 3. A KIMONDHATATLAN SZÖVEGDARAB
# ======================================================================

@pytest.mark.parametrize("szoveg", [".", "—————", "* * *", "   ", "", "…",
                                    "!?", "-- --"])
def test_a_csupa_irasjel_nem_mondhato(szoveg):
    """⚠️ MÉRVE: az Edge-TTS ezekre NoAudioReceived-et dob."""
    assert AB.mondhato(szoveg) is False


@pytest.mark.parametrize("szoveg", ["A", "1 2 3", "III.", "Ez egy mondat.",
                                    "— Jó napot!"])
def test_a_beszelheto_szoveg_mondhato(szoveg):
    assert AB.mondhato(szoveg) is True


def test_a_build_kiszuri_a_mondhatatlan_darabokat():
    src = inspect.getsource(AB.build)
    assert "mondhato" in src


def test_a_fejezet_hozzarendeles_egyutt_szurodik():
    """⚠️ Ha csak a `parts`-ból vennénk ki a darabot, a `part_fej` elcsúszna,
    és a fejezetenkénti összefűzés rossz helyen vágna."""
    src = inspect.getsource(AB.build)
    i = src.index("mondhato")
    korny = src[i - 400:i + 400]
    assert "part_fej" in korny


def test_a_hiba_megmondja_hanyadik_darabnal_akadt_el():
    src = inspect.getsource(AB.build)
    assert "szövegdarabnál akadt el" in src
    assert "A darab eleje" in src


def test_ures_konyvnel_ertheto_magyar_uzenet():
    src = inspect.getsource(AB.build)
    assert "nincs felolvasható tartalom" in src
