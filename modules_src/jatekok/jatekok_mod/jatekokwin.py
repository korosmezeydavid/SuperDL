"""Játékok ablak – Retró játékok és SuperDL saját játékok.

Akadálymentes-first: natív wx vezérlők, minden elem címkézett, teljesen
billentyűzetről kezelhető, és minden fontos állapot HALLHATÓ (nem csak a
státuszsorban jelenik meg).
"""

import threading

import wx

from superdl import retrospeech as RS     # a Core SAJÁT formánsszintetizátora
from superdl import store                 # a választott hang megőrzéséhez
from . import brailab                     # az IGAZI BraiLab PC hang (külön motor)
from . import katalogus

_HANG_CFG = "jatekok.json"                 # a felhasználó hang+tempó beállítása


HELP = """JÁTÉKOK

MIRE VALÓ
Akadálymentes játékok két csoportban:
• RETRÓ JÁTÉKOK – a 80-as/90-es évek magyar beszélő gépeinek hangulatában,
  korhű, „gépi” beszédhanggal.
• SUPERDL SAJÁT JÁTÉKOK – a program saját, mai játékai.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. A fülek között Ctrl+Tab-bal válts (Retró játékok / Saját játékok /
   Hangbeállítás).
2. A listában fel/le nyíllal válassz játékot – a program felolvassa a nevét és
   a rövid leírását.
3. Enter vagy az „Indítás” gomb: a játék elindul.
4. A HANGBEÁLLÍTÁS fülön kiválaszthatod a retró hangkaraktert, és a
   „Hangpróba” gombbal meg is hallgathatod, mielőtt játszanál.

GYORSBILLENTYŰK
F1 – ez a súgó.  Ctrl+Tab – fülváltás.  Enter – a kijelölt játék indítása.
F8 – a kijelölt játék leírásának megismétlése.  Escape – hang leállítása.

A RETRÓ HANGRÓL
A hangkarakterek nagy részét a SuperDL SAJÁT formáns-alapú motorja készíti, a
korszak beszédszintézisének akusztikai jellemzői alapján; ezek nem tartalmaznak
és nem használnak fel semmilyen eredeti gépi ROM-ot vagy idegen kódot.

A hanglistában külön szerepel a „BraiLab PC – az IGAZI hang”: ez az EREDETI
BraiLab PC beszédszintetizátor. Nála a hangmagasság, a tempó és a hangerő
saját, fokozatos szabályzóval állítható (a motor csak ezeket a fokozatokat
ismeri), és a hangpróba ugyanúgy működik.

NÉVJEGY – KÖSZÖNET
Hálás köszönettel Ujfalusi Zoltánnak, aki rendelkezésünkre bocsátotta ezt a
hangot!"""


class JatekokFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Játékok", size=(880, 620))
        self.main = main
        self._closing = False       # zárás alatt a háttér-callbackek kilépnek
        self._busy = False
        self._player = None
        # Laci kérése: NE mindig az első hang legyen a modul indulásakor, hanem
        # amit a felhasználó egyszer beállított. A választást a store-ban őrizzük.
        cfg = store.load_json(store.CONFIG_DIR / _HANG_CFG, {})
        # a választható hangok: a Core retró gépei + (ha megvan) az IGAZI BraiLab
        self._hangok = [(g.kulcs, g.nev) for g in RS.GEPEK]
        if brailab.elerheto():
            self._hangok.append((brailab.KULCS, brailab.NEV))
        kulcsok = [k for k, _ in self._hangok]
        self._hang = cfg.get("hang") if cfg.get("hang") in kulcsok else RS.ALAP_GEP
        # a BraiLab FOKOZATAI (a motor csak szűk tartományt ismer)
        self._bl_magassag = brailab.hatarol(cfg.get("brailab_magassag", 0),
                                            brailab.MAGASSAGOK, 0)
        self._bl_tempo = brailab.hatarol(cfg.get("brailab_tempo", 4),
                                         brailab.TEMPOK, 4)
        self._bl_hangero = brailab.hatarol(cfg.get("brailab_hangero", 0),
                                           brailab.HANGEROK, 0)
        self._tempo_szazalek = int(cfg.get("tempo") or 100)
        if not 50 <= self._tempo_szazalek <= 160:
            self._tempo_szazalek = 100
        self._tempo = 100.0 / self._tempo_szazalek   # a beszéd időtartam-szorzója
        self._retro_hang = bool(cfg.get("retro_hang", False))   # ALAPBÓL KI
        self._sapi = None            # rendszer-TTS tartalék (lusta)

        self._build()
        self.CreateStatusBar()
        self._announce("Válassz játékot a listából. Fülváltás: Ctrl+Tab. "
                       "Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        self.nb = wx.Notebook(self)
        self._lista_retro = self._build_lista(
            "Retró játékok", katalogus.RETRO,
            "A 80-as/90-es évek hangulatában, korhű beszédhanggal.")
        self._lista_sajat = self._build_lista(
            "Saját játékok", katalogus.SAJAT,
            "A SuperDL saját, mai akadálymentes játékai.")
        self._build_hang()

    def _build_lista(self, cim, tetelek, alcim):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=alcim), 0, wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Játékok (fel/le nyíl, Enter: indítás):"),
              0, wx.LEFT, 8)
        lst = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        lst.SetName(f"{cim} listája")
        lst.InsertColumn(0, "Játék", width=260)
        lst.InsertColumn(1, "Miről szól", width=520)
        for j in tetelek:
            r = lst.InsertItem(lst.GetItemCount(), j.nev)
            lst.SetItem(r, 1, j.leiras)
        if tetelek:
            lst.Select(0)
            lst.Focus(0)
        lst.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._indit())
        lst.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: self._kijelolve())
        v.Add(lst, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="&Indítás")
        b.Bind(wx.EVT_BUTTON, lambda e: self._indit())
        sor.Add(b, 0, wx.RIGHT, 6)
        b2 = wx.Button(p, label="&Leírás felolvasása (F8)")
        b2.Bind(wx.EVT_BUTTON, lambda e: self._felolvas_leiras())
        sor.Add(b2, 0, wx.RIGHT, 6)
        b3 = wx.Button(p, label="Hang leállí&tása")
        b3.Bind(wx.EVT_BUTTON, lambda e: self._hang_stop())
        sor.Add(b3, 0)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.nb.AddPage(p, cim)
        lst._tetelek = tetelek           # a laphoz tartozó katalógus
        return lst

    def _build_hang(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=
              "Itt választhatod ki, milyen hangon szóljanak a retró játékok."),
              0, wx.ALL, 8)
        # A retró hang ALAPBÓL KIKAPCSOLVA; itt (vagy magában a játékban)
        # bekapcsolható, és a választás megmarad. Aki képernyőolvasót használ,
        # az alaphelyzetben azzal hallgatja a játékokat.
        self.retro_be = wx.CheckBox(
            p, label="&Retró hang beszéljen a retró játékokban "
                     "(alapból kikapcsolva)")
        self.retro_be.SetValue(bool(self._retro_hang))
        self.retro_be.Bind(wx.EVT_CHECKBOX, lambda e: self._retro_be_valt())
        v.Add(self.retro_be, 0, wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Hangkarakter (fel/le nyíl):"), 0,
              wx.LEFT, 8)
        self.hang_lst = wx.ListBox(
            p, choices=[nev for _, nev in self._hangok], style=wx.LB_SINGLE)
        self.hang_lst.SetName("Retró hangkarakter")
        kulcsok = [k for k, _ in self._hangok]
        self.hang_lst.SetSelection(kulcsok.index(self._hang)
                                   if self._hang in kulcsok else 0)
        self.hang_lst.Bind(wx.EVT_LISTBOX, lambda e: self._hang_valaszt())
        v.Add(self.hang_lst, 0, wx.EXPAND | wx.ALL, 8)

        # A BraiLab hangot Ujfalusi Zoltán bocsátotta a rendelkezésünkre – ez a
        # köszönet a felületen IS ott van, nem csak a súgóban.
        if brailab.elerheto():
            kosz = wx.StaticText(
                p, label="Hálás köszönettel Ujfalusi Zoltánnak, aki "
                         "rendelkezésünkre bocsátotta ezt a hangot!")
            kosz.SetName("Köszönet a BraiLab hangért")
            v.Add(kosz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # --- a SAJÁT retró motor tempója (százalék) ---
        self.tempo_cim = wx.StaticText(
            p, label="&Beszédtempó (nagyobb = gyorsabb):")
        v.Add(self.tempo_cim, 0, wx.LEFT, 8)
        self.tempo_cs = wx.Slider(p, value=self._tempo_szazalek,
                                  minValue=50, maxValue=160,
                                  style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.tempo_cs.SetName("Beszédtempó százalékban")
        self.tempo_cs.Bind(wx.EVT_SLIDER, lambda e: self._tempo_valaszt())
        v.Add(self.tempo_cs, 0, wx.EXPAND | wx.ALL, 8)

        # --- a BraiLab SAJÁT fokozatai (a motor csak ezeket ismeri) ---
        # Amikor nem a BraiLab a választott hang, ezek REJTVE vannak (nem
        # letiltva): így a tabulátor-sorrend sem visz üresbe.
        self.bl_elemek = []
        if brailab.elerheto():
            self.bl_mag_cim = wx.StaticText(p, label="BraiLab hang&magasság:")
            v.Add(self.bl_mag_cim, 0, wx.LEFT, 8)
            self.bl_mag = wx.Choice(p, choices=["Mély", "Alap", "Magas"])
            self.bl_mag.SetName("BraiLab hangmagasság")
            self.bl_mag.SetSelection(brailab.MAGASSAGOK.index(self._bl_magassag))
            self.bl_mag.Bind(wx.EVT_CHOICE, lambda e: self._bl_valaszt())
            v.Add(self.bl_mag, 0, wx.ALL, 8)

            self.bl_tempo_cim = wx.StaticText(
                p, label="BraiLab &tempó (0 a leglassabb, 5 a leggyorsabb):")
            v.Add(self.bl_tempo_cim, 0, wx.LEFT, 8)
            self.bl_tempo_v = wx.Choice(
                p, choices=["0 – leglassabb", "1", "2", "3", "4 – alap",
                            "5 – leggyorsabb"])
            self.bl_tempo_v.SetName("BraiLab tempó")
            self.bl_tempo_v.SetSelection(brailab.TEMPOK.index(self._bl_tempo))
            self.bl_tempo_v.Bind(wx.EVT_CHOICE, lambda e: self._bl_valaszt())
            v.Add(self.bl_tempo_v, 0, wx.ALL, 8)

            self.bl_ero_cim = wx.StaticText(p, label="BraiLab hang&erő:")
            v.Add(self.bl_ero_cim, 0, wx.LEFT, 8)
            self.bl_ero = wx.Choice(p, choices=["Halk", "Alap", "Hangos"])
            self.bl_ero.SetName("BraiLab hangerő")
            self.bl_ero.SetSelection(brailab.HANGEROK.index(self._bl_hangero))
            self.bl_ero.Bind(wx.EVT_CHOICE, lambda e: self._bl_valaszt())
            v.Add(self.bl_ero, 0, wx.ALL, 8)
            self.bl_elemek = [self.bl_mag_cim, self.bl_mag, self.bl_tempo_cim,
                              self.bl_tempo_v, self.bl_ero_cim, self.bl_ero]

        v.Add(wx.StaticText(p, label="&Próbaszöveg:"), 0, wx.LEFT, 8)
        self.proba_txt = wx.TextCtrl(
            p, value="Üdvözöllek a Super D L retro játékok menüjében!")
        self.proba_txt.SetName("Próbaszöveg a hangpróbához")
        v.Add(self.proba_txt, 0, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Hang&próba")
        b.Bind(wx.EVT_BUTTON, lambda e: self._hangproba())
        sor.Add(b, 0, wx.RIGHT, 6)
        b2 = wx.Button(p, label="Hang leállí&tása")
        b2.Bind(wx.EVT_BUTTON, lambda e: self._hang_stop())
        sor.Add(b2, 0)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.nb.AddPage(p, "Hangbeállítás")
        self._hang_vezerlok()          # a választott hanghoz tartozó szabályzók

    # ---- akadálymentes visszajelzés -----------------------------------

    def _announce(self, text, beszel=False):
        """Státuszsor + (fontos állapotnál) AKTÍV bemondás. A státuszsor
        változását a képernyőolvasó nem feltétlenül mondja be."""
        if self._closing:
            return
        self.SetStatusText(text)
        if beszel:
            self._beszel(text)

    def _beszel(self, text):
        """Megbízhatóan HALLHATÓ bemondás. ELŐBB a FUTÓ képernyőolvasó (Tolk) –
        a felhasználó saját, magyar hangján; ha nincs, az app SelfVoice-a, végül
        a rendszer-TTS (SAPI)."""
        try:
            from superdl import screenreader
            if screenreader.speak(text):
                return
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
                return
            except Exception:
                pass
        sp = self._sapi_hang()
        if sp is not None:
            try:
                sp.speak(text)
            except Exception:
                pass

    def _sapi_hang(self):
        if self._sapi is None:
            try:
                from superdl.speech import Speaker
                sp = Speaker()
                self._sapi = sp if getattr(sp, "available", False) else False
            except Exception:
                self._sapi = False
        return self._sapi or None

    # ---- kijelölés / leírás -------------------------------------------

    def _aktiv_lista(self):
        i = self.nb.GetSelection()
        if i == 0:
            return self._lista_retro
        if i == 1:
            return self._lista_sajat
        return None

    def _kijelolt(self):
        lst = self._aktiv_lista()
        if lst is None:
            return None
        i = lst.GetFirstSelected()
        tetelek = getattr(lst, "_tetelek", [])
        return tetelek[i] if 0 <= i < len(tetelek) else None

    def _kijelolve(self):
        j = self._kijelolt()
        if j:
            self._announce(f"{j.nev}. {j.leiras}")

    def _felolvas_leiras(self):
        j = self._kijelolt()
        if not j:
            self._announce("Előbb válassz játékot a listából.", beszel=True)
            return
        self._retro_mond(f"{j.nev}. {j.leiras}")

    # ---- retró hang ---------------------------------------------------

    def _brailab_e(self) -> bool:
        """Az IGAZI BraiLab motor a választott hang?"""
        return self._hang == brailab.KULCS

    def _hang_vezerlok(self):
        """A választott hanghoz tartozó szabályzókat MUTATJUK, a többit REJTJÜK
        (nem letiltjuk – így a tabulátor sem visz használhatatlan elemre)."""
        bl = self._brailab_e()
        for w in (self.tempo_cim, self.tempo_cs):
            w.Show(not bl)
        for w in self.bl_elemek:
            w.Show(bl)
        try:
            self.tempo_cs.GetParent().Layout()
        except Exception:
            pass

    def _hang_valaszt(self):
        i = self.hang_lst.GetSelection()
        if 0 <= i < len(self._hangok):
            self._hang, nev = self._hangok[i]
            self._save_hang_cfg()
            self._hang_vezerlok()
            if self._brailab_e():
                # a fokozatokat MINDIG rátoltjuk a motorra, ha ő szól
                brailab.motor().beallit(self._bl_magassag, self._bl_tempo,
                                        self._bl_hangero)
            self._announce(f"Hangkarakter: {nev}", beszel=True)

    def _bl_valaszt(self):
        """A BraiLab fokozatainak állítása (magasság, tempó, hangerő)."""
        self._bl_magassag = brailab.MAGASSAGOK[max(0, self.bl_mag.GetSelection())]
        self._bl_tempo = brailab.TEMPOK[max(0, self.bl_tempo_v.GetSelection())]
        self._bl_hangero = brailab.HANGEROK[max(0, self.bl_ero.GetSelection())]
        self._save_hang_cfg()
        jo = brailab.motor().beallit(self._bl_magassag, self._bl_tempo,
                                    self._bl_hangero)
        szoveg = ("BraiLab: magasság %s, tempó %d, hangerő %s."
                  % (self.bl_mag.GetStringSelection(), self._bl_tempo,
                     self.bl_ero.GetStringSelection()))
        if not jo:
            szoveg += " A motor nem fogadta el mindegyik fokozatot."
        self._announce(szoveg, beszel=True)

    def _tempo_valaszt(self):
        # a csúszka „sebesség %", ebből lesz az időtartam-szorzó (nagyobb
        # sebesség = rövidebb idő = gyorsabb beszéd)
        szazalek = max(50, self.tempo_cs.GetValue())
        self._tempo_szazalek = szazalek
        self._tempo = 100.0 / szazalek
        self._save_hang_cfg()
        self._announce(f"Beszédtempó: {szazalek} százalék.", beszel=True)

    def _save_hang_cfg(self):
        """A választott hang + tempó + retró-hang kapcsoló megőrzése a következő
        indításig. MERGE (nem felülírás), hogy a játékban állított retró-hang
        választás se vesszen el."""
        try:
            p = store.CONFIG_DIR / _HANG_CFG
            cfg = store.load_json(p, {})
            cfg["hang"] = self._hang
            cfg["tempo"] = self._tempo_szazalek
            cfg["retro_hang"] = bool(self._retro_hang)
            cfg["brailab_magassag"] = self._bl_magassag
            cfg["brailab_tempo"] = self._bl_tempo
            cfg["brailab_hangero"] = self._bl_hangero
            store.save_json(p, cfg)
        except Exception:
            pass

    def _retro_be_valt(self):
        self._retro_hang = self.retro_be.GetValue()
        self._save_hang_cfg()
        self._announce("A retró hang mostantól "
                       + ("bekapcsolva." if self._retro_hang
                          else "kikapcsolva; a képernyőolvasó beszél."),
                       beszel=True)

    def _hangproba(self):
        szoveg = self.proba_txt.GetValue().strip()
        if not szoveg:
            self._announce("Írj be próbaszöveget.", beszel=True)
            return
        self._retro_mond(szoveg)

    def _retro_mond(self, szoveg: str):
        """A szöveg megszólaltatása a választott hangon, háttérben."""
        if self._brailab_e():
            # A BraiLab MAGA szólal meg (nincs WAV-készítés), ezért nincs
            # „hang készítése" fázis sem – csak elindítjuk.
            m = brailab.motor()
            m.beallit(self._bl_magassag, self._bl_tempo, self._bl_hangero)
            if not m.mond(szoveg):
                self._announce("A BraiLab hang nem szólalt meg"
                               + (f": {m.hiba}" if m.hiba else "."), beszel=True)
                return
            self._announce("Szól a BraiLab hang. Leállítás: Escape.")
            return
        if self._busy:
            self._announce("Egy hang már készül, várd meg a végét.")
            return
        if not RS.available():
            self._announce("A retró hanghoz szükséges beszédmotor nem érhető "
                           "el ezen a gépen.", beszel=True)
            return
        self._busy = True
        self._announce("Hang készítése…")
        hang = self._hang
        tempo = self._tempo

        def work():
            try:
                try:
                    path = RS.synth(szoveg, "", hang, tempo_szorzo=tempo)
                except TypeError:
                    # régebbi Core: nincs tempo_szorzo – tempó nélkül, de NEM néma
                    path = RS.synth(szoveg, "", hang)
            except Exception as e:
                wx.CallAfter(self._hang_kesz, "", str(e))
                return
            wx.CallAfter(self._hang_kesz, path, "")

        threading.Thread(target=work, daemon=True).start()

    def _hang_kesz(self, path, hiba):
        if self._closing:
            return
        self._busy = False
        if hiba:
            self._announce(f"A hang nem készült el: {hiba}", beszel=True)
            return
        try:
            if self._player is None:
                from superdl.audioengine import Player
                self._player = Player()
            self._player.play(path, "")
            self._announce("Szól a retró hang. Leállítás: Escape.")
        except Exception as e:
            self._announce(f"A lejátszás nem sikerült: {e}", beszel=True)

    def _hang_stop(self):
        try:
            if self._player:
                self._player.stop()
        except Exception:
            pass
        try:
            brailab.motor().stop()      # a BraiLab a saját motorján szól
        except Exception:
            pass
        self._announce("Hang leállítva.")

    # ---- játék indítása ------------------------------------------------

    def _indit(self):
        j = self._kijelolt()
        if not j:
            self._announce("Előbb válassz játékot a listából.", beszel=True)
            return
        from .jatekkonzol import indithato, indit_jatek
        if not indithato(j.kulcs):
            # A keretrendszer kész, a játék maga még nem – ezt MEGMONDJUK,
            # nem teszünk úgy, mintha elindult volna.
            self._announce(
                f"A(z) „{j.nev}” még készül – hamarosan játszható lesz.",
                beszel=True)
            return
        if self._brailab_e():
            # a mentett fokozatok akkor is érvényesüljenek, ha a felhasználó
            # most nem járt a Hangbeállítás fülön
            brailab.motor().beallit(self._bl_magassag, self._bl_tempo,
                                    self._bl_hangero)
        try:
            indit_jatek(self, j, lambda: (self._hang, self._tempo))
        except Exception as e:
            self._announce(f"A játék nem indult el: {e}", beszel=True)

    # ---- súgó / billentyűk / zárás -------------------------------------

    def _on_key(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_F1:
            self._help()
        elif k == wx.WXK_F8:
            self._felolvas_leiras()
        elif k == wx.WXK_ESCAPE:
            self._hang_stop()
        else:
            e.Skip()

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Játékok", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Játékok",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True
        try:
            if self._player:
                self._player.stop()
        except Exception:
            pass
        try:
            brailab.motor().leallit()   # a 32 bites kísérő-folyamat is záruljon
        except Exception:
            pass
        if getattr(self.main, "_jatekok_win", None) is self:
            self.main._jatekok_win = None
        e.Skip()
