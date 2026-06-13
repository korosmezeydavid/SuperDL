"""Médiakereső ablak: kulcsszavas keresés több legális forráson, a
találatok egybefűzött listája, virtuális kosár, és egy beépített
médialejátszó a kért, billentyűzetes vezérléssel.

Akadálymentes: minden listában fel/le nyíllal mozogsz, az elemekre a
szabványos helyi menü (jobb klikk, Menü-billentyű, Shift+F10) ad
műveleteket, és vannak közvetlen gyorsbillentyűk is.
"""

import glob
import os
import threading
from pathlib import Path

import wx
import wx.media

from . import search as S
from . import store

SEEK_INTERVALS = [5, 10, 15, 20, 25, 30, 40, 50, 60]
PAGE = 25
PLAY_DIR = Path.home() / ".superdl" / "play"   # ideiglenes lejátszó-fájlok


def _fmt_time(ms: int) -> str:
    return S.human_duration(int(ms) // 1000) or "0:00"


class MediaSearchFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Médiakereső",
                         size=(960, 700))
        self.main = main                 # a fő ablak (letöltés, beállítások)
        self.results: list[S.Result] = []
        self.cart: list[S.Result] = [self._from_rec(r)
                                     for r in store.load_cart()]
        self.query = ""
        self.count = PAGE
        self._interval_idx = 2           # 15 mp
        self._audio_only_play = True
        self._cur = None                 # épp játszott találat

        self._build()
        self._refresh_cart()
        self.CreateStatusBar()
        self.SetStatusText("Írd be a keresőszót, és nyomj Entert. "
                           "Lejátszás: Enter a találaton. Súgó: F1.")
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
        btn_search = wx.Button(p, label="Ke&resés")
        btn_search.Bind(wx.EVT_BUTTON, lambda e: self._on_search())
        row.Add(self.search_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(btn_search, 0)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # találatok
        v.Add(wx.StaticText(p, label="&Találatok (Enter: lejátszás, "
              "Ctrl+B: kosárba, Ctrl+D: letöltés, Ctrl+C: URL):"),
              0, wx.LEFT, 8)
        self.res_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.res_list.SetName("Találatok listája")
        for i, (t, w) in enumerate((("Cím", 540), ("Hossz", 90),
                                    ("Feltöltő", 240))):
            self.res_list.InsertColumn(i, t, width=w)
        self.res_list.Bind(wx.EVT_KEY_DOWN, self._on_res_key)
        self.res_list.Bind(wx.EVT_CONTEXT_MENU, self._on_res_menu)
        self.res_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                           lambda e: self._play_selected())
        v.Add(self.res_list, 3, wx.EXPAND | wx.ALL, 8)

        self.btn_more = wx.Button(p, label="To&vább (következő 25 találat)")
        self.btn_more.Bind(wx.EVT_BUTTON, lambda e: self._on_more())
        self.btn_more.Disable()
        v.Add(self.btn_more, 0, wx.LEFT | wx.BOTTOM, 8)

        # kosár
        v.Add(wx.StaticText(p, label="K&osár (Ctrl+K ide ugrik):"), 0,
              wx.LEFT, 8)
        self.cart_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.cart_list.SetName("Kosár listája")
        self.cart_list.InsertColumn(0, "Cím", width=620)
        self.cart_list.InsertColumn(1, "Hossz", width=90)
        self.cart_list.Bind(wx.EVT_KEY_DOWN, self._on_cart_key)
        v.Add(self.cart_list, 1, wx.EXPAND | wx.ALL, 8)

        crow = wx.BoxSizer(wx.HORIZONTAL)
        b_dl = wx.Button(p, label="Kosár &letöltése")
        b_dl.Bind(wx.EVT_BUTTON, lambda e: self._download_cart())
        b_rm = wx.Button(p, label="Kijelölt &eltávolítása")
        b_rm.Bind(wx.EVT_BUTTON, lambda e: self._cart_remove_selected())
        crow.Add(b_dl, 0, wx.RIGHT, 6)
        crow.Add(b_rm, 0)
        v.Add(crow, 0, wx.LEFT | wx.BOTTOM, 8)

        # lejátszó
        v.Add(wx.StaticText(p, label="Lejátszó:"), 0, wx.LEFT, 8)
        self.player_panel = wx.Panel(p, style=wx.WANTS_CHARS | wx.BORDER_SUNKEN)
        self.player_panel.SetName("Lejátszó – nyilakkal vezérelhető")
        pv = wx.BoxSizer(wx.VERTICAL)
        try:
            self.mc = wx.media.MediaCtrl(self.player_panel, size=(-1, 180))
        except Exception:
            self.mc = None
        if self.mc:
            self.mc.SetVolume(0.8)
            pv.Add(self.mc, 1, wx.EXPAND | wx.ALL, 2)
            self.mc.Bind(wx.media.EVT_MEDIA_LOADED, lambda e: self._mc_loaded())
            self.mc.Bind(wx.media.EVT_MEDIA_FINISHED,
                         lambda e: self._announce("A lejátszás véget ért."))
        self.pos_label = wx.StaticText(
            self.player_panel,
            label="Nincs lejátszás. Enter egy találaton: lejátszás. "
                  "Bal/jobb: tekerés, fel/le: hangerő, Ctrl+bal/jobb: "
                  "ugrásköz, szóköz: szünet, Escape: vissza a listához.")
        self.pos_label.SetName("Lejátszó állapota")
        pv.Add(self.pos_label, 0, wx.ALL, 4)
        self.player_panel.SetSizer(pv)
        self.player_panel.Bind(wx.EVT_KEY_DOWN, self._on_player_key)
        v.Add(self.player_panel, 2, wx.EXPAND | wx.ALL, 8)

        self.audio_chk = wx.CheckBox(p, label="Lejátszásnál csak &hang")
        self.audio_chk.SetValue(True)
        self.audio_chk.SetName("A lejátszó csak a hangot játssza (megbízhatóbb)")
        self.audio_chk.Bind(
            wx.EVT_CHECKBOX,
            lambda e: setattr(self, "_audio_only_play",
                              self.audio_chk.GetValue()))
        v.Add(self.audio_chk, 0, wx.LEFT | wx.BOTTOM, 8)

        p.SetSizer(v)

        # gyorsbillentyűk: Ctrl+K a kosárhoz, F1 súgó
        ido = wx.NewIdRef(); ihelp = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, lambda e: self.cart_list.SetFocus(), id=ido)
        self.Bind(wx.EVT_MENU, lambda e: self._help(), id=ihelp)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('K'), ido),
            (wx.ACCEL_NORMAL, wx.WXK_F1, ihelp),
        ]))

    # ---- segédek ------------------------------------------------------

    def _announce(self, text: str):
        self.SetStatusText(text)
        self.pos_label.SetLabel(text)

    @staticmethod
    def _from_rec(r: dict) -> S.Result:
        return S.Result(title=r.get("title", ""), url=r.get("url", ""),
                        source=r.get("source", ""),
                        duration=r.get("duration", 0),
                        uploader=r.get("uploader", ""), id=r.get("id", ""))

    @staticmethod
    def _to_rec(x: S.Result) -> dict:
        return {"title": x.title, "url": x.url, "source": x.source,
                "duration": x.duration, "uploader": x.uploader, "id": x.id}

    def _selected_result(self) -> S.Result | None:
        i = self.res_list.GetFirstSelected()
        return self.results[i] if 0 <= i < len(self.results) else None

    # ---- keresés ------------------------------------------------------

    def _on_search(self):
        q = self.search_entry.GetValue().strip()
        if not q:
            return
        self.query, self.count = q, PAGE
        self._run_search(focus_first=True)

    def _on_more(self):
        self.count += PAGE
        self._run_search(focus_first=False, keep=len(self.results))

    def _run_search(self, focus_first: bool, keep: int = 0):
        self.SetStatusText(f"Keresés: {self.query} …")
        self.btn_more.Disable()
        q, count = self.query, self.count

        def work():
            try:
                res = S.search(q, count=count)
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Keresési hiba: {e}")
                return
            wx.CallAfter(self._show_results, res, focus_first, keep)

        threading.Thread(target=work, daemon=True).start()

    def _show_results(self, res, focus_first, keep):
        self.results = res
        self.res_list.DeleteAllItems()
        for x in res:
            row = self.res_list.InsertItem(self.res_list.GetItemCount(),
                                           x.title)
            self.res_list.SetItem(row, 1, S.human_duration(x.duration))
            self.res_list.SetItem(row, 2, x.uploader)
        self.SetStatusText(f"{len(res)} találat a(z) „{self.query}” szóra.")
        if res and hasattr(self.main, "_sfx"):
            self.main._sfx("results")
        self.btn_more.Enable(bool(res))
        if res:
            sel = 0 if focus_first else min(keep, len(res) - 1)
            self.res_list.Select(sel)
            self.res_list.Focus(sel)
            self.res_list.SetFocus()

    # ---- találat-műveletek -------------------------------------------

    def _on_res_key(self, e):
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_selected()
        elif ctrl and code == ord('B'):
            self._add_to_cart()
        elif ctrl and code == ord('D'):
            self._download_selected()
        elif ctrl and code == ord('C'):
            self._copy_url()
        else:
            e.Skip()

    def _on_res_menu(self, e):
        if not self._selected_result():
            return
        m = wx.Menu()
        mi_play = m.Append(wx.ID_ANY, "&Lejátszás\tEnter")
        mi_cart = m.Append(wx.ID_ANY, "&Kosárba\tCtrl+B")
        mi_dl = m.Append(wx.ID_ANY, "Közvetlen le&töltés\tCtrl+D")
        mi_url = m.Append(wx.ID_ANY, "&URL pontos másolása\tCtrl+C")
        self.Bind(wx.EVT_MENU, lambda e: self._play_selected(), mi_play)
        self.Bind(wx.EVT_MENU, lambda e: self._add_to_cart(), mi_cart)
        self.Bind(wx.EVT_MENU, lambda e: self._download_selected(), mi_dl)
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), mi_url)
        self.res_list.PopupMenu(m)
        m.Destroy()

    def _add_to_cart(self):
        x = self._selected_result()
        if not x:
            return
        if any(c.id == x.id for c in self.cart):
            self._announce("Ez már a kosárban van.")
            return
        self.cart.append(x)
        self._save_cart()
        self._refresh_cart()
        self._announce(f"Kosárba téve: {x.title}")

    def _download_selected(self):
        x = self._selected_result()
        if x:
            self.main._on_add(url=x.url)
            self._announce(f"Letöltésre küldve: {x.title}")

    def _copy_url(self):
        x = self._selected_result()
        if x and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(x.url))
            wx.TheClipboard.Close()
            self._announce(f"URL a vágólapra másolva: {x.url}")

    # ---- kosár --------------------------------------------------------

    def _refresh_cart(self):
        self.cart_list.DeleteAllItems()
        for x in self.cart:
            row = self.cart_list.InsertItem(self.cart_list.GetItemCount(),
                                            x.title)
            self.cart_list.SetItem(row, 1, S.human_duration(x.duration))

    def _save_cart(self):
        store.save_cart([self._to_rec(c) for c in self.cart])

    def _on_cart_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._cart_remove_selected()
        else:
            e.Skip()

    def _cart_remove_selected(self):
        i = self.cart_list.GetFirstSelected()
        if 0 <= i < len(self.cart):
            x = self.cart.pop(i)
            self._save_cart()
            self._refresh_cart()
            self._announce(f"Eltávolítva a kosárból: {x.title}")

    def _download_cart(self):
        if not self.cart:
            self._announce("A kosár üres.")
            return
        for x in self.cart:
            self.main._on_add(url=x.url)
        self._announce(f"{len(self.cart)} elem letöltésre küldve a kosárból.")

    # ---- lejátszó -----------------------------------------------------

    def _play_selected(self):
        x = self._selected_result()
        if not x or not self.mc:
            return
        self._cur = x
        self._announce(f"Letöltés lejátszáshoz: {x.title} …")
        ckb, ckf = (self.main._cookies_config()
                    if hasattr(self.main, "_cookies_config") else (None, None))
        audio = self._audio_only_play

        def work():
            try:
                path = self._fetch_for_play(x.url, audio, ckb, ckf)
            except Exception as ex:
                wx.CallAfter(self._announce, self._friendly_error(str(ex)))
                return
            wx.CallAfter(self._load_local, path, x.title)

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _friendly_error(msg: str) -> str:
        m = msg.lower()
        if "not available" in m or "unavailable" in m or "removed" in m:
            return ("Ez a videó nem elérhető (lehet, hogy régiózárt vagy "
                    "törölt). Próbálj egy másikat a listából.")
        if "sign in" in m or "age" in m or "consent" in m or "private" in m:
            return ("Bejelentkezés szükséges. A fő ablakban állítsd be a "
                    "Sütik-et (böngésződ), majd próbáld újra.")
        return f"Nem lejátszható: {msg[:120]}. Próbálj egy másikat."

    def _fetch_for_play(self, url, audio, ckb, ckf) -> str:
        """A választott médiát ideiglenes fájlba tölti, és visszaadja az
        útvonalát. A helyi fájlt a beépített lejátszó megbízhatóan megnyitja
        (van kiterjesztése, ismert kodek)."""
        import yt_dlp
        PLAY_DIR.mkdir(parents=True, exist_ok=True)
        self._cleanup_play()
        if audio:
            fmt = "bestaudio[ext=m4a]/bestaudio"
        else:
            fmt = ("best[ext=mp4][acodec!=none][vcodec!=none]/"
                   "best[acodec!=none][vcodec!=none]/bestaudio[ext=m4a]/"
                   "bestaudio")
        holder: dict = {}

        def hook(d):
            if d["status"] == "downloading":
                t = (d.get("total_bytes") or d.get("total_bytes_estimate")
                     or 0)
                done = d.get("downloaded_bytes") or 0
                pct = int(done / t * 100) if t else 0
                wx.CallAfter(self._announce, f"Letöltés lejátszáshoz: {pct}%")
            elif d["status"] == "finished":
                holder["path"] = d.get("filename")

        opts = {"quiet": True, "no_warnings": True, "format": fmt,
                "outtmpl": str(PLAY_DIR / "play.%(ext)s"),
                "progress_hooks": [hook], "noprogress": True}
        if ckb:
            opts["cookiesfrombrowser"] = (ckb,)
        elif ckf:
            opts["cookiefile"] = ckf
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
        path = holder.get("path")
        if not path or not os.path.exists(path):
            files = glob.glob(str(PLAY_DIR / "play.*"))
            path = files[0] if files else None
        if not path:
            raise RuntimeError("nem jött létre lejátszható fájl")
        return path

    def _load_local(self, path, title):
        if not self.mc:
            return
        self._play_title = title
        if not self.mc.Load(path):
            self._announce("A lejátszó nem tudta megnyitni a fájlt.")
            return
        # FONTOS: a „betöltve” (EVT_MEDIA_LOADED) esemény ezzel a Windows-
        # motorral gyakran NEM sül el, ezért nem várunk rá – rövid késleltetés
        # után közvetlenül indítjuk a lejátszást (a fájl ekkorra már kész).
        self.player_panel.SetFocus()
        wx.CallLater(250, self._start_play)

    def _start_play(self):
        if not self.mc:
            return
        self.mc.Play()
        self._announce(f"Lejátszás: {getattr(self, '_play_title', '')}  "
                       "(bal/jobb tekerés, fel/le hangerő, Escape vissza)")

    def _mc_loaded(self):
        # ha mégis megérkezik a „betöltve” esemény, az is indítson (ártalmatlan)
        if self.mc:
            self.mc.Play()

    def _cleanup_play(self):
        try:
            for f in glob.glob(str(PLAY_DIR / "play.*")):
                try:
                    os.remove(f)
                except OSError:
                    pass
        except Exception:
            pass

    def _on_player_key(self, e):
        if not self.mc:
            e.Skip()
            return
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        step = SEEK_INTERVALS[self._interval_idx] * 1000
        if code == wx.WXK_ESCAPE:
            self.res_list.SetFocus()
        elif code == wx.WXK_SPACE:
            if self.mc.GetState() == wx.media.MEDIASTATE_PLAYING:
                self.mc.Pause()
                self._announce("Szünet.")
            else:
                self.mc.Play()
                self._announce("Lejátszás.")
        elif ctrl and code == wx.WXK_LEFT:
            self._interval_idx = max(0, self._interval_idx - 1)
            self._announce(f"Ugrásköz: {SEEK_INTERVALS[self._interval_idx]} "
                           "másodperc.")
        elif ctrl and code == wx.WXK_RIGHT:
            self._interval_idx = min(len(SEEK_INTERVALS) - 1,
                                     self._interval_idx + 1)
            self._announce(f"Ugrásköz: {SEEK_INTERVALS[self._interval_idx]} "
                           "másodperc.")
        elif code == wx.WXK_LEFT:
            self.mc.Seek(max(0, self.mc.Tell() - step))
            self._announce_pos()
        elif code == wx.WXK_RIGHT:
            self.mc.Seek(min(self.mc.Length(), self.mc.Tell() + step))
            self._announce_pos()
        elif code == wx.WXK_UP:
            self.mc.SetVolume(min(1.0, self.mc.GetVolume() + 0.05))
            self._announce(f"Hangerő: {round(self.mc.GetVolume() * 100)} "
                           "százalék.")
        elif code == wx.WXK_DOWN:
            self.mc.SetVolume(max(0.0, self.mc.GetVolume() - 0.05))
            self._announce(f"Hangerő: {round(self.mc.GetVolume() * 100)} "
                           "százalék.")
        else:
            e.Skip()

    def _announce_pos(self):
        if self.mc:
            self._announce(f"{_fmt_time(self.mc.Tell())} / "
                           f"{_fmt_time(self.mc.Length())}")

    # ---- súgó / zárás -------------------------------------------------

    def _help(self):
        wx.MessageBox(
            "Médiakereső – billentyűk\n\n"
            "Keresőmező: írd be a szót, Enter = keresés.\n"
            "Találatlista (fel/le nyíl a mozgás):\n"
            "  Enter – lejátszás\n"
            "  Ctrl+B – kosárba\n"
            "  Ctrl+D – közvetlen letöltés\n"
            "  Ctrl+C – URL pontos másolása\n"
            "  Menü-billentyű / jobb klikk – helyi menü\n"
            "  Tovább gomb – következő 25 találat\n\n"
            "Kosár (Ctrl+K): Delete – eltávolítás; „Kosár letöltése” gomb.\n\n"
            "Lejátszó (Enter után ide kerül a fókusz):\n"
            "  bal/jobb nyíl – tekerés, fel/le – hangerő\n"
            "  Ctrl+bal/jobb – ugrásköz (5–60 mp)\n"
            "  szóköz – szünet/folytatás, Escape – vissza a listához",
            "Médiakereső súgó", wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        try:
            if self.mc:
                self.mc.Stop()
        except Exception:
            pass
        self._cleanup_play()
        self._save_cart()
        if getattr(self.main, "_search_win", None) is self:
            self.main._search_win = None
        e.Skip()          # bezárjuk; a kosár tartalma megmarad a lemezen
