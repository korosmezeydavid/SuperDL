"""Podcast-felfedező ablak: keresés és ország-top az Apple/iTunes API-val,
feliratkozás a meglévő FeedManager-rel.

Akadálymentes: a találati listában fel/le nyíllal mozogsz, Enter = feliratkozás,
a helyi menü (jobb klikk / Menü-billentyű) ad további műveleteket.
"""

import threading
import webbrowser

import wx

from . import podcast as P


class PodcastFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Podcastok felfedezése",
                         size=(860, 600))
        self.main = main
        self.results: list[P.Podcast] = []

        self._build()
        self.CreateStatusBar()
        self.SetStatusText("Keress podcastot, vagy nézd egy ország "
                           "legnépszerűbbjeit. Feliratkozás: Enter.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.search_entry.SetFocus()

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # keresősor
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="&Keresés:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.search_entry = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.search_entry.SetName("Keresőszó")
        self.search_entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_search())
        b_search = wx.Button(p, label="Ke&resés")
        b_search.Bind(wx.EVT_BUTTON, lambda e: self._on_search())
        row.Add(self.search_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(b_search, 0)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # ország-top sor
        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(wx.StaticText(p, label="&Ország:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.country_choice = wx.Choice(
            p, choices=[name for name, _c in P.COUNTRIES])
        self.country_choice.SetName("Ország választása")
        self.country_choice.SetSelection(self._saved_country_index())
        b_top = wx.Button(p, label="&Top podcastok ebben az országban")
        b_top.Bind(wx.EVT_BUTTON, lambda e: self._on_top())
        crow.Add(self.country_choice, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        crow.Add(b_top, 0)
        v.Add(crow, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(
            p, label="&Találatok (Enter: feliratkozás az új epizódokra, "
                     "Ctrl+C: URL, Menü-billentyű: több művelet):"),
            0, wx.LEFT, 8)
        self.list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName("Podcastok listája")
        for i, (t, w) in enumerate((("Név", 380), ("Szerző", 250),
                                    ("Műfaj", 170))):
            self.list.InsertColumn(i, t, width=w)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.list.Bind(wx.EVT_CONTEXT_MENU, self._on_list_menu)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                       lambda e: self._subscribe())
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

    # ---- ország-emlékezet ---------------------------------------------

    def _saved_country_index(self) -> int:
        s = getattr(self.main, "settings", None)
        code = (s.get("podcast_country") if isinstance(s, dict) else "") or "hu"
        return next((i for i, (_n, c) in enumerate(P.COUNTRIES) if c == code), 0)

    def _country_code(self) -> str:
        i = self.country_choice.GetSelection()
        return P.COUNTRIES[i][1] if 0 <= i < len(P.COUNTRIES) else "hu"

    # ---- keresés / top ------------------------------------------------

    def _on_search(self):
        q = self.search_entry.GetValue().strip()
        if not q:
            return
        cc = self._country_code()
        self._fetch(lambda: P.search(q, country=cc), f"„{q}”")

    def _on_top(self):
        cc = self._country_code()
        s = getattr(self.main, "settings", None)
        if isinstance(s, dict):
            s["podcast_country"] = cc            # utolsó ország megjegyzése
        name = self.country_choice.GetStringSelection()
        self._fetch(lambda: P.top(country=cc), f"{name} – legnépszerűbb")

    def _fetch(self, fn, label):
        self.SetStatusText(f"Lekérdezés: {label} …")

        def work():
            try:
                res = fn()
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Hiba: {e}")
                return
            wx.CallAfter(self._show, res, label)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, res, label):
        self.results = res
        self.list.DeleteAllItems()
        for pod in res:
            row = self.list.InsertItem(self.list.GetItemCount(), pod.name)
            self.list.SetItem(row, 1, pod.author)
            self.list.SetItem(row, 2, pod.genre)
        self.SetStatusText(f"{len(res)} podcast – {label}.")
        if res:
            self.list.Select(0)
            self.list.Focus(0)
            self.list.SetFocus()

    # ---- műveletek ----------------------------------------------------

    def _selected(self) -> P.Podcast | None:
        i = self.list.GetFirstSelected()
        return self.results[i] if 0 <= i < len(self.results) else None

    def _on_list_key(self, e):
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._subscribe()
        elif ctrl and code == ord('C'):
            self._copy_url()
        else:
            e.Skip()

    def _on_list_menu(self, e):
        if not self._selected():
            return
        m = wx.Menu()
        ms = m.Append(wx.ID_ANY, "&Feliratkozás\tEnter")
        mo = m.Append(wx.ID_ANY, "Meg&nyitás a böngészőben")
        mu = m.Append(wx.ID_ANY, "&URL (RSS) másolása\tCtrl+C")
        self.Bind(wx.EVT_MENU, lambda e: self._subscribe(), ms)
        self.Bind(wx.EVT_MENU, lambda e: self._open_browser(), mo)
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), mu)
        self.list.PopupMenu(m)
        m.Destroy()

    def _subscribe(self):
        pod = self._selected()
        if not pod:
            return
        if hasattr(self.main, "_do_subscribe"):
            self.main._do_subscribe(pod.feed_url)
            self.SetStatusText(f"Feliratkozás: {pod.name} – csak az új "
                               "epizódokat tölti majd le.")
        else:
            self.SetStatusText("A feliratkozás-kezelő nem érhető el.")

    def _open_browser(self):
        pod = self._selected()
        if pod and pod.page_url:
            webbrowser.open(pod.page_url)
            self.SetStatusText(f"Megnyitva a böngészőben: {pod.name}")
        elif pod:
            self.SetStatusText("Ehhez a podcasthoz nincs weboldal.")

    def _copy_url(self):
        pod = self._selected()
        if pod and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(pod.feed_url))
            wx.TheClipboard.Close()
            self.SetStatusText(f"RSS-cím a vágólapra másolva: {pod.feed_url}")

    def _on_close(self, e):
        if getattr(self.main, "_podcast_win", None) is self:
            self.main._podcast_win = None
        self.Destroy()
