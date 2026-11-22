"""A gépen lévő Sherpa-hangok (Piper, Supertonic) felolvasása.

A hangok a felhasználó saját letöltései, tipikusan az NVDA Sonata Sherpa
Voices mappájából. A SuperDL nem másolja be a bővítmény kódját: a nyílt
sherpa-onnx C felületét hívja (Apache 2.0), a modell pedig a helyén marad.

Minden hanghoz készítő és licenc tartozik, hogy a listában látszódjon:
nyílt hang, nem idegen kereskedelmi felvétel.
"""

from __future__ import annotations

import ctypes
import json
import os
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

SHERPA_API_VERSION = "1.13.4"
_LOCK = threading.RLock()


@dataclass(frozen=True)
class SherpaVoice:
    engine: str
    config_path: str
    speaker: int
    lang: str
    name: str
    source: str
    playable: bool

    @property
    def voice_id(self) -> str:
        return "\t".join((self.engine, self.config_path, str(self.speaker), self.lang))


def voice_roots() -> list[Path]:
    """Mappák, ahol voice.json szerinti hangok vannak."""
    roots: list[Path] = []
    extra = (os.environ.get("SUPERDL_SHERPA_VOICES") or "").strip()
    if extra:
        roots.append(Path(extra))
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "nvda" / "sonataSherpaVoices" / "voices")
    seen = set()
    out = []
    for root in roots:
        key = os.path.normcase(os.path.abspath(root))
        if key in seen or not root.is_dir():
            continue
        seen.add(key)
        out.append(root)
    return out


def dll_path() -> Path | None:
    env = (os.environ.get("SUPERDL_SHERPA_DLL") or "").strip()
    if env and Path(env).is_file():
        return Path(env)
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    candidate = (Path(appdata) / "nvda" / "addons" / "sonataSherpaVoices"
                 / "synthDrivers" / "sonata_sherpa" / "engine"
                 / "sherpa-onnx-c-api.dll")
    return candidate if candidate.is_file() else None


def discover(roots: list[Path] | None = None) -> list[SherpaVoice]:
    found: list[SherpaVoice] = []
    for root in roots if roots is not None else voice_roots():
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            cfg_path = folder / "voice.json"
            if folder.is_dir() and cfg_path.is_file():
                found.extend(_voices_in(cfg_path))
    found.sort(key=_sort_key)
    return found


def source_for(voice_id: str) -> str:
    try:
        engine, config_path, _speaker, _lang = _parse_id(voice_id)
    except ValueError:
        return ""
    for voice in discover():
        if voice.voice_id == voice_id:
            return voice.source
    if engine == "vits":
        return _piper_source(Path(config_path))
    return ""


def synthesize(voice_id: str, text: str, out_base: str, pitch: int = 0,
               rate: int = 0) -> str:
    """Egy szövegdarabot 16 bites mono WAV-ba ír. A fájl útját adja vissza."""
    engine, config_path, speaker, lang = _parse_id(voice_id)
    if engine == "tinytts":
        raise RuntimeError(
            "A TinyTTS angol hang a gépen megvan, de a motorja a Sonata "
            "bővítmény saját kódja. A SuperDL a nyílt Piper és Supertonic "
            "hangokat szólaltatja meg.")
    if engine not in ("vits", "supertonic"):
        raise RuntimeError("Ezt a Sherpa-motort a SuperDL nem ismeri: %s" % engine)
    text = " ".join((text or "").split())
    if not text:
        raise RuntimeError("Üres a felolvasandó szöveg.")
    speed = max(0.5, min(2.0, 1.0 + int(rate or 0) * 0.08))
    with _LOCK:
        handle = _engine_for(config_path)
        pcm, sample_rate = handle.generate(text, speaker, lang, speed)
    if pitch:
        pcm = _pitch(pcm, int(pitch))
    if not pcm:
        raise RuntimeError("A hang nem adott hangmintát erre a szövegre.")
    path = out_base + ".wav"
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return path


def _parse_id(voice_id: str) -> tuple[str, str, int, str]:
    parts = (voice_id or "").split("\t")
    if len(parts) != 4:
        raise ValueError("Ismeretlen Sherpa-hangazonosító.")
    try:
        speaker = int(parts[2])
    except ValueError as exc:
        raise ValueError("Ismeretlen Sherpa-hangazonosító.") from exc
    return parts[0], parts[1], speaker, parts[3]


