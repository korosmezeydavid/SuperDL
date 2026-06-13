#!/usr/bin/env python3
"""SuperDL - akadálymentes grafikus felület (wxPython).

A wxPython natív Windows-vezérlőket használ, így az NVDA, a JAWS és a
Narrátor is hibátlanul felolvassa. Minden funkció elérhető billentyűzetről:

  Ctrl+N   URL-mező fókuszálása (új letöltés)
  Ctrl+T   torrentfájl megnyitása
  Ctrl+O   URL-lista megnyitása fájlból
  Ctrl+R   feliratkozás podcast/RSS-csatornára
  Ctrl+L   feliratkozások kezelése
  Ctrl+D   letöltési lista fókuszálása
  Ctrl+E   eseménynapló fókuszálása
  Ctrl+J   összefoglaló felolvasása (mennyi van hátra)
  Delete   futó letöltés leállítása; befejezett/hibás elem törlése
  Shift+Del  a kijelölt elem eltávolítása a listából
  Ctrl+M   célmappa megnyitása
  Ctrl+Q   kilépés

Torrenthez magnet-linket is beilleszthetsz az URL-mezőbe.
Időzítéshez töltsd ki az Időzítés mezőt (pl. 03:00 vagy +2h).
"""

import json
import sys
import threading
import time
from pathlib import Path

import wx
import wx.adv

sys.path.insert(0, str(Path(__file__).parent))

from superdl.manager import DownloadManager, parse_when
from superdl.media import is_media_url
from superdl.segment import parse_limit
from superdl.torrent import is_torrent_url
from superdl.feeds import FeedManager
from superdl.report import build_summary
from superdl.speech import Speaker
from superdl import updater, selfupdate, __version__

try:
    import winsound
except ImportError:
    winsound = None

SETTINGS_FILE = Path.home() / ".superdl.json"

ABOUT_TEXT = (
    f"SuperDL {__version__} – akadálymentes, többfunkciós, többszálú letöltő\n\n"
    "Készítette: Kőrösmezey Dávid\n"
    "Elérhetőség: korosmezey.david.richard@gmail.com\n\n"
    "Egy program, amely közvetlen fájlokat, médiaoldalakat és torrenteket "
    "tölt le – kiemelt hangsúllyal a teljes, minden szintű "
    "képernyőolvasó-támogatáson. A cél, hogy a letöltés mindenki számára "
    "egyszerű és átlátható legyen.\n\n"
    "Felhasznált, nyílt forráskódú összetevők és licenceik:\n"
    "  • yt-dlp – médialetöltő motor (Unlicense)\n"
    "  • aria2 – torrent- és letöltőmotor (GPL v2)\n"
    "  • wxPython – grafikus felület (wxWindows licenc)\n"
    "  • feedparser – RSS/podcast (BSD)\n"
    "  • requests – HTTP (Apache 2.0)\n\n"
    "Fontos: csak olyan tartalmat tölts le és ossz meg (seedelj), "
    "amelyhez jogod van. A program technológiája legális; a felelősség "
    "a letöltött tartalomért a felhasználóé."
)

HOWITWORKS_TEXT = (
    "Hogyan dolgozik a SuperDL?\n\n"
    "Amikor beillesztesz egy hivatkozást, a program automatikusan eldönti, "
    "melyik motor a megfelelő hozzá:\n\n"
    "1. KÖZVETLEN FÁJL (zip, iso, mp4, pdf, bármi)\n"
    "   A fájlt több darabra osztja, és egyszerre több kapcsolaton tölti le "
    "(ezt állítod a Szálak mezővel), így gyorsabb. Ha megszakad, a már "
    "letöltött darabokat megőrzi, és onnan folytatja.\n\n"
    "2. MÉDIAOLDAL (YouTube, Vimeo, SoundCloud és sok ezer más)\n"
    "   A yt-dlp motor intézi; a videó-darabokat szintén több szálon szedi. "
    "A „Csak hang” beállítással csak a hangsávot töltöd le, a "
    "„Hangformátum” választóval pedig a formátumát (MP3, M4A, OPUS, FLAC, "
    "WAV, AAC). Az átkódoláshoz ffmpeg kell; ha nincs a gépen, a program "
    "az első ilyen letöltéskor egyszer automatikusan letölti.\n\n"
    "3. TORRENT (magnet-link vagy .torrent fájl)\n"
    "   Az aria2 motor kezeli. Letöltés után a „Seed-arány” mezőben megadott "
    "arányig oszt vissza (seedel) másoknak; 0 esetén nem seedel.\n\n"
    "BEJELENTKEZÉS / SÜTIK\n"
    "   Ha egy videó csak bejelentkezve tölthető (korhatáros, tagsági, "
    "régiózárt, vagy „erősítsd meg, hogy nem vagy robot”), a „Sütik” "
    "választóval megadhatod, melyik böngészőből vegye a program a "
    "bejelentkezésed sütijeit – abba a böngészőbe légy belépve. "
    "Alternatívaként egy cookies.txt fájl is betölthető. A program nem "
    "tárolja a jelszavadat; csak a böngésződ meglévő munkamenetét használja.\n\n"
    "TOVÁBBI KÉPESSÉGEK\n"
    "  • Időzítés: megadott időpontban indítja a letöltést.\n"
    "  • Folytatás: a félbeszakadt letöltéseket újraindításkor felkínálja.\n"
    "  • Podcast/RSS: feliratkozol egy csatornára, az új epizódokat magától "
    "letölti.\n"
    "  • Hangos összefoglaló (Ctrl+J): egy mondatban felolvassa az állapotot.\n"
    "  • Sebességkorlát: az összes letöltésre együttesen érvényes.\n"
    "  • Frissítés: a letöltőmotorok új verzióit felkínálja telepítésre."
)

KEYS_TEXT = (
    "Billentyűparancsok\n\n"
    "  Enter (az URL-mezőben)  – a letöltés indítása\n"
    "  Ctrl+N   – az URL-mező fókuszálása (új letöltés)\n"
    "  Ctrl+T   – torrentfájl megnyitása\n"
    "  Ctrl+O   – URL-lista megnyitása fájlból\n"
    "  Ctrl+R   – feliratkozás podcast/RSS-csatornára\n"
    "  Ctrl+L   – feliratkozások kezelése\n"
    "  Ctrl+D   – a letöltési lista fókuszálása\n"
    "  Ctrl+E   – az eseménynapló fókuszálása\n"
    "  Ctrl+J   – hangos összefoglaló (mennyi van hátra)\n"
    "  Ctrl+U   – frissítések keresése\n"
    "  Delete   – futó letöltés leállítása; befejezett/hibás elem törlése\n"
    "  Shift+Delete – a kijelölt elem eltávolítása a listából\n"
    "  Ctrl+Shift+S – minden letöltés leállítása\n"
    "  Ctrl+M   – a célmappa megnyitása\n"
    "  F1       – ez a súgó\n"
    "  Ctrl+Q   – kilépés\n\n"
    "Minden mező és gomb elérhető a menüből és Tab-bal is, az aláhúzott "
    "betűkkel pedig Alt+betű gyorsbillentyűként."
)

