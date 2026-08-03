# -*- coding: utf-8 -*-
"""Felirat-felolvasó: a WebVTT óra nélküli (MM:SS.mmm) időbélyege.

Herman Tibor média-audit SUB-P1-05: a _TS regex kötelezően óra:perc:mp alakot
várt, ezért a szabványos WebVTT rövid cue-időpontokból (pl. 00:12.500) nulla
vagy részleges felirat készült."""
import pytest

S = pytest.importorskip("modules_src.felolvaso.felolvaso_mod.subtitles")


def test_webvtt_ora_nelkuli_idobelyeg():
    vtt = "WEBVTT\n\n00:01.000 --> 00:03.500\nSzia világ\n"
    cues = S.parse_srt(vtt)
    assert len(cues) == 1
    assert abs(cues[0].start - 1.0) < 0.01
    assert abs(cues[0].end - 3.5) < 0.01
    assert cues[0].text == "Szia világ"


def test_oras_es_ora_nelkuli_vegyes():
    txt = ("1\n01:02:03,250 --> 01:02:05,000\nÓrás sor\n\n"
           "2\n00:10.000 --> 00:12.000\nÓra nélküli sor\n")
    cues = S.parse_srt(txt)               # a parse_srt start szerint RENDEZ
    assert len(cues) == 2
    starts = sorted(c.start for c in cues)
    assert abs(starts[0] - 10.0) < 0.01                       # óra nélküli
    assert abs(starts[1] - (3600 + 120 + 3.25)) < 0.01        # órás
    nohour = next(c for c in cues if abs(c.start - 10.0) < 0.01)
    assert nohour.text == "Óra nélküli sor"


def test_klasszikus_srt_valtozatlan():
    srt = "1\n00:00:01,000 --> 00:00:02,000\nRendes SRT\n"
    cues = S.parse_srt(srt)
    assert len(cues) == 1
    assert abs(cues[0].start - 1.0) < 0.01
