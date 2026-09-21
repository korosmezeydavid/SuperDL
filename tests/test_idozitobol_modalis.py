# -*- coding: utf-8 -*-
"""A 4.6.7-es szabály őrzése: IDŐZÍTŐBŐL NEM NYITUNK MODÁLIS ABLAKOT.

Tóth László és Ujfalusi Zoltán 4.6.11-es jelentésében ugyanaz a verem áll:

    File "superdl_gui.py", line 1763 in _offer_resume
    File "wx\\core.py", line 3550 in Notify
    File "wx\\core.py", line 2254 in MainLoop
    Windows fatal exception: code 0x8001010d

A `wx.CallLater` időzítő. Ha a hívott függvény modális ablakot nyit, a
COM bemenet-szinkron hívást dolgoz fel, és kifelé nem indítható hívás —
`RPC_E_CANTCALLOUT_ININPUTSYNCCALL`. A szabályt egyszer már kimondtuk és
egy helyen be is tartottuk; ez a teszt a TÖBBIRE vigyáz.
"""
import re
from pathlib import Path

GYOKER = Path(__file__).resolve().parent.parent
FORRAS = (GYOKER / "superdl_gui.py").read_text(encoding="utf-8")

# a CallLater első argumentuma után MI következik
_HIVAS = re.compile(r"wx\.CallLater\(\s*\d+\s*,\s*(.+?)\)\s*$", re.M)

# ezek nyitnak modális ablakot vagy beszélnek – időzítőből TILOS közvetlenül
MODALIS = ("_offer_resume",)


def test_az_offer_resume_nem_fut_kozvetlenul_idozitobol():
    """A konkrét hiba: a folytatás-kérdés modális ablaka időzítőből."""
    for hivas in _HIVAS.findall(FORRAS):
        for nev in MODALIS:
            if nev not in hivas:
                continue
            assert "CallAfter" in hivas, (
                "A %s közvetlenül időzítő-visszahívásból fut, és modális "
                "ablakot nyit. Ez a 0x8001010d. Tedd `wx.CallAfter`-be: %s"
                % (nev, hivas))


def test_a_folytatas_kerdese_tenyleg_modalis():
    """Kontroll: ha a `_offer_resume`-ból valaha eltűnne a modális ablak, a
    fenti teszt üres ígéretté válna. Ez itt bizonyítja, hogy van mit védeni."""
    resz = FORRAS.split("def _offer_resume", 1)[1].split("\n    def ", 1)[0]
    assert "wx.MessageBox" in resz
