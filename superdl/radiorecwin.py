"""Rádiófelvétel párbeszédek: időzítés beállítása és a felvételek kezelése.

Akadálymentes: minden mezőnek beszédes neve és gyorsbillentyűje (&) van;
a listákban fel/le nyíllal mozogsz, a műveletek gombbal és billentyűvel is
elérhetők.
"""

from datetime import datetime, timedelta

import wx

from .radiorec import Schedule, WEEKDAY_NAMES


class ScheduleDialog(wx.Dialog):
    """Egy időzített felvétel beállítása. Az állomást a KEDVENCEK közül egy
    legördülőből választod (átfedő/párhuzamos időzítések is megadhatók)."""

    def __init__(self, parent, stations, manager, preselect=0):
        super().__init__(parent, title="Időzített rádiófelvétel",
                         size=(560, 560))
        # stations: [(név, url), …] – jellemzően a kedvencek
        self.stations = list(stations)
        self.manager = manager

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        v.Add(wx.StaticText(p, label="&Állomás (a kedvencek közül):"), 0,
              wx.LEFT | wx.TOP, 10)
        self.station_choice = wx.Choice(
            p, choices=[n for n, _u in self.stations])
        self.station_choice.SetName("Felveendő állomás")
        if 0 <= preselect < len(self.stations):
            self.station_choice.SetSelection(preselect)
        elif self.stations:
            self.station_choice.SetSelection(0)
        v.Add(self.station_choice, 0, wx.ALL | wx.EXPAND, 8)

        now = datetime.now()
        # --- kezdés ---
        v.Add(wx.StaticText(p, label="Kezdés időpontja:"), 0, wx.LEFT, 10)
        r1 = wx.BoxSizer(wx.HORIZONTAL)
        r1.Add(wx.StaticText(p, label="Ó&ra:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sh = wx.SpinCtrl(p, min=0, max=23, initial=now.hour)
        self.sh.SetName("Kezdés órája")
        r1.Add(self.sh, 0, wx.RIGHT, 12)
        r1.Add(wx.StaticText(p, label="&Perc:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sm = wx.SpinCtrl(p, min=0, max=59, initial=0)
        self.sm.SetName("Kezdés perce")
        r1.Add(self.sm, 0)
        v.Add(r1, 0, wx.ALL, 8)

        # --- befejezés ---
        v.Add(wx.StaticText(p, label="Befejezés időpontja:"), 0, wx.LEFT, 10)
        r2 = wx.BoxSizer(wx.HORIZONTAL)
        r2.Add(wx.StaticText(p, label="Óra (&v):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.eh = wx.SpinCtrl(p, min=0, max=23, initial=(now.hour + 1) % 24)
        self.eh.SetName("Befejezés órája")
        r2.Add(self.eh, 0, wx.RIGHT, 12)
        r2.Add(wx.StaticText(p, label="Perc (&c):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.em = wx.SpinCtrl(p, min=0, max=59, initial=0)
        self.em.SetName("Befejezés perce")
        r2.Add(self.em, 0)
        v.Add(r2, 0, wx.ALL, 8)

        # --- ismétlés ---
        v.Add(wx.StaticText(p, label="&Ismétlés:"), 0, wx.LEFT | wx.TOP, 10)
        self.rep = wx.Choice(p, choices=[
            "Egyszeri (a következő alkalommal)",
            "Minden nap",
            "A hét kijelölt napjain"])
        self.rep.SetSelection(0)
        self.rep.SetName("Ismétlés módja")
        self.rep.Bind(wx.EVT_CHOICE, self._on_rep)
        v.Add(self.rep, 0, wx.ALL | wx.EXPAND, 8)

        # --- hétköznapok (csak heti ismétlésnél) ---
        self.day_box = wx.StaticBox(p, label="Napok (heti ismétlésnél)")
        dsz = wx.StaticBoxSizer(self.day_box, wx.HORIZONTAL)
        self.day_chk = []
        for i, name in enumerate(WEEKDAY_NAMES):
            c = wx.CheckBox(p, label=name)
            c.SetName(name)
            c.Enable(False)
            self.day_chk.append(c)
            dsz.Add(c, 0, wx.RIGHT, 6)
        v.Add(dsz, 0, wx.ALL | wx.EXPAND, 8)

        # --- gombok ---
        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        p.SetSizer(v)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.station_choice.SetFocus()

    def _on_rep(self, _evt):
        weekly = self.rep.GetSelection() == 2
        for c in self.day_chk:
            c.Enable(weekly)

    def _on_ok(self, evt):
        sh, sm = self.sh.GetValue(), self.sm.GetValue()
        eh, em = self.eh.GetValue(), self.em.GetValue()
        if (sh, sm) == (eh, em):
            wx.MessageBox("A kezdés és a befejezés időpontja nem lehet azonos.",
                          "Időzítés", wx.OK | wx.ICON_WARNING, self)
            return
        rep = {0: "once", 1: "daily", 2: "weekly"}[self.rep.GetSelection()]
        weekdays = [i for i, c in enumerate(self.day_chk) if c.IsChecked()]
        if rep == "weekly" and not weekdays:
            wx.MessageBox("Heti ismétlésnél jelölj ki legalább egy napot.",
                          "Időzítés", wx.OK | wx.ICON_WARNING, self)
            return
        si = self.station_choice.GetSelection()
        if not (0 <= si < len(self.stations)):
            wx.MessageBox("Válassz ki egy állomást a legördülőből.",
                          "Időzítés", wx.OK | wx.ICON_WARNING, self)
            return
        station_name, url = self.stations[si]
        date = ""
        if rep == "once":
            now = datetime.now()
            start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
            if start <= now:
                start += timedelta(days=1)      # ma már elmúlt → holnap
            date = start.strftime("%Y-%m-%d")
        self.result = Schedule(
            id=self.manager.new_id(), station_name=station_name,
            url=url, start_h=sh, start_m=sm, end_h=eh, end_m=em,
            repeat=rep, weekdays=weekdays, date=date)
        evt.Skip()        # bezárja a párbeszédet ID_OK-kal


class RecordingsDialog(wx.Dialog):
    """A folyó felvételek és a mentett időzítések kezelése."""

    def __init__(self, parent, manager):
        super().__init__(parent, title="Rádiófelvételek kezelése",
                         size=(720, 560))
        self.manager = manager

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        v.Add(wx.StaticText(p, label="Most folyó &felvételek "
              "(Delete vagy „Leállítás”: leállítás és mentés):"), 0,
              wx.ALL, 8)
        self.act_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.act_list.SetName("Folyó felvételek")
        self.act_list.InsertColumn(0, "Állomás", width=300)
        self.act_list.InsertColumn(1, "Eltelt idő", width=120)
        self.act_list.InsertColumn(2, "Fájl", width=260)
        self.act_list.Bind(wx.EVT_KEY_DOWN, self._on_act_key)
        v.Add(self.act_list, 1, wx.EXPAND | wx.ALL, 8)
        b_stop = wx.Button(p, label="Kijelölt felvétel &leállítása")
        b_stop.Bind(wx.EVT_BUTTON, lambda e: self._stop_active())
        v.Add(b_stop, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="Mentett &időzítések "
              "(szóköz: be/ki, Delete: törlés):"), 0, wx.ALL, 8)
        self.sch_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.sch_list.SetName("Időzített felvételek")
        self.sch_list.InsertColumn(0, "Időzítés", width=680)
        self.sch_list.Bind(wx.EVT_KEY_DOWN, self._on_sch_key)
        v.Add(self.sch_list, 1, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        b_tog = wx.Button(p, label="Be / &kikapcsolás")
        b_tog.Bind(wx.EVT_BUTTON, lambda e: self._toggle())
        b_del = wx.Button(p, label="&Törlés")
        b_del.Bind(wx.EVT_BUTTON, lambda e: self._delete())
        row.Add(b_tog, 0, wx.RIGHT, 6)
        row.Add(b_del, 0)
        v.Add(row, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.Button(p, wx.ID_CANCEL, "&Bezárás"), 0,
              wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)

        self._refresh()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._refresh_active(), self.timer)
        self.timer.Start(1500)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.sch_list.SetFocus()

    # ---- frissítés ----------------------------------------------------

    def _refresh(self):
        self._refresh_active()
        self._refresh_sched()

    def _refresh_active(self):
        self._active = self.manager.snapshot_active()
        sel = self.act_list.GetFirstSelected()
        self.act_list.DeleteAllItems()
        for r in self._active:
            i = self.act_list.InsertItem(self.act_list.GetItemCount(),
                                         r.station_name)
            m, s = divmod(r.elapsed_s(), 60)
            self.act_list.SetItem(i, 1, f"{m}:{s:02d}")
            self.act_list.SetItem(i, 2, r.path.name)
        if 0 <= sel < self.act_list.GetItemCount():
            self.act_list.Select(sel)

    def _refresh_sched(self):
        self._sched = self.manager.list_schedules()
        self.sch_list.DeleteAllItems()
        for s in self._sched:
            self.sch_list.InsertItem(self.sch_list.GetItemCount(),
                                     s.describe())

    # ---- folyó felvételek ---------------------------------------------

    def _stop_active(self):
        i = self.act_list.GetFirstSelected()
        if 0 <= i < len(self._active):
            self._active[i].stop()
            wx.CallLater(600, self._refresh_active)

    def _on_act_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._stop_active()
        else:
            e.Skip()

    # ---- időzítések ---------------------------------------------------

    def _toggle(self):
        i = self.sch_list.GetFirstSelected()
        if 0 <= i < len(self._sched):
            s = self._sched[i]
            self.manager.set_enabled(s.id, not s.enabled)
            self._refresh_sched()
            self.sch_list.Select(i)

    def _delete(self):
        i = self.sch_list.GetFirstSelected()
        if 0 <= i < len(self._sched):
            s = self._sched[i]
            self.manager.remove_schedule(s.id)
            self._refresh_sched()

    def _on_sch_key(self, e):
        code = e.GetKeyCode()
        if code == wx.WXK_DELETE:
            self._delete()
        elif code == wx.WXK_SPACE:
            self._toggle()
        else:
            e.Skip()

    def _on_close(self, e):
        self.timer.Stop()
        e.Skip()