PRIVACY_TEXT = (
    "Adatkezelés és adatvédelem – pontosan mihez fér hozzá a program\n\n"
    "A SuperDL NEM gyűjt és NEM küld semmilyen adatot magáról rólad. "
    "Nincs benne nyomkövetés, nincs fiók, nincs reklám. Minden a te "
    "gépeden marad.\n\n"
    "HÁLÓZAT – a program csak ezekhez kapcsolódik:\n"
    "  • azokhoz a címekhez, amelyeket te adsz meg letöltésre;\n"
    "  • azokhoz az RSS/podcast-csatornákhoz, amelyekre feliratkozol;\n"
    "  • médiaoldal letöltésekor az adott oldalhoz (a yt-dlp révén);\n"
    "  • torrentnél a trackerekhez és a többi felhasználóhoz (peer);\n"
    "  • frissítéskereséskor a github.com és a pypi.org címekhez "
    "(csak verziók lekérdezése és a motorok letöltése).\n\n"
    "FÁJLOK – a program ezeket írja vagy olvassa a gépeden:\n"
    "  • a letöltött fájlok a kiválasztott célmappába kerülnek;\n"
    "  • beállítások: a felhasználói mappádban a .superdl.json fájl;\n"
    "  • letöltési sor, feliratkozások és motorfrissítések: a .superdl mappa;\n"
    "  • a megnyitott .torrent fájlokat beolvassa.\n\n"
    "VÁGÓLAP – a vágólapot CSAK akkor figyeli, ha a „Vágólap figyelése” "
    "beállítást bekapcsolod; egyébként soha nem nézi.\n\n"
    "Semmi mást nem ér el, és semmilyen adatot nem továbbít sehová."
)


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def beep(ok: bool = True) -> None:
    if winsound:
        winsound.MessageBeep(
            winsound.MB_ICONASTERISK if ok else winsound.MB_ICONHAND)


