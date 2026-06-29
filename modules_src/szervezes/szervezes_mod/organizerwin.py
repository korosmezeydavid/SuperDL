"""Naptár / teendők / jegyzetek + külső naptár (ICS) – akadálymentes ablak.

NEM vizuális hónap-rács, hanem nap szerinti, nyilakkal bejárható AGENDA-lista
a közelgő eseményekről, plusz teendők és jegyzetek külön füleken, és az
ICS-link feliratkozások kezelése.
"""

from datetime import date, datetime

import wx

from superdl import organizer as O   # a naptár-backend a Core-ban marad (agenda + indítás)
from . import rezsi as R              # rezsi/költség-kalkulátor (a fülhöz)

REMINDERS = [("Nincs", -1), ("Pontban", 0), ("5 perccel előtte", 5),
             ("10 perccel előtte", 10), ("15 perccel előtte", 15),
             ("30 perccel előtte", 30), ("1 órával előtte", 60)]
REPEATS = [("Egyszeri", O.REPEAT_NONE), ("Minden nap", O.REPEAT_DAILY),
           ("A hét adott napjain", O.REPEAT_WEEKLY)]
ACTIONS = [("Nincs", O.ACTION_NONE),
           ("Megnyitás (hivatkozás / fájl / levél)", O.ACTION_OPEN),
           ("Szöveg felolvasása a megadott időben", O.ACTION_SPEAK)]


# ====================== fő ablak =======================================

