"""A moduláris rendszer Core-oldali BEKÖTÉSE a futó SuperDL-be (It.1).

A `modkit.py` a tiszta-Python váz (manifest, CoreContext-szerződés, betöltő,
telepítő). Ez a fájl köti a vázat a VALÓDI alkalmazáshoz:
  • WxHost – a CoreContext menü/ablak-műveleteit a tényleges wx menüsorra és
    egyablakos kezelésre fordítja.
  • Service-adapterek – a CoreContext szolgáltatásai (store, settings, voice,
    ai, tools, downloads) a meglévő alrendszerekre kötve.
  • init_modules(main) – induláskor betölti a telepített modulokat (hibatűrően).

A modulok így a `core`-on át bővítik a futó programot, anélkül hogy egymást
vagy a Core belső szerkezetét ismernék.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from pathlib import Path

import wx

from . import modkit
from . import store

_log = logging.getLogger("superdl.coremod")
_INDEX_UA = {"User-Agent": "SuperDL-modules"}


def default_index_url() -> str:
    """A távoli modul-index (modules.json) helye a fő repóban (raw). A
    self-update repóját használja – egy elállított repo így legalább látható."""
    try:
        from . import selfupdate
        repo = selfupdate.get_repo()
    except Exception:
        repo = "korosmezeydavid/SuperDL"
    return f"https://raw.githubusercontent.com/{repo}/main/modules.json"


def download_bytes(url: str, progress=None, timeout: int = 300) -> bytes:
    """Egy URL tartalmának letöltése a memóriába, folyamatjelzéssel
    (progress(arany 0..1)). A HTTPS a beépített certifi-kontextussal megy."""
    req = urllib.request.Request(url, headers=_INDEX_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length", 0) or 0)
        buf = bytearray()
        while True:
            ch = r.read(262144)
            if not ch:
                break
            buf += ch
            if progress and total:
                progress(len(buf) / total)
    return bytes(buf)


def install_entry(loader, entry, progress=None, root=None):
    """Egy bolt-beli ModuleEntry TRANZAKCIÓS telepítése/frissítése:
    letöltés → SHA-256-os telepítés a régi .bak-ban tartásával → IMPORT+REGISTER
    PRÓBA → siker esetén commit (.bak eldobása), HIBA esetén ROLLBACK a régire
    (és a régi visszatöltése). Így egy hibás új modul SOSEM teszi tönkre a
    meglévő, működő verziót. Visszaadja a Manifestet; hibánál kivételt dob."""
    root = Path(root) if root is not None else modkit.modules_root()
    data = download_bytes(entry.url, progress)
    if entry.id in loader.loaded:
        loader.unload(entry.id)            # a régi leszerelése a fájlcsere előtt
    man = modkit.install_module_zip(data, entry.sha256 or None, root,
                                    keep_backup=True)
    lm = loader.load_dir(root / man.id)    # IMPORT + REGISTER próba
    if lm is None:                         # hibás új modul → VISSZAGÖRGETÉS
        err = loader.errors.get(man.id, "ismeretlen hiba")
        if modkit.rollback_install(man.id, root):
            loader.load_dir(root / man.id)   # a RÉGI, működő verzió visszatöltése
        raise RuntimeError(
            f"Az új modul betöltése sikertelen, visszaálltunk a korábbira: {err}")
    modkit.commit_install(man.id, root)    # siker → a .bak eldobható
    return man


def remove_module(loader, module_id, root=None) -> bool:
    """Egy telepített modul leszerelése + a mappája törlése."""
    import shutil
    root = Path(root) if root is not None else modkit.modules_root()
    loader.unload(module_id)
    d = root / module_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    return not d.exists()


def fetch_index(url: str | None = None, timeout: int = 30):
    """A távoli modules.json letöltése és értelmezése → ModuleEntry-lista. A
    HTTPS a beépített certifi-kontextussal megy (ld. superdl/__init__.py).
    Hálózati/elemzési hibánál üres lista, hogy az offline használat ne dőljön meg."""
    url = url or default_index_url()
    try:
        req = urllib.request.Request(url, headers=_INDEX_UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return modkit.parse_index(data)
    except Exception:
        _log.warning("modules.json letöltése/elemzése sikertelen: %s", url)
        return []


# ---- Service-adapterek (a meglévő alrendszerekre kötve) ----------------

class StoreAdapter:
    """Modul-tároló: kulcsonként egy JSON-fájl a ~/.superdl/modules_data
    mappában. A CoreContext névteresíti a kulcsot (mod.<id>.), így a modulok
    nem ütköznek egymással vagy a Core-ral."""

    def __init__(self):
        self._dir = Path.home() / ".superdl" / "modules_data"

    def _path(self, key: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", key) or "data"
        return self._dir / (safe + ".json")

    def load(self, key, default=None):
        return store.load_json(self._path(key), default)

    def save(self, key, data):
        self._dir.mkdir(parents=True, exist_ok=True)
        store.save_json(self._path(key), data)


class SettingsAdapter:
    def __init__(self, main):
        self._main = main

    def get(self, key, default=None):
        return getattr(self._main, "settings", {}).get(key, default)

    def set(self, key, value):
        if hasattr(self._main, "settings"):
            self._main.settings[key] = value
            if hasattr(self._main, "_save_settings"):
                try:
                    self._main._save_settings()
                except Exception:
                    _log.exception("settings mentés hiba")


class VoiceAdapter:
    def __init__(self, main):
        self._sv = getattr(main, "selfvoice", None)

    def speak(self, text):
        if self._sv:
            try:
                self._sv.speak(text, force=True)
            except Exception:
                _log.exception("voice.speak hiba")


class AiAdapter:
    def chat(self, prompt, **kw):
        from . import aiclient
        return aiclient.chat(prompt, **kw)

    def vision(self, prompt, image_bytes, **kw):
        from . import aiclient
        return aiclient.vision(prompt, image_bytes, **kw)

    def transcribe(self, audio_path, **kw):
        from . import aiclient
        return aiclient.transcribe(audio_path, **kw)


class ToolsAdapter:
    """Download-on-demand binárisok a meglévő ensure-okon át."""

    def ensure(self, name, progress=None):
        name = (name or "").lower()
        try:
            if name in ("ffmpeg", "ffprobe"):
                from . import ffmpeg
                ffmpeg.ensure_ffmpeg(progress)
                return ffmpeg.find_ffmpeg()
            if name == "pandoc":
                from . import extratools
                return extratools.ensure_pandoc(progress)
            if name == "tesseract":
                from . import extratools
                return extratools.ensure_tesseract(progress)
        except Exception:
            _log.exception("tools.ensure(%s) hiba", name)
        return None


class DownloadsAdapter:
    def __init__(self, main):
        self._main = main

    def add(self, url, **opts):
        if hasattr(self._main, "_on_add"):
            return self._main._on_add(url=url)
        return None


# ---- WxHost: a CoreContext menü/ablak-műveletei a valódi wx-re --------

class WxHost:
    """A CoreContext menü- és ablak-műveleteit a tényleges wx menüsorra és
    egyablakos kezelésre fordítja (a meglévő _xxx_win minta szerint)."""

    def __init__(self, frame: wx.Frame):
        self.frame = frame
        self._windows: dict = {}

    @property
    def main_frame(self):
        return self.frame

    # A felső menük kívánt sorrendje (rang szerint). Az ismeretlen címek 5-ös
    # rangot kapnak (a tartalom-menük és az Eszközök közé kerülnek), a Súgó és
    # az AI rangja a legmagasabb, így azok mindig hátul maradnak.
    _TOP_RANK = {
        "Fájl": 0, "Letöltések": 1, "Feliratkozások": 2,
        "Média": 3, "Könyvek": 4, "Eszközök": 6, "AI": 7, "Súgó": 8,
    }

    def _menubar(self):
        mb = self.frame.GetMenuBar()
        if mb is None:
            mb = wx.MenuBar()
            self.frame.SetMenuBar(mb)
        return mb

    def _find_top_menu(self, mb, plain_title):
        for i in range(mb.GetMenuCount()):
            if mb.GetMenuLabelText(i) == plain_title:
                return mb.GetMenu(i)
        return None

    def _top_insert_pos(self, mb, plain_title):
        rank = self._TOP_RANK.get(plain_title, 5)
        for i in range(mb.GetMenuCount()):
            if self._TOP_RANK.get(mb.GetMenuLabelText(i), 5) > rank:
                return i
        return mb.GetMenuCount()

    def add_menu(self, title: str):
        """Felső menüt ad vissza CÍM szerint. Ha már van ilyen című felső menü,
        AZT adja vissza (nem hoz létre duplikátumot) – így több modul is
        ugyanabba a kategória-menübe (pl. Média, Könyvek, Eszközök) tölthet.
        Új menüt a kívánt sorrendi helyre szúr be (a Súgó mindig utolsó)."""
        mb = self._menubar()
        plain = title.replace("&", "")
        existing = self._find_top_menu(mb, plain)
        if existing is not None:
            return existing
        menu = wx.Menu()
        mb.Insert(self._top_insert_pos(mb, plain), menu, title)
        return menu

    def add_submenu(self, top_title: str, sub_title: str):
        """A megadott felső menü (cím szerinti find-or-create) ALÁ fűz egy
        almenüt, és AZT adja vissza – a modul abba teszi az elemeit. Így a
        média/könyv/eszköz modulok egy-egy közös felső menü alatt csoportosulnak."""
        top = self.add_menu(top_title)
        sub = wx.Menu()
        top.AppendSubMenu(sub, sub_title)
        return sub

    def add_menu_item(self, menu, label, callback, shortcut=None, help=""):
        text = f"{label}\t{shortcut}" if shortcut else label
        item = menu.Append(wx.ID_ANY, text, help)
        self.frame.Bind(wx.EVT_MENU, lambda e: callback(), item)
        return item

    def remove_menu_item(self, item):
        try:
            menu = item.GetMenu()
            if menu:
                menu.Remove(item)
        except Exception:
            _log.exception("remove_menu_item hiba")

    def register_window(self, key, factory):
        """Egyablakos megnyitót ad vissza: ha már nyitva van, előtérbe hozza,
        különben a `factory(parent)`-tel létrehozza (záráskor elfelejti)."""
        def _bring_to_front(w):
            # Az ablakot LÁTHATÓVÁ tesszük, kibontjuk (ha ikonizált), előtérbe
            # hozzuk ÉS fókuszt adunk neki – hogy tényleg ELŐJÖJJÖN, ne csak
            # „villanjon" és visszadobjon a főablakra.
            try:
                w.Show()
            except Exception:
                pass
            for meth in ("Iconize", "Raise", "SetFocus"):
                try:
                    fn = getattr(w, meth, None)
                    if fn is None:
                        continue
                    fn(False) if meth == "Iconize" else fn()
                except Exception:
                    pass

        def opener():
            win = self._windows.get(key)
            if win:
                try:
                    _bring_to_front(win)
                    return win
                except Exception:
                    self._windows.pop(key, None)
            try:
                win = factory(self.frame)
            except Exception as exc:
                _log.exception("A(z) %r ablak megnyitása nem sikerült", key)
                try:
                    wx.MessageBox(
                        "Az ablakot sajnos nem sikerült megnyitni.\n\n"
                        "Hiba: %s\n\nPróbáld újraindítani a programot; ha így is "
                        "marad, írd meg ezt a hibaüzenetet." % exc,
                        "Megnyitási hiba", wx.OK | wx.ICON_ERROR)
                except Exception:
                    pass
                return None
            if win is None:
                return None
            self._windows[key] = win
            try:
                win.Bind(wx.EVT_CLOSE, lambda e: (self._windows.pop(key, None),
                                                  e.Skip()))
            except Exception:
                pass
            _bring_to_front(win)         # KRITIKUS: tényleg jöjjön elő és kapjon fókuszt
            return win
        return opener


# ---- a Core-bekötés összeállítása + a betöltő indítása ----------------

def build_services(main) -> modkit.Services:
    return modkit.Services(
        store=StoreAdapter(),
        settings=SettingsAdapter(main),
        voice=VoiceAdapter(main),
        ai=AiAdapter(),
        tools=ToolsAdapter(),
        downloads=DownloadsAdapter(main),
    )


def make_core_factory(main):
    """Visszaad: (make_core, host, bus). A make_core(manifest) egy modul-
    specifikus CoreContextet ad (közös Services + host + közös EventBus)."""
    services = build_services(main)
    host = WxHost(main)
    bus = modkit.EventBus()

    def make_core(manifest):
        return modkit.CoreContext(manifest.id, services=services, host=host,
                                  events=bus)
    return make_core, host, bus


def init_modules(main, root=None):
    """Induláskor: a telepített modulok hibatűrő betöltése. A loadert/hostot a
    `main`-re tesszük (a Modulkezelő és a leszerelés is eléri). A betöltő
    naplózza a kihagyott/hibás modulokat – a Core mindenképp fut tovább."""
    make_core, host, bus = make_core_factory(main)
    loader = modkit.ModuleLoader(make_core)
    try:
        loader.load_all(root)
    except Exception:
        _log.exception("a modulok betöltése közben hiba történt")
    main._module_loader = loader
    main._module_host = host
    main._module_bus = bus
    if loader.errors:
        _log.warning("Betöltési figyelmeztetések: %s", loader.errors)
    return loader
