"""Képernyőolvasó-mód: a felhasználó kérte, hogy legyen egy kapcsoló, amivel
MINDEN egyéb program-beszéd (a saját SelfVoice-hang és a gépi felolvasás)
elnémul, és CSAK a képernyőolvasó (NVDA/JAWS) beszéljen.

Ezek a tesztek a némítás linchpin-jét (a SelfVoice muted felülírja a force-ot)
és a GUI bekötésének SZERZŐDÉSÉT ellenőrzik – kijelző nélkül is futnak.
"""

import inspect

from superdl import selfvoice
from superdl.selfvoice import SelfVoice


def test_muted_felulirja_a_force_ot(monkeypatch):
    """A képernyőolvasó-mód a SelfVoice muted kapcsolóján keresztül némít – és a
    muted MÉG a force=True bemondást is elnyeli (erre épül a funkció)."""
    # az eSpeak-utat használjuk megfigyelhető háttérként (kijelző nélkül is megy)
    monkeypatch.setattr(selfvoice, "espeak_available", lambda: True)
    hits = []
    sv = SelfVoice()
    monkeypatch.setattr(sv, "_speak_espeak", lambda t: hits.append(t))

    sv.configure(muted=True, voice_desc="espeak:hu")
    sv.speak("bármi", force=True)            # force ellenére NÉMA
    assert hits == []

    # ellenőrzés: némítás nélkül force-ra megszólal
    sv.configure(muted=False, voice_desc="espeak:hu")
    sv.speak("most igen", force=True)
    assert hits == ["most igen"]


def test_gui_bekotese_szerzodes():
    """A GUI a screenreader_only-t a speaker KIKAPCSOLÁSÁRA és a selfvoice
    NÉMÍTÁSÁRA fordítja, és az _announce a képernyőolvasónak adja a szöveget."""
    import superdl_gui
    src = inspect.getsource(superdl_gui)
    # a beszéd-beállítás alkalmazása
    assert "sr_only = bool(s.get(\"screenreader_only\", False))" in src
    assert 'self.speaker.set_mode("off" if sr_only' in src
    assert "muted=bool(s.get(\"selfvoice_off\", False)) or sr_only" in src
    # a visszajelzést a képernyőolvasó mondja képernyőolvasó-módban
    ann = inspect.getsource(superdl_gui.MainFrame._announce)
    assert "screenreader_only" in ann and "screenreader.speak" in ann


def test_alap_kikapcsolva():
    """Alapból NINCS bekapcsolva – aki nem képernyőolvasós, mindent hall."""
    import superdl_gui
    src = inspect.getsource(superdl_gui)
    assert '"screenreader_only": False' in src
