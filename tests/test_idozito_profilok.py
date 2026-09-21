"""Időzítő-profilok: köztes figyelmeztetés, utolsó perc, párhuzamos futás.

A `FutoIdozito` a monotonic órát használja, de MINDEN függvénye fogad
`most`-ot – így a tesztek nem alszanak és nem függnek a gép sebességétől.
"""

import pytest

from superdl import idoora as I


def _uj(nev="ebédszünet", hossz=20, kozbenso=5, valtozat="f2", **kw):
    p = {"nev": nev, "hossz_perc": hossz, "kozbenso_perc": kozbenso,
         "valtozat": valtozat}
    p.update(kw)
    return I.FutoIdozito(p, most=0.0)


def _szovegek(f, t):
    return [sz for sz, _ in f.esedekes(t)]


# ───────────────────────── profil-ellenőrzés ────────────────────────

def test_nev_nelkul_nem_menthato():
    ok, uz = I.profil_rendben({"nev": "  ", "hossz_perc": 20})
    assert not ok and "nev" in uz.lower().replace("é", "e")


@pytest.mark.parametrize("hossz", [0, -3, 24 * 60 + 1, "húsz", None])
def test_ertelmetlen_hossz_nem_menthato(hossz):
    ok, _ = I.profil_rendben({"nev": "x", "hossz_perc": hossz})
    assert not ok


def test_a_koztes_figyelmeztetes_nem_lehet_hosszabb_az_idozitonel():
    ok, uz = I.profil_rendben(
        {"nev": "x", "hossz_perc": 20, "kozbenso_perc": 20})
    assert not ok and uz


def test_ervenyes_profil_menthetp():
    ok, uz = I.profil_rendben(
        {"nev": "ebédszünet", "hossz_perc": 20, "kozbenso_perc": 5})
    assert ok and uz == ""


def test_nulla_koztes_azt_jelenti_csak_a_vegen_szol():
    ok, _ = I.profil_rendben(
        {"nev": "x", "hossz_perc": 20, "kozbenso_perc": 0})
    assert ok
    f = _uj(kozbenso=0)
    # 15 perc hátra – ilyenkor semmi
    assert _szovegek(f, 5 * 60) == []


# ─────────────────── köztes figyelmeztetés + utolsó perc ────────────

def test_ot_percenkenti_figyelmeztetes_husz_perces_idozitonel():
    f = _uj(hossz=20, kozbenso=5)
    assert _szovegek(f, 1.0) == []                     # 20 perc hátra
    assert _szovegek(f, 5 * 60) == ["ebédszünet: tizenöt perc van hátra."]
    assert _szovegek(f, 10 * 60) == ["ebédszünet: tíz perc van hátra."]
    assert _szovegek(f, 15 * 60) == ["ebédszünet: öt perc van hátra."]


def test_az_utolso_perc_surubb_60_30_10_masodpercnel():
    f = _uj(hossz=20, kozbenso=5)
    for t in (5 * 60, 10 * 60, 15 * 60):
        f.esedekes(t)
    assert _szovegek(f, 19 * 60) == ["ebédszünet: egy perc van hátra."]
    assert _szovegek(f, 19 * 60 + 30) == \
        ["ebédszünet: harminc másodperc van hátra."]
    assert _szovegek(f, 19 * 60 + 50) == \
        ["ebédszünet: tíz másodperc van hátra."]


def test_az_utolso_perc_akkor_is_szol_ha_nincs_koztes_figyelmeztetes():
    f = _uj(hossz=20, kozbenso=0)
    assert _szovegek(f, 19 * 60) == ["ebédszünet: egy perc van hátra."]


def test_lejaratkor_letelt_az_ido():
    f = _uj(hossz=20, kozbenso=0)
    ki = f.esedekes(20 * 60)
    assert ki == [("ebédszünet: letelt az idő.", True)]
    assert f.lejart(20 * 60)


def test_a_lejarat_surgos_a_koztes_figyelmeztetes_nem():
    f = _uj(hossz=20, kozbenso=5)
    assert f.esedekes(5 * 60)[0][1] is False
    assert f.esedekes(20 * 60)[0][1] is True


