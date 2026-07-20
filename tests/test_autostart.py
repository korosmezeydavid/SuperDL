"""autostart: az automatikus háttérindítás őrei.

Kényelmi funkció (felhasználói kérés): a SuperDL a Windowsba való belépéskor
magától elinduljon a HÁTTÉRBEN (rendszertálcán), hogy az időzített rádiófelvételek
akkor is elmenjenek, ha a felhasználó nem nyitotta meg a programot. HKCU „Run"
kulcs, admin nélkül, visszavonhatóan.
"""

import inspect

from superdl import autostart


def test_available_csak_frozen():
    """Forrásból futtatva NINCS értelme (nincs stabil exe-útvonal) → False."""
    # a teszt forrásból fut, tehát nem frozen
    assert autostart.available() is False


def test_background_flag_es_felismeres():
    assert autostart.BACKGROUND_FLAG == "--background"
    assert autostart.is_background_launch(["superdl.exe", "--background"]) is True
    assert autostart.is_background_launch(["superdl.exe"]) is False
    assert autostart.is_background_launch(["superdl.exe", "film.mp4"]) is False


def test_command_a_hatter_kapcsoloval_indit():
    """A Run-kulcsba írt parancs a háttér-kapcsolóval indítja az exét."""
    cmd = autostart._command()
    assert cmd.endswith(autostart.BACKGROUND_FLAG)
    assert autostart._exe() in cmd


def test_hkcu_run_kulcs_per_felhasznalo():
    """A Run-kulcs a HKCU (per-felhasználó) ág – NEM kell rendszergazda."""
    assert autostart._RUN_KEY.lower().startswith("software\\microsoft\\windows")
    src = inspect.getsource(autostart)
    assert "HKEY_CURRENT_USER" in src
    assert "HKEY_LOCAL_MACHINE" not in src   # sehol NE írjunk gépszintű ágat


def test_enable_gatolt_ha_nem_frozen():
    """Forrásból az enable() érthető hibát dob (nincs stabil exe-út)."""
    import pytest
    with pytest.raises(RuntimeError):
        autostart.enable()


def test_gui_hatter_es_talca_bekotes():
    """A GUI-oldali bekötés meglétének őre: tálca-ikon osztály, háttérmódú
    bezárás (tálcára minimalizál, nem lép ki), és EGY-példány-védelem (ne fusson
    két RecordManager → dupla időzített felvétel)."""
    import pytest
    pytest.importorskip("wx")
    import superdl_gui as G
    assert hasattr(G, "_SuperDLTrayIcon")
    for m in ("_enter_background", "_show_from_tray", "_quit_app", "_ensure_tray",
              "_add_autostart_switch"):
        assert hasattr(G.MainFrame, m), f"hiányzik: {m}"
    close_src = inspect.getsource(G.MainFrame._on_close)
    assert "_bg_mode" in close_src and "Veto" in close_src
    main_src = inspect.getsource(G.main)
    assert "_instance_is_first" in main_src   # egy-példány-védelem
    assert "_enter_background" in main_src     # háttér-ág
