"""Régi processzor: a numpy-őr (Tóth Zoltán, 2026-09-24).

A numpy második betöltési kísérlete régi gépen natívan megöli a programot,
ezért a `numpyor` az első kudarc után lezárja a numpyt, a hanglejátszás
numpy nélkül is megy, a fordító pedig hozzá sem nyúl a ctranslate2-höz."""
import array
import importlib.abc
import sys

import pytest

from superdl import audioengine, numpyor, offlineford


class _NumpyTilto(importlib.abc.MetaPathFinder):
    """Úgy tesz, mintha a numpy DLL-je nem indulna el – és SZÁMOLJA, hányszor
    próbálták betölteni (élesben a második próba a halálos)."""
    def __init__(self):
        self.probak = 0

    def find_spec(self, name, path=None, target=None):
        if name == "numpy":
            self.probak += 1
            raise ImportError("DLL load failed while importing "
                              "_multiarray_umath: DLL inicializáló rutin")
        return None


@pytest.fixture
def regi_gep(monkeypatch):
    mentett = {n: m for n, m in sys.modules.items()
               if n == "numpy" or n.startswith("numpy.")}
    for n in mentett:
        del sys.modules[n]
    for n in [n for n in sys.modules if n.startswith("ctranslate2")]:
        monkeypatch.delitem(sys.modules, n)
    tilto = _NumpyTilto()
    sys.meta_path.insert(0, tilto)
    numpyor._visszaallit_tesztnek()
    yield tilto
    sys.meta_path.remove(tilto)
    sys.modules.pop("numpy", None)
    sys.modules.update(mentett)
    numpyor._visszaallit_tesztnek()


def test_elso_kudarc_utan_soha_tobbe_nem_probalja(regi_gep):
    assert numpyor.elerheto() is False
    assert "túl régi" in numpyor.hiba()
    assert "DLL" in numpyor.hiba()
    for _ in range(3):
        with pytest.raises(ImportError):
            numpyor.betolt()
    # külső csomag sima `import numpy`-ja sem nyúl újra a DLL-hez
    with pytest.raises(ImportError):
        import numpy  # noqa: F401
    assert regi_gep.probak == 1
    assert sys.modules["numpy"] is None


def test_fordito_nem_nyul_a_ctranslate2hoz(regi_gep):
    with pytest.raises(ImportError) as e:
        offlineford.ct2()
    assert "túl régi" in str(e.value)
    assert "ctranslate2" not in sys.modules
    assert offlineford.elerheto() is False
    assert regi_gep.probak == 1


def test_hibajelentes_nem_omlik_ossze_es_megmondja_miert(regi_gep):
    from superdl import diagnostics
    szoveg = diagnostics.build_report({})
    assert "Számolókönyvtár:  NEM TÖLTHETŐ BE" in szoveg
    assert "Offline fordítás:  NINCS" in szoveg
    assert regi_gep.probak == 1


def test_jo_gepen_rendben():
    numpyor._visszaallit_tesztnek()
    assert numpyor.elerheto() is True
    assert numpyor.hiba() is None


def test_hangero_numpy_nelkul_ugyanaz_mint_numpyval():
    import numpy as np
    minta = array.array("h", [0, 1000, -1000, 32767, -32768, 12345, -7])
    raw = minta.tobytes()
    for v in (0.0, 0.3, 0.5, 0.95):
        assert audioengine.hangero_alkalmaz(raw, v, None) == \
            audioengine.hangero_alkalmaz(raw, v, np)


def test_hangero_paratlan_hossz_nem_hasal_el():
    raw = array.array("h", [100, 200]).tobytes() + b"\x01"
    ki = audioengine.hangero_alkalmaz(raw, 0.5, None)
    assert array.array("h", ki).tolist() == [50, 100]


def test_lejatszo_szal_nem_importal_numpyt_kozvetlenul():
    import inspect
    feed = inspect.getsource(audioengine).split("def _feed", 1)[1] \
        .split("\n    def ", 1)[0]
    assert "import numpy as" not in feed
    assert "numpyor.betolt()" in feed


def test_gui_indulaskor_betolti_az_ort():
    with open("superdl_gui.py", encoding="utf-8") as f:
        forras = f.read()
    main = forras.split("def main():", 1)[1]
    assert "numpyor.elerheto()" in main
    # az önpróba és minden szál ELŐTT
    assert main.index("numpyor.elerheto()") < main.index("--onproba")
