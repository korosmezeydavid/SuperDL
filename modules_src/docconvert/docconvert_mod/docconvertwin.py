"""Dokumentum-konverter ablak: szöveg-, könyv- és KÉP-formátumok átalakítása,
kódolás-konverzió, és kép→szöveg OCR (több motorral). A gazdag formátumokhoz
(RTF/ODT/MD/FB2, illetve MOBI/PDF) külső eszközöket (Pandoc, Calibre,
LibreOffice) használ – a Pandoc igény szerint letölthető. Teljesen
billentyűzetről kezelhető, felolvasott visszajelzéssel.
"""

import os
import threading

import wx

from . import docconvert as DC          # a converter-logika a MODULBAN van
from superdl import extratools          # megosztott segédek a Core csomagjából
from superdl import ocr

HELP = """DOKUMENTUM-KONVERTER

MIRE VALÓ
Dokumentumok és képek átalakítása más formátumba (TXT, DOCX, EPUB, PDF, HTML,
RTF, ODT, Markdown, FB2…), régi kódlapok javítása, és képből szöveg kiolvasása
(OCR). Teljesen billentyűzetről kezelhető.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. „Fájl betöltése" gomb (Tab-bal ráállsz, Enter). Válaszd ki a dokumentumot
   vagy képet – a program bemondja, mit töltött be.
2. Tab-bal a „Kimeneti formátum" listára, nyilakkal válaszd, mibe alakítsa
   (pl. TXT, DOCX, EPUB, PDF).
3. TXT-nél a „Bemeneti kódolás" és „Kimeneti kódolás" listával állítható a
   kódlap. Régi magyar szövegnél hagyd a bemenetet „Automatikus felismerés"-en
   (a CP852-t és a CWI-2-t is felismeri).
4. „Konvertálás" gomb – a végén a program bemondja, hova mentette.
Képnél: OCR-rel kiolvassa a szöveget; az OCR-motort a listából választhatod.

GYORSBILLENTYŰK
F1 – ez a súgó.  Tab / Shift+Tab – mozgás a vezérlők közt.  Szóköz vagy Enter –
gomb megnyomása.  Fel/le nyíl – választás a listákban.

TIPPEK
- Ha egy régi magyar szöveg „kacatosan" jön át, a bemeneti kódolásnál válaszd
  kézzel a „Magyar DOS (CP852)" vagy a „Magyar CWI-2" beállítást.
- A gazdag formátumokhoz (RTF/ODT/MD, MOBI) a program szükség szerint letölti a
  Pandoc/Calibre segédet – ezt egyszer engedélyezned kell."""

WILDCARD = (
    "Minden támogatott|*.txt;*.docx;*.epub;*.pdf;*.html;*.htm;*.rtf;*.odt;"
    "*.md;*.markdown;*.fb2;*.doc;*.mobi;*.azw3;"
    "*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp|"
    "Dokumentum|*.txt;*.docx;*.epub;*.pdf;*.html;*.htm;*.rtf;*.odt;*.md;*.fb2;"
    "*.doc;*.mobi;*.azw3|"
    "Kép (OCR-hez)|*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp|"
    "Minden fájl|*.*")


class DocConvertFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Dokumentum-konverter",
                         size=(820, 600))
        self.main = main
        self.src = ""
        self._busy = False
        self._ocr_keys = list(ocr.ENGINES.keys())
        self._build()
        self.CreateStatusBar()
        self._announce("Tölts be egy dokumentumot vagy képet, válaszd ki a "
                       "kimeneti formátumot, és konvertálom. Képnél OCR-rel "
                       "olvasom ki a szöveget. Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_help_key)

    def _on_help_key(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            self._help()
        else:
            e.Skip()

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Dokumentum-konverter", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Dokumentum-konverter",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Fájl &betöltése…")
        b.Bind(wx.EVT_BUTTON, lambda e: self._load())
        self.src_lbl = wx.StaticText(p, label="Nincs betöltött fájl.")
        self.src_lbl.SetName("Betöltött fájl")
        top.Add(b, 0, wx.RIGHT, 8)
        top.Add(self.src_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        g = wx.FlexGridSizer(0, 2, 8, 8)
        g.AddGrowableCol(1)
        g.Add(wx.StaticText(p, label="Kimeneti &formátum:"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.fmt_ch = wx.Choice(p, choices=[n for n, _e, _t in DC.OUT_FORMATS],
                                name="Kimeneti formátum")
        self.fmt_ch.SetSelection(0)
        self.fmt_ch.Bind(wx.EVT_CHOICE, lambda e: self._sync())
        g.Add(self.fmt_ch, 0, wx.EXPAND)

        g.Add(wx.StaticText(p, label="Kimeneti &kódolás (TXT-nél):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.enc_ch = wx.Choice(p, choices=[n for n, _ in DC.OUT_ENCODINGS],
                                name="Kimeneti kódolás")
        self.enc_ch.SetSelection(0)      # UTF-8 (az OUT_ENCODINGS első eleme)
        g.Add(self.enc_ch, 0, wx.EXPAND)

        g.Add(wx.StaticText(p, label="Bemeneti kó&dolás (TXT-nél):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        # a bemeneti lista: „Automatikus felismerés" + a KONKRÉT kódlapok (a cwi2
        # is, ami DEKÓDOLHATÓ). Az ENCODINGS[0] maga az auto, ezért azt kihagyjuk,
        # nehogy kétszer szerepeljen.
        self.in_enc_ch = wx.Choice(
            p, choices=["Automatikus felismerés"]
            + [n for n, _ in DC.ENCODINGS[1:]],
            name="Bemeneti kódolás")
        self.in_enc_ch.SetSelection(0)
        g.Add(self.in_enc_ch, 0, wx.EXPAND)

        g.Add(wx.StaticText(p, label="O&CR-motor (képeknél):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.ocr_ch = wx.Choice(p, choices=[ocr.ENGINES[k]
                                            for k in self._ocr_keys],
                                name="OCR-motor")
        self.ocr_ch.SetSelection(0)
        g.Add(self.ocr_ch, 0, wx.EXPAND)
        v.Add(g, 0, wx.EXPAND | wx.ALL, 8)

        self.conv_btn = wx.Button(p, label="&Konvertálás új fájlba…")
        self.conv_btn.Bind(wx.EVT_BUTTON, lambda e: self._convert())
        v.Add(self.conv_btn, 0, wx.LEFT | wx.BOTTOM, 8)

        # külső eszközök státusza + Pandoc-letöltés
        tb = wx.BoxSizer(wx.HORIZONTAL)
        self.tools_lbl = wx.StaticText(p, label="")
        self.tools_lbl.SetName("Külső eszközök állapota")
        tb.Add(self.tools_lbl, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.pandoc_btn = wx.Button(p, label="&Pandoc letöltése (RTF/ODT/MD…)")
        self.pandoc_btn.Bind(wx.EVT_BUTTON, lambda e: self._get_pandoc())
        tb.Add(self.pandoc_btn, 0)
        v.Add(tb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="&Eredmény:"), 0, wx.LEFT, 8)
        self.report = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.report.SetName("Eredmény")
        v.Add(self.report, 1, wx.EXPAND | wx.ALL, 8)

        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        p.SetSizer(v)
        self._sync()
        self._refresh_tools()

    # ---- segédek ------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)

    def _say(self, text):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _result(self, text):
        self.report.SetValue(text)
        self._announce(text.splitlines()[0] if text else "")
        self._say(text)

    def _refresh_tools(self):
        def st(name, ok, hint):
            return f"{name}: {'kész' if ok else 'nincs (' + hint + ')'}"
        self.tools_lbl.SetLabel(" · ".join([
            st("Pandoc", extratools.find_pandoc(), "RTF/ODT/MD-hez"),
            st("Calibre", extratools.find_calibre(), "MOBI/AZW3-hoz"),
            st("LibreOffice", extratools.find_libreoffice(), "DOC/PDF-hez"),
            st("Tesseract", extratools.find_tesseract(), "offline OCR"),
        ]))
        self.pandoc_btn.Enable(not extratools.find_pandoc())

    def _sync(self):
        is_txt = self._out_format() == "txt"
        self.enc_ch.Enable(is_txt)

    def _out_format(self) -> str:
        return DC.OUT_FORMATS[self.fmt_ch.GetSelection()][1]

    def _out_encoding(self) -> str:
        return DC.OUT_ENCODINGS[self.enc_ch.GetSelection()][1]

    def _in_encoding(self):
        i = self.in_enc_ch.GetSelection()
        return None if i <= 0 else DC.ENCODINGS[i][1]   # i=1 → ENCODINGS[1]=utf-8

    def _ocr_engine(self) -> str:
        i = self.ocr_ch.GetSelection()
        return self._ocr_keys[i] if 0 <= i < len(self._ocr_keys) else "ai"

    # ---- Pandoc letöltés ----------------------------------------------

    def _get_pandoc(self):
        if self._busy:
            return
        self._busy = True
        self.pandoc_btn.Enable(False)
        self._announce("Pandoc letöltése… (kb. 40 MB, egyszeri)")

        def prog(done, total):
            if total:
                wx.CallAfter(self.gauge.SetValue, int(done / total * 100))

        def work():
            path = extratools.ensure_pandoc(prog)
            wx.CallAfter(self._pandoc_done, path)

        threading.Thread(target=work, daemon=True).start()

    def _pandoc_done(self, path):
        self._busy = False
        self.gauge.SetValue(0)
        self._refresh_tools()
        self._result("A Pandoc letöltve és kész." if path else
                     "A Pandoc letöltése nem sikerült (internet?).")

    # ---- fájl + konvertálás -------------------------------------------

    def _load(self):
        dlg = wx.FileDialog(self, "Dokumentum vagy kép betöltése",
                            wildcard=WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.src = dlg.GetPath()
            self.src_lbl.SetLabel(os.path.basename(self.src))
            img = os.path.splitext(self.src)[1].lower() in ocr.IMAGE_EXTS
            self._announce(f"Betöltve: {os.path.basename(self.src)}."
                           + (" Kép – OCR-rel olvasom majd." if img else ""))
        dlg.Destroy()

    def _convert(self):
        if not self.src:
            self._result("Előbb tölts be egy dokumentumot vagy képet.")
            return
        if self._busy:
            return
        out_fmt = self._out_format()
        root = os.path.splitext(self.src)[0]
        suggested = os.path.basename(root) + "." + out_fmt
        dlg = wx.FileDialog(self, "A konvertált fájl mentése",
                            defaultDir=os.path.dirname(self.src),
                            defaultFile=suggested,
                            wildcard=f"{out_fmt.upper()}|*.{out_fmt}|"
                                     "Minden fájl|*.*",
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        dst = dlg.GetPath()
        dlg.Destroy()
        self._busy = True
        self.conv_btn.Enable(False)
        self.gauge.Pulse()
        self._announce("Konvertálás…")
        src = self.src
        in_enc, out_enc = self._in_encoding(), self._out_encoding()
        engine = self._ocr_engine()

        def prog(done, total):
            if total:
                wx.CallAfter(self.gauge.SetValue, int(done / total * 100))

        def work():
            try:
                msg = DC.convert(src, dst, out_fmt, in_enc, out_enc,
                                 ocr_engine=engine, progress=prog)
            except Exception as e:
                msg = f"Hiba a konvertáláskor: {e}"
            wx.CallAfter(self._done, msg)

        threading.Thread(target=work, daemon=True).start()

    def _done(self, msg):
        self._busy = False
        self.conv_btn.Enable(True)
        self.gauge.SetValue(0)
        self._refresh_tools()
        self._result(msg)

    def _on_close(self, e):
        if getattr(self.main, "_docconvert_win", None) is self:
            self.main._docconvert_win = None
        self.Destroy()
