# -*- coding: utf-8 -*-
"""Super Mail – akadálymentes levelező ablak (wxPython).

Tisztán emailezés: fogadás (IMAP/POP3), küldés (SMTP), keresés. Semmi mást nem
csinál, és SEMMIT nem továbbít sehová. Az első indításkor hozzájárulást kérünk,
és világosan közöljük: a megadott adatok kizárólag a te gépeden, titkosítva
élnek, és egyetlen céljuk, hogy az e-mail működjön.
"""
import os
import re
import threading
from pathlib import Path

import wx

from . import ailevel as AI
from . import forditas as FORD

from . import mail_core as MC
# OAuth eltávolítva: kizárólag app-jelszavas hitelesítés (lásd a súgót).


HOZZAJARULAS_SZOVEG = (
    "SUPER MAIL – ADATVÉDELMI TÁJÉKOZTATÓ ÉS HOZZÁJÁRULÁS\n\n"
    "Ez a program KIZÁRÓLAG e-mailezésre való: leveleket olvasol, küldesz és "
    "keresel vele. Nincs benne naptár, nyomkövetés, hirdetés vagy bármi más.\n\n"
    "AMIT TUDNOD KELL:\n\n"
    "• A belépéshez NEM a valódi fiók-fő-jelszavadat adod meg, hanem egy "
    "APP-JELSZÓT: ezt te hozod létre a saját fiókod beállításaiban, KIZÁRÓLAG a "
    "Super Mail számára. Csak levelezésre jó, és bármikor VISSZAVONHATOD a "
    "fiókodnál – a fő-jelszavad érintetlen és titok marad.\n\n"
    "• A megadott fiók-adatok (e-mail cím és app-jelszó) KIZÁRÓLAG a te gépeden, "
    "a Windows saját titkosításával (DPAPI) titkosítva tárolódnak.\n\n"
    "• SEMMIT, DE SEMMIT nem továbbítunk sehová: nincs telemetria, nincs felhő, "
    "nincs harmadik fél, nincs külső belépés. A program KÖZVETLENÜL a te "
    "e-mail-szolgáltatód szerveréhez csatlakozik (IMAP, POP3, SMTP), semmi "
    "máshoz.\n\n"
    "• A hitelesítő adatoknak EGYETLEN célja van: hogy az olvasás, küldés és "
    "keresés működjön.\n\n"
    "• Bármikor visszavonhatod: ha törlöd a fiókot, a tárolt app-jelszava "
    "véglegesen törlődik a gépedről; és a szolgáltatódnál is bármikor "
    "letilthatod magát az app-jelszót.\n\n"
    "• Csak a SAJÁT e-mail-fiókjaidhoz használd.\n\n"
    "Ha ezt elfogadod, nyomd meg az Elfogadom gombot. Ha nem, a Mégsem-mel "
    "kiléphetsz."
)


_SUGO = (
    "SUPER MAIL – SÚGÓ\n\n"
    "Akadálymentes e-mail kliens: KIZÁRÓLAG emailezés (olvasás, küldés, "
    "keresés). Nincs naptár, nincs nyomkövetés, és SEMMIT nem továbbítunk "
    "sehová – a program közvetlenül a te szolgáltatód szerveréhez csatlakozik, "
    "a fiók-adatok a gépeden, titkosítva élnek.\n\n"
    "FIÓK HOZZÁADÁSA\n"
    "• Nyomd meg a Fiók hozzáadása gombot.\n"
    "• Az ELSŐ mező az E-MAIL CÍM (pl. valaki@gmail.com). A szervereket és a "
    "portokat a program magától kitölti (kézzel felülírhatók).\n"
    "• Hitelesítés APP-JELSZÓVAL: az App-jelszó létrehozása gombbal a program "
    "megnyitja hozzá a pontos oldalt, és felolvassa a lépéseket. A kapott "
    "jelszót másold be a Jelszó mezőbe.\n"
    "• Kapcsolat tesztelése, majd Mentés.\n\n"
    "MIÉRT APP-JELSZÓ – ÉS MIÉRT EZ A BIZTONSÁGOS MEGOLDÁS\n"
    "• Az app-jelszó egy KÜLÖN, kizárólag a Super Mailhez szóló belépő, amit TE "
    "hozol létre a saját fiókod beállításaiban. Így a VALÓDI fő-jelszavadat SOHA "
    "nem kell megadnod a programnak – az titok és érintetlen marad.\n"
    "• DEDIKÁLT és VISSZAVONHATÓ: az app-jelszó csak levelezésre jó, és bármikor, "
    "egyetlen kattintással letilthatod a fiókodnál – anélkül, hogy a "
    "fő-jelszavadat vagy bármi mást megváltoztatnál. Ha visszavonod, a Super "
    "Mail egyszerűen nem fér hozzá többé; a fiókod többi része érintetlen.\n"
    "• Az azonosságod és a fiókod így VÉGIG a te kezedben marad: a program pont "
    "annyit kap, amennyit te adsz neki, pontosan addig, ameddig te akarod.\n"
    "• A megadott app-jelszó a gépeden, a Windows DPAPI-titkosításával él, és "
    "SEMMIT nem továbbítunk sehová – a program közvetlenül a te szolgáltatód "
    "szerveréhez kapcsolódik, semmi máshoz. Nincs külső belépés, nincs felhő, "
    "nincs harmadik fél.\n\n"
    "BÁRMILYEN FIÓK KÉZI BEÁLLÍTÁSA (Freemail, Citromail, céges, saját domain)\n"
    "• Ha a fiókodhoz van IMAP/POP3 és SMTP hozzáférés, akkor is beállíthatod, ha "
    "a program nem ismeri automatikusan.\n"
    "• Írd be az e-mail címet, majd a haladó mezőkben add meg KÉZZEL a szerver-"
    "neveket (IMAP/POP3/SMTP) és a portokat. Szokásos portok: IMAP 993, POP3 "
    "995, SMTP 465 (SSL) vagy 587 (STARTTLS). A pontos értékeket a szolgáltatód "
    "súgójában megtalálod.\n"
    "• Sok szolgáltatónál (pl. Freemail, Citromail) a sima fiókjelszó is működik "
    "IMAP/SMTP-n; ha elutasít, a fiókodnál keress rá az app-jelszó "
    "létrehozására.\n\n"
    "MENÜSÁV (minden művelet itt, szépen rendezve – Alt-tal is elérhető)\n"
    "• ÖSSZES BEJÖVŐ: ha egynél több fiókod van, a MAPPÁK LISTÁJÁNAK legelső "
    "eleme az „Összes bejövő (minden fiók)” – minden fiók beérkezett levele EGY "
    "listában, IDŐRENDBEN (a legfrissebb elöl), soronként a fiók nevével. "
    "(A Fiók menüből is elérhető.)\n"
    "• A LISTA SZÉLÉN (a tetején felfelé, az alján lefelé) a program nem "
    "olvassa fel újra ugyanazt a sort: rövid hangjelzés szól. A Beállítások → "
    "Általános fülön átállítható, hogy inkább mondja ki.\n"
    "• Fiók: Fiók hozzáadása/törlése, Összes bejövő (minden fiók egy listában), "
    "Frissítés (F5), Keresés, Bezárás.\n"
    "• Levél: Új levél (N), Megnyitás külön ablakban (Enter), Válasz (R), Válasz "
    "mindenkinek, Továbbítás (F), Olvasottnak/Olvasatlannak jelölés, Csatolmány "
    "mentése, AI-összefoglaló (AI-kulcs kell), Törlés (Del).\n"
    "• Segítség: Súgó (F1), Támogatás, Névjegy.\n"
    "A levéllistán a helyi menü (Alkalmazások-billentyű / Shift+F10 / jobbklikk) "
    "is ugyanezeket kínálja.\n\n"
    "TÖBB FIÓK\n"
    "• Fent a Fiók legördülővel válthatsz köztük.\n"
    "• Ha egynél több fiók van, a Fiók menü Összes bejövő pontja minden fiók "
    "bejövő levelét egy listába gyűjti, mindegyik előtt a fiók nevével.\n\n"
    "OLVASÁS – KÜLÖN ABLAKBAN, KATTINTHATÓ HIVATKOZÁSOKKAL\n"
    "• Bal oldalt a Mappák (Beérkezett, Elküldött, Kuka…), jobbra a Levelek.\n"
    "• Enter (vagy dupla kattintás) a levélen: KÜLÖN ABLAKBAN nyílik meg. Ott "
    "külön van a fejléc és a szöveg, és LENT a Hivatkozások lista: rállsz egy "
    "linkre, Enter, és megnyílik a böngészőben (a levélben lévő linkek így "
    "kattinthatók).\n"
    "• Az olvasó-ablaknak SAJÁT menüsávja van (Levél, Hivatkozások, Segítség): "
    "válasz, továbbítás, csatolmány mentése, AI-összefoglaló, törlés, bezárás "
    "(Esc). A HTML-levelek távoli képeit adatvédelmi okból nem töltjük be.\n\n"
    "AI-ÖSSZEFOGLALÓ\n"
    "• A gép tömören összefoglalja a levelet: mi a lényeg, van-e teendő.\n"
    "• EHHEZ AI-KULCS KELL: állítsd be a SuperDL Beállítások, AI fülén "
    "(OpenAI, Gemini, Anthropic vagy xAI). A kulcs a gépeden marad.\n\n"
    "TÖMEGES KEZELÉS – KIJELÖLÉS, TÖRLÉS, MOZGATÁS\n"
    "• Több levél kijelölése: a listában Ctrl+kattintás vagy Shift+nyíl. "
    "Ctrl+A: a mappa MINDEN levele.\n"
    "• Törlés: a kijelölt levele(ke)t a Del (vagy a Levél menü Törlés) egyszerre "
    "törli, egy megerősítéssel.\n"
    "• Mozgatás (pl. Spam-be): állj a levele(ke)n, Ctrl+X (kivágás) vagy Ctrl+C "
    "(másolás), majd válaszd ki a cél-mappát a Mappák listában, és nyomj "
    "Ctrl+V-t. Kivágásnál a levél átkerül; másolásnál a forrásban is megmarad. "
    "Ez IMAP-fióknál működik (POP3-nál nincsenek szerver-mappák), ugyanazon a "
    "fiókon belül.\n"
    "• A Mappák listában a Beérkezett MINDIG legfelül van, alatta a rendszer-"
    "mappák (Elküldött, Piszkozatok, Kuka, Spam), majd a többi.\n\n"
    "CÍMJEGYZÉK (magától tanul a leveleidből)\n"
    "• A program a küldött ÉS kapott leveleid címeit MAGÁTÓL összegyűjti.\n"
    "• Levélíráskor a Címzett/Másolat/Titkos mezőben elég elkezdened beírni: a "
    "program kiegészíti, fel/le nyíllal a beírt szöveg alapján választhatsz.\n"
    "• A 📇 Címjegyzék gombbal listából is beszúrhatsz Címzettbe, Másolatba (Cc) "
    "vagy Titkos másolatba (Bcc). Válaszkor a címzett magától bekerül.\n\n"
    "ÚJ LEVÉL ÉRTESÍTŐ (fiókonként külön)\n"
    "• Fiók menü → Új levél értesítő: beállíthatod, hogy amikor új levél érkezik, "
    "a program felolvasson egy szöveget VAGY lejátsszon egy hangot – FIÓKONKÉNT "
    "más-más. A program a háttérben is figyeli az új leveleket.\n\n"
    "KÜLDÉS, KERESÉS\n"
    "• Új (N) levél; Válasz (R); Továbbítás (F); Titkos másolat (Bcc) is. A "
    "küldés mindig megerősítést kér.\n"
    "• VÁLASZNÁL a kurzor egyből a levél szövegének elejére kerül (az idézet "
    "fölé), tehát csak írni kell. Új levélnél és továbbításnál a Címzett mezőn "
    "indulsz, mert ott azt kell először kitölteni.\n"
    "• LEVELEZŐLISTA: ha a levél listáról jött, a program ezt megnyitáskor ki "
    "is mondja, és az L betűvel (vagy a Levél menüből) a LISTÁRA válaszolsz, "
    "nem a feladónak – a lista címét a levél fejléce adja, nem kell beírni. A "
    "küldés-megerősítés ilyenkor figyelmeztet, hogy a levél a lista minden "
    "tagjához megy.\n"
    "• FORDÍTÁS (F9 a megnyitott levélben): idegen nyelvű levél lefordítása "
    "magyarra. A nyelvet magától felismeri. Két fordító közül választhatsz: az "
    "ingyenes, kulcs nélküli szolgáltatás, vagy – ha van AI-kulcsod – az "
    "AI-fordítás (jobb minőség). MINDKETTŐNÉL elhagyja a levél szövege a gépet, "
    "ezért a program előbb figyelmeztet. A fordítás a levél elejére kerül, az "
    "eredeti alatta marad.\n"
    "• PISZKOZAT: ha félkész levéllel zárnád be az ablakot, a program "
    "rákérdez, és a szolgáltatód Piszkozatok mappájába menti (így a telefonodon "
    "is ott lesz); ha az nem megy, a saját gépedre. Menet közben: Ctrl+S.\n"
    "• ALÁÍRÁS: a Beállítások → Általános fülön szabadon átírható, akár "
    "törölhető. A levél legaljára minden esetben odakerül egy sor: "
    "„Super Mail-lel küldve.”\n"
    "• BESZÚRÁS gomb (a levélírásnál): HIVATKOZÁS (Ctrl+K – a megjelenő szöveg "
    "nem kötelező), KÉP a levél testébe (Ctrl+Shift+K) és VIDEÓ-HIVATKOZÁS. "
    "Videót levélbe beágyazva egyetlen levelező sem játszik le, ezért oda "
    "kattintható hivatkozás kerül. Ha van a levélben hivatkozás vagy kép, a "
    "program HTML-t ÉS sima szöveget is küld – a címzett gépe választ.\n"
    "• CTRL+V: ha a vágólapon fájl vagy kép van (pl. képernyőkép), a program "
    "csatolmányként teszi be, és bemondja.\n"
    "• NAGY FÁJL: a program megkérdezi a szolgáltatód VALÓDI méretkorlátját, és "
    "ha a levél nem férne át, választhatsz: feltöltés nyilvános megosztóra "
    "(a link a levélbe kerül – de figyelj: az a tárhely bárkinek elérhető, "
    "akinek megvan a link), vagy P2P fájlküldés (titkosított, felhő nélkül).\n"
    "• AI-LEVÉL gomb: megmondod, kinek és miről írjunk, választasz hangnemet, "
    "megszólítást és hosszt, a többit az AI írja meg – elfogadod, pontosítod "
    "vagy újragenerálod. EHHEZ AI-KULCS KELL (AI menü → AI-beállítások). A "
    "leírás és – ha kéred – a megválaszolandó levél elmegy a választott "
    "AI-szolgáltatóhoz; csatolmányt sosem küldünk el.\n"
    "• Keresés: feladó, tárgy vagy szöveg szerint.\n\n"
    "GYORSBILLENTYŰK\n"
    "• Enter: megnyitás külön ablakban  • N: új  • R: válasz  • F: továbbítás\n"
    "• Ctrl+A: mind kijelöl  • Ctrl+X: kivágás  • Ctrl+C: másolás  "
    "• Ctrl+V: beillesztés  • Del: törlés\n"
    "• F5: frissítés  • F1: ez a súgó  • Esc: bezárás\n\n"
    "ADATVÉDELEM\n"
    "• Az app-jelszó a gépeden, a Windows DPAPI-titkosításával él, egyetlen célja "
    "az e-mail működése. Bármikor visszavonható: a fiók törlésével a tárolt "
    "app-jelszó törlődik, és a szolgáltatódnál is letilthatod. A valódi "
    "fő-jelszavadat sosem adod meg. Csak a saját fiókjaidhoz.\n\n"
    "A program ingyenes. Ha megköszönnéd, alul a Támogatás gomb segít – de "
    "SOHA nem kötelező, és semmilyen funkciót nem zár el."
)


def _mondd(main, szoveg):
    if not (szoveg or "").strip():
        return
    try:
        from superdl import screenreader
        if screenreader.speak(szoveg):
            return
    except Exception:
        pass
    sv = getattr(main, "selfvoice", None)
    if sv:
        try:
            sv.speak(szoveg, force=True)
        except Exception:
            pass


class HelyesirasDialog(wx.Dialog):
    """A talált helyesírási hibák VAK-FIRST javítója: a hibák listában, minden
    hibához javaslatok; Enterrel cserélsz. (Nem aláhúzás – felsorolás.)"""

    def __init__(self, parent, main, ellenorzo, szoveg):
        super().__init__(parent, title="Helyesírás-ellenőrzés",
                         size=(640, 480),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self._e = ellenorzo
        self._szoveg = szoveg
        self._hibak = []
        v = wx.BoxSizer(wx.VERTICAL)
        self._cimke = wx.StaticText(self, label="Ellenőrzés…")
        v.Add(self._cimke, 0, wx.ALL, 8)

        v.Add(wx.StaticText(self, label="&Talált hibák (fel/le nyíl):"),
              0, wx.LEFT, 8)
        self._lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self._lista.SetName("Talált helyesírási hibák")
        self._lista.Bind(wx.EVT_LISTBOX, lambda e: self._hiba_valt())
        v.Add(self._lista, 1, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(self, label="&Javaslatok (Enter: csere):"),
              0, wx.LEFT, 8)
        self._jav = wx.ListBox(self, style=wx.LB_SINGLE)
        self._jav.SetName("Javaslatok")
        self._jav.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._csere())
        v.Add(self._jav, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, kez in (("&Csere", self._csere),
                           ("&Kihagyás", self._kihagy),
                           ("Felvétel a &szótárba", self._szotarba)):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, k=kez: k())
            sor.Add(b, 0, wx.RIGHT, 6)
        kesz = wx.Button(self, wx.ID_OK, "&Kész")
        sor.Add(kesz, 0)
        v.Add(sor, 0, wx.ALL, 8)
        self.SetSizer(v)
        self.Bind(wx.EVT_CHAR_HOOK, self._bill)
        wx.CallAfter(self._ujraellenoriz)

    @property
    def szoveg(self):
        return self._szoveg

    def _ujraellenoriz(self):
        self._hibak = self._e.ellenoriz(self._szoveg)
        self._lista.Set([h.felolvasva() for h in self._hibak])
        if self._hibak:
            self._lista.SetSelection(0)
            self._hiba_valt()
            self._cimke.SetLabel("%d lehetséges hiba." % len(self._hibak))
            _mondd(self.main, "%d lehetséges helyesírási hiba. Az elsőt "
                   "kijelöltem: %s" % (len(self._hibak),
                                       self._hibak[0].felolvasva()))
        else:
            self._jav.Set([])
            self._cimke.SetLabel("Nincs több hiba.")
            _mondd(self.main, "Nem találtam több helyesírási hibát.")

    def _hiba_valt(self):
        i = self._lista.GetSelection()
        if 0 <= i < len(self._hibak):
            self._jav.Set(self._hibak[i].javaslatok or ["(nincs javaslat)"])
            if self._hibak[i].javaslatok:
                self._jav.SetSelection(0)

    def _aktualis(self):
        i = self._lista.GetSelection()
        return self._hibak[i] if 0 <= i < len(self._hibak) else None

    def _csere(self):
        h = self._aktualis()
        j = self._jav.GetSelection()
        if not h or not h.javaslatok or j < 0 or j >= len(h.javaslatok):
            _mondd(self.main, "Nincs kiválasztott javaslat.")
            return
        uj = h.javaslatok[j]
        self._szoveg = (self._szoveg[:h.kezdet] + uj
                        + self._szoveg[h.kezdet + h.hossz:])
        _mondd(self.main, "Kicserélve: %s helyett %s." % (h.szo, uj))
        self._ujraellenoriz()

    def _kihagy(self):
        h = self._aktualis()
        if h:
            self._e.hozzaad  # (nem szótárazzuk, csak a listából vesszük ki)
            i = self._lista.GetSelection()
            self._hibak.pop(i)
            self._lista.Delete(i)
            if self._lista.GetCount():
                self._lista.SetSelection(min(i, self._lista.GetCount() - 1))
                self._hiba_valt()
            _mondd(self.main, "Kihagyva: %s" % h.szo)

    def _szotarba(self):
        h = self._aktualis()
        if h and self._e.hozzaad(h.szo):
            _mondd(self.main, "Felvéve a szótárba: %s" % h.szo)
            self._ujraellenoriz()
        elif h:
            _mondd(self.main, "A szótárba felvétel nem sikerült.")

    def _bill(self, e):
        if (e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
                and self.FindFocus() is self._jav):
            self._csere()
        else:
            e.Skip()


_ERT_PLAYER = None          # az értesítő-hang lejátszója (életben tartva)


