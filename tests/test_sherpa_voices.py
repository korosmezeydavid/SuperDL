"""A gépen lévő Sherpa-hangok listája és a forrásmegjelölés."""

import json
import sys
from types import SimpleNamespace

from superdl import audiobook, sherpa_voices, tts


def _piper(root, slug, name):
    folder = root / slug
    folder.mkdir()
    (folder / "voice.json").write_text(json.dumps({
        "engine": "vits",
        "name": name,
        "language": "hu_HU",
        "default_speaker": 0,
    }), encoding="utf-8")
    (folder / "MODEL_CARD").write_text(
        "# card\n* URL: https://github.com/NabuCasa/voice-datasets\n"
        "* License: CC0\n", encoding="utf-8")


def test_a_lista_forrast_es_licencet_mond(tmp_path):
    _piper(tmp_path, "catalog-vits-piper-hu_HU-imre-medium", "imre")
    _piper(tmp_path, "catalog-vits-piper-hu_HU-anna-medium", "anna")
    super_dir = tmp_path / "catalog-sherpa-onnx-supertonic"
    super_dir.mkdir()
    (super_dir / "voice.json").write_text(json.dumps({
        "engine": "supertonic",
        "name": "Supertonic 3",
        "speakers": {"1": "Speaker 2", "0": "Speaker 1"},
    }), encoding="utf-8")
    (super_dir / "LICENSE").write_text(
        "MIT License\nCopyright (c) 2025 Supertone Inc.\n", encoding="utf-8")
    tiny = tmp_path / "catalog-tinytts-english-onnx"
    tiny.mkdir()
    (tiny / "voice.json").write_text(json.dumps({
        "engine": "tinytts",
        "name": "TinyTTS English",
        "language": "en_us",
    }), encoding="utf-8")

    voices = sherpa_voices.discover([tmp_path])
    nevek = [v.name for v in voices]
    assert nevek[0].startswith("Anna, magyar")
    assert "CC0" in nevek[0]
    assert "NabuCasa" in nevek[0]
    assert nevek[1].startswith("Imre, magyar")
    assert any(n.startswith("Supertonic 3, beszélő 1") for n in nevek)
    assert any("MIT" in n and "Supertone" in n for n in nevek)
    assert any("TinyTTS" in n and "nem szólaltatja meg" in n for n in nevek)
    anna = voices[0]
    assert "CC0" in anna.source
    assert "Apache 2.0" in anna.source
    assert anna.playable
    assert not voices[-1].playable


def test_a_konyv_vege_kimondja_a_hang_forrasat():
    eng = SimpleNamespace(source_line=lambda _vid: "Piper Anna, licenc: CC0.")
    zaro = audiobook.zaro_szoveg(eng, "barmilyen")
    assert zaro.startswith(audiobook.OUTRO)
    assert "A felolvasó hang forrása: Piper Anna, licenc: CC0." in zaro
    assert audiobook.zaro_szoveg(SimpleNamespace(), "x") == audiobook.OUTRO


def test_a_hangoskonyv_motorjai_koze_bekerult():
    assert "sherpa" in tts.ENGINES
    assert tts.ENGINES["sherpa"].needs_key is False
    sys.path.insert(0, "modules_src/konyvek")
    from konyvek_mod import bookwin
    assert bookwin.ENGINE_ORDER[0] == "sherpa"
    assert "edge" in bookwin.ENGINE_ORDER
    from konyvek_mod import readerwin
    assert readerwin.READ_ENGINE_KEYS[0] == "sherpa"
    assert "edge" in readerwin.READ_ENGINE_KEYS


def test_a_hangminta_pont_vesszo_felkialto_es_kerdojel():
    szoveg = tts.PREVIEW_TEXT
    assert szoveg.index(".") < szoveg.index(",")
    assert szoveg.index(",") < szoveg.index("!")
    assert szoveg.index("!") < szoveg.index("?")
    assert "Hang meghallgatása" in (
        open("modules_src/konyvek/konyvek_mod/readerwin.py", encoding="utf-8").read())
    assert "Hang meghallgatása" in (
        open("modules_src/konyvek/konyvek_mod/bookwin.py", encoding="utf-8").read())


def test_a_sajat_mappa_es_a_piper_kartya(tmp_path, monkeypatch):
    monkeypatch.setattr(sherpa_voices, "home_root", lambda: tmp_path)
    folder = tmp_path / "voices" / "anna"
    folder.mkdir(parents=True)
    (folder / "hu.onnx").write_bytes(b"x")
    (folder / "tokens.txt").write_text("a\n", encoding="utf-8")
    offer = sherpa_voices.offer_by_id("vits-piper-hu_HU-anna-medium")
    sherpa_voices._write_voice_config(folder, offer)
    found = sherpa_voices.discover()
    assert found and "CC0" in found[0].source
    assert "NabuCasa" in found[0].source
    assert "Hangok letöltése" in (
        open("modules_src/konyvek/konyvek_mod/readerwin.py", encoding="utf-8").read())
    assert "Hangok letöltése" in (
        open("modules_src/konyvek/konyvek_mod/bookwin.py", encoding="utf-8").read())


def test_a_csomag_nem_loghat_ki(tmp_path):
    archive = tmp_path / "rossz.tar.bz2"
    import tarfile
    with tarfile.open(archive, "w:bz2") as package:
        info = tarfile.TarInfo("../kint.txt")
        package.addfile(info, __import__("io").BytesIO(b"x"))
    try:
        sherpa_voices._extract(archive, tmp_path / "cel")
    except RuntimeError as exc:
        assert "kilóg" in str(exc)
    else:
        raise AssertionError("a kilógó csomagot el kell utasítani")


def test_a_tinytts_nem_szolal_meg(tmp_path):
    try:
        sherpa_voices.synthesize(
            "tinytts\tC:\\nincs\t0\ten", "Hello", str(tmp_path / "x"))
    except RuntimeError as exc:
        assert "TinyTTS" in str(exc)
        assert "Piper" in str(exc)
    else:
        raise AssertionError("a TinyTTS-nek el kell utasítania a felolvasást")