def test_a_lejarat_csak_egyszer_szolal_meg():
    f = _uj(hossz=20, kozbenso=0)
    assert f.esedekes(20 * 60)
    assert f.esedekes(20 * 60 + 5) == []
    assert f.esedekes(30 * 60) == []


# ───────────────────────── alvás és ébredés ─────────────────────────

def test_atalvasnal_a_koztes_figyelmeztetesek_elmaradnak():
    """Ha a gép hármat aludt, nem zúdítunk rá négy elmaradt jelzést."""
    f = _uj(hossz=60, kozbenso=10)
    assert _szovegek(f, 45 * 60) == []       # 15 perc hátra, de mind elmúlt


def test_de_a_lejarat_ebredes_utan_is_bemondando():
    """⚠️ Az idő elmúlt, az ESEMÉNY nem évül el."""
    f = _uj(hossz=20, kozbenso=5)
    ki = f.esedekes(3 * 3600)                # három órát aludtunk
    assert ki == [("ebédszünet: letelt az idő.", True)]


def test_epp_hogy_kesve_meg_bemondja_a_koztes_jelzest():
    """A 20 mp-es ébredés miatt sosem pontos a pillanat – 60 mp türelem."""
    f = _uj(hossz=20, kozbenso=5)
    assert _szovegek(f, 5 * 60 + 40) == ["ebédszünet: tizenöt perc van hátra."]


# ───────────────────────── név és hang ──────────────────────────────

def test_a_nevet_alapbol_kimondja_kulon_hang_mellett_is():
    f = _uj(valtozat="f2")
    assert f.valtozat == "f2"
    assert _szovegek(f, 20 * 60)[0].startswith("ebédszünet: ")


def test_a_nev_kimondasa_kikapcsolhato():
    f = _uj(kimondja_a_nevet=False)
    assert _szovegek(f, 20 * 60) == ["letelt az idő."]


def test_a_kerdesre_adott_valasz_mindig_nevesit():
    """Akkor is, ha a bemondásban ki van kapcsolva a név – itt egyszerre
    több időzítőről van szó, a hang nem elég azonosító."""
    f = _uj(kimondja_a_nevet=False, hossz=20)
    assert f.allapot_szoveg(13 * 60) == "ebédszünet: hét perc van hátra."


# ───────────── több párhuzamos időzítő (Dávid használati esete) ─────

def test_harom_parhuzamos_idozito_kulon_hanggal_es_ritmussal():
    munka = I.FutoIdozito({"nev": "munkaidő", "hossz_perc": 480,
                           "kozbenso_perc": 60, "valtozat": "m3"}, most=0.0)
    ebed = I.FutoIdozito({"nev": "ebédszünet", "hossz_perc": 20,
                          "kozbenso_perc": 5, "valtozat": "f2"}, most=0.0)
    meeting = I.FutoIdozito({"nev": "meeting", "hossz_perc": 60,
                             "kozbenso_perc": 20, "valtozat": "boris"},
                            most=0.0)
    assert {munka.valtozat, ebed.valtozat, meeting.valtozat} == \
        {"m3", "f2", "boris"}
    # 20 perccel az indulás után: az ebéd LETELT, a meeting 40 percnél tart
    assert ebed.esedekes(20 * 60) == [("ebédszünet: letelt az idő.", True)]
    assert _szovegek(meeting, 20 * 60) == ["meeting: negyven perc van hátra."]
    # a munkaidő ekkor még csendben van (60 percenként szól)
    assert _szovegek(munka, 20 * 60) == []


def test_minden_futonak_sajat_azonositoja_van():
    a, b = _uj(), _uj()
    assert a.azon != b.azon


# ──────────────────────── hátralévő idő szövege ─────────────────────

@pytest.mark.parametrize("mp,var", [
    (0, "nulla másodperc"), (10, "tíz másodperc"), (30, "harminc másodperc"),
    (60, "egy perc"), (120, "két perc"), (420, "hét perc"),
    (90, "egy perc harminc másodperc"),
    (3600, "egy óra"), (3600 + 600, "egy óra tíz perc"),
    (2 * 3600, "két óra"),
])
def test_hatralevo_szoveg_kimondva(mp, var):
    assert I.hatralevo_szoveg(mp) == var
    assert not any(c.isdigit() for c in I.hatralevo_szoveg(mp))
