"""Akadálymentes hírolvasó ablak.

Fent kiválasztod a hírforrást, alatta a szalagcímek listája; egy szalagcímen
Entert nyomva a cikk teljes, letisztított szövege megjelenik egy csak
olvasható mezőben, reklám és menü nélkül. Tabbal és nyilakkal navigálható,
a cikk fel is olvastatható.
"""

import threading
import webbrowser

import wx

from . import aiclient, news
from .aiwin import run_ai


class NewsFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Hírolvasó", size=(900, 680))
        self.main = main
        self.nm = main.news_mgr
        self.speaker = getattr(main, "speaker", None)
        self.articles: list[news.Article] = []

        self._build()
        self.CreateStatusBar()      # a státuszsor MIELŐTT bármi SetStatusText-et hív
        self.SetStatusText("Válassz forrást, Enter a szalagcímen = cikk. "
                           "Felolvasás: a gomb vagy a cikknél. Frissítés: F5.")
        self._reload_feeds()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        if self.feed_ch.GetCount():
            self.feed_ch.SetFocus()

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="&Forrás:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.feed_ch = wx.Choice(p, choices=[])
        self.feed_ch.SetName("Hírforrás választása")
        self.feed_ch.Bind(wx.EVT_CHOICE, lambda e: self._on_feed_change())
        # rövid késleltetés a betöltés elé: ha nyilakkal pörgeted a forrásokat,
        # csak a megállás után tölt be (és a fókusz a forrásokon marad)
        self._load_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._load_headlines(),
                  self._load_timer)
        row.Add(self.feed_ch, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        for label, fn in (("Fri&ssítés", lambda e: self._load_headlines()),
                          ("Ú&j forrás…", lambda e: self._add_feed()),
                          ("Forrás &törlése", lambda e: self._remove_feed())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Szalagcímek (Enter: a cikk megnyitása):"),
              0, wx.LEFT, 8)
        self.head_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.head_list.SetName("Szalagcímek listája")
        self.head_list.InsertColumn(0, "Szalagcím", width=820)
        self.head_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                            lambda e: self._open_article())
        v.Add(self.head_list, 2, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Cikk szövege (csak olvasható):"),
              0, wx.LEFT, 8)
        self.article = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.article.SetName("Cikk szövege")
        v.Add(self.article, 3, wx.EXPAND | wx.ALL, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        self.speak_btn = wx.Button(p, label="&Felolvasás")
        self.speak_btn.Bind(wx.EVT_BUTTON, lambda e: self._speak())
        self.speak_btn.Enable(bool(getattr(self.speaker, "available", False)))
        b_stop = wx.Button(p, label="Némí&tás")
        b_stop.Bind(wx.EVT_BUTTON, lambda e: self._stop_speech())
        b_open = wx.Button(p, label="Megnyitás a &böngészőben")
        b_open.Bind(wx.EVT_BUTTON, lambda e: self._open_browser())
        b_sum = wx.Button(p, label="AI össze&foglaló")
        b_sum.Bind(wx.EVT_BUTTON, lambda e: self._ai_summary())
        b_tr = wx.Button(p, label="Fordítás m&agyarra")
        b_tr.Bind(wx.EVT_BUTTON, lambda e: self._ai_translate())
        for b in (self.speak_btn, b_stop, b_open, b_sum, b_tr):
            ctl.Add(b, 0, wx.RIGHT, 6)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)
        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in ("refresh", "stop")}
        self.Bind(wx.EVT_MENU, lambda e: self._load_headlines(),
                  id=ids["refresh"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop_speech(), id=ids["stop"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["refresh"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
        ]))

    # ---- forrás / szalagcímek -----------------------------------------

    def _reload_feeds(self):
        self.feed_ch.Set([f.label() for f in self.nm.feeds])
        if self.nm.feeds:
            self.feed_ch.SetSelection(0)
            self._load_headlines()

    def _on_feed_change(self):
        # nem töltünk be azonnal: kis késleltetéssel (a fókusz a választón
        # marad, és a gyors nyíl-léptetés nem indít fölösleges letöltést)
        self._load_timer.Stop()
        self._load_timer.StartOnce(450)

    def _current_feed(self):
        i = self.feed_ch.GetSelection()
        return self.nm.feeds[i] if 0 <= i < len(self.nm.feeds) else None

    def _load_headlines(self):
        feed = self._current_feed()
        if not feed:
            return
        self.SetStatusText(f"Szalagcímek betöltése: {feed.title or feed.url} …")
        self.head_list.DeleteAllItems()
        self.article.SetValue("")

        def work():
            try:
                title, arts = news.parse_news(feed.url)
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Hiba a forrásnál: {e}")
                return
            wx.CallAfter(self._show_headlines, feed, title, arts)

        threading.Thread(target=work, daemon=True).start()

    def _show_headlines(self, feed, title, arts):
        self.articles = arts
        self.head_list.DeleteAllItems()
        for a in arts:
            self.head_list.InsertItem(self.head_list.GetItemCount(), a.title)
        # ha a forrásnak még nincs neve, töltsük ki – de a legördülő elemét
        # HELYBEN frissítjük (nem építjük újra), hogy ne ugorjon el a kurzor
        if title and not feed.title:
            feed.title = title
            self.nm.save()
            try:
                self.feed_ch.SetString(self.nm.feeds.index(feed), feed.label())
            except Exception:
                pass
        self.SetStatusText(f"{len(arts)} szalagcím – {title}. "
                           "(Tabbal a szalagcímekhez.)")
        if arts:
            self.head_list.Select(0)
            self.head_list.Focus(0)
            # a fókusz SZÁNDÉKOSAN a forrás-választón marad: így nyugodtan
            # végiglépkedhetsz a forrásokon; Tabbal mész a szalagcímekhez

    # ---- cikk ---------------------------------------------------------

    def _selected_article(self):
        i = self.head_list.GetFirstSelected()
        return self.articles[i] if 0 <= i < len(self.articles) else None

    def _open_article(self):
        art = self._selected_article()
        if not art:
            return
        self.SetStatusText(f"Cikk betöltése: {art.title} …")
        self.article.SetValue("A cikk letöltése és tisztítása folyamatban…")

        def work():
            text = news.fetch_article_text(art.link, fallback=art.summary)
            wx.CallAfter(self._show_article, art, text)

        threading.Thread(target=work, daemon=True).start()

    def _show_article(self, art, text):
        header = art.title
        if art.published:
            header += f"\n{art.published}"
        body = f"{header}\n\n{text}\n\n— Forrás: {art.link}"
        self.article.SetValue(body)
        self.article.SetInsertionPoint(0)
        self.article.SetFocus()
        self.SetStatusText(f"Kész: {art.title}. Felolvasás: F a gombbal, "
                           "némítás: Escape.")

    # ---- felolvasás / böngésző ----------------------------------------

    def _speak(self):
        if getattr(self.speaker, "available", False):
            text = self.article.GetValue().strip()
            if text:
                self.speaker.speak(text)
                self.SetStatusText("Felolvasás… (némítás: Escape)")

    def _stop_speech(self):
        if self.speaker:
            try:
                self.speaker.stop()
            except Exception:
                pass

    def _open_browser(self):
        art = self._selected_article()
        if art and art.link:
            webbrowser.open(art.link)

    # ---- AI: összefoglaló / fordítás ----------------------------------

    def _ai_summary(self):
        text = self.article.GetValue().strip()
        if len(text) < 30:
            self.SetStatusText("Előbb nyiss meg egy cikket (Enter a "
                               "szalagcímen).")
            return

        def worker():
            return aiclient.chat(
                "Foglald össze a következő hírcikket magyarul, 3–6 tömör, "
                "tárgyilagos pontban:\n\n" + text, max_tokens=1200)
        run_ai(self.main, "Cikk összefoglaló", worker,
               busy="A cikk összefoglalása folyamatban…")

    def _ai_translate(self):
        text = self.article.GetValue().strip()
        if len(text) < 5:
            self.SetStatusText("Előbb nyiss meg egy cikket.")
            return

        def worker():
            return aiclient.chat(
                "Fordítsd le a következő szöveget magyarra, természetes, "
                "gördülékeny stílusban. Csak a fordítást add vissza:\n\n"
                + text, max_tokens=3000)
        run_ai(self.main, "Fordítás magyarra", worker,
               busy="Fordítás folyamatban…")

    # ---- forrás hozzáadása / törlése ----------------------------------

    def _add_feed(self):
        dlg = wx.TextEntryDialog(
            self, "A hírforrás RSS-címe (URL):", "Új hírforrás")
        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.GetValue().strip()
            if url:
                self.SetStatusText(f"Forrás vizsgálata: {url} …")

                def work():
                    self.nm.add_feed(url)
                    wx.CallAfter(self._after_add)
                threading.Thread(target=work, daemon=True).start()
        dlg.Destroy()

    def _after_add(self):
        self.feed_ch.Set([f.title or f.url for f in self.nm.feeds])
        self.feed_ch.SetSelection(len(self.nm.feeds) - 1)
        self._load_headlines()

    def _remove_feed(self):
        feed = self._current_feed()
        if not feed:
            return
        if wx.MessageBox(f"Törlöd ezt a hírforrást?\n\n{feed.title or feed.url}",
                         "Forrás törlése", wx.YES_NO | wx.ICON_QUESTION,
                         self) == wx.YES:
            self.nm.remove_feed(feed.url)
            self.head_list.DeleteAllItems()
            self.article.SetValue("")
            self._reload_feeds()

    def _on_close(self, e):
        self._load_timer.Stop()
        self._stop_speech()
        if getattr(self.main, "_news_win", None) is self:
            self.main._news_win = None
        e.Skip()