def _sort_key(voice: SherpaVoice):
    family = {"vits": 0, "supertonic": 1, "tinytts": 2}.get(voice.engine, 9)
    return (family, voice.speaker, voice.name.lower())


def _voices_in(cfg_path: Path) -> list[SherpaVoice]:
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    engine = str(data.get("engine") or "vits").lower()
    if engine == "vits":
        return [_piper_voice(cfg_path, data)]
    if engine == "supertonic":
        return _supertonic_voices(cfg_path, data)
    if engine == "tinytts":
        return [_tiny_voice(cfg_path, data)]
    return []


def _piper_voice(cfg_path: Path, data: dict) -> SherpaVoice:
    raw_name = str(data.get("name") or cfg_path.parent.name)
    title = raw_name[:1].upper() + raw_name[1:]
    lang = str(data.get("language") or "")
    nyelv = _nyelv(lang)
    source = _piper_source(cfg_path)
    label = "%s, %s. Forrás: %s" % (title, nyelv or lang or "Piper", _rovid_forras(source))
    return SherpaVoice("vits", str(cfg_path), int(data.get("default_speaker") or 0),
                       lang, label, source, True)


def _piper_source(cfg_path: Path) -> str:
    lic, url = _model_card(cfg_path.parent / "MODEL_CARD")
    nev = cfg_path.parent.name
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        raw = str(data.get("name") or "")
        if raw:
            nev = raw[:1].upper() + raw[1:]
    except (OSError, json.JSONDecodeError):
        pass
    if not lic:
        lic = "a modell saját közlése"
    adat = url or "a hang mappájában lévő model card"
    return ("Piper „%s”. Adatkészlet: %s, licenc: %s. "
            "Nyílt hang, a sherpa-onnx (Apache 2.0) futtatja a saját gépedről."
            % (nev, adat, lic))


def _supertonic_voices(cfg_path: Path, data: dict) -> list[SherpaVoice]:
    speakers = data.get("speakers") or {"0": "Speaker 1"}
    source = ("Supertonic 3, Supertone Inc., MIT licenc (a modell mappájának "
              "LICENSE fájlja). Nyílt hang, a sherpa-onnx (Apache 2.0) "
              "futtatja a saját gépedről. Magyar szövegre van állítva.")
    out = []
    for key in sorted(speakers, key=lambda k: int(k) if str(k).isdigit() else 0):
        try:
            sid = int(key)
        except (TypeError, ValueError):
            continue
        cimke = _beszelo(str(speakers[key]), sid)
        label = ("%s, %s. Forrás: Supertone Inc., MIT. Magyar szövegre állítva."
                 % (str(data.get("name") or "Supertonic 3"), cimke))
        out.append(SherpaVoice("supertonic", str(cfg_path), sid, "hu", label, source, True))
    return out


def _tiny_voice(cfg_path: Path, data: dict) -> SherpaVoice:
    source = ("TinyTTS English. A hang a saját gépeden van, a Sonata Sherpa "
              "Voices töltötte le. A mappában külön licencfájl nincs, ezért "
              "a SuperDL nem szólaltatja meg; a Piper és a Supertonic hangok "
              "igen, azok licence a sorukban olvasható.")
    label = ("%s, angol. Forrás: a géped Sonata-hangja. A SuperDL ezt a motort "
             "nem szólaltatja meg." % str(data.get("name") or "TinyTTS English"))
    return SherpaVoice("tinytts", str(cfg_path), 0, str(data.get("language") or "en"),
                       label, source, False)


def _beszelo(raw: str, sid: int) -> str:
    text = (raw or "").strip()
    if text.lower().startswith("speaker"):
        return "beszélő %d" % (sid + 1)
    return text or ("beszélő %d" % (sid + 1))


def _nyelv(code: str) -> str:
    c = (code or "").replace("-", "_").lower()
    if c.startswith("hu"):
        return "magyar"
    if c.startswith("en"):
        return "angol"
    return code


