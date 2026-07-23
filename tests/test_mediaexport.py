# -*- coding: utf-8 -*-
"""Atomikus média-export: `.part` → ellenőrzés → csere.
Herman Tibi AUDIO-P0-04 / EDIT-P1-17 / RING-P0-04 / REC-P1-15."""
import os
import pathlib

from superdl import mediaexport as ME

ROOT = pathlib.Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_part_ugyanabban_a_mappaban_van():
    """Az atomikus cserének AZONOS köteten kell történnie."""
    final = os.path.join("C:", os.sep, "hang", "kimenet.mp3")
    p = ME.part_path(final)
    assert os.path.dirname(p) == os.path.dirname(final)
    assert p.endswith(".mp3") and ".part" in p


def test_part_nevek_egyediek():
    a, b = ME.part_path("x/y.mp3"), ME.part_path("x/y.mp3")
    assert a != b, "két párhuzamos export ugyanazt a part fájlt írná"


def test_ures_es_csonka_fajl_megbukik(tmp_path):
    p = tmp_path / "ures.mp3"
    p.write_bytes(b"")
    ok, indok = ME.verify_audio(str(p))
    assert ok is False and indok

    p2 = tmp_path / "csonka.mp3"
    p2.write_bytes(b"x" * 100)
    assert ME.verify_audio(str(p2))[0] is False


def test_nem_letezo_fajl_megbukik(tmp_path):
    assert ME.verify_audio(str(tmp_path / "nincs.mp3"))[0] is False


def test_commit_atomikusan_cserel(tmp_path):
    final = tmp_path / "vegleges.wav"
    final.write_bytes(b"REGI" * 300)
    part = tmp_path / "uj.part.wav"
    part.write_bytes(b"UJUJ" * 300)
    ME.commit(str(part), str(final))
    assert final.read_bytes().startswith(b"UJUJ")
    assert not part.exists(), "a part fájl nem tűnt el"


def test_cleanup_eltakaritja_a_felkeszet(tmp_path):
    part = tmp_path / "felkesz.part.mp3"
    part.write_bytes(b"x")
    ME.cleanup(str(part))
    assert not part.exists()
    ME.cleanup(str(part))          # kétszer hívva sem dobhat


def test_cleanup_ures_utvonalra_sem_dob():
    ME.cleanup("")


def test_ffprobe_az_ffmpeg_mellol(tmp_path):
    ff = tmp_path / "ffmpeg.exe"
    ff.write_bytes(b"x")
    assert ME.ffprobe_for(str(ff)) == ""       # nincs mellette ffprobe
    (tmp_path / "ffprobe.exe").write_bytes(b"x")
    assert ME.ffprobe_for(str(ff)).endswith("ffprobe.exe")


# ---- a tényleges bekötések ------------------------------------------------

def test_felvevo_mento_atomikus():
    src = _src("modules_src/supermedia/supermedia_mod/superrec.py")
    assert "mediaexport.part_path" in src, "a save_pcm közvetlenül a célra ír"
    assert "mediaexport.verify_audio" in src, "nincs kimenet-ellenőrzés"
    assert "mediaexport.commit" in src and "mediaexport.cleanup" in src


def test_csengohang_atomikus():
    src = _src("modules_src/mediatools/mediatools_mod/ringtone.py")
    assert "mediaexport.part_path" in src, "a csengőhang közvetlenül a célra ír"
    assert "mediaexport.verify_audio" in src
    assert "mediaexport.commit" in src


def test_a_regi_fajl_nem_serul_hibas_exportnal(tmp_path):
    """A lényeg: ha az ellenőrzés bukik, a MEGLÉVŐ fájl érintetlen marad."""
    final = tmp_path / "meglevo.mp3"
    final.write_bytes(b"EREDETI" * 200)
    eredeti = final.read_bytes()
    part = ME.part_path(str(final))
    pathlib.Path(part).write_bytes(b"")        # csonka render
    ok, _ = ME.verify_audio(part)
    assert ok is False
    ME.cleanup(part)                           # így NEM commitolunk
    assert final.read_bytes() == eredeti, "a régi fájl megsérült"
