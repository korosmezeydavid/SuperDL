"""Super Surf – natív lista és olvasómező a SuperDL RSS-olvasó mintájára."""
from __future__ import annotations

import html
import threading
import webbrowser

import wx

from .models import ResearchQuery
from .service import ResearchService

MODES = (
    ("Wikipédia – teljes cikk", "wikipedia_search", "Keresőszó, például Budapest"),
    ("Cikk webcímről", "article_url", "Cikk webcíme: https://…"),
    ("Időjárás", "weather", "Település, például Budapest"),
    ("Árfolyam", "exchange_rate", "Pénznempár, például EUR HUF"),
    ("Angol szótár", "dictionary", "Angol szó, például hello"),
)

HELP = (
    "SUPER SURF – KUTATÁS ÉS OLVASÁS\n\n"
    "Válassz forrást, írd be a keresést vagy cikk webcímét, majd Enter.\n"
    "A fejezeteken fel/le nyíllal lépkedhetsz. Enter: a kijelölt fejezet "
    "szövege. A szövegből Escape visszavisz a fejezetlistára.\n"
    "F5: új lekérdezés. Ctrl+F: keresőmező. F1: ez a súgó. "
    "A teljes eredmény másolható vagy menthető.\n\n"
    "Az angol szótár csak angol szavakat ismer. Az árfolyam nem valós idejű banki adat."
    " A Wikipédia keresés a találat teljes olvasható cikkét fejezetekre bontva mutatja."
)


def sections_from_content(content) -> list[tuple[str, str]]:
    """A H2/H3 címekből nyíllal járható fejezetlista készül."""
    lines = ([content.byline] if content.byline else [])
    if content.published_at:
        lines.append("Megjelenés: " + content.published_at)
    sections, label = [], "Összefoglaló"

    def flush():
        if lines:
            sections.append((label, "\n\n".join(lines)))

    for block in content.blocks:
        if block.kind == "heading":
            flush()
            label = ("Alfejezet: " if block.level >= 3 else "") + block.text
            lines = []
        elif block.kind == "list":
            lines.append("\n".join(
                f"{i}. {item}" if block.ordered else f"• {item}"
                for i, item in enumerate(block.items, 1)))
        elif block.text:
            lines.append(block.text)
    flush()
    return sections or [("Eredmény", content.plain_text())]


def render_html(content) -> str:
    """Szemantikus HTML-export; a felület maga nem használ beágyazott böngészőt."""
    parts = ["<!doctype html><html lang='hu'><head><meta charset='utf-8'>",
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'">',
             "</head><body>",
             f"<h1>{html.escape(content.title)}</h1>"]
    for block in content.blocks:
        value = html.escape(block.text)
        if block.kind == "heading":
            level = min(3, max(2, block.level))
            parts.append(f"<h{level}>{value}</h{level}>")
        elif block.kind == "list":
            tag = "ol" if block.ordered else "ul"
            parts.append(f"<{tag}>")
            parts.extend(f"<li>{html.escape(item)}</li>" for item in block.items)
            parts.append(f"</{tag}>")
        elif value:
            parts.append(f"<p>{value}</p>")
    return "".join(parts) + "</body></html>"


