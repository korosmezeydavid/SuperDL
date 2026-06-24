"""Általános média-böngésző párbeszéd: egy forrás ÖSSZES tételének listája,
streameléssel és letöltéssel. Használja a podcast-feliratkozás RÉGEBBI epizódjait
és a figyelt YouTube-csatorna RÉGEBBI videóit is.

Akadálymentes: a listában fel/le nyíl; Enter = online lejátszás, D = letöltés,
Ctrl+C = az URL másolása, Szóköz = szünet, Esc = leállítás.
"""

import threading

import wx

from .audioengine import Player


class MediaListDialog(wx.Dialog):
    def __init__(self, parent, title, items, resolve_fn, download_fn,
                 subtitle_header="Forrás"):
        """items: (cím, alcím, URL) hármasok listája.
        resolve_fn(url) -> (stream_url, cím, hossz); közvetlen médiánál legyen
        az azonosság (url, '', 0). download_fn(url, cím) indítja a letöltést."""
        super().__init__(parent, title=title, size=(780, 540))
        self.items = list(items)
        self._resolve = resolve_fn
        self._download = download_fn
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._on_state, s)
        self._cur = None

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Tételek (Enter: online lejátszás, "
              "D: letöltés, Ctrl+C: URL másolása):"), 0, wx.ALL, 8)
        self.lst = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                               name="Tételek listája")
        self.lst.InsertColumn(0, "Cím", width=470)
        self.lst.InsertColumn(1, subtitle_header, width=250)
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
                ("&URL másolása (Ctrl+C)", lambda e: self._copy())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 5)
        v.Add(row, 0, wx.LEFT | wx.BOTTOM, 8)
        v.Add(wx.Button(p, wx.ID_CANCEL, "&Bezárás"), 0,
              wx.ALL | wx.ALIGN_RIGHT, 8)
        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in ("stop", "pause")}
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), id=ids["pause"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_CTRL, wx.WXK_SPACE, ids["pause"]),
        ]))

        self._refresh()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.lst.SetFocus()

    def _refresh(self):
        self.lst.DeleteAllItems()
        for title, sub, _url in self.items:
            i = self.lst.InsertItem(self.lst.GetItemCount(), title)
            self.lst.SetItem(i, 1, sub or "")
        if self.items:
            self.lst.Select(0)
            self.lst.Focus(0)

    def _selected(self):
        i = self.lst.GetFirstSelected()
        return self.items[i] if 0 <= i < len(self.items) else None

    def _announce(self, text):
        self.now.SetLabel(text)

    # ---- streamelés ----------------------------------------------------

    def _stream(self):
        it = self._selected()
        if not it:
            return
        title, _sub, url = it
        self._cur = title
        self._announce(f"Kapcsolódás: {title} …")

        def work():
            try:
                stream_url, _t, _d = self._resolve(url)
            except Exception as e:
                wx.CallAfter(self._announce, f"Nem játszható le: {title} – {e}")
                return
            if not stream_url:
                wx.CallAfter(self._announce, f"Nem elérhető: {title}.")
                return
            wx.CallAfter(self.player.play, stream_url, title)

        threading.Thread(target=work, daemon=True).start()

    def _on_state(self, text):
        if text == "lejátszás" and self._cur:
            self._announce(f"Most szól: {self._cur}  "
                           f"(hangerő {round(self.player.volume * 100)}%)")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba – {text}.")
        elif text == "vége":
            self._announce("A lejátszás véget ért.")

    def _toggle(self):
        if not self.player.is_active():
            return
        paused = self.player.toggle_pause()
        self._announce("Szünet." if paused else f"Folytatás: {self._cur or ''}")

    def _stop(self):
        if self.player.is_active():
            self.player.stop()
            self._announce("Leállítva.")

    # ---- letöltés / vágólap -------------------------------------------

    def _dl(self):
        it = self._selected()
        if not it:
            return
        title, _sub, url = it
        self._download(url, title)
        self._announce(f"Letöltés elindítva: {title}")

    def _copy(self):
        it = self._selected()
        if it and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(it[2]))
            wx.TheClipboard.Close()
            self._announce("Az URL a vágólapra másolva.")

    def _on_key(self, e):
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._stream()
        elif code in (ord('D'), ord('d')) and not ctrl:
            self._dl()
        elif ctrl and code == ord('C'):
            self._copy()
        else:
            e.Skip()

    def _on_close(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        e.Skip()
