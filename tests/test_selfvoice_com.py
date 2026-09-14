"""selfvoice: a SAPI-bemondás HÁTTÉRSZÁLAS COM-inicializálásának őre.

Egy felhasználó jelezte, hogy az F8 (és minden hangos jelzés) NÉMA – pedig a
felirat-narráció szól. Gyökér-ok (élesben igazolva): a `SelfVoice.speak` SAPI-ága
worker szálon hívta a főszálon készített COM-objektumot CoInitialize nélkül →
`com_error (CoInitialize has not been called)` → némán elnyelődött. Ugyanaz a
COM-hiba, mint a narrátornál – de a Core self-voice rétegében.
"""

import inspect

from superdl import selfvoice


def test_speak_worker_coinitialize():
    """A speak() háttérszála CoInitialize-t hív ÉS ott hozza létre a COM-hangot
    (a főszálon készített SpVoice más szálon com_error-t ad)."""
    src = inspect.getsource(selfvoice.SelfVoice.speak)
    assert "CoInitialize" in src, "a speak worker nem hív CoInitialize-t"
    assert "CoUninitialize" in src
    assert 'Dispatch("SAPI.SpVoice")' in src, \
        "a speak worker nem a saját szálán hozza létre a SAPI-hangot"


def test_speak_szinkron_a_workerben():
    """A worker SZINKRON Speak-et használjon (0), hogy a szál megvárja a végét,
    mielőtt CoUninitialize-t hív (async esetén a hang megszakadna)."""
    src = inspect.getsource(selfvoice.SelfVoice.speak)
    assert "Speak(body, 0)" in src, "a worker nem szinkron Speak-et használ"


# ---- 0x8001010d: COM a fő szálon, billentyű-esemény közben ---------------
#
# ⚠️ A 4.6.11 összeomlás-naplójában `Windows fatal exception: code 0x8001010d`
# (RPC_E_CANTCALLOUT_ININPUTSYNCCALL) szerepelt. Ez akkor jön, ha kimenő
# COM-hívást indítunk, miközben a Windows „input-synchronous" hívást kézbesít
# — pontosan ez a helyzet, amikor billentyű- vagy fókusz-eseményből szólalunk
# meg, és a képernyőolvasó is épp kérdezi a vezérlőt. A bemondás útján a
# `GetVoices()` volt az egyetlen ilyen hívás; most egyszer fut, indításkor.


class _Token:
    def __init__(self, leiras):
        self._l = leiras

    def GetDescription(self):
        return self._l


class _HamisHang:
    """Számolja, hányszor kérdezték le a hanglistát (ez a COM-hívás)."""

    def __init__(self, leirasok):
        self.hivasok = 0
        self._leirasok = leirasok

    def GetVoices(self):
        self.hivasok += 1
        return [_Token(x) for x in self._leirasok]


def _hang(leirasok):
    sv = selfvoice.SelfVoice.__new__(selfvoice.SelfVoice)
    sv.voice_desc = ""
    sv._magyar_desc = None
    sv._voice = _HamisHang(leirasok)
    return sv


def test_a_hanglistat_csak_egyszer_kerdezzuk_le():
    sv = _hang(["Microsoft Szabolcs - Hungarian (Hungary)", "Zira"])
    elso = sv._effective_voice_desc()
    for _ in range(20):
        sv._effective_voice_desc()
    assert sv._voice.hivasok == 1
    assert "Szabolcs" in elso


def test_a_valasztott_hangnal_egyaltalan_nincs_lekerdezes():
    sv = _hang(["Microsoft Szabolcs - Hungarian (Hungary)"])
    sv._magyar_desc = ""          # mintha indításkor már megnéztük volna
    sv.voice_desc = "Microsoft Zira"
    assert sv._effective_voice_desc() == "Microsoft Zira"
    assert sv._voice.hivasok == 0


def test_ha_nincs_magyar_hang_nem_kerdezunk_ujra():
    sv = _hang(["Microsoft Zira", "Microsoft David"])
    sv._effective_voice_desc()
    sv._effective_voice_desc()
    assert sv._voice.hivasok == 1
