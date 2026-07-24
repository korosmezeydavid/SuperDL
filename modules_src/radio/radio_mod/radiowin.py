"""Internetes rádió ablak: keresés (név/címke/ország) és népszerű
állomások, kedvencek, és élő lejátszás a streaming hangmotorral.

Akadálymentes: a listákban fel/le nyíllal mozogsz; a lejátszó-vezérlők
gombokkal ÉS gyorsbillentyűkkel is elérhetők, amelyek nem ütköznek a lista
navigációjával.
"""

import threading

import wx

from . import radio as R                        # a rádió-backend a modulban van
from superdl import store                       # megosztott tároló a Core-ból
from superdl.audioengine import Player          # megosztott lejátszó a Core-ból
from .radiorecwin import RecordingsDialog, ScheduleDialog   # a modulban


def _net_ok(what):
    """Internet-elő-ellenőrzés VÉDETTEN: ha a Core-ban nincs netcheck (régebbi
    verzió), egyszerűen átengedjük (True) – a modul így régi Core-on is működik."""
    try:
        from superdl import netcheck
        return netcheck.require_online(what)
    except Exception:
        return True, ""

HELP = """INTERNETES RÁDIÓ

MIRE VALÓ
Élő rádióállomások keresése és hallgatása, azonnali és időzített felvétellel.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. Keress: a keresőmezőbe írd be a szót, válaszd, mi szerint (Név / Címke),
   Enter. Vagy „Népszerű állomások”, vagy ország szerint a legördülőből + „Az
   ország állomásai”.
2. Az állomáslistában fel/le nyíllal mozogsz; Enter vagy F5: lejátszás.
3. Hangerő: Ctrl+fel / Ctrl+le. Szünet: Ctrl+Szóköz. Leállítás: Esc.
4. Felvétel: F9 a kijelölt állomásra (újra F9: leállítás). Egyszerre több
   állomás is felvehető. Időzített felvétel: Ctrl+R (az állomást a KEDVENCEK
   közül választod, mettől meddig, egyszeri / minden nap / adott napokon).

NÉMÍTÁS FELVÉTEL KÖZBEN
A „Némítás be/ki” gomb (vagy Ctrl+M) elnémítja a HALLGATOTT hangot, de a
FELVÉTEL zavartalanul tovább megy. Így pl. munkahelyen vagy időzített felvétel
alatt csendben rögzítheted a műsort. (Ez nem szünet: a szünet – Ctrl+Szóköz –
csak a lejátszást állítja meg, a némítás viszont halkít, a hang bármikor
visszahozható.)

GYORSBILLENTYŰK
F1 – súgó.  Enter vagy F5 – lejátszás.  Ctrl+B – kedvencekhez.  Ctrl+C – URL
másolása.  Ctrl+fel / Ctrl+le – hangerő.  Ctrl+M – némítás be/ki.  Ctrl+Szóköz –
szünet.  Esc – leállítás.  F9 – felvétel most.  Ctrl+R – időzített felvétel.
Ctrl+Shift+F – felvételek és időzítések kezelése.  A listákban Delete – törlés.

SAJÁT ÁLLOMÁS ÉS MEGOSZTÁS
- „Saját állomás hozzáadása”: ha egy rádió nincs a listában, itt megadhatod a
  nevét és a stream-URL-jét – a kedvencek közé kerül, és rögtön hallgathatod.
- „Megosztás a közösséggel”: a kijelölt (saját) állomást beküldheted a
  radio-browser.info NYILVÁNOS közösségi adatbázisába – így más SuperDL-esek is
  megtalálják kereséssel. A beküldés nyilvános, kérdés után történik; csak
  saját, legális, nyilvánosan sugárzott állomást küldj be.

TIPP
A felvételek a célmappa „Rádiófelvételek” dátumozott almappájába kerülnek,
MP3-ként. Az időzített felvételhez a program legyen nyitva a megadott időben."""


