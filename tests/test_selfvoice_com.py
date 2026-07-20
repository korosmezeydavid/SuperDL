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
