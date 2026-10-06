"""A programajánló szűrői nem veszik el a billentyűzetes fókuszt."""

from datetime import date, datetime

import wx

from modules_src.szervezes.szervezes_mod import programok
from modules_src.szervezes.szervezes_mod.programwin import ProgramFrame, idoszak_hatarok


def test_weekend_limits_include_current_sunday_only():
    assert idoszak_hatarok(3, date(2026, 10, 11)) == (
        date(2026, 10, 11), date(2026, 10, 11))


def test_choice_filter_preserves_focus_and_tab_to_results(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(programok, "osszegyujt", lambda: programok.ProgramGyujtemeny((), ()))
    frame = ProgramFrame(None)
    frame.Show()
    try:
        event = programok.Program(
            "Koncert", datetime(2026, 11, 2, 19, 0, tzinfo=programok.BUDAPEST),
            "Budapest", "Budapest Park", "Koncert és zene", "Budapest Park",
            "https://www.budapestpark.hu/events/koncert")
        frame._events = [event]
        frame.city.SetFocus()
        frame.period.SetSelection(4)
        frame.city.SetSelection(1)
        frame._apply_filters()
        assert wx.Window.FindFocus() is frame.city
        assert len(frame._visible) == 1
        frame.results.SetFocus()
        frame._focus_details()
        assert wx.Window.FindFocus() is frame.details
    finally:
        frame.Close()
        app.Yield()
