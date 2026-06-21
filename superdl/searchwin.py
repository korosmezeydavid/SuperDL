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

from . import search as S
from . import store
from .audioengine import Player

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
        self.results: list[S.Result] = []   # az összes lekért találat
        self._shown: list[S.Result] = []    # a hossz-szűrő után megjelenítettek
        self.cart: list[S.Result] = [self._from_rec(r)
                                     for r in store.load_cart()]
        self.query = ""
        self.count = PAGE
        self._audio_only_play = True
        self._cur = None                 # épp játszott találat
        self._player_mode = False        # lejátszó-vezérlés be van-e kapcsolva
        # megbízható streaming hangmotor (ffmpeg → sounddevice), ugyanaz, mint
        # a rádiónál; a kényes wx.media helyett
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._on_player_state, s)

        self._build()
        self._refresh_cart()
        self.CreateStatusBar()
        self.SetStatusText("Írd be a keresőszót, és nyomj Entert. "
                           "Lejátszás: Enter a találaton. Súgó: F1.")
        # ablakszintű billentyű-elkapó: lejátszó módban a nyilak a lejátszót
        # vezérlik (a panel nem tartja a fókuszt, ezért kell a CHAR_HOOK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
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
        row.Add(wx.StaticText(p, label="&Típus:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.kind_choice = wx.Choice(
            p, choices=["Videó", "Lejátszási lista", "Csatorna"])
        self.kind_choice.SetSelection(0)
        self.kind_choice.SetName("Keresés típusa")
        # típusváltáskor – ha van már keresőszó – újrakeresünk
        self.kind_choice.Bind(
            wx.EVT_CHOICE,
            lambda e: self._on_search() if self.search_entry.GetValue().strip()
            else None)
        btn_search = wx.Button(p, label="Ke&resés")
        btn_search.Bind(wx.EVT_BUTTON, lambda e: self._on_search())
        row.Add(self.search_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.kind_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(btn_search, 0)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # hossz-szűrő: a már lekért találatokat a hosszuk alapján szűri
        # (letöltés/újrakeresés nélkül, azonnal)
        frow = wx.BoxSizer(wx.HORIZONTAL)
        frow.Add(wx.StaticText(p, label="&Hossz:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.dur_choice = wx.Choice(
            p, choices=["Bármilyen", "rövidebb, mint", "hosszabb, mint"])
        self.dur_choice.SetSelection(0)
        self.dur_choice.SetName("Hossz szerinti szűrés")
        self.dur_choice.Bind(wx.EVT_CHOICE, lambda e: self._display())
        self.dur_spin = wx.SpinCtrl(p, min=1, max=600, initial=10,
                                    size=(70, -1))
        self.dur_spin.SetName("Perc")
        self.dur_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._display())
        frow.Add(self.dur_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        frow.Add(self.dur_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        frow.Add(wx.StaticText(p, label="perc"), 0, wx.ALIGN_CENTER_VERTICAL)
        v.Add(frow, 0, wx.LEFT | wx.BOTTOM, 8)

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
                           lambda e: self._primary_action())
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

        # lejátszó (streaming hangmotor – nincs külön videofelület)
        v.Add(wx.StaticText(p, label="Lejátszó:"), 0, wx.LEFT, 8)
        self.player_panel = wx.Panel(p)
        pv = wx.BoxSizer(wx.VERTICAL)
        self.pos_label = wx.StaticText(
            self.player_panel,
            label="Nincs lejátszás. Enter egy találaton: lejátszás. "
                  "Fel/le: hangerő, szóköz: szünet/folytatás, Escape: "
                  "leállítás.")
        self.pos_label.SetName("Lejátszó állapota")
        pv.Add(self.pos_label, 0, wx.ALL, 4)
        self.player_panel.SetSizer(pv)
        v.Add(self.player_panel, 0, wx.EXPAND | wx.ALL, 8)

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
        return self._shown[i] if 0 <= i < len(self._shown) else None

    # ---- keresés ------------------------------------------------------

    def _on_search(self):
        q = self.search_entry.GetValue().strip()
        if not q:
            return
        self._player_mode = False        # új keresés: vissza lista-módba
        self.query, self.count = q, PAGE
        self._run_search(focus_first=True)

    def _on_more(self):
        self.count += PAGE
        self._run_search(focus_first=False, keep=len(self.results))

    def _run_search(self, focus_first: bool, keep: int = 0):
        self.SetStatusText(f"Keresés: {self.query} …")
        self.btn_more.Disable()
        q, count = self.query, self.count
        kind = ("video", "playlist", "channel")[self.kind_choice.GetSelection()]

        def work():
            try:
                res = S.search(q, count=count, kind=kind)
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Keresési hiba: {e}")
                return
            wx.CallAfter(self._show_results, res, focus_first, keep)

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _dedup(items):
        """Találatok duplikátum-szűrése id/url alapján, sorrend megtartásával."""
        seen, out = set(), []
        for x in items:
            key = x.id or x.url
            if key in seen:
                continue
            seen.add(key)
            out.append(x)
        return out

    def _add_row(self, x):
        """Egy találat hozzáfűzése a ListCtrl végéhez (egységes oszlopokkal)."""
        row = self.res_list.InsertItem(self.res_list.GetItemCount(), x.title)
        self.res_list.SetItem(row, 1, S.human_duration(x.duration))
        self.res_list.SetItem(row, 2, x.uploader)
        return row

    def _show_results(self, res, focus_first, keep):
        if res and hasattr(self.main, "_sfx"):
            self.main._sfx("results")
        if focus_first:
            # új keresés: teljes csere + dedup, majd teljes újraépítés
            self.results = self._dedup(res)
            self.btn_more.Enable(bool(self.results))
            self._display(focus_first=True)
        else:
            # „Tovább": CSAK a még nem látott találatokat fűzzük hozzá (nincs
            # duplikátum, és nem építjük újra a listát → a képernyőolvasó nem
            # veszti el a helyét). A fókusz az ELSŐ ÚJ találatra kerül.
            seen = {(r.id or r.url) for r in self.results}
            added = [r for r in res if (r.id or r.url) not in seen]
            self.results.extend(added)
            self.btn_more.Enable(True)
            self._append_new(added)

    def _pass_duration(self, x) -> bool:
        """Átmegy-e a hossz-szűrőn? (0 = bármilyen, 1 = rövidebb, 2 = hosszabb)"""
        # lejátszási listáknak / csatornáknak nincs értelmezhető hosszuk
        if (getattr(x, "kind", "video") or "video") != "video":
            return True
        mode = self.dur_choice.GetSelection()
        if mode == 0:
            return True
        secs = self.dur_spin.GetValue() * 60
        d = x.duration or 0
        if d <= 0:                       # ismeretlen hossz – szűrésnél kihagyjuk
            return False
        return d <= secs if mode == 1 else d >= secs

    def _display(self, focus_first: bool = True, keep: int = 0):
        """A találatok TELJES újraépítése a hossz-szűrő alkalmazásával
        (új keresésnél és a szűrő változásakor)."""
        self._shown = [x for x in self.results if self._pass_duration(x)]
        self.res_list.DeleteAllItems()
        for x in self._shown:
            self._add_row(x)
        self._update_status()
        if self._shown:
            sel = 0 if focus_first else min(keep, len(self._shown) - 1)
            self.res_list.Select(sel)
            self.res_list.Focus(sel)
            self.res_list.SetFocus()

    def _append_new(self, added):
        """A „Tovább" után CSAK az új találatok hozzáfűzése a lista végéhez,
        a meglévő sorok és a kijelölés bolygatása nélkül. A fókusz az első új
        találatra ugrik, hogy a képernyőolvasó onnan folytassa az olvasást."""
        new_shown = [x for x in added if self._pass_duration(x)]
        first_row = None
        for x in new_shown:
            row = self._add_row(x)
            if first_row is None:
                first_row = row
        self._shown.extend(new_shown)
        self._update_status()
        if first_row is not None:
            self.res_list.Select(first_row)
            self.res_list.Focus(first_row)
            self.res_list.SetFocus()
        else:
            # nem jött új találat (vagy mind kiszűrtük) – jelezzük
            self._announce("Nincs több új találat.")

    def _update_status(self):
        if self.dur_choice.GetSelection() == 0:
            self.SetStatusText(f"{len(self._shown)} találat a(z) "
                               f"„{self.query}” szóra.")
        else:
            self.SetStatusText(f"{len(self._shown)} találat a szűrés után "
                               f"({len(self.results)} összesen) – "
                               f"„{self.query}”.")

    # ---- találat-műveletek -------------------------------------------

    def _on_res_key(self, e):
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._primary_action()
        elif ctrl and code == ord('B'):
            self._add_to_cart()
        elif ctrl and code == ord('D'):
            self._download_selected()
        elif ctrl and code == ord('C'):
            self._copy_url()
        else:
            e.Skip()

    def _on_res_menu(self, e):
        x = self._selected_result()
        if not x:
            return
        m = wx.Menu()
        if x.kind == "channel":
            # csatorna: a fő művelet a feliratkozás
            mi_sub = m.Append(wx.ID_ANY, "&Feliratkozás a csatornára\tEnter")
            mi_open = m.Append(wx.ID_ANY, "Meg&nyitás a böngészőben")
            mi_url = m.Append(wx.ID_ANY, "&URL pontos másolása\tCtrl+C")
            self.Bind(wx.EVT_MENU, lambda e: self._subscribe_channel(), mi_sub)
            self.Bind(wx.EVT_MENU, lambda e: self._open_in_browser(), mi_open)
            self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), mi_url)
        elif x.kind == "playlist":
            # lejátszási lista: a fő művelet a teljes lista letöltése
            mi_dl = m.Append(wx.ID_ANY, "A teljes lista le&töltése\tEnter")
            mi_cart = m.Append(wx.ID_ANY, "&Kosárba\tCtrl+B")
            mi_open = m.Append(wx.ID_ANY, "Meg&nyitás a böngészőben")
            mi_url = m.Append(wx.ID_ANY, "&URL pontos másolása\tCtrl+C")
            self.Bind(wx.EVT_MENU, lambda e: self._download_selected(), mi_dl)
            self.Bind(wx.EVT_MENU, lambda e: self._add_to_cart(), mi_cart)
            self.Bind(wx.EVT_MENU, lambda e: self._open_in_browser(), mi_open)
            self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), mi_url)
        else:
            mi_play = m.Append(wx.ID_ANY, "&Lejátszás\tEnter")
            mi_cart = m.Append(wx.ID_ANY, "&Kosárba\tCtrl+B")
            mi_dl = m.Append(wx.ID_ANY, "Közvetlen le&töltés\tCtrl+D")
            mi_url = m.Append(wx.ID_ANY, "&URL pontos másolása\tCtrl+C")
            m.AppendSeparator()
            mi_ai = m.Append(wx.ID_ANY, "AI: Videó &elemzése")
            self.Bind(wx.EVT_MENU, lambda e: self._play_selected(), mi_play)
            self.Bind(wx.EVT_MENU, lambda e: self._add_to_cart(), mi_cart)
            self.Bind(wx.EVT_MENU, lambda e: self._download_selected(), mi_dl)
            self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), mi_url)
            self.Bind(wx.EVT_MENU, lambda e: self._ai_analyze(), mi_ai)
        self.res_list.PopupMenu(m)
        m.Destroy()

    def _primary_action(self):
        """A kiválasztott találat típusától függő fő művelet (Enter)."""
        x = self._selected_result()
        if not x:
            return
        if x.kind == "channel":
            self._subscribe_channel()
        elif x.kind == "playlist":
            self._download_selected()
        else:
            self._play_selected()

    def _subscribe_channel(self):
        x = self._selected_result()
        if x:
            self._announce(f"Feliratkozás a csatornára: {x.title}")
            self.main._do_channel_subscribe(x.url)

    def _open_in_browser(self):
        x = self._selected_result()
        if x:
            import webbrowser
            webbrowser.open(x.url)
            self._announce(f"Megnyitva a böngészőben: {x.title}")

    def _ai_analyze(self):
        x = self._selected_result()
        if x:
            self._announce(f"Videó elemzése AI-jal: {x.title}")
            self.main._analyze_video_auto(x.url)

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
        if not x:
            return
        self._cur = x
        self._announce(f"Csatlakozás: {x.title} …")
        ckb, ckf = (self.main._cookies_config()
                    if hasattr(self.main, "_cookies_config") else (None, None))
        audio = self._audio_only_play

        # próbáljuk sütikkel; ha az elbukik (pl. fut a böngésző, zárolt
        # sütik-adatbázis), újrapróbáljuk sütik NÉLKÜL – a legtöbb keresőtalálat
        # nyilvános, nem kell hozzá bejelentkezés
        attempts = [(ckb, ckf)]
        if ckb or ckf:
            attempts.append((None, None))

        def work():
            last = None
            for b, f in attempts:
                try:
                    stream_url, _, _ = S.resolve_stream(
                        x.url, audio_only=audio, cookies_browser=b,
                        cookies_file=f)
                    if stream_url:
                        wx.CallAfter(self.player.play, stream_url, x.title)
                        return
                    last = "üres találat"
                except Exception as ex:
                    last = ex
            wx.CallAfter(self._announce, self._friendly_error(str(last)))

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

    def _on_player_state(self, text):
        if text == "lejátszás":
            self._player_mode = True
            t = self._cur.title if self._cur else ""
            self._announce(f"Lejátszás: {t}  (hangerő "
                           f"{round(self.player.volume * 100)}%). Szóköz: "
                           "szünet, fel/le: hangerő, Escape: leállítás.")
        elif text.startswith("hiba"):
            self._player_mode = False
            self._announce(f"Nem lejátszható – {text}. Próbálj másikat.")
        elif text == "vége":
            self._player_mode = False
            self._announce("A lejátszás véget ért. Enter egy találaton: új "
                           "lejátszás.")

    def _on_char_hook(self, e):
        """Ablakszintű billentyű-elkapó. Lejátszó módban (Enter után) a
        nyilak/szóköz a lejátszót vezérlik – kivéve, ha épp szövegmezőben
        gépelsz (akkor a kurzor mozogjon normálisan)."""
        focus = wx.Window.FindFocus()
        if (self._player_mode and self.player.is_active()
                and not isinstance(focus, wx.TextCtrl)):
            if self._player_key(e):
                return                   # kezeltük, nem adjuk tovább
        # lista módban: Enter a találati listán MINDIG a típus szerinti fő
        # műveletet indítsa (videó: lejátszás, lista: letöltés, csatorna:
        # feliratkozás) – megbízhatóbb, mint a lista saját Enter-eseménye
        if (not self._player_mode and focus is self.res_list
                and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
            self._primary_action()
            return
        e.Skip()

    def _player_key(self, e) -> bool:
        """A lejátszó-vezérlő billentyűk kezelése. True, ha lekezeltük."""
        code = e.GetKeyCode()
        if code == wx.WXK_ESCAPE:
            self.player.stop()
            self._player_mode = False
            self.res_list.SetFocus()
            self._announce("Leállítva. Vissza a találati listához.")
        elif code == wx.WXK_SPACE:
            paused = self.player.toggle_pause()
            self._announce("Szünet." if paused else "Folytatás.")
        elif code == wx.WXK_UP:
            self.player.set_volume(self.player.volume + 0.05)
            self._announce(f"Hangerő: {round(self.player.volume * 100)} "
                           "százalék.")
        elif code == wx.WXK_DOWN:
            self.player.set_volume(self.player.volume - 0.05)
            self._announce(f"Hangerő: {round(self.player.volume * 100)} "
                           "százalék.")
        else:
            return False
        return True

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
            "Lejátszás közben (a fókusz a listán marad):\n"
            "  fel/le nyíl – hangerő\n"
            "  szóköz – szünet/folytatás, Escape – leállítás",
            "Médiakereső súgó", wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        self._save_cart()
        if getattr(self.main, "_search_win", None) is self:
            self.main._search_win = None
        e.Skip()          # bezárjuk; a kosár tartalma megmarad a lemezen