class SuperSurfFrame(wx.Frame):
    def __init__(self, parent, core):
        super().__init__(parent, title="SuperDL – Super Surf", size=(820, 620))
        self.core = core
        self.service = ResearchService()
        self._active_id = None
        self._closed = False
        self._last = None
        self._sections = []
        self._build()
        self.CreateStatusBar()
        self.Bind(wx.EVT_CLOSE, self._close)
        self.Bind(wx.EVT_CHAR_HOOK, self._key)
        self.CentreOnParent()
        wx.CallAfter(self.query.SetFocus)

    def _build(self):
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)
        fields = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)
        fields.AddGrowableCol(1)
        fields.Add(wx.StaticText(panel, label="&Forrás:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.mode = wx.Choice(panel, choices=[m[0] for m in MODES])
        self.mode.SetName("Forrás")
        self.mode.SetSelection(0)
        self.mode.Bind(wx.EVT_CHOICE, self._mode_changed)
        fields.Add(self.mode, 1, wx.EXPAND)
        fields.Add(wx.StaticText(panel, label="&Keresés vagy webcím:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.query = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.query.SetName("Keresés vagy webcím")
        self.query.SetHint(MODES[0][2])
        self.query.Bind(wx.EVT_TEXT_ENTER, self._start)
        fields.Add(self.query, 1, wx.EXPAND)
        root.Add(fields, 0, wx.EXPAND | wx.ALL, 8)

        root.Add(wx.StaticText(panel, label="&Fejezetek (fel/le nyíl; Enter: elolvasás):"),
                 0, wx.LEFT, 8)
        self.sections = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.sections.SetName("A találat fejezetei")
        self.sections.Bind(wx.EVT_LISTBOX, self._section_selected)
        self.sections.Bind(wx.EVT_LISTBOX_DCLICK, self._read_section)
        root.Add(self.sections, 1, wx.EXPAND | wx.ALL, 8)

        root.Add(wx.StaticText(panel, label="A kijelölt fejezet s&zövege:"), 0, wx.LEFT, 8)
        self.detail = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.detail.SetName("A kijelölt fejezet szövege")
        root.Add(self.detail, 2, wx.EXPAND | wx.ALL, 8)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (("&Lekérdezés (F5)", self._start),
                               ("&Megszakítás", self._cancel),
                               ("&Másolás", self._copy), ("M&entés…", self._save),
                               ("Forrás megnyitása (Ctrl+O)", self._source),
                               ("Sú&gó (F1)", self._help),
                               ("Be&zárás", lambda e: self.Close())):
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            actions.Add(button, 0, wx.RIGHT, 6)
            if label == "&Megszakítás":
                self.stop = button
        self.stop.Hide()
        root.Add(actions, 0, wx.ALL, 8)
        panel.SetSizer(root)
        self.panel = panel

    def _announce(self, message):
        self.SetStatusText(message)
        voice = getattr(self.core, "voice", None)
        if voice:
            voice.speak(message)

    def _mode_changed(self, _event):
        self.query.SetHint(MODES[self.mode.GetSelection()][2])

    def _set_busy(self, busy):
        self.stop.Show(busy)
        self.panel.Layout()

    def _start(self, _event):
        if self._active_id is not None:
            self._announce("A lekérdezés már folyamatban van.")
            return
        query = ResearchQuery(kind=MODES[self.mode.GetSelection()][1],
                              input=self.query.GetValue())
        self._active_id = query.request_id
        self._last = None
        self._sections = []
        self.sections.Clear()
        self.detail.ChangeValue("")
        self._set_busy(True)
        self._announce("Lekérdezés folyamatban…")

        def work():
            result = self.service.run(query,
                progress=lambda p: wx.CallAfter(self._progress, p),
                cancelled=lambda: self._closed or self._active_id != query.request_id)
            wx.CallAfter(self._finish, result)
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, progress):
        if not self._closed and progress.request_id == self._active_id:
            if progress.phase == "extracting":
                self._announce(progress.message_hu)

    def _finish(self, result):
        if self._closed or result.request_id != self._active_id:
            return
        self._active_id = None
        self._set_busy(False)
        if result.status != "success" or result.content is None:
            self._announce(result.error.message_hu if result.error else "Nincs eredmény.")
            self.query.SetFocus()
            return
        self._last = result
        self._sections = sections_from_content(result.content)
        self.sections.Set([label for label, _ in self._sections])
        self.sections.SetSelection(0)
        self._section_selected(None)
        warning = " " + " ".join(result.warnings) if result.warnings else ""
        self._announce(f"{result.title}. {len(self._sections)} fejezet. "
                       "Fel/le nyíl: fejezetek; Enter: olvasás." + warning)
        self.sections.SetFocus()

    def _section_selected(self, _event):
        index = self.sections.GetSelection()
        if 0 <= index < len(self._sections):
            self.detail.ChangeValue(self._sections[index][1])
            self.detail.SetInsertionPoint(0)

    def _read_section(self, _event):
        if self.sections.GetSelection() != wx.NOT_FOUND:
            self.detail.SetFocus()
            self.detail.SetInsertionPoint(0)

    def _cancel(self, _event):
        self._active_id = None
        self._set_busy(False)
        self._announce("Lekérdezés megszakítva.")
        self.query.SetFocus()

    def _copy(self, _event):
        if not self._last:
            self._announce("Előbb kérj le egy eredményt.")
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(self._last.content.plain_text()))
            finally:
                wx.TheClipboard.Close()
            self._announce("A teljes eredményt a vágólapra másoltam.")
        else:
            self._announce("A vágólap most nem érhető el.")

    def _save(self, _event):
        if not self._last:
            self._announce("Előbb kérj le egy eredményt.")
            return
        with wx.FileDialog(self, "Eredmény mentése", wildcard="Szövegfájl (*.txt)|*.txt",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                with open(dialog.GetPath(), "w", encoding="utf-8") as output:
                    output.write(self._last.content.plain_text())
                self._announce("Az eredményt elmentettem.")
            except OSError:
                self._announce("A fájl mentése nem sikerült.")

    def _source(self, _event):
        if not self._last or not self._last.source_url:
            self._announce("Nincs megnyitható forrás.")
            return
        webbrowser.open(self._last.source_url)

    def _help(self, _event):
        try:
            from superdl import helpdialog
            helpdialog.show_help(self, "Súgó – Super Surf", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Super Surf", wx.OK | wx.ICON_INFORMATION, self)

    def _key(self, event):
        key = event.GetKeyCode()
        focus = self.FindFocus()
        if key == wx.WXK_F1:
            self._help(None)
        elif key == wx.WXK_F5:
            self._start(None)
        elif event.ControlDown() and key in (ord("F"), ord("f")):
            self.query.SetFocus()
        elif event.ControlDown() and key in (ord("O"), ord("o")):
            self._source(None)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focus is self.sections:
            self._read_section(None)
        elif key == wx.WXK_ESCAPE and focus is self.detail:
            self.sections.SetFocus()
        elif key == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _close(self, event):
        self._closed = True
        self._active_id = None
        event.Skip()