class UrlDropTarget(wx.TextDropTarget):
    """Böngészőből idehúzott hivatkozások fogadása."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def OnDropText(self, x, y, data):
        for line in data.strip().splitlines():
            if line.strip().lower().startswith(
                    ("http://", "https://", "magnet:")):
                self.callback(line.strip())
        return True


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="SuperDL – akadálymentes többszálú letöltő",
                         size=(980, 640))
        self.mgr: DownloadManager | None = None
        self.fm = FeedManager()
        self.speaker = Speaker()
        self._known_rows: dict[int, int] = {}   # job.id -> listasor
        self._last_values: dict[int, tuple] = {}
        self._reported: dict[int, str] = {}
        self._conflict_asked: set = set()        # mely job-okra kérdeztünk rá
        self._last_clip = ""

        self._load_settings()
        self._build_menu()
        self._build_ui()
        self._apply_settings()

        self.SetDropTarget(UrlDropTarget(self._on_drop_url))
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self.timer)
        self.timer.Start(700)
        # a feliratkozások időnkénti, automatikus ellenőrzése (15 perc)
        self.feed_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._check_feeds(quiet=True),
                  self.feed_timer)
        self.feed_timer.Start(15 * 60 * 1000)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        # induláskor: félbeszakadt letöltések felajánlása + feed-ellenőrzés
        wx.CallLater(400, self._offer_resume)
        if self.fm.subs:
            wx.CallLater(3000, lambda: self._check_feeds(quiet=True))
        # naponta egyszer, csendben frissítést keresünk (a háttérben)
        wx.CallLater(6000, self._auto_update_check)

        self.url_entry.SetFocus()

    # ---- felépítés ----------------------------------------------------

    def _build_menu(self):
        mb = wx.MenuBar()

        m_file = wx.Menu()
        mi_url = m_file.Append(wx.ID_ANY, "Ú&j letöltés (URL-mező)\tCtrl+N",
                               "Az URL-beviteli mező fókuszálása")
        mi_torrent = m_file.Append(wx.ID_ANY, "&Torrentfájl megnyitása...\tCtrl+T",
                                   ".torrent fájl megnyitása letöltéshez")
        mi_list = m_file.Append(wx.ID_ANY, "URL-lista meg&nyitása...\tCtrl+O",
                                "Szövegfájl megnyitása, soronként egy URL-lel")
        mi_open = m_file.Append(wx.ID_ANY, "Cél&mappa megnyitása\tCtrl+M",
                                "A letöltési mappa megnyitása a Fájlkezelőben")
        m_file.AppendSeparator()
        mi_quit = m_file.Append(wx.ID_EXIT, "&Kilépés\tCtrl+Q")
        mb.Append(m_file, "&Fájl")

        m_dl = wx.Menu()
        mi_focus = m_dl.Append(wx.ID_ANY, "Letöltési &lista\tCtrl+D",
                               "A letöltési lista fókuszálása")
        mi_log = m_dl.Append(wx.ID_ANY, "&Eseménynapló\tCtrl+E",
                             "Az eseménynapló fókuszálása")
        mi_stop = m_dl.Append(
            wx.ID_ANY, "Kijelölt leállí&tása / törlése\tDel",
            "Futó letöltés leállítása; befejezett vagy hibás elem törlése")
        mi_remove = m_dl.Append(
            wx.ID_ANY, "Eltávolítás a &listából\tShift+Del",
            "A kijelölt elem eltávolítása a listából (és a mentett sorból)")
        mi_stopall = m_dl.Append(wx.ID_ANY, "Összes leállítá&sa\tCtrl+Shift+S")
        m_dl.AppendSeparator()
        mi_speak = m_dl.Append(wx.ID_ANY, "Összefoglaló &felolvasása\tCtrl+J",
                               "Az aktuális állapot felolvasása egy mondatban")
        self.mi_tts = m_dl.AppendCheckItem(
            wx.ID_ANY, "Be&fejezés felolvasása",
            "Minden elkészült letöltést hangosan is bemond")
        mb.Append(m_dl, "&Letöltések")

        m_sub = wx.Menu()
        mi_subnew = m_sub.Append(wx.ID_ANY, "Új &feliratkozás...\tCtrl+R",
                                 "Feliratkozás podcast vagy RSS-csatornára")
        mi_submng = m_sub.Append(wx.ID_ANY, "Feliratkozások &kezelése...\tCtrl+L",
                                 "Feliratkozások listája és törlése")
        mi_subchk = m_sub.Append(wx.ID_ANY, "Új epizódok le&töltése most",
                                 "Minden feliratkozás ellenőrzése azonnal")
        mb.Append(m_sub, "F&eliratkozások")

        m_help = wx.Menu()
        mi_keys = m_help.Append(wx.ID_ANY, "&Billentyűparancsok\tF1")
        mi_how = m_help.Append(wx.ID_ANY, "&Hogyan működik")
        mi_priv = m_help.Append(wx.ID_ANY, "&Adatkezelés és adatvédelem")
        m_help.AppendSeparator()
        mi_upd = m_help.Append(wx.ID_ANY, "&Frissítések keresése\tCtrl+U",
                               "A letöltőmotorok új verzióinak keresése")
        m_help.AppendSeparator()
        mi_about = m_help.Append(wx.ID_ABOUT, "&Névjegy")
        mb.Append(m_help, "&Súgó")

        self.SetMenuBar(mb)
        self.Bind(wx.EVT_MENU, lambda e: self.url_entry.SetFocus(), mi_url)
        self.Bind(wx.EVT_MENU, self._on_open_torrent, mi_torrent)
        self.Bind(wx.EVT_MENU, self._on_open_list, mi_list)
        self.Bind(wx.EVT_MENU, self._on_open_folder, mi_open)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), mi_quit)
        self.Bind(wx.EVT_MENU, lambda e: self.dl_list.SetFocus(), mi_focus)
        self.Bind(wx.EVT_MENU, lambda e: self.log.SetFocus(), mi_log)
        self.Bind(wx.EVT_MENU, self._on_stop_selected, mi_stop)
        self.Bind(wx.EVT_MENU, self._on_remove_selected, mi_remove)
        self.Bind(wx.EVT_MENU, self._on_stop_all, mi_stopall)
        self.Bind(wx.EVT_MENU, self._on_speak_summary, mi_speak)
        self.Bind(wx.EVT_MENU, self._on_subscribe, mi_subnew)
        self.Bind(wx.EVT_MENU, self._on_manage_subs, mi_submng)
        self.Bind(wx.EVT_MENU, lambda e: self._check_feeds(quiet=False),
                  mi_subchk)
        self.Bind(wx.EVT_MENU, lambda e: self._show_info(1), mi_keys)
        self.Bind(wx.EVT_MENU, lambda e: self._show_info(2), mi_how)
        self.Bind(wx.EVT_MENU, lambda e: self._show_info(3), mi_priv)
        self.Bind(wx.EVT_MENU, self._on_check_updates, mi_upd)
        self.Bind(wx.EVT_MENU, lambda e: self._show_info(0), mi_about)

    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # URL-sor
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        lbl_url = wx.StaticText(panel, label="&Letöltendő URL:")
        self.url_entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.url_entry.SetName("Letöltendő URL")
        self.url_entry.SetHint("Illeszd be a hivatkozást, majd nyomj Entert")
        lbl_sched = wx.StaticText(panel, label="&Időzítés:")
        self.sched_entry = wx.TextCtrl(panel, size=(80, -1))
        self.sched_entry.SetName("Időzített indítás, például 03:00 vagy +2h; "
                                 "üresen hagyva azonnal indul")
        self.sched_entry.SetHint("pl. 03:00")
        btn_dl = wx.Button(panel, label="Le&töltés")
        btn_dl.SetDefault()
        row1.Add(lbl_url, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row1.Add(self.url_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row1.Add(lbl_sched, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        row1.Add(self.sched_entry, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row1.Add(btn_dl, 0)
        vbox.Add(row1, 0, wx.EXPAND | wx.ALL, 8)

        # beállítások
        box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Beállítások")
        sb = box.GetStaticBox()

        lbl_dir = wx.StaticText(sb, label="&Célmappa:")
        self.dir_entry = wx.TextCtrl(sb, size=(260, -1))
        self.dir_entry.SetName("Célmappa")
        btn_dir = wx.Button(sb, label="Tall&ózás...")

        lbl_conn = wx.StaticText(sb, label="S&zálak:")
        self.conn_spin = wx.SpinCtrl(sb, min=1, max=32, initial=8,
                                     size=(60, -1))
        self.conn_spin.SetName("Szálak száma letöltésenként")

        lbl_par = wx.StaticText(sb, label="&Párhuzamos letöltés:")
        self.par_spin = wx.SpinCtrl(sb, min=1, max=10, initial=3,
                                    size=(60, -1))
        self.par_spin.SetName("Egyszerre futó letöltések száma")

        lbl_lim = wx.StaticText(sb, label="Sebesség&korlát:")
        self.limit_entry = wx.TextCtrl(sb, size=(70, -1))
        self.limit_entry.SetName("Sebességkorlát, például 2M vagy 500K, "
                                 "üresen hagyva nincs korlát")
        self.limit_entry.SetHint("pl. 2M")

        lbl_seed = wx.StaticText(sb, label="Seed-&arány:")
        self.seed_entry = wx.TextCtrl(sb, size=(50, -1), value="1.0")
        self.seed_entry.SetName("Torrent megosztási arány, eddig seedel a "
                                "letöltés után; nulla esetén nem seedel")

        self.audio_chk = wx.CheckBox(sb, label="Csak &hang")
        self.audio_chk.SetName("Médiaoldalról csak a hangsáv letöltése")

        lbl_fmt = wx.StaticText(sb, label="Hang&formátum:")
        self.fmt_choice = wx.Choice(
            sb, choices=["MP3", "M4A", "OPUS", "FLAC", "WAV", "AAC"])
        self.fmt_choice.SetSelection(0)
        self.fmt_choice.SetName("Hangformátum a Csak hang módhoz; MP3-hoz és "
                                "a többihez a program szükség esetén letölti "
                                "az átalakítót")

        lbl_cookies = wx.StaticText(sb, label="&Sütik:")
        self.cookies_choice = wx.Choice(sb, choices=[
            "Nincs", "Chrome", "Firefox", "Edge", "Brave", "Opera",
            "Vivaldi", "Chromium", "cookies.txt fájl…"])
        self.cookies_choice.SetSelection(0)
        self.cookies_choice.SetName(
            "Bejelentkezés sütikkel a fiókod mögötti (korhatáros, tagsági) "
            "videókhoz: válassz böngészőt, amelybe be vagy jelentkezve, vagy "
            "egy cookies.txt fájlt")
        self.cookies_choice.Bind(wx.EVT_CHOICE, self._on_cookies_choice)
        self._cookies_file = None

        self.clip_chk = wx.CheckBox(sb, label="&Vágólap figyelése")
        self.clip_chk.SetName("Vágólapra másolt hivatkozások automatikus "
                              "letöltése")
        self.notify_chk = wx.CheckBox(sb, label="É&rtesítések")
        self.notify_chk.SetValue(True)
        self.notify_chk.SetName("Rendszerértesítés a letöltések elkészültéről")

        # tördelődő elrendezés: szűk ablaknál több sorba rendeződik
        wrap = wx.WrapSizer(wx.HORIZONTAL)
        for w in (lbl_dir, self.dir_entry, btn_dir, lbl_conn, self.conn_spin,
                  lbl_par, self.par_spin, lbl_lim, self.limit_entry,
                  lbl_seed, self.seed_entry, self.audio_chk, lbl_fmt,
                  self.fmt_choice, lbl_cookies, self.cookies_choice,
                  self.clip_chk, self.notify_chk):
            wrap.Add(w, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.BOTTOM, 6)
        box.Add(wrap, 1, wx.EXPAND | wx.ALL, 4)
        vbox.Add(box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # letöltési lista
        lbl_list = wx.StaticText(panel, label="Letöltések listája:")
        self.dl_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.dl_list.SetName("Letöltések listája")
        for i, (title, width) in enumerate(
                (("Fájl", 300), ("Állapot", 100), ("Haladás", 80),
                 ("Sebesség", 95), ("Feltöltés", 110), ("Méret", 85),
                 ("Szálak", 55), ("Típus", 65))):
            self.dl_list.InsertColumn(i, title, width=width)
        self.dl_list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        vbox.Add(lbl_list, 0, wx.LEFT | wx.TOP, 8)
        vbox.Add(self.dl_list, 3, wx.EXPAND | wx.ALL, 8)

        # eseménynapló - képernyőolvasóval kényelmesen visszaolvasható
        lbl_log = wx.StaticText(panel, label="Eseménynapló:")
        self.log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.log.SetName("Eseménynapló, csak olvasható")
        vbox.Add(lbl_log, 0, wx.LEFT, 8)
        vbox.Add(self.log, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        panel.SetSizer(vbox)

        self.CreateStatusBar()
        self.SetStatusText("Üdvözöl a SuperDL! Illessz be egy URL-t, majd "
                           "nyomj Entert. Súgó: F1.")

        btn_dl.Bind(wx.EVT_BUTTON, self._on_add)
        self.url_entry.Bind(wx.EVT_TEXT_ENTER, self._on_add)
        btn_dir.Bind(wx.EVT_BUTTON, self._on_pick_dir)

    # ---- beállítások mentése/betöltése --------------------------------

    def _load_settings(self):
        self.settings = {
            "out_dir": str(Path.home() / "Downloads"),
            "connections": 8, "parallel": 3, "limit": "",
            "clipboard": False, "notify": True, "seed_ratio": "1.0",
            "tts": False, "update_last_check": "", "audio_format": "MP3",
            "cookies": "Nincs", "cookies_file": "",
        }
        try:
            self.settings.update(json.loads(SETTINGS_FILE.read_text()))
        except (OSError, json.JSONDecodeError):
            pass

    def _apply_settings(self):
        s = self.settings
        self.dir_entry.SetValue(s["out_dir"])
        self.conn_spin.SetValue(s["connections"])
        self.par_spin.SetValue(s["parallel"])
        self.limit_entry.SetValue(s["limit"])
        self.clip_chk.SetValue(s["clipboard"])
        self.notify_chk.SetValue(s["notify"])
        self.seed_entry.SetValue(str(s["seed_ratio"]))
        self.mi_tts.Enable(self.speaker.available)
        self.mi_tts.Check(bool(s.get("tts")) and self.speaker.available)
        if self.fmt_choice.SetStringSelection(str(s.get("audio_format", "MP3"))) \
                is False:
            self.fmt_choice.SetSelection(0)
        self._cookies_file = s.get("cookies_file") or None
        if self.cookies_choice.SetStringSelection(
                str(s.get("cookies", "Nincs"))) is False:
            self.cookies_choice.SetSelection(0)

    def _save_settings(self):
        self.settings = {
            "out_dir": self.dir_entry.GetValue(),
            "connections": self.conn_spin.GetValue(),
            "parallel": self.par_spin.GetValue(),
            "limit": self.limit_entry.GetValue(),
            "clipboard": self.clip_chk.GetValue(),
            "notify": self.notify_chk.GetValue(),
            "seed_ratio": self.seed_entry.GetValue(),
            "tts": self.mi_tts.IsChecked(),
            "update_last_check": self.settings.get("update_last_check", ""),
            "audio_format": self.fmt_choice.GetStringSelection() or "MP3",
            "cookies": self.cookies_choice.GetStringSelection() or "Nincs",
            "cookies_file": self._cookies_file or "",
        }
        try:
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2))
        except OSError:
            pass

    # ---- események ----------------------------------------------------

    def _announce(self, text: str, ok: bool = True, toast: bool = False):
        """Állapotsor + napló + hang; fontos eseménynél rendszerértesítés,
        amelyet a képernyőolvasók maguktól felolvasnak."""
        self.SetStatusText(text)
        stamp = time.strftime("%H:%M:%S")
        self.log.AppendText(f"[{stamp}] {text}\n")
        beep(ok)
        if toast and self.notify_chk.GetValue():
            note = wx.adv.NotificationMessage("SuperDL", text)
            note.Show(timeout=8)

    def _seed_ratio(self) -> float:
        try:
            return max(0.0, float(self.seed_entry.GetValue().replace(",", ".")))
        except ValueError:
            return 1.0

    def _cookies_config(self) -> tuple[str | None, str | None]:
        """(böngésző, cookies.txt-fájl) a sütik-választó alapján."""
        sel = self.cookies_choice.GetStringSelection()
        if sel == "cookies.txt fájl…":
            return None, self._cookies_file
        if sel and sel != "Nincs":
            return sel.lower(), None
        return None, None

    def _on_cookies_choice(self, event):
        if self.cookies_choice.GetStringSelection() != "cookies.txt fájl…":
            return
        dlg = wx.FileDialog(
            self, "cookies.txt fájl kiválasztása",
            wildcard="cookies.txt (*.txt)|*.txt|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self._cookies_file = dlg.GetPath()
            self._announce(f"Sütifájl beállítva: {self._cookies_file}")
        else:
            self.cookies_choice.SetSelection(0)   # vissza a „Nincs"-re
        dlg.Destroy()

    def _ensure_mgr(self) -> DownloadManager:
        fmt = (self.fmt_choice.GetStringSelection() or "mp3").lower()
        ck_browser, ck_file = self._cookies_config()
        if self.mgr is None:
            self.mgr = DownloadManager(
                self.dir_entry.GetValue(),
                parallel=self.par_spin.GetValue(),
                connections=self.conn_spin.GetValue(),
                audio_only=self.audio_chk.GetValue(),
                limit_bps=parse_limit(self.limit_entry.GetValue() or "0"),
                seed_ratio=self._seed_ratio(), audio_format=fmt,
                cookies_browser=ck_browser, cookies_file=ck_file)
        else:
            self.mgr.out_dir = self.dir_entry.GetValue()
            self.mgr.connections = self.conn_spin.GetValue()
            self.mgr.audio_only = self.audio_chk.GetValue()
            self.mgr.limiter.bps = parse_limit(
                self.limit_entry.GetValue() or "0")
            self.mgr.seed_ratio = self._seed_ratio()
            self.mgr.audio_format = fmt
            self.mgr.cookies_browser = ck_browser
            self.mgr.cookies_file = ck_file
        return self.mgr

    def _on_add(self, event=None, url: str | None = None):
        url = (url or self.url_entry.GetValue()).strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://", "magnet:")) \
                and not is_torrent_url(url):
            wx.MessageBox("Érvényes URL-t adj meg: http(s) hivatkozást, "
                          "magnet-linket vagy .torrent fájl útvonalát.",
                          "SuperDL", wx.OK | wx.ICON_WARNING, self)
            return
        if not url_is_new(self.mgr, url):
            self._announce("Ez az URL már a listában van.", ok=False)
            return
        self.url_entry.Clear()
        self.SetStatusText("URL vizsgálata...")

        def detect():
            if is_torrent_url(url):
                kind = "torrent"
            else:
                kind = "media" if is_media_url(url) else "file"
            wx.CallAfter(self._add_job, url, kind)

        threading.Thread(target=detect, daemon=True).start()

    def _add_job(self, url: str, kind: str):
        mgr = self._ensure_mgr()
        start_at = parse_when(self.sched_entry.GetValue())
        job = mgr.add(url, kind=kind, start_at=start_at)
        self._row_for(job)
        kind_hu = {"media": "médialetöltés", "torrent": "torrent"}.get(
            kind, "fájlletöltés")
        if start_at:
            when = time.strftime("%H:%M", time.localtime(start_at))
            self._announce(f"Időzítve {when}-ra ({kind_hu}): {url}")
        else:
            self._announce(f"Hozzáadva a sorhoz ({kind_hu}): {url}")

    def _row_for(self, job) -> int:
        """Megkeresi vagy létrehozza a job listasorát (bármely forrásból)."""
        row = self._known_rows.get(job.id)
        if row is None:
            row = self.dl_list.InsertItem(self.dl_list.GetItemCount(),
                                          job.progress.filename or job.url)
            kind_label = {"media": "média", "torrent": "torrent"}.get(
                job.kind, "fájl")
            self.dl_list.SetItem(row, 1, job.progress.status)
            self.dl_list.SetItem(row, 7, kind_label)
            self._known_rows[job.id] = row
        return row

    def _on_drop_url(self, url: str):
        self._on_add(url=url)

    def _on_pick_dir(self, event):
        dlg = wx.DirDialog(self, "Célmappa kiválasztása",
                           self.dir_entry.GetValue())
        if dlg.ShowModal() == wx.ID_OK:
            self.dir_entry.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_open_torrent(self, event):
        dlg = wx.FileDialog(self, "Torrentfájl megnyitása",
                            wildcard="Torrentfájlok (*.torrent)|*.torrent",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self._on_add(url=dlg.GetPath())
        dlg.Destroy()

    def _on_open_list(self, event):
        dlg = wx.FileDialog(self, "URL-lista megnyitása",
                            wildcard="Szövegfájlok (*.txt)|*.txt|Minden fájl|*.*",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            try:
                for line in Path(dlg.GetPath()).read_text(
                        encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._on_add(url=line)
            except OSError as e:
                wx.MessageBox(f"Nem sikerült megnyitni: {e}", "SuperDL",
                              wx.OK | wx.ICON_ERROR, self)
        dlg.Destroy()

    def _on_open_folder(self, event):
        path = Path(self.dir_entry.GetValue())
        path.mkdir(parents=True, exist_ok=True)
        wx.LaunchDefaultApplication(str(path))

    def _selected_job(self):
        row = self.dl_list.GetFirstSelected()
        if row < 0 or not self.mgr:
            return None
        for jid, r in self._known_rows.items():
            if r == row:
                for j in self.mgr.jobs:
                    if j.id == jid:
                        return j
        return None

    def _on_stop_selected(self, event=None):
        job = self._selected_job()
        if not job:
            return
        if job.progress.status in ("letöltés", "seedelés", "várakozik",
                                   "ütemezve"):
            self.mgr.stop(job)
            self._announce(
                f"Leállítva: {job.progress.filename or job.url}", ok=False)
        else:
            # befejezett, hibás vagy már leállított elem: eltávolítjuk
            self._remove_job(job)

    def _on_remove_selected(self, event=None):
        job = self._selected_job()
        if job:
            self._remove_job(job)

    def _remove_job(self, job):
        name = job.progress.filename or job.url
        if self.mgr:
            self.mgr.remove(job)          # leállítja, törli a sorból + mentésből
        self._remove_row(job)
        self._conflict_asked.discard(job.id)
        self._reported.pop(job.id, None)
        self._announce(f"Eltávolítva a listából: {name}")

    def _on_stop_all(self, event=None):
        if self.mgr:
            self.mgr.stop_all()
            self._announce("Minden letöltés leállítva.", ok=False)

    def _on_list_key(self, event):
        if event.GetKeyCode() == wx.WXK_DELETE:
            if event.ShiftDown():
                self._on_remove_selected()
            else:
                self._on_stop_selected()
        else:
            event.Skip()

    def _show_info(self, page: int = 0):
        InfoDialog(self, page).ShowModal()

    def _on_check_updates(self, event=None):
        UpdateDialog(self).ShowModal()

    def _auto_update_check(self):
        import datetime
        today = datetime.date.today().isoformat()
        if self.settings.get("update_last_check") == today:
            return

        def work():
            names = []
            try:
                if selfupdate.check().get("update"):
                    names.append("SuperDL")
            except Exception:
                pass
            try:
                for c in updater.check_updates():
                    if c["update"]:
                        names.append(c["name"].split(" (")[0])
            except Exception:
                pass
            wx.CallAfter(self._after_auto_check, names, today)

        threading.Thread(target=work, daemon=True).start()

    def _after_auto_check(self, names, today):
        self.settings["update_last_check"] = today
        self._save_settings()
        if not names:
            return
        joined = ", ".join(names)
        self._announce(f"Frissítés érhető el: {joined}.", toast=True)
        if wx.MessageBox(
                f"Új verzió érhető el ehhez: {joined}.\n\n"
                "Megnyitod a frissítéskezelőt?",
                "SuperDL – frissítés", wx.YES_NO | wx.ICON_INFORMATION,
                self) == wx.YES:
            self._on_check_updates()

    # ---- folytatás induláskor -----------------------------------------

    def _offer_resume(self):
        from superdl import store
        saved = store.load_queue()
        pending = [r for r in saved if r.get("status") != "kész"]
        if not pending:
            return
        if wx.MessageBox(
                f"{len(pending)} félbeszakadt vagy időzített letöltés található "
                f"a legutóbbi munkamenetből.\n\nFolytatod őket?",
                "SuperDL – folytatás", wx.YES_NO | wx.ICON_QUESTION,
                self) != wx.YES:
            store.save_queue([])      # elvetjük, hogy ne ajánlja fel újra
            self._announce("A korábbi befejezetlen letöltések elvetve.")
            return
        mgr = self._ensure_mgr()
        restored = mgr.restore()
        for job in restored:
            self._row_for(job)
        self._announce(f"{len(restored)} korábbi letöltés folytatása.")

    # ---- feliratkozások -----------------------------------------------

    def _on_subscribe(self, event=None):
        dlg = wx.TextEntryDialog(
            self, "A podcast vagy RSS-csatorna címe (URL):",
            "Új feliratkozás")
        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.GetValue().strip()
            if url:
                self._do_subscribe(url)
        dlg.Destroy()

    def _do_subscribe(self, url: str):
        out_dir = self.dir_entry.GetValue()
        audio = self.audio_chk.GetValue()
        self._announce(f"Feliratkozás vizsgálata: {url}")

        def work():
            try:
                sub = self.fm.subscribe(url, out_dir=out_dir, audio_only=audio)
                wx.CallAfter(
                    self._announce,
                    f"Feliratkozva: {sub.title} ({len(sub.seen)} meglévő "
                    f"epizód kihagyva, csak az újakat tölti).")
            except Exception as e:
                wx.CallAfter(self._announce,
                             f"Nem sikerült a feliratkozás: {e}", False)

        threading.Thread(target=work, daemon=True).start()

    def _on_manage_subs(self, event=None):
        dlg = SubsDialog(self, self.fm)
        dlg.ShowModal()
        dlg.Destroy()

    def _check_feeds(self, quiet: bool = True):
        if not self.fm.subs:
            if not quiet:
                self._announce("Nincs feliratkozás. Adj hozzá egyet a "
                               "Feliratkozások menüből (Ctrl+R).")
            return
        if not quiet:
            self._announce("Feliratkozások ellenőrzése...")

        def work():
            found = self.fm.check_all()
            wx.CallAfter(self._enqueue_episodes, found, quiet)

        threading.Thread(target=work, daemon=True).start()

    def _enqueue_episodes(self, found, quiet):
        if not found:
            if not quiet:
                self._announce("Nincs új epizód a feliratkozásokban.")
            return
        mgr = self._ensure_mgr()
        for sub, ep in found:
            job = mgr.add(ep.url, out_dir=sub.out_dir or self.dir_entry.GetValue(),
                          audio_only=sub.audio_only)
            job.progress.filename = ep.title
            self._row_for(job)
            self.fm.mark_seen(sub, ep)
        self._announce(f"{len(found)} új epizód letöltése elindult.",
                       toast=True)

    # ---- torrent: a fájl már létezik ----------------------------------

    def _ask_conflict(self, job):
        name = job.progress.filename or job.url
        choices = ["Kihagyom – nem töltöm le újra",
                   "Felülírom – újra letöltöm az elejéről",
                   "Ellenőrzöm és megosztom – a meglévő fájlt seedelem"]
        dlg = wx.SingleChoiceDialog(
            self, f"A torrent cél fájlja már létezik a mappában:\n\n{name}\n\n"
            "Mit tegyek?", "A fájl már létezik", choices)
        dlg.SetSelection(2)
        if dlg.ShowModal() == wx.ID_OK:
            i = dlg.GetSelection()
            if i == 0:
                self.mgr.remove(job)
                self._remove_row(job)
                self._announce("A torrent kihagyva – a meglévő fájl megmarad.")
            elif i == 1:
                self.mgr.resolve_conflict(job, "overwrite")
                self._announce("Felülírás: a torrent letöltése elölről indul.")
            else:
                self.mgr.resolve_conflict(job, "verify")
                self._announce("Ellenőrzés és megosztás: a meglévő fájlt "
                               "ellenőrzöm, majd seedelem.")
        dlg.Destroy()

    def _remove_row(self, job):
        row = self._known_rows.pop(job.id, None)
        if row is None:
            return
        self.dl_list.DeleteItem(row)
        self._last_values.pop(job.id, None)
        for jid, r in list(self._known_rows.items()):
            if r > row:
                self._known_rows[jid] = r - 1

    # ---- hangos összefoglaló ------------------------------------------

    def _on_speak_summary(self, event=None):
        text = build_summary(self.mgr.jobs if self.mgr else [])
        # a képernyőolvasó az értesítésből/állapotsorból olvassa fel,
        # a beszédmotor pedig hangosan is kimondja (ha elérhető)
        self._announce(text, toast=True)
        if self.speaker.available:
            self.speaker.speak(text)
        elif not self.notify_chk.GetValue():
            self.SetStatusText(text)

    # ---- időzített frissítés ------------------------------------------

    def _on_tick(self, event):
        if self.clip_chk.GetValue():
            self._check_clipboard()
        if not self.mgr:
            return
        active = 0
        for j in self.mgr.jobs:
            p = j.progress
            row = self._row_for(j)      # visszatöltött/podcast elemekhez is
            if p.status in ("letöltés", "seedelés"):
                active += 1
            halad = f"{p.percent:.0f}%" if p.total else human(p.downloaded)
            if p.status == "seedelés" or (j.kind == "torrent" and p.uploaded):
                feltoltes = f"{human(p.up_speed)}/s ({p.ratio:.2f})"
            else:
                feltoltes = ""
            values = (p.filename or j.url, p.status, halad,
                      f"{human(p.speed)}/s"
                      if p.status in ("letöltés", "seedelés") else "",
                      feltoltes,
                      human(p.total) if p.total else "",
                      str(p.connections))
            if self._last_values.get(j.id) != values:
                self._last_values[j.id] = values
                for col, val in enumerate(values):
                    self.dl_list.SetItem(row, col, val)
            if p.status in ("kész", "hiba", "seedelés") and \
                    self._reported.get(j.id) != p.status:
                self._reported[j.id] = p.status
                if p.status == "kész":
                    msg = f"Elkészült: {p.filename or j.url}"
                    self._announce(msg, toast=True)
                elif p.status == "seedelés":
                    msg = f"Letöltve, seedelés folyamatban: {p.filename or j.url}"
                    self._announce(msg, toast=True)
                else:
                    msg = f"Hiba: {p.filename or j.url} – {p.error}"
                    self._announce(msg, ok=False, toast=True)
                if self.mi_tts.IsChecked() and self.speaker.available:
                    self.speaker.speak(msg)
            # torrent: a cél fájl már létezik – felkínáljuk a választást
            if p.conflict and j.id not in self._conflict_asked:
                self._conflict_asked.add(j.id)
                wx.CallAfter(self._ask_conflict, j)
        title = "SuperDL – akadálymentes többszálú letöltő"
        if active:
            title = f"SuperDL – {active} letöltés fut"
        if self.GetTitle() != title:
            self.SetTitle(title)

    def _check_clipboard(self):
        text = ""
        if wx.TheClipboard.Open():
            if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_UNICODETEXT)):
                data = wx.TextDataObject()
                wx.TheClipboard.GetData(data)
                text = data.GetText().strip()
            wx.TheClipboard.Close()
        if text == self._last_clip:
            return
        self._last_clip = text
        if text.lower().startswith(("http://", "https://", "magnet:")) \
                and "\n" not in text and url_is_new(self.mgr, text):
            self._on_add(url=text)

    def _on_close(self, event):
        running = self.mgr and any(
            j.progress.status in ("letöltés", "seedelés")
            for j in self.mgr.jobs)
        if running:
            if wx.MessageBox("Letöltés van folyamatban. Biztosan kilépsz?\n\n"
                             "(A félbeszakadt letöltések legközelebb "
                             "folytathatók.)",
                             "SuperDL", wx.YES_NO | wx.ICON_QUESTION,
                             self) != wx.YES:
                event.Veto()
                return
        if self.mgr:
            self.mgr.stop_all()
            self.mgr.close()       # elmenti a sort a folytatáshoz
        from superdl.torrent import shutdown_aria2
        shutdown_aria2()
        self.speaker.stop()
        self._save_settings()
        self.timer.Stop()
        self.feed_timer.Stop()
        event.Skip()


class SubsDialog(wx.Dialog):
    """Feliratkozások listája és törlése - akadálymentes."""

    def __init__(self, parent, fm: FeedManager):
        super().__init__(parent, title="Feliratkozások kezelése",
                         size=(560, 380))
        self.fm = fm
        vbox = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(self, label="&Feliratkozások:")
        self.listbox = wx.ListBox(self, style=wx.LB_SINGLE)
        self.listbox.SetName("Feliratkozások listája")
        vbox.Add(lbl, 0, wx.ALL, 8)
        vbox.Add(self.listbox, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        btn_del = wx.Button(self, label="Kijelölt &törlése")
        btn_close = wx.Button(self, wx.ID_CLOSE, "&Bezárás")
        btns.Add(btn_del, 0, wx.RIGHT, 6)
        btns.Add(btn_close, 0)
        vbox.Add(btns, 0, wx.ALL, 8)
        self.SetSizer(vbox)

        btn_del.Bind(wx.EVT_BUTTON, self._on_delete)
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        self._refresh()
        self.listbox.SetFocus()

    def _refresh(self):
        self.listbox.Clear()
        for s in self.fm.subs:
            mode = "hang" if s.audio_only else "videó"
            self.listbox.Append(f"{s.title}  ({mode}, {len(s.seen)} epizód "
                                f"látva)  –  {s.feed_url}")

    def _on_delete(self, event):
        i = self.listbox.GetSelection()
        if i == wx.NOT_FOUND or i >= len(self.fm.subs):
            return
        sub = self.fm.subs[i]
        if wx.MessageBox(f"Törlöd a feliratkozást?\n\n{sub.title}",
                         "Feliratkozás törlése",
                         wx.YES_NO | wx.ICON_QUESTION, self) == wx.YES:
            self.fm.unsubscribe(sub.feed_url)
            self._refresh()


class InfoDialog(wx.Dialog):
    """Névjegy, billentyűparancsok, működés és adatkezelés - lapozható,
    minden lap felolvasható szövegmező."""

    PAGES = [("Névjegy", ABOUT_TEXT),
             ("Billentyűparancsok", KEYS_TEXT),
             ("Hogyan működik", HOWITWORKS_TEXT),
             ("Adatkezelés", PRIVACY_TEXT)]

    def __init__(self, parent, page: int = 0):
        super().__init__(parent, title="Súgó és névjegy – SuperDL",
                         size=(700, 540),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        vbox = wx.BoxSizer(wx.VERTICAL)
        nb = wx.Notebook(self)
        for title, text in self.PAGES:
            panel = wx.Panel(nb)
            s = wx.BoxSizer(wx.VERTICAL)
            tc = wx.TextCtrl(panel, value=text,
                             style=wx.TE_MULTILINE | wx.TE_READONLY)
            tc.SetName(title)
            s.Add(tc, 1, wx.EXPAND | wx.ALL, 6)
            panel.SetSizer(s)
            nb.AddPage(panel, title)
        nb.SetSelection(max(0, min(page, len(self.PAGES) - 1)))
        vbox.Add(nb, 1, wx.EXPAND | wx.ALL, 6)
        btn = wx.Button(self, wx.ID_CLOSE, "&Bezárás")
        btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        vbox.Add(btn, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        self.SetSizer(vbox)
        self.SetEscapeId(wx.ID_CLOSE)


class UpdateDialog(wx.Dialog):
    """A letöltőmotorok (yt-dlp, aria2) verzióinak ellenőrzése és frissítése."""

    def __init__(self, parent):
        super().__init__(parent, title="Frissítések keresése – SuperDL",
                         size=(640, 440),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.comps: list[dict] = []
        self.app: dict = {}
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.info = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.info.SetName("Frissítések állapota")
        vbox.Add(self.info, 1, wx.EXPAND | wx.ALL, 8)
        self.gauge = wx.Gauge(self, range=100)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_check = wx.Button(self, label="Keresés ú&jra")
        self.btn_inst = wx.Button(self, label="Frissítések &telepítése")
        self.btn_inst.Disable()
        btn_close = wx.Button(self, wx.ID_CLOSE, "&Bezárás")
        btns.Add(self.btn_check, 0, wx.RIGHT, 6)
        btns.Add(self.btn_inst, 0, wx.RIGHT, 6)
        btns.AddStretchSpacer()
        btns.Add(btn_close, 0)
        vbox.Add(btns, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(vbox)

        self.btn_check.Bind(wx.EVT_BUTTON, lambda e: self._check())
        self.btn_inst.Bind(wx.EVT_BUTTON, lambda e: self._install())
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        self._check()

    def _check(self):
        self.btn_check.Disable()
        self.btn_inst.Disable()
        self.info.SetValue("Frissítések keresése folyamatban...")

        def work():
            app = selfupdate.check()
            try:
                comps = updater.check_updates()
            except Exception:
                comps = []
            wx.CallAfter(self._show, app, comps)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, app, comps):
        self.btn_check.Enable()
        self.app = app
        self.comps = comps
        lines, any_upd = [], False

        # SuperDL maga
        if app.get("error") == "nincs beállítva a frissítési tárhely":
            lines.append("SuperDL (maga a program)\n   a frissítési tárhely "
                         "nincs beállítva")
        elif app.get("error"):
            lines.append(f"SuperDL (maga a program)\n   jelenlegi: "
                         f"{app['current']}   (nem sikerült: {app['error']})")
        elif app.get("update"):
            any_upd = True
            lines.append(f"SuperDL (maga a program)\n   jelenlegi: "
                         f"{app['current']}   →   új: {app['latest']}"
                         f"   [FRISSÍTHETŐ]")
        else:
            lines.append(f"SuperDL (maga a program)\n   jelenlegi: "
                         f"{app['current']}   (naprakész)")

        # letöltőmotorok
        for c in comps:
            lat = c["latest"] or "ismeretlen"
            if c["update"]:
                any_upd = True
                lines.append(f"{c['name']}\n   jelenlegi: {c['current']}"
                             f"   →   új: {lat}   [FRISSÍTHETŐ]")
            else:
                lines.append(f"{c['name']}\n   jelenlegi: {c['current']}"
                             f"   (naprakész)")

        msg = "\n\n".join(lines)
        if any_upd:
            msg += ("\n\nNyomd meg a „Frissítések telepítése” gombot. "
                    "A frissítés a hivatalos forrásból tölt le.")
            self.btn_inst.Enable()
        else:
            msg += "\n\nMinden naprakész."
        self.info.SetValue(msg)

    def _install(self):
        self.btn_check.Disable()
        self.btn_inst.Disable()
        engines = [c for c in self.comps if c["update"]]
        app_upd = bool(self.app and self.app.get("update"))
        app_assets = self.app.get("assets", {}) if self.app else {}
        self.info.SetValue("Frissítések letöltése és telepítése...")

        def prog(f):
            wx.CallAfter(self.gauge.SetValue, int(f * 100))

        def work():
            results = []
            for c in engines:
                try:
                    fn = (updater.update_ytdlp if c["key"] == "ytdlp"
                          else updater.update_aria2)
                    results.append(f"{c['name']}: frissítve erre: {fn(prog)}")
                except Exception as e:
                    results.append(f"{c['name']}: hiba – {e}")
                wx.CallAfter(self.gauge.SetValue, 0)
            app_done = False
            if app_upd:
                try:
                    selfupdate.apply(app_assets, prog, restart=False)
                    results.append(f"SuperDL: letöltve a(z) {self.app['latest']} "
                                   "verzió.")
                    app_done = True
                except Exception as e:
                    results.append(f"SuperDL: hiba – {e}")
                wx.CallAfter(self.gauge.SetValue, 0)
            wx.CallAfter(self._installed, results, app_done)

        threading.Thread(target=work, daemon=True).start()

    def _installed(self, results, app_done):
        self.gauge.SetValue(0)
        self.btn_check.Enable()
        tail = ("\n\nKész. A motorfrissítések a következő indításkor lépnek "
                "életbe.")
        if app_done:
            tail = ("\n\nKész. A SuperDL új verziójához újra kell indítani a "
                    "programot.")
        self.info.SetValue("\n".join(results) + tail)
        parent = self.GetParent()
        if hasattr(parent, "_announce"):
            parent._announce("Frissítés kész.", toast=True)
        if app_done and wx.MessageBox(
                "A SuperDL új verziója letöltődött.\n\nÚjraindítod most?",
                "SuperDL frissítés", wx.YES_NO | wx.ICON_QUESTION,
                self) == wx.YES:
            import subprocess
            subprocess.Popen([sys.executable], close_fds=True)
            self.EndModal(wx.ID_CLOSE)
            wx.CallAfter(parent.Close)


def url_is_new(mgr, url: str) -> bool:
    if mgr is None:
        return True
    return all(j.url != url for j in mgr.jobs)


def main():
    app = wx.App()
    selfupdate.cleanup_old()      # korábbi önfrissítés maradékának törlése
    # induláskor a vágólap tartalmát nem töltjük le automatikusan
    frame = MainFrame()
    if wx.TheClipboard.Open():
        data = wx.TextDataObject()
        if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_UNICODETEXT)):
            wx.TheClipboard.GetData(data)
            frame._last_clip = data.GetText().strip()
        wx.TheClipboard.Close()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
