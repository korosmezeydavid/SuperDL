"""Az AI modellnév szolgáltatónkénti kezelése.

A GOND (Bizik Péter Károly jelentése, 4.6.7): egyetlen közös „model" mező
szolgálta mind a négy szolgáltatót. Ha oda OpenAI-modell került, a videó
képi elemzése – ami MINDIG Geminit hív – a gpt-… nevet küldte a Google
végpontjára: „GenerateContentRequest.model: unexpected model name format"
(400). Fordítva (Gemini-modell OpenAI-hívásban) 404.
"""

import pytest

from superdl import aiclient


# ---- családfelismerés -------------------------------------------------

@pytest.mark.parametrize("nev,csalad", [
    ("gpt-4o-mini", "openai"),
    ("ft:gpt-4o:sajat", "openai"),
    ("o3-mini", "openai"),
    ("whisper-1", "openai"),
    ("gemini-2.5-flash", "gemini"),
    ("claude-sonnet-4-6", "anthropic"),
    ("grok-2-vision-latest", "xai"),
    ("", None),
    ("valami-uj-modell-2030", None),      # ismeretlent NEM sorolunk sehová
])
def test_csalad(nev, csalad):
    assert aiclient._csalad(nev) == csalad


def test_maseknal_csak_biztos_esetben():
    assert aiclient._maseknal("gpt-4o", "gemini") is True
    assert aiclient._maseknal("gemini-2.5-flash", "gemini") is False
    # ismeretlen nevet nem utasítunk el – lehet új modell
    assert aiclient._maseknal("valami-uj", "gemini") is False


# ---- a modellválasztás ------------------------------------------------

def test_sajat_mezo_nyer():
    cfg = {"model_gemini": "gemini-2.5-pro", "model_openai": "gpt-4o"}
    assert aiclient._model(cfg, "gemini") == "gemini-2.5-pro"
    assert aiclient._model(cfg, "openai") == "gpt-4o"


def test_a_peter_hiba_nem_fordulhat_elo():
    """A régi közös mezőben OpenAI-modell van; a Gemini-hívás NEM kaphatja."""
    cfg = {"model": "gpt-4o-mini", "provider": "openai"}
    assert aiclient._model(cfg, "gemini") == aiclient.DEFAULT_MODELS["gemini"]
    # a saját szolgáltatójánál viszont érvényes marad
    assert aiclient._model(cfg, "openai") == "gpt-4o-mini"


def test_forditva_is(caplog):
    cfg = {"model": "gemini-2.5-flash", "provider": "gemini"}
    assert aiclient._model(cfg, "openai") == aiclient.DEFAULT_MODELS["openai"]
    assert aiclient._model(cfg, "gemini") == "gemini-2.5-flash"


def test_rossz_sajat_mezot_is_eldobjuk():
    """Ha valaki a Gemini-mezőbe ír gpt-modellt, akkor sem küldjük el."""
    cfg = {"model_gemini": "gpt-4o"}
    assert aiclient._model(cfg, "gemini") == aiclient.DEFAULT_MODELS["gemini"]


def test_ures_konfig_alapertelmezett():
    for p in aiclient.ALL_PROVIDERS:
        assert aiclient._model({}, p) == aiclient.DEFAULT_MODELS[p]


def test_override_eros():
    cfg = {"model_openai": "gpt-4o"}
    assert aiclient._model(cfg, "openai", "gpt-4.1") == "gpt-4.1"


def test_ismeretlen_nev_atmegy():
    """Új, még nem ismert modellnevet nem írunk felül."""
    cfg = {"model_openai": "sajat-finomhangolt-2030"}
    assert aiclient._model(cfg, "openai") == "sajat-finomhangolt-2030"


# ---- migráció ---------------------------------------------------------

def test_migracio_a_csalad_szerint():
    uj = aiclient.migralt_modellek({"model": "gpt-4o", "provider": "gemini"})
    assert uj["model_openai"] == "gpt-4o"      # a NÉV dönt, nem a provider
    assert uj.get("model_gemini", "") == ""
    assert uj["model"] == ""


def test_migracio_ismeretlen_nev_az_elsodlegeshez():
    uj = aiclient.migralt_modellek({"model": "sajat-modell",
                                    "provider": "anthropic"})
    assert uj["model_anthropic"] == "sajat-modell"
    assert uj["model"] == ""


def test_migracio_nem_ir_felul_meglevot():
    uj = aiclient.migralt_modellek({"model": "gpt-4o",
                                    "model_openai": "gpt-4.1"})
    assert uj["model_openai"] == "gpt-4.1"
    assert uj["model"] == ""


def test_migracio_ures_konfigon_nem_hal_meg():
    assert aiclient.migralt_modellek({})["model"] == ""


def test_migracio_nem_bantja_a_kulcsokat():
    uj = aiclient.migralt_modellek({"openai_key": "sk-x", "model": "gpt-4o"})
    assert uj["openai_key"] == "sk-x"


# ---- hibaüzenet -------------------------------------------------------

class _Valasz:
    def __init__(self, kod, uzenet):
        self.status_code = kod
        self._u = uzenet
        self.text = uzenet

    def json(self):
        return {"error": {"message": self._u}}


def test_400_rossz_modellnev_erthetoen():
    v = _Valasz(400, "GenerateContentRequest.model: unexpected model "
                     "name format")
    with pytest.raises(aiclient.AIError) as e:
        aiclient._check(v)
    assert "modellnév" in str(e.value)


def test_analyze_video_a_gemini_mezot_hasznalja():
    """Az analyze_video MINDIG Geminit hív – a Gemini modellmezőjével."""
    import inspect
    forras = inspect.getsource(aiclient.analyze_video)
    assert '_model(cfg, "gemini")' in forras
