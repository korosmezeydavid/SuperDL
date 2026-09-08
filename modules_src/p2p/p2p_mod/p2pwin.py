"""Gépről gépre fájlküldés ablak: két gomb (Küldök / Fogadok) és egy könnyen
bemondható szó-kód. A tényleges átvitelt a p2p modul (magic-wormhole) végzi.
"""

from pathlib import Path

import wx
import wx.adv

from . import csomag, feltoltes, megosztas, p2p, tarhely


HELP = """FÁJL- ÉS MAPPAKÜLDÉS, MEGOSZTÁS

MIRE VALÓ
Fájl VAGY MAPPA eljuttatása valaki máshoz. Két út van, és a különbség köztük
nem a méret, hanem hogy a másik fél ott van-e MOST a gépénél:

1. GÉPRŐL GÉPRE (kóddal) – ha ott van. Nincs méretkorlát, senki máshoz nem
   kerül, és végpontok között titkosítva megy. Ez a biztonságos út.
2. IDEIGLENES TÁRHELY – ha nincs ott. Feltöltöm, kapsz egy linket, és azt
   elküldheted neki bármikor. FIGYELEM: a linket bárki használhatja, aki
   megkapja, mert nincs rajta jelszó. Iratot, orvosi papírt, jelszót ne így
   küldj – arra ott az első út.

MAPPA KÜLDÉSE
A „Mappa küldése" gombbal. A program megkérdezi, milyen formátumba csomagolja
(ZIP mindenhova jó; tar.gz akkor, ha Linuxra vagy Macre küldöd), bemondja, hány
fájl és mekkora, majd csomagolás közben mondja a százalékot. Az Escape leállítja
– ilyenkor a félkész csomagot kitörlöm. A küldés után megkérdezem, megtartsam-e
a csomagot vagy töröljem.

JELSZÓ NINCS – ÉS EZ TUDATOS
A csomagra nem teszünk jelszót. Az erős, jelszavas zipet a Windows saját
Intézője nem nyitja meg (a címzett érthetetlen hibát kapna), a régi, mindenhol
nyíló megoldás pedig gyenge – egy gyenge titkosítás pedig rosszabb a semminél,
mert biztonságérzetet ad. Ha titkot küldesz, használd a gépről gépre utat: az
eleve titkosít.

MEGOSZTÁSI ELŐZMÉNYEK
Amit tárhelyre töltöttél, bekerül az előzményekbe – elöl, ami hamarabb lejár,
emberi idővel („még két nap és négy óra"). Innen a link a vágólapra tehető,
betűzve felolvastatható, és ahol a szolgáltató engedi, a feltöltés vissza is
vonható. A lejárt sorok még egy napig látszanak: ha valaki azt mondja, hogy nem
működik a tegnapi link, itt találod meg a választ.

LÉPÉSRŐL LÉPÉSRE (vakon is)
KÜLDÉS:
1. „Fájl küldése" vagy „Mappa küldése" gomb.
2. A program ad egy KÓDOT a „küldés kódja" mezőben – a képernyőolvasó felolvassa.
   Mondd be ezt a kódot a másik félnek (telefonon, üzenetben).
3. Várd meg, míg a másik beírja a kódot. A program jelzi (felolvasva), amikor a
   fájl megérkezett.
FOGADÁS:
1. A másiktól kapott kódot írd be a „fogadás kódja" mezőbe.
2. „Fogadás" gomb – a program megkérdezi, hova mentse, és letölti.

GYORSBILLENTYŰK
F1 – súgó.  F8 – hány százaléknál tart a küldés/fogadás (bemondva).
Tab / Shift+Tab – mozgás a vezérlők közt.  Enter – gomb.

TIPPEK
- A kódot pontosan úgy add meg, ahogy hallottad (kötőjelekkel, kis/nagybetű nem
  számít).
- Mindkét gépnek internet kell. A fájl tartalma VÉGPONTOK KÖZÖTT TITKOSÍTVA
  megy: csak a te géped és a másik gép tudja elolvasni. A kapcsolat felvételéhez
  a program egy nyilvános találkozó-szolgáltatást használ, és ha a két gép
  tűzfal/NAT miatt nem éri el egymást közvetlenül, a titkosított adat egy
  továbbító szerveren keresztül halad. A tartalmat így SEM láthatja senki más,
  de az adat útja nem minden esetben közvetlen.
- A küldési kód EGYSZER használatos titok: aki megkapja, letöltheti a fájlt.
  Az F8 újra elmondja; az átvitel végén és az ablak bezárásakor a program
  törli a vágólapról.
- Ha egy küldés/fogadás közben be akarod zárni az ablakot, a program RÁKÉRDEZ,
  nehogy véletlenül megszakítsd az átvitelt.
- Menet közben az F8-cal bármikor megkérdezheted, hány százaléknál tart."""