class CustomStationDialog(wx.Dialog):
    """Saját rádióállomás megadása (név + stream-URL, opcionális ország/címke).
    Akadálymentes: minden mező címkézve, a Hozzáadás az alapértelmezett gomb."""

    def __init__(self, parent):
        super().__init__(parent, title="Saját rádióállomás hozzáadása",
                         size=(560, 340))
        self.station = None
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        g = wx.FlexGridSizer(0, 2, 8, 8)
        g.AddGrowableCol(1)

        def row(label, acc_name, hint=""):
            g.Add(wx.StaticText(p, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            c = wx.TextCtrl(p)
            c.SetName(acc_name)
            if hint:
                c.SetHint(hint)
            g.Add(c, 0, wx.EXPAND)
            return c

        self.c_name = row("&Név:", "Állomás neve")
        self.c_url = row("&Stream-URL:", "Stream URL",
                         "http:// vagy https://… (mp3/aac/m3u8…)")
        self.c_country = row("&Ország (ISO-kód, pl. HU):", "Ország ISO-kódja")
        self.c_tags = row("&Címkék (vesszővel):", "Címkék", "pl. pop, hírek")
        v.Add(g, 1, wx.EXPAND | wx.ALL, 12)
        v.Add(wx.StaticText(
            p, label="A saját állomás a KEDVENCEK közé kerül. A közösségi "
            "megosztás külön, a főablak „Megosztás” gombjával, kérdés után "
            "történik."), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK, "&Hozzáadás")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(p, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        v.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        p.SetSizer(v)
        from superdl.uihelp import bind_help
        bind_help(self, "Súgó – Saját állomás",
                  "SAJÁT RÁDIÓÁLLOMÁS\n\nEgy nem listázott rádió hozzáadása a "
                  "saját stream-címével.\n• Add meg az állomás nevét és a "
                  "streaming URL-t (m3u, pls vagy közvetlen hangstream).\n"
                  "• OK: hozzáadja a kedvenceidhez.\n\n"
                  "Ha nem tudod a stream-címet, gyakran a rádió weboldalán, a "
                  "„hallgatás” vagy „lejátszó” hivatkozásnál található.")

    def _on_ok(self, e):
        name = self.c_name.GetValue().strip()
        url = self.c_url.GetValue().strip()
        if not name or not url:
            wx.MessageBox("A név és a stream-URL is kötelező.", "Hiányzó adat",
                          wx.OK | wx.ICON_WARNING, self)
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            wx.MessageBox("A stream-URL http:// vagy https:// címmel kezdődjön.",
                          "Érvénytelen URL", wx.OK | wx.ICON_WARNING, self)
            return
        self.station = R.Station(
            name=name, url=url,
            country=self.c_country.GetValue().strip().upper()[:2],
            tags=self.c_tags.GetValue().strip())
        e.Skip()          # érvényes → a párbeszéd ID_OK-kal zárul


class RadioFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Internetes rádió",
                         size=(900, 640))
        self.main = main
        self._closing = False        # zárás alatt a háttér-callbackek kilépnek
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._on_state, s)
        self.rec = getattr(main, "_record_mgr", None)   # felvétel-kezelő
        self._manual_rec = None                          # folyó kézi felvétel
        self._sapi = None                                # rendszer-TTS tartalék
        self.stations: list[R.Station] = []
        self.favorites: list[R.Station] = [
            self._from_rec(r) for r in store.load_radio_favorites()]
        self._cur: R.Station | None = None
        self.countries: list[R.Country] = []
        self._country_limit = 50         # ország-top találatszám (Tovább növeli)
        self._cur_country: R.Country | None = None
        self._pre_mute_vol = None        # némításkor ide mentjük a hangerőt

        self._build()
        self._refresh_fav()
        self._load_countries()
        self.CreateStatusBar()
        self.SetStatusText("Keress állomást, vagy nézd a népszerűeket. "
                           "Lejátszás: Enter. Hangerő: Ctrl+fel/le. Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.search_entry.SetFocus()

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, label="&Keresés:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.search_entry = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.search_entry.SetName("Keresőszó")
        self.search_entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_search())
        self.by_choice = wx.Choice(p, choices=["Név", "Címke (műfaj)"])
        self.by_choice.SetSelection(0)
        self.by_choice.SetName("Mi szerint keressen")
        b_search = wx.Button(p, label="Ke&resés")
        b_search.Bind(wx.EVT_BUTTON, lambda e: self._on_search())
        b_top = wx.Button(p, label="&Népszerű állomások")
        b_top.Bind(wx.EVT_BUTTON, lambda e: self._on_top())
        row.Add(self.search_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.by_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(b_search, 0, wx.RIGHT, 6)
        row.Add(b_top, 0)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # ország szerinti böngészés (a régi, hibás név-szerinti keresés helyett:
        # legördülő ország + az adott ország legnépszerűbb állomásai)
        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(wx.StaticText(p, label="&Ország:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.country_choice = wx.Choice(p, choices=["(betöltés…)"])
        self.country_choice.SetName("Ország választása")
        self.country_choice.Disable()
        b_country = wx.Button(p, label="Az ország á&llomásai")
        b_country.Bind(wx.EVT_BUTTON, lambda e: self._on_country_top())
        self.b_country_more = wx.Button(p, label="To&vább (több ország-állomás)")
        self.b_country_more.Bind(wx.EVT_BUTTON, lambda e: self._on_country_more())
        self.b_country_more.Disable()
        crow.Add(self.country_choice, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        crow.Add(b_country, 0, wx.RIGHT, 6)
        crow.Add(self.b_country_more, 0)
        v.Add(crow, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="&Állomások (Enter: lejátszás, "
              "Ctrl+B: kedvencekhez, Ctrl+C: URL):"), 0, wx.LEFT, 8)
        self.st_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.st_list.SetName("Állomások listája")
        for i, (t, w) in enumerate((("Név", 430), ("Ország", 170),
                                    ("Minőség", 150))):
            self.st_list.InsertColumn(i, t, width=w)
        self.st_list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.st_list.Bind(wx.EVT_CONTEXT_MENU, self._on_list_menu)
        self.st_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                          lambda e: self._play(self._selected()))
        v.Add(self.st_list, 3, wx.EXPAND | wx.ALL, 8)

        self.now_label = wx.StaticText(p, label="Most nem szól semmi.")
        self.now_label.SetName("Lejátszás állapota")
        v.Add(self.now_label, 0, wx.LEFT | wx.BOTTOM, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Le&játszás", lambda e: self._play(self._selected())),
                          ("&Szünet / folytatás", lambda e: self._toggle()),
                          ("&Leállítás", lambda e: self._stop()),
                          ("Hangerő −", lambda e: self._vol(-0.05)),
                          ("Hangerő +", lambda e: self._vol(0.05)),
                          ("Né&mítás be/ki (Ctrl+M)",
                           lambda e: self._toggle_mute()),
                          ("&Kedvenc", lambda e: self._fav_selected())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 6)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        rec = wx.BoxSizer(wx.HORIZONTAL)
        self.rec_btn = wx.Button(p, label="&Felvétel most (F9)")
        self.rec_btn.Bind(wx.EVT_BUTTON, lambda e: self._record_now())
        b_sched = wx.Button(p, label="&Időzített felvétel… (Ctrl+R)")
        b_sched.Bind(wx.EVT_BUTTON, lambda e: self._schedule_dialog())
        b_recs = wx.Button(p, label="Fel&vételek kezelése… (Ctrl+Shift+F)")
        b_recs.Bind(wx.EVT_BUTTON, lambda e: self._recordings_dialog())
        for b in (self.rec_btn, b_sched, b_recs):
            rec.Add(b, 0, wx.RIGHT, 6)
        v.Add(rec, 0, wx.LEFT | wx.BOTTOM, 8)

        # saját állomás + közösségi megosztás
        own = wx.BoxSizer(wx.HORIZONTAL)
        b_own = wx.Button(p, label="Saját á&llomás hozzáadása…")
        b_own.Bind(wx.EVT_BUTTON, lambda e: self._add_custom())
        b_share = wx.Button(p, label="Meg&osztás a közösséggel…")
        b_share.Bind(wx.EVT_BUTTON, lambda e: self._share_selected())
        own.Add(b_own, 0, wx.RIGHT, 6)
        own.Add(b_share, 0)
        v.Add(own, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="Ke&dvencek (Enter: lejátszás, "
              "Delete: törlés):"), 0, wx.LEFT, 8)
        self.fav_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.fav_list.SetName("Kedvenc állomások")
        self.fav_list.InsertColumn(0, "Név", width=430)
        self.fav_list.InsertColumn(1, "Ország", width=170)
        self.fav_list.Bind(wx.EVT_KEY_DOWN, self._on_fav_key)
        self.fav_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                           lambda e: self._play(self._fav_selected_station()))
        v.Add(self.fav_list, 2, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

        # gyorsbillentyűk (nem ütköznek a listák fel/le nyilával)
        ids = {k: wx.NewIdRef() for k in
               ("volup", "voldown", "stop", "pause", "play", "help", "fav",
                "rec", "sched", "recs", "mute")}
        self.Bind(wx.EVT_MENU, lambda e: self._vol(0.05), id=ids["volup"])
        self.Bind(wx.EVT_MENU, lambda e: self._vol(-0.05), id=ids["voldown"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), id=ids["pause"])
        self.Bind(wx.EVT_MENU, lambda e: self._play(self._selected()),
                  id=ids["play"])
        self.Bind(wx.EVT_MENU, lambda e: self._fav_selected(), id=ids["fav"])
        self.Bind(wx.EVT_MENU, lambda e: self._help(), id=ids["help"])
        self.Bind(wx.EVT_MENU, lambda e: self._record_now(), id=ids["rec"])
        self.Bind(wx.EVT_MENU, lambda e: self._schedule_dialog(),
                  id=ids["sched"])
        self.Bind(wx.EVT_MENU, lambda e: self._recordings_dialog(),
                  id=ids["recs"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle_mute(), id=ids["mute"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, wx.WXK_UP, ids["volup"]),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, ids["voldown"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_CTRL, wx.WXK_SPACE, ids["pause"]),
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["play"]),
            (wx.ACCEL_CTRL, ord('D'), ids["fav"]),
            (wx.ACCEL_CTRL, ord('M'), ids["mute"]),
            (wx.ACCEL_NORMAL, wx.WXK_F9, ids["rec"]),
            (wx.ACCEL_CTRL, ord('R'), ids["sched"]),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('F'), ids["recs"]),
            (wx.ACCEL_NORMAL, wx.WXK_F1, ids["help"]),
        ]))

    # ---- segédek ------------------------------------------------------

    @staticmethod
    def _from_rec(r: dict) -> R.Station:
        return R.Station(name=r.get("name", ""), url=r.get("url", ""),
                         codec=r.get("codec", ""), bitrate=r.get("bitrate", 0),
                         country=r.get("country", ""), tags=r.get("tags", ""),
                         uuid=r.get("uuid", ""))

    @staticmethod
    def _to_rec(s: R.Station) -> dict:
        return {"name": s.name, "url": s.url, "codec": s.codec,
                "bitrate": s.bitrate, "country": s.country, "tags": s.tags,
                "uuid": s.uuid}

    def _announce(self, text):
        if self._closing:
            return
        self.SetStatusText(text)
        self.now_label.SetLabel(text)
        # vakon a státuszsor/címke változását a képernyőolvasó nem olvassa fel
        # magától – ezért HANGOSAN is bemondjuk. Előbb az app SelfVoice-a (ha be
        # van kapcsolva), különben a rendszer-TTS (SAPI) – így akkor sem NÉMA,
        # ha a SelfVoice ki van kapcsolva (alapból az). Enélkül a felvétel-gomb
        # „nem reagál" hatását kelti, pedig csak nem hallható a válasza.
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
                return
            except Exception:
                pass
        if self._sapi is None:
            try:
                from superdl.speech import Speaker
                sp = Speaker()
                self._sapi = sp if getattr(sp, "available", False) else False
            except Exception:
                self._sapi = False
        if self._sapi:
            try:
                self._sapi.speak(text)
            except Exception:
                pass

    def _selected(self) -> R.Station | None:
        i = self.st_list.GetFirstSelected()
        return self.stations[i] if 0 <= i < len(self.stations) else None

    def _fav_selected_station(self) -> R.Station | None:
        i = self.fav_list.GetFirstSelected()
        return self.favorites[i] if 0 <= i < len(self.favorites) else None

    # ---- keresés ------------------------------------------------------

    def _on_search(self):
        q = self.search_entry.GetValue().strip()
        if not q:
            return
        by = {0: "name", 1: "tag"}[self.by_choice.GetSelection()]
        self._fetch(lambda: R.search(q, by=by), f"„{q}”")

    def _on_top(self):
        self._fetch(R.top, "népszerű állomások")

    # ---- ország szerinti böngészés ------------------------------------

    def _saved_country_code(self) -> str:
        s = getattr(self.main, "settings", None)
        return (s.get("radio_country") if isinstance(s, dict) else "") or "HU"

    def _load_countries(self):
        """Az országlista betöltése a háttérben, az utolsó (vagy magyar)
        ország kiválasztásával."""
        def work():
            try:
                cs = R.countries()
            except Exception:
                cs = []
            wx.CallAfter(self._countries_ready, cs)

        threading.Thread(target=work, daemon=True).start()

    def _countries_ready(self, cs):
        self.countries = cs
        if not cs:
            self.country_choice.Set(["(nem sikerült betölteni)"])
            return
        self.country_choice.Set([f"{c.name} ({c.count})" for c in cs])
        want = self._saved_country_code()
        idx = next((i for i, c in enumerate(cs) if c.code == want), 0)
        self.country_choice.SetSelection(idx)
        self.country_choice.Enable()

    def _on_country_top(self):
        if not self.countries:
            self._announce("Az országlista még töltődik, próbáld kicsit "
                           "később.")
            return
        i = self.country_choice.GetSelection()
        if not (0 <= i < len(self.countries)):
            return
        self._cur_country = self.countries[i]
        self._country_limit = 50
        s = getattr(self.main, "settings", None)        # utolsó ország mentése
        if isinstance(s, dict):
            s["radio_country"] = self._cur_country.code
        self._fetch_country()

    def _on_country_more(self):
        if self._cur_country:
            self._country_limit += 50
            self._fetch_country()

    def _fetch_country(self):
        c = self._cur_country
        self.b_country_more.Disable()
        self._fetch(lambda: R.by_country_code(c.code, self._country_limit),
                    f"{c.name} – legnépszerűbb állomások",
                    on_done=lambda res: self.b_country_more.Enable(
                        len(res) >= self._country_limit))

    def _fetch(self, fn, label, on_done=None):
        self.SetStatusText(f"Keresés: {label} …")

        def work():
            ok, netmsg = _net_ok("a rádióállomások kereséséhez")
            if not ok:                       # nincs net → hangosan jelez
                wx.CallAfter(self._announce, netmsg)
                return
            try:
                res = fn()
            except Exception as e:
                from superdl import media
                wx.CallAfter(self._announce, media.friendly_error(str(e)))
                return
            wx.CallAfter(self._show, res, label)
            if on_done:
                wx.CallAfter(on_done, res)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, res, label):
        self.stations = res
        self.st_list.DeleteAllItems()
        for s in res:
            row = self.st_list.InsertItem(self.st_list.GetItemCount(), s.name)
            self.st_list.SetItem(row, 1, s.country)
            self.st_list.SetItem(row, 2, s.quality())
        self.SetStatusText(f"{len(res)} állomás – {label}.")
        if res:
            self.st_list.Select(0)
            self.st_list.Focus(0)
            self.st_list.SetFocus()

    # ---- lejátszás ----------------------------------------------------

    def _play(self, st: R.Station | None):
        if not st:
            return
        self._cur = st
        self._announce(f"Csatlakozás: {st.name} …")

        def go():                            # a net-ellenőrzés ne fagyassza a GUI-t
            ok, msg = _net_ok("a rádió hallgatásához")
            if not ok:                       # nincs net → hangosan jelez
                wx.CallAfter(self._announce, msg)
                return
            wx.CallAfter(self.player.play, st.url, title=st.name)

        threading.Thread(target=go, daemon=True).start()

    def _on_state(self, text):
        if text == "lejátszás" and self._cur:
            self._announce(f"Most szól: {self._cur.name}  "
                           f"(hangerő {round(self.player.volume * 100)}%)")
        elif text.startswith("hiba"):
            self._announce(f"Nem szól: {self._cur.name if self._cur else ''} – "
                           f"{text}. Próbálj másik állomást.")
        elif text == "vége":
            self._announce("Az adás megszakadt.")

    def _toggle(self):
        if not self.player.is_active():
            return
        paused = self.player.toggle_pause()
        self._announce("Szünet." if paused else
                       f"Folytatás: {self._cur.name if self._cur else ''}")

    def _stop(self):
        if self.player.is_active():
            self.player.stop()
            self._announce("Leállítva.")

    def _vol(self, delta):
        self._pre_mute_vol = None        # kézi hangerő-állítás feloldja a némítást
        self.player.set_volume(self.player.volume + delta)
        self._announce(f"Hangerő: {round(self.player.volume * 100)} százalék"
                       + (f" – {self._cur.name}" if self._cur
                          and self.player.is_active() else "."))

    def _toggle_mute(self):
        """A LEJÁTSZÁS némítása/visszahangosítása. Csak a hallgatott hangot
        némítja – a FELVÉTEL (külön ffmpeg-folyamat) ettől függetlenül tovább
        megy, így pl. munkahelyen, időzített felvétel közben elnémítható a rádió
        (Laci kérése). Ctrl+M-mel is."""
        if self._pre_mute_vol is None:
            self._pre_mute_vol = self.player.volume or 0.5   # jelenlegi hangerő
            self.player.set_volume(0.0)
            rec = ""
            if self.rec:
                try:
                    if self.rec.snapshot_active():
                        rec = " A felvétel tovább megy."
                except Exception:
                    pass
            self._announce("Némítva (a hallgatott hang elnémult)." + rec)
        else:
            self.player.set_volume(self._pre_mute_vol)
            self._pre_mute_vol = None
            self._announce(f"Hang vissza: {round(self.player.volume * 100)} "
                           "százalék.")

    # ---- felvétel -----------------------------------------------------

    def _record_now(self):
        """A KIJELÖLT állomás felvételének indítása/leállítása. Egyszerre több
        állomás is felvehető (mindegyiket külön F9-cel indítod/állítod le),
        miközben akár egy másikat hallgatsz."""
        if not self.rec:
            self._announce("A felvétel-kezelő nem érhető el.")
            return
        # az állomás: a keresési lista VAGY a KEDVENCEK kijelöltje, vagy ha
        # egyik sincs, az épp szóló adás. (Eddig csak a keresési listát nézte,
        # ezért a kedvencekből kijelölt állomásnál a gomb „nem csinált semmit".)
        st = self._selected() or self._fav_selected_station() or self._cur
        if not st:
            self._announce("Előbb válassz ki egy állomást a felvételhez – a "
                           "keresési listából vagy a kedvencek közül.")
            return
        # erre az állomásra (URL szerint) fut-e már felvétel? → akkor leállítjuk
        running = [r for r in self.rec.snapshot_active() if r.url == st.url]
        if running:
            utolso = running[-1]
            for r in running:
                r.stop()
            # MONDJUK MEG, HOVÁ MENTETTÜK – a leggyakoribb panasz, hogy „nem
            # találom a felvételt": a fájl a célmappa Rádiófelvételek almappájában
            self._announce(f"Felvétel leállítva és elmentve: {st.name}. "
                           f"A fájl helye: {utolso.path}")
            return
        ok, netmsg = _net_ok("a rádiófelvételhez")   # felvételhez net kell
        if not ok:
            self._announce(netmsg)
            return
        r = self.rec.start_manual(st.name, st.url)
        if r:
            n = len(self.rec.snapshot_active())
            extra = (f" Most {n} felvétel fut egyszerre." if n > 1 else "")
            # MONDJUK MEG a MAPPÁT is, hogy a felhasználó tudja, hova készül
            self._announce(
                f"Felvétel folyamatban: {st.name}.{extra} A fájl ide kerül: "
                f"{r.path.parent}. Leállítás: F9 ezen az állomáson, vagy a "
                "Felvételek kezelése (Ctrl+Shift+F).")
        else:
            self._announce("A felvétel nem indult el – próbáld újra, vagy "
                           "ellenőrizd, hogy az állomás szól-e.")

    def _schedule_dialog(self):
        if not self.rec:
            self._announce("A felvétel-kezelő nem érhető el.")
            return
        # az időzítéshez a KEDVENCEK közül választhatsz (legördülő); így átfedő,
        # párhuzamos időzítések is megadhatók, akár több állomásra
        stations = [(f.name, f.url) for f in self.favorites]
        if not stations:
            st = self._selected() or self._cur
            if not st:
                self._announce("Az időzítéshez előbb tegyél állomásokat a "
                               "kedvencek közé (Ctrl+B), vagy válassz ki egyet "
                               "a listából.")
                return
            stations = [(st.name, st.url)]
        sel = self._selected() or self._cur
        preselect = 0
        if sel:
            preselect = next((i for i, (_n, u) in enumerate(stations)
                              if u == sel.url), 0)
        dlg = ScheduleDialog(self, stations, self.rec, preselect=preselect)
        if dlg.ShowModal() == wx.ID_OK and getattr(dlg, "result", None):
            self.rec.add_schedule(dlg.result)
            self._announce(f"Időzített felvétel mentve: {dlg.result.describe()}")
        dlg.Destroy()

    def _recordings_dialog(self):
        if not self.rec:
            self._announce("A felvétel-kezelő nem érhető el.")
            return
        dlg = RecordingsDialog(self, self.rec)
        dlg.ShowModal()
        dlg.Destroy()

    # ---- listák / kedvencek ------------------------------------------

    def _on_list_key(self, e):
        code, ctrl = e.GetKeyCode(), e.ControlDown()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play(self._selected())
        elif ctrl and code == ord('B'):
            self._fav_selected()
        elif ctrl and code == ord('C'):
            self._copy_url(self._selected())
        else:
            e.Skip()

    def _on_list_menu(self, e):
        if not self._selected():
            return
        m = wx.Menu()
        mp = m.Append(wx.ID_ANY, "Le&játszás\tEnter")
        mf = m.Append(wx.ID_ANY, "&Kedvencekhez\tCtrl+B")
        mu = m.Append(wx.ID_ANY, "&URL másolása\tCtrl+C")
        self.Bind(wx.EVT_MENU, lambda e: self._play(self._selected()), mp)
        self.Bind(wx.EVT_MENU, lambda e: self._fav_selected(), mf)
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(self._selected()), mu)
        self.st_list.PopupMenu(m)
        m.Destroy()

    def _copy_url(self, st):
        if st and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(st.url))
            wx.TheClipboard.Close()
            self._announce(f"URL a vágólapra másolva: {st.url}")

    def _fav_selected(self):
        st = self._selected()
        if not st:
            return
        if any(f.uuid == st.uuid and f.url == st.url for f in self.favorites):
            self._announce("Ez már a kedvencek között van.")
            return
        self.favorites.append(st)
        self._save_fav()
        self._refresh_fav()
        self._announce(f"Kedvencekhez adva: {st.name}")

    def _refresh_fav(self):
        self.fav_list.DeleteAllItems()
        for s in self.favorites:
            row = self.fav_list.InsertItem(self.fav_list.GetItemCount(), s.name)
            self.fav_list.SetItem(row, 1, s.country)

    # ---- saját állomás + közösségi megosztás --------------------------

    def _add_custom(self):
        """Saját állomás (név + URL) → a kedvencek közé, és felajánljuk a
        lejátszást. Így a listában nem szereplő rádiók is hallgathatók (M1)."""
        dlg = CustomStationDialog(self)
        try:
            if dlg.ShowModal() != wx.ID_OK or not dlg.station:
                return
            st = dlg.station
        finally:
            dlg.Destroy()
        if any(f.url == st.url for f in self.favorites):
            self._announce("Ez az URL már a kedvencek között van.")
        else:
            self.favorites.append(st)
            self._save_fav()
            self._refresh_fav()
            self._announce(f"Saját állomás a kedvencekhez adva: {st.name}")
        if wx.MessageBox(f"Lejátsszam most: {st.name}?", "Saját állomás",
                         wx.YES_NO | wx.ICON_QUESTION, self) == wx.YES:
            self._play(st)

    def _share_source(self) -> R.Station | None:
        """A megosztandó állomás: a kedvencek kijelöltje elsőbbséggel (ide
        kerülnek a saját állomások), különben a keresési lista kijelöltje."""
        return self._fav_selected_station() or self._selected()

    def _share_selected(self):
        """A kijelölt állomás beküldése a radio-browser NYILVÁNOS közösségi
        adatbázisába – KIFEJEZETT megerősítés után (M2)."""
        st = self._share_source()
        if not st:
            self._announce("Előbb jelölj ki egy állomást (a kedvencekben vagy "
                           "a listában).")
            return
        msg = (f"Megosztod a radio-browser.info NYILVÁNOS közösségi "
               f"adatbázisában?\n\nÁllomás: {st.name}\nURL: {st.url}\n\n"
               "Így más SuperDL-felhasználók (és bárki) is megtalálja "
               "kereséssel. A beküldés NYILVÁNOS és nem vonható vissza. Csak "
               "SAJÁT, legális, nyilvánosan sugárzott állomást küldj be.")
        if wx.MessageBox(msg, "Megosztás a közösséggel",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                         self) != wx.YES:
            return
        self._announce("Beküldés a radio-browser közösségi adatbázisába…")

        def work():
            try:
                res = R.add_station(st.name, st.url,
                                    country_code=st.country, tags=st.tags)
                ok = bool(res.get("ok")) if isinstance(res, dict) else False
                message = (res.get("message") if isinstance(res, dict)
                           else "") or ""
                uuid = res.get("uuid", "") if isinstance(res, dict) else ""
                wx.CallAfter(self._share_done, ok, message, uuid)
            except Exception as e:
                wx.CallAfter(self._share_done, False, str(e), "")

        threading.Thread(target=work, daemon=True).start()

    def _share_done(self, ok: bool, message: str, uuid: str):
        if ok:
            self._announce(
                "Megosztva! Az állomás beküldve a közösségi adatbázisba"
                + (f" (azonosító: {uuid})." if uuid else ".")
                + " Kis idő múlva keresésre is előjön.")
        else:
            self._announce("A megosztás nem sikerült: "
                           + (message or "ismeretlen hiba") + ".")

    def _save_fav(self):
        store.save_radio_favorites([self._to_rec(f) for f in self.favorites])

    def _on_fav_key(self, e):
        code = e.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play(self._fav_selected_station())
        elif code == wx.WXK_DELETE:
            i = self.fav_list.GetFirstSelected()
            if 0 <= i < len(self.favorites):
                s = self.favorites.pop(i)
                self._save_fav()
                self._refresh_fav()
                self._announce(f"Törölve a kedvencekből: {s.name}")
        else:
            e.Skip()

    # ---- súgó / zárás -------------------------------------------------

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Internetes rádió", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Internetes rádió",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True
        try:
            self.player.stop()
        except Exception:
            pass
        self._save_fav()
        if getattr(self.main, "_radio_win", None) is self:
            self.main._radio_win = None
        e.Skip()
