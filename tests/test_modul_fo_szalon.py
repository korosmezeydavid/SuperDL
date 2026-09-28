"""A Modulkezelő háttérszálon tölt be modult; a `register` ettől még a fő
szálon fusson (wx.Timer, menü). Szerencsesüti, 2026-09-27.

A wx-es rész KÜLÖN FOLYAMATBAN fut: egy tesztbeli wx.App a pytest többi,
szintén wx-et használó tesztjét natívan összeomlasztaná."""
import subprocess
import sys
from pathlib import Path

import pytest

from superdl import modkit

pytest.importorskip("wx")

GYOKER = Path(__file__).resolve().parents[1]

SZKRIPT = r'''
import sys, threading, wx
sys.path.insert(0, sys.argv[1])
from superdl import modkit
app = wx.App(False)
keret = wx.Frame(None)
eredmeny = {}
def register(core):
    eredmeny["fo"] = wx.IsMainThread()
    t = wx.Timer(); t.Start(1000); t.Stop()
    return "kesz"
def rossz(core):
    raise ValueError("hibas modul")
def hatter():
    try:
        eredmeny["ertek"] = modkit.fo_szalon(register, None, varakozas=8)
        try:
            modkit.fo_szalon(rossz, None, varakozas=8)
        except ValueError as e:
            eredmeny["hiba"] = str(e)
    except Exception as e:
        eredmeny["vart_hiba"] = repr(e)
    wx.CallAfter(app.ExitMainLoop)
threading.Thread(target=hatter).start()
wx.CallLater(15000, app.ExitMainLoop)
app.MainLoop()
keret.Destroy()
print(sorted(eredmeny.items()))
'''


def test_hatterszalrol_a_fo_szalon_fut_es_a_hiba_visszajut():
    r = subprocess.run([sys.executable, "-c", SZKRIPT, str(GYOKER)],
                       capture_output=True, text=True, timeout=60)
    assert "[('ertek', 'kesz'), ('fo', True), ('hiba', 'hibas modul')]" \
        in r.stdout, r.stdout + r.stderr


def test_fo_szalon_kozvetlenul_hiv():
    assert modkit.fo_szalon(lambda x: x + 1, 1) == 2
