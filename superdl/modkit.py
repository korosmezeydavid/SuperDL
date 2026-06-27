"""SuperDL moduláris „plug-and-play" alaprendszer (It.0 alapozás).

Ez a Core-oldali, TISZTA PYTHON infrastruktúra a MODULE_ARCHITECTURE.md szerint:
  • Manifest – egy modul leíró-adatai (manifest.json) + érvényesítés + kompat.
  • CoreContext – a Core↔Modul SZERZŐDÉS (a `core` objektum, amit a modul
    `register(core)`-ja kap): menü, ablak, letöltés, beszéd, AI, tárolás (modul-
    névtérrel), eszközök, beállítás, események, napló.
  • EventBus – laza csatolás a modulok közt (NEM importálnak egymást).
  • RemoteIndex – a távoli „bolt-index" (modules.json) értelmezése.
  • ModuleLoader – felfedezés → érvényesítés → import → register, HIBATŰRŐEN
    (egy rossz modul naplóz és kimarad, a Core fut tovább).

A nehéz, build-környezetes rész (onefile→onedir, Inno Setup, a gui tényleges
szétszedése) KÉSŐBBI iteráció; ez a réteg önmagában is tesztelhető.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import logging
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# A Core↔Modul API szemantikus verziója. A modul `min_core_api`-t deklarál; a
# Core csak a vele kompatibilist (min_core_api <= CORE_API) tölti be.
CORE_API = "1.0"

_log = logging.getLogger("superdl.modkit")


def _api_tuple(v: str) -> tuple[int, ...]:
    nums = tuple(int(x) for x in re.findall(r"\d+", v or ""))
    return nums or (0,)


def modules_root() -> Path:
    """A telepített modulok gyökere a felhasználónál (~/.superdl/modules)."""
    return Path.home() / ".superdl" / "modules"


# ======================================================================
#  Manifest (a modulban lévő manifest.json)
# ======================================================================

class ManifestError(ValueError):
    """Hibás vagy hiányos manifest."""


_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_ENTRY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_REQUIRED = ("id", "name", "version", "entry")


@dataclass
class Manifest:
    id: str
    name: str
    version: str
    entry: str                      # a belépési PYTHON-csomag neve (register/unregister)
    min_core_api: str = "1.0"
    category: str = "Egyéb"
    description: str = ""
    requires_tools: list = field(default_factory=list)     # pl. ["ffmpeg","pandoc"]
    requires_modules: list = field(default_factory=list)
    author: str = ""
    raw: dict = field(default_factory=dict)


def parse_manifest(data: dict) -> Manifest:
    """Egy manifest-szótár érvényesítése és Manifest-té alakítása. Hibás adatnál
    ManifestError-t dob (érthető magyar üzenettel)."""
    if not isinstance(data, dict):
        raise ManifestError("A manifest nem JSON-objektum.")
    missing = [k for k in _REQUIRED if not str(data.get(k, "")).strip()]
    if missing:
        raise ManifestError("Hiányzó mező(k) a manifestben: " + ", ".join(missing))
    mid = str(data["id"]).strip()
    if not _ID_RE.fullmatch(mid):
        raise ManifestError(
            f"Érvénytelen modul-azonosító: {mid!r} (csak kisbetű, szám, - és _).")
    entry = str(data["entry"]).strip()
    if not _ENTRY_RE.fullmatch(entry):
        raise ManifestError(
            f"Érvénytelen belépési csomagnév: {entry!r}.")
    return Manifest(
        id=mid,
        name=str(data["name"]).strip(),
        version=str(data["version"]).strip(),
        entry=entry,
        min_core_api=str(data.get("min_core_api", "1.0")).strip() or "1.0",
        category=str(data.get("category", "Egyéb")).strip() or "Egyéb",
        description=str(data.get("description", "")).strip(),
        requires_tools=list(data.get("requires_tools", []) or []),
        requires_modules=list(data.get("requires_modules", []) or []),
        author=str(data.get("author", "")).strip(),
        raw=dict(data),
    )


def is_compatible(m: Manifest, core_api: str = CORE_API) -> bool:
    """A modul betölthető-e ezzel a Core-ral? (min_core_api <= core_api)"""
    return _api_tuple(m.min_core_api) <= _api_tuple(core_api)


# ======================================================================
#  EventBus – laza csatolás
# ======================================================================

class EventBus:
    """Egyszerű téma-alapú pub/sub. A feliratkozó hibája NEM dönti meg a
    közzétevőt (try/except). A subscribe egy leiratkozó-függvényt ad vissza."""

    def __init__(self):
        self._subs: dict[str, list] = {}

    def subscribe(self, topic: str, callback):
        self._subs.setdefault(topic, []).append(callback)

        def _unsub():
            lst = self._subs.get(topic)
            if lst and callback in lst:
                lst.remove(callback)
        return _unsub

    def publish(self, topic: str, data=None):
        for cb in list(self._subs.get(topic, [])):
            try:
                cb(data)
            except Exception:
                _log.exception("EventBus: a(z) %r feliratkozó hibázott", topic)


# ======================================================================
#  Core-szolgáltatások és a CoreContext (a `core` objektum)
# ======================================================================

@dataclass
class Services:
    """A Core valódi szolgáltatásai, amiket a modulok a CoreContext-en át érnek
    el. Mind duck-typed (a tesztben pótolható), így ez a réteg wx/Core nélkül is
    működik."""
    store: object = None        # .load(key, default) / .save(key, data)
    settings: object = None     # .get(key, default) / .set(key, value)
    voice: object = None        # .speak(text)
    ai: object = None           # .chat / .vision / .transcribe
    tools: object = None        # .ensure(name, progress) -> path
    downloads: object = None    # .add(url, **opts) -> job


class _StoreNS:
    """Modul-névtérrel ellátott tároló: a modul nem tudja felülírni a Core vagy
    más modul kulcsait (a kulcs elé „mod.<id>." kerül)."""

    def __init__(self, store, module_id: str):
        self._s = store
        self._p = f"mod.{module_id}."

    def load(self, name: str, default=None):
        return self._s.load(self._p + name, default)

    def save(self, name: str, data):
        return self._s.save(self._p + name, data)


class CoreContext:
    """A Core↔Modul szerződés egy adott modul felé. A modul `register(core)`-ban
    ezen át épít menüt/ablakot és kér szolgáltatást; az `unregister(core)`-ban
    mindent leszerel (a frissítés/hot-reload miatt)."""

    def __init__(self, module_id: str, services: Services | None = None,
                 host=None, events: EventBus | None = None,
                 log: logging.Logger | None = None, api_version: str = CORE_API):
        self.module_id = module_id
        self.api_version = api_version
        self.events = events or EventBus()
        self.log = log or logging.getLogger(f"superdl.module.{module_id}")
        self._host = host                       # a wx-oldali menü/ablak-adapter
        s = services or Services()
        self.store = _StoreNS(s.store, module_id) if s.store is not None else None
        self.settings = s.settings
        self.voice = s.voice
        self.ai = s.ai
        self.tools = s.tools
        self.downloads = s.downloads

    # --- ablak/menü (a host adapter felé delegálva) ---
    @property
    def main_frame(self):
        return getattr(self._host, "main_frame", None)

    def add_menu(self, title: str):
        return self._host.add_menu(title)

    def add_menu_item(self, menu, label, callback, shortcut=None, help=""):
        return self._host.add_menu_item(menu, label, callback, shortcut, help)

    def remove_menu_item(self, item):
        return self._host.remove_menu_item(item)

    def register_window(self, key, factory):
        return self._host.register_window(key, factory)


# ======================================================================
#  RemoteIndex – a távoli bolt-index (modules.json)
# ======================================================================

@dataclass
class ModuleEntry:
    id: str
    name: str
    category: str
    description: str
    version: str
    min_core_api: str
    url: str
    sha256: str
    size: int

    def compatible(self, core_api: str = CORE_API) -> bool:
        return _api_tuple(self.min_core_api) <= _api_tuple(core_api)


def parse_index(data: dict) -> list[ModuleEntry]:
    """A modules.json értelmezése ModuleEntry-listává. A hibás bejegyzéseket
    kihagyja (az egész index ne dőljön meg egy rossz elemtől)."""
    if not isinstance(data, dict):
        raise ValueError("A modules.json nem JSON-objektum.")
    out: list[ModuleEntry] = []
    for m in data.get("modules", []) or []:
        try:
            latest = m.get("latest", {}) or {}
            entry = ModuleEntry(
                id=str(m["id"]).strip(),
                name=str(m.get("name", m["id"])).strip(),
                category=str(m.get("category", "Egyéb")).strip() or "Egyéb",
                description=str(m.get("description", "")).strip(),
                version=str(latest.get("version", "")).strip(),
                min_core_api=str(latest.get("min_core_api", "1.0")).strip() or "1.0",
                url=str(latest.get("url", "")).strip(),
                sha256=str(latest.get("sha256", "")).strip().lower(),
                size=int(latest.get("size", 0) or 0),
            )
            if entry.id and entry.url:
                out.append(entry)
        except (KeyError, TypeError, ValueError):
            _log.warning("modules.json: hibás bejegyzés kihagyva: %r", m)
    return out


def compatible_entries(entries: list[ModuleEntry],
                       core_api: str = CORE_API) -> list[ModuleEntry]:
    return [e for e in entries if e.compatible(core_api)]


# ======================================================================
#  ModuleLoader – felfedezés, érvényesítés, import, register (hibatűrő)
# ======================================================================

# ======================================================================
#  Biztonságos telepítő-folyamat (SHA-256 + zip-slip/zip-bomba + atomi)
# ======================================================================

class InstallError(Exception):
    """A modul telepítése nem biztonságos vagy sikertelen."""


# kicsomagolt méret-korlát (zip-bomba ellen); egy tiszta-Python modul bőven elfér
_MAX_UNCOMPRESSED = 200 * 1024 * 1024


def _safe_extract_zip(data: bytes, dest: Path) -> None:
    """A modul-ZIP kicsomagolása a `dest`-be – ÚTVONALBEJÁRÁS (zip-slip) és
    ZIP-BOMBA ellen védve. A manifest.json a ZIP GYÖKERÉBEN van (nem hántolunk
    felső mappát, ellentétben a runtime-bináris csomagokkal)."""
    z = zipfile.ZipFile(io.BytesIO(data))
    if sum(max(0, i.file_size) for i in z.infolist()) > _MAX_UNCOMPRESSED:
        raise InstallError("A modulcsomag kicsomagolva túl nagy (zip-bomba védelem).")
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    for info in z.infolist():
        if info.is_dir():
            continue
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(base)):
            raise InstallError("Útvonalbejárás a csomagban (zip-slip) – elutasítva.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as s, open(target, "wb") as d:
            shutil.copyfileobj(s, d)


def install_module_zip(data: bytes, expected_sha256: str | None = None,
                       root=None, core_api: str = CORE_API) -> Manifest:
    """Egy modul-ZIP biztonságos telepítése a modules/<id>/ alá.

    Lépések (MODULE_ARCHITECTURE §7): SHA-256 ellenőrzés → kicsomagolás temp-be
    (zip-slip/bomba védve) → manifest érvényesítés + kompat → ATOMI áthelyezés
    (a régi verzió .bak-ba, hibánál visszagörgetés). Visszaadja a Manifestet.
    Bármi hibánál InstallError, és a meglévő telepítés ÉRINTETLEN marad."""
    if expected_sha256:
        got = hashlib.sha256(data).hexdigest().lower()
        if got != expected_sha256.strip().lower():
            raise InstallError(
                "A modul SHA-256 ellenőrző összege nem egyezik a hivatalossal – "
                "sérült vagy manipulált csomag, a telepítést megszakítottam.")

    root = Path(root) if root is not None else modules_root()
    staging = Path(tempfile.mkdtemp(prefix="superdl_mod_"))
    moved = False
    try:
        _safe_extract_zip(data, staging)
        mfp = staging / "manifest.json"
        if not mfp.is_file():
            raise InstallError("A modulcsomagban nincs manifest.json.")
        try:
            man = parse_manifest(json.loads(mfp.read_text(encoding="utf-8")))
        except (ValueError, OSError) as e:
            raise InstallError(f"Hibás manifest a csomagban: {e}")
        if not is_compatible(man, core_api):
            raise InstallError(
                f"Ehhez a modulhoz újabb SuperDL kell (min_core_api "
                f"{man.min_core_api} > {core_api}).")
        if not (staging / man.entry).is_dir() \
                and not (staging / (man.entry + ".py")).is_file():
            raise InstallError(
                f"A belépési csomag ({man.entry}) hiányzik a csomagból.")

        root.mkdir(parents=True, exist_ok=True)
        target = root / man.id
        backup = root / (man.id + ".bak")
        if target.exists():
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            target.rename(backup)            # régi félretétele a rollbackhez
        try:
            shutil.move(str(staging), str(target))
            moved = True
        except OSError as e:
            if backup.exists() and not target.exists():
                backup.rename(target)        # VISSZAGÖRGETÉS a régire
            raise InstallError(f"A modul áthelyezése sikertelen: {e}")
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        return man
    finally:
        if not moved and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


class LoadedModule:
    def __init__(self, manifest: Manifest, module, core: CoreContext):
        self.manifest = manifest
        self.module = module
        self.core = core


class ModuleLoader:
    """A telepített modulok betöltése. A `make_core(manifest) -> CoreContext`-et
    a Core adja (így a tároló/napló modulonként névterezett). HIBATŰRŐ: egy rossz
    modul naplóz és kimarad, a többi és a Core megy tovább (MODULE_ARCHITECTURE §6)."""

    def __init__(self, make_core, core_api: str = CORE_API,
                 log: logging.Logger | None = None):
        self._make_core = make_core
        self._core_api = core_api
        self._log = log or _log
        self.loaded: dict[str, LoadedModule] = {}
        self.errors: dict[str, str] = {}

    def discover(self, root=None) -> list[Path]:
        """A `root`/<id>/manifest.json mappák felsorolása."""
        root = Path(root) if root is not None else modules_root()
        if not root.is_dir():
            return []
        return [d for d in sorted(root.iterdir())
                if (d / "manifest.json").is_file()]

    def load_dir(self, module_dir) -> LoadedModule | None:
        module_dir = Path(module_dir)
        try:
            data = json.loads((module_dir / "manifest.json")
                              .read_text(encoding="utf-8"))
            man = parse_manifest(data)
        except Exception as e:
            self.errors[module_dir.name] = f"manifest: {e}"
            self._log.warning("Modul kihagyva (%s): %s", module_dir.name, e)
            return None

        if not is_compatible(man, self._core_api):
            self.errors[man.id] = (
                f"újabb SuperDL kell (min_core_api {man.min_core_api} > "
                f"{self._core_api})")
            self._log.warning("Modul kihagyva (%s): %s", man.id, self.errors[man.id])
            return None

        if man.id in self.loaded:
            return self.loaded[man.id]

        try:
            if str(module_dir) not in sys.path:
                sys.path.insert(0, str(module_dir))
            mod = importlib.import_module(man.entry)
            core = self._make_core(man)
            if hasattr(mod, "register"):
                mod.register(core)
            lm = LoadedModule(man, mod, core)
            self.loaded[man.id] = lm
            self.errors.pop(man.id, None)
            self._log.info("Modul betöltve: %s (%s)", man.id, man.version)
            return lm
        except Exception as e:
            self.errors[man.id] = f"betöltés/register: {e}"
            self._log.exception("Modul betöltése sikertelen: %s", man.id)
            return None

    def load_all(self, root=None) -> dict[str, LoadedModule]:
        for d in self.discover(root):
            self.load_dir(d)
        return self.loaded

    def unload(self, module_id: str) -> bool:
        lm = self.loaded.pop(module_id, None)
        if not lm:
            return False
        try:
            if hasattr(lm.module, "unregister"):
                lm.module.unregister(lm.core)
        except Exception:
            self._log.exception("Modul unregister hibája: %s", module_id)
        return True
