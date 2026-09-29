"""NVDA-s felhasználó visszajelzése (2026-09-29) – a beszéd és a billentyűzet.

1. A modulkezelőben a program saját hangja az NVDA mellett is mondta a
   kijelölt sort, és a bemondások sorba álltak (percekig mesélt).
2. A „Csak a képernyőolvasó beszéljen" csak újraindítás után hatott, és az
   induló köszöntést (Edge-hang) sosem némította.
3. A beszéd-beállítások szám-mezői a SZOMSZÉDJUK nevét kapták.
4. Az AI-ablak és néhány „Bezárás" gombos ablak nem zárult Escape-re.
5. Az Általános lap középen volt."""

import inspect
import os
import sys

import pytest

from superdl import coremod, modmanagerwin, screenreader, selfvoice, speech


# ---- 1. a modulkezelő és a modulok: előbb a képernyőolvasó ----------------

class _Sv:
    muted = False

    def __init__(self):
        self.mondott = []

    def speak(self, t, force=False):
        self.mondott.append(t)


class _Ablak:
    def __init__(self):
        self.main = type("M", (), {})()
        self.main.selfvoice = _Sv()
        self.status = None

    def SetStatusText(self, t):
        self.status = t


def _modkezelo_osztaly():
    for nev, obj in vars(modmanagerwin).items():
        if isinstance(obj, type) and "_announce" in vars(obj):
            return obj
    raise AssertionError("nincs _announce-os osztály a modmanagerwin-ben")


def test_listasor_nvda_mellett_nema(monkeypatch):
    monkeypatch.setattr(screenreader, "running", lambda: True)
    sr = []
    monkeypatch.setattr(screenreader, "speak",
                        lambda t, interrupt=False: sr.append(t) or True)
    a = _Ablak()
    _modkezelo_osztaly()._announce(a, "Zene – telepítve", lista_sor=True)
    assert a.status == "Zene – telepítve"
    assert sr == [] and a.main.selfvoice.mondott == []


def test_egyeb_bemondas_a_kepernyoolvasohoz_megy(monkeypatch):
    sr = []
    monkeypatch.setattr(screenreader, "speak",
                        lambda t, interrupt=False: sr.append(t) or True)
    a = _Ablak()
    _modkezelo_osztaly()._announce(a, "Eltávolítva: Zene.")
    assert sr == ["Eltávolítva: Zene."] and a.main.selfvoice.mondott == []


def test_kepernyoolvaso_nelkul_marad_a_sajat_hang(monkeypatch):
    monkeypatch.setattr(screenreader, "running", lambda: False)
    monkeypatch.setattr(screenreader, "speak", lambda t, interrupt=False: False)
    a = _Ablak()
    _modkezelo_osztaly()._announce(a, "Zene – telepítve", lista_sor=True)
    _modkezelo_osztaly()._announce(a, "Kész.")
    assert a.main.selfvoice.mondott == ["Zene – telepítve", "Kész."]


def test_modulok_voice_adaptere_is_elobb_az_olvaso(monkeypatch):
    sr = []
    monkeypatch.setattr(screenreader, "speak",
                        lambda t, interrupt=False: sr.append(t) or True)
    main = type("M", (), {})()
    main.selfvoice = _Sv()
    coremod.VoiceAdapter(main).speak("szia")
    assert sr == ["szia"] and main.selfvoice.mondott == []
    monkeypatch.setattr(screenreader, "speak", lambda t, interrupt=False: False)
    coremod.VoiceAdapter(main).speak("szia")
    assert main.selfvoice.mondott == ["szia"]


def test_sajat_hang_nem_torlodik():
    """A zárra váró, közben elavult bemondás kimarad (generáció-őr)."""
    src = inspect.getsource(selfvoice.SelfVoice.speak)
    assert "gen = self._gen" in src and "if gen != self._gen" in src