# Az utoljára megnyitott ablak – ezen keresztül tud a menü EGYENESEN a
# mappaküldésbe ugrani, anélkül hogy a Core-nak bármit tudnia kellene róla.
_utolso_ablak = None


def mappa_kuldes_inditasa():
    """A „Mappa küldése és megosztás" menüpont belépője.

    A `wx.CallAfter` azért kell, mert az ablak megnyitása után a felület még
    nem állt össze; a mappaválasztó egy fél lépéssel később nyílhat csak ki."""
    ablak = _utolso_ablak
    if ablak is not None:
        wx.CallAfter(ablak._on_send_folder)


class P2PFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Fájl- és mappaküldés, megosztás",
                         size=(720, 620))
        self.main = main
        global _utolso_ablak
        _utolso_ablak = self
        self.send_session = None
        self.recv_session = None
        self._send_name = ""             # a küldött fájl neve a visszaigazoláshoz
        self._csomag_takarit = None      # ideiglenes csomag: a végén kérdezünk róla
        self._closing = False            # zárás alatt a háttér-callbackek ne nyúljanak hozzánk
        self._send_pct = -1              # utolsó ismert haladás (küldés/fogadás)
        self._recv_pct = -1
        self._beeper = None              # hallható haladás-pittyegés (Core)
        self._mondott_pct = {}           # irány → utoljára BEMONDOTT 25%-lépcső

        self._build()
        self.CreateStatusBar()
        self.SetStatusText("Küldéshez: Fájl kiválasztása. Fogadáshoz: írd be a "
                           "küldőtől kapott kódot. Súgó: F1. Haladás: F8.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_help_key)

    def _on_help_key(self, e):
        code = e.GetKeyCode()
        if code == wx.WXK_F1:
            self._help()
        elif code == wx.WXK_F8:
            self._announce_progress()
        else:
            e.Skip()

    def _speak(self, text):
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

    def _announce_progress(self):
        """F8: bemondja, hány százaléknál tart az épp folyó küldés/fogadás."""
        if self.send_session and self._send_pct >= 0:
            msg = f"Küldés: {self._send_pct} százalék."
        elif self.send_session:
            msg = "Küldés folyamatban; a másik gép még nem kezdte el letölteni."
        elif self.recv_session and self._recv_pct >= 0:
            msg = f"Fogadás: {self._recv_pct} százalék."
        elif self.recv_session:
            msg = "Fogadás folyamatban; a kapcsolat épül."
        else:
            msg = "Most nincs folyamatban küldés vagy fogadás."
        self.SetStatusText(msg)
        self._speak(msg)

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Fájlküldés gépről gépre", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Fájlküldés",
                          wx.OK | wx.ICON_INFORMATION, self)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        v.Add(wx.StaticText(p, label=(
            "Nagy fájlt is egyszerűen küldhetsz egy másik gépre felhő nélkül. "
            "A küldő kap egy rövid, bemondható kódot (pl. 7-alma-traktor); a "
            "fogadó beírja ugyanazt, és a fájl titkosítva, gépről gépre megy "
            "át.")), 0, wx.ALL, 10)

        # --- KÜLDÉS ---
        sb1 = wx.StaticBoxSizer(wx.StaticBox(p, label="Küldés"), wx.VERTICAL)
        self.send_btn = wx.Button(p, label="&Fájl küldése…")
        self.send_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_send())
        sb1.Add(self.send_btn, 0, wx.ALL, 6)
        # ÚJ (2026-09-06): mappa küldése. Eddig csak EGYETLEN fájlt lehetett —
        # a felhasználók jogosan kérték, hogy ami Androidon megy, az itt is.
        self.folder_btn = wx.Button(p, label="&Mappa küldése…")
        self.folder_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_send_folder())
        sb1.Add(self.folder_btn, 0, wx.ALL, 6)
        self.share_btn = wx.Button(
            p, label="Feltöltés &ideiglenes tárhelyre…")
        self.share_btn.SetName("Feltöltés ideiglenes tárhelyre, ha a másik "
                               "fél nincs most a gépénél")
        self.share_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_share())
        sb1.Add(self.share_btn, 0, wx.ALL, 6)
        self.hist_btn = wx.Button(p, label="Megosztási &előzmények…")
        self.hist_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_history())
        sb1.Add(self.hist_btn, 0, wx.ALL, 6)
        sb1.Add(wx.StaticText(p, label="A küldés &kódja (mondd be a másiknak):"),
                0, wx.LEFT, 6)
        self.code_out = wx.TextCtrl(p, style=wx.TE_READONLY)
        self.code_out.SetName("A küldés kódja")
        f = self.code_out.GetFont()
        f.SetPointSize(f.GetPointSize() + 4)
        self.code_out.SetFont(f)
        sb1.Add(self.code_out, 0, wx.EXPAND | wx.ALL, 6)
        brow = wx.BoxSizer(wx.HORIZONTAL)
        self.copy_btn = wx.Button(p, label="Kód &másolása a vágólapra")
        self.copy_btn.Bind(wx.EVT_BUTTON, lambda e: self._copy_code(manual=True))
        self.copy_btn.Disable()
        self.send_cancel = wx.Button(p, label="Küldés meg&szakítása")
        self.send_cancel.Bind(wx.EVT_BUTTON, lambda e: self._cancel_send())
        self.send_cancel.Disable()
        brow.Add(self.copy_btn, 0, wx.RIGHT, 6)
        brow.Add(self.send_cancel, 0)
        sb1.Add(brow, 0, wx.ALL, 6)
        v.Add(sb1, 0, wx.EXPAND | wx.ALL, 10)

        # --- FOGADÁS ---
        sb2 = wx.StaticBoxSizer(wx.StaticBox(p, label="Fogadás"), wx.VERTICAL)
        cr = wx.BoxSizer(wx.HORIZONTAL)
        cr.Add(wx.StaticText(p, label="A kapott &kód:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.code_in = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.code_in.SetName("A kapott kód")
        self.code_in.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_receive())
        cr.Add(self.code_in, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.recv_btn = wx.Button(p, label="Fo&gadás")
        self.recv_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_receive())
        cr.Add(self.recv_btn, 0)
        sb2.Add(cr, 0, wx.EXPAND | wx.ALL, 6)

        dr = wx.BoxSizer(wx.HORIZONTAL)
        dr.Add(wx.StaticText(p, label="Hova &mentse:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.dir_txt = wx.TextCtrl(p, value=str(Path.home() / "Downloads"))
        self.dir_txt.SetName("Cél mappa")
        db = wx.Button(p, label="&Tallózás…")
        db.Bind(wx.EVT_BUTTON, lambda e: self._pick_dir())
        dr.Add(self.dir_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        dr.Add(db, 0)
        sb2.Add(dr, 0, wx.EXPAND | wx.ALL, 6)
        v.Add(sb2, 0, wx.EXPAND | wx.ALL, 10)

        p.SetSizer(v)

    # ---- küldés -------------------------------------------------------

    def _on_send(self):
        if self.send_session:
            self.SetStatusText("Már folyamatban van egy küldés.")
            return
        dlg = wx.FileDialog(self, "Küldendő fájl kiválasztása",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        self._kuldes_inditas(path)

    def _kuldes_inditas(self, path, takarithato=None):
        """A p2p küldés KÖZÖS indítása – fájlra és becsomagolt mappára is.

        `takarithato`: az ideiglenes csomag útvonala, amiről a küldés végén meg
        kell kérdezni, megtartsuk-e. Egy négygigás zip csendben megenné a
        lemezt, ha kérdés nélkül ottfelejtenénk."""
        self._csomag_takarit = takarithato
        self._send_name = Path(path).name
        self.code_out.SetValue("")
        self.send_btn.Disable()
        self.send_cancel.Enable()
        self._sv("send", "start")
        self.SetStatusText(f"Küldés előkészítése: {Path(path).name} … "
                           "mindjárt megjelenik a kód.")
        self._send_pct = -1
        self._mondott_pct.pop("kuld", None)
        self.send_session = p2p.SendSession(
            path,
            on_code=lambda c: wx.CallAfter(self._send_code, c),
            on_done=lambda ok, msg: wx.CallAfter(self._send_done, ok, msg),
            on_progress=lambda p: wx.CallAfter(self._send_progress, p))
        self.send_session.start()

    def _send_progress(self, pct):
        if self._closing:
            return
        self._send_pct = pct
        self.SetStatusText(f"Küldés folyamatban: {pct} százalék. (F8: haladás "
                           "bemondása. Az ablakot tartsd nyitva.)")
        self._haladas_jelez("Küldés", pct, "kuld")

    def _send_code(self, code):
        if self._closing:
            return
        self.code_out.SetValue(code)
        self.copy_btn.Enable()
        copied = self._copy_code()       # rögtön a vágólapra is tesszük
        extra = (" A kódot a vágólapra is másoltam – beillesztheted "
                 "Messengerbe, e-mailbe stb. a másiknak."
                 if copied else
                 " (A vágólapra másoláshoz nyomd meg a „Kód másolása” gombot.)")
        self.SetStatusText(f"A küldés kódja: {code}.{extra} Tartsd nyitva az "
                           "ablakot, amíg átmegy a fájl.")
        # A kód a fájl átvételéhez szükséges TITOK, és a státuszsort a
        # képernyőolvasó nem feltétlenül mondja be → AKTÍVAN, tagoltan
        # elmondjuk (F8-cal bármikor újra kérhető). [Herman Tibi P2P-P0-02]
        self._speak(f"A küldés kódja: {self._spell_code(code)}. "
                    "Az F8 billentyűvel bármikor újra elmondom.")

    @staticmethod
    def _spell_code(code: str) -> str:
        """A kód tagolt felolvasása: a wormhole-kód „szám-szó-szó" alakú, a
        kötőjeleket szóra bontjuk, hogy telefonban is diktálható legyen."""
        return code.replace("-", ", kötőjel, ")

    def _clear_clipboard_code(self) -> None:
        """A küldési kód TÖRLÉSE a vágólapról, ha még az van rajta. A kód
        egyszer használatos titok; nem maradhat az ablak bezárása/az átvitel
        vége után a vágólap-előzményben. [Herman Tibi P2P-P0-02]"""
        code = self.code_out.GetValue().strip()
        if not code:
            return
        try:
            if not wx.TheClipboard.Open():
                return
            try:
                data = wx.TextDataObject()
                if (wx.TheClipboard.GetData(data)
                        and data.GetText().strip() == code):
                    wx.TheClipboard.SetData(wx.TextDataObject(""))
                    wx.TheClipboard.Flush()
            finally:
                wx.TheClipboard.Close()
        except Exception:
            pass

    def _copy_code(self, manual: bool = False) -> bool:
        code = self.code_out.GetValue().strip()
        if not code:
            return False
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(code))
            wx.TheClipboard.Flush()      # marad a vágólapon az ablak után is
            wx.TheClipboard.Close()
            if manual:
                self.SetStatusText(f"A kód a vágólapra másolva: {code}. "
                                   "Beillesztheted a másiknak.")
            return True
        return False

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _notify(self, title: str, text: str):
        """Aktív, figyelemfelkeltő értesítés a küldőnek – akkor is megjelenik
        (és a képernyőolvasó felolvassa), ha épp más ablakban vársz, plusz
        kimondjuk az önhanggal. Ez Farkas István kérése: »a fájl megérkezésekor
        nálam is jelezzen«."""
        try:
            if getattr(self.main, "settings", {}).get("notify", True):
                wx.adv.NotificationMessage(title, text).Show(timeout=10)
        except Exception:
            pass
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

    def _send_done(self, ok, msg):
        if self._closing:
            return
        self.send_session = None
        self._send_pct = -1
        self._clear_clipboard_code()   # az egyszer használatos kód ne maradjon
        self.send_btn.Enable()
        self.send_cancel.Disable()
        self.copy_btn.Disable()
        self._sv("send", "done" if ok else "error")
        if ok:
            self.code_out.SetValue("")
            name = self._send_name or "A fájl"
            # FONTOS (magyar idézőjel-csapda): a nyitó „ után ZÁRÓ ” kell, nem
            # ASCII " – az előre lezárná az f-stringet
            confirm = f"Kézbesítve: „{name}” megérkezett a másik géphez."
            self.SetStatusText(confirm)
            self._notify("SuperDL – fájl kézbesítve", confirm)
        else:
            self.SetStatusText(msg)
            self._notify("SuperDL – a küldés nem fejeződött be", msg)
        # a becsomagolt mappa sorsa – sikeres és sikertelen küldés után is
        takarit, self._csomag_takarit = self._csomag_takarit, None
        if takarit:
            wx.CallAfter(self._csomag_kerdes, takarit)

    def _cancel_send(self):
        if self.send_session:
            self.send_session.cancel()
            self.SetStatusText("Küldés megszakítása…")

    # ---- fogadás ------------------------------------------------------

    def _on_receive(self):
        if self.recv_session:
            self.SetStatusText("Már folyamatban van egy fogadás.")
            return
        code = self.code_in.GetValue().strip()
        if not code:
            self.SetStatusText("Írd be a küldőtől kapott kódot.")
            return
        out_dir = self.dir_txt.GetValue().strip() or str(Path.home() / "Downloads")
        self.recv_btn.Disable()
        self._sv("receive", "start")
        self.SetStatusText("Csatlakozás a küldőhöz… egy pillanat.")
        self._recv_pct = -1
        self._mondott_pct.pop("fogad", None)
        self.recv_session = p2p.ReceiveSession(
            code, out_dir,
            on_done=lambda ok, msg: wx.CallAfter(self._recv_done, ok, msg),
            on_progress=lambda p: wx.CallAfter(self._recv_progress, p))
        self.recv_session.start()

    def _recv_progress(self, pct):
        if self._closing:
            return
        self._recv_pct = pct
        self.SetStatusText(f"Fogadás folyamatban: {pct} százalék. "
                           "(F8: haladás bemondása.)")
        self._haladas_jelez("Fogadás", pct, "fogad")

    def _haladas_jelez(self, cimke, pct, irany):
        """AKTÍV haladás-jelzés – a státuszsort a képernyőolvasó NEM olvassa
        magától, ezért a vak felhasználó eddig nem érzékelte, hol tart az
        átvitel (Laci jelezte a küldő, Barbi a fogadó oldalról).

        Kettős visszajelzés, hogy ne legyen se néma, se fárasztó:
          • HANG: halk pittyegés, ami a haladással emelkedik (a Core közös
            ProgressBeeperje) – folyamatos érzet, beszéd nélkül;
          • BESZÉD: 25 százalékonként (25/50/75) és a végén egy rövid mondat.
        """
        try:
            if self._beeper is None:
                from superdl import sounds
                self._beeper = sounds.ProgressBeeper()
            self._beeper.update(pct)
        except Exception:
            pass
        try:
            utolso = self._mondott_pct.get(irany, -1)
            lepcso = (pct // 25) * 25            # 0 / 25 / 50 / 75 / 100
            if lepcso >= 25 and lepcso > utolso:
                self._mondott_pct[irany] = lepcso
                self._speak("%s: %d százalék." % (cimke, lepcso))
        except Exception:
            pass

    def _recv_done(self, ok, msg):
        if self._closing:
            return
        self.recv_session = None
        self._recv_pct = -1
        self.recv_btn.Enable()
        self._sv("receive", "done" if ok else "error")
        self.SetStatusText(msg)
        if ok and wx.MessageBox(msg + "\n\nMegnyitod a mappát?", "Fájl megérkezett",
                                wx.YES_NO | wx.ICON_INFORMATION, self) == wx.YES:
            import os
            try:
                os.startfile(self.dir_txt.GetValue().strip())
            except OSError:
                pass

    def _pick_dir(self):
        dlg = wx.DirDialog(self, "Cél mappa")
        if dlg.ShowModal() == wx.ID_OK:
            self.dir_txt.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_close(self, e):
        # MEGERŐSÍTÉS folyamatban lévő átvitelnél – ne szakítsuk meg véletlenül
        # (felhasználói kérés). Csak akkor kérdezünk, ha tényleg van folyó művelet.
        if (self.send_session or self.recv_session) and not self._closing:
            what = "küldés" if self.send_session else "fogadás"
            ans = wx.MessageBox(
                f"Egy {what} van folyamatban. Ha most bezárod, MEGSZAKAD.\n\n"
                "Biztosan bezárod és megszakítod?",
                "Fájlküldés – folyamatban", wx.YES_NO | wx.NO_DEFAULT |
                wx.ICON_WARNING, self)
            if ans != wx.YES:
                if e.CanVeto():
                    e.Veto()            # marad nyitva, az átvitel folytatódik
                return
        self._closing = True            # innentől a háttér-callbackek kilépnek
        self._clear_clipboard_code()    # a titkos kód ne maradjon a vágólapon
        if self.send_session:
            self.send_session.cancel()
        if self.recv_session:
            self.recv_session.cancel()
        if getattr(self.main, "_p2p_win", None) is self:
            self.main._p2p_win = None
        self.Destroy()

    # ================================================================
    # MAPPAKÜLDÉS ÉS MEGOSZTÁS (2026-09-06)
    # A felhasználók kérése: „ha Androidon lehet, akkor itt is lehessen."
    # ================================================================

    def _on_send_folder(self):
        """Mappa küldése: kiválasztás → formátum → csomagolás → út."""
        if self.send_session:
            self.SetStatusText("Már folyamatban van egy küldés.")
            return
        mappa = self._mappat_valaszt("Küldendő mappa kiválasztása")
        if not mappa:
            return
        csomag_ut = self._becsomagol(mappa)
        if not csomag_ut:
            return
        # A csomag kész – most dől el, MERRE megy
        if self._p2p_az_ut():
            self._kuldes_inditas(str(csomag_ut), takarithato=csomag_ut)
        else:
            self._tarhelyre(csomag_ut, takarithato=csomag_ut)

    def _mappat_valaszt(self, cim):
        dlg = wx.DirDialog(self, cim, style=wx.DD_DIR_MUST_EXIST)
        ut = dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else ""
        dlg.Destroy()
        return ut

    def _becsomagol(self, mappa):
        """Formátum-kérdés + csomagolás haladás-jelzéssel. Kész útvonal vagy None.

        ⚠️ A szabad helyet ELŐRE ellenőrizzük: félúton elfogyó lemez pontosan az
        a hiba, amit az MK3-ban javítottunk."""
        fajlok, ossz = csomag.gyujtes(mappa)
        if not fajlok:
            self._uzenet("Ez a mappa üres, vagy nem tudom elolvasni a "
                         "tartalmát – nincs mit küldeni.", hiba=True)
            return None

        dlg = wx.SingleChoiceDialog(
            self, f"{Path(mappa).name}: {len(fajlok)} fájl, összesen "
            f"{tarhely.emberi_meret(ossz)}.\n\nMilyen formátumba csomagoljam?",
            "Mappa küldése", csomag.formatum_nevek())
        dlg.SetSelection(0)
        rendben = dlg.ShowModal() == wx.ID_OK
        formatum = csomag.formatum_id(dlg.GetSelection())
        dlg.Destroy()
        if not rendben:
            return None

        cel = csomag.csomag_utvonal(mappa, formatum, ideiglenes=True)
        hiba = self._hely_ellenorzes(cel, ossz)
        if hiba:
            self._uzenet(hiba, hiba=True)
            return None

        return self._csomagolas_futtat(mappa, cel, formatum, fajlok, ossz)

    @staticmethod
    def _hely_ellenorzes(cel, ossz):
        """A Core lemezhely-modulja, ha elérhető. A becsléshez a tömörítetlen
        méretet vesszük: a tömörítés nyer, de nem tudjuk előre, mennyit."""
        try:
            from superdl import lemezhely
        except ImportError:
            return ""
        fer, szabad, hianyzik = lemezhely.eleg_hely(cel.parent, ossz)
        if fer:
            return ""
        return lemezhely.hiba_szoveg("a csomag", ossz, szabad, hianyzik)

    def _csomagolas_futtat(self, mappa, cel, formatum, fajlok, ossz):
        """A csomagolás modális haladásjelzővel, MEGSZAKÍTHATÓAN."""
        self._szol(csomag.csomagolas_mondat(
            Path(mappa).name, len(fajlok), tarhely.emberi_meret(ossz)))
        halado = wx.ProgressDialog(
            "Csomagolás", "Előkészítés…", maximum=100, parent=self,
            style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE |
            wx.PD_ELAPSED_TIME)
        allapot = {"megall": False, "mondott": -1}

        def halad(i, db, kesz, teljes):
            pct = int(kesz * 100 / teljes) if teljes else 0
            tovabb, _ = halado.Update(
                min(pct, 99), f"{i}. fájl a {db}-ból – {pct} százalék")
            if not tovabb:
                allapot["megall"] = True
            # tizedenként szólunk: a folyamatos beszéd használhatatlan volna
            if pct // 10 != allapot["mondott"] // 10:
                allapot["mondott"] = pct
                self._sv("csomag", "halad")

        try:
            csomag.csomagol(mappa, cel, formatum, halad=halad,
                            megall=lambda: allapot["megall"])
        except csomag.Megszakitva:
            halado.Destroy()
            self._uzenet("A csomagolást leállítottad. A félkész csomagot "
                         "kitöröltem.")
            return None
        except (OSError, ValueError) as e:
            halado.Destroy()
            self._uzenet(f"A csomagolás nem sikerült: {e}", hiba=True)
            return None
        halado.Destroy()
        meret = cel.stat().st_size if cel.exists() else 0
        self._szol(f"A csomag kész: {tarhely.emberi_meret(meret)}.")
        return cel

    def _p2p_az_ut(self) -> bool:
        """A folyamat ELSŐ kérdése – és szándékosan NEM a méretről szól.

        A p2p és a tárhely közti valódi különbség az, hogy a p2p-hez a másik
        félnek EGYSZERRE kell gépnél lennie. Ha ott van, a p2p minden méretnél
        jobb: nincs korlát, nincs harmadik fél, titkosítva megy. Ha nincs ott,
        a p2p a legkisebb fájlnál is használhatatlan. A méret csak EZUTÁN
        dönti el, melyik tárhely jöhet szóba."""
        dlg = wx.MessageDialog(
            self,
            "A másik fél MOST a gépénél van?\n\n"
            "Ha igen: gépről gépre küldöm – nincs méretkorlát, senki máshoz "
            "nem kerül, és titkosítva megy.\n\n"
            "Ha nincs ott: feltöltöm egy ideiglenes tárhelyre, és a linket "
            "elküldheted neki bármikor.",
            "Hogyan küldjem?", wx.YES_NO | wx.ICON_QUESTION)
        dlg.SetYesNoLabels("Ott van – gépről gépre",
                           "Nincs ott – tárhelyre")
        valasz = dlg.ShowModal()
        dlg.Destroy()
        return valasz == wx.ID_YES

    def _on_share(self):
        """Feltöltés ideiglenes tárhelyre – fájl vagy mappa."""
        dlg = wx.MessageDialog(
            self, "Mit töltsek fel?", "Feltöltés tárhelyre",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
        dlg.SetYesNoCancelLabels("Egy fájlt", "Egy mappát", "Mégse")
        valasz = dlg.ShowModal()
        dlg.Destroy()
        if valasz == wx.ID_YES:
            fd = wx.FileDialog(self, "Feltöltendő fájl",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            ut = fd.GetPath() if fd.ShowModal() == wx.ID_OK else ""
            fd.Destroy()
            if ut:
                self._tarhelyre(Path(ut))
        elif valasz == wx.ID_NO:
            mappa = self._mappat_valaszt("Feltöltendő mappa")
            if mappa:
                cel = self._becsomagol(mappa)
                if cel:
                    self._tarhelyre(cel, takarithato=cel)

    def _tarhelyre(self, ut: Path, takarithato=None):
        """A felhős út: figyelmeztetés → tárhely → megerősítés → feltöltés."""
        ut = Path(ut)
        try:
            meret = ut.stat().st_size
        except OSError as e:
            self._uzenet(f"A fájlt nem tudom elolvasni: {e}", hiba=True)
            return
        valaszthatok = tarhely.valaszthatok(meret)
        if not valaszthatok:
            self._uzenet(
                f"Ez a fájl {tarhely.emberi_meret(meret)} – egyik ideiglenes "
                "tárhelybe sem fér bele. Küldd inkább kóddal, gépről gépre: "
                "ott nincs méretkorlát.", hiba=True)
            return

        # ⚠️ A KÖTELEZŐ FIGYELMEZTETÉS. Ez az egyetlen hely, ahol a megosztás
        # megáll és kérdez – minden alkalommal, nem csak először.
        self._szol(tarhely.FIGYELMEZTETES)
        fdlg = wx.MessageDialog(self, tarhely.FIGYELMEZTETES + "\n\nFolytatod?",
                                "Nyilvános feltöltés",
                                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        fdlg.SetYesNoLabels("Folytatom", "Mégse")
        megy = fdlg.ShowModal() == wx.ID_YES
        fdlg.Destroy()
        if not megy:
            return

        leirasok = [tarhely.leiras(t) for t in valaszthatok]
        vdlg = wx.SingleChoiceDialog(
            self, f"{ut.name} – {tarhely.emberi_meret(meret)}.\n\n"
            "Hova töltsem fel? (Csak azok látszanak, amelyekbe belefér.)",
            "Tárhely választása", leirasok)
        vdlg.SetSelection(0)
        rendben = vdlg.ShowModal() == wx.ID_OK
        index = vdlg.GetSelection()
        vdlg.Destroy()
        if not rendben:
            return
        cel = valaszthatok[index]

        mdlg = wx.MessageDialog(
            self, tarhely.megerosito_kerdes(cel, ut.name, meret),
            "Megerősítés", wx.YES_NO | wx.ICON_QUESTION)
        mdlg.SetYesNoLabels("Feltöltöm", "Mégse")
        indul = mdlg.ShowModal() == wx.ID_YES
        mdlg.Destroy()
        if not indul:
            return

        self._feltoltes_futtat(ut, cel, meret, takarithato)

    def _feltoltes_futtat(self, ut: Path, cel, meret, takarithato):
        halado = wx.ProgressDialog(
            "Feltöltés", f"Feltöltés ide: {cel.nev}…", maximum=100, parent=self,
            style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE |
            wx.PD_ELAPSED_TIME)
        allapot = {"mondott": -1}
        self._szol(f"Feltöltés indul ide: {cel.nev}.")

        def halad(kesz, teljes):
            pct = int(kesz * 100 / teljes) if teljes else 0
            wx.CallAfter(self._feltoltes_halad, halado, allapot, pct, munka)

        def kesz(ok, uzenet):
            wx.CallAfter(self._feltoltes_kesz, halado, ok, uzenet, ut, cel,
                         meret, munka, takarithato)

        munka = feltoltes.Feltoltes(ut, cel, halad=halad, kesz=kesz)
        munka.start()

    def _feltoltes_halad(self, halado, allapot, pct, munka):
        if self._closing:
            return
        try:
            tovabb, _ = halado.Update(min(pct, 99), f"{pct} százalék")
        except RuntimeError:
            return
        if not tovabb:
            munka.cancel()
        if pct // 20 != allapot["mondott"] // 20:
            allapot["mondott"] = pct
            self._sv("feltolt", "halad")

    def _feltoltes_kesz(self, halado, ok, uzenet, ut, cel, meret, munka,
                        takarithato):
        if self._closing:
            return
        try:
            halado.Destroy()
        except RuntimeError:
            pass
        if not ok:
            self._uzenet(uzenet, hiba=True)
            self._csomag_kerdes(takarithato)
            return
        link = uzenet
        megosztas.rogzit(ut.name, link, cel.id, cel.nev, meret, cel.nap,
                         egyszeri=cel.egyszeri, torolheto=cel.torolheto,
                         torlo_kulcs=munka.torlo_kulcs)
        self._vagolapra(link)
        mondat = (f"Kész. A link a vágólapon van, és bekerült a megosztási "
                  f"előzményekbe. {tarhely.emberi_nap(cel.nap).capitalize()} "
                  "lesz elérhető")
        if cel.egyszeri:
            mondat += ", és CSAK EGYSZER tölthető le"
        self._szol(mondat + ".")
        self.SetStatusText(link)
        self._csomag_kerdes(takarithato)

    def _csomag_kerdes(self, csomag_ut):
        """A küldés/feltöltés után: megtartsam a csomagot vagy töröljem?

        Alph döntése: KÉRDEZZE MEG minden alkalommal. Egy négygigás zip csendben
        megenné a lemezt, de van, amikor pont kell még."""
        if not csomag_ut:
            return
        csomag_ut = Path(csomag_ut)
        if not csomag_ut.exists():
            return
        meret = tarhely.emberi_meret(csomag_ut.stat().st_size)
        dlg = wx.MessageDialog(
            self, f"Megtartsam a becsomagolt fájlt? ({meret})\n\n"
            "Ha megtartom, megkérdezem, hova tegyem. Ha nem, törlöm – a "
            "mappád természetesen érintetlen marad.",
            "A csomag sorsa", wx.YES_NO | wx.ICON_QUESTION)
        dlg.SetYesNoLabels("Megtartom", "Töröld")
        tart = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if not tart:
            try:
                csomag_ut.unlink(missing_ok=True)
                self._szol("A csomagot töröltem.")
            except OSError as e:
                self._uzenet(f"A csomagot nem tudtam törölni: {e}", hiba=True)
            return
        sdlg = wx.FileDialog(self, "Hova mentsem a csomagot?",
                             defaultFile=csomag_ut.name.split("-", 1)[-1],
                             style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if sdlg.ShowModal() == wx.ID_OK:
            uj = Path(sdlg.GetPath())
            try:
                csomag_ut.replace(uj)
                self._szol(f"A csomag itt van: {uj}")
            except OSError as e:
                self._uzenet(f"Nem sikerült odamásolni: {e}", hiba=True)
        sdlg.Destroy()

    # ---- megosztási előzmények ----------------------------------------

    def _on_history(self):
        tetelek = megosztas.lathatoak()
        if not tetelek:
            self._uzenet("Még nem osztottál meg semmit ideiglenes tárhelyre.")
            return
        sorok = [megosztas.sor_szoveg(t) for t in tetelek]
        dlg = wx.SingleChoiceDialog(
            self, "A megosztásaid – elöl, ami hamarabb lejár.\n"
            "Válassz egyet, és megmondom, mit tehetsz vele.",
            "Megosztási előzmények", sorok)
        dlg.SetSelection(0)
        rendben = dlg.ShowModal() == wx.ID_OK
        index = dlg.GetSelection()
        dlg.Destroy()
        if rendben and 0 <= index < len(tetelek):
            self._elozmeny_muvelet(tetelek[index])

    def _elozmeny_muvelet(self, tetel):
        muveletek = ["Link a vágólapra",
                     "A link betűzve felolvasva",
                     "Törlés a tárhelyről (ha lehet)",
                     "Kivétel a nyilvántartásból",
                     "A lejártak eltakarítása"]
        dlg = wx.SingleChoiceDialog(
            self, megosztas.sor_szoveg(tetel), "Mit tegyek vele?", muveletek)
        dlg.SetSelection(0)
        rendben = dlg.ShowModal() == wx.ID_OK
        valasztott = dlg.GetSelection()
        dlg.Destroy()
        if not rendben:
            return
        link = str(tetel.get("link", ""))
        if valasztott == 0:
            self._vagolapra(link)
            self._szol("A link a vágólapon van.")
        elif valasztott == 1:
            self._szol(megosztas.betuzve(link))
        elif valasztott == 2:
            self._tarhelyrol_torol(tetel)
        elif valasztott == 3:
            maradok = [t for t in megosztas.betolt()
                       if t.get("link") != link]
            megosztas.ment(maradok)
            self._szol(megosztas.sor_torles_mondat(tetel))
        else:
            db = megosztas.takarit()
            self._szol(f"{db} lejárt sort takarítottam el." if db
                       else "Nem volt eltakarítani való.")

    def _tarhelyrol_torol(self, tetel):
        cel = next((t for t in tarhely.TARHELYEK
                    if t.id == tetel.get("tarhely")), None)
        if cel is None:
            self._uzenet("Ezt a tárhelyet már nem ismerem.", hiba=True)
            return
        ok, uzenet = feltoltes.torles(cel, str(tetel.get("link", "")),
                                      str(tetel.get("torlo_kulcs", "")))
        if ok:
            maradok = [t for t in megosztas.betolt()
                       if t.get("link") != tetel.get("link")]
            megosztas.ment(maradok)
        self._szol(uzenet)

    # ---- közös apróságok ----------------------------------------------

    def _vagolapra(self, szoveg):
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(szoveg))
                wx.TheClipboard.Close()
        except Exception:
            pass

    def _szol(self, szoveg):
        """Kimondás ÉS az állapotsorba írás – vakon a hang a fő csatorna."""
        self.SetStatusText(szoveg)
        self._speak(szoveg)

    def _uzenet(self, szoveg, hiba=False):
        self._szol(szoveg)
        wx.MessageBox(szoveg, "Fájlküldés",
                      wx.OK | (wx.ICON_ERROR if hiba else wx.ICON_INFORMATION),
                      self)