class OrganizerFrame(wx.Frame):
    def __init__(self, main, manager: O.OrganizerManager):
        super().__init__(main, title="SuperDL – Naptár, teendők, jegyzetek",
                         size=(880, 620))
        self.main = main
        self.mgr = manager

        self.nb = wx.Notebook(self)
        self._build_agenda()
        self._build_tasks()
        self._build_notes()
        self._build_rezsi()
        self._build_ics()
        self.CreateStatusBar()
        self._announce(f"Ma {date.today().isoformat()} van. Lapozz a fülek "
                       "között a Ctrl+Tab billentyűvel.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.refresh_all()

    def _announce(self, text):
        self.SetStatusText(text)

    def refresh_all(self):
        self._refresh_agenda()
        self._refresh_tasks()
        self._refresh_notes()
        self._refresh_ics()

    # ---- AGENDA fül ---------------------------------------------------

    def _build_agenda(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Közelgő események (a következő 30 nap). "
              "Enter: szerkesztés, Delete: törlés (csak saját esemény)."),
              0, wx.ALL, 8)
        self.ag_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.ag_list.SetName("Közelgő események")
        for i, (t, w) in enumerate((("Mikor", 200), ("Esemény", 440),
                                    ("Forrás", 120))):
            self.ag_list.InsertColumn(i, t, width=w)
        self.ag_list.Bind(wx.EVT_KEY_DOWN, self._on_ag_key)
        self.ag_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._edit_event())
        v.Add(self.ag_list, 1, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Ú&j esemény…", lambda e: self._new_event()),
                          ("&Szerkesztés…", lambda e: self._edit_event()),
                          ("&Törlés", lambda e: self._delete_event()),
                          ("Mai &dátum és idő", lambda e: self._say_now())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 6)
        p.SetSizer(v)
        self.nb.AddPage(p, "Agenda")

    def _refresh_agenda(self):
        self._agenda = self.mgr.upcoming(days=30)
        self.ag_list.DeleteAllItems()
        for dt, ev in self._agenda:
            when = (f"{dt.strftime('%Y-%m-%d')} {ev.time}"
                    if ev.time != "egész nap"
                    else f"{dt.strftime('%Y-%m-%d')} egész nap")
            row = self.ag_list.InsertItem(self.ag_list.GetItemCount(), when)
            self.ag_list.SetItem(row, 1, ev.title)
            self.ag_list.SetItem(row, 2,
                                 "Külső" if ev.source == "ics" else "Saját")
        self._announce(f"{len(self._agenda)} közelgő esemény.")

    def _sel_event(self):
        i = self.ag_list.GetFirstSelected()
        return self._agenda[i][1] if 0 <= i < len(self._agenda) else None

    def _on_ag_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._delete_event()
        else:
            e.Skip()

    def _new_event(self):
        dlg = EventDialog(self, None)
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.mgr.add_event(dlg.result)
            self._refresh_agenda()
            self._announce(f"Esemény mentve: {dlg.result.title}")
        dlg.Destroy()

    def _edit_event(self):
        ev = self._sel_event()
        if not ev:
            return
        if ev.source == "ics":
            self._announce("A külső (ICS) események csak megtekinthetők, nem "
                           "szerkeszthetők itt.")
            return
        dlg = EventDialog(self, ev)
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.mgr.update_event(ev)
            self._refresh_agenda()
            self._announce(f"Esemény frissítve: {ev.title}")
        dlg.Destroy()

    def _delete_event(self):
        ev = self._sel_event()
        if not ev:
            return
        if ev.source == "ics":
            self._announce("A külső események törléséhez a feliratkozást "
                           "távolítsd el a Külső naptár fülön.")
            return
        self.mgr.remove_event(ev.id)
        self._refresh_agenda()
        self._announce(f"Esemény törölve: {ev.title}")

    def _say_now(self):
        now = datetime.now()
        self._announce(now.strftime("Ma %Y-%m-%d, pontos idő %H:%M."))

    # ---- TEENDŐK fül --------------------------------------------------

    def _build_tasks(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Teendők. Szóköz: kész/visszavon, "
              "Delete: törlés."), 0, wx.ALL, 8)
        self.tk_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.tk_list.SetName("Teendők")
        for i, (t, w) in enumerate((("Kész", 70), ("Teendő", 470),
                                    ("Határidő", 150))):
            self.tk_list.InsertColumn(i, t, width=w)
        self.tk_list.Bind(wx.EVT_KEY_DOWN, self._on_tk_key)
        self.tk_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._toggle_task())
        v.Add(self.tk_list, 1, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Ú&j teendő…", lambda e: self._new_task()),
                          ("&Kész / visszavon", lambda e: self._toggle_task()),
                          ("&Törlés", lambda e: self._delete_task())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 6)
        p.SetSizer(v)
        self.nb.AddPage(p, "Teendők")

    def _refresh_tasks(self):
        self.tk_list.DeleteAllItems()
        for t in self.mgr.tasks:
            row = self.tk_list.InsertItem(self.tk_list.GetItemCount(),
                                          "kész" if t.done else "–")
            self.tk_list.SetItem(row, 1, t.title)
            self.tk_list.SetItem(row, 2, t.due or "")

    def _sel_task(self):
        i = self.tk_list.GetFirstSelected()
        return self.mgr.tasks[i] if 0 <= i < len(self.mgr.tasks) else None

    def _on_tk_key(self, e):
        code = e.GetKeyCode()
        if code == wx.WXK_DELETE:
            self._delete_task()
        elif code == wx.WXK_SPACE:
            self._toggle_task()
        else:
            e.Skip()

    def _new_task(self):
        dlg = TaskDialog(self, None)
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.mgr.add_task(dlg.result)
            self._refresh_tasks()
            self._announce(f"Teendő hozzáadva: {dlg.result.title}")
        dlg.Destroy()

    def _toggle_task(self):
        t = self._sel_task()
        if t:
            self.mgr.toggle_task(t.id)
            self._refresh_tasks()
            self._announce(f"{t.title}: {'kész' if not t.done else 'visszavonva'}.")

    def _delete_task(self):
        t = self._sel_task()
        if t:
            self.mgr.remove_task(t.id)
            self._refresh_tasks()
            self._announce(f"Teendő törölve: {t.title}")

    # ---- JEGYZETEK fül ------------------------------------------------

    def _build_notes(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Jegyzetek. Enter: megnyitás, "
              "Delete: törlés."), 0, wx.ALL, 8)
        self.nt_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.nt_list.SetName("Jegyzetek")
        self.nt_list.InsertColumn(0, "Cím", width=480)
        self.nt_list.InsertColumn(1, "Létrehozva", width=180)
        self.nt_list.Bind(wx.EVT_KEY_DOWN, self._on_nt_key)
        self.nt_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._edit_note())
        v.Add(self.nt_list, 1, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Ú&j jegyzet…", lambda e: self._new_note()),
                          ("&Megnyitás…", lambda e: self._edit_note()),
                          ("&Törlés", lambda e: self._delete_note())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 6)
        p.SetSizer(v)
        self.nb.AddPage(p, "Jegyzetek")

    def _refresh_notes(self):
        self.nt_list.DeleteAllItems()
        for n in self.mgr.notes:
            row = self.nt_list.InsertItem(self.nt_list.GetItemCount(), n.title)
            self.nt_list.SetItem(row, 1, n.created)

    def _sel_note(self):
        i = self.nt_list.GetFirstSelected()
        return self.mgr.notes[i] if 0 <= i < len(self.mgr.notes) else None

    def _on_nt_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._delete_note()
        else:
            e.Skip()

    def _new_note(self):
        dlg = NoteDialog(self, None)
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.mgr.add_note(dlg.result)
            self._refresh_notes()
            self._announce(f"Jegyzet mentve: {dlg.result.title}")
        dlg.Destroy()

    def _edit_note(self):
        n = self._sel_note()
        if not n:
            return
        dlg = NoteDialog(self, n)
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.mgr.save()
            self._refresh_notes()
            self._announce(f"Jegyzet frissítve: {n.title}")
        dlg.Destroy()

    def _delete_note(self):
        n = self._sel_note()
        if n:
            self.mgr.remove_note(n.id)
            self._refresh_notes()
            self._announce(f"Jegyzet törölve: {n.title}")

    # ---- REZSI / KÖLTSÉG-KALKULÁTOR fül ------------------------------

    def _build_rezsi(self):
        self.rz = R.RezsiData.load()
        self._rz_unlocked = not self.rz.has_pin()
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)

        # zár-réteg (PIN): csak akkor látszik, ha lakat van és még nincs feloldva
        self.rz_lock = wx.Panel(p)
        lv = wx.BoxSizer(wx.VERTICAL)
        lv.Add(wx.StaticText(self.rz_lock,
               label="Ez a fül zárolva. Add meg a PIN-kódot a feloldáshoz:"),
               0, wx.ALL, 8)
        lr = wx.BoxSizer(wx.HORIZONTAL)
        self.rz_pin = wx.TextCtrl(self.rz_lock, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER,
                                  size=(120, -1))
        self.rz_pin.SetName("PIN-kód a rezsi-fül feloldásához")
        self.rz_pin.Bind(wx.EVT_TEXT_ENTER, lambda e: self._rz_unlock())
        b_unlock = wx.Button(self.rz_lock, label="&Feloldás")
        b_unlock.Bind(wx.EVT_BUTTON, lambda e: self._rz_unlock())
        lr.Add(self.rz_pin, 0, wx.RIGHT, 6)
        lr.Add(b_unlock, 0)
        lv.Add(lr, 0, wx.LEFT | wx.BOTTOM, 8)
        self.rz_lock.SetSizer(lv)
        v.Add(self.rz_lock, 0, wx.EXPAND)

        # tartalom-réteg: a lista + vezérlők + összesítés
        self.rz_body = wx.Panel(p)
        bv = wx.BoxSizer(wx.VERTICAL)
        bv.Add(wx.StaticText(self.rz_body,
               label="&Rendszeres és egyszeri költségek:"), 0, wx.LEFT | wx.TOP, 4)
        self.rz_list = wx.ListCtrl(self.rz_body,
                                   style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.rz_list.SetName("Költségtételek listája")
        for i, (c, w) in enumerate((("Név", 160), ("Összeg (Ft)", 100),
                                    ("Gyakoriság", 110), ("Esed. nap", 80),
                                    ("Megjegyzés", 200))):
            self.rz_list.InsertColumn(i, c, width=w)
        self.rz_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._rz_edit())
        bv.Add(self.rz_list, 1, wx.EXPAND | wx.ALL, 4)

        br = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Ú&j tétel", self._rz_add),
                          ("S&zerkesztés", self._rz_edit),
                          ("&Törlés", self._rz_del),
                          ("&Naptárba (emlékeztetők)", self._rz_to_calendar),
                          ("&Lakat (PIN)", self._rz_set_pin)):
            b = wx.Button(self.rz_body, label=label)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fn: f())
            br.Add(b, 0, wx.RIGHT, 5)
        bv.Add(br, 0, wx.LEFT | wx.BOTTOM, 4)

        self.rz_sum = wx.StaticText(self.rz_body, label="")
        self.rz_sum.SetName("Költség-összesítés")
        bv.Add(self.rz_sum, 0, wx.LEFT | wx.BOTTOM, 6)
        self.rz_body.SetSizer(bv)
        v.Add(self.rz_body, 1, wx.EXPAND)

        p.SetSizer(v)
        self.nb.AddPage(p, "Rezsi")
        self._rz_apply_lock()

    def _rz_apply_lock(self):
        """A zár/tartalom réteg láthatóságának frissítése."""
        locked = self.rz.has_pin() and not self._rz_unlocked
        self.rz_lock.Show(locked)
        self.rz_body.Show(not locked)
        self.rz_lock.GetParent().Layout()
        if not locked:
            self._refresh_rezsi()

    def _rz_unlock(self):
        if self.rz.check_pin(self.rz_pin.GetValue()):
            self._rz_unlocked = True
            self.rz_pin.SetValue("")
            self._rz_apply_lock()
            self._announce("Rezsi-fül feloldva.")
        else:
            self.rz_pin.SetValue("")
            self._announce("Hibás PIN-kód.")

    def _refresh_rezsi(self):
        self.rz_list.DeleteAllItems()
        for i, it in enumerate(self.rz.items):
            self.rz_list.InsertItem(i, it.name)
            self.rz_list.SetItem(i, 1, f"{it.amount:,.0f}".replace(",", " "))
            self.rz_list.SetItem(i, 2, it.period)
            self.rz_list.SetItem(i, 3, "—" if it.period == "egyszeri" else str(it.day))
            self.rz_list.SetItem(i, 4, it.note)
        m = self.rz.monthly_total()
        y = self.rz.yearly_total()
        o = self.rz.onetime_total()
        txt = (f"Havi összesen (ismétlődő): {m:,.0f} Ft   ·   "
               f"Éves összesen: {y:,.0f} Ft").replace(",", " ")
        if o:
            txt += f"   ·   Egyszeri tételek: {o:,.0f} Ft".replace(",", " ")
        self.rz_sum.SetLabel(txt)

    def _rz_selected(self):
        i = self.rz_list.GetFirstSelected()
        return i if 0 <= i < len(self.rz.items) else -1

    def _rz_add(self):
        dlg = RezsiItemDialog(self, None)
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.rz.items.append(dlg.result)
            self.rz.save()
            self._refresh_rezsi()
            self._announce(f"Tétel hozzáadva: {dlg.result.name}.")
        dlg.Destroy()

    def _rz_edit(self):
        i = self._rz_selected()
        if i < 0:
            self._announce("Előbb válassz egy tételt.")
            return
        dlg = RezsiItemDialog(self, self.rz.items[i])
        if dlg.ShowModal() == wx.ID_OK and dlg.result:
            self.rz.items[i] = dlg.result
            self.rz.save()
            self._refresh_rezsi()
            self._announce("Tétel módosítva.")
        dlg.Destroy()

    def _rz_del(self):
        i = self._rz_selected()
        if i < 0:
            return
        name = self.rz.items[i].name
        if wx.MessageBox(f"Törlöd ezt a tételt?\n\n{name}", "Rezsi",
                         wx.YES_NO | wx.ICON_QUESTION, self) == wx.YES:
            self.rz.items.pop(i)
            self.rz.save()
            self._refresh_rezsi()
            self._announce(f"Tétel törölve: {name}.")

    def _rz_to_calendar(self):
        """Minden ISMÉTLŐDŐ tételhez emlékeztetőt tesz a naptárba a KÖVETKEZŐ
        esedékességre (a naptár-backend nincs havi ismétlés, ezért egyszeri
        emlékeztető a következő dátumra)."""
        from calendar import monthrange
        today = date.today()
        added = 0
        for it in self.rz.items:
            if it.period == "egyszeri":
                continue
            day = max(1, min(it.day, 28))
            y, mo = today.year, today.month
            if day < today.day:                    # ehavi nap elmúlt → jövő hónap
                mo += 1
                if mo > 12:
                    mo, y = 1, y + 1
            day = min(day, monthrange(y, mo)[1])
            due = date(y, mo, day)
            ev = O.Event(id=O.new_id(),
                         title=f"Rezsi: {it.name} – {it.amount:,.0f} Ft".replace(",", " "),
                         date=due.isoformat(), time="08:00",
                         note=it.note or "Esedékes költség (rezsi-kalkulátor).",
                         reminder_min=O.REMINDER_DEFAULT if hasattr(O, "REMINDER_DEFAULT") else 10)
            self.mgr.add_event(ev)
            added += 1
        self.refresh_all()
        self._announce(f"{added} emlékeztető a naptárba a következő "
                       "esedékességekre." if added else
                       "Nincs ismétlődő tétel a naptárba tételhez.")

    def _rz_set_pin(self):
        if self.rz.has_pin():
            msg = ("A fül jelenleg PIN-lakattal védett.\n\nÚj PIN beírása "
                   "megváltoztatja; ÜRESEN hagyva a lakatot TÖRLÖD.\n\nÚj PIN "
                   "(max 6 számjegy):")
        else:
            msg = ("Állíts be PIN-kódot (max 6 számjegy), hogy a rezsi-fülbe "
                   "csak az nézhessen bele, aki ismeri.\n\n(Üresen hagyva nincs "
                   "lakat.) PIN:")
        dlg = wx.TextEntryDialog(self, msg, "Rezsi – PIN-lakat")
        if dlg.ShowModal() == wx.ID_OK:
            pin = "".join(c for c in dlg.GetValue() if c.isdigit())[:6]
            self.rz.set_pin(pin)
            if pin:
                self._announce("PIN-lakat beállítva. Legközelebb a fül "
                               "megnyitásakor kéri.")
            else:
                self._rz_unlocked = True
                self._announce("PIN-lakat törölve.")
        dlg.Destroy()

    # ---- KÜLSŐ NAPTÁR (ICS) fül --------------------------------------

    def _build_ics(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Külső naptár-feliratkozások (read-only, "
              "ICS-link). Az események az Agenda fülön jelennek meg."),
              0, wx.ALL, 8)
        self.ics_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.ics_list.SetName("ICS-feliratkozások")
        for i, (t, w) in enumerate((("Név", 240), ("Cím (URL)", 360),
                                    ("Utolsó frissítés", 160))):
            self.ics_list.InsertColumn(i, t, width=w)
        self.ics_list.Bind(wx.EVT_KEY_DOWN, self._on_ics_key)
        v.Add(self.ics_list, 1, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("Ú&j feliratkozás…", lambda e: self._new_ics()),
                ("&Honnan szerzem a linket?", lambda e: self._ics_help()),
                ("&Frissítés most", lambda e: self._sync_ics()),
                ("&Törlés", lambda e: self._delete_ics())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 6)
        p.SetSizer(v)
        self.nb.AddPage(p, "Külső naptár")

    def _refresh_ics(self):
        self.ics_list.DeleteAllItems()
        for s in self.mgr.ics_subs:
            row = self.ics_list.InsertItem(self.ics_list.GetItemCount(), s.name)
            self.ics_list.SetItem(row, 1, s.url)
            self.ics_list.SetItem(row, 2, s.last_sync or "még nem")

    def _sel_ics(self):
        i = self.ics_list.GetFirstSelected()
        return self.mgr.ics_subs[i] if 0 <= i < len(self.mgr.ics_subs) else None

    def _on_ics_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._delete_ics()
        else:
            e.Skip()

    def _new_ics(self):
        dlg = IcsDialog(self)
        if dlg.ShowModal() == wx.ID_OK and dlg.url:
            self.mgr.add_ics(dlg.name, dlg.url)
            self._refresh_ics()
            self._announce("Feliratkozás mentve. Frissítés folyamatban…")
            self._sync_ics()
        dlg.Destroy()

    def _delete_ics(self):
        s = self._sel_ics()
        if s:
            self.mgr.remove_ics(s.id)
            self._refresh_ics()
            self._refresh_agenda()
            self._announce(f"Feliratkozás törölve: {s.name}")

    def _sync_ics(self):
        import threading
        self._announce("Külső naptárak frissítése…")

        def work():
            summary = self.mgr.sync_ics()
            wx.CallAfter(self._sync_done, summary)

        threading.Thread(target=work, daemon=True).start()

    def _sync_done(self, summary):
        self._refresh_ics()
        self._refresh_agenda()
        self._announce(f"Külső naptárak frissítve: {summary}.")

    def _ics_help(self):
        IcsHelpDialog(self).ShowModal()

    def _on_close(self, e):
        if getattr(self.main, "_organizer_win", None) is self:
            self.main._organizer_win = None
        self.Destroy()


