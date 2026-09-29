"""A Beállítások ablak minden lapján minden Alt+betű EGYSZER szerepel, és
egyik sem ütközik a Mentés (Alt+M) / Mégse (Alt+G) gombbal.

Két azonos Alt+betűnél a Windows nem aktiválja a vezérlőt, csak váltogat
közöttük – vakon ez úgy hat, mintha a billentyű nem működne (2026-09-29:
a Hangjelzések / Beszéd lapon a P, a J és a T is kétszer szerepelt)."""

import re
import sys

import pytest


def test_nincs_duplikalt_alt_betu():
    if sys.platform != "win32":
        pytest.skip("csak Windowson")
    wx = pytest.importorskip("wx")
    app = wx.App.Get() or wx.App(False)
    from superdl.settingsdialog import SettingsDialog
    d = SettingsDialog(None, {}, {})
    try:
        gombok = {re.search(r"&(\w)", w.GetLabel()).group(1).lower()
                  for w in d.GetChildren()
                  if isinstance(w, wx.Button) and re.search(r"&(\w)", w.GetLabel())}
        assert gombok >= {"m", "g"}
        hibak = []
        for i in range(d.nb.GetPageCount()):
            lap = d.nb.GetPageText(i)
            lattuk = {}
            for w in d.nb.GetPage(i).GetChildren():
                m = re.search(r"&(\w)", w.GetLabel() or "")
                if not m:
                    continue
                b = m.group(1).lower()
                if b in gombok:
                    hibak.append(f"{lap}: Alt+{b} a gombé is ({w.GetLabel()!r})")
                if b in lattuk:
                    hibak.append(f"{lap}: Alt+{b} kétszer ({lattuk[b]!r}, "
                                 f"{w.GetLabel()!r})")
                lattuk[b] = w.GetLabel()
        assert not hibak, "\n".join(hibak)
    finally:
        d.Destroy()
