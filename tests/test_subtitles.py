"""felolvaso.subtitles: SRT/VTT feldolgozás, kódolás-felismerés, cue-ütemező,
mellé tett feliratfájl felismerése (M2 – felirat-felolvasó)."""

import pytest

subs = pytest.importorskip("modules_src.felolvaso.felolvaso_mod.subtitles")

SRT = """1
00:00:01,000 --> 00:00:03,500
Első felirat.

2
00:00:04,000 --> 00:00:06,000
<i>Dőlt</i> második {\\an8}sor.

3
00:00:10,000 --> 00:00:12,000
Harmadik.
"""

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
Egy VTT sor.

00:00:05.000 --> 00:00:07.000
Másik VTT sor.
"""


def test_parse_srt_alap():
    cues = subs.parse_srt(SRT)
    assert len(cues) == 3
    assert cues[0].start == 1.0 and cues[0].end == 3.5
    assert cues[0].text == "Első felirat."
    # a formázás (dőlt, ASS-pozíció) eltávolítva
    assert cues[1].text == "Dőlt második sor."


def test_parse_vtt():
    cues = subs.parse_srt(VTT)
    assert len(cues) == 2
    assert cues[0].start == 1.0 and cues[0].text == "Egy VTT sor."


def test_parse_ures_es_hibas_blokk():
    assert subs.parse_srt("") == []
    assert subs.parse_srt("csak szöveg\ntimestamp nélkül") == []


def test_decode_utf8_es_cp1250():
    txt = "Árvíztűrő őőűű"
    assert subs.decode_bytes(txt.encode("utf-8")) == txt
    # BOM-os UTF-8
    assert subs.decode_bytes(b"\xef\xbb\xbf" + txt.encode("utf-8")) == txt
    # CP1250-es magyar felirat
    assert subs.decode_bytes(txt.encode("cp1250")) == txt


def test_scheduler_sorban_egyszer():
    cues = subs.parse_srt(SRT)
    sch = subs.CueScheduler(cues)
    assert sch.next_due(0.5) is None                 # még semmi
    c = sch.next_due(1.2)
    assert c and c.text == "Első felirat."
    assert sch.next_due(1.5) is None                 # ugyanazt nem adja újra
    c2 = sch.next_due(4.5)
    assert c2 and c2.text.startswith("Dőlt")


def test_scheduler_lejart_feliratot_atugor():
    cues = subs.parse_srt(SRT)
    sch = subs.CueScheduler(cues)
    # rögtön a 10 mp-es pozícióra: az 1. és 2. rég lejárt → csak a 3. jön
    c = sch.next_due(10.5)
    assert c and c.text == "Harmadik."


def test_scheduler_reset_visszaugras():
    cues = subs.parse_srt(SRT)
    sch = subs.CueScheduler(cues)
    sch.next_due(11.0)                               # elfogyasztja mindet
    sch.reset_to(0.0)                                # visszaugrás az elejére
    c = sch.next_due(1.2)
    assert c and c.text == "Első felirat."


def test_find_sidecar_magyar_elorebb(tmp_path):
    (tmp_path / "Film.mp4").write_bytes(b"x")
    (tmp_path / "Film.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n",
                                          encoding="utf-8")
    (tmp_path / "Film.hu.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nszia\n",
                                          encoding="utf-8")
    found = subs.find_sidecar_subs(str(tmp_path / "Film.mp4"))
    assert len(found) == 2
    assert found[0].endswith("Film.hu.srt")          # a magyar előre sorolva


def test_load_subtitle_file_srt(tmp_path):
    p = tmp_path / "s.srt"
    p.write_text(SRT, encoding="utf-8")
    cues = subs.load_subtitle_file(str(p))
    assert len(cues) == 3 and cues[2].text == "Harmadik."
