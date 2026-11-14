import threading
import webbrowser
from datetime import datetime
import wx
from . import core as C

class LinkFrame(wx.Frame):
    def __init__(self, parent=None):
        super().__init__(parent, title='Super Link – linkrövidítő és QR-kód készítő', size=(750, 700))
        self.busy = False
        try: self.items = C.load()
        except Exception as exc:
            self.items = None
            wx.MessageBox('A mentett lista nem olvasható. Nem írjuk felül. ' + str(exc), 'Hiba', wx.OK | wx.ICON_ERROR, self)
        panel = wx.Panel(self)
        box = wx.BoxSizer(wx.VERTICAL)
        def field(label, name):
            box.Add(wx.StaticText(panel, label=label), 0, wx.ALL, 5)
            ctrl = wx.TextCtrl(panel); ctrl.SetName(name)
            box.Add(ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
            return ctrl
        self.url = field('&Hosszú link:', 'Hosszú link')
        self.alias = field('Egyedi link&vég (elhagyható):', 'Egyedi linkvég')
        self.stats = wx.CheckBox(panel, label='&Kattintási statisztika bekapcsolása')
        self.stats.SetValue(True); box.Add(self.stats, 0, wx.ALL, 5)
        self.create = wx.Button(panel, label='&Rövid link létrehozása')
        self.create.Bind(wx.EVT_BUTTON, self.on_create); box.Add(self.create, 0, wx.ALL, 5)
        box.Add(wx.StaticText(panel, label='&Mentett linkek:'), 0, wx.ALL, 5)
        self.list = wx.ListBox(panel); self.list.SetName('Mentett rövid linkek listája')
        self.list.Bind(wx.EVT_LISTBOX, self.on_select)
        box.Add(self.list, 1, wx.EXPAND | wx.ALL, 5)
        self.info = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.info.SetName('Kijelölt link adatai'); box.Add(self.info, 1, wx.EXPAND | wx.ALL, 5)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in [('Link &másolása', self.on_copy), ('Statisztika meg&nyitása', self.on_stats), ('Eltávolítás a &listából', self.on_remove)]:
            b = wx.Button(panel, label=label); b.Bind(wx.EVT_BUTTON, fn); row.Add(b, 0, wx.ALL, 4)
        box.Add(row)
        self.qrurl = field('&QR-kód tartalma – webcím:', 'QR-kódhoz használt webcím')
        self.caption = field('&Felirat a QR-kód alatt (elhagyható):', 'QR-kód alatti felirat')
        qr = wx.Button(panel, label='QR-kód &mentése PNG-ként…')
        qr.Bind(wx.EVT_BUTTON, self.on_qr); box.Add(qr, 0, wx.ALL, 5)
        self.status = wx.StaticText(panel, label='Kész.'); self.status.SetName('Művelet állapota')
        box.Add(self.status, 0, wx.ALL, 5)
        close = wx.Button(panel, wx.ID_CLOSE, '&Bezárás'); close.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        box.Add(close, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        panel.SetSizer(box); self.refresh(); self.url.SetFocus()

    def refresh(self):
        self.list.Set([f"{x.get('short','')} – {x.get('caption') or x.get('url','')}" for x in (self.items or [])])
        self.info.SetValue('')
        if self.items: self.list.SetSelection(0); self.on_select(None)

    def selected(self):
        i = self.list.GetSelection()
        return self.items[i] if self.items is not None and 0 <= i < len(self.items) else None

    def on_select(self, event):
        item = self.selected()
        if item:
            self.info.SetValue(f"Rövid link: {item['short']}\nEredeti link: {item['url']}\nFelirat: {item.get('caption','')}\nStatisztika: {'bekapcsolva' if item.get('statistics') else 'kikapcsolva'}")
            self.qrurl.SetValue(item['short'])
            self.caption.SetValue(item.get('caption', ''))

    def on_create(self, event):
        if self.busy or self.items is None: return
        url, alias, stats, caption = self.url.GetValue(), self.alias.GetValue(), self.stats.GetValue(), self.caption.GetValue()
        try:
            C.normalize_url(url)
            if alias.strip() and not __import__('re').fullmatch(r'[A-Za-z0-9_]{5,30}', alias.strip()): raise ValueError('A link vége 5–30 ékezet nélküli betű, szám vagy aláhúzás lehet.')
        except ValueError as exc:
            wx.MessageBox(str(exc), 'Hibás adat', wx.OK | wx.ICON_WARNING, self); return
        self.busy = True; self.create.Disable(); self.status.SetLabel('Rövid link létrehozása folyamatban…')
        def work():
            try: item, error = C.shorten(url, alias, stats), None
            except Exception as exc: item, error = None, str(exc)
            wx.CallAfter(self.created, item, error, caption)
        threading.Thread(target=work, daemon=True).start()

    def created(self, item, error, caption):
        if not self: return
        self.busy = False; self.create.Enable()
        if error:
            self.status.SetLabel('A link létrehozása nem igazolt.'); wx.MessageBox(error, 'Linkrövidítés', wx.OK | wx.ICON_WARNING, self); return
        item['caption'] = caption; item['created'] = datetime.now().isoformat(timespec='seconds')
        self.items.insert(0, item)
        try: C.save(self.items)
        except Exception as exc:
            self.refresh(); self.status.SetLabel('A link létrejött, de a helyi mentés nem sikerült.')
            wx.MessageBox(f"A link létrejött: {item['short']}\nMásold ki most! A mentés sikertelen: {exc}", 'Mentési hiba', wx.OK | wx.ICON_ERROR, self); return
        self.refresh(); self.status.SetLabel('A rövid link elkészült és elmentettem.')
        wx.MessageBox('Elkészült: ' + item['short'], 'Linkrövidítés', wx.OK | wx.ICON_INFORMATION, self)

    def on_copy(self, event):
        item = self.selected()
        if item and wx.TheClipboard.Open():
            try: wx.TheClipboard.SetData(wx.TextDataObject(item['short']))
            finally: wx.TheClipboard.Close()
            self.status.SetLabel('A rövid linket a vágólapra másoltam.')

    def on_stats(self, event):
        item = self.selected()
        if not item: return
        if not item.get('statistics'):
            wx.MessageBox('Ehhez a linkhez nem volt bekapcsolva a statisztika.', 'Statisztika', wx.OK, self); return
        webbrowser.open(item['short'] + '-')
        self.status.SetLabel('Megnyitottam a link előnézetét; ott válaszd a statisztikát.')

    def on_remove(self, event):
        item = self.selected()
        if not item: return
        if wx.MessageBox('Eltávolítod a helyi listából? Az is.gd címe továbbra is működni fog.', 'Link eltávolítása', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES: return
        updated = list(self.items); updated.pop(self.list.GetSelection())
        try: C.save(updated)
        except Exception as exc: wx.MessageBox(str(exc), 'Mentési hiba', wx.OK | wx.ICON_ERROR, self); return
        self.items = updated; self.refresh(); self.status.SetLabel('Eltávolítva a helyi listából.')

    def on_qr(self, event):
        try: C.normalize_url(self.qrurl.GetValue())
        except ValueError as exc: wx.MessageBox(str(exc), 'Hibás cím', wx.OK | wx.ICON_WARNING, self); return
        dialog = wx.FileDialog(self, 'QR-kód mentése', wildcard='PNG kép (*.png)|*.png', style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            path = dialog.GetPath()
            if not path.lower().endswith('.png'): path += '.png'
            C.make_qr(self.qrurl.GetValue(), self.caption.GetValue(), path)
            self.status.SetLabel('A QR-kód elkészült: ' + path)
            wx.MessageBox('QR-kód elmentve: ' + path, 'QR-kód', wx.OK | wx.ICON_INFORMATION, self)
        except Exception as exc: wx.MessageBox('A QR-kód mentése nem sikerült: ' + str(exc), 'Hiba', wx.OK | wx.ICON_ERROR, self)
        finally: dialog.Destroy()

