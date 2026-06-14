"""Internetes rádió ablak: keresés (név/címke/ország) és népszerű
állomások, kedvencek, és élő lejátszás a streaming hangmotorral.

Akadálymentes: a listákban fel/le nyíllal mozogsz; a lejátszó-vezérlők
gombokkal ÉS gyorsbillentyűkkel is elérhetők, amelyek nem ütköznek a lista
navigációjával.
"""

import threading

import wx

from . import radio as R
from . import store
from .audioengine import Player
from .radiorecwin import RecordingsDialog, ScheduleDialog


class RadioFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Internetes rádió",
                         size=(900, 640))
        self.main = main
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._on_state, s)
        self.rec = getattr(main, "_record_mgr", None)   # felvétel-kezelő
        self._manual_rec = None                          # folyó kézi felvétel
        self.stations: list[R.Station] = []
        self.favorites: list[R.Station] = [
            self._from_rec(r) for r in store.load_radio_favorites()]
        self._cur: R.Station | None = None

        self._build()
        self._refresh_fav()
        self.CreateStatusBar()
        self.SetStatusText("Keress állomást, vagy nézd a népszerűeket. "
                           "Lejátszás: Enter. Hangerő: Ctrl+fel/le. Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.search_entry.SetFocus()

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="&Keresés:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.search_entry = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.search_entry.SetName("Keresőszó")
        self.search_entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_search())
        self.by_choice = wx.Choice(p, choices=["Név", "Címke (műfaj)", "Ország"])
        self.by_choice.SetSelection(0)
        self.by_choice.SetName("Mi szerint keressen")
        b_search = wx.Button(p, label="Ke&resés")
        b_search.Bind(wx.EVT_BUTTON, lambda e: self._on_search())
        b_top = wx.Button(p, label="&Népszerű állomások")
        b_top.Bind(wx.EVT_BUTTON, lambda e: self._on_top())
        row.Add(self.search_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.by_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(b_search, 0, wx.RIGHT, 6)
        row.Add(b_top, 0)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Állomások (Enter: lejátszás, "
              "Ctrl+B: kedvencekhez, Ctrl+C: URL):"), 0, wx.LEFT, 8)
        self.st_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.st_list.SetName("Állomások listája")
        for i, (t, w) in enumerate((("Név", 430), ("Ország", 170),
                                    ("Minőség", 150))):
            self.st_list.InsertColumn(i, t, width=w)
        self.st_list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.st_list.Bind(wx.EVT_CONTEXT_MENU, self._on_list_menu)
        self.st_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                          lambda e: self._play(self._selected()))
        v.Add(self.st_list, 3, wx.EXPAND | wx.ALL, 8)

        self.now_label = wx.StaticText(p, label="Most nem szól semmi.")
        self.now_label.SetName("Lejátszás állapota")
        v.Add(self.now_label, 0, wx.LEFT | wx.BOTTOM, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Le&játszás", lambda e: self._play(self._selected())),
                          ("&Szünet / folytatás", lambda e: self._toggle()),
                          ("&Leállítás", lambda e: self._stop()),
                          ("Hangerő −", lambda e: self._vol(-0.05)),
                          ("Hangerő +", lambda e: self._vol(0.05)),
                          ("&Kedvenc", lambda e: self._fav_selected())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 6)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        rec = wx.BoxSizer(wx.HORIZONTAL)
        self.rec_btn = wx.Button(p, label="&Felvétel most (F9)")
        self.rec_btn.Bind(wx.EVT_BUTTON, lambda e: self._record_now())
        b_sched = wx.Button(p, label="&Időzített felvétel… (Ctrl+R)")
        b_sched.Bind(wx.EVT_BUTTON, lambda e: self._schedule_dialog())
        b_recs = wx.Button(p, label="Fel&vételek kezelése… (Ctrl+Shift+F)")
        b_recs.Bind(wx.EVT_BUTTON, lambda e: self._recordings_dialog())
        for b in (self.rec_btn, b_sched, b_recs):
            rec.Add(b, 0, wx.RIGHT, 6)
        v.Add(rec, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="Ke&dvencek (Enter: lejátszás, "
              "Delete: törlés):"), 0, wx.LEFT, 8)
        self.fav_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.fav_list.SetName("Kedvenc állomások")
        self.fav_list.InsertColumn(0, "Név", width=430)
        self.fav_list.InsertColumn(1, "Ország", width=170)
        self.fav_list.Bind(wx.EVT_KEY_DOWN, self._on_fav_key)
        self.fav_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                           lambda e: self._play(self._fav_selected_station()))
        v.Add(self.fav_list, 2, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

        # gyorsbillentyűk (nem ütköznek a listák fel/le nyilával)
        ids = {k: wx.NewIdRef() for k in
               ("volup", "voldown", "stop", "pause", "play", "help", "fav",
                "rec", "sched", "recs")}
        self.Bind(wx.EVT_MENU, lambda e: self._vol(0.05), id=ids["volup"])
        self.Bind(wx.EVT_MENU, lambda e: self._vol(-0.05), id=ids["voldown"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), id=ids["pause"])
        self.Bind(wx.EVT_MENU, lambda e: self._play(self._selected()),
                  id=ids["play"])
        self.Bind(wx.EVT_MENU, lambda e: self._fav_selected(), id=ids["fav"])
        self.Bind(wx.EVT_MENU, lambda e: self._help(), id=ids["help"])
        self.Bind(wx.EVT_MENU, lambda e: self._record_now(), id=ids["rec"])
        self.Bind(wx.EVT_MENU, lambda e: self._schedule_dialog(),
                  id=ids["sched"])
        self.Bind(wx.EVT_MENU, lambda e: self._recordings_dialog(),
                  id=ids["recs"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, wx.WXK_UP, ids["volup"]),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, ids["voldown"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_CTRL, wx.WXK_SPACE, ids["pause"]),
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["play"]),
            (wx.ACCEL_CTRL, ord('D'), ids["fav"]),
            (wx.ACCEL_NORMAL, wx.WXK_F9, ids["rec"]),
            (wx.ACCEL_CTRL, ord('R'), ids["sched"]),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('F'), ids["recs"]),
            (wx.ACCEL_NORMAL, wx.WXK_F1, ids["help"]),
        ]))

    # ---- segédek ------------------------------------------------------

    @staticmethod
    def _from_rec(r: dict) -> R.Station:
        return R.Station(name=r.get("name", ""), url=r.get("url", ""),
                         codec=r.get("codec", ""), bitrate=r.get("bitrate", 0),
                         country=r.get("country", ""), tags=r.get("tags", ""),
                         uuid=r.get("uuid", ""))

    @staticmethod
    def _to_rec(s: R.Station) -> dict:
        return {"name": s.name, "url": s.url, "codec": s.codec,
                "bitrate": s.bitrate, "country": s.country, "tags": s.tags,
                "uuid": s.uuid}

    def _announce(self, text):
        self.SetStatusText(text)
        self.now_label.SetLabel(text)

    def _selected(self) -> R.Station | None:
        i = self.st_list.GetFirstSelected()
        return self.stations[i] if 0 <= i < len(self.stations) else None

    def _fav_selected_station(self) -> R.Station | None:
        i = self.fav_list.GetFirstSelected()
        return self.favorites[i] if 0 <= i < len(self.favorites) else None

    # ---- keresés ------------------------------------------------------

    def _on_search(self):
        q = self.search_entry.GetValue().strip()
        if not q:
            return
        by = {0: "name", 1: "tag", 2: "country"}[self.by_choice.GetSelection()]
        self._fetch(lambda: R.search(q, by=by), f"„{q}”")

    def _on_top(self):
        self._fetch(R.top, "népszerű állomások")

    def _fetch(self, fn, label):
        self.SetStatusText(f"Keresés: {label} …")

        def work():
            try:
                res = fn()
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Hiba: {e}")
                return
            wx.CallAfter(self._show, res, label)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, res, label):
        self.stations = res
        self.st_list.DeleteAllItems()
        for s in res:
            row = self.st_list.InsertItem(self.st_list.GetItemCount(), s.name)
            self.st_list.SetItem(row, 1, s.country)
            self.st_list.SetItem(row, 2, s.quality())
        self.SetStatusText(f"{len(res)} állomás – {label}.")
        if res:
            self.st_list.Select(0)
            self.st_list.Focus(0)
            self.st_list.SetFocus()

    # ---- lejátszás ----------------------------------------------------

    def _play(self, st: R.Station | None):
        if not st:
            return
        self._cur = st
        self._announce(f"Csatlakozás: {st.name} …")
        self.player.play(st.url, title=st.name)

    def _on_state(self, text):
        if text == "lejátszás" and self._cur:
            self._announce(f"Most szól: {self._cur.name}  "
                           f"(hangerő {round(self.player.volume * 100)}%)")
        elif text.startswith("hiba"):
            self._announce(f"Nem szól: {self._cur.name if self._cur else ''} – "
                           f"{text}. Próbálj másik állomást.")
        elif text == "vége":
            self._announce("Az adás megszakadt.")

    def _toggle(self):
        if not self.player.is_active():
            return
        paused = self.player.toggle_pause()
        self._announce("Szünet." if paused else
                       f"Folytatás: {self._cur.name if self._cur else ''}")

    def _stop(self):
        if self.player.is_active():
            self.player.stop()
            self._announce("Leállítva.")

    def _vol(self, delta):
        self.player.set_volume(self.player.volume + delta)
        self._announce(f"Hangerő: {round(self.player.volume * 100)} százalék"
                       + (f" – {self._cur.name}" if self._cur
                          and self.player.is_active() else "."))

    # ---- felvétel -----------------------------------------------------

    def _record_now(self):
        if not self.rec:
            self._announce("A felvétel-kezelő nem érhető el.")
            return
        if self._manual_rec and self._manual_rec.is_active():
            path = self._manual_rec.path
            self._manual_rec.stop()
            self._manual_rec = None
            self.rec_btn.SetLabel("&Felvétel most (F9)")
            self._announce(f"Felvétel leállítva és elmentve ide: {path}")
            return
        st = self._selected() or self._cur
        if not st:
            self._announce("Előbb válassz ki egy állomást a felvételhez.")
            return
        r = self.rec.start_manual(st.name, st.url)
        if r:
            self._manual_rec = r
            self.rec_btn.SetLabel("Felvétel &leállítása (F9)")
            self._announce(f"Felvétel folyamatban: {st.name}. "
                           f"Leállítás: F9. Mentés ide: {r.path}")
        else:
            self._announce("A felvétel nem indult el – próbáld újra, vagy "
                           "ellenőrizd, hogy az állomás szól-e.")

    def _schedule_dialog(self):
        if not self.rec:
            self._announce("A felvétel-kezelő nem érhető el.")
            return
        st = self._selected() or self._cur
        if not st:
            self._announce("Előbb válassz ki egy állomást az időzítéshez.")
            return
        dlg = ScheduleDialog(self, st.name, st.url, self.rec)
        if dlg.ShowModal() == wx.ID_OK and getattr(dlg, "result", None):
            self.rec.add_schedule(dlg.result)
            self._announce(f"Időzített felvétel mentve: {dlg.result.describe()}")
        dlg.Destroy()

    def _recordings_dialog(self):
        if not self.rec:
            self._announce("A felvétel-kezelő nem érhető el.")
            return
        dlg = RecordingsDialog(self, self.rec)
        dlg.ShowModal()
        dlg.Destroy()

    # ---- listák / kedvencek ------------------------------------------

    def _on_list_key(self, e):
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play(self._selected())
        elif ctrl and code == ord('B'):
            self._fav_selected()
        elif ctrl and code == ord('C'):
            self._copy_url(self._selected())
        else:
            e.Skip()

    def _on_list_menu(self, e):
        if not self._selected():
            return
        m = wx.Menu()
        mp = m.Append(wx.ID_ANY, "Le&játszás\tEnter")
        mf = m.Append(wx.ID_ANY, "&Kedvencekhez\tCtrl+B")
        mu = m.Append(wx.ID_ANY, "&URL másolása\tCtrl+C")
        self.Bind(wx.EVT_MENU, lambda e: self._play(self._selected()), mp)
        self.Bind(wx.EVT_MENU, lambda e: self._fav_selected(), mf)
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(self._selected()), mu)
        self.st_list.PopupMenu(m)
        m.Destroy()

    def _copy_url(self, st):
        if st and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(st.url))
            wx.TheClipboard.Close()
            self._announce(f"URL a vágólapra másolva: {st.url}")

    def _fav_selected(self):
        st = self._selected()
        if not st:
            return
        if any(f.uuid == st.uuid and f.url == st.url for f in self.favorites):
            self._announce("Ez már a kedvencek között van.")
            return
        self.favorites.append(st)
        self._save_fav()
        self._refresh_fav()
        self._announce(f"Kedvencekhez adva: {st.name}")

    def _refresh_fav(self):
        self.fav_list.DeleteAllItems()
        for s in self.favorites:
            row = self.fav_list.InsertItem(self.fav_list.GetItemCount(), s.name)
            self.fav_list.SetItem(row, 1, s.country)

    def _save_fav(self):
        store.save_radio_favorites([self._to_rec(f) for f in self.favorites])

    def _on_fav_key(self, e):
        code = e.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play(self._fav_selected_station())
        elif code == wx.WXK_DELETE:
            i = self.fav_list.GetFirstSelected()
            if 0 <= i < len(self.favorites):
                s = self.favorites.pop(i)
                self._save_fav()
                self._refresh_fav()
                self._announce(f"Törölve a kedvencekből: {s.name}")
        else:
            e.Skip()

    # ---- súgó / zárás -------------------------------------------------

    def _help(self):
        wx.MessageBox(
            "Internetes rádió – billentyűk\n\n"
            "Keresőmező: írd be, válaszd ki, mi szerint (Név / Címke / "
            "Ország), Enter = keresés. „Népszerű állomások” gomb is van.\n\n"
            "Állomáslista (fel/le nyíl a mozgás):\n"
            "  Enter vagy F5 – lejátszás\n"
            "  Ctrl+B – kedvencekhez\n"
            "  Ctrl+C – URL másolása\n"
            "  Menü-billentyű / jobb klikk – helyi menü\n\n"
            "Lejátszás közben (bárhol):\n"
            "  Ctrl+fel / Ctrl+le – hangerő\n"
            "  Ctrl+szóköz – szünet / folytatás\n"
            "  Escape – leállítás\n\n"
            "Felvétel:\n"
            "  F9 – a kijelölt állomás felvétele most (újra F9: leállítás)\n"
            "  Ctrl+R – időzített felvétel beállítása (mettől meddig, "
            "egyszeri / minden nap / a hét adott napjain)\n"
            "  Ctrl+Shift+F – a folyó felvételek és időzítések kezelése\n"
            "  A felvételek a célmappa „Rádiófelvételek” dátumozott "
            "almappájába kerülnek, MP3-ként. Az időzített felvételhez a "
            "program legyen nyitva a megadott időpontban.\n\n"
            "Kedvencek: Enter – lejátszás, Delete – törlés.",
            "Rádió súgó", wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        self._save_fav()
        if getattr(self.main, "_radio_win", None) is self:
            self.main._radio_win = None
        e.Skip()
