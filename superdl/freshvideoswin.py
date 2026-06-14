"""YouTube-csatornák: „Friss videók" ablak és a csatorna-feliratkozások
kezelése.

Akadálymentes: listákban fel/le nyíllal mozogsz, a műveletek gombbal ÉS
gyorsbillentyűvel is elérhetők. A friss videó Enterrel online lejátszható
(streamelés a beépített hangmotorral), D-vel letölthető.
"""

import threading

import wx

from .audioengine import Player


class FreshVideosDialog(wx.Dialog):
    """A figyelt csatornák friss videói: streamelés vagy letöltés."""

    def __init__(self, parent, manager, resolve_fn, download_fn):
        super().__init__(parent, title="SuperDL – Friss videók",
                         size=(760, 520))
        self.manager = manager
        self._resolve = resolve_fn          # resolve(url) -> (stream_url, cím, hossz)
        self._download = download_fn        # download(video)
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._on_state, s)
        self._cur = None

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Friss videók (Enter: online lejátszás, "
              "D: letöltés, Delete: eltávolítás a listából):"), 0, wx.ALL, 8)
        self.lst = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.lst.SetName("Friss videók listája")
        self.lst.InsertColumn(0, "Cím", width=470)
        self.lst.InsertColumn(1, "Csatorna", width=240)
        self.lst.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.lst.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._stream())
        v.Add(self.lst, 1, wx.EXPAND | wx.ALL, 8)

        self.now = wx.StaticText(p, label="Most nem szól semmi.")
        self.now.SetName("Lejátszás állapota")
        v.Add(self.now, 0, wx.LEFT | wx.BOTTOM, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("Le&játszás (Enter)", lambda e: self._stream()),
                ("&Letöltés (D)", lambda e: self._dl()),
                ("&Szünet (szóköz)", lambda e: self._toggle()),
                ("Le&állítás (Esc)", lambda e: self._stop()),
                ("&Eltávolítás (Del)", lambda e: self._remove()),
                ("Mind &törlése", lambda e: self._clear())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 5)
        v.Add(row, 0, wx.LEFT | wx.BOTTOM, 8)
        v.Add(wx.Button(p, wx.ID_CANCEL, "&Bezárás"), 0,
              wx.ALL | wx.ALIGN_RIGHT, 8)
        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in
               ("dl", "stop", "pause", "volup", "voldown")}
        self.Bind(wx.EVT_MENU, lambda e: self._dl(), id=ids["dl"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), id=ids["pause"])
        self.Bind(wx.EVT_MENU, lambda e: self._vol(0.05), id=ids["volup"])
        self.Bind(wx.EVT_MENU, lambda e: self._vol(-0.05), id=ids["voldown"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_CTRL, wx.WXK_SPACE, ids["pause"]),
            (wx.ACCEL_CTRL, wx.WXK_UP, ids["volup"]),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, ids["voldown"]),
        ]))

        self._refresh()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.lst.SetFocus()

    # ---- lista --------------------------------------------------------

    def _refresh(self):
        self.lst.DeleteAllItems()
        for vd in self.manager.fresh:
            i = self.lst.InsertItem(self.lst.GetItemCount(), vd.title)
            self.lst.SetItem(i, 1, vd.channel_title)
        if self.manager.fresh:
            self.lst.Select(0)
            self.lst.Focus(0)

    def _selected(self):
        i = self.lst.GetFirstSelected()
        return self.manager.fresh[i] if 0 <= i < len(self.manager.fresh) else None

    def _announce(self, text):
        self.now.SetLabel(text)

    # ---- streamelés ---------------------------------------------------

    def _stream(self):
        vd = self._selected()
        if not vd:
            return
        self._cur = vd
        self._announce(f"Kapcsolódás: {vd.title} …")

        def work():
            try:
                stream_url, title, _ = self._resolve(vd.url)
            except Exception as e:
                wx.CallAfter(self._announce,
                             f"Nem játszható le: {vd.title} – {e}")
                return
            if not stream_url:
                wx.CallAfter(self._announce,
                             f"Nem elérhető: {vd.title} (törölt vagy zárt).")
                return
            wx.CallAfter(self.player.play, stream_url, vd.title)
        threading.Thread(target=work, daemon=True).start()

    def _on_state(self, text):
        if text == "lejátszás" and self._cur:
            self._announce(f"Most szól: {self._cur.title}  "
                           f"(hangerő {round(self.player.volume * 100)}%)")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba – {text}.")
        elif text == "vége":
            self._announce("A lejátszás véget ért.")

    def _toggle(self):
        if not self.player.is_active():
            return
        paused = self.player.toggle_pause()
        self._announce("Szünet." if paused else
                       f"Folytatás: {self._cur.title if self._cur else ''}")

    def _stop(self):
        if self.player.is_active():
            self.player.stop()
            self._announce("Leállítva.")

    def _vol(self, d):
        self.player.set_volume(self.player.volume + d)
        self._announce(f"Hangerő: {round(self.player.volume * 100)} százalék.")

    # ---- letöltés / lista-műveletek -----------------------------------

    def _dl(self):
        vd = self._selected()
        if not vd:
            return
        self._download(vd)
        self.manager.remove_fresh(vd)
        self._refresh()
        self._announce(f"Letöltés elindítva: {vd.title}")

    def _remove(self):
        vd = self._selected()
        if vd:
            self.manager.remove_fresh(vd)
            self._refresh()
            self._announce(f"Eltávolítva a listából: {vd.title}")

    def _clear(self):
        self.manager.clear_fresh()
        self._refresh()
        self._announce("A friss videók listája kiürítve.")

    def _on_key(self, e):
        code = e.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._stream()
        elif code in (ord('D'), ord('d')):
            self._dl()
        elif code == wx.WXK_DELETE:
            self._remove()
        else:
            e.Skip()

    def _on_close(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        e.Skip()


class ChannelsDialog(wx.Dialog):
    """YouTube-csatorna feliratkozások kezelése."""

    def __init__(self, parent, manager, subscribe_fn, check_fn):
        super().__init__(parent, title="YouTube-csatornák kezelése",
                         size=(640, 460))
        self.manager = manager
        self._subscribe = subscribe_fn      # subscribe_fn(url) háttérben
        self._check = check_fn              # check_fn() ellenőrzés most

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Feliratkozott &csatornák "
              "(szóköz: automatikus figyelés be/ki, Delete: törlés):"), 0,
              wx.ALL, 8)
        self.lst = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.lst.SetName("Csatornák listája")
        self.lst.InsertColumn(0, "Csatorna", width=440)
        self.lst.InsertColumn(1, "Figyelés", width=140)
        self.lst.Bind(wx.EVT_KEY_DOWN, self._on_key)
        v.Add(self.lst, 1, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        b_add = wx.Button(p, label="Ú&j csatorna…")
        b_add.Bind(wx.EVT_BUTTON, lambda e: self._add())
        b_tog = wx.Button(p, label="Figyelés be/&ki")
        b_tog.Bind(wx.EVT_BUTTON, lambda e: self._toggle())
        b_del = wx.Button(p, label="&Törlés")
        b_del.Bind(wx.EVT_BUTTON, lambda e: self._delete())
        b_chk = wx.Button(p, label="&Ellenőrzés most")
        b_chk.Bind(wx.EVT_BUTTON, lambda e: self._check())
        for b in (b_add, b_tog, b_del, b_chk):
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.LEFT | wx.BOTTOM, 8)
        v.Add(wx.Button(p, wx.ID_CANCEL, "&Bezárás"), 0,
              wx.ALL | wx.ALIGN_RIGHT, 8)
        p.SetSizer(v)

        self._refresh()
        self.lst.SetFocus()

    def _refresh(self):
        self.lst.DeleteAllItems()
        for c in self.manager.channels:
            i = self.lst.InsertItem(self.lst.GetItemCount(),
                                    c.title or c.url)
            self.lst.SetItem(i, 1, "automatikus" if c.auto else "kikapcsolva")
        if self.manager.channels:
            self.lst.Select(0)

    def _sel(self):
        i = self.lst.GetFirstSelected()
        return self.manager.channels[i] if 0 <= i < len(self.manager.channels) \
            else None

    def _add(self):
        dlg = wx.TextEntryDialog(
            self, "A YouTube-csatorna címe (URL), pl. "
            "https://www.youtube.com/@csatornanev", "Új csatorna")
        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.GetValue().strip()
            if url:
                self._subscribe(url, self._refresh)
        dlg.Destroy()

    def _toggle(self):
        c = self._sel()
        if c:
            c.auto = not c.auto
            self.manager.save()
            i = self.lst.GetFirstSelected()
            self._refresh()
            if 0 <= i < self.lst.GetItemCount():
                self.lst.Select(i)

    def _delete(self):
        c = self._sel()
        if c:
            self.manager.unsubscribe(c.url)
            self._refresh()

    def _on_key(self, e):
        code = e.GetKeyCode()
        if code == wx.WXK_DELETE:
            self._delete()
        elif code == wx.WXK_SPACE:
            self._toggle()
        else:
            e.Skip()
