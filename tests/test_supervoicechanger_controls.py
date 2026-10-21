"""Az élő hangváltoztató új tempóvezérlésének célzott próbája."""

from modules_src.supermedia.supermedia_mod import supervoicechanger as voice
from modules_src.supermedia.supermedia_mod import superm_fx as effects
from ctypes import cast, POINTER


def test_tempo_is_independent_from_pitch_and_clamped(monkeypatch):
    calls = []

    class Bass:
        def BASS_ChannelSetAttribute(self, channel, attribute, value):
            calls.append((channel, attribute, value.value))
            return 1

    monkeypatch.setattr(voice.A, "_lib", lambda: Bass())
    changer = voice.VoiceChanger()
    changer._tempo = 42
    changer.set_pitch(-4)
    changer.set_tempo(100)
    assert changer.pitch == -4
    assert changer.tempo == 30
    assert calls[0][:2] == (42, voice.BASS_ATTRIB_TEMPO_PITCH)
    assert calls[1] == (42, voice.BASS_ATTRIB_TEMPO, 30.0)


def test_presets_do_not_reference_unknown_effects():
    available = {effect for _, effect in voice.EFFECTS}
    for pitch, tempo, effects in voice.PRESETS.values():
        assert -12 <= pitch <= 12
        assert -30 <= tempo <= 30
        assert set(effects) <= available
        assert all(0 <= amount <= 100 for amount in effects.values())


def test_echo_delay_and_feedback_are_independent(monkeypatch):
    captured = {}

    class Bass:
        def BASS_FXGetParameters(self, handle, ptr):
            echo = cast(ptr, POINTER(effects._DX8_ECHO)).contents
            echo.fLeftDelay = echo.fRightDelay = 500
            echo.fFeedback = 50
            return 1

        def BASS_FXSetParameters(self, handle, ptr):
            echo = cast(ptr, POINTER(effects._DX8_ECHO)).contents
            captured.update(delay=echo.fLeftDelay, right=echo.fRightDelay,
                            feedback=echo.fFeedback)
            return 1

    monkeypatch.setattr(effects, "_bass", lambda: Bass())
    assert effects.set_effect_params(12, effects.DX8_ECHO, 40,
                                     {"delay": 160, "feedback": 70})
    assert captured == {"delay": 160, "right": 160, "feedback": 70}


def test_equalizer_character_uses_real_bass_effect_type(monkeypatch):
    types = []

    class Bass:
        def BASS_ChannelSetFX(self, channel, effect_type, priority):
            types.append(effect_type)
            return 12

    monkeypatch.setattr(effects, "_bass", lambda: Bass())
    assert effects.apply_effect(42, effects.EQ_BASS) == 12
    assert effects.apply_effect(42, effects.EQ_DARK) == 12
    assert types == [effects.DX8_PARAMEQ, effects.DX8_PARAMEQ]


def test_distortion_and_compressor_details_remain_within_bass_ranges(monkeypatch):
    captured = {}

    class Bass:
        def BASS_FXGetParameters(self, handle, ptr):
            return 1

        def BASS_FXSetParameters(self, handle, ptr):
            if handle == 1:
                s = cast(ptr, POINTER(effects._DX8_DISTORTION)).contents
                captured["distortion"] = (s.fEdge, s.fPostEQCenterFrequency,
                                           s.fPreLowpassCutoff)
            else:
                s = cast(ptr, POINTER(effects._DX8_COMPRESSOR)).contents
                captured["compressor"] = (s.fThreshold, s.fRatio,
                                           s.fAttack, s.fRelease)
            return 1

    monkeypatch.setattr(effects, "_bass", lambda: Bass())
    assert effects.set_effect_params(1, effects.DX8_DISTORTION, 45,
                                     {"edge": 65, "color": 3400, "lowpass": 4000})
    assert effects.set_effect_params(2, effects.DX8_COMPRESSOR, 50,
                                     {"threshold": -26, "ratio": 7,
                                      "attack": 8, "release": 300})
    assert captured == {"distortion": (65, 3400, 4000),
                        "compressor": (-26, 7, 8, 300)}


def test_natural_pitch_routes_mono_pcm_before_bass(monkeypatch):
    from ctypes import create_string_buffer

    sent = []

    class Bass:
        def BASS_StreamPutData(self, handle, data, length):
            sent.append((handle, voice.C.string_at(data, length)))
            return length

        def BASS_ChannelSetAttribute(self, channel, attribute, value):
            sent.append((attribute, value.value))
            return 1

    class Stretch:
        max_frames = 2

        def __init__(self):
            self.calls = []

        def set_pitch(self, value):
            self.calls.append(("pitch", value))

        def process(self, data, output, frames):
            self.calls.append(("frames", frames))
            voice.C.memmove(output, data, frames * 2)

    monkeypatch.setattr(voice.A, "_lib", lambda: Bass())
    changer = voice.VoiceChanger(natural_pitch=True)
    changer._stretch = Stretch()
    changer._stretch_buffer = create_string_buffer(4)
    changer._push = 9
    changer._tempo = 8
    changer.set_pitch(4)
    assert sent[-1] == (voice.BASS_ATTRIB_TEMPO_PITCH, 0.0)
    pcm = (voice.C.c_int16 * 5)(1, 2, 3, 4, 5)
    changer._record_cb(0, voice.C.addressof(pcm), 10, None)
    assert [item[1] for item in sent[1:]] == [b"\x01\x00\x02\x00",
                                             b"\x03\x00\x04\x00", b"\x05\x00"]
    assert changer._stretch.calls == [("pitch", 4.0), ("frames", 2),
                                      ("frames", 2), ("frames", 1)]


def test_natural_pitch_failure_keeps_microphone_audible(monkeypatch):
    sent = []

    class Bass:
        def BASS_StreamPutData(self, handle, data, length):
            sent.append(voice.C.string_at(data, length))
            return length

    class BrokenStretch:
        max_frames = 128

        def process(self, *_):
            raise RuntimeError("processor failed")

    monkeypatch.setattr(voice.A, "_lib", lambda: Bass())
    changer = voice.VoiceChanger(natural_pitch=True)
    changer._stretch = BrokenStretch()
    changer._stretch_buffer = voice.C.create_string_buffer(256)
    changer._push = 9
    pcm = (voice.C.c_int16 * 2)(123, 456)
    changer._record_cb(0, voice.C.addressof(pcm), 4, None)
    assert changer._stretch_failed
    assert sent == [voice.C.string_at(pcm, 4)]