def ertesito_hang(ut):
    """Egy értesítő-hang lejátszása. Visszaad: (siker, üzenet).

    FONTOS TANULSÁG (tesztelői visszajelzés): korábban a Core Player-ét
    használtuk, ami FFMPEG-et igényel – ha az nincs letöltve, a hang NÉMÁN
    elmaradt (sem WAV, sem MP3 nem szólt). Most:
      1) WAV → a Windows beépített `winsound`-ja (nem kell hozzá SEMMI),
      2) egyéb (MP3, OGG…) → a Player (ffmpeg),
      3) ha egyik sem megy, VISSZAJELZÜNK, hogy miért – néma hiba nincs.
    A lejátszót modul-szinten tartjuk életben, hogy a párbeszéd bezárása ne
    vágja el a hangot."""
    ut = (ut or "").strip()
    if not ut:
        return False, "Nincs hangfájl megadva."
    if not os.path.isfile(ut):
        return False, "A megadott hangfájl nem található: %s" % ut
    if os.path.splitext(ut)[1].lower() == ".wav":
        try:
            import winsound
            winsound.PlaySound(ut, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True, ""
        except Exception as ex:
            return False, "A WAV lejátszása nem sikerült: %s" % ex
    try:
        from superdl.audioengine import Player, _ffmpeg_exe
        if not _ffmpeg_exe():
            return False, ("Ehhez a formátumhoz az FFmpeg kell, ami még nincs "
                           "letöltve. WAV-fájl viszont FFmpeg nélkül is szól – "
                           "próbálj egy .wav hangot!")
        global _ERT_PLAYER
        _ERT_PLAYER = Player()
        _ERT_PLAYER.play(ut, "")
        return True, ""
    except Exception as ex:
        return False, "A hang lejátszása nem sikerült: %s" % ex


def _hatterben(munka, kesz, hiba):
    """A `munka()` háttérszálon fut; siker → kesz(eredmény), hiba → hiba(kivétel).
    Mindkettő a fő szálon (wx.CallAfter)."""
    def fut():
        try:
            e = munka()
        except Exception as ex:
            wx.CallAfter(hiba, ex)
        else:
            wx.CallAfter(kesz, e)
    threading.Thread(target=fut, daemon=True).start()


def _kliens(fiok):
    # App-jelszavas (LOGIN) hitelesítés – nincs OAuth, nincs token-lekérő.
    if fiok.get("protokoll") == "pop":
        return MC.Pop3Kliens(fiok)
    return MC.ImapKliens(fiok)


# ======================================================================
#  Hozzájárulási képernyő
# ======================================================================
class HozzajarulasDialog(wx.Dialog):
    def __init__(self, parent, main):
        super().__init__(parent, title="Super Mail – hozzájárulás",
                         size=(640, 560))
        self.main = main
        v = wx.BoxSizer(wx.VERTICAL)
        t = wx.TextCtrl(self, value=HOZZAJARULAS_SZOVEG,
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        t.SetName("Adatvédelmi tájékoztató")
        v.Add(t, 1, wx.EXPAND | wx.ALL, 10)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        el = wx.Button(self, wx.ID_OK, "&Elfogadom")
        el.Bind(wx.EVT_BUTTON, self._elfogad)
        m = wx.Button(self, wx.ID_CANCEL, "&Mégsem")
        sor.Add(el, 0, wx.RIGHT, 8)
        sor.Add(m, 0)
        v.Add(sor, 0, wx.ALL | wx.ALIGN_CENTER, 12)
        self.SetSizer(v)
        wx.CallAfter(_mondd, main, "Super Mail. Kérlek, olvasd el az "
                     "adatvédelmi tájékoztatót, majd Elfogadom vagy Mégsem.")

    def _elfogad(self, e):
        # Ha a tartós mentés (DPAPI-titkosítás) épp nem megy, akkor se RAGADJON
        # BE a párbeszéd: bezárjuk, és ebben a munkamenetben használható.
        try:
            MC.hozzajarulas_ment(True)
        except Exception:
            _mondd(self.main, "A hozzájárulást most nem sikerült tartósan "
                   "elmenteni (titkosítási hiba), de ebben a munkamenetben "
                   "használhatod a levelezőt. Ha ez megmarad, ellenőrizd a "
                   "telepítést.")
        self.EndModal(wx.ID_OK)


# ======================================================================
#  Fiók-varázsló (kizárólag app-jelszó / jelszó – nincs OAuth)
# ======================================================================
class FiokDialog(wx.Dialog):
    def __init__(self, parent, main, fiok=None):
        super().__init__(parent, title="E-mail fiók hozzáadása",
                         size=(560, 520),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.eredmeny = None
        v = wx.BoxSizer(wx.VERTICAL)

        # FONTOS (akadálymentesség): a címke-StaticText MINDIG a mező ELŐTT jön
        # létre (z-sorrend) – különben a képernyőolvasó ELTOLVA olvassa a
        # címkéket (a mező a KÖVETKEZŐ címkét kapná). Plusz explicit SetName.
        def sor(cimke, **kw):
            s = wx.BoxSizer(wx.HORIZONTAL)
            st = wx.StaticText(self, label=cimke)          # ELŐBB a címke
            ctrl = wx.TextCtrl(self, **kw)                 # UTÁNA a mező
            ctrl.SetName(cimke.replace("&", "").rstrip(":"))
            s.Add(st, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            s.Add(ctrl, 1)
            v.Add(s, 0, wx.EXPAND | wx.ALL, 6)
            return ctrl

        # Az E-MAIL CÍM az elsődleges, egyértelmű mező (elöl); a név opcionális.
        self.email = sor("&E-mail cím (pl. valaki@gmail.com):")
        self.email.Bind(wx.EVT_KILL_FOCUS, self._auto)
        self.nev = sor("Megjelenő &név (nem kötelező):")

        # Hitelesítés: KIZÁRÓLAG app-jelszó / jelszó. Nincs OAuth, nincs külső
        # böngészős belépés. A felhasználó a SAJÁT fiókjánál készített, csak a
        # Super Mailhez szóló DEDIKÁLT app-jelszót adja meg – a valódi
        # fő-jelszavát SOHA. (A részletes indoklás a súgóban.)
        self.jelszo = sor("&Jelszó / app-jelszó:", style=wx.TE_PASSWORD)
        self.jelszo_info = wx.StaticText(self, label="")
        v.Add(self.jelszo_info, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self.appjelszo_gomb = wx.Button(
            self, label="App-jelszó &létrehozása (megnyitom a böngészőben)")
        self.appjelszo_gomb.Bind(wx.EVT_BUTTON, self._app_jelszo_nyit)
        self.appjelszo_gomb.Hide()
        v.Add(self.appjelszo_gomb, 0, wx.ALL, 6)

        self.protokoll = wx.RadioBox(
            self, label="Protokoll", choices=["IMAP (ajánlott)", "POP3"],
            style=wx.RA_SPECIFY_ROWS)
        v.Add(self.protokoll, 0, wx.EXPAND | wx.ALL, 6)

        # haladó: szerverek ÉS portok (auto-kitöltve, kézzel felülírható – így
        # BÁRMILYEN POP/IMAP/SMTP-fiók (pl. Freemail, Citromail, céges) manuálisan
        # is beállítható)
        self.imap_host = sor("IMAP szerver:")
        self.imap_port = sor("IMAP port (alap: 993):")
        self.pop_host = sor("POP3 szerver:")
        self.pop_port = sor("POP3 port (alap: 995):")
        self.smtp_host = sor("SMTP szerver:")
        self.smtp_port = sor("SMTP port (alap: 465 SSL vagy 587 STARTTLS):")

        gs = wx.BoxSizer(wx.HORIZONTAL)
        teszt = wx.Button(self, label="Kapcsolat &tesztelése")
        teszt.Bind(wx.EVT_BUTTON, self._teszt)
        ment = wx.Button(self, wx.ID_OK, "M&entés")
        ment.Bind(wx.EVT_BUTTON, self._ment)
        gs.Add(teszt, 0, wx.RIGHT, 8)
        gs.Add(ment, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        self.SetSizer(v)
        if fiok:
            self._betolt(fiok)

    def _betolt(self, f):
        self.nev.SetValue(f.get("nev", ""))
        self.email.SetValue(f.get("email", ""))
        self.jelszo.SetValue(f.get("jelszo", ""))
        self.imap_host.SetValue(f.get("imap_host", ""))
        self.pop_host.SetValue(f.get("pop_host", ""))
        self.smtp_host.SetValue(f.get("smtp_host", ""))
        self.imap_port.SetValue(str(f.get("imap_port", "") or ""))
        self.pop_port.SetValue(str(f.get("pop_port", "") or ""))
        self.smtp_port.SetValue(str(f.get("smtp_port", "") or ""))
        self.protokoll.SetSelection(1 if f.get("protokoll") == "pop" else 0)

    def _auto(self, e):
        cim = self.email.GetValue().strip()
        ervenyes = "@" in cim and "." in cim.rsplit("@", 1)[-1]
        if ervenyes:
            # érvényes cím → a szervereket kitöltjük (a korábbi szemetet is
            # felülírva), és megjelenítjük a szolgáltató-specifikus segítséget
            k = MC.auto_konfig(cim)
            self.imap_host.SetValue(k["imap_host"])
            self.pop_host.SetValue(k["pop_host"])
            self.smtp_host.SetValue(k["smtp_host"])
            self.imap_port.SetValue(str(k["imap_port"]))
            self.pop_port.SetValue(str(k["pop_port"]))
            self.smtp_port.SetValue(str(k["smtp_port"]))
            if MC.app_jelszo_kell(cim):
                self.jelszo_info.SetLabel(MC.app_jelszo_utmutato(cim))
                self.appjelszo_gomb.Show(bool(MC.app_jelszo_url(cim)))
            else:
                self.jelszo_info.SetLabel(
                    "Ehhez a szolgáltatóhoz általában a sima fiókjelszó is "
                    "működik. Ha elutasít, hozz létre app-jelszót a fiókodnál.")
                self.appjelszo_gomb.Hide()
            self.Layout()
        elif cim:
            self.imap_host.SetValue("")
            self.pop_host.SetValue("")
            self.smtp_host.SetValue("")
            self.jelszo_info.SetLabel(
                "Írj be egy érvényes e-mail címet, kukac jellel "
                "(pl. valaki@gmail.com) – ez az első mező.")
            self.Layout()
        if e:
            e.Skip()

    def _app_jelszo_nyit(self, e):
        import webbrowser
        cim = self.email.GetValue().strip()
        url = MC.app_jelszo_url(cim)
        if url:
            webbrowser.open(url)
        _mondd(self.main, "Megnyitottam az app-jelszó oldalát a böngészőben. "
               + MC.app_jelszo_utmutato(cim))

    def _fiok_epit(self):
        felul = {
            "imap_host": self.imap_host.GetValue().strip(),
            "pop_host": self.pop_host.GetValue().strip(),
            "smtp_host": self.smtp_host.GetValue().strip(),
        }
        # a kézzel megadott portok felülírják az alapértelmezetteket
        for kulcs, mezo in (("imap_port", self.imap_port),
                            ("pop_port", self.pop_port),
                            ("smtp_port", self.smtp_port)):
            ertek = mezo.GetValue().strip()
            if ertek.isdigit():
                felul[kulcs] = int(ertek)
        prot = "pop" if self.protokoll.GetSelection() == 1 else "imap"
        return MC.uj_fiok(self.nev.GetValue(), self.email.GetValue().strip(),
                          self.jelszo.GetValue(), prot, felul)

    def _teszt(self, e):
        try:
            f = self._fiok_epit()
        except Exception as ex:
            self._hiba("Hibás adatok", ex)
            return
        _mondd(self.main, "Kapcsolat tesztelése…")

        def munka():
            k = _kliens(f).kapcsolodik()
            if isinstance(k, MC.ImapKliens):
                k.valaszt("INBOX")
            k.bezar()
            return True
        _hatterben(munka,
                   lambda r: _mondd(self.main, "A kapcsolat rendben! "
                                    "Mentheted a fiókot."),
                   lambda ex: self._hiba("A kapcsolat nem jött létre", ex))

    def _ment(self, e):
        try:
            f = self._fiok_epit()
        except Exception as ex:
            self._hiba("Hibás adatok", ex)
            return
        if not f["email"] or "@" not in f["email"]:
            self._hiba("Hiányzó adat", Exception("Adj meg érvényes e-mail címet."))
            return
        if not f["jelszo"]:
            self._hiba("Hiányzó jelszó",
                       Exception("Adj meg jelszót vagy app-jelszót."))
            return
        self.eredmeny = f
        self.EndModal(wx.ID_OK)

    def _hiba(self, cim, ex):
        uz = f"{cim}: {ex}"
        _mondd(self.main, uz)
        wx.MessageBox(uz, cim, wx.OK | wx.ICON_ERROR, self)


# ======================================================================
#  Címjegyzék-választó (beszúrás Címzett / Másolat / Titkos mezőbe)
# ======================================================================
class CimjegyzekValaszto(wx.Dialog):
    def __init__(self, iro, main):
        super().__init__(iro, title="Címjegyzék", size=(560, 480),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._iro = iro
        self.main = main
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Keresés (név vagy e-mail):"),
              0, wx.LEFT | wx.TOP, 8)
        self.szuro = wx.TextCtrl(p)
        self.szuro.SetName("Keresés a címjegyzékben")
        self.szuro.Bind(wx.EVT_TEXT, lambda e: self._frissit())
        v.Add(self.szuro, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Címek (Ctrl/Shift: több is):"),
              0, wx.LEFT, 8)
        self.lista = wx.ListBox(p, style=wx.LB_EXTENDED)
        self.lista.SetName("Címjegyzék")
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
        s = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, mezo in (("→ &Címzett", "cimzett"),
                            ("→ &Másolat (Cc)", "masolat"),
                            ("→ &Titkos (Bcc)", "titkos")):
            b = wx.Button(p, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, m=mezo: self._beilleszt(m))
            s.Add(b, 0, wx.RIGHT, 6)
        be = wx.Button(p, wx.ID_CLOSE, "&Bezárás")
        be.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        s.Add(be, 0)
        v.Add(s, 0, wx.ALL, 8)
        p.SetSizer(v)
        self._frissit()
        wx.CallAfter(self.szuro.SetFocus)

    def _frissit(self):
        self._talalatok = MC.cimjegyzek_kereses(self.szuro.GetValue())
        self.lista.Set(
            [MC.cimjegyzek_megjelenit(c) for c in self._talalatok]
            or ["(a címjegyzék üres – ahogy levelet küldesz/kapsz, feltöltődik)"])

    def _beilleszt(self, mezo_nev):
        idx = self.lista.GetSelections()
        if not idx or not self._talalatok:
            _mondd(self.main, "Előbb jelölj ki legalább egy címet.")
            return
        cimek = [MC.cimjegyzek_megjelenit(self._talalatok[i]) for i in idx
                 if 0 <= i < len(self._talalatok)]
        mezo = getattr(self._iro, mezo_nev)
        meglevo = mezo.GetValue().strip()
        ujj = ", ".join(cimek)
        mezo.SetValue((meglevo + ", " + ujj) if meglevo else ujj)
        _mondd(self.main, f"{len(cimek)} cím beillesztve.")


# ======================================================================
#  Levélíró
# ======================================================================
def _helyi_piszkozat(msg) -> str:
    """Tartalék: a piszkozat mentése a saját gépre .eml-ként (POP3-fióknál vagy
    ha a szolgáltatónál nincs Piszkozatok mappa)."""
    import time as _ido
    mappa = Path.home() / ".superdl" / "mail_piszkozatok"
    mappa.mkdir(parents=True, exist_ok=True)
    nev = _ido.strftime("piszkozat_%Y-%m-%d_%H-%M-%S.eml")
    ut = mappa / nev
    ut.write_bytes(msg.as_bytes() if hasattr(msg, "as_bytes") else bytes(msg))
    return str(ut)


class HaromValaszDialog(wx.Dialog):
    """Háromgombos, FELOLVASOTT kérdés (Igen / Nem / Mégsem). Saját ablak, mert
    a Windows beépített háromgombos párbeszédét nem minden képernyőolvasó
    kezeli egyformán; itt minden gomb tabulátorral elérhető és nevesített."""

    def __init__(self, parent, cim, kerdes, igen, nem, megsem, main=None):
        super().__init__(parent, title=cim)
        v = wx.BoxSizer(wx.VERTICAL)
        szoveg = wx.StaticText(self, label=kerdes)
        szoveg.SetName(kerdes)
        v.Add(szoveg, 0, wx.ALL, 14)
        gs = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, azon, alap in ((igen, wx.ID_YES, True), (nem, wx.ID_NO, False),
                                  (megsem, wx.ID_CANCEL, False)):
            b = wx.Button(self, azon, cimke)
            b.SetName(cimke.replace("&", ""))
            b.Bind(wx.EVT_BUTTON, lambda e, a=azon: self.EndModal(a))
            if alap:
                b.SetDefault()
                b.SetFocus()
            gs.Add(b, 0, wx.RIGHT, 8)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 12)
        self.SetSizerAndFit(v)
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()
        if main is not None:
            wx.CallAfter(_mondd, main, "%s %s, %s, vagy %s."
                         % (kerdes, igen.replace("&", ""), nem.replace("&", ""),
                            megsem.replace("&", "")))


class KuldesKerdesDialog(wx.Dialog):
    """Küldés megerősítése – PIPÁVAL, hogy legközelebb ne kérdezzen.
    A pipa saját vezérlő (nem a Windows task-dialógusáé), így biztosan
    felolvasható és tabulátorral elérhető. A Beállítások → Általános fülön
    bármikor visszakapcsolható – egy kikapcsolt kérdés ne legyen egyirányú."""

    def __init__(self, parent, cimzett, main=None):
        super().__init__(parent, title="Küldés megerősítése")
        v = wx.BoxSizer(wx.VERTICAL)
        kerdes = "Elküldöd a levelet ide: %s?" % cimzett
        st = wx.StaticText(self, label=kerdes)
        st.SetName(kerdes)
        v.Add(st, 0, wx.ALL, 14)
        self.pipa = wx.CheckBox(self, label="&Ne kérdezze meg többé")
        self.pipa.SetName("Ne kérdezze meg többé a küldés előtt; a "
                          "Beállítások Általános fülén visszakapcsolható")
        v.Add(self.pipa, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
        gs = wx.BoxSizer(wx.HORIZONTAL)
        b_ok = wx.Button(self, wx.ID_YES, "&Küldés")
        b_ok.SetDefault()
        b_ok.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES))
        b_no = wx.Button(self, wx.ID_NO, "&Mégsem")
        b_no.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_NO))
        gs.Add(b_ok, 0, wx.RIGHT, 8)
        gs.Add(b_no, 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 12)
        self.SetSizerAndFit(v)
        self.SetEscapeId(wx.ID_NO)
        self.CentreOnParent()
        b_ok.SetFocus()
        if main is not None:
            wx.CallAfter(_mondd, main, kerdes + " Küldés, vagy Mégsem. "
                         "Pipával kérheted, hogy többé ne kérdezzen.")


class AiLevelDialog(wx.Dialog):
    """LEVÉL ÍRÁSA AI-VAL. Megmondod, kinek és miről; választasz hangnemet,
    megszólítást és hosszt; a kész szöveget elfogadod, pontosítod vagy
    újragenerálod. Elfogadáskor AZONNAL a levélbe kerül.

    ADATVÉDELEM: a leírás – és ha kéred, a megválaszolandó levél – elmegy a
    VÁLASZTOTT AI-szolgáltatóhoz, a TE kulcsoddal. Csatolmányt sosem küldünk."""

    def __init__(self, parent, main, cimzett="", eredeti=""):
        super().__init__(parent, title="Levél írása AI-val",
                         size=(700, 640),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self._eredeti = eredeti or ""
        self._eredmeny = ""
        self._targy = ""
        self._fut = False
        cfg = MC.altalanos_betolt()

        v = wx.BoxSizer(wx.VERTICAL)
        fej = wx.StaticText(self, label=(
            "A megadott leírás%s elmegy a beállított AI-szolgáltatóhoz (a te "
            "kulcsoddal). Csatolmányt sosem küldünk el."
            % (" és a megválaszolandó levél" if self._eredeti else "")))
        fej.Wrap(660)
        v.Add(fej, 0, wx.ALL, 10)

        s1 = wx.BoxSizer(wx.HORIZONTAL)
        s1.Add(wx.StaticText(self, label="&Kinek írunk?"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.kinek = wx.TextCtrl(self, value=cimzett)
        self.kinek.SetName("Kinek írunk")
        s1.Add(self.kinek, 1)
        v.Add(s1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        v.Add(wx.StaticText(self, label="&Miről szóljon a levél?"), 0,
              wx.LEFT | wx.TOP, 10)
        self.mirol = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 80))
        self.mirol.SetName("Miről szóljon a levél")
        self.mirol.SetHint("pl. lemondom a keddi időpontot, kérek újat jövő hétre")
        v.Add(self.mirol, 0, wx.EXPAND | wx.ALL, 10)

        r = wx.BoxSizer(wx.HORIZONTAL)
        self.hangnem = wx.RadioBox(
            self, label="&Hangnem", majorDimension=1,
            choices=[n for _, n, _ in AI.HANGNEMEK])
        self.megszolitas = wx.RadioBox(
            self, label="Meg&szólítás", majorDimension=1,
            choices=[n for _, n, _ in AI.MEGSZOLITASOK])
        self.hossz = wx.RadioBox(
            self, label="H&ossz", majorDimension=1,
            choices=["%s (%d–%d karakter)" % (n, a, b)
                     for _, n, a, b in AI.HOSSZAK])
        for doboz, kulcs, lista in ((self.hangnem, "ai_hangnem", AI.HANGNEMEK),
                                    (self.megszolitas, "ai_megszolitas",
                                     AI.MEGSZOLITASOK),
                                    (self.hossz, "ai_hossz", AI.HOSSZAK)):
            mentett = cfg.get(kulcs)
            kulcsok = [x[0] for x in lista]
            doboz.SetSelection(kulcsok.index(mentett) if mentett in kulcsok else 0)
            r.Add(doboz, 0, wx.RIGHT, 10)
        v.Add(r, 0, wx.LEFT | wx.RIGHT, 10)

        self.eredetit = wx.CheckBox(
            self, label="&Vegye figyelembe a megválaszolandó levelet is")
        self.eredetit.SetValue(bool(self._eredeti))
        self.eredetit.Enable(bool(self._eredeti))
        v.Add(self.eredetit, 0, wx.ALL, 10)

        g1 = wx.BoxSizer(wx.HORIZONTAL)
        self.b_gen = wx.Button(self, label="&Generálás")
        self.b_gen.SetDefault()
        self.b_gen.Bind(wx.EVT_BUTTON, lambda e: self._general())
        g1.Add(self.b_gen, 0, wx.RIGHT, 8)
        v.Add(g1, 0, wx.LEFT | wx.BOTTOM, 10)

        v.Add(wx.StaticText(self, label="A &kész levél (szerkeszthető):"), 0,
              wx.LEFT, 10)
        self.szoveg = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 180))
        self.szoveg.SetName("A generált levél szövege, szerkeszthető")
        v.Add(self.szoveg, 1, wx.EXPAND | wx.ALL, 10)

        g2 = wx.BoxSizer(wx.HORIZONTAL)
        self.b_ok = wx.Button(self, wx.ID_OK, "&Beillesztés a levélbe")
        self.b_pont = wx.Button(self, label="&Pontosítás…")
        self.b_pont.Bind(wx.EVT_BUTTON, lambda e: self._pontositas())
        self.b_ujra = wx.Button(self, label="Ú&jra")
        self.b_ujra.Bind(wx.EVT_BUTTON, lambda e: self._general())
        for b in (self.b_ok, self.b_pont, self.b_ujra):
            b.Enable(False)
            g2.Add(b, 0, wx.RIGHT, 8)
        g2.Add(wx.Button(self, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(g2, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        self.SetSizer(v)
        self.CentreOnParent()
        self.mirol.SetFocus()

    # -- generálás --------------------------------------------------------

    def _general(self, pontositas: str = ""):
        mirol = self.mirol.GetValue().strip()
        if not mirol and not pontositas:
            _mondd(self.main, "Előbb írd le, miről szóljon a levél.")
            self.mirol.SetFocus()
            return
        if self._fut:
            return
        self._fut = True
        self.b_gen.Enable(False)
        _mondd(self.main, "A levél készül…")
        kulcsok = ([x[0] for x in AI.HANGNEMEK][self.hangnem.GetSelection()],
                   [x[0] for x in AI.MEGSZOLITASOK][self.megszolitas.GetSelection()],
                   [x[0] for x in AI.HOSSZAK][self.hossz.GetSelection()])
        cfg = MC.altalanos_betolt()
        cfg.update({"ai_hangnem": kulcsok[0], "ai_megszolitas": kulcsok[1],
                    "ai_hossz": kulcsok[2]})
        MC.altalanos_ment(cfg)
        eredeti = self._eredeti if self.eredetit.GetValue() else ""
        kerdes = AI.prompt_epit(mirol, self.kinek.GetValue(), kulcsok[0],
                                kulcsok[1], kulcsok[2], eredeti, pontositas,
                                self.szoveg.GetValue())

        def munka():
            from superdl import aiclient
            szoveg = AI.valasz_tisztit(aiclient.chat(kerdes, AI.RENDSZER))
            targy = ""
            try:
                targy = AI.targy_tisztit(aiclient.chat(AI.targy_prompt(szoveg)))
            except Exception:
                pass
            return szoveg, targy

        _hatterben(munka, self._kesz, self._hiba)

    def _kesz(self, eredmeny):
        szoveg, targy = eredmeny
        self._fut = False
        self.b_gen.Enable(True)
        self._eredmeny, self._targy = szoveg, targy
        self.szoveg.SetValue(szoveg)
        for b in (self.b_ok, self.b_pont, self.b_ujra):
            b.Enable(True)
        self.szoveg.SetFocus()
        _mondd(self.main, "Elkészült, %d karakter. Elfogadhatod, pontosíthatod, "
               "vagy kérhetsz újat." % len(szoveg))

    def _hiba(self, ex):
        self._fut = False
        self.b_gen.Enable(True)
        uz = str(ex)
        if "kulcs" in uz.lower() or "key" in uz.lower() or "provider" in uz.lower():
            uz = ("Ehhez AI-kulcs kell. A főablakban: AI menü → AI-beállítások, "
                  "vagy Súgó → AI-kulcsok beszerzése.")
        _mondd(self.main, "Nem sikerült: " + uz)
        wx.MessageBox(uz, "AI-levélírás", wx.OK | wx.ICON_ERROR, self)

    def _pontositas(self):
        d = wx.TextEntryDialog(self, "Mit írjon át? (pl. legyen rövidebb, "
                               "hagyd ki a bocsánatkérést, tegeződjön)",
                               "Pontosítás")
        if d.ShowModal() == wx.ID_OK and d.GetValue().strip():
            self._general(pontositas=d.GetValue().strip())
        d.Destroy()

    def levelszoveg(self):
        return self.szoveg.GetValue().strip()

    def javasolt_targy(self):
        return self._targy


class KetMezosDialog(wx.Dialog):
    """Két beviteli mező (pl. webcím + megjelenő szöveg), felolvasott súgóval.
    A második mező SZÁNDÉKOSAN nem kötelező – a felhasználó kérése szerint a
    magyarázó szöveg elhagyható."""

    def __init__(self, parent, cim, cimke1, cimke2, main=None, sugo=""):
        super().__init__(parent, title=cim, size=(560, -1))
        v = wx.BoxSizer(wx.VERTICAL)
        if sugo:
            st = wx.StaticText(self, label=sugo)
            st.Wrap(520)
            st.SetName(sugo)
            v.Add(st, 0, wx.ALL, 12)
        self._m1 = self._sor(v, cimke1)
        self._m2 = self._sor(v, cimke2)
        gs = wx.BoxSizer(wx.HORIZONTAL)
        ok = wx.Button(self, wx.ID_OK, "&Beszúrás")
        ok.SetDefault()
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 12)
        self.SetSizerAndFit(v)
        self.CentreOnParent()
        self._m1.SetFocus()
        if main is not None and sugo:
            wx.CallAfter(_mondd, main, "%s %s" % (cim, sugo))

    def _sor(self, v, cimke):
        s = wx.BoxSizer(wx.HORIZONTAL)
        st = wx.StaticText(self, label=cimke)
        ctrl = wx.TextCtrl(self, size=(340, -1))
        ctrl.SetName(cimke.replace("&", "").rstrip(":"))
        s.Add(st, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        s.Add(ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(s, 0, wx.EXPAND | wx.ALL, 8)
        return ctrl

    def ertek1(self):
        return self._m1.GetValue().strip()

    def ertek2(self):
        return self._m2.GetValue().strip()


class LevelIroDialog(wx.Dialog):
    def __init__(self, parent, main, fiok, cimzett="", targy="", torzs="",
                 valasz_id=None, torzsre=False):
        super().__init__(parent, title="Új levél", size=(640, 560),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.fiok = fiok
        self.valasz_id = valasz_id
        self._csatolmanyok = []
        self._kepek = []          # a levél TESTÉBE ágyazott képek
        v = wx.BoxSizer(wx.VERTICAL)

        # A címke MINDIG a mező ELŐTT jön létre (z-sorrend) – hogy a
        # képernyőolvasó ne eltolva olvassa a címkéket.
        def sor(cimke, **kw):
            s = wx.BoxSizer(wx.HORIZONTAL)
            st = wx.StaticText(self, label=cimke)
            ctrl = wx.TextCtrl(self, **kw)
            ctrl.SetName(cimke.replace("&", "").rstrip(":"))
            s.Add(st, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            s.Add(ctrl, 1)
            v.Add(s, 0, wx.EXPAND | wx.ALL, 6)
            return ctrl

        self.cimzett = sor("&Címzett:", value=cimzett)
        self.masolat = sor("&Másolat (Cc):")
        self.titkos = sor("&Titkos másolat (Bcc):")
        self.targy = sor("&Tárgy:", value=targy)
        # autókiegészítés a címjegyzékből (fel/le nyíllal a beírt szöveg alapján)
        self._cimjegyzek_autocomplete()

        self.torzs = wx.TextCtrl(self, value=torzs,
                                 style=wx.TE_MULTILINE | wx.TE_RICH2)
        # A fix zárósort a mező NEVÉBEN mondjuk ki (a képernyőolvasó a mezőre
        # lépéskor felolvassa) – így senkit nem ér meglepetés, de nem is
        # szövegelünk minden ablaknyitáskor.
        self.torzs.SetName("Levél szövege; a levél aljára automatikusan "
                           "odakerül: %s" % MC.FIX_ZAROSOR)
        v.Add(self.torzs, 1, wx.EXPAND | wx.ALL, 6)
        self.csat_cimke = wx.StaticText(self, label="Csatolmány: nincs")
        v.Add(self.csat_cimke, 0, wx.LEFT, 8)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        cj = wx.Button(self, label="📇 &Címjegyzék…")
        cj.Bind(wx.EVT_BUTTON, self._cimjegyzek_nyit)
        # BESZÚRÁS: valódi felugró menü (a képernyőolvasók a menüket jól
        # kezelik), plusz minden pontnak van saját gyorsbillentyűje is.
        ai = wx.Button(self, label="🤖 &AI-levél…")
        ai.SetName("Levél írása AI-val – AI-kulcs szükséges hozzá")
        ai.SetToolTip("A megadott leírásból megírja a levelet (AI-kulcs kell)")
        ai.Bind(wx.EVT_BUTTON, lambda e: self._ai_level())
        besz = wx.Button(self, label="➕ &Beszúrás…")
        besz.SetName("Beszúrás: hivatkozás, kép, videó-hivatkozás")
        besz.Bind(wx.EVT_BUTTON, lambda e: self._beszuras_menu(besz))
        cs = wx.Button(self, label="📎 Csatolmány &hozzáadása")
        cs.Bind(wx.EVT_BUTTON, self._csatol)
        kb = wx.Button(self, wx.ID_OK, "&Küldés  (Ctrl+Enter)")
        kb.Bind(wx.EVT_BUTTON, self._kuld)
        gs.Add(cj, 0, wx.RIGHT, 8)
        gs.Add(ai, 0, wx.RIGHT, 8)
        gs.Add(besz, 0, wx.RIGHT, 8)
        gs.Add(cs, 0, wx.RIGHT, 8)
        gs.Add(kb, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        self.SetSizer(v)
        # CTRL+ENTER = küldés (mint az Outlookban) – bárhonnan az ablakban
        self.Bind(wx.EVT_CHAR_HOOK, self._iro_billentyu)
        # HELYESÍRÁS: helyi menü (jobb gomb / Alkalmazás billentyű) a szövegen
        self._helyesiras = None
        self.torzs.Bind(wx.EVT_CONTEXT_MENU, self._helyi_menu)

        # VÁLASZNÁL egyből a LEVÉL SZÖVEGÉBE ugrunk, a kurzor az elejére – az
        # idézet FÖLÉ –, hogy csak írni kelljen (felhasználói kérés). A címzett
        # és a tárgy ilyenkor már ki van töltve, azokon nincs mit tenni. Új
        # levélnél és TOVÁBBÍTÁSNÁL marad a Címzett, mert ott az az első dolog.
        # ALÁÍRÁS: a felhasználó SZERKESZTHETŐ aláírása bekerül a szövegbe (így
        # látja, hallja és bele is írhat), válasznál az IDÉZET FÖLÉ. A fix
        # zárósor NEM itt, hanem küldéskor kerül a legaljára.
        self._alairas_beszur(torzs)
        self._kuldve = False
        self._indulo_allapot = self._allapot()      # ehhez mérjük a változást
        self.Bind(wx.EVT_CLOSE, self._on_iro_close)
        # az Esc / Mégsem gomb is a piszkozat-kérdésen menjen át
        self.Bind(wx.EVT_BUTTON, self._on_iro_close, id=wx.ID_CANCEL)

        if torzsre:
            self.torzs.SetInsertionPoint(0)
            wx.CallAfter(self.torzs.SetFocus)
            wx.CallAfter(self.torzs.SetInsertionPoint, 0)

    # ---- helyesírás-ellenőrzés ----
    def _helyesiras_be(self):
        """Be van-e kapcsolva a küldés előtti ellenőrzés (elmentett beállítás)."""
        return bool(MC.altalanos_betolt().get("helyesiras", True))

    def _helyi_menu(self, e):
        """A levél szövegének HELYI MENÜJE – innen kapcsolható a helyesírás-
        ellenőrzés, és innen indítható azonnal (a tesztelő kérése)."""
        m = wx.Menu()
        it_most = m.Append(wx.ID_ANY, "Helyesírás-ellenőrzés &most\tF7")
        self.Bind(wx.EVT_MENU, lambda ev: self._helyesiras_futtat(), it_most)
        it_be = m.AppendCheckItem(
            wx.ID_ANY, "Ellenőrzés &küldés előtt (be/ki)")
        it_be.Check(self._helyesiras_be())

        def valt(ev):
            cfg = MC.altalanos_betolt()
            uj = not bool(cfg.get("helyesiras", True))
            cfg["helyesiras"] = uj
            MC.altalanos_ment(cfg)
            _mondd(self.main, "Helyesírás-ellenőrzés küldés előtt: "
                   + ("bekapcsolva." if uj else "kikapcsolva."))
        self.Bind(wx.EVT_MENU, valt, it_be)
        self.PopupMenu(m)
        m.Destroy()

    def _ellenorzo(self):
        if self._helyesiras is None:
            from .helyesiras import Ellenorzo
            self._helyesiras = Ellenorzo()
        return self._helyesiras

    def _helyesiras_futtat(self, csendes=False):
        """Ellenőrzés + javító párbeszéd. Visszaad: True, ha mehet a küldés."""
        e = self._ellenorzo()
        if not e.elerheto:
            if not csendes:
                _mondd(self.main, e.hiba_oka)
                wx.MessageBox(e.hiba_oka, "Helyesírás-ellenőrzés",
                              wx.OK | wx.ICON_INFORMATION, self)
            return True                     # ne akadályozza a küldést
        szoveg = self.torzs.GetValue()
        if not e.ellenoriz(szoveg):
            if not csendes:
                _mondd(self.main, "Nem találtam helyesírási hibát. ")
            return True
        dlg = HelyesirasDialog(self, self.main, e, szoveg)
        dlg.ShowModal()
        self.torzs.SetValue(dlg.szoveg)     # a javított szöveg vissza
        dlg.Destroy()
        return True

    def _iro_billentyu(self, e):
        k = e.GetKeyCode()
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and e.ControlDown():
            self._kuld(None)
        elif k == wx.WXK_F7:               # F7 = helyesírás (mint az Office-ban)
            self._helyesiras_futtat()
        elif k in (ord("S"), ord("s")) and e.ControlDown():
            self._piszkozat_ment(bezar=False)     # Ctrl+S: mentés menet közben
        elif k in (ord("K"), ord("k")) and e.ControlDown() and e.ShiftDown():
            self._beszur_kep()
        elif k in (ord("K"), ord("k")) and e.ControlDown():
            self._beszur_link()
        elif k in (ord("V"), ord("v")) and e.ControlDown():
            # Ctrl+V: ha a vágólapon FÁJL vagy KÉP van, csatolmány lesz belőle;
            # sima szövegnél megy a szokásos beillesztés.
            if not self._vagolap_csatolmany():
                e.Skip()
        else:
            e.Skip()

    # ---- AI-levélírás --------------------------------------------------

    def _ai_level(self):
        """Levél írása AI-val. Az elfogadott szöveg AZONNAL a levélbe kerül –
        a kurzor helyére, az aláírás fölé –, semmi másolgatás."""
        eredeti = ""
        if self.valasz_id:                    # válasznál az idézetet adjuk át
            eredeti = re.sub(r"^> ?", "", self.torzs.GetValue(), flags=re.M)
        d = AiLevelDialog(self, self.main, self.cimzett.GetValue().strip(),
                          eredeti)
        if d.ShowModal() == wx.ID_OK:
            szoveg = d.levelszoveg()
            if szoveg:
                regi = self.torzs.GetValue()
                self.torzs.SetValue(szoveg + ("\n" + regi if regi else ""))
                self.torzs.SetInsertionPoint(0)
                self.torzs.SetFocus()
                if not self.targy.GetValue().strip() and d.javasolt_targy():
                    self.targy.SetValue(d.javasolt_targy())
                    _mondd(self.main, "A levél bekerült. Javasolt tárgy: %s"
                           % d.javasolt_targy())
                else:
                    _mondd(self.main, "A levél bekerült a szerkesztőbe.")
        d.Destroy()

    # ---- beszúrás (hivatkozás, kép, videó) -----------------------------

    def _beszuras_menu(self, honnan=None):
        m = wx.Menu()
        pontok = ((("&Hivatkozás…\tCtrl+K"), self._beszur_link),
                  (("&Kép a levélbe…\tCtrl+Shift+K"), self._beszur_kep),
                  (("&Videó-hivatkozás…"), self._beszur_video),
                  (("&Csatolmány…"), lambda: self._csatol(None)))
        for cimke, fv in pontok:
            it = m.Append(wx.ID_ANY, cimke)
            self.Bind(wx.EVT_MENU, lambda e, f=fv: f(), it)
        self.PopupMenu(m, honnan.GetPosition() if honnan else wx.DefaultPosition)
        m.Destroy()

    def _torzsbe_ir(self, szoveg: str, bemondas: str = "") -> None:
        """A kurzor helyére szúrja a jelölést, és a fókusz marad a szövegen."""
        self.torzs.WriteText(szoveg)
        self.torzs.SetFocus()
        if bemondas:
            _mondd(self.main, bemondas)

    def _beszur_link(self):
        d = KetMezosDialog(
            self, "Hivatkozás beszúrása", "&Webcím (URL):",
            "&Megjelenő szöveg (nem kötelező):", self.main,
            sugo="Ha a megjelenő szöveget üresen hagyod, maga a webcím látszik.")
        if d.ShowModal() == wx.ID_OK:
            url, cimke = d.ertek1(), d.ertek2()
            if url:
                if not re.match(r"^[a-z]+://", url, re.I):
                    url = "https://" + url         # a puszta domaint kiegészítjük
                self._torzsbe_ir("[%s](%s)" % (cimke, url) if cimke else url,
                                 "Hivatkozás beszúrva."
                                 + (" Megjelenő szöveg: %s." % cimke if cimke
                                    else " A címzett a webcímet fogja látni."))
        d.Destroy()

    def _beszur_kep(self):
        dlg = wx.FileDialog(
            self, "Kép a levélbe",
            wildcard="Képek (*.png;*.jpg;*.jpeg;*.gif;*.bmp)|"
                     "*.png;*.jpg;*.jpeg;*.gif;*.bmp|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            ut = dlg.GetPath()
            self._kepek.append(ut)
            nev = os.path.basename(ut)
            self._torzsbe_ir("\n[kép: %s]\n" % nev,
                             "Kép beszúrva a levél testébe: %s. A címzett a "
                             "levélben látja majd." % nev)
        dlg.Destroy()

    def _beszur_video(self):
        d = KetMezosDialog(
            self, "Videó-hivatkozás beszúrása", "A videó &webcíme:",
            "&Megjelenő szöveg (nem kötelező):", self.main,
            sugo="Fontos: videót nem lehet lejátszhatóan beágyazni levélbe – "
                 "egyetlen levelező sem támogatja biztonsági okból. Ide "
                 "KATTINTHATÓ HIVATKOZÁS kerül, ami a címzett böngészőjében "
                 "nyílik meg.")
        if d.ShowModal() == wx.ID_OK:
            url, cimke = d.ertek1(), d.ertek2()
            if url:
                if not re.match(r"^[a-z]+://", url, re.I):
                    url = "https://" + url
                self._torzsbe_ir("[%s](%s)" % (cimke or "Videó megtekintése",
                                               url),
                                 "Videó-hivatkozás beszúrva.")
        d.Destroy()

    # ---- nagy fájlok ---------------------------------------------------

    def _szerver_korlat(self) -> int:
        """A fiók SMTP-kiszolgálójának valódi méretkorlátja, fiókonként
        megjegyezve (a lekérdezés egy kapcsolatot igényel, ne csináljuk
        minden küldésnél)."""
        kulcs = "smtp_korlat_" + (self.fiok.get("email") or "")
        cfg = MC.altalanos_betolt()
        if cfg.get(kulcs):
            return int(cfg[kulcs])
        try:
            korlat = MC.SmtpKuldo(self.fiok).max_meret()
        except Exception:
            korlat = 0
        if korlat:
            cfg[kulcs] = int(korlat)
            MC.altalanos_ment(cfg)
        return korlat or MC.ALAP_MERETKORLAT

    def _nagy_fajl_rendez(self) -> bool:
        """Ha a levél nem férne át, három választást adunk. False = ne küldjünk."""
        if not (self._csatolmanyok or self._kepek):
            return True
        meret = MC.becsult_meret(self.torzs.GetValue(), self._csatolmanyok,
                                 self._kepek)
        korlat = self._szerver_korlat()
        if meret <= korlat:
            return True
        uzenet = ("A levél kb. %s lenne, a szolgáltatód viszont legfeljebb %s-ot "
                  "enged át.\n\nMit tegyünk a nagy fájllal?"
                  % (MC.meret_szoveg(meret), MC.meret_szoveg(korlat)))
        d = HaromValaszDialog(
            self, "Nagy fájl", uzenet,
            "&Feltöltés megosztóra, link a levélbe",
            "&P2P fájlküldés (titkosított, felhő nélkül)",
            "&Mégsem (nem küldöm el)", self.main)
        valasz = d.ShowModal()
        d.Destroy()
        if valasz == wx.ID_YES:
            return self._feltoltes_megosztora()
        if valasz == wx.ID_NO:
            self._p2p_ajanlat()
            return False
        return False

    def _feltoltes_megosztora(self) -> bool:
        """Feltöltés – de CSAK kifejezett, tájékozott engedéllyel: ezek a
        tárhelyek NYILVÁNOSAK, akinek megvan a link, letöltheti."""
        nevek = ", ".join(os.path.basename(u) for u in self._csatolmanyok)
        figyelmeztetes = (
            "A fájl(ok) egy NYILVÁNOS megosztóra kerülnek (filebin.net), és "
            "akinek megvan a link, LETÖLTHETI – nincs titkosítás, nincs "
            "jelszó. A fájl néhány nap múlva magától törlődik.\n\n"
            "Bizalmas anyagot inkább a P2P fájlküldéssel küldj.\n\n"
            "Feltöltsem ezeket: %s?" % nevek)
        _mondd(self.main, figyelmeztetes)
        if wx.MessageBox(figyelmeztetes, "Feltöltés nyilvános megosztóra",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                         self) != wx.YES:
            return False
        kesz, hibak = [], []
        for ut in list(self._csatolmanyok):
            _mondd(self.main, "Feltöltés: %s…" % os.path.basename(ut))
            try:
                kesz.append(MC.megoszto_feltolt(ut))
            except Exception as ex:
                hibak.append("%s: %s" % (os.path.basename(ut), ex))
        if hibak:
            uz = ("A feltöltés nem sikerült: %s. A levelet nem küldtem el."
                  % "; ".join(hibak))
            _mondd(self.main, uz)
            wx.MessageBox(uz, "Feltöltés", wx.OK | wx.ICON_ERROR, self)
            return False
        self.torzs.SetValue(self.torzs.GetValue().rstrip() + "\n"
                            + MC.nagy_fajl_szoveg(kesz))
        self._csatolmanyok = []          # a fájlok már a linken vannak
        self._csat_frissit()
        _mondd(self.main, "Kész: %d fájl feltöltve, a hivatkozás bekerült a "
               "levélbe." % len(kesz))
        return True

    def _p2p_ajanlat(self) -> None:
        """A P2P küldés a SuperDL SAJÁT modulja: végpontok közötti titkosítás,
        semmilyen külső tárhely. Cserébe MINDKÉT gépnek online kell lennie az
        átvitel alatt – ezt ki is mondjuk, mert enélkül félrevezető lenne."""
        _mondd(self.main, "P2P fájlküldés választva.")
        wx.MessageBox(
            "A P2P fájlküldésnél a fájl közvetlenül a másik gépre megy, "
            "végpontok közötti titkosítással – semmilyen külső tárhelyre nem "
            "kerül fel.\n\nFONTOS: ehhez MINDKÉT gépnek online kell lennie az "
            "átvitel alatt, tehát előbb beszéljétek meg.\n\n"
            "Nyisd meg: Eszközök → P2P fájlküldés (a Modulkezelőből "
            "telepíthető), és a kapott kódot írd bele a levélbe.\n\n"
            "A levél most nem ment el – küldd el, ha a kód megvan.",
            "P2P fájlküldés", wx.OK | wx.ICON_INFORMATION, self)

    # ---- vágólap: fájl vagy kép beillesztése csatolmányként ------------

    def _vagolap_csatolmany(self) -> bool:
        """Ctrl+V-re: ha a vágólapon FÁJL vagy KÉP van, csatolmány lesz belőle.
        Sima szövegnél False, és akkor a szokásos beillesztés fut le."""
        if not wx.TheClipboard.Open():
            return False
        try:
            fajlok = wx.FileDataObject()
            if wx.TheClipboard.GetData(fajlok):
                utak = list(fajlok.GetFilenames())
                if utak:
                    self._csatolmanyok.extend(utak)
                    self._csat_frissit()
                    _mondd(self.main, "Csatolva: %s."
                           % ", ".join(os.path.basename(u) for u in utak))
                    return True
            kep = wx.BitmapDataObject()
            if wx.TheClipboard.GetData(kep):
                import time as _ido
                mappa = Path.home() / ".superdl" / "mail_vagolap"
                mappa.mkdir(parents=True, exist_ok=True)
                nev = _ido.strftime("kep_%Y-%m-%d_%H-%M-%S.png")
                ut = str(mappa / nev)
                kep.GetBitmap().ConvertToImage().SaveFile(ut, wx.BITMAP_TYPE_PNG)
                self._csatolmanyok.append(ut)
                self._csat_frissit()
                _mondd(self.main, "A vágólapon lévő kép csatolva: %s." % nev)
                return True
        except Exception:
            return False
        finally:
            wx.TheClipboard.Close()
        return False

    def _csat_frissit(self):
        nevek = [os.path.basename(u) for u in self._csatolmanyok]
        self.csat_cimke.SetLabel("Csatolmány: " + (", ".join(nevek) or "nincs"))

    # ---- aláírás -------------------------------------------------------

    def _alairas_beszur(self, eredeti_torzs: str) -> None:
        """Az aláírás a levél TETEJE (a te szövegednek hagyott hely) és az
        esetleges IDÉZET közé kerül – ez a szokásos magyar levelezési sorrend.
        Ha az aláírás üres (a felhasználó törölte), nem teszünk semmit."""
        alairas = (MC.altalanos_betolt().get("alairas", MC.ALAP_ALAIRAS) or "").strip()
        if not alairas:
            return
        blokk = "\n\n-- \n" + alairas + "\n"
        idezet = eredeti_torzs or ""
        self.torzs.SetValue(blokk + idezet if idezet else blokk)

    # ---- piszkozat -----------------------------------------------------

    def _allapot(self) -> tuple:
        return (self.cimzett.GetValue(), self.masolat.GetValue(),
                self.titkos.GetValue(), self.targy.GetValue(),
                self.torzs.GetValue(), tuple(self._csatolmanyok))

    def _valtozott(self) -> bool:
        """Írt-e egyáltalán valamit? Csak akkor kérdezünk piszkozatról, ha IGEN
        – egy érintetlenül bezárt válasz-ablak (címzett, tárgy, idézet, aláírás)
        ne nyaggassa a felhasználót."""
        return self._allapot() != getattr(self, "_indulo_allapot", None)

    def _piszkozat_uzenet(self):
        return MC.level_epit(
            MC.felado_fejlec(self.fiok), self.cimzett.GetValue().strip(),
            self.targy.GetValue(), self.torzs.GetValue(),
            self.masolat.GetValue(), self._csatolmanyok, self.valasz_id,
            titkos=self.titkos.GetValue().strip())

    def _piszkozat_ment(self, bezar: bool = True) -> None:
        """Mentés a SZOLGÁLTATÓ piszkozatai közé (így a telefonon is ott lesz).
        Ha az nem megy (POP3-fiók, nincs ilyen mappa, hiba), akkor HELYBEN
        mentjük .eml-ként – és mindkét esetben KIMONDJUK, hova került."""
        try:
            msg = self._piszkozat_uzenet()
        except Exception as ex:
            _mondd(self.main, "A piszkozat összeállítása nem sikerült: %s" % ex)
            return
        _mondd(self.main, "Piszkozat mentése…")

        def munka():
            if self.fiok.get("protokoll") != "pop":
                try:
                    k = _kliens(self.fiok).kapcsolodik()
                    try:
                        mappa = k.piszkozat_ment(msg)
                    finally:
                        k.bezar()
                    if mappa:
                        return "a szolgáltatód „%s” mappájába"\
                            % MC.mappa_display(mappa)
                except Exception:
                    pass
            return "ide a gépeden: %s" % _helyi_piszkozat(msg)

        def kesz(hol):
            _mondd(self.main, "Piszkozat elmentve %s." % hol)
            if bezar:
                self.EndModal(wx.ID_CANCEL)

        def hiba(ex):
            _mondd(self.main, "A piszkozat mentése nem sikerült: %s" % ex)

        _hatterben(munka, kesz, hiba)

    def _on_iro_close(self, e=None):
        """Bezáráskor: ha van mit menteni, HÁROM választás – mentés, eldobás,
        vagy visszatérés a levélhez (az utóbbi nélkül nem lehetne meggondolni
        magad)."""
        if getattr(self, "_kuldve", False) or not self._valtozott():
            self.EndModal(wx.ID_CANCEL)
            return
        d = HaromValaszDialog(
            self, "Piszkozat",
            "A levél nincs elküldve. Elmentsem piszkozatként?",
            "&Mentés piszkozatként", "&Eldobás", "&Mégsem (vissza a levélhez)",
            self.main)
        valasz = d.ShowModal()
        d.Destroy()
        if valasz == wx.ID_YES:
            self._piszkozat_ment(bezar=True)
        elif valasz == wx.ID_NO:
            _mondd(self.main, "A levél eldobva.")
            self.EndModal(wx.ID_CANCEL)
        # ID_CANCEL: marad nyitva

    def _cimjegyzek_autocomplete(self):
        """A címzett/Cc/Bcc mezőkre autókiegészítést tesz a címjegyzékből."""
        cimek = []
        for c in MC.cimjegyzek_betolt():
            cimek.append(MC.cimjegyzek_megjelenit(c))
            if c.get("email"):
                cimek.append(c["email"])
        cimek = list(dict.fromkeys(cimek))     # duplikátumok ki, sorrend marad
        for mezo in (self.cimzett, self.masolat, self.titkos):
            try:
                mezo.AutoComplete(cimek)
            except Exception:
                pass

    def _cimjegyzek_nyit(self, e):
        CimjegyzekValaszto(self, self.main).ShowModal()

    def _csatol(self, e):
        with wx.FileDialog(self, "Csatolmány", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._csatolmanyok.append(dlg.GetPath())
                self._csat_frissit()

    def _kuld(self, e):
        cim = self.cimzett.GetValue().strip()
        bcc = self.titkos.GetValue().strip()
        if not cim and not bcc:
            wx.MessageBox("Adj meg legalább egy címzettet.", "Küldés",
                          wx.OK | wx.ICON_WARNING, self)
            return
        # helyesírás-ellenőrzés küldés ELŐTT (a helyi menüből kikapcsolható)
        if self._helyesiras_be():
            self._helyesiras_futtat(csendes=True)
        if MC.altalanos_betolt().get("kuldes_kerdes", True):
            # LISTÁS VÁLASZNÁL kimondjuk, hogy ez mindenkihez megy – ezt a hibát
            # mindenki elköveti egyszer az életében.
            cimzett_szoveg = cim or bcc
            if getattr(self, "listanev", ""):
                cimzett_szoveg = ("a(z) %s LEVELEZŐLISTA – a levél a lista "
                                  "MINDEN tagjához megy (%s)"
                                  % (self.listanev, cim or bcc))
            d = KuldesKerdesDialog(self, cimzett_szoveg, self.main)
            valasz = d.ShowModal()
            ne_kerdezze = d.pipa.GetValue()
            d.Destroy()
            if valasz != wx.ID_YES:
                return
            if ne_kerdezze:
                cfg = MC.altalanos_betolt()
                cfg["kuldes_kerdes"] = False
                MC.altalanos_ment(cfg)
                _mondd(self.main, "Rendben, többé nem kérdezem meg. A "
                       "Beállítások Általános fülén bármikor visszakapcsolhatod.")
        # NAGY FÁJLOK: mielőtt nekifutnánk egy olyan küldésnek, amit a
        # kiszolgáló úgyis visszadob, felajánljuk a megoldást.
        if not self._nagy_fajl_rendez():
            return
        # A FIX ZÁRÓSOR a levél legaljára. Az aláírás NEM kerül be újra: az
        # már a szerkesztőben van (nyitáskor beillesztve), és ha a felhasználó
        # átírta vagy törölte, az az ő döntése – nem írjuk felül.
        torzs = MC.torzs_zarosorral(self.torzs.GetValue())
        # HTML-levél CSAK akkor, ha tényleg van benne hivatkozás vagy kép –
        # fölösleges HTML-t nem gyártunk (a sima szöveg jobban is kézbesül).
        if self._kepek or MC.van_html_jeloles(torzs):
            msg = MC.level_epit_html(
                MC.felado_fejlec(self.fiok), cim, self.targy.GetValue(), torzs,
                self.masolat.GetValue(), self._csatolmanyok, self.valasz_id,
                titkos=bcc, kepek=self._kepek)
        else:
            msg = MC.level_epit(MC.felado_fejlec(self.fiok), cim,
                                self.targy.GetValue(), torzs,
                                self.masolat.GetValue(), self._csatolmanyok,
                                self.valasz_id, titkos=bcc)
        # a címzetteket felvesszük a címjegyzékbe (auto-tanulás)
        for mezo in (self.cimzett, self.masolat, self.titkos):
            try:
                MC.cimjegyzek_felvesz_szovegbol(mezo.GetValue())
            except Exception:
                pass
        _mondd(self.main, "Küldés folyamatban…")
        _hatterben(lambda: MC.SmtpKuldo(self.fiok).kuld(msg),
                   lambda r: self._kesz(),
                   lambda ex: self._hiba(ex))

    def _kesz(self):
        self._kuldve = True          # elküldve: bezáráskor nincs piszkozat-kérdés
        _mondd(self.main, "A levél elment!")
        self.EndModal(wx.ID_OK)

    def _hiba(self, ex):
        uz = f"A küldés nem sikerült: {ex}"
        _mondd(self.main, uz)
        wx.MessageBox(uz, "Küldés", wx.OK | wx.ICON_ERROR, self)


# ======================================================================
#  Fő ablak
# ======================================================================
class ErtesitoDialog(wx.Dialog):
    """Fiókonkénti „új levél" értesítő: nincs / felolvasott szöveg / hang."""

    def __init__(self, parent, main, fiok):
        super().__init__(parent, title="Új levél értesítő", size=(580, 380),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self._fiok = fiok
        cfg = MC.ertesito_fiok(fiok.get("email", ""))
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Fiók: "
                            + (fiok.get("nev") or fiok.get("email", ""))),
              0, wx.ALL, 8)
        self.mod = wx.RadioBox(
            p, label="Amikor ÚJ levél érkezik ebbe a fiókba…",
            choices=["Ne jelezzen", "Olvasson fel egy szöveget",
                     "Játsszon le egy hangot"], style=wx.RA_SPECIFY_ROWS)
        self.mod.SetSelection({"nincs": 0, "szoveg": 1, "hang": 2}
                              .get(cfg["tipus"], 1))
        v.Add(self.mod, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Felolvasandó szöveg:"), 0, wx.LEFT, 8)
        self.szoveg = wx.TextCtrl(p, value=cfg.get("szoveg")
                                  or "Új leveled érkezett.")
        self.szoveg.SetName("Felolvasandó szöveg")
        v.Add(self.szoveg, 0, wx.EXPAND | wx.ALL, 8)
        hs = wx.BoxSizer(wx.HORIZONTAL)
        hs.Add(wx.StaticText(p, label="&Hangfájl:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.hang = wx.TextCtrl(p, value=cfg.get("hang", ""))
        self.hang.SetName("Értesítő hangfájl")
        hs.Add(self.hang, 1, wx.RIGHT, 6)
        tall = wx.Button(p, label="&Tallózás…")
        tall.Bind(wx.EVT_BUTTON, self._tallo)
        hs.Add(tall, 0, wx.RIGHT, 6)
        proba = wx.Button(p, label="&Próba")
        proba.Bind(wx.EVT_BUTTON, self._proba)
        hs.Add(proba, 0)
        v.Add(hs, 0, wx.EXPAND | wx.ALL, 8)
        s = wx.BoxSizer(wx.HORIZONTAL)
        ment = wx.Button(p, wx.ID_OK, "M&entés")
        ment.Bind(wx.EVT_BUTTON, self._ment)
        s.Add(ment, 0, wx.RIGHT, 6)
        s.Add(wx.Button(p, wx.ID_CANCEL, "Mégsem"), 0)
        v.Add(s, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        p.SetSizer(v)

    def _tallo(self, e):
        wc = ("Hangfájl|*.mp3;*.m4a;*.wav;*.ogg;*.oga;*.opus;*.flac;*.aac;"
              "*.wma|Minden fájl|*.*")
        with wx.FileDialog(self, "Értesítő hang", wildcard=wc,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.hang.SetValue(dlg.GetPath())

    def _proba(self, e):
        if self.mod.GetSelection() == 2:
            siker, uzenet = ertesito_hang(self.hang.GetValue())
            if not siker:                     # SOHA ne haljon el némán
                _mondd(self.main, uzenet)
                wx.MessageBox(uzenet, "Az értesítő hang nem szólalt meg",
                              wx.OK | wx.ICON_WARNING, self)
            return
        _mondd(self.main, self.szoveg.GetValue() or "Új leveled érkezett.")

    def _ment(self, e):
        tipus = {0: "nincs", 1: "szoveg", 2: "hang"}[self.mod.GetSelection()]
        MC.ertesito_fiok_ment(self._fiok.get("email", ""), tipus,
                              self.szoveg.GetValue().strip(),
                              self.hang.GetValue().strip())
        _mondd(self.main, "Az értesítő beállítás elmentve.")
        self.EndModal(wx.ID_OK)


class LevelOlvasoFrame(wx.Frame):
    """Egy levél KÜLÖN ablakban: fejléc + szöveg + KATTINTHATÓ hivatkozás-lista,
    saját menüsávval (válasz, továbbítás, csatolmány, AI, törlés). A műveletek a
    fő ablak bevált logikáját használják."""

    def __init__(self, mailframe, main, info, msg, fiok, mappa):
        fej = MC.level_fejlec_info(msg)
        cim = fej["targy"] or "(nincs tárgy)"
        super().__init__(None, title=f"Levél – {cim}", size=(840, 660))
        self._mf = mailframe
        self.main = main
        self._info, self._msg, self._fiok, self._mappa = info, msg, fiok, mappa
        self._closing = False
        self.SetMenuBar(self._menusav())

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        torzs = MC.level_szovegtorzs(msg)
        csat = MC.csatolmanyok(msg)
        cs = (f"   •   Csatolmány: {len(csat)}" if csat else "")
        fejlec = (f"Feladó: {fej['felado']}\nCímzett: {fej['cimzett']}\n"
                  f"Tárgy: {fej['targy']}\nDátum: {fej['datum']}{cs}")
        h = wx.TextCtrl(p, value=fejlec, size=(-1, 108),
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        h.SetName("Levél fejléce")
        v.Add(h, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="Levél &szövege:"), 0, wx.LEFT, 8)
        self.olvaso = wx.TextCtrl(
            p, value=torzs, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.olvaso.SetName("Levél szövege")
        self.olvaso.SetInsertionPoint(0)
        v.Add(self.olvaso, 1, wx.EXPAND | wx.ALL, 8)

        self._linkek = MC.hivatkozasok_szovegbol(torzs)
        v.Add(wx.StaticText(p, label="&Hivatkozások a levélben (Enter: megnyitás "
              "a böngészőben):"), 0, wx.LEFT, 8)
        self.link_lista = wx.ListBox(
            p, choices=self._linkek or ["(ebben a levélben nincs hivatkozás)"])
        self.link_lista.SetName("Hivatkozások")
        self.link_lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._link_nyit())
        v.Add(self.link_lista, 0, wx.EXPAND | wx.ALL, 8)
        p.SetSizer(v)

        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Centre()
        # a fókusz rögtön a LEVÉL SZÖVEGÉRE kerül (a tesztelő kérése): így a
        # képernyőolvasóval azonnal olvasható a tartalom, nem kell a fejlécen
        # átlépkedni – a fejléc külön mezőben ott marad (Shift+Tab).
        wx.CallAfter(self.olvaso.SetFocus)
        n = len(self._linkek)
        lista = MC.lista_neve(msg) if MC.listas_level(msg) else ""
        wx.CallAfter(_mondd, self.main,
                     f"{fej['felado']}. Tárgy: {fej['targy']}. A szöveg a Levél "
                     "szövege mezőben. "
                     + (f"{n} hivatkozás a levélben, lent a listában. "
                        if n else "Nincs hivatkozás a levélben. ")
                     + (f"Ez a levél a(z) {lista} listáról jött – válasz a "
                        "listára: L betű." if lista else ""))

    def _menusav(self):
        mb = wx.MenuBar()

        def mi(menu, cimke, kez):
            it = menu.Append(wx.ID_ANY, cimke)
            self.Bind(wx.EVT_MENU, kez, it)

        m = wx.Menu()
        mi(m, "&Válasz  (R vagy Ctrl+R)", lambda e: self._mf._valasz(
            msg=self._msg, fiok=self._fiok))
        mi(m, "Válasz a &levelezőlistára  (L)",
           lambda e: self._valasz_listara())
        mi(m, "&Fordítás magyarra  (F9)", lambda e: self._forditas())
        mi(m, "Válasz min&denkinek  (Shift+R)", lambda e: self._mf._valasz(
            msg=self._msg, fiok=self._fiok, mind=True))
        mi(m, "&Továbbítás  (F vagy Ctrl+F)", lambda e: self._mf._tovabbit(
            msg=self._msg, fiok=self._fiok))
        m.AppendSeparator()
        mi(m, "&Csatolmány mentése…",
           lambda e: self._mf._csat_ment_msg(self._msg))
        mi(m, "&AI-összefoglaló  (AI-kulcs kell)",
           lambda e: self._mf._ai_osszefoglalo(self._msg))
        mi(m, "Ol&vasatlannak jelölés", lambda e: self._jelol_olvasatlan())
        m.AppendSeparator()
        mi(m, "Tör&lés", lambda e: self._torol())
        mi(m, "Be&zárás  (Esc)", lambda e: self.Close())
        mb.Append(m, "&Levél")

        mh = wx.Menu()
        mi(mh, "A kijelölt hivatkozás &megnyitása a böngészőben",
           lambda e: self._link_nyit())
        mb.Append(mh, "&Hivatkozások")

        ms = wx.Menu()
        mi(ms, "&Súgó  (F1)", lambda e: self._mf._sugo())
        mb.Append(ms, "&Segítség")
        return mb

    def _link_nyit(self):
        if not self._linkek:
            _mondd(self.main, "Ebben a levélben nincs hivatkozás.")
            return
        i = self.link_lista.GetSelection()
        if not (0 <= i < len(self._linkek)):
            i = 0
        import webbrowser
        try:
            webbrowser.open(self._linkek[i])
            _mondd(self.main, "Megnyitottam a hivatkozást a böngészőben.")
        except Exception:
            _mondd(self.main, "Nem sikerült megnyitni a hivatkozást.")

    def _jelol_olvasatlan(self):
        info, fiok, mappa = self._info, self._fiok, self._mappa
        if not info or not fiok or fiok.get("protokoll") == "pop":
            _mondd(self.main, "Ez POP3-fióknál nem támogatott.")
            return

        def munka():
            k = _kliens(fiok).kapcsolodik()
            k.olvasatlannak(info["uid"], mappa)
            k.bezar()
            return True
        _hatterben(munka, lambda r: _mondd(self.main, "Olvasatlannak jelölve."),
                   lambda ex: _mondd(self.main, f"Hiba: {ex}"))

    def _torol(self):
        info, fiok, mappa = self._info, self._fiok, self._mappa
        if wx.MessageBox("Törlöd ezt a levelet?", "Törlés",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return

        def munka():
            k = _kliens(fiok).kapcsolodik()
            if isinstance(k, MC.Pop3Kliens):
                k.torol(info["szam"])
            else:
                k.torol(info["uid"], mappa)
            k.bezar()
            return True

        def kesz(r):
            _mondd(self.main, "Levél törölve.")
            try:
                self._mf._frissit_aktualis()
            except Exception:
                pass
            self.Close()
        _hatterben(munka, kesz, lambda ex: _mondd(self.main, f"Hiba: {ex}"))

    def _on_key(self, e):
        """A megnyitott levél billentyűi. FONTOS: a válasz/továbbítás billentyűk
        eddig CSAK a levéllistában működtek, a megnyitott levélben NEM (a menü
        felirata viszont ígérte) – a tesztelő jelezte, javítva. Itt minden mező
        csak olvasható, ezért a puszta R/F is biztonságos, de a kért Ctrl+R és
        Ctrl+F is megy (mint máshol a „reply" és „forward")."""
        k = e.GetKeyCode()
        ch = chr(k).lower() if 32 < k < 256 else ""
        ctrl = e.ControlDown()
        if k == wx.WXK_ESCAPE:
            self.Close()
        elif k == wx.WXK_F1:
            self._mf._sugo()
        elif (k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
              and self.FindFocus() is self.link_lista):
            self._link_nyit()
        elif ch == "r" and e.ShiftDown():          # válasz MINDENKINEK
            self._mf._valasz(msg=self._msg, fiok=self._fiok, mind=True)
        elif ch == "r":                            # R vagy Ctrl+R: válasz
            self._mf._valasz(msg=self._msg, fiok=self._fiok)
        elif ch == "f":                            # F vagy Ctrl+F: továbbítás
            self._mf._tovabbit(msg=self._msg, fiok=self._fiok)
        elif ctrl and ch == "s":                   # Ctrl+S: csatolmány mentése
            self._mf._csat_ment_msg(self._msg)
        elif k == wx.WXK_F9:                       # F9: fordítás magyarra
            self._forditas()
        elif ch == "l":                            # L: válasz a LISTÁRA
            self._valasz_listara()
        else:
            e.Skip()

    # ---- fordítás ------------------------------------------------------

    def _forditas(self):
        """F9: a levél lefordítása magyarra. A fordítás a szöveg FÖLÉ kerül, az
        eredeti alatta marad – nevek, számok, linkek miatt azt is látni kell."""
        eredeti = getattr(self, "_eredeti_torzs", None) or self.olvaso.GetValue()
        self._eredeti_torzs = eredeti
        nyelv, biztos = FORD.nyelv_felismer(eredeti)
        if nyelv == "hu":
            _mondd(self.main, "Ez a levél magyarul van.")
            return
        d = ForditasDialog(self, self.main, nyelv if biztos else "")
        rendben = d.ShowModal() == wx.ID_OK
        motor, honnan = d.motor(), d.nyelv()
        d.Destroy()
        if not rendben:
            return
        _mondd(self.main, "Fordítás folyamatban…")

        def munka():
            return FORD.fordit(eredeti, "hu", motor, honnan)

        def kesz(eredmeny):
            if self._closing:
                return
            self.olvaso.SetValue(FORD.megjelenites(eredeti, eredmeny))
            self.olvaso.SetInsertionPoint(0)
            self.olvaso.SetFocus()
            _mondd(self.main, "Kész a fordítás %s nyelvről. A lefordított "
                   "szöveg a levél elején van, alatta az eredeti."
                   % FORD.nyelv_neve(eredmeny["honnan"]))

        def hiba(ex):
            if not self._closing:
                _mondd(self.main, "A fordítás nem sikerült: %s" % ex)
                wx.MessageBox(str(ex), "Fordítás", wx.OK | wx.ICON_ERROR, self)

        _hatterben(munka, kesz, hiba)

    # ---- válasz a levelezőlistára --------------------------------------

    def _valasz_listara(self):
        cim = MC.lista_cim(self._msg)
        if not cim:
            _mondd(self.main, "Ez a levél nem levelezőlistáról jött. Az R "
                   "betűvel válaszolhatsz a feladónak.")
            return
        self._mf._valasz(msg=self._msg, fiok=self._fiok, listara=cim)

    def _on_close(self, e):
        self._closing = True
        e.Skip()


class ForditasDialog(wx.Dialog):
    """Fordítás előtti kérdés: melyik motorral, és milyen nyelvről.

    Azért van külön párbeszéd, mert a felhasználónak TUDNIA kell, hogy a levele
    szövege elhagyja a gépet – egy magánlevélnél ez nem apróság."""

    def __init__(self, parent, main, felismert=""):
        super().__init__(parent, title="Fordítás magyarra")
        v = wx.BoxSizer(wx.VERTICAL)
        fig = wx.StaticText(self, label=(
            "FIGYELEM: a fordításhoz a levél szövege elhagyja a gépet, és "
            "elmegy a választott fordítóhoz. Bizalmas levélnél gondold meg."))
        fig.Wrap(520)
        fig.SetName(fig.GetLabel())
        v.Add(fig, 0, wx.ALL, 12)
        self._motor = wx.RadioBox(self, label="&Fordító", majorDimension=1,
                                  choices=[n for _k, n in FORD.MOTOROK])
        v.Add(self._motor, 0, wx.LEFT | wx.RIGHT, 12)
        cimke = ("A felismert nyelv: %s. Ha nem stimmel, válassz másikat."
                 % FORD.nyelv_neve(felismert) if felismert
                 else "A nyelvet nem sikerült biztosan felismerni – válaszd ki:")
        v.Add(wx.StaticText(self, label=cimke), 0, wx.ALL, 12)
        self._nyelv = wx.Choice(self, choices=["%s (%s)" % (n, k)
                                               for k, n in FORD.NYELVEK])
        self._nyelv.SetName("A levél nyelve")
        kodok = [k for k, _n in FORD.NYELVEK]
        self._nyelv.SetSelection(kodok.index(felismert) if felismert in kodok
                                 else 1)
        v.Add(self._nyelv, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        gs = wx.BoxSizer(wx.HORIZONTAL)
        ok = wx.Button(self, wx.ID_OK, "&Fordítás")
        ok.SetDefault()
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 12)
        self.SetSizerAndFit(v)
        self.CentreOnParent()
        wx.CallAfter(_mondd, main, fig.GetLabel() + " " + cimke)

    def motor(self):
        return FORD.MOTOROK[self._motor.GetSelection()][0]

    def nyelv(self):
        return FORD.NYELVEK[self._nyelv.GetSelection()][0]


class BeallitasokDialog(wx.Dialog):
    """Super Mail beállítások LAPFÜLEKRE osztva: Fiókok, Értesítők, Címjegyzék,
    Általános."""

    def __init__(self, parent, main, mailframe, lap=0):
        super().__init__(parent, title="Super Mail – Beállítások", size=(700, 580),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self._mf = mailframe
        v = wx.BoxSizer(wx.VERTICAL)
        nb = wx.Notebook(self)
        nb.AddPage(self._fiokok_lap(nb), "Fiókok")
        nb.AddPage(self._ertesitok_lap(nb), "Értesítők")
        nb.AddPage(self._cimjegyzek_lap(nb), "Címjegyzék")
        nb.AddPage(self._altalanos_lap(nb), "Általános")
        nb.SetSelection(max(0, min(lap, 3)))
        v.Add(nb, 1, wx.EXPAND | wx.ALL, 8)
        be = wx.Button(self, wx.ID_CLOSE, "&Bezárás")
        be.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        v.Add(be, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizer(v)

    # ---- Fiókok lap ----
    def _fiokok_lap(self, nb):
        p = wx.Panel(nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=(
            "A beállított e-mail fiókjaid. A LISTA SORRENDJE számít: a LEGFELSŐ "
            "az ALAPÉRTELMEZETT – ez nyílik meg a levelező indításakor. A "
            "sorrendet a Feljebb/Lejjebb gombokkal állíthatod.")),
            0, wx.ALL, 6)
        self.fiok_lb = wx.ListBox(p)
        self.fiok_lb.SetName("Fiókok (a legfelső az alapértelmezett)")
        v.Add(self.fiok_lb, 1, wx.EXPAND | wx.ALL, 6)
        s = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, kez in (("&Hozzáadás…", self._f_add),
                           ("Sze&rkesztés…", self._f_edit),
                           ("&Törlés", self._f_del),
                           ("Fel&jebb", self._f_fel),
                           ("&Lejjebb", self._f_le),
                           ("Legyen ez az &alapértelmezett", self._f_alap)):
            b = wx.Button(p, label=cimke)
            b.Bind(wx.EVT_BUTTON, kez)
            s.Add(b, 0, wx.RIGHT, 6)
        v.Add(s, 0, wx.ALL, 6)
        p.SetSizer(v)
        self._fiokok_frissit()
        return p

    # ---- fiók-sorrend (az első = alapértelmezett, az indul is ezt nyitja) ----
    def _f_mozgat(self, irany):
        i = self.fiok_lb.GetSelection()
        j = i + irany
        if i < 0 or not (0 <= j < len(self._fiokok)):
            return
        self._fiokok[i], self._fiokok[j] = self._fiokok[j], self._fiokok[i]
        MC.fiokok_ment(self._fiokok)
        self._fiokok_frissit()
        self.fiok_lb.SetSelection(j)
        self._mf_reload()
        nev = self._fiokok[j].get("nev") or self._fiokok[j].get("email")
        _mondd(self.main, "%s a(z) %d. helyre került.%s"
               % (nev, j + 1,
                  " Ez mostantól az alapértelmezett fiók." if j == 0 else ""))

    def _f_fel(self, e):
        self._f_mozgat(-1)

    def _f_le(self, e):
        self._f_mozgat(1)

    def _f_alap(self, e):
        """A kijelölt fiókot a lista ELEJÉRE teszi → ez lesz az alapértelmezett."""
        i = self.fiok_lb.GetSelection()
        if i <= 0:
            if i == 0:
                _mondd(self.main, "Ez már az alapértelmezett fiók.")
            return
        self._fiokok.insert(0, self._fiokok.pop(i))
        MC.fiokok_ment(self._fiokok)
        self._fiokok_frissit()
        self.fiok_lb.SetSelection(0)
        self._mf_reload()
        nev = self._fiokok[0].get("nev") or self._fiokok[0].get("email")
        _mondd(self.main, "%s mostantól az alapértelmezett fiók – ez nyílik "
               "meg a levelező indításakor." % nev)

    def _fiokok_frissit(self):
        self._fiokok = MC.fiokok_betolt()
        self.fiok_lb.Set([f.get("nev") or f.get("email") for f in self._fiokok])

    def _mf_reload(self):
        try:
            self._mf._fiokok = MC.fiokok_betolt()
            self._mf._fiok_valaszto_feltolt()
        except Exception:
            pass

    def _f_add(self, e):
        dlg = FiokDialog(self, self.main)
        if dlg.ShowModal() == wx.ID_OK and dlg.eredmeny:
            fi = [f for f in MC.fiokok_betolt()
                  if f["email"] != dlg.eredmeny["email"]]
            fi.append(dlg.eredmeny)
            MC.fiokok_ment(fi)
            self._fiokok_frissit()
            self._also_ertesito_fiokok()
            self._mf_reload()
        dlg.Destroy()

    def _f_edit(self, e):
        i = self.fiok_lb.GetSelection()
        if not (0 <= i < len(self._fiokok)):
            return
        regi = self._fiokok[i]["email"]
        dlg = FiokDialog(self, self.main, self._fiokok[i])
        if dlg.ShowModal() == wx.ID_OK and dlg.eredmeny:
            fi = [f for f in MC.fiokok_betolt() if f["email"] != regi]
            fi.append(dlg.eredmeny)
            MC.fiokok_ment(fi)
            self._fiokok_frissit()
            self._also_ertesito_fiokok()
            self._mf_reload()
        dlg.Destroy()

    def _f_del(self, e):
        i = self.fiok_lb.GetSelection()
        if not (0 <= i < len(self._fiokok)):
            return
        cim = self._fiokok[i]["email"]
        if wx.MessageBox(f"Törlöd a(z) {cim} fiókot? A tárolt app-jelszava is "
                         "törlődik.", "Fiók törlése",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        MC.fiok_torol(cim)
        self._fiokok_frissit()
        self._also_ertesito_fiokok()
        self._mf_reload()

    # ---- Értesítők lap ----
    def _ertesitok_lap(self, nb):
        p = wx.Panel(nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Fiók:"), 0, wx.LEFT | wx.TOP, 6)
        self.ert_fiok = wx.Choice(p, choices=[])
        self.ert_fiok.SetName("Fiók az értesítőhöz")
        self.ert_fiok.Bind(wx.EVT_CHOICE, lambda e: self._ert_betolt())
        v.Add(self.ert_fiok, 0, wx.EXPAND | wx.ALL, 6)
        self.ert_mod = wx.RadioBox(
            p, label="Amikor ÚJ levél érkezik ebbe a fiókba…",
            choices=["Ne jelezzen", "Olvasson fel egy szöveget",
                     "Játsszon le egy hangot"], style=wx.RA_SPECIFY_ROWS)
        v.Add(self.ert_mod, 0, wx.EXPAND | wx.ALL, 6)
        v.Add(wx.StaticText(p, label="&Felolvasandó szöveg:"), 0, wx.LEFT, 6)
        self.ert_szoveg = wx.TextCtrl(p)
        v.Add(self.ert_szoveg, 0, wx.EXPAND | wx.ALL, 6)
        hs = wx.BoxSizer(wx.HORIZONTAL)
        hs.Add(wx.StaticText(p, label="&Hangfájl:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.ert_hang = wx.TextCtrl(p)
        hs.Add(self.ert_hang, 1, wx.RIGHT, 6)
        tb = wx.Button(p, label="&Tallózás…")
        tb.Bind(wx.EVT_BUTTON, self._ert_tallo)
        hs.Add(tb, 0, wx.RIGHT, 6)
        pb = wx.Button(p, label="&Próba")
        pb.Bind(wx.EVT_BUTTON, self._ert_proba)
        hs.Add(pb, 0)
        v.Add(hs, 0, wx.EXPAND | wx.ALL, 6)
        mb = wx.Button(p, label="&Mentés erre a fiókra")
        mb.Bind(wx.EVT_BUTTON, self._ert_ment)
        v.Add(mb, 0, wx.ALL, 6)
        p.SetSizer(v)
        self._also_ertesito_fiokok()
        return p

    def _also_ertesito_fiokok(self):
        self._ert_fiokok = MC.fiokok_betolt()
        self.ert_fiok.Set([f.get("nev") or f.get("email")
                           for f in self._ert_fiokok])
        if self._ert_fiokok:
            self.ert_fiok.SetSelection(0)
            self._ert_betolt()

    def _ert_akt(self):
        i = self.ert_fiok.GetSelection()
        return self._ert_fiokok[i] if 0 <= i < len(self._ert_fiokok) else None

    def _ert_betolt(self):
        f = self._ert_akt()
        if not f:
            return
        cfg = MC.ertesito_fiok(f.get("email", ""))
        self.ert_mod.SetSelection({"nincs": 0, "szoveg": 1, "hang": 2}
                                  .get(cfg["tipus"], 1))
        self.ert_szoveg.SetValue(cfg.get("szoveg") or "Új leveled érkezett.")
        self.ert_hang.SetValue(cfg.get("hang", ""))

    def _ert_tallo(self, e):
        wc = ("Hangfájl|*.mp3;*.m4a;*.wav;*.ogg;*.oga;*.opus;*.flac;*.aac;"
              "*.wma|Minden fájl|*.*")
        with wx.FileDialog(self, "Értesítő hang", wildcard=wc,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.ert_hang.SetValue(dlg.GetPath())

    def _ert_proba(self, e):
        if self.ert_mod.GetSelection() == 2:
            siker, uzenet = ertesito_hang(self.ert_hang.GetValue())
            if not siker:                     # SOHA ne haljon el némán
                _mondd(self.main, uzenet)
                wx.MessageBox(uzenet, "Az értesítő hang nem szólalt meg",
                              wx.OK | wx.ICON_WARNING, self)
            return
        _mondd(self.main, self.ert_szoveg.GetValue() or "Új leveled érkezett.")

    def _ert_ment(self, e):
        f = self._ert_akt()
        if not f:
            return
        tipus = {0: "nincs", 1: "szoveg", 2: "hang"}[self.ert_mod.GetSelection()]
        MC.ertesito_fiok_ment(f.get("email", ""), tipus,
                              self.ert_szoveg.GetValue().strip(),
                              self.ert_hang.GetValue().strip())
        _mondd(self.main, "Értesítő elmentve erre a fiókra.")

    # ---- Címjegyzék lap ----
    def _cimjegyzek_lap(self, nb):
        p = wx.Panel(nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="&Keresés (név vagy e-mail):"),
              0, wx.LEFT | wx.TOP, 6)
        self.cj_szuro = wx.TextCtrl(p)
        self.cj_szuro.Bind(wx.EVT_TEXT, lambda e: self._cj_frissit())
        v.Add(self.cj_szuro, 0, wx.EXPAND | wx.ALL, 6)
        self.cj_lb = wx.ListBox(p)
        self.cj_lb.SetName("Címjegyzék")
        v.Add(self.cj_lb, 1, wx.EXPAND | wx.ALL, 6)
        s = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, kez in (("&Új…", self._cj_uj),
                           ("Sze&rkesztés…", self._cj_edit),
                           ("&Törlés", self._cj_del)):
            b = wx.Button(p, label=cimke)
            b.Bind(wx.EVT_BUTTON, kez)
            s.Add(b, 0, wx.RIGHT, 6)
        v.Add(s, 0, wx.ALL, 6)
        p.SetSizer(v)
        self._cj_frissit()
        return p

    def _cj_frissit(self):
        self._cj_talalatok = MC.cimjegyzek_kereses(self.cj_szuro.GetValue(),
                                                   limit=1000)
        self.cj_lb.Set([MC.cimjegyzek_megjelenit(c) for c in self._cj_talalatok]
                       or ["(a címjegyzék üres – ahogy levelezel, feltöltődik)"])

    def _cj_uj(self, e):
        em = wx.GetTextFromUser("E-mail cím:", "Új cím", "", self).strip()
        if "@" not in em:
            return
        nev = wx.GetTextFromUser("Név (nem kötelező):", "Új cím", "", self).strip()
        MC.cimjegyzek_frissit(em, nev)
        self._cj_frissit()

    def _cj_edit(self, e):
        i = self.cj_lb.GetSelection()
        if not (0 <= i < len(self._cj_talalatok)):
            return
        c = self._cj_talalatok[i]
        nev = wx.GetTextFromUser(f"Név a(z) {c['email']} címhez:", "Szerkesztés",
                                 c.get("nev", ""), self)
        MC.cimjegyzek_frissit(c["email"], nev.strip())
        self._cj_frissit()

    def _cj_del(self, e):
        i = self.cj_lb.GetSelection()
        if not (0 <= i < len(self._cj_talalatok)):
            return
        c = self._cj_talalatok[i]
        if wx.MessageBox(f"Törlöd a címjegyzékből: {c['email']}?", "Törlés",
                         wx.YES_NO | wx.ICON_QUESTION, self) == wx.YES:
            MC.cimjegyzek_torol(c["email"])
            self._cj_frissit()

    # ---- Általános lap ----
    def _altalanos_lap(self, nb):
        p = wx.Panel(nb)
        v = wx.BoxSizer(wx.VERTICAL)
        cfg = MC.altalanos_betolt()
        self.alt_auto = wx.CheckBox(
            p, label="Háttérben &figyelje az új leveleket (az értesítőhöz)")
        self.alt_auto.SetValue(bool(cfg.get("auto_ellenoriz", True)))
        v.Add(self.alt_auto, 0, wx.ALL, 8)
        hs = wx.BoxSizer(wx.HORIZONTAL)
        hs.Add(wx.StaticText(p, label="Ellenőrzés &percenként:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.alt_perc = wx.SpinCtrl(p, min=1, max=60,
                                    initial=int(cfg.get("ellenoriz_perc", 3)))
        hs.Add(self.alt_perc, 0)
        v.Add(hs, 0, wx.ALL, 8)
        hs2 = wx.BoxSizer(wx.HORIZONTAL)
        hs2.Add(wx.StaticText(p, label="Levelek száma &listánként:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.alt_limit = wx.SpinCtrl(p, min=10, max=500,
                                     initial=int(cfg.get("lista_limit", 50)))
        hs2.Add(self.alt_limit, 0)
        v.Add(hs2, 0, wx.ALL, 8)

        # --- mi legyen a levéllista soraiban? (a tesztelő kérése) ---
        v.Add(wx.StaticText(p, label=(
            "Mi hangozzon el a levéllistában? (Csak azt kapcsold be, amire "
            "szükséged van – így rövidebb, gyorsabban átfutható sorokat kapsz.)")),
            0, wx.LEFT | wx.TOP, 8)
        self.alt_lista_mezok = {}
        for kulcs, cimke, alap in (
                ("lista_allapot", "&Olvasatlan jelzés (kimondja: „olvasatlan”)", True),
                ("lista_felado", "A feladó &neve", True),
                ("lista_cim", "A feladó &e-mail címe", False),
                ("lista_targy", "A levél &tárgya", True),
                ("lista_ido", "A küldés &ideje", True)):
            cb = wx.CheckBox(p, label=cimke)
            cb.SetValue(bool(cfg.get(kulcs, alap)))
            v.Add(cb, 0, wx.LEFT | wx.TOP, 12)
            self.alt_lista_mezok[kulcs] = cb

        # --- mi történjen a lista SZÉLÉN? ---
        v.Add(wx.StaticText(p, label=(
            "Ha a lista tetején vagy alján tovább nyilaznál (hogy ne olvassa "
            "fel újra ugyanazt a sort):")), 0, wx.LEFT | wx.TOP, 8)
        self.alt_szel = wx.RadioBox(
            p, label="A lista &szélén", majorDimension=1,
            choices=["Rövid hangjelzés (bling)", "Mondja ki (A lista teteje)"])
        self.alt_szel.SetSelection(
            0 if str(cfg.get("lista_szel", "bling")) == "bling" else 1)
        self.alt_szel.SetName("Mi történjen a lista szélén")
        v.Add(self.alt_szel, 0, wx.LEFT | wx.TOP, 12)

        self.alt_kuldes_kerdes = wx.CheckBox(
            p, label="&Küldés előtt kérdezzen rá")
        self.alt_kuldes_kerdes.SetValue(bool(cfg.get("kuldes_kerdes", True)))
        self.alt_kuldes_kerdes.SetName("Küldés előtt kérdezzen rá – ha a "
                                       "küldés-párbeszédben kikapcsoltad, itt "
                                       "bármikor visszakapcsolhatod")
        v.Add(self.alt_kuldes_kerdes, 0, wx.LEFT | wx.TOP, 12)

        # --- ALÁÍRÁS ---
        v.Add(wx.StaticText(p, label=(
            "&Aláírás (a levél végére kerül; szabadon átírható, akár teljesen "
            "törölhető). A levél legaljára minden esetben odakerül még egy "
            "sor: „%s”" % MC.FIX_ZAROSOR)), 0, wx.LEFT | wx.TOP, 8)
        self.alt_alairas = wx.TextCtrl(
            p, style=wx.TE_MULTILINE, size=(-1, 90),
            value=str(cfg.get("alairas", MC.ALAP_ALAIRAS)))
        self.alt_alairas.SetName("Aláírás szövege")
        v.Add(self.alt_alairas, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        ab = wx.Button(p, label="Alap&értelmezett aláírás visszaállítása")
        ab.Bind(wx.EVT_BUTTON,
                lambda e: (self.alt_alairas.SetValue(MC.ALAP_ALAIRAS),
                           _mondd(self.main, "Alapértelmezett aláírás "
                                  "visszaállítva. Mentés a Mentés gombbal.")))
        v.Add(ab, 0, wx.LEFT | wx.TOP, 12)

        mb = wx.Button(p, label="&Mentés")
        mb.Bind(wx.EVT_BUTTON, self._alt_ment)
        v.Add(mb, 0, wx.ALL, 8)
        p.SetSizer(v)
        return p

    def _alt_ment(self, e):
        adat = {"auto_ellenoriz": bool(self.alt_auto.GetValue()),
                "ellenoriz_perc": int(self.alt_perc.GetValue()),
                "lista_limit": int(self.alt_limit.GetValue()),
                "lista_szel": ("bling" if self.alt_szel.GetSelection() == 0
                               else "beszed"),
                "kuldes_kerdes": bool(self.alt_kuldes_kerdes.GetValue()),
                "alairas": self.alt_alairas.GetValue().strip()}
        for kulcs, cb in getattr(self, "alt_lista_mezok", {}).items():
            adat[kulcs] = bool(cb.GetValue())
        MC.altalanos_ment(adat)
        try:                                   # a lista azonnal az új formátumra
            self._mf._lista_ujrarajzol()
        except Exception:
            pass
        try:
            self._mf._ertesito_timer_beallit()
        except Exception:
            pass
        _mondd(self.main, "Az általános beállítások elmentve.")


class MailFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(None, title="Super Mail – akadálymentes levelező",
                         size=(980, 660))
        self.main = main
        self._closing = False
        self._fiokok = []
        self._aktiv = None
        self._mappa = "INBOX"
        self._mappak_raw = []          # a mappák NYERS (IMAP) nevei
        self._lista = []               # a jelenlegi levéllista info-dictjei
        self._osszesitett = False      # „Összes bejövő" nézet aktív?
        self._aktiv_fiok = None        # a MEGNYITOTT levél fiókja
        self._aktiv_msg = None
        self._vagolap = None           # kivágott/másolt levelek (Ctrl+X/C → Ctrl+V)
        self._utolso_uid = {}          # fiók-email → a legfrissebb látott INBOX-UID
        self._ert_hang = None          # az értesítő-hang lejátszója
        self._panel = wx.Panel(self)
        self._build()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Centre()
        wx.CallAfter(self._indul)
        # háttér új-levél ellenőrzés (értesítővel), hogy kézi frissítés nélkül is szóljon
        self._ellenor_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._auto_ellenoriz(),
                  self._ellenor_timer)
        self._ertesito_timer_beallit()

    def _ertesito_timer_beallit(self):
        """A háttér-ellenőrzés idejét/ki-be kapcsolását az Általános beállításból."""
        cfg = MC.altalanos_betolt()
        try:
            self._ellenor_timer.Stop()
        except Exception:
            pass
        if cfg.get("auto_ellenoriz", True):
            perc = max(1, int(cfg.get("ellenoriz_perc", 3)))
            self._ellenor_timer.Start(perc * 60000)

    def _beallitasok(self, e=None, lap=0):
        dlg = BeallitasokDialog(self, self.main, self, lap=lap)
        dlg.ShowModal()
        dlg.Destroy()

    def _auto_ellenoriz(self):
        """Háttér új-levél ellenőrzés az AKTÍV fiók INBOX-ában.

        A tesztelő jelezte, hogy hiába állította 1 percre, az új levél csak
        F5-re jött meg. Két oka volt: (1) csak a legfrissebb UID-et néztük, és a
        LISTÁT csak akkor frissítettük, ha a UID-összehasonlítás sikerült;
        (2) a háttérhibák NÉMÁN elnyelődtek (`lambda ex: None`), így semmi jel
        nem volt. Most: ha a Beérkezett van nyitva, egyszerűen ÚJRATÖLTJÜK a
        listát (ez az, amit a felhasználó „automatikus frissítésen" ért), és a
        hibát legalább az állapotsorban jelezzük."""
        if (self._closing or not self._aktiv
                or self._aktiv.get("protokoll") == "pop"):
            return
        fiok = self._aktiv
        em = (fiok.get("email") or "").lower()
        beerkezett_nezet = (not self._osszesitett
                            and (self._mappa or "").upper() == "INBOX")

        if beerkezett_nezet:
            # a lista tényleges újratöltése – az új levél MEGJELENIK magától
            # (az értesítést a _lista_kesz → _uj_level_ellenoriz intézi)
            self._frissit(csendes=True)
            return

        def munka():
            k = _kliens(fiok).kapcsolodik()
            u = k.legujabb_uid("INBOX")
            k.bezar()
            return u

        def kesz(u):
            if self._closing:
                return
            elozo = self._utolso_uid.get(em)
            if elozo is None:
                self._utolso_uid[em] = u        # kiindulási alap, ha még nem volt
                return
            if u > elozo:
                self._utolso_uid[em] = u
                self._ertesit(fiok)

        def hiba(ex):                            # nem némán: legalább látszódjon
            if not self._closing:
                self._allapot_uzenet("A háttér-ellenőrzés most nem sikerült: %s"
                                     % ex)
        _hatterben(munka, kesz, hiba)

    def _allapot_uzenet(self, szoveg):
        """Csendes állapot-üzenet (nem szakítja félbe a képernyőolvasót)."""
        try:
            self.SetStatusText(szoveg)
        except Exception:
            pass

    def _build(self):
        p = self._panel
        v = wx.BoxSizer(wx.VERTICAL)
        self.SetMenuBar(self._menusav())   # minden művelet az Alt-menükben

        felso = wx.BoxSizer(wx.HORIZONTAL)
        felso.Add(wx.StaticText(p, label="&Fiók:"), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.fiok_valaszto = wx.Choice(p, choices=[])
        self.fiok_valaszto.SetName("Fiók")
        self.fiok_valaszto.Bind(wx.EVT_CHOICE, self._fiok_valt)
        felso.Add(self.fiok_valaszto, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(felso, 0, wx.EXPAND | wx.ALL, 8)

        közép = wx.BoxSizer(wx.HORIZONTAL)
        # mappák
        bal = wx.BoxSizer(wx.VERTICAL)
        bal.Add(wx.StaticText(p, label="&Mappák:"), 0)
        self.mappa_lista = wx.ListBox(p, size=(200, -1))
        self.mappa_lista.SetName("Mappák")
        self.mappa_lista.Bind(wx.EVT_LISTBOX, self._mappa_valt)
        self.mappa_lista.Bind(
            wx.EVT_KEY_DOWN, lambda e: self._lista_szel(e, self.mappa_lista,
                                                        "mappa"))
        bal.Add(self.mappa_lista, 1, wx.EXPAND)
        közép.Add(bal, 0, wx.EXPAND | wx.RIGHT, 8)
        # levéllista
        közép_j = wx.BoxSizer(wx.VERTICAL)
        közép_j.Add(wx.StaticText(
            p, label="&Levelek (Enter: megnyitás; Ctrl+A: mind; Ctrl+X/C/V: "
            "kivágás/másolás/beillesztés):"), 0)
        self.level_lista = wx.ListBox(p, style=wx.LB_EXTENDED)
        self.level_lista.SetName("Levéllista")
        self.level_lista.Bind(wx.EVT_LISTBOX, self._level_valt)
        self.level_lista.Bind(
            wx.EVT_KEY_DOWN, lambda e: self._lista_szel(e, self.level_lista,
                                                        "level"))
        self.level_lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._megnyit())
        # Helyi menü (Alkalmazások-billentyű / Shift+F10 / jobbklikk) minden levélen
        self.level_lista.Bind(wx.EVT_CONTEXT_MENU, self._level_menu)
        közép_j.Add(self.level_lista, 1, wx.EXPAND)
        közép.Add(közép_j, 1, wx.EXPAND)
        v.Add(közép, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        p.SetSizer(v)

    # A régi „Összes bejövő" gomb helyett menüpont; ez a mező már nem kell,
    # de a régi kód hivatkozhat rá – ártalmatlan helyettesítő.
    class _Noop:
        def Show(self, *a):
            pass

    def _menusav(self):
        """A teljes menüsáv: minden művelet szépen, szekciókra bontva."""
        mb = wx.MenuBar()

        m_fiok = wx.Menu()
        self._mi(m_fiok, "Fiók &hozzáadása…", self._fiok_add)
        self._mi(m_fiok, "Fiók &törlése", self._fiok_del)
        self.osszes_menu = self._mi(
            m_fiok, "&Összes bejövő (minden fiók)", self._osszes_bejovo)
        m_fiok.AppendSeparator()
        self._mi(m_fiok, "&Frissítés  (F5)", lambda e: self._frissit_aktualis())
        self._mi(m_fiok, "További levelek &betöltése  (B)",
                 lambda e: self._tovabb_betolt())
        self._mi(m_fiok, "&Keresés…", self._keres)
        self._mi(m_fiok, "⚙ &Beállítások (fiókok, értesítők, címjegyzék)…",
                 self._beallitasok)
        m_fiok.AppendSeparator()
        self._mi(m_fiok, "Be&zárás  (Alt+F4)", lambda e: self.Close())
        mb.Append(m_fiok, "&Fiók")

        m_level = wx.Menu()
        self._mi(m_level, "Ú&j levél  (N)", self._uj)
        self._mi(m_level, "&Megnyitás külön ablakban  (Enter)",
                 lambda e: self._megnyit())
        m_level.AppendSeparator()
        self._mi(m_level, "&Válasz  (R vagy Ctrl+R)", lambda e: self._menu_level_akcio(
            lambda msg, f: self._valasz(msg=msg, fiok=f)))
        self._mi(m_level, "Válasz min&denkinek", lambda e: self._menu_level_akcio(
            lambda msg, f: self._valasz(msg=msg, fiok=f, mind=True)))
        self._mi(m_level, "Válasz a &levelezőlistára  (L)",
                 lambda e: self._menu_level_akcio(self._listara_valasz))
        self._mi(m_level, "&Továbbítás  (F vagy Ctrl+F)", lambda e: self._menu_level_akcio(
            lambda msg, f: self._tovabbit(msg=msg, fiok=f)))
        m_level.AppendSeparator()
        self._mi(m_level, "&Olvasottnak jelölés", lambda e: self._jelol(True))
        self._mi(m_level, "Ol&vasatlannak jelölés", lambda e: self._jelol(False))
        self._mi(m_level, "&Csatolmány mentése…", lambda e: self._menu_level_akcio(
            lambda msg, f: self._csat_ment_msg(msg)))
        m_level.AppendSeparator()
        self._mi(m_level, "&AI-összefoglaló  (AI-kulcs kell)",
                 lambda e: self._menu_level_akcio(
                     lambda msg, f: self._ai_osszefoglalo(msg)))
        m_level.AppendSeparator()
        self._mi(m_level, "Összes &kijelölése  (Ctrl+A)",
                 lambda e: self._mind_kijelol())
        self._mi(m_level, "Ki&vágás  (Ctrl+X)",
                 lambda e: self._masol_vagolapra(cut=True))
        self._mi(m_level, "Máso&lás  (Ctrl+C)",
                 lambda e: self._masol_vagolapra(cut=False))
        self._mi(m_level, "&Beillesztés ebbe a mappába  (Ctrl+V)",
                 lambda e: self._beilleszt())
        m_level.AppendSeparator()
        self._mi(m_level, "Tör&lés – Kukába  (Del)", self._torol)
        self._mi(m_level, "Vé&gleges törlés  (Shift+Del)",
                 lambda e: self._torol(None, vegleges_kenyszer=True))
        mb.Append(m_level, "&Levél")

        m_seg = wx.Menu()
        self._mi(m_seg, "&Súgó  (F1)", lambda e: self._sugo())
        self._mi(m_seg, "❤ &Támogatás", self._tamogatas)
        self._mi(m_seg, "&Névjegy", self._nevjegy)
        mb.Append(m_seg, "&Segítség")

        self.osszes_gomb = MailFrame._Noop()   # a régi hivatkozás ártalmatlanná
        return mb

    def _mi(self, menu, cimke, kez):
        it = menu.Append(wx.ID_ANY, cimke)
        self.Bind(wx.EVT_MENU, kez, it)
        return it

    def _menu_level_akcio(self, callback):
        """A kijelölt levélre: háttérben letölti a teljes üzenetet, majd
        callback(msg, fiok). Így a menüből is működik, ha a levél nincs megnyitva."""
        info = self._kivalasztott()
        if not info:
            self._mond("Előbb válassz egy levelet a listából.")
            return
        self._uzenet_lekero(info, callback)

    # ---- indulás / hozzájárulás ----
    def _indul(self):
        if not MC.hozzajarulas_megvan():
            dlg = HozzajarulasDialog(self, self.main)
            ok = dlg.ShowModal()
            dlg.Destroy()
            if ok != wx.ID_OK:
                self.Close()
                return
        self._fiokok = MC.fiokok_betolt()
        self._fiok_valaszto_feltolt()
        if not self._fiokok:
            self._mond("Üdv a Super Mailben! Előbb adj hozzá egy e-mail fiókot "
                       "a Fiók hozzáadása gombbal.")
            self._fiok_add(None)
        else:
            self.fiok_valaszto.SetSelection(0)
            self._fiok_valt(None)

    def _fiok_valaszto_feltolt(self):
        self.fiok_valaszto.Set([f.get("nev") or f.get("email")
                                for f in self._fiokok])
        self.osszes_gomb.Show(len(self._fiokok) > 1)
        self.Layout()

    # ---- fiókok ----
    def _fiok_add(self, e):
        dlg = FiokDialog(self, self.main)
        if dlg.ShowModal() == wx.ID_OK and dlg.eredmeny:
            self._fiokok = [f for f in self._fiokok
                            if f["email"] != dlg.eredmeny["email"]]
            self._fiokok.append(dlg.eredmeny)
            MC.fiokok_ment(self._fiokok)
            self._fiok_valaszto_feltolt()
            self.fiok_valaszto.SetSelection(len(self._fiokok) - 1)
            self._fiok_valt(None)
        dlg.Destroy()

    def _fiok_del(self, e):
        if not self._aktiv:
            return
        cim = self._aktiv["email"]
        if wx.MessageBox(f"Törlöd a(z) {cim} fiókot? A tárolt app-jelszava is "
                         "véglegesen törlődik.", "Fiók törlése",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        MC.fiok_torol(cim)
        self._fiokok = MC.fiokok_betolt()
        self._fiok_valaszto_feltolt()
        self._aktiv = None
        self.level_lista.Clear()
        if self._fiokok:
            self.fiok_valaszto.SetSelection(0)
            self._fiok_valt(None)
        self._mond(f"A(z) {cim} fiók törölve.")

    def _fiok_valt(self, e):
        i = self.fiok_valaszto.GetSelection()
        if 0 <= i < len(self._fiokok):
            self._aktiv = self._fiokok[i]
            self._mappak_betolt()

    # ---- mappák + lista ----
    def _mappak_betolt(self):
        if not self._aktiv:
            return
        if self._aktiv.get("protokoll") == "pop":
            self._mappak_raw = self._mappakkal_osszes(["INBOX"])
            self.mappa_lista.Set([MC.OSSZES_NEV if m == MC.OSSZES_MAPPA
                                  else "Beérkezett (POP3)"
                                  for m in self._mappak_raw])
            self._mappa = "INBOX"
            self._mappa_kijelol("INBOX")
            self._frissit()
            return
        self._mond("Mappák betöltése…")

        def munka():
            k = _kliens(self._aktiv).kapcsolodik()
            m = k.mappak()
            k.bezar()
            return m
        _hatterben(munka, self._mappak_kesz, self._halo_hiba)

    def _mappak_kesz(self, mappak):
        if self._closing:
            return
        # a NYERS neveket megőrizzük (ezekkel megy az IMAP select/fetch),
        # de a DEKÓDOLT (felolvasható) neveket jelenítjük meg; a Beérkezett felül
        mappak = self._mappakkal_osszes(self._mappak_rendez(mappak))
        self._mappak_raw = mappak
        self.mappa_lista.Set([MC.OSSZES_NEV if m == MC.OSSZES_MAPPA
                              else MC.mappa_display(m) for m in mappak])
        # A Beérkezett a kiinduló nézet (az Összes bejövő fölötte áll, de azt a
        # felhasználó válassza – ne töltsünk le magától minden fiókot).
        elso = next((m for m in mappak if m != MC.OSSZES_MAPPA), "INBOX")
        self._mappa = elso
        self._mappa_kijelol(elso)
        self._frissit()

    def _mappakkal_osszes(self, mappak):
        """Az „Összes bejövő" ÁL-MAPPA a lista LEGELEJÉRE, ha egynél több fiók
        van. A felhasználó egyesített MAPPÁT várt (mint a Thunderbirdben), nem
        egy menüpontot – így a mappák közt nyilazva magától rátalál."""
        mappak = list(mappak or [])
        if len(getattr(self, "_fiokok", []) or []) > 1:
            return [MC.OSSZES_MAPPA] + mappak
        return mappak

    @staticmethod
    def _mappak_rendez(mappak):
        """A Beérkezett (INBOX) MINDIG legfelül; utána a szokásos rendszer-mappák
        (Elküldött, Piszkozatok, Kuka, Spam, Archívum), majd a többi ábécében."""
        rendszer = ["sent", "elküld", "kimen", "draft", "piszkoz", "trash",
                    "kuka", "deleted", "junk", "spam", "levélszem", "archiv",
                    "archív"]

        def kulcs(m):
            ml = (m or "").lower()
            if ml == "inbox":
                return (0, "")
            for r, nev in enumerate(rendszer):
                if nev in ml:
                    return (1, f"{r:02d}{ml}")
            return (2, ml)
        return sorted(mappak, key=kulcs)

    def _mappa_valt(self, e):
        i = self.mappa_lista.GetSelection()
        raw = getattr(self, "_mappak_raw", [])
        valasztott = raw[i] if 0 <= i < len(raw) else "INBOX"
        if valasztott == MC.OSSZES_MAPPA:      # az egyesített ÁL-MAPPA
            self._osszes_bejovo(None)
            return
        self._osszesitett = False
        self._mappa = valasztott
        self._frissit()

    def _frissit(self, csendes=False):
        """A lista újratöltése. `csendes`=True: háttér-frissítés – nem szövegel,
        csak akkor szól, ha ÚJ levél érkezett (ezt a _lista_kesz intézi)."""
        if not self._aktiv:
            return
        self._osszesitett = False
        fiok, mappa = self._aktiv, self._mappa
        limit = int(MC.altalanos_betolt().get("lista_limit", 50))
        self._utolso_limit = limit
        self._csendes_frissites = bool(csendes)
        if not csendes:
            self._mond(f"Levelek betöltése – {MC.mappa_display(mappa)}… "
                       "kis türelmet, amíg megjönnek.")

        def munka():
            k = _kliens(fiok).kapcsolodik()
            lista = (k.lista(limit) if isinstance(k, MC.Pop3Kliens)
                     else k.lista(mappa, limit))
            k.bezar()
            for it in lista:
                it["_fiok"] = fiok
                it["_mappa"] = mappa
            return lista
        _hatterben(munka, self._lista_kesz, self._halo_hiba)

    def _osszes_bejovo(self, e):
        """Minden fiók bejövő (INBOX) leveleit EGY listába gyűjti, fiók-jelöléssel.

        Három dolgot javítottunk itt a felhasználó jelzésére („nem dob be egy
        egyesített mappába, ahol minden levelemet látom"):
          • a levelek IDŐRENDBE kerülnek (eddig fiókonként egymás UTÁN jöttek,
            ami tíz fiókkal nem egyesített postaláda, hanem tíz egymás alá
            ragasztott lista);
          • a fiókonkénti darabszám a beállított listaméretet követi (eddig fix
            30/40 volt);
          • ha egy fiók nem válaszol, azt KIMONDJUK (eddig csendben kimaradt)."""
        if not self._fiokok:
            return
        self._osszesitett = True
        self._mappa = MC.OSSZES_MAPPA
        self._mappa_kijelol(MC.OSSZES_MAPPA)
        self._mond("Minden fiók bejövő leveleinek betöltése…")
        fiokok = list(self._fiokok)
        limit = int(MC.altalanos_betolt().get("lista_limit", 50))
        self._osszes_fiok_db = len(fiokok)
        self._osszes_hibas = []

        def munka():
            egyben, hibas = [], []
            for fiok in fiokok:
                nev = fiok.get("nev") or fiok.get("email") or "ismeretlen fiók"
                try:
                    k = _kliens(fiok).kapcsolodik()
                    lista = (k.lista(limit) if isinstance(k, MC.Pop3Kliens)
                             else k.lista("INBOX", limit))
                    k.bezar()
                    for it in lista:
                        it["_fiok"] = fiok
                        it["_mappa"] = "INBOX"
                    egyben.extend(lista)
                except Exception:
                    hibas.append(nev)
            return MC.rendez_ido_szerint(egyben), hibas

        def kesz(eredmeny):
            lista, hibas = eredmeny
            self._osszes_hibas = hibas
            self._lista_kesz(lista)

        _hatterben(munka, kesz, self._halo_hiba)

    def _mappa_kijelol(self, raw_nev: str) -> None:
        """A mappalistában kijelöli a megadott (nyers nevű) mappát, ha ott van –
        így a menüből indított Összes bejövő is látszik a mappák közt."""
        raw = getattr(self, "_mappak_raw", [])
        if raw_nev in raw:
            try:
                self.mappa_lista.SetSelection(raw.index(raw_nev))
            except Exception:
                pass

    def _frissit_aktualis(self):
        """A jelenlegi nézetet frissíti (aggregált vagy egy-fiók)."""
        if self._osszesitett:
            self._osszes_bejovo(None)
        else:
            self._frissit()

    def _sor_szoveg(self, info):
        """Egy levél listasora – a TARTALMA a Beállítás → Általános fülön
        szabható testre (feladó / e-mail cím / tárgy / idő), és az OLVASATLAN
        állapotot SZÓVAL is kimondjuk (nem csak egy jellel, amit a képernyő-
        olvasó könnyen elhallgat)."""
        cfg = MC.altalanos_betolt()
        reszek = []
        if cfg.get("lista_allapot", True) and not info.get("olvasott"):
            reszek.append("olvasatlan")
        if self._osszesitett:
            f = info.get("_fiok") or {}
            reszek.append("[%s]" % (f.get("nev") or f.get("email") or ""))
        felado = (info.get("felado", "") or "").strip()
        if cfg.get("lista_felado", True):
            # a „Név <cim@pelda.hu>" formából csak a NEVET, ha kérték a címet
            # külön (vagy ha a cím nem kell)
            nev = re.sub(r"\s*<[^>]*>\s*", "", felado).strip().strip('"')
            reszek.append(nev or felado)
        if cfg.get("lista_cim", False):
            m = re.search(r"<([^>]+)>", felado)
            cim = m.group(1) if m else (felado if "@" in felado else "")
            if cim:
                reszek.append(cim)
        if cfg.get("lista_targy", True):
            reszek.append(info.get("targy", "") or "(nincs tárgy)")
        if cfg.get("lista_ido", True):
            reszek.append(info.get("datum", ""))
        if info.get("csatolmany"):
            reszek.append("csatolmány")
        return " — ".join(r for r in reszek if r)

    def _lista_kesz(self, lista):
        if self._closing:
            return
        self._lista = lista
        # a feladókat felvesszük a címjegyzékbe (passzív tanulás, csak új címek)
        try:
            MC.cimjegyzek_tanul([info.get("felado", "") for info in lista])
        except Exception:
            pass
        # új-levél értesítő (Beérkezett, egy-fiók nézet, IMAP)
        if (not self._osszesitett and self._aktiv
                and self._aktiv.get("protokoll") != "pop"
                and (self._mappa or "").upper() == "INBOX"):
            self._uj_level_ellenoriz(self._aktiv, lista)
        self.level_lista.Set([self._sor_szoveg(info) for info in lista])
        if getattr(self, "_csendes_frissites", False):
            self._csendes_frissites = False     # háttér-frissítés: nem szövegel
            return
        tobb = (not self._osszesitett
                and len(lista) >= int(getattr(self, "_utolso_limit", 50)))
        self._tovabb_van = bool(tobb)     # a lista alján ezt is odamondjuk
        if self._osszesitett:
            hibas = getattr(self, "_osszes_hibas", [])
            szoveg = ("%d levél %d fiók bejövőjéből, időrendben, a legfrissebb "
                      "elöl; mindegyiknél a fiók nevével."
                      % (len(lista), getattr(self, "_osszes_fiok_db", 0)))
            if hibas:
                # NEM némán hagyjuk ki a hibás fiókot: eddig egy `continue`
                # elnyelte, és a felhasználónak csak kevesebb levele lett.
                szoveg += (" Figyelem: %d fiók nem válaszolt: %s."
                           % (len(hibas), ", ".join(hibas)))
            self._mond(szoveg)
        else:
            self._mond(f"{len(lista)} levél a(z) "
                       f"{MC.mappa_display(self._mappa)} mappában."
                       + (" A B betűvel tölthetsz be továbbiakat." if tobb else ""))

    def _lista_ujrarajzol(self):
        """A meglévő listát újrarajzolja (pl. ha a megjelenítendő mezők
        beállítása változott) – a kijelölést megtartva, hálózat nélkül."""
        if self._closing or not self._lista:
            return
        kijel = self.level_lista.GetSelection()
        self.level_lista.Set([self._sor_szoveg(i) for i in self._lista])
        if 0 <= kijel < self.level_lista.GetCount():
            self.level_lista.SetSelection(kijel)

    def _lista_hozzafuz(self, lista):
        """A lapozással behúzott KÖVETKEZŐ adag hozzáfűzése a listához."""
        if self._closing:
            return
        if not lista:
            self._mond("Nincs több betölthető levél ebben a mappában.")
            return
        try:
            MC.cimjegyzek_tanul([info.get("felado", "") for info in lista])
        except Exception:
            pass
        self._lista.extend(lista)
        for info in lista:
            self.level_lista.Append(self._sor_szoveg(info))
        self._mond(f"Még {len(lista)} levél betöltve – összesen "
                   f"{len(self._lista)}. A B betűvel jöhet a következő adag.")

    def _tovabb_betolt(self):
        """A KÖVETKEZŐ adag levél betöltése az aktuális mappából (lapozás, B)."""
        if self._osszesitett:
            self._mond("Az Összes bejövő nézetben nincs lapozás – válassz egy "
                       "konkrét mappát a továbbiakhoz.")
            return
        if not self._aktiv:
            return
        fiok, mappa = self._aktiv, self._mappa
        offset = len(self._lista)
        limit = int(MC.altalanos_betolt().get("lista_limit", 50))
        self._mond("További levelek betöltése… kis türelmet.")

        def munka():
            k = _kliens(fiok).kapcsolodik()
            lista = (k.lista(limit, offset) if isinstance(k, MC.Pop3Kliens)
                     else k.lista(mappa, limit, offset))
            k.bezar()
            for it in lista:
                it["_fiok"] = fiok
                it["_mappa"] = mappa
            return lista
        _hatterben(munka, self._lista_hozzafuz, self._halo_hiba)

    def _uj_level_ellenoriz(self, fiok, lista):
        """Új levél észlelése a legfrissebb INBOX-UID alapján; ha nőtt, értesít."""
        em = (fiok.get("email") or "").lower()
        try:
            legujabb = max((int(it["uid"]) for it in lista if it.get("uid")),
                           default=0)
        except (ValueError, TypeError):
            return
        elozo = self._utolso_uid.get(em)
        self._utolso_uid[em] = legujabb
        if elozo is not None and legujabb > elozo:      # tényleg új érkezett
            self._ertesit(fiok)

    def _ertesit(self, fiok):
        """A fiókhoz beállított értesítés: hang lejátszása VAGY szöveg felolvasása."""
        try:
            cfg = MC.ertesito_fiok(fiok.get("email", ""))
        except Exception:
            cfg = {"tipus": "szoveg", "szoveg": "Új leveled érkezett."}
        tipus = cfg.get("tipus", "szoveg")
        if tipus == "nincs":
            return
        if tipus == "hang" and cfg.get("hang"):
            siker, _uz = ertesito_hang(cfg["hang"])
            if siker:
                return
        # szöveg (vagy ha a hang nem szólalt meg): felolvasás
        self._mond(cfg.get("szoveg") or "Új leveled érkezett.")

    def _ertesito_beallit(self, e=None):
        """Az értesítők a Beállítások Értesítők-fülén állíthatók."""
        self._beallitasok(lap=1)

    def _level_valt(self, e):
        # A kijelölés csak KIJELÖL (a képernyőolvasó felolvassa a tételt); a
        # levél KÜLÖN ablakban az Enterrel (vagy dupla kattintással) nyílik.
        if e:
            e.Skip()

    # ---- a lista SZÉLE (felhasználói kérés) ----------------------------

    def _lista_szel(self, e, lista, fajta):
        """A lista TETEJÉN a felfelé nyíl (és az alján a lefelé) ELNYELŐDIK.

        Miért? Mert a szélen a nyíl „lefut", de nem mozdul semmi – a
        képernyőolvasó viszont ÚJRA FELOLVASSA ugyanazt a sort, és ez gyors
        nyilazásnál végtelen ismétlésnek hallatszik. Ha nem engedjük tovább a
        billentyűt, nincs mit újramondani; helyette egy rövid „bling" jelzi a
        szélet (vagy egy tömör mondat, ha a felhasználó azt kérte)."""
        kod = e.GetKeyCode()
        fel = kod in (wx.WXK_UP, wx.WXK_NUMPAD_UP, wx.WXK_PAGEUP,
                      wx.WXK_NUMPAD_PAGEUP)
        le = kod in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN, wx.WXK_PAGEDOWN,
                     wx.WXK_NUMPAD_PAGEDOWN)
        if not (fel or le) or e.ShiftDown() or e.ControlDown():
            e.Skip()                      # a kijelölés-bővítést nem bántjuk
            return
        n = lista.GetCount()
        i = self._lista_index(lista)
        if n == 0 or i < 0:
            # NEM TUDJUK, hol állunk (pl. semmi nincs kijelölve, vagy több sor
            # van kijelölve) → SOHA nem nyelünk el billentyűt. Ez a szabály
            # azért van, mert a levéllista TÖBBSZÖRÖS kijelölésű (LB_EXTENDED),
            # és ott a `GetSelection()` mínusz egyet ad – emiatt a felfelé nyíl
            # egy kiadásban ELNYELŐDÖTT, vagyis megbénult a navigáció.
            e.Skip()
            return
        if fel and i <= 0:
            self._szel_jelzes(True, fajta)
            return                        # NEM Skip: itt áll meg a billentyű
        if le and i >= n - 1:
            self._szel_jelzes(False, fajta)
            return
        e.Skip()

    @staticmethod
    def _lista_index(lista) -> int:
        """Hol állunk a listában? Mínusz egy, ha ezt NEM tudjuk BIZTOSAN.

        A levéllista LB_EXTENDED (többszörös kijelölés), ahol a `GetSelection()`
        mínusz egyet ad – ezért a kijelöléseket kérdezzük. Ha nincs vagy több
        kijelölés van, inkább bevalljuk, hogy nem tudjuk (mínusz egy), és a
        hívó nem nyel el semmilyen billentyűt."""
        try:
            sel = list(lista.GetSelections())
        except Exception:
            sel = []
        if len(sel) == 1:
            return sel[0]
        if sel:
            return -1                     # több kijelölt sor: ne kockáztassunk
        try:
            return int(lista.GetSelection())
        except Exception:
            return -1

    def _szel_jelzes(self, teteje: bool, fajta: str) -> None:
        hol = "teteje" if teteje else "vége"
        szoveg = ("A mappalista %s." if fajta == "mappa"
                  else "A levéllista %s.") % hol
        if not teteje and fajta == "level" and getattr(self, "_tovabb_van", False):
            szoveg += " A B betűvel tölthetsz be továbbiakat."
        self._allapot_uzenet(szoveg)
        mod = str(MC.altalanos_betolt().get("lista_szel", "bling"))
        if mod == "bling":
            from . import hangok
            if hangok.bling(teteje):
                return                    # sikerült a hang – mondat nem kell
        self._mond(szoveg)

    def _kivalasztott(self):
        """A (fő) kijelölt levél info-dictje (fiókkal/mappával), vagy None."""
        sel = self.level_lista.GetSelections()
        i = sel[0] if sel else self.level_lista.GetSelection()
        return self._lista[i] if 0 <= i < len(self._lista) else None

    def _kivalasztottak(self):
        """MINDEN kijelölt levél info-dictje (a többszörös kijelöléshez)."""
        return [self._lista[i] for i in self.level_lista.GetSelections()
                if 0 <= i < len(self._lista)]

    def _mind_kijelol(self):
        n = self.level_lista.GetCount()
        for i in range(n):
            self.level_lista.SetSelection(i)
        self._mond(f"{n} levél kijelölve." if n else "Nincs levél a listában.")

    def _megnyit(self):
        info = self._kivalasztott()
        fiok = (info or {}).get("_fiok") or self._aktiv
        mappa = (info or {}).get("_mappa") or self._mappa
        if not info or not fiok:
            return
        self._mond("Levél megnyitása…")

        def munka():
            k = _kliens(fiok).kapcsolodik()
            if isinstance(k, MC.Pop3Kliens):
                msg = k.teljes(info["szam"])
            else:
                msg = k.teljes(info["uid"], mappa)
                try:
                    k.olvasottnak(info["uid"], mappa)
                except Exception:
                    pass
            k.bezar()
            return msg
        _hatterben(munka, lambda m: self._level_mutat(info, m, fiok),
                   self._halo_hiba)

    def _uzenet_lekero(self, info, kesz):
        """A kijelölt levél teljes üzenetét háttérben letölti, majd kesz(msg, fiok)."""
        fiok = (info or {}).get("_fiok") or self._aktiv
        mappa = (info or {}).get("_mappa") or self._mappa
        if not info or not fiok:
            return

        def munka():
            k = _kliens(fiok).kapcsolodik()
            msg = (k.teljes(info["szam"]) if isinstance(k, MC.Pop3Kliens)
                   else k.teljes(info["uid"], mappa))
            k.bezar()
            return msg
        _hatterben(munka, lambda m: kesz(m, fiok), self._halo_hiba)

    def _jelol(self, olvasott):
        """A kijelölt levelet olvasottnak/olvasatlannak jelöli (IMAP)."""
        info = self._kivalasztott()
        fiok = (info or {}).get("_fiok") or self._aktiv
        mappa = (info or {}).get("_mappa") or self._mappa
        if not info or not fiok or fiok.get("protokoll") == "pop":
            self._mond("Ez POP3-fióknál nem támogatott.")
            return

        def munka():
            k = _kliens(fiok).kapcsolodik()
            if olvasott:
                k.olvasottnak(info["uid"], mappa)
            else:
                k.olvasatlannak(info["uid"], mappa)
            k.bezar()
            return True
        _hatterben(munka,
                   lambda r: (self._mond("Olvasottnak jelölve." if olvasott
                                         else "Olvasatlannak jelölve."),
                              self._frissit_aktualis()),
                   self._halo_hiba)

    def _level_mutat(self, info, msg, fiok=None):
        if self._closing or msg is None:
            return
        fiok = fiok or self._aktiv
        self._aktiv_msg = msg
        self._aktiv_fiok = fiok
        mappa = (info or {}).get("_mappa") or self._mappa
        fej = MC.level_fejlec_info(msg)
        # KÜLÖN ablakban nyílik – ott kattinthatók a hivatkozások, és saját menü
        LevelOlvasoFrame(self, self.main, info, msg, fiok, mappa).Show()
        self._mond(f"Megnyitva külön ablakban: {fej['felado']}. Tárgy: "
                   f"{fej['targy']}.")

    # ---- műveletek ----
    def _uj(self, e):
        if self._aktiv:
            LevelIroDialog(self, self.main, self._aktiv).ShowModal()

    def _valasz(self, e=None, mind=False, msg=None, fiok=None,
                listara=""):
        msg = msg or getattr(self, "_aktiv_msg", None)
        fiok = fiok or getattr(self, "_aktiv_fiok", None) or self._aktiv
        if not (fiok and msg):
            return
        fej = MC.level_fejlec_info(msg)
        import email.utils
        cim = email.utils.parseaddr(msg.get("Reply-To") or fej["felado"])[1]
        cc = ", ".join(MC.cimzettek(msg.get("Cc", ""))) if mind else ""
        if listara:
            # LEVELEZŐLISTÁS VÁLASZ: a címzett maga a lista, nem a feladó –
            # és a másolat-mezőt üresen hagyjuk, hogy senki ne kapja duplán.
            cim, cc = listara, ""

        idezet = "\n\n> " + MC.level_szovegtorzs(msg).replace("\n", "\n> ")
        d = LevelIroDialog(self, self.main, fiok, cim,
                           "Re: " + fej["targy"], idezet,
                           msg.get("Message-ID"), torzsre=True)
        d.masolat.SetValue(cc)
        if listara:
            d.listanev = MC.lista_neve(msg) or listara
            _mondd(self.main, "Válasz a(z) %s listára. A levél a lista MINDEN "
                   "tagjához megy." % d.listanev)
        d.ShowModal()

    def _valasz_mind(self, e):
        self._valasz(mind=True)

    def _listara_valasz(self, msg, fiok):
        """Válasz a levelezőlistára: a címzett a lista, nem a feladó."""
        cim = MC.lista_cim(msg)
        if not cim:
            self._mond("Ez a levél nem levelezőlistáról jött. Az R betűvel "
                       "válaszolhatsz a feladónak.")
            return
        self._valasz(msg=msg, fiok=fiok, listara=cim)

    def _tovabbit(self, e=None, msg=None, fiok=None):
        msg = msg or getattr(self, "_aktiv_msg", None)
        fiok = fiok or getattr(self, "_aktiv_fiok", None) or self._aktiv
        if not (fiok and msg):
            return
        fej = MC.level_fejlec_info(msg)
        torzs = (f"\n\n--- Továbbított levél ---\nFeladó: {fej['felado']}\n"
                 f"Tárgy: {fej['targy']}\n\n{MC.level_szovegtorzs(msg)}")
        LevelIroDialog(self, self.main, fiok, "",
                       "Fwd: " + fej["targy"], torzs).ShowModal()

    def _level_menu(self, e):
        """Helyi menü a kijelölt levélre (Alkalmazások-billentyű / Shift+F10)."""
        info = self._kivalasztott()
        if not info:
            return
        m = wx.Menu()

        def add(cimke, kez):
            it = m.Append(wx.ID_ANY, cimke)
            self.Bind(wx.EVT_MENU, kez, it)

        add("Megnyitás", lambda ev: self._megnyit())
        add("Válasz", lambda ev: self._uzenet_lekero(
            info, lambda msg, f: self._valasz(msg=msg, fiok=f)))
        add("Válasz mindenkinek", lambda ev: self._uzenet_lekero(
            info, lambda msg, f: self._valasz(msg=msg, fiok=f, mind=True)))
        add("Továbbítás", lambda ev: self._uzenet_lekero(
            info, lambda msg, f: self._tovabbit(msg=msg, fiok=f)))
        m.AppendSeparator()
        add("Olvasottnak jelölés", lambda ev: self._jelol(True))
        add("Olvasatlannak jelölés", lambda ev: self._jelol(False))
        add("Csatolmány mentése", lambda ev: self._uzenet_lekero(
            info, lambda msg, f: self._csat_ment_msg(msg)))
        m.AppendSeparator()
        add("Levél / beszélgetés AI-összefoglalója  (AI-kulcs kell)",
            lambda ev: self._uzenet_lekero(
                info, lambda msg, f: self._ai_osszefoglalo(msg)))
        m.AppendSeparator()
        add("Összes kijelölése  (Ctrl+A)", lambda ev: self._mind_kijelol())
        add("Kivágás  (Ctrl+X)", lambda ev: self._masol_vagolapra(cut=True))
        add("Másolás  (Ctrl+C)", lambda ev: self._masol_vagolapra(cut=False))
        add("Beillesztés ebbe a mappába  (Ctrl+V)",
            lambda ev: self._beilleszt())
        m.AppendSeparator()
        add("Törlés", lambda ev: self._torol(None))
        self.level_lista.PopupMenu(m)
        m.Destroy()

    def _ai_osszefoglalo(self, msg):
        if not msg:
            return
        fej = MC.level_fejlec_info(msg)
        torzs = MC.level_szovegtorzs(msg)
        if not torzs.strip():
            self._mond("Nincs szöveg, amit összefoglalhatnék.")
            return
        self._mond("AI-összefoglaló készül…")
        prompt = (
            "Foglald össze tömören, magyarul ezt az e-mailt (ha idézett "
            "előzményt tartalmaz, a beszélgetés egészét): mi a lényege, mit "
            "kérnek vagy ajánlanak, és van-e teendő. Pár mondat legyen.\n\n"
            f"Feladó: {fej['felado']}\nTárgy: {fej['targy']}\n\n"
            f"A levél szövege:\n{torzs[:6000]}")

        def munka():
            from superdl import aiclient
            return aiclient.chat(
                prompt, system="Segítőkész, tömör magyar asszisztens vagy.")
        _hatterben(munka, self._ai_kesz, self._ai_hiba)

    def _ai_kesz(self, szoveg):
        if self._closing:
            return
        txt = "— AI-ÖSSZEFOGLALÓ —\n\n" + (szoveg or "").strip()
        try:
            from superdl.helpdialog import show_help
            show_help(self, "AI-összefoglaló", txt)
        except Exception:
            wx.MessageBox(txt, "AI-összefoglaló",
                          wx.OK | wx.ICON_INFORMATION, self)
        self._mond("Elkészült az AI-összefoglaló.")

    def _ai_hiba(self, ex):
        if self._closing:
            return
        uz = (f"Az AI-összefoglaló nem sikerült: {ex}  Ehhez AI-kulcs kell – "
              "állítsd be a SuperDL Beállítások, AI fülén (OpenAI, Gemini, "
              "Anthropic vagy xAI). A kulcs a gépeden marad.")
        self._mond(uz)
        wx.MessageBox(uz, "AI-összefoglaló", wx.OK | wx.ICON_INFORMATION, self)

    def _kuka_mappa(self):
        """A Kuka/Trash mappa NYERS neve az aktuális fiókban (vagy None). Ide
        helyezzük a törölt leveleket – ez a megbízható, visszaállítható törlés."""
        for m in getattr(self, "_mappak_raw", []):
            ml = (m or "").lower()
            if any(s in ml for s in ("trash", "kuka", "deleted", "törölt")):
                return m
        return None

    def _torol(self, e, vegleges_kenyszer=False):
        infok = self._kivalasztottak()
        if not infok:
            egy = self._kivalasztott()
            infok = [egy] if egy else []
        if not infok:
            return
        n = len(infok)
        # a törlés UTÁNI fókuszhoz: az első kijelölt sor indexe
        sel = self.level_lista.GetSelections()
        elso_idx = sel[0] if sel else self.level_lista.GetSelection()
        kuka = self._kuka_mappa()
        # KUKÁBA helyezés = visszaállítható → NEM kérdezünk. VÉGLEGES törlésnél
        # (nincs Kuka, a Kukából törlünk, vagy Shift+Del) MINDIG kérdezünk.
        vegleges = vegleges_kenyszer or (not kuka) or (self._mappa == kuka)
        if vegleges:
            kerdes = (f"VÉGLEGESEN törlöd a kijelölt {n} levelet? Ez NEM vonható "
                      "vissza!" if n > 1
                      else "VÉGLEGESEN törlöd ezt a levelet? Ez NEM vonható "
                      "vissza!")
            if wx.MessageBox(kerdes, "Végleges törlés",
                             wx.YES_NO | wx.ICON_WARNING, self) != wx.YES:
                return

        torlendo = list(infok)
        torlendo_id = {id(x) for x in torlendo}

        def munka():
            from collections import defaultdict
            csoport = defaultdict(list)
            for it in torlendo:
                f = it.get("_fiok") or self._aktiv
                m = it.get("_mappa") or self._mappa
                csoport[(id(f), m)].append((f, m, it))
            total = 0
            for tetelek in csoport.values():
                f, m = tetelek[0][0], tetelek[0][1]
                k = _kliens(f).kapcsolodik()
                if isinstance(k, MC.Pop3Kliens):
                    for _, _, it in tetelek:
                        k.torol(it["szam"])
                else:
                    uidok = ",".join(it["uid"] for _, _, it in tetelek)
                    # VÉGLEGES kényszernél sosem tesszük Kukába; különben a fiók
                    # Kukájába helyezzük (visszaállítható), ha van és nem onnan
                    # törlünk
                    kuka_f = (None if vegleges_kenyszer
                              else (self._kuka_mappa() if f is self._aktiv
                                    else None))
                    if kuka_f and m != kuka_f:
                        if not k.athelyez(uidok, kuka_f, m):
                            k.torol(uidok, m)
                    else:
                        k.torol(uidok, m)
                k.bezar()
                total += len(tetelek)
            return total

        def kesz(r):
            if self._closing:
                return
            self._mond(f"{r} levél " + ("véglegesen törölve."
                                        if vegleges else "a Kukába helyezve."))
            # a törölteket HELYBEN kivesszük, és a KÖVETKEZŐ levélre lépünk
            # (nem töltjük újra a szerverről – gyors és megtartja a helyed)
            self._lista = [it for it in self._lista
                           if id(it) not in torlendo_id]
            self.level_lista.Set([self._sor_szoveg(it) for it in self._lista])
            if self._lista:
                uj = max(0, min(elso_idx, len(self._lista) - 1))
                self.level_lista.SetSelection(uj)
                self._mond(self._sor_szoveg(self._lista[uj]))
            else:
                self._mond("Nincs több levél ebben a mappában.")
        _hatterben(munka, kesz, self._halo_hiba)

    # ---- vágólap: kivágás/másolás (Ctrl+X/C) → beillesztés (Ctrl+V) ----
    def _masol_vagolapra(self, cut):
        infok = self._kivalasztottak()
        if not infok:
            self._mond("Előbb jelölj ki legalább egy levelet.")
            return
        fiok = infok[0].get("_fiok") or self._aktiv
        if not fiok or fiok.get("protokoll") == "pop":
            self._mond("POP3-fióknál a mozgatás nem támogatott – nincsenek "
                       "szerver-mappák.")
            return
        mappa = infok[0].get("_mappa") or self._mappa
        # csak az ugyanabból a fiókból+mappából valókat vesszük (egyszerű, biztos)
        uidok = [it["uid"] for it in infok
                 if (it.get("_fiok") or self._aktiv) is fiok
                 and (it.get("_mappa") or self._mappa) == mappa]
        if not uidok:
            self._mond("A kijelölt levelek nem egy mappából valók.")
            return
        self._vagolap = {"fiok": fiok, "mappa": mappa, "uidok": uidok,
                         "cut": bool(cut)}
        self._mond(f"{len(uidok)} levél {'kivágva' if cut else 'másolva'}. "
                   "Állj a cél-mappára, és nyomj Ctrl+V-t a beillesztéshez.")

    def _beilleszt(self):
        vp = self._vagolap
        if not vp or not vp.get("uidok"):
            self._mond("A vágólap üres. Előbb Ctrl+X (kivágás) vagy Ctrl+C "
                       "(másolás) egy vagy több levélen.")
            return
        if not self._aktiv or self._aktiv.get("protokoll") == "pop":
            self._mond("Ide nem lehet beilleszteni (POP3-fiók).")
            return
        if self._aktiv is not vp["fiok"]:
            self._mond("A mozgatás csak ugyanazon a fiókon belül lehetséges.")
            return
        cel, forras = self._mappa, vp["mappa"]
        if cel == forras:
            self._mond("A cél-mappa ugyanaz, mint a forrás – válassz másik mappát.")
            return
        uidok = ",".join(vp["uidok"])
        cut, fiok, n = vp["cut"], vp["fiok"], len(vp["uidok"])
        self._mond(f"{n} levél {'áthelyezése' if cut else 'másolása'} ide: "
                   f"{MC.mappa_display(cel)}…")

        def munka():
            k = _kliens(fiok).kapcsolodik()
            ok = (k.athelyez(uidok, cel, forras) if cut
                  else k.masol(uidok, cel, forras))
            k.bezar()
            return ok

        def kesz(ok):
            if self._closing:
                return
            if ok:
                self._mond(f"{n} levél {'áthelyezve' if cut else 'másolva'} ide: "
                           f"{MC.mappa_display(cel)}.")
                if cut:
                    self._vagolap = None
                self._frissit_aktualis()
            else:
                self._mond("A művelet nem sikerült (a szerver elutasította).")
        _hatterben(munka, kesz, self._halo_hiba)

    def _keres(self, e):
        if not self._aktiv:
            return
        dlg = wx.TextEntryDialog(self, "Mit keresel? (feladó, tárgy vagy szöveg)",
                                 "Keresés")
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        kif = dlg.GetValue().strip()
        dlg.Destroy()
        if not kif:
            return
        self._osszesitett = False
        fiok, mappa = self._aktiv, self._mappa
        self._mond(f"Keresés: {kif}…")

        def munka():
            k = _kliens(fiok).kapcsolodik()
            if isinstance(k, MC.Pop3Kliens):
                lista = [x for x in k.lista(100)
                         if kif.lower() in (x.get("targy", "") + " "
                                            + x.get("felado", "")).lower()]
            else:
                lista = k.keres(kif, mappa, 50)
            k.bezar()
            for it in lista:
                it["_fiok"] = fiok
                it["_mappa"] = mappa
            return lista
        _hatterben(munka, self._lista_kesz, self._halo_hiba)

    def _csat_ment(self, e):
        self._csat_ment_msg(getattr(self, "_aktiv_msg", None))

    def _csat_ment_msg(self, msg):
        if not msg:
            return
        csat = MC.csatolmanyok(msg)
        if not csat:
            self._mond("Ehhez a levélhez nincs csatolmány.")
            return
        for nev, adat in csat:
            with wx.FileDialog(self, f"Csatolmány mentése: {nev}",
                               defaultFile=nev,
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    try:
                        with open(dlg.GetPath(), "wb") as f:
                            f.write(adat)
                        self._mond(f"Mentve: {nev}.")
                    except OSError as ex:
                        self._mond(f"Nem sikerült menteni: {ex}")

    # ---- segédek ----
    def _on_key(self, e):
        k = e.GetKeyCode()
        m = e.GetModifiers()
        if k == wx.WXK_F1:
            self._sugo()
        elif (k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
              and self.FindFocus() is self.level_lista):
            self._megnyit()                       # Enter a listán → külön ablak
        elif m == wx.MOD_CONTROL and k == ord("V"):
            self._beilleszt()                     # beillesztés az AKTUÁLIS mappába
        elif (m == wx.MOD_CONTROL and k == ord("A")
              and self.FindFocus() is self.level_lista):
            self._mind_kijelol()
        elif (m == wx.MOD_CONTROL and k == ord("C")
              and self.FindFocus() is self.level_lista):
            self._masol_vagolapra(cut=False)
        elif (m == wx.MOD_CONTROL and k == ord("X")
              and self.FindFocus() is self.level_lista):
            self._masol_vagolapra(cut=True)
        elif m == 0 and k == ord("N"):
            self._uj(None)
        elif k == ord("R") and m in (0, wx.MOD_CONTROL):
            self._menu_level_akcio(lambda msg, f: self._valasz(msg=msg, fiok=f))
        elif k == ord("R") and m == wx.MOD_SHIFT:
            self._menu_level_akcio(
                lambda msg, f: self._valasz(msg=msg, fiok=f, mind=True))
        elif k == ord("F") and m in (0, wx.MOD_CONTROL):
            self._menu_level_akcio(
                lambda msg, f: self._tovabbit(msg=msg, fiok=f))
        elif k == ord("L") and m == 0:
            # L = válasz a LEVELEZŐLISTÁRA (a lista címét a levél fejléce adja)
            self._menu_level_akcio(self._listara_valasz)
        elif m == 0 and k == ord("B"):
            self._tovabb_betolt()                 # következő adag levél (lapozás)
        elif k == wx.WXK_F5:
            self._frissit_aktualis()
        elif k == wx.WXK_DELETE:
            # Del = Kukába (nem kérdez); Shift+Del = VÉGLEGES törlés (kérdez)
            self._torol(None, vegleges_kenyszer=(m == wx.MOD_SHIFT))
        else:
            # Az ESC SZÁNDÉKOSAN nem zár be (a tesztelő kérése): egy levelezőt
            # nem szerencsés véletlen Escape-pel bezárni. Kilépés: Alt+F4, a
            # Fiók menü „Bezárás” pontja, vagy az ablak bezáró gombja.
            e.Skip()

    def _sugo(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Súgó – Super Mail", _SUGO)
        except Exception:
            wx.MessageBox(_SUGO, "Súgó – Super Mail",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _tamogatas(self, e):
        try:
            from superdl.supportwin import SupportDialog
            d = SupportDialog(self)
            d.ShowModal()
            d.Destroy()
        except Exception:
            wx.MessageBox(
                "Köszönöm, hogy támogatnál! A támogatási lehetőségek a SuperDL "
                "súgójában (F1) is elérhetők. Egyetlen funkciót sem zár el.",
                "Támogatás", wx.OK | wx.ICON_INFORMATION, self)

    def _nevjegy(self, e):
        wx.MessageBox(
            "Super Mail – akadálymentes e-mail kliens a SuperDL-hez. Kizárólag "
            "emailezés (IMAP/POP3/SMTP), adatvédelem az első helyen: semmit nem "
            "továbbítunk sehová. Készítette: Kőrösmezey Dávid.",
            "Névjegy – Super Mail", wx.OK | wx.ICON_INFORMATION, self)

    def _mond(self, szoveg):
        _mondd(self.main, szoveg)

    def _halo_hiba(self, ex):
        if self._closing:
            return
        uz = (f"Hálózati/hitelesítési hiba: {ex}. Ellenőrizd a fiók adatait "
              "(app-jelszó), az internetet, valamint a szerver nevét és portját.")
        self._mond(uz)

    def _on_close(self, e):
        self._closing = True
        try:
            self._ellenor_timer.Stop()
        except Exception:
            pass
        if getattr(self.main, "_mail_win", None) is self:
            self.main._mail_win = None
        e.Skip()
