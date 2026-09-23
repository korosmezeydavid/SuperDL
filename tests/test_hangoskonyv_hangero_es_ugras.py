"""4.6.15 utáni modulkör: hangoskönyv-hangerő + időpontra ugrás + rádió-hangerő.

⚠️ MIÉRT VAN EZ A FÁJL. Turai László (2026-09-23): „a hangoskönyv lejátszóban
a hangerőt nem lehet állítani". Nagy Károly ugyanaznap: a rádió is felejtse el
a hangerőt. Mind a kettő olyan hiba, amit forrásolvasással el lehet nézni —
ezért itt a TÉNYLEGES viselkedést mérjük, nem a kód szövegét.
"""
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parents[1]


def _modul(relut: str, nev: str):
    """Egy modul-forrás betöltése a modules_src alól, wx nélkül is."""
    ut = GYOKER / relut
    spec = importlib.util.spec_from_file_location(nev, ut)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nev] = mod
    spec.loader.exec_module(mod)
    return mod


AB = _modul("modules_src/konyvek/konyvek_mod/audiobook_player.py",
            "_ab_player_teszt")


# ---- az időpont-értelmező ------------------------------------------------

@pytest.mark.parametrize("szoveg, vart", [
    ("12:30", 750.0),
    ("1:02:03", 3723.0),
    ("0:30", 30.0),
    ("90", 90.0),
    ("5 perc", 300.0),
    ("5 perc 30", 330.0),
    ("2 óra 10 perc", 7800.0),
    ("90 mp", 90.0),
    ("2 ora", 7200.0),
    ("  12:30  ", 750.0),
])
def test_ido_ertelmez_elfogadja_a_szokasos_alakokat(szoveg, vart):
    assert AB.ido_ertelmez(szoveg) == pytest.approx(vart)


@pytest.mark.parametrize("szoveg", ["", "   ", "alma", "1:2:3:4", None, "x:y"])
def test_ido_ertelmez_a_zagyvasagra_none_t_ad(szoveg):
    assert AB.ido_ertelmez(szoveg) is None


def test_a_puszta_szam_masodperc_nem_perc():
    """⚠️ Ez szándékos döntés: a kettőspontos alak a perces írásmód, tehát a
    puszta szám másodperc. Ha ezt elrontjuk, a „90" kilencven PERCRE ugrana."""
    assert AB.ido_ertelmez("90") == 90.0
    assert AB.ido_ertelmez("1:30") == 90.0


def test_ido_ertelmez_nem_ad_negativot():
    assert AB.ido_ertelmez("-5") == 0.0


# ---- a megjegyzett hangerő (hangoskönyv) ---------------------------------

def test_hangero_betolt_alapja_a_lejatszo_alapja():
    """Alap 0.7 – ugyanaz, amivel a Core lejátszója indul. Ha ezt elrontjuk,
    az ELSŐ indítás hangereje változna meg mindenkinél."""
    from superdl.audioengine import Player
    assert "0.7" in inspect.getsource(AB.hangero_betolt)
    assert Player().volume == pytest.approx(0.7)


def test_hangero_ment_es_betolt_korbeer(tmp_path, monkeypatch):
    monkeypatch.setattr(AB, "_BEALL_FILE", tmp_path / "ab.json")
    AB.hangero_ment(0.35)
    assert AB.hangero_betolt() == pytest.approx(0.35)


def test_hangero_ment_nem_enged_ki_a_tartomanybol(tmp_path, monkeypatch):
    monkeypatch.setattr(AB, "_BEALL_FILE", tmp_path / "ab.json")
    AB.hangero_ment(5.0)
    assert AB.hangero_betolt() == pytest.approx(1.0)
    AB.hangero_ment(-2.0)
    assert AB.hangero_betolt() == pytest.approx(0.0)


def test_serult_beallitasfajl_nem_dol_el(tmp_path, monkeypatch):
    f = tmp_path / "ab.json"
    f.write_text("{ez nem json", encoding="utf-8")
    monkeypatch.setattr(AB, "_BEALL_FILE", f)
    assert AB.hangero_betolt() == pytest.approx(0.7)


def test_a_lejatszonak_van_hangero_allitasa():
    assert hasattr(AB.AudioBookPlayer, "set_volume")


# ---- az ablak kötései (forrásból, wx nélkül) -----------------------------

WIN = (GYOKER / "modules_src/konyvek/konyvek_mod/audiobookwin.py").read_text(
    encoding="utf-8")


def test_az_ablak_bekoti_a_ctrl_fel_le_t():
    assert "wx.WXK_UP, ids[\"hfel\"]" in WIN
    assert "wx.WXK_DOWN, ids[\"hle\"]" in WIN


def test_az_ablak_bekoti_a_ctrl_g_t():
    assert "ord('G'), ids[\"ugras\"]" in WIN


def test_a_hangero_mentese_benne_van_az_allitasban():
    i = WIN.index("def _hangero_allit")
    blokk = WIN[i:i + 900]
    assert "hangero_ment" in blokk, "a hangerő nem maradna meg a következő indításra"
    assert "set_volume" in blokk


def test_az_ugras_nem_megy_tul_a_sav_vegen():
    i = WIN.index("def _ugras_idopontra")
    blokk = WIN[i:WIN.index("# ---- súgó", i)]
    assert "cel > hossz" in blokk


def test_a_szunet_szunet_marad_ugras_utan():
    i = WIN.index("def _ugras_idopontra")
    blokk = WIN[i:WIN.index("# ---- súgó", i)]
    assert "is_paused" in blokk and "pause()" in blokk


def test_a_sugo_emliti_az_uj_billentyuket():
    assert "Ctrl+fel / Ctrl+le" in WIN
    assert "Ctrl+G" in WIN


def test_nincs_alt_utkozes_a_hangoskonyv_gombjain():
    """⚠️ A gombok Alt-betűi: a képernyőolvasós használatban egy ütköző betű
    két gomb között ugrál. Az ÚJ gombokat nézzük, a régieket nem bántjuk."""
    betuk = [m.group(2).lower()
             for m in re.finditer(r'\("([^"]*?)&(\w)', WIN)]
    for uj in ("f", "j", "u"):
        assert betuk.count(uj) == 1, f"a(z) '{uj}' Alt-betű ütközik"


# ---- rádió: megjegyzett hangerő -----------------------------------------

RAD = (GYOKER / "modules_src/radio/radio_mod/radiowin.py").read_text(
    encoding="utf-8")


def test_a_radio_betolti_a_hangerot_indulaskor():
    assert "_hangero_betolt()" in RAD
    assert RAD.index("_hangero_betolt()") < RAD.index("self._build()")


def test_a_radio_menti_a_hangerot_allitaskor():
    i = RAD.index("def _vol")
    blokk = RAD[i:i + 500]
    assert "_hangero_ment" in blokk


def test_a_nemitas_nem_ment_nullat():
    """⚠️ Ha a némítás elmentené a 0-t, a következő indítás NÉMA rádió lenne —
    és a felhasználó azt hinné, elromlott."""
    i = RAD.index("def _toggle_mute")
    blokk = RAD[i:RAD.index("# ---- felvétel", i)]
    assert "_hangero_ment" not in blokk


# ---- manifestek ----------------------------------------------------------

@pytest.mark.parametrize("ut, verzio", [
    ("modules_src/konyvek/manifest.json", "1.3.4"),
    ("modules_src/radio/manifest.json", "1.1.9"),
])
def test_a_manifest_verzioja_emelve(ut, verzio):
    d = json.loads((GYOKER / ut).read_text(encoding="utf-8"))
    assert d["version"] == verzio