def _rovid_forras(source: str) -> str:
    """A lista sorába a licenc eleje, a teljes mondat a forrásmezőben marad."""
    if "Adatkészlet:" in source and "licenc:" in source:
        adat = source.split("Adatkészlet:", 1)[1]
        adat = adat.split(". Nyílt hang", 1)[0].strip()
        return adat
    return source


def _model_card(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "", ""
    lic = url = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "", ""
    for line in lines:
        item = line.strip().lstrip("*").strip()
        low = item.lower()
        if low.startswith("license:"):
            lic = item.split(":", 1)[1].strip()
        elif low.startswith("url:"):
            url = item.split(":", 1)[1].strip()
    return lic, url


# ----------------------------------------------------------------------
# sherpa-onnx 1.13.4 C felület. A mezők sorrendje a kiadott c-api.h
# OfflineTts struktúráit követi; a Sonata Python-kódját nem használjuk.

class _Vits(ctypes.Structure):
    _fields_ = [("model", ctypes.c_char_p), ("lexicon", ctypes.c_char_p),
                ("tokens", ctypes.c_char_p), ("data_dir", ctypes.c_char_p),
                ("noise_scale", ctypes.c_float), ("noise_scale_w", ctypes.c_float),
                ("length_scale", ctypes.c_float), ("dict_dir", ctypes.c_char_p)]


class _Matcha(ctypes.Structure):
    _fields_ = [("acoustic_model", ctypes.c_char_p), ("vocoder", ctypes.c_char_p),
                ("lexicon", ctypes.c_char_p), ("tokens", ctypes.c_char_p),
                ("data_dir", ctypes.c_char_p), ("noise_scale", ctypes.c_float),
                ("length_scale", ctypes.c_float), ("dict_dir", ctypes.c_char_p)]


class _Kokoro(ctypes.Structure):
    _fields_ = [("model", ctypes.c_char_p), ("voices", ctypes.c_char_p),
                ("tokens", ctypes.c_char_p), ("data_dir", ctypes.c_char_p),
                ("length_scale", ctypes.c_float), ("dict_dir", ctypes.c_char_p),
                ("lexicon", ctypes.c_char_p), ("lang", ctypes.c_char_p)]


class _Kitten(ctypes.Structure):
    _fields_ = [("model", ctypes.c_char_p), ("voices", ctypes.c_char_p),
                ("tokens", ctypes.c_char_p), ("data_dir", ctypes.c_char_p),
                ("length_scale", ctypes.c_float)]


class _Zipvoice(ctypes.Structure):
    _fields_ = [("tokens", ctypes.c_char_p), ("encoder", ctypes.c_char_p),
                ("decoder", ctypes.c_char_p), ("vocoder", ctypes.c_char_p),
                ("data_dir", ctypes.c_char_p), ("lexicon", ctypes.c_char_p),
                ("feat_scale", ctypes.c_float), ("t_shift", ctypes.c_float),
                ("target_rms", ctypes.c_float), ("guidance_scale", ctypes.c_float)]


class _Pocket(ctypes.Structure):
    _fields_ = [("lm_flow", ctypes.c_char_p), ("lm_main", ctypes.c_char_p),
                ("encoder", ctypes.c_char_p), ("decoder", ctypes.c_char_p),
                ("text_conditioner", ctypes.c_char_p), ("vocab_json", ctypes.c_char_p),
                ("token_scores_json", ctypes.c_char_p),
                ("voice_embedding_cache_capacity", ctypes.c_int32)]


class _Supertonic(ctypes.Structure):
    _fields_ = [("duration_predictor", ctypes.c_char_p),
                ("text_encoder", ctypes.c_char_p),
                ("vector_estimator", ctypes.c_char_p),
                ("vocoder", ctypes.c_char_p), ("tts_json", ctypes.c_char_p),
                ("unicode_indexer", ctypes.c_char_p),
                ("voice_style", ctypes.c_char_p)]


class _Model(ctypes.Structure):
    _fields_ = [("vits", _Vits), ("num_threads", ctypes.c_int32),
                ("debug", ctypes.c_int32), ("provider", ctypes.c_char_p),
                ("matcha", _Matcha), ("kokoro", _Kokoro), ("kitten", _Kitten),
                ("zipvoice", _Zipvoice), ("pocket", _Pocket),
                ("supertonic", _Supertonic)]


class _Config(ctypes.Structure):
    _fields_ = [("model", _Model), ("rule_fsts", ctypes.c_char_p),
                ("max_num_sentences", ctypes.c_int32),
                ("rule_fars", ctypes.c_char_p), ("silence_scale", ctypes.c_float)]


class _Audio(ctypes.Structure):
    _fields_ = [("samples", ctypes.POINTER(ctypes.c_float)),
                ("n", ctypes.c_int32), ("sample_rate", ctypes.c_int32)]


class _Generation(ctypes.Structure):
    _fields_ = [("silence_scale", ctypes.c_float), ("speed", ctypes.c_float),
                ("sid", ctypes.c_int32),
                ("reference_audio", ctypes.POINTER(ctypes.c_float)),
                ("reference_audio_len", ctypes.c_int32),
                ("reference_sample_rate", ctypes.c_int32),
                ("reference_text", ctypes.c_char_p),
                ("num_steps", ctypes.c_int32), ("extra", ctypes.c_char_p)]


_TTS_CALLBACK = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.POINTER(ctypes.c_float), ctypes.c_int32,
    ctypes.c_float, ctypes.c_void_p)


