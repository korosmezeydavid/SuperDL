"""Dokumentum-konverter ablak: szöveg-, könyv- és KÉP-formátumok átalakítása,
kódolás-konverzió, és kép→szöveg OCR (több motorral). KÖTEGELT: több fájl vagy
egy egész mappa egyszerre, mindegyik a saját kimenetébe VAGY egyetlen fájlba
összefűzve. A gazdag formátumokhoz (RTF/ODT/MD/FB2, illetve MOBI/PDF) külső
eszközöket (Pandoc, Calibre, LibreOffice) használ – a Pandoc igény szerint
letölthető. Teljesen billentyűzetről kezelhető, felolvasott visszajelzéssel.
"""

import os
import threading
from pathlib import Path

import wx

from . import docconvert as DC          # a converter-logika a MODULBAN van
from superdl import extratools          # megosztott segédek a Core csomagjából
from superdl import ocr

HELP = """DOKUMENTUM-KONVERTER

MIRE VALÓ
Dokumentumok és képek átalakítása más formátumba (TXT, DOCX, EPUB, PDF, HTML,
RTF, ODT, Markdown, FB2…), régi kódlapok javítása, és képből szöveg kiolvasása
(OCR). Egy fájl vagy AKÁR SOK fájl / egy egész mappa egyszerre. Teljesen
billentyűzetről kezelhető.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. „Fájlok hozzáadása" gomb (Tab-bal ráállsz, Enter). Egyszerre több fájlt is
   kijelölhetsz. VAGY „Mappa hozzáadása" – a mappa összes támogatott fájlját
   berakja a listába.
2. A „Konvertálandó fájlok" lista mutatja, mi van kijelölve, és konvertáláskor
   fájlonként az állapotot (folyamatban / kész / hiba). A Delete billentyű a
   kijelölt sort kiveszi.
3. Tab-bal a „Kimeneti formátum" listára, nyilakkal válaszd, mibe alakítsa
   (pl. TXT, DOCX, EPUB, PDF).
4. „Kimeneti mód": „Külön fájlokba" – mindegyik a saját fájljába (egy mappát
   kell választanod); vagy „Egy fájlba összefűzve" – az összes szöveg EGYETLEN
   fájlba kerül, fájlonkénti címmel (egy mentési nevet kell megadnod).
5. TXT-nél a „Bemeneti kódolás" és „Kimeneti kódolás" listával állítható a
   kódlap. Régi magyar szövegnél hagyd a bemenetet „Automatikus felismerés"-en.
6. „Konvertálás" gomb – a végén a program bemondja, hova mentette, és hány fájl
   sikerült.
Képnél: OCR-rel olvassa ki a szöveget; az OCR-motort a listából választhatod.

GYORSBILLENTYŰK
F1 – ez a súgó.  Tab / Shift+Tab – mozgás a vezérlők közt.  Szóköz vagy Enter –
gomb.  Fel/le nyíl – választás a listákban.  Delete – kijelölt fájl kivétele.

TIPPEK
- Ha egy régi magyar szöveg „kacatosan" jön át, a bemeneti kódolásnál válaszd
  kézzel a „Magyar DOS (CP852)" vagy a „Magyar CWI-2" beállítást.
- Az összefűzés jó pl. sok kis szövegfájl EGY dokumentummá fésüléséhez.
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

# kimeneti mód: külön fájlokba / egyetlen fájlba összefűzve
CONVERT_MODES = [
    ("Külön fájlokba (mindegyik a saját fájljába)", "separate"),
    ("Egy fájlba összefűzve", "merge"),
]


def _unique(path: str) -> str:
    """Ütközésmentes kimeneti út: ha létezik, sorszámot fűz a névhez."""
    p = Path(path)
    if not p.exists():
        return str(p)
    i = 2
    while True:
        cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not cand.exists():
            return str(cand)
        i += 1


class DocConvertFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Dokumentum-konverter",
                         size=(860, 640))
        self.main = main
        self.files: list[str] = []         # a konvertálandó fájlok (teljes út)
        self._busy = False
        self._closing = False              # zárás alatt a háttér-callbackek kilépnek
        self._ocr_keys = list(ocr.ENGINES.keys())
        self._build()
        self.CreateStatusBar()
        self._announce("Adj hozzá fájlokat vagy egy mappát, válaszd a kimeneti "
                       "formátumot és módot, és konvertálom. Több fájlt "
                       "egyszerre is, akár egy fájlba összefűzve. Súgó: F1.")
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

        # ---- fájllista-műveletek ----
        fb = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
                ("&Fájlok hozzáadása…", self._add_files),
                ("&Mappa hozzáadása…", self._add_folder),
                ("Kijelölt e&ltávolítása", self._remove_selected),
                ("Lista ü&rítése", self._clear)):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, lambda e, h=handler: h())
            fb.Add(b, 0, wx.RIGHT, 6)
        v.Add(fb, 0, wx.ALL, 8)

        # ---- a konvertálandó fájlok listája (fájlonkénti állapottal) ----
        self.list = wx.ListCtrl(
            p, style=wx.LC_REPORT, name="Konvertálandó fájlok")
        self.list.InsertColumn(0, "Fájl", width=430)
        self.list.InsertColumn(1, "Állapot", width=180)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        v.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.count_lbl = wx.StaticText(p, label="0 fájl a listában.")
        self.count_lbl.SetName("Fájlok száma a listában")
        v.Add(self.count_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        # ---- beállítások ----
        g = wx.FlexGridSizer(0, 2, 8, 8)
        g.AddGrowableCol(1)
        g.Add(wx.StaticText(p, label="Kimeneti &formátum:"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.fmt_ch = wx.Choice(p, choices=[n for n, _e, _t in DC.OUT_FORMATS],
                                name="Kimeneti formátum")
        self.fmt_ch.SetSelection(0)
        self.fmt_ch.Bind(wx.EVT_CHOICE, lambda e: self._sync())
        g.Add(self.fmt_ch, 0, wx.EXPAND)

        g.Add(wx.StaticText(p, label="Kimeneti &mód:"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.mode_ch = wx.Choice(p, choices=[n for n, _ in CONVERT_MODES],
                                 name="Kimeneti mód")
        self.mode_ch.SetSelection(0)
        g.Add(self.mode_ch, 0, wx.EXPAND)

        g.Add(wx.StaticText(p, label="Kimeneti &kódolás (TXT-nél):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.enc_ch = wx.Choice(p, choices=[n for n, _ in DC.OUT_ENCODINGS],
                                name="Kimeneti kódolás")
        self.enc_ch.SetSelection(0)      # UTF-8 (az OUT_ENCODINGS első eleme)
        g.Add(self.enc_ch, 0, wx.EXPAND)

        g.Add(wx.StaticText(p, label="Bemeneti kó&dolás (TXT-nél):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        # a bemeneti lista: „Automatikus felismerés" + a KONKRÉT kódlapok (a cwi2
        # is, ami DEKÓDOLHATÓ). Az ENCODINGS[0] maga az auto, ezért azt kihagyjuk.
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

        cb = wx.BoxSizer(wx.HORIZONTAL)
        self.conv_btn = wx.Button(p, label="&Konvertálás")
        self.conv_btn.Bind(wx.EVT_BUTTON, lambda e: self._convert())
        cb.Add(self.conv_btn, 0, wx.RIGHT, 6)
        # LEÁLLÍTÁS: a külső eszközök (Pandoc/Calibre/LibreOffice) sokáig
        # blokkolhatnak, a köteg pedig órákig futhat. [Herman Tibi DOC-P0-03]
        self.stop_btn = wx.Button(p, label="Konvertálás &leállítása")
        self.stop_btn.SetName("A konvertálás leállítása")
        self.stop_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_stop_convert())
        self.stop_btn.Enable(False)
        cb.Add(self.stop_btn, 0)
        v.Add(cb, 0, wx.LEFT | wx.BOTTOM, 8)

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
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
            size=(-1, 96))
        self.report.SetName("Eredmény")
        v.Add(self.report, 0, wx.EXPAND | wx.ALL, 8)

        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        p.SetSizer(v)
        self._sync()
        self._refresh_tools()

    # ---- segédek ------------------------------------------------------

    def _announce(self, text):
        if self._closing:
            return
        self.SetStatusText(text)

    def _say(self, text):
        sv = getattr(self.main, "selfvoice", None)
        # 1) A BEJELENTŐ a KÉPERNYŐOLVASÓ – ELŐSZÖR mindig ŐT kérjük.
        #    FONTOS: képernyőolvasó-módban a Core a saját hangot NÉMÍTJA
        #    (muted=True) ÉPP AZÉRT, hogy az olvasó beszéljen – ezért a
        #    némítás-ellenőrzés CSAK a beépített hangra vonatkozhat, ide nem.
        try:
            from superdl import screenreader
            if screenreader.speak(text):
                return
        except Exception:
            pass
        # 2) Nincs képernyőolvasó → a beépített hang segít ki, DE a Teljes
        #    némítás ilyenkor is némít
        if sv is not None and getattr(sv, "muted", False):
            return
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _result(self, text):
        if self._closing:
            return
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

    def _mode(self) -> str:
        return CONVERT_MODES[self.mode_ch.GetSelection()][1]

    def _out_encoding(self) -> str:
        return DC.OUT_ENCODINGS[self.enc_ch.GetSelection()][1]

    def _in_encoding(self):
        i = self.in_enc_ch.GetSelection()
        return None if i <= 0 else DC.ENCODINGS[i][1]   # i=1 → ENCODINGS[1]=utf-8

    def _ocr_engine(self) -> str:
        i = self.ocr_ch.GetSelection()
        return self._ocr_keys[i] if 0 <= i < len(self._ocr_keys) else "ai"

    # ---- fájllista kezelése -------------------------------------------

    def _add_files(self):
        dlg = wx.FileDialog(self, "Dokumentumok vagy képek hozzáadása",
                            wildcard=WILDCARD,
                            style=wx.FD_OPEN | wx.FD_MULTIPLE
                            | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self._add_paths(dlg.GetPaths())
        dlg.Destroy()

    def _add_folder(self):
        dlg = wx.DirDialog(self, "Mappa hozzáadása (a támogatott fájljai)",
                           style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            folder = dlg.GetPath()
            try:
                found = [str(f) for f in sorted(Path(folder).iterdir())
                         if f.is_file() and f.suffix.lower() in DC.IN_EXTS]
            except OSError as e:
                found = []
                self._announce(f"A mappa nem olvasható: {e}")
            if found:
                self._add_paths(found)
            else:
                self._announce("Ebben a mappában nincs támogatott fájl.")
        dlg.Destroy()

    def _add_paths(self, paths):
        have = set(self.files)
        added = 0
        for pth in paths:
            if pth not in have:
                self.files.append(pth)
                have.add(pth)
                added += 1
        self._refresh_list()
        self._announce(f"{added} fájl hozzáadva. Összesen "
                       f"{len(self.files)} a listában.")

    def _remove_selected(self):
        idxs = []
        i = self.list.GetFirstSelected()
        while i != -1:
            idxs.append(i)
            i = self.list.GetNextSelected(i)
        for i in sorted(idxs, reverse=True):
            if 0 <= i < len(self.files):
                self.files.pop(i)
        self._refresh_list()
        self._announce(f"{len(idxs)} fájl eltávolítva. Maradt "
                       f"{len(self.files)}.")

    def _clear(self):
        self.files.clear()
        self._refresh_list()
        self._announce("A lista kiürítve.")

    def _refresh_list(self):
        self.list.DeleteAllItems()
        for i, pth in enumerate(self.files):
            self.list.InsertItem(i, os.path.basename(pth))
            self.list.SetItem(i, 1, "várakozik")
        self.count_lbl.SetLabel(f"{len(self.files)} fájl a listában.")

    def _set_status(self, i: int, status: str):
        if 0 <= i < self.list.GetItemCount():
            self.list.SetItem(i, 1, status)

    def _on_list_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._remove_selected()
        else:
            e.Skip()

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
        # A KONKRÉT okot mondjuk meg, ne csak azt, hogy „internet?" – a
        # 403/rate limit/sérült ZIP/jogosultság/ujjlenyomat-hiba mind más
        # teendőt jelent. [Herman Tibi OCR-P1-12]
        hiba = getattr(extratools, "last_tool_error", "") or ""
        figy = getattr(extratools, "last_tool_warning", "") or ""
        if path:
            self._result("A Pandoc letöltve és kész."
                         + (f" FIGYELEM: {figy}" if figy else ""))
        else:
            self._result(hiba or "A Pandoc letöltése nem sikerült (internet?).")

    # ---- konvertálás --------------------------------------------------

    def _cancelled(self) -> bool:
        ev = getattr(self, "_cancel", None)
        return bool(ev is not None and ev.is_set())

    def _on_stop_convert(self):
        """A konvertálás leállítása a következő fájl előtt."""
        ev = getattr(self, "_cancel", None)
        if ev is not None and not ev.is_set():
            ev.set()
            if hasattr(self, "stop_btn"):
                self.stop_btn.Enable(False)
            self._announce("Leállítás kérve – a most futó fájl után "
                           "befejezem.")

    def _convert(self):
        if not self.files:
            self._result("Előbb adj hozzá legalább egy fájlt (vagy egy mappát).")
            return
        if self._busy:
            return
        out_fmt = self._out_format()
        mode = self._mode()
        in_enc, out_enc = self._in_encoding(), self._out_encoding()
        engine = self._ocr_engine()

        if mode == "merge":
            suggested = "osszefuzott." + out_fmt
            dlg = wx.FileDialog(
                self, "Az összefűzött fájl mentése", defaultFile=suggested,
                wildcard=f"{out_fmt.upper()}|*.{out_fmt}|Minden fájl|*.*",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            dst = dlg.GetPath()
            dlg.Destroy()
            target, extra = dst, None
        else:
            dlg = wx.DirDialog(self, "Cél-mappa a konvertált fájloknak",
                               style=wx.DD_DEFAULT_STYLE)
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            target, extra = dlg.GetPath(), None
            dlg.Destroy()

        files = list(self.files)
        self._busy = True
        self._cancel = threading.Event()   # megszakítás-jelző [DOC-P0-03]
        self.conv_btn.Enable(False)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.Enable(True)
        self.gauge.SetValue(0)
        self._announce("Konvertálás…")
        for i in range(len(files)):
            wx.CallAfter(self._set_status, i, "várakozik")

        def work():
            if mode == "merge":
                self._run_merge(files, target, out_fmt, in_enc, out_enc, engine)
            else:
                self._run_separate(files, target, out_fmt, in_enc, out_enc,
                                   engine)

        threading.Thread(target=work, daemon=True).start()

    def _run_separate(self, files, out_dir, out_fmt, in_enc, out_enc, engine):
        ok = 0
        errors = []
        total = len(files)
        megszakitva = False
        for i, src in enumerate(files):
            # MEGSZAKÍTÁS: a külső eszközök (Pandoc/Calibre/LibreOffice) akár
            # 10-15 percig blokkolhatnak, ezért fájlonként ellenőrzünk, hogy a
            # felhasználó ne várjon a teljes köteg végéig. [DOC-P0-03]
            if self._cancelled():
                megszakitva = True
                break
            wx.CallAfter(self._set_status, i, "folyamatban")
            try:
                base = os.path.splitext(os.path.basename(src))[0]
                dst = _unique(os.path.join(out_dir, base + "." + out_fmt))
                DC.convert(src, dst, out_fmt, in_enc, out_enc,
                           ocr_engine=engine)
                ok += 1
                wx.CallAfter(self._set_status, i, "kész")
            except Exception as e:
                errors.append((os.path.basename(src), str(e)))
                wx.CallAfter(self._set_status, i, "hiba")
            wx.CallAfter(self.gauge.SetValue, int((i + 1) / total * 100))
        if megszakitva:
            msg = (f"LEÁLLÍTVA. Eddig {ok}/{total} fájl készült el ide: "
                   f"{out_dir} ({out_fmt.upper()}). A többihez nem nyúltam.")
        else:
            msg = (f"Kész: {ok}/{total} fájl konvertálva ide: {out_dir}"
                   f" ({out_fmt.upper()}).")
        if errors:
            msg += "\n\nHibás fájlok:\n" + "\n".join(
                f"• {n}: {err.splitlines()[0]}" for n, err in errors[:8])
            if len(errors) > 8:
                msg += f"\n… és további {len(errors) - 8}."
        wx.CallAfter(self._done, msg)

    def _run_merge(self, files, dst, out_fmt, in_enc, out_enc, engine):
        def on_file(i, name, status, err):
            wx.CallAfter(self._set_status, i, status)

        def prog(done, total):
            if total:
                wx.CallAfter(self.gauge.SetValue, int(done / total * 100))

        try:
            ok, errors = DC.merge_documents(
                files, dst, out_fmt, in_enc, out_enc, ocr_engine=engine,
                on_file=on_file, progress=prog)
            msg = (f"Összefűzve: {ok}/{len(files)} fájl szövege ide: "
                   f"{os.path.basename(dst)} ({out_fmt.upper()}).")
            if errors:
                msg += "\n\nKihagyott fájlok:\n" + "\n".join(
                    f"• {n}: {err.splitlines()[0]}" for n, err in errors[:8])
                if len(errors) > 8:
                    msg += f"\n… és további {len(errors) - 8}."
        except Exception as e:
            msg = f"Az összefűzés nem sikerült: {e}"
        wx.CallAfter(self._done, msg)

    def _done(self, msg):
        if self._closing:
            return
        self._busy = False
        self.conv_btn.Enable(True)
        if hasattr(self, "stop_btn"):
            self.stop_btn.Enable(False)
        self.gauge.SetValue(0)
        self._refresh_tools()
        self._result(msg)

    def _on_close(self, e):
        # MEGERŐSÍTÉS folyó konvertálásnál: eddig a bezárás után a worker és a
        # külső programok tovább futottak. [Herman Tibi DOC-P0-03]
        if self._busy and not self._closing:
            ans = wx.MessageBox(
                "A konvertálás FOLYAMATBAN van. Ha most bezárod, a program "
                "a most futó fájl után leáll.\n\nBiztosan bezárod?",
                "Dokumentum-konverter – folyamatban",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
            if ans != wx.YES:
                if e.CanVeto():
                    e.Veto()
                return
            ev = getattr(self, "_cancel", None)
            if ev is not None:
                ev.set()
        self._closing = True
        if getattr(self.main, "_docconvert_win", None) is self:
            self.main._docconvert_win = None
        self.Destroy()