def test_jaws_csak_ha_fut(monkeypatch):
    """Telepített, de nem futó JAWS nem számít futó olvasónak."""
    monkeypatch.setattr(screenreader, "_ensure_nvda", lambda: False)
    monkeypatch.setattr(screenreader, "_ensure_jaws", lambda: object())
    monkeypatch.setattr(screenreader, "_jaws_running", lambda: False)
    monkeypatch.setattr(screenreader, "_running_cache", [0.0, False])
    assert screenreader.available() is False
    assert screenreader.running() is False
    assert screenreader.screen_reader_name() == ""


# ---- 2. képernyőolvasó-mód: azonnal, és a köszöntésre is -----------------

def test_speaker_off_mod_a_kepernyoolvasonak_ad(monkeypatch):
    sr = []
    monkeypatch.setattr(screenreader, "speak",
                        lambda t, interrupt=False: sr.append(t) or True)
    sp = speech.VoiceSpeaker.__new__(speech.VoiceSpeaker)
    import threading
    sp._lock = threading.Lock()
    sp._seq = 0
    sp._player = None
    sp.mode = "auto"
    sp.set_mode("off")
    assert sp.mode == "off"
    sp.speak("Jelenleg nincs aktív letöltés.")
    assert sr == ["Jelenleg nincs aktív letöltés."]


def test_mentes_utan_is_ervenyesul():
    import superdl_gui
    rt = inspect.getsource(superdl_gui.MainFrame._apply_runtime_settings)
    assert "self._apply_voice_settings()" in rt
    ind = inspect.getsource(superdl_gui.MainFrame._apply_settings)
    assert "self._apply_voice_settings()" in ind
    vs = inspect.getsource(superdl_gui.MainFrame._apply_voice_settings)
    assert "self.selfvoice.configure(" in vs and "set_mode(" in vs


# ---- 4. Escape ----------------------------------------------------------

def test_escape_zar():
    from superdl import aiwin
    src = inspect.getsource(aiwin.AIResultFrame.__init__)
    assert "lambda e: self.Close(), id=sid" in src
    import superdl_gui
    for nev in ("HistoryDialog", "SubsDialog", "UpdateDialog"):
        assert "SetEscapeId(wx.ID_CLOSE)" in inspect.getsource(
            getattr(superdl_gui, nev).__init__), nev


# ---- 3. és 5. a beállítás-ablak élesben (wx) -----------------------------

@pytest.fixture(scope="module")
def dialogus():
    if sys.platform != "win32":
        pytest.skip("csak Windowson")
    wx = pytest.importorskip("wx")
    app = wx.App.Get() or wx.App(False)
    from superdl.settingsdialog import SettingsDialog
    d = SettingsDialog(None, {}, {})
    yield d
    d.Destroy()


def _elozo_szoveg(hwnd):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.GetWindow.restype = wintypes.HWND
    u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    h = u.GetWindow(wintypes.HWND(hwnd), 3)          # GW_HWNDPREV
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(h, buf, 256)
    return buf.value.replace("&", "")


def test_altalanos_az_elso_lap(dialogus):
    assert dialogus.nb.GetPageText(0) == "Általános"
    dialogus.valassz_lapot("AI")
    assert dialogus.nb.GetPageText(dialogus.nb.GetSelection()) == "AI"


def test_szam_mezok_a_sajat_cimkejuket_kapjak(dialogus):
    from superdl.settingsdialog import _vezerlo_hwndjei
    varas = {"c_svrate": "Tempó", "c_svpitch": "Hangmagasság",
             "c_svvol": "Beszéd hangereje"}
    for attr, cimke in varas.items():
        ctrl = getattr(dialogus, attr)
        for h in _vezerlo_hwndjei(ctrl):
            elotte = _elozo_szoveg(h)
            # a léptető (updown) a szerkesztő után állhat; a SZERKESZTŐ a döntő
            if len(_vezerlo_hwndjei(ctrl)) == 2 and h == int(ctrl.GetHandle()):
                continue
            assert elotte.startswith(cimke), (attr, elotte)
