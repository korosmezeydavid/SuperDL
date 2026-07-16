"""felolvaso.ytsource: YouTube-link → hang-stream + felirat kiválasztás.
A hálózatot NEM használjuk (mockolt info/fetch) – CI-biztos."""

import pytest

Y = pytest.importorskip("modules_src.felolvaso.felolvaso_mod.ytsource")


def test_is_url():
    assert Y.is_url("https://youtu.be/x") and Y.is_url("www.youtube.com/x")
    assert not Y.is_url("film.mp4") and not Y.is_url("")


def test_best_audio_url_valaszt():
    info = {"formats": [
        {"acodec": "opus", "vcodec": "none", "abr": 70, "url": "A70"},
        {"acodec": "opus", "vcodec": "none", "abr": 130, "url": "A130"},
        {"acodec": "aac", "vcodec": "h264", "abr": 200, "url": "V200"}]}
    assert Y._best_audio_url(info) == "A130"      # a legjobb HANG-only


def test_best_audio_url_tartalek():
    # nincs tiszta hang-only → bármely url, végül a fő url
    assert Y._best_audio_url({"formats": [], "url": "MAIN"}) == "MAIN"


def test_pick_sub_entry_srt_elonyben():
    tl = [{"ext": "vtt", "url": "v"}, {"ext": "srt", "url": "s"},
          {"ext": "json3", "url": "j"}]
    assert Y._pick_sub_entry(tl)["url"] == "s"
    # ha nincs srt/vtt, az első url-es
    assert Y._pick_sub_entry([{"ext": "json3", "url": "j"}])["url"] == "j"
    assert Y._pick_sub_entry([]) is None


def test_load_subs_manualis_elonyben(monkeypatch):
    monkeypatch.setattr(Y, "_fetch_text",
                        lambda url: "1\n00:00:01,000 --> 00:00:02,000\nSzia\n")
    info = {"subtitles": {"hu": [{"ext": "srt", "url": "m"}]},
            "automatic_captions": {"hu": [{"ext": "srt", "url": "a"}]}}
    cues, lang = Y._load_subs(info, ("hu", "en"))
    assert len(cues) == 1 and "manuális" in lang and "hu" in lang


def test_load_subs_csak_auto(monkeypatch):
    monkeypatch.setattr(Y, "_fetch_text",
                        lambda url: "1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    info = {"automatic_captions": {"hu": [{"ext": "srt", "url": "a"}]}}
    cues, lang = Y._load_subs(info, ("hu", "en"))
    assert len(cues) == 1 and "auto" in lang


def test_load_subs_nyelv_sorrend(monkeypatch):
    monkeypatch.setattr(Y, "_fetch_text",
                        lambda url: "1\n00:00:01,000 --> 00:00:02,000\nx\n")
    # csak angol elérhető → azt hozza, ha a hu üres
    info = {"subtitles": {"en": [{"ext": "srt", "url": "e"}]}}
    _cues, lang = Y._load_subs(info, ("hu", "en"))
    assert "en" in lang


def test_load_subs_nincs_felirat():
    cues, lang = Y._load_subs({"formats": []}, ("hu", "en"))
    assert cues == [] and lang == ""