@_TTS_CALLBACK
def _keep_going(samples, count, progress, arg):
    return 1


class _Native:
    def __init__(self):
        self.dll = None
        self.dir_cookie = None
        self.tts = None
        self.key = ""
        self.kind = ""
        self.kept: list[bytes] = []

    def _library(self):
        if self.dll is not None:
            return
        path = dll_path()
        if path is None:
            raise RuntimeError(
                "A sherpa-onnx motor nincs a gépen. A Piper és Supertonic "
                "hangok az NVDA Sonata Sherpa Voices bővítményével együtt "
                "érkező sherpa-onnx-c-api.dll-t használják.")
        if hasattr(os, "add_dll_directory"):
            self.dir_cookie = os.add_dll_directory(os.fspath(path.parent))
        self.dll = ctypes.CDLL(os.fspath(path))
        lib = self.dll
        lib.SherpaOnnxGetVersionStr.restype = ctypes.c_char_p
        actual = lib.SherpaOnnxGetVersionStr().decode("ascii")
        if actual != SHERPA_API_VERSION:
            self.dll = None
            raise RuntimeError(
                "A sherpa-onnx verziója %s, a SuperDL a %s felületet ismeri."
                % (actual, SHERPA_API_VERSION))
        lib.SherpaOnnxCreateOfflineTts.argtypes = [ctypes.POINTER(_Config)]
        lib.SherpaOnnxCreateOfflineTts.restype = ctypes.c_void_p
        lib.SherpaOnnxDestroyOfflineTts.argtypes = [ctypes.c_void_p]
        lib.SherpaOnnxOfflineTtsGenerateWithConfig.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(_Generation),
            _TTS_CALLBACK, ctypes.c_void_p]
        lib.SherpaOnnxOfflineTtsGenerateWithConfig.restype = ctypes.POINTER(_Audio)
        lib.SherpaOnnxDestroyOfflineTtsGeneratedAudio.argtypes = [
            ctypes.POINTER(_Audio)]

    def _pin(self, text: str | None) -> bytes | None:
        if not text:
            return None
        raw = os.fspath(text).encode("utf-8")
        self.kept.append(raw)
        return raw

    def _file(self, root: Path, name: str | None) -> str | None:
        if not name:
            return None
        path = Path(name)
        if not path.is_absolute():
            path = (root / path).resolve()
        if path.exists():
            return str(path)
        return None

    def ensure(self, config_path: str) -> None:
        self._library()
        key = os.path.normcase(os.path.abspath(config_path))
        if self.tts and self.key == key:
            return
        if self.tts:
            self.dll.SherpaOnnxDestroyOfflineTts(self.tts)
            self.tts = None
        self.kept = []
        root = Path(config_path).parent
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        kind = str(data.get("engine") or "vits").lower()
        model = _Model()
        model.num_threads = 2
        model.debug = 0
        model.provider = self._pin("cpu")
        if kind == "supertonic":
            need = {
                "duration_predictor": data.get("duration_predictor"),
                "text_encoder": data.get("text_encoder"),
                "vector_estimator": data.get("vector_estimator"),
                "vocoder": data.get("vocoder"),
                "tts_json": data.get("tts_json") or "tts.json",
                "unicode_indexer": data.get("unicode_indexer"),
                "voice_style": data.get("voice_style") or "voice.bin",
            }
            files = {k: self._file(root, v) for k, v in need.items()}
            missing = [k for k, v in files.items() if not v]
            if missing:
                raise RuntimeError("Hiányzik a Supertonic fájl: " + ", ".join(missing))
            model.supertonic = _Supertonic(
                self._pin(files["duration_predictor"]),
                self._pin(files["text_encoder"]),
                self._pin(files["vector_estimator"]),
                self._pin(files["vocoder"]),
                self._pin(files["tts_json"]),
                self._pin(files["unicode_indexer"]),
                self._pin(files["voice_style"]))
        elif kind == "vits":
            onnx = self._file(root, data.get("model"))
            tokens = self._file(root, data.get("tokens") or "tokens.txt")
            espeak = self._espeak(root, data.get("data_dir"))
            if not onnx or not tokens or not espeak:
                raise RuntimeError(
                    "A Piper hanghoz kell az onnx modell, a tokens.txt és az "
                    "espeak-ng-data mappa. Valamelyik hiányzik: %s" % root.name)
            model.vits = _Vits(
                self._pin(onnx), self._pin(self._file(root, data.get("lexicon"))),
                self._pin(tokens), self._pin(espeak),
                ctypes.c_float(0.667), ctypes.c_float(0.8), ctypes.c_float(1.0),
                self._pin(self._file(root, data.get("dict_dir"))))
        else:
            raise RuntimeError("Ezt a Sherpa-motort a SuperDL nem tölti be: %s" % kind)
        cfg = _Config()
        cfg.model = model
        cfg.max_num_sentences = 1
        cfg.silence_scale = ctypes.c_float(0.2)
        tts = self.dll.SherpaOnnxCreateOfflineTts(ctypes.byref(cfg))
        if not tts:
            raise RuntimeError("A sherpa-onnx nem tudta betölteni ezt a hangot: "
                               + root.name)
        self.tts = tts
        self.key = key
        self.kind = kind

    def _espeak(self, root: Path, data_dir: str | None) -> str | None:
        found = self._file(root, data_dir) if data_dir else None
        if found:
            return found
        shared = root.parent.parent / "shared" / "espeak-ng-data"
        if shared.is_dir():
            return str(shared)
        return None

    def generate(self, text: str, speaker: int, lang: str, speed: float):
        gen = _Generation()
        gen.silence_scale = ctypes.c_float(0.2)
        gen.speed = ctypes.c_float(speed)
        gen.sid = int(speaker)
        if self.kind == "supertonic":
            gen.num_steps = 5
            code = (lang or "hu").replace("_", "-").split("-", 1)[0].lower()
            gen.extra = self._pin(json.dumps({"lang": code}))
        audio = self.dll.SherpaOnnxOfflineTtsGenerateWithConfig(
            self.tts, text.encode("utf-8"), ctypes.byref(gen), _keep_going, None)
        if not audio:
            raise RuntimeError("A sherpa-onnx nem készített hangot.")
        try:
            block = audio.contents
            count = int(block.n)
            rate = int(block.sample_rate) or 22050
            if count <= 0:
                raise RuntimeError("A sherpa-onnx üres hangot adott.")
            import numpy as np
            samples = np.ctypeslib.as_array(block.samples, shape=(count,)).astype("float32")
            pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2").tobytes()
            return pcm, rate
        finally:
            self.dll.SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio)


_NATIVE = _Native()


def _engine_for(config_path: str) -> _Native:
    _NATIVE.ensure(config_path)
    return _NATIVE


def _pitch(pcm: bytes, steps: int) -> bytes:
    factor = 1.0 + max(-10, min(10, steps)) * 0.03
    if abs(factor - 1.0) < 0.001 or len(pcm) < 4:
        return pcm
    import numpy as np
    src = np.frombuffer(pcm, dtype="<i2").astype("float64")
    out_len = max(1, int(src.size / factor))
    pos = np.arange(out_len, dtype="float64") * factor
    out = np.interp(pos, np.arange(src.size, dtype="float64"), src)
    return np.clip(out, -32768, 32767).astype("<i2").tobytes()