# ====================== párbeszédek ====================================

class EventDialog(wx.Dialog):
    """Esemény felvétele/szerkesztése emlékeztetővel, ismétléssel, akcióval."""

    def __init__(self, parent, ev: O.Event | None):
        super().__init__(parent, title="Esemény", size=(560, 640))
        self.ev = ev
        self.result = None
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        v.Add(wx.StaticText(p, label="&Cím:"), 0, wx.LEFT | wx.TOP, 8)
        self.title = wx.TextCtrl(p, value=ev.title if ev else "")
        self.title.SetName("Cím")
        v.Add(self.title, 0, wx.EXPAND | wx.ALL, 8)

        dr = wx.BoxSizer(wx.HORIZONTAL)
        dr.Add(wx.StaticText(p, label="&Dátum (ÉÉÉÉ-HH-NN):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.date = wx.TextCtrl(
            p, value=(ev.date if ev else date.today().isoformat()),
            size=(120, -1))
        self.date.SetName("Dátum (év-hónap-nap)")
        dr.Add(self.date, 0, wx.RIGHT, 12)
        dr.Add(wx.StaticText(p, label="&Óra:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        hh, mm = (ev.time.split(":") + ["0"])[:2] if ev and ":" in ev.time \
            else (str(datetime.now().hour), "0")
        self.sh = wx.SpinCtrl(p, min=0, max=23, initial=int(hh))
        self.sh.SetName("Óra")
        dr.Add(self.sh, 0, wx.RIGHT, 8)
        dr.Add(wx.StaticText(p, label="&Perc:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sm = wx.SpinCtrl(p, min=0, max=59, initial=int(mm))
        self.sm.SetName("Perc")
        dr.Add(self.sm, 0)
        v.Add(dr, 0, wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Jegyzet (nem kötelező):"), 0,
              wx.LEFT, 8)
        self.note = wx.TextCtrl(p, value=ev.note if ev else "",
                                style=wx.TE_MULTILINE, size=(-1, 60))
        self.note.SetName("Jegyzet")
        v.Add(self.note, 0, wx.EXPAND | wx.ALL, 8)

        rr = wx.BoxSizer(wx.HORIZONTAL)
        rr.Add(wx.StaticText(p, label="E&mlékeztető:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.remind = wx.Choice(p, choices=[n for n, _ in REMINDERS])
        self.remind.SetName("Emlékeztető")
        self.remind.SetSelection(self._remind_index())
        rr.Add(self.remind, 0, wx.RIGHT, 12)
        rr.Add(wx.StaticText(p, label="&Ismétlés:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.repeat = wx.Choice(p, choices=[n for n, _ in REPEATS])
        self.repeat.SetName("Ismétlés")
        self.repeat.SetSelection(self._repeat_index())
        self.repeat.Bind(wx.EVT_CHOICE, self._on_repeat)
        rr.Add(self.repeat, 0)
        v.Add(rr, 0, wx.ALL, 8)

        self.day_chk = []
        dsz = wx.StaticBoxSizer(wx.StaticBox(p, label="Napok (heti ismétlésnél)"),
                                wx.HORIZONTAL)
        for i, name in enumerate(O.WEEKDAYS):
            c = wx.CheckBox(p, label=name)
            c.SetName(name)
            if ev and i in (ev.weekdays or []):
                c.SetValue(True)
            c.Enable(self.repeat.GetSelection() == 2)
            self.day_chk.append(c)
            dsz.Add(c, 0, wx.RIGHT, 4)
        v.Add(dsz, 0, wx.ALL | wx.EXPAND, 8)

        ar = wx.BoxSizer(wx.HORIZONTAL)
        ar.Add(wx.StaticText(p, label="&Akció a megadott időben:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.action = wx.Choice(p, choices=[n for n, _ in ACTIONS])
        self.action.SetName("Akció a megadott időben")
        self.action.SetSelection(self._action_index())
        ar.Add(self.action, 1)
        v.Add(ar, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="Akció adata (URL / fájl / mailto:cím, "
              "vagy a felolvasandó szöveg):"), 0, wx.LEFT, 8)
        self.action_data = wx.TextCtrl(p, value=ev.action_data if ev else "")
        self.action_data.SetName("Akció adata (URL, fájl, mailto-cím vagy szöveg)")
        v.Add(self.action_data, 0, wx.EXPAND | wx.ALL, 8)

        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.title.SetFocus()

    def _remind_index(self):
        val = self.ev.reminder_min if self.ev else 10
        return next((i for i, (_n, v) in enumerate(REMINDERS) if v == val), 3)

    def _repeat_index(self):
        val = self.ev.repeat if self.ev else O.REPEAT_NONE
        return next((i for i, (_n, v) in enumerate(REPEATS) if v == val), 0)

    def _action_index(self):
        val = self.ev.action_type if self.ev else O.ACTION_NONE
        return next((i for i, (_n, v) in enumerate(ACTIONS) if v == val), 0)

    def _on_repeat(self, _e):
        weekly = self.repeat.GetSelection() == 2
        for c in self.day_chk:
            c.Enable(weekly)

    def _on_ok(self, e):
        title = self.title.GetValue().strip()
        if not title:
            wx.MessageBox("Adj címet az eseménynek.", "Esemény",
                          wx.OK | wx.ICON_WARNING, self)
            return
        try:
            d = date.fromisoformat(self.date.GetValue().strip())
        except ValueError:
            wx.MessageBox("A dátum formátuma ÉÉÉÉ-HH-NN legyen, pl. "
                          f"{date.today().isoformat()}.", "Esemény",
                          wx.OK | wx.ICON_WARNING, self)
            return
        repeat = REPEATS[self.repeat.GetSelection()][1]
        weekdays = [i for i, c in enumerate(self.day_chk) if c.IsChecked()]
        if repeat == O.REPEAT_WEEKLY and not weekdays:
            wx.MessageBox("Heti ismétlésnél jelölj ki legalább egy napot.",
                          "Esemény", wx.OK | wx.ICON_WARNING, self)
            return
        ev = self.ev or O.Event(id=O.new_id(), title="", date="", time="")
        ev.title = title
        ev.date = d.isoformat()
        ev.time = f"{self.sh.GetValue():02d}:{self.sm.GetValue():02d}"
        ev.note = self.note.GetValue().strip()
        ev.reminder_min = REMINDERS[self.remind.GetSelection()][1]
        ev.repeat = repeat
        ev.weekdays = weekdays
        ev.action_type = ACTIONS[self.action.GetSelection()][1]
        ev.action_data = self.action_data.GetValue().strip()
        ev.source = "local"
        ev.last_reminded = ev.last_actioned = ""    # új idő → újra elsülhet
        self.result = ev
        e.Skip()


class TaskDialog(wx.Dialog):
    def __init__(self, parent, task: O.Task | None):
        super().__init__(parent, title="Teendő", size=(480, 320))
        self.task = task
        self.result = None
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Teendő:"), 0, wx.LEFT | wx.TOP, 8)
        self.title = wx.TextCtrl(p, value=task.title if task else "")
        self.title.SetName("Teendő")
        v.Add(self.title, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Határidő (ÉÉÉÉ-HH-NN, nem kötelező):"),
              0, wx.LEFT, 8)
        self.due = wx.TextCtrl(p, value=task.due if task else "")
        self.due.SetName("Határidő (év-hónap-nap)")
        v.Add(self.due, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Jegyzet:"), 0, wx.LEFT, 8)
        self.note = wx.TextCtrl(p, value=task.note if task else "",
                                name="Jegyzet",
                                style=wx.TE_MULTILINE, size=(-1, 60))
        v.Add(self.note, 0, wx.EXPAND | wx.ALL, 8)
        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.title.SetFocus()

    def _on_ok(self, e):
        title = self.title.GetValue().strip()
        if not title:
            wx.MessageBox("Adj nevet a teendőnek.", "Teendő",
                          wx.OK | wx.ICON_WARNING, self)
            return
        due = self.due.GetValue().strip()
        if due:
            try:
                date.fromisoformat(due)
            except ValueError:
                wx.MessageBox("A határidő formátuma ÉÉÉÉ-HH-NN legyen.",
                              "Teendő", wx.OK | wx.ICON_WARNING, self)
                return
        t = self.task or O.Task(id=O.new_id(), title="")
        t.title, t.due, t.note = title, due, self.note.GetValue().strip()
        self.result = t
        e.Skip()


class RezsiItemDialog(wx.Dialog):
    """Egy rezsi/költség-tétel hozzáadása vagy szerkesztése."""

    def __init__(self, parent, item):
        super().__init__(parent, title="Költségtétel", size=(460, 380))
        self.result = None
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Megnevezés (pl. Áram, Internet):"),
              0, wx.LEFT | wx.TOP, 8)
        self.name = wx.TextCtrl(p, value=item.name if item else "")
        self.name.SetName("A költség megnevezése")
        v.Add(self.name, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="Ö&sszeg (Ft):"), 0, wx.LEFT, 8)
        self.amount = wx.TextCtrl(p, value=(f"{item.amount:g}" if item else ""))
        self.amount.SetName("Összeg forintban")
        v.Add(self.amount, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Gyakoriság:"), 0, wx.LEFT, 8)
        self.period = wx.Choice(p, choices=R.PERIODS)
        self.period.SetName("Milyen gyakran fizetendő")
        self.period.SetSelection(R.PERIODS.index(item.period)
                                 if item and item.period in R.PERIODS else 0)
        v.Add(self.period, 0, wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Esedékesség (a hónap napja, 1–31):"),
              0, wx.LEFT, 8)
        self.day = wx.SpinCtrl(p, min=1, max=31, initial=item.day if item else 1)
        self.day.SetName("A hónap melyik napján esedékes")
        v.Add(self.day, 0, wx.ALL, 8)
        v.Add(wx.StaticText(p, label="Meg&jegyzés (nem kötelező):"), 0, wx.LEFT, 8)
        self.note = wx.TextCtrl(p, value=item.note if item else "",
                                name="Megjegyzés")
        v.Add(self.note, 0, wx.EXPAND | wx.ALL, 8)
        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.name.SetFocus()

    def _on_ok(self, e):
        name = self.name.GetValue().strip()
        if not name:
            wx.MessageBox("Adj megnevezést a tételnek.", "Költségtétel",
                          wx.OK | wx.ICON_WARNING, self)
            return
        try:
            amount = float(self.amount.GetValue().replace(" ", "").replace(",", "."))
        except ValueError:
            wx.MessageBox("Az összeg egy szám legyen (Ft).", "Költségtétel",
                          wx.OK | wx.ICON_WARNING, self)
            return
        self.result = R.Item(name=name, amount=amount,
                             period=R.PERIODS[self.period.GetSelection()],
                             day=self.day.GetValue(),
                             note=self.note.GetValue().strip())
        e.Skip()


class NoteDialog(wx.Dialog):
    def __init__(self, parent, note: O.Note | None):
        super().__init__(parent, title="Jegyzet", size=(560, 440))
        self.note = note
        self.result = None
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Cím:"), 0, wx.LEFT | wx.TOP, 8)
        self.title = wx.TextCtrl(p, value=note.title if note else "")
        self.title.SetName("Cím")
        v.Add(self.title, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Szöveg:"), 0, wx.LEFT, 8)
        self.body = wx.TextCtrl(p, value=note.body if note else "",
                                name="Szöveg",
                                style=wx.TE_MULTILINE, size=(-1, 240))
        v.Add(self.body, 1, wx.EXPAND | wx.ALL, 8)
        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.title.SetFocus()

    def _on_ok(self, e):
        title = self.title.GetValue().strip()
        if not title:
            wx.MessageBox("Adj címet a jegyzetnek.", "Jegyzet",
                          wx.OK | wx.ICON_WARNING, self)
            return
        if self.note:
            self.note.title = title
            self.note.body = self.body.GetValue()
            self.result = self.note
        else:
            self.result = O.Note(
                id=O.new_id(), title=title, body=self.body.GetValue(),
                created=datetime.now().strftime("%Y-%m-%d %H:%M"))
        e.Skip()


class IcsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Új ICS-naptárfeliratkozás",
                         size=(620, 280))
        self.name = ""
        self.url = ""
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Név (szabadon választható):"), 0,
              wx.LEFT | wx.TOP, 8)
        self.name_txt = wx.TextCtrl(p, name="Naptár neve")
        v.Add(self.name_txt, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="ICS- (iCal-) &link (titkos cím):"), 0,
              wx.LEFT, 8)
        self.url_txt = wx.TextCtrl(p, name="ICS-link (iCal cím)")
        v.Add(self.url_txt, 0, wx.EXPAND | wx.ALL, 8)
        help_btn = wx.Button(p, label="&Honnan szerzem ezt a linket?")
        help_btn.Bind(wx.EVT_BUTTON, lambda e: IcsHelpDialog(self).ShowModal())
        v.Add(help_btn, 0, wx.ALL, 8)
        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.url_txt.SetFocus()

    def _on_ok(self, e):
        url = self.url_txt.GetValue().strip()
        if not (url.startswith("http://") or url.startswith("https://")
                or url.startswith("webcal://")):
            wx.MessageBox("Adj meg egy érvényes ICS-linket (http, https vagy "
                          "webcal kezdetű).", "ICS",
                          wx.OK | wx.ICON_WARNING, self)
            return
        if url.startswith("webcal://"):
            url = "https://" + url[len("webcal://"):]
        self.url = url
        self.name = self.name_txt.GetValue().strip()
        e.Skip()


class IcsHelpDialog(wx.Dialog):
    """Hol szerezhető a titkos iCal-link szolgáltatónként."""

    TEXT = (
        "A legtöbb naptár-szolgáltatás ad egy TITKOS iCal-linket (read-only), "
        "amivel a SuperDL csak OLVASNI tudja a naptáradat. Hol találod:\n\n"
        "GOOGLE NAPTÁR (számítógépen):\n"
        "  Beállítások → a bal oldalon a naptár neve → „Naptár integrálása” → "
        "„Titkos cím iCal formátumban”. Másold ki, és illeszd be ide.\n\n"
        "MICROSOFT / OUTLOOK.COM:\n"
        "  Beállítások → Naptár → Megosztott naptárak → „Naptár közzététele” "
        "→ ICS-hivatkozás. Másold ki.\n\n"
        "APPLE ICLOUD:\n"
        "  iCloud.com → Naptár → a naptár melletti megosztás ikon → „Nyilvános "
        "naptár” bekapcsolása → a webcal-cím másolása (a SuperDL átalakítja).\n\n"
        "CALENDLY és más szolgáltatások:\n"
        "  Keresd a „Subscribe / iCal / ICS feed” lehetőséget a "
        "beállításokban.\n\n"
        "FONTOS: ez a link TITKOS – aki ismeri, láthatja a naptáradat. Csak "
        "olyannak add meg, akiben megbízol. A SuperDL csak olvassa, nem "
        "módosítja a naptáradat.")

    def __init__(self, parent):
        super().__init__(parent, title="Honnan szerzem az ICS-linket?",
                         size=(640, 540))
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        t = wx.TextCtrl(p, value=self.TEXT,
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        t.SetName("ICS-súgó szövege")
        v.Add(t, 1, wx.EXPAND | wx.ALL, 10)
        v.Add(wx.Button(p, wx.ID_OK, "&Bezárás"), 0,
              wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
