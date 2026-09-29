"""Dávid döntése (2026-09-29): „Alapból legyen kikapcsolva a saját beszédhang,
ha érzékeli az olvasót." Futó NVDA/JAWS mellett a program saját hangja
(SelfVoice és az Edge/SAPI-felolvasó) hallgat, és a szöveget a képernyőolvasó
mondja. Olvasó nélkül minden marad a régiben."""

import inspect
import threading

from superdl import screenreader, selfvoice, speech
from superdl.selfvoice import SelfVoice


def _sv(monkeypatch):
    monkeypatch.setattr(selfvoice, "espeak_available", lambda: True)
    sv = SelfVoice()
    hits = []
    monkeypatch.setattr(sv, "_speak_espeak", lambda t: hits.append(t))
    sv.configure(muted=False, voice_desc="espeak:hu")
    return sv, hits


def _sr(monkeypatch, fut):
    mondta = []
    monkeypatch.setattr(screenreader, "running", lambda: fut)
    monkeypatch.setattr(screenreader, "speak",
                        lambda t, interrupt=False: mondta.append(t) or fut)
    return mondta


def test_olvaso_mellett_a_sajat_hang_hallgat(monkeypatch):
    sv, hits = _sv(monkeypatch)
    mondta = _sr(monkeypatch, True)
    sv.auto_sr = True
    sv.speak("Letöltés kész.", force=True)
    assert hits == [] and mondta == ["Letöltés kész."]


def test_olvaso_nelkul_szol_a_sajat_hang(monkeypatch):
    sv, hits = _sv(monkeypatch)
    mondta = _sr(monkeypatch, False)
    sv.auto_sr = True
    sv.speak("Letöltés kész.", force=True)
    assert hits == ["Letöltés kész."] and mondta == []


def test_kikapcsolva_a_regi_viselkedes(monkeypatch):
    sv, hits = _sv(monkeypatch)
    mondta = _sr(monkeypatch, True)
    sv.auto_sr = False
    sv.speak("x", force=True)
    assert hits == ["x"] and mondta == []


def test_kikapcsolt_bejelentes_akkor_sem_megy_az_olvasohoz(monkeypatch):
    """A force nélküli, kikapcsolt bejelentés továbbra is néma marad."""
    sv, hits = _sv(monkeypatch)
    mondta = _sr(monkeypatch, True)
    sv.auto_sr = True
    sv.speak("nem kért", force=False)
    assert hits == [] and mondta == []


def _speaker():
    sp = speech.VoiceSpeaker.__new__(speech.VoiceSpeaker)
    sp._lock = threading.Lock()
    sp._seq = 0
    sp._player = None
    sp.mode = "auto"
    sp.auto_sr = True
    return sp


def test_koszontes_olvaso_mellett_az_olvasoe(monkeypatch):
    mondta = _sr(monkeypatch, True)
    inditott = []
    monkeypatch.setattr(threading, "Thread",
                        lambda *a, **k: inditott.append(1) or
                        type("T", (), {"start": lambda self: None})())
    sp = _speaker()
    sp.speak("Jó reggelt!")
    assert mondta == ["Jó reggelt!"] and inditott == []


def test_alapbol_be_van_kapcsolva_es_allithato():
    import superdl_gui
    src = inspect.getsource(superdl_gui)
    assert '"sr_auto_csend": True' in src
    vs = inspect.getsource(superdl_gui.MainFrame._apply_voice_settings)
    assert "self.selfvoice.auto_sr" in vs and "self.speaker.auto_sr" in vs
    from superdl import settingsdialog
    d = inspect.getsource(settingsdialog)
    assert '"sr_auto_csend": self.c_srauto.GetValue()' in d


def test_running_ket_masodpercig_emlekszik(monkeypatch):
    hivas = []
    monkeypatch.setattr(screenreader, "_running_cache", [0.0, False])
    monkeypatch.setattr(screenreader, "_ensure_nvda", lambda: object())
    monkeypatch.setattr(screenreader, "_nvda_running",
                        lambda n: hivas.append(1) or True)
    assert screenreader.running() is True
    assert screenreader.running() is True
    assert len(hivas) == 1
