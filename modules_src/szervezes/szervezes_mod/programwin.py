"""Egyszerű, billentyűzettel kezelhető programajánló ablak."""

import threading
import webbrowser
from datetime import datetime, timedelta

import wx

from superdl import urlpolicy
from . import programok


HELP = """PROGRAMOK ÉS SZÓRAKOZÁS

A város, az időszak és a műfaj legördülő listájában a nyilakkal választhatsz.
Tabbal léphetsz a következő mezőre. A kereső a már letöltött műsorban keres.
A találatok között fel/le nyíllal haladhatsz; Enterrel a részletekhez lépsz.
Escape a részleteknél visszavisz a találatokhoz. F5 újra lekéri a műsort.

Jelenleg a Müpa, a Móricz Zsigmond Színház, a Budapest Park, az ARTMozi,
valamint a Cinema City Arena és Nyíregyháza nyilvános programlistája szerepel.
A kínálat nem teljes országos programjegyzék.
Jegyvásárlás az alkalmazáson belül nincs; az eredeti oldal külön nyitható meg.
"""


def idoszak_hatarok(index, today):
    """A választott időszak két befoglaló dátumhatára."""
    if index == 0:  # következő 30 nap
        return today, today + timedelta(days=29)
    if index == 1:  # ma
        return today, today
    if index == 2:  # következő hét nap
        return today, today + timedelta(days=6)
    if index == 3:  # következő hétvége (vagy az aktuális hétvége)
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        if today.weekday() == 6:
            saturday = today - timedelta(days=1)
        return today if today.weekday() >= 5 else saturday, saturday + timedelta(days=1)
    return today, None


class ProgramFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Programok és szórakozás", size=(900, 670))
        self._closing = False
        self._loading = False
        self._events = []
        self._visible = []
        self._errors = ()
        self._build()
        self.CreateStatusBar()
        self.SetStatusText("Programok lekérdezése folyamatban…")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.city.SetFocus()
        wx.CallAfter(self._refresh)

    def _build(self):
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)

        for label, attr, choices, width in (
            ("&Város:", "city", ["Minden város", "Budapest", "Nyíregyháza"], 185),
            ("&Időszak:", "period", ["Következő 30 nap", "Ma", "Következő 7 nap", "Hétvége", "Összes elérhető"], 200),
            ("&Műfaj:", "genre", ["Minden műfaj", "Színház", "Mozi", "Koncert és zene", "Kulturális program"], 190),
        ):
            row.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            choice = wx.Choice(panel, choices=choices, size=(width, -1))
            choice.SetName(label.replace("&", "").rstrip(":"))
            choice.SetSelection(0)
            choice.Bind(wx.EVT_CHOICE, self._apply_filters)
            setattr(self, attr, choice)
            row.Add(choice, 0, wx.RIGHT, 12)
        root.Add(row, 0, wx.ALL, 8)

        search_row = wx.BoxSizer(wx.HORIZONTAL)
        search_row.Add(wx.StaticText(panel, label="&Keresés címben és helyszínben:"),
                       0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.search = wx.TextCtrl(panel)
        self.search.SetName("Keresés a letöltött programokban")
        self.search.Bind(wx.EVT_TEXT, self._apply_filters)
        search_row.Add(self.search, 1, wx.RIGHT, 8)
        refresh = wx.Button(panel, label="&Frissítés (F5)")
        refresh.Bind(wx.EVT_BUTTON, self._refresh)
        search_row.Add(refresh)
        root.Add(search_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        root.Add(wx.StaticText(panel, label="&Programok (Enter: részletek):"), 0, wx.LEFT, 8)
        self.results = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.results.SetName("Programok listája")
        self.results.Bind(wx.EVT_LISTBOX, self._on_select)
        self.results.Bind(wx.EVT_LISTBOX_DCLICK, self._focus_details)
        root.Add(self.results, 3, wx.EXPAND | wx.ALL, 8)

        root.Add(wx.StaticText(panel, label="&Részletek (csak olvasható):"), 0, wx.LEFT, 8)
        self.details = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.details.SetName("A kijelölt program részletei")
        root.Add(self.details, 2, wx.EXPAND | wx.ALL, 8)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        for label, callback in (("&Hivatkozás másolása", self._copy_link),
                                ("Megnyitás &böngészőben", self._open_browser),
                                ("&Bezárás", lambda event: self.Close())):
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, callback)
            actions.Add(button, 0, wx.RIGHT, 8)
        root.Add(actions, 0, wx.LEFT | wx.BOTTOM, 8)
        panel.SetSizer(root)

        refresh_id = wx.NewIdRef()
        help_id = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self._refresh, id=refresh_id)
        self.Bind(wx.EVT_MENU, self._show_help, id=help_id)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, refresh_id),
            (wx.ACCEL_NORMAL, wx.WXK_F1, help_id),
        ]))

    def _on_key(self, event):
        key = event.GetKeyCode()
        focus = wx.Window.FindFocus()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focus is self.results:
            self._focus_details()
        elif key == wx.WXK_ESCAPE and focus is self.details:
            self.results.SetFocus()
        else:
            event.Skip()

    def _show_help(self, event=None):
        from superdl.helpdialog import show_help
        show_help(self, "Programok és szórakozás", HELP)

    def _refresh(self, event=None):
        if self._closing or self._loading:
            return
        self._loading = True
        self.SetStatusText("Programok lekérdezése folyamatban…")

        def work():
            try:
                data = programok.osszegyujt()
            except Exception as exc:
                wx.CallAfter(self._on_load_error, str(exc))
            else:
                wx.CallAfter(self._on_loaded, data)

        threading.Thread(target=work, daemon=True).start()

    def _on_load_error(self, error):
        if self._closing:
            return
        self._loading = False
        self.SetStatusText("A programok nem frissültek: " + error)

    def _on_loaded(self, data):
        if self._closing:
            return
        self._loading = False
        self._events = list(data.programok)
        self._errors = data.hibak
        self._apply_filters()

    def _selected(self):
        index = self.results.GetSelection()
        return self._visible[index] if 0 <= index < len(self._visible) else None

    def _apply_filters(self, event=None):
        if self._closing:
            return
        selected = self._selected()
        today = datetime.now(programok.BUDAPEST).date()
        start, end = idoszak_hatarok(self.period.GetSelection(), today)
        city = "" if self.city.GetSelection() == 0 else self.city.GetStringSelection()
        genre = "" if self.genre.GetSelection() == 0 else self.genre.GetStringSelection()
        self._visible = programok.szur_programok(
            self._events, varos=city, ettol=start, eddig=end,
            mufaj=genre, kereses=self.search.GetValue())
        self.results.Set([f"{item.kezdet:%Y. %m. %d. %H:%M} – {item.varos} – "
                          f"{item.cim} – {item.helyszin}" for item in self._visible])
        if self._visible:
            index = self._visible.index(selected) if selected in self._visible else 0
            self.results.SetSelection(index)
            self._show_details(self._visible[index])
        else:
            self.details.SetValue("Nincs program a megadott szűrőkkel.")
        error_note = (f"; {len(self._errors)} forrás nem volt elérhető"
                      if self._errors else "")
        self.SetStatusText(f"{len(self._visible)} program a szűrésben, "
                           f"{len(self._events)} összesen{error_note}. "
                           "Tabbal léphetsz a találatokhoz.")
        # Szűréskor soha nem állítunk fókuszt: a nyilakkal szabadon járható a Choice.

    def _on_select(self, event):
        item = self._selected()
        if item:
            self._show_details(item)

    def _show_details(self, item):
        self.details.SetValue(item.felolvasas() + "\n\nEredeti oldal: " + item.url)

    def _focus_details(self, event=None):
        if self._selected():
            self.details.SetFocus()
            self.details.SetInsertionPoint(0)

    def _copy_link(self, event):
        item = self._selected()
        if not item:
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(item.url))
                self.SetStatusText("Hivatkozás a vágólapra másolva.")
            finally:
                wx.TheClipboard.Close()

    def _open_browser(self, event):
        item = self._selected()
        if item and urlpolicy.is_web_url(item.url):
            webbrowser.open(item.url)

    def _on_close(self, event):
        self._closing = True
        event.Skip()
