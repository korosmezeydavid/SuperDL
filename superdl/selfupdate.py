"""A SuperDL saját frissítése a GitHub-kiadásokból.

A program a megadott GitHub-tárhely legújabb kiadását (Release) figyeli.
Ha a kiadás verziója újabb a futónál, letölti a hozzá tartozó exe-t, és
kicseréli magát. Windows alatt a FUTÓ exe nem írható felül és nem mozgatható
megbízhatóan (memóriába mappelve van, az AV is beleszólhat), ezért a cserét
egy LEVÁLASZTOTT kötegfájl (.bat) végzi, MIUTÁN a program kilépett:
  1. az új exe a helyére `SuperDL.exe.new` néven töltődik le,
  2. a program elindít egy swapper-kötegfájlt és KILÉP,
  3. a swapper megvárja a folyamat kilépését, `move /Y`-nal a helyére teszi
     az új exét (zárolás esetén újrapróbálva), naplóz a ~/.superdl/update.log
     fájlba, majd – ha kérted – újraindítja a programot, végül törli magát.

Korábban a csere a futó folyamatból, helyben történt (átnevezés + azonnali
újraindítás), ami sok gépen csendben elbukott (AV-karantén, írásvédett mappa,
verseny a régi folyamattal) – ezért „letöltötte, de a régi verzió maradt".

A tárhely megadása (bármelyik, ebben a sorrendben):
  - SUPERDL_REPO környezeti változó,
  - a ~/.superdl/repo.txt fájl tartalma (egy sor: "felhasznalo/repo"),
  - a lenti DEFAULT_REPO állandó.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import __version__

# A SuperDL hivatalos GitHub-tárhelye – beégetve, hogy az önfrissítés
# repo.txt nélkül is működjön (akkor is, ha valaki csak az exét tölti le).
DEFAULT_REPO = "korosmezeydavid/SuperDL"
UA = {"User-Agent": "SuperDL-selfupdate"}


def _clean_child_env() -> dict:
    """A PyInstaller-bootloader BELSŐ környezeti változóit kiszedi a gyerek-
    folyamat környezetéből.

    A frozen app indításakor a bootloader beállítja a `_PYI_APPLICATION_HOME_DIR`
    (és társai: `_PYI_ARCHIVE_FILE`, `_PYI_PARENT_PROCESS_LEVEL`, `_MEIPASS2`…)
    változókat. Ha az önfrissítő ezek ÖRÖKLÉSÉVEL indítja a telepítőt/swappert,
    azok TOVÁBBADJÁK az ÚJRAINDÍTOTT SuperDL-nek, és annak a bootloadere a régi
    SZÜLŐ értékét/üres értékét látja → „_PYI_APPLICATION_HOME_DIR is not defined".
    Ezért minden olyan gyereknek, ami (közvetve) ÚJ frozen appot indít, TISZTA
    környezetet adunk."""
    env = os.environ.copy()
    for k in list(env):
        if k.startswith("_PYI") or k == "_MEIPASS2":
            env.pop(k, None)
    return env


def _repo_file_candidates() -> list[Path]:
    cands: list[Path] = []
    if getattr(sys, "frozen", False):              # az exe melletti repo.txt
        cands.append(Path(sys.executable).resolve().parent / "repo.txt")
    else:
        cands.append(Path(__file__).resolve().parent.parent / "repo.txt")
    cands.append(Path.home() / ".superdl" / "repo.txt")
    return cands


def get_repo() -> str:
    r = os.environ.get("SUPERDL_REPO")
    if r:
        return r.strip()
    for f in _repo_file_candidates():
        if f.exists():
            try:
                t = f.read_text(encoding="utf-8").strip()
                if t and not t.startswith("#"):
                    return t
            except OSError:
                pass
    return DEFAULT_REPO


def set_repo(repo: str) -> None:
    """A tárhely elmentése a ~/.superdl/repo.txt fájlba (újraépítés nélkül)."""
    d = Path.home() / ".superdl"
    d.mkdir(parents=True, exist_ok=True)
    (d / "repo.txt").write_text(repo.strip(), encoding="utf-8")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _ver(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def current_version() -> str:
    return __version__


def latest_release(repo: str) -> tuple[str, dict, dict]:
    """(tag, {assetnév: url}, {assetnév: sha256-hex}). A GitHub minden assethez
    megadja a `digest` (sha256:…) mezőt – ezt használjuk a letöltés ELLENŐRZÉSÉRE."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    tag = d.get("tag_name", "")
    assets, digests = {}, {}
    for a in d.get("assets", []):
        assets[a["name"]] = a["browser_download_url"]
        dg = (a.get("digest") or "")
        if dg.startswith("sha256:"):
            digests[a["name"]] = dg.split(":", 1)[1].strip().lower()
    return tag, assets, digests


def check() -> dict:
    """Visszaadja: {update, current, latest, assets, digests, error}."""
    repo = get_repo()
    res = {"update": False, "current": __version__, "latest": None,
           "assets": {}, "digests": {}, "error": None, "repo": repo}
    if not repo:
        res["error"] = "nincs beállítva a frissítési tárhely"
        return res
    try:
        tag, assets, digests = latest_release(repo)
    except Exception as e:
        res["error"] = str(e)
        return res
    latest = tag.lstrip("vV")
    res["latest"] = latest
    res["assets"] = assets
    res["digests"] = digests
    res["update"] = _ver(latest) > _ver(__version__)
    return res


def _download_to_file(url: str, dest: Path, progress=None) -> str:
    """A fájlt KÖZVETLENÜL a lemezre streameli (nem gyűjti a teljes ~165 MB-ot a
    memóriába), és közben kiszámolja a SHA-256-ot. Visszaadja a hex-lenyomatot,
    hogy az apply() összevethesse a GitHub által megadott hivatalos digesttel."""
    import hashlib
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0) or 0)
        done = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    return h.hexdigest().lower()


def cleanup_old() -> None:
    """A korábbi frissítés maradékainak törlése (induláskor): a régi
    .old.exe-k, a félbemaradt .new fájlok és az elárvult swapper-kötegfájlok."""
    try:
        folder = Path(sys.executable).parent
        for pat in ("*.old.exe", "*.exe.new", "superdl_update_*.bat"):
            for p in folder.glob(pat):
                try:
                    p.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def update_log() -> Path:
    """A frissítés naplófájlja (~/.superdl/update.log) – ide ír a swapper is."""
    d = Path.home() / ".superdl"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d / "update.log"


def _folder_writable(folder: Path) -> bool:
    """A program mappája írható-e? (Program Files / OneDrive / írásvédett hely
    esetén nem – ott a csere eleve nem sikerülhet.)"""
    try:
        t = folder / ".superdl_write_test"
        t.write_text("x", encoding="ascii")
        t.unlink()
        return True
    except OSError:
        return False


def _swapper_script(folder: Path, pairs: list[tuple[Path, Path]],
                    relaunch_name: str | None, pid: int, log: Path) -> str:
    """A swapper-kötegfájl tartalmának előállítása (külön a tesztelhetőségért).

    A külső segédprogramokat (tasklist/find/ping) ABSZOLÚT System32-útvonallal
    hívjuk, nehogy egy PATH-on lévő idegen eszköz (pl. a git Unix-os `find`-ja)
    elrontsa a várakozó ciklust. A késleltetés `ping`-gel megy (nem `timeout`-tal),
    mert a swapper KONZOL NÉLKÜL (leválasztva) fut, ahol a `timeout` stdin híján
    azonnal hibára futna – a `ping -n 2` viszont konzol nélkül is ~1 mp-et vár."""
    sys32 = r'%SystemRoot%\System32'
    wait1 = f'"{sys32}\\ping.exe" -n 2 127.0.0.1 >NUL'   # ~1 mp késleltetés
    L = ['@echo off', 'setlocal enableextensions',
         f'set "LOG={log}"',
         f'echo [SWAP] %DATE% %TIME% indul, varakozas a PID {pid}-re >> "%LOG%" 2>&1',
         'set /a n=0',
         ':wait',
         f'"{sys32}\\tasklist.exe" /FI "PID eq {pid}" 2>NUL | '
         f'"{sys32}\\find.exe" "{pid}" >NUL',
         'if errorlevel 1 goto swap',
         'set /a n+=1',
         'if %n% GEQ 90 goto swap',         # max ~90 mp várakozás
         wait1,
         'goto wait',
         ':swap']
    for i, (newf, target) in enumerate(pairs):
        L += [f'set /a m{i}=0',
              f':mv{i}',
              f'move /Y "{newf}" "{target}" >> "%LOG%" 2>&1',
              f'if not errorlevel 1 goto ok{i}',
              f'set /a m{i}+=1',
              f'if %m{i}% GEQ 30 goto fail{i}',   # max ~30 mp a zárolás oldására
              wait1,
              f'goto mv{i}',
              # a kimerült próbálkozást ŐSZINTÉN naplózzuk (nem tesszük úgy,
              # mintha sikerült volna); a cél exe ilyenkor a régi, ép marad
              f':fail{i}',
              f'echo [SWAP] HIBA: a csere nem sikerult (zarolva maradt): '
              f'{target} >> "%LOG%" 2>&1',
              f':ok{i}']
    if relaunch_name:
        # FONTOS: a frissen lecserélt (nagy, ~165 MB-os) exét NEM indítjuk
        # azonnal újra. A víruskereső a friss írás után átvizsgálja a fájlt, és
        # közben fogja – ha rögtön indítanánk, a onefile-kicsomagolás leszakadna
        # („Failed to load Python DLL python314.dll”). Várunk ~8 mp-et, hogy az
        # AV végezzen, csak utána indítunk.
        L.append('echo [SWAP] varakozas az ujraindites elott (AV atvizsgalas) '
                 '>> "%LOG%" 2>&1')
        L.append(f'"{sys32}\\ping.exe" -n 9 127.0.0.1 >NUL')   # ~8 mp
        L.append(f'echo [SWAP] ujraindites: {relaunch_name} >> "%LOG%" 2>&1')
        L.append(f'start "" "{folder / relaunch_name}"')
    L += ['echo [SWAP] kesz >> "%LOG%" 2>&1', 'del "%~f0"']
    return "\r\n".join(L) + "\r\n"


def _oem_encoding() -> str | None:
    """A cmd.exe a kötegfájlt az OEM-kódlapon olvassa (pl. magyar Windowson
    cp852). Ezt a Python-kódlapnevet adjuk vissza, hogy a swapper-.bat-ot
    PONTOSAN azon írhassuk – így az ÉKEZETES útvonalak (pl. ékezetes Windows-
    felhasználónév) nem romlanak el. None, ha nem állapítható meg."""
    try:
        import ctypes
        cp = int(ctypes.windll.kernel32.GetOEMCP())   # type: ignore[attr-defined]
    except (OSError, AttributeError, ValueError):
        return None
    enc = "utf-8" if cp == 65001 else f"cp{cp}"
    try:
        "x".encode(enc)                                # van-e ilyen codec?
    except LookupError:
        return None
    return enc


def _write_bat(bat: Path, script: str) -> None:
    """A swapper-.bat kiírása úgy, hogy a cmd.exe az ÉKEZETES útvonalakat is
    helyesen értelmezze.

    KORÁBBI HIBA: a fájlt `encoding="ascii"`-vel írtuk, ezért ha a beágyazott
    útvonalban (pl. a ~/.superdl naplófájl vagy a program mappája egy ékezetes
    felhasználónév alatt) ékezetes betű volt, a kiírás elszállt:
    „'ascii' codec can't encode character '\\xda' …" → a frissítés MINDIG
    bukott az ilyen gépeken.

    MEGOLDÁS: elsőként az OEM-kódlapon írunk (a cmd ezt várja, nincs kódlap-
    váltás); ha egy karakter abba nem fér bele, UTF-8-ra váltunk és a .bat
    élére `chcp 65001`-et teszünk, hogy a cmd UTF-8-ként olvassa. Mindkét úton
    `write_bytes`, hogy a `\\r\\n` sorvégek ne duplázódjanak."""
    enc = _oem_encoding()
    if enc and enc != "utf-8":
        try:
            bat.write_bytes(script.encode(enc))        # strict: belefér-e OEM-be
            return
        except UnicodeEncodeError:
            pass                                       # nem fért bele → UTF-8 út
    lines = script.split("\r\n")
    if enc != "utf-8":          # nem-UTF-8 (vagy ismeretlen) konzolról váltunk
        at = 1 if (lines and lines[0].startswith("@echo off")) else 0
        lines.insert(at, "chcp 65001 >NUL")
    bat.write_bytes("\r\n".join(lines).encode("utf-8"))


def _spawn_swapper(folder: Path, pairs: list[tuple[Path, Path]],
                   relaunch_name: str | None) -> None:
    """Leválasztott kötegfájl, ami a folyamat kilépése UTÁN cseréli a fájlokat.
    `pairs`: (új_fájl, cél_fájl) párok; `relaunch_name`: melyik exét indítsa
    újra a csere után (None = ne indítson semmit)."""
    pid = os.getpid()
    log = update_log()
    script = _swapper_script(folder, pairs, relaunch_name, pid, log)

    bat = folder / f"superdl_update_{pid}.bat"
    try:
        _write_bat(bat, script)
    except OSError:
        import tempfile
        bat = Path(tempfile.gettempdir()) / f"superdl_update_{pid}.bat"
        _write_bat(bat, script)

    # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP – a swappernek SAJÁT, rejtett
    # konzolja legyen (így a `tasklist | find` cső és a segédprogramok valós
    # std-leírókkal működnek; a DETACHED_PROCESS itt épp ezért NEM jó, mert
    # leírók nélkül a cső nem jön létre), és a szülő kilépése után is fusson.
    flags = 0x08000000 | 0x00000200
    # TISZTA környezet: különben a swapper által ÚJRAINDÍTOTT SuperDL örökölné a
    # szülő _PYI_APPLICATION_HOME_DIR-jét → bootloader-hiba indításkor.
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags,
                     close_fds=True, cwd=str(folder), env=_clean_child_env())


def is_onedir() -> bool:
    """Onedir (telepítős) build? A futó exe mellett ott van a _internal mappa."""
    try:
        return (Path(sys.executable).parent / "_internal").is_dir()
    except Exception:
        return False


def _find_installer_asset(assets: dict) -> str | None:
    """A kiadás telepítő-assetje (SuperDL-Setup-<verzió>.exe), ha van."""
    for name in assets:
        n = name.lower()
        if n.startswith("superdl-setup-") and n.endswith(".exe"):
            return name
    return None


def _installer_script(setup: Path, pid: int, log: Path) -> str:
    """A telepítő-INDÍTÓ kötegfájl tartalma. KRITIKUS: NEM azonnal futtatja a
    Setup.exe-t, hanem előbb MEGVÁRJA, míg a futó SuperDL (PID) KILÉP – csak
    AZUTÁN indítja a telepítőt. Így a telepítő már zárolatlan fájlokat talál és
    nem ütközik a kilépő/modális appal (ez volt a „letölt, de nem cserél" oka).
    A swapperrel azonos, konzol nélkül is működő mintát (abszolút System32-utak,
    ping-késleltetés, PID-figyelés) használja."""
    sys32 = r'%SystemRoot%\System32'
    wait1 = f'"{sys32}\\ping.exe" -n 2 127.0.0.1 >NUL'      # ~1 mp
    L = ['@echo off', 'setlocal enableextensions',
         f'set "LOG={log}"',
         f'echo [INST] %DATE% %TIME% indul, varakozas a PID {pid} kilepesere '
         f'>> "%LOG%" 2>&1',
         'set /a n=0',
         ':wait',
         f'"{sys32}\\tasklist.exe" /FI "PID eq {pid}" 2>NUL | '
         f'"{sys32}\\find.exe" "{pid}" >NUL',
         'if errorlevel 1 goto run',
         'set /a n+=1',
         'if %n% GEQ 90 goto run',          # max ~90 mp, aztán mindenképp futtat
         wait1,
         'goto wait',
         ':run',
         # rövid ráadás-várakozás, hogy a Restart Manager biztosan elengedje a
         # fájlokat, mielőtt a telepítő nekiállna
         f'"{sys32}\\ping.exe" -n 3 127.0.0.1 >NUL',
         f'echo [INST] telepito inditasa: {setup} >> "%LOG%" 2>&1',
         f'"{setup}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART '
         f'/FORCECLOSEAPPLICATIONS /RESTARTAPPLICATIONS >> "%LOG%" 2>&1',
         'echo [INST] telepito vegzett (kod %ERRORLEVEL%) >> "%LOG%" 2>&1',
         'del "%~f0"']
    return "\r\n".join(L) + "\r\n"


def apply_installer(assets: dict, name: str, progress=None,
                    digests: dict | None = None) -> list[str]:
    """ONEDIR önfrissítés: a Setup.exe letöltése (SHA-256 ellenőrzéssel), majd egy
    INDÍTÓ kötegfájl, ami MEGVÁRJA a SuperDL kilépését, és CSAK AZUTÁN futtatja a
    telepítőt csendben. A telepítő (AppMutex + Restart Manager) kicseréli az
    ÖSSZES fájlt (a _internal mappát is), és újraindítja. A hívónak a visszatérés
    után MIHAMARABB ki kell lépnie."""
    import tempfile
    url = assets.get(name)
    if not url:
        raise RuntimeError(f"A kiadásban nincs telepítő ({name}).")
    dest = Path(tempfile.gettempdir()) / name
    got = _download_to_file(url, dest, progress)
    want = (digests or {}).get(name)
    if want and got != want:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            "A letöltött telepítő ellenőrző összege nem egyezik a hivatalossal "
            "– sérült vagy manipulált, a frissítést megszakítottam.")
    # INDÍTÓ kötegfájl: megvárja a SuperDL kilépését, AZUTÁN futtatja a telepítőt
    # (így nem ütközik a kilépő/modális appal – ez volt a „letölt, de nem cserél").
    pid = os.getpid()
    script = _installer_script(dest, pid, update_log())
    import tempfile as _tf
    bat = Path(_tf.gettempdir()) / f"superdl_install_{pid}.bat"
    _write_bat(bat, script)
    # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP, leválasztva, TISZTA környezettel
    # (a telepítő és az általa ÚJRAINDÍTOTT SuperDL NE örökölje a szülő _PYI_*
    # változóit → különben az újraindított app bootloadere elszáll).
    flags = 0x08000000 | 0x00000200
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags,
                     close_fds=True, env=_clean_child_env())
    return [name]


def apply(assets: dict, progress=None, restart: bool = True,
          digests: dict | None = None) -> list[str]:
    """A futó exe (és a SuperDL-cli.exe, ha van rá kiadás) cseréje egy
    kilépés utáni swapper-kötegfájllal. `restart=True` esetén a csere után
    újraindítja a programot. A hívónak a visszatérés után MIHAMARABB ki kell
    lépnie, hogy a swapper a (már nem zárolt) exét lecserélhesse.

    A letöltött exét a GitHub hivatalos SHA-256 digestjével ELLENŐRIZZÜK: ha
    nem egyezik (sérült vagy manipulált letöltés), megszakítjuk, és a régi,
    működő exe érintetlen marad."""
    if not is_frozen():
        raise RuntimeError(
            "Automatikusan csak a kész exe frissíthető. Forrásból a "
            "megfelelő a 'git pull' a tárhelyről.")
    # ONEDIR/telepítős build: a teljes mappát (a _internal-t is) a TELEPÍTŐ
    # cseréli – nem a single-exe swapper. Letöltjük és csendben futtatjuk.
    inst = _find_installer_asset(assets)
    if inst and is_onedir():
        return apply_installer(assets, inst, progress, digests)
    exe = Path(sys.executable)
    folder = exe.parent
    if not _folder_writable(folder):
        raise RuntimeError(
            f"A program mappája nem írható: {folder}. Valószínűleg Program "
            "Files vagy OneDrive/írásvédett hely. Helyezd át a SuperDL.exe-t "
            "egy saját, írható mappába (pl. az Asztal vagy a Letöltések egy "
            "almappájába), vagy töltsd le kézzel a frissítést a kiadási "
            "oldalról.")

    # a hivatalos ellenőrző összegek (és ha a tárhely nem a hivatalos, azt
    # naplózzuk – egy elállított repo.txt/SUPERDL_REPO így legalább látható)
    repo = get_repo()
    if digests is None:
        try:
            _, _, digests = latest_release(repo)
        except Exception:
            digests = {}
    if repo != DEFAULT_REPO:
        try:
            with open(update_log(), "a", encoding="utf-8") as lf:
                lf.write(f"[UPDATE] FIGYELEM: nem a hivatalos tarhelyrol "
                         f"frissitunk: {repo}\n")
        except OSError:
            pass

    targets = [exe.name]
    if "SuperDL-cli.exe" != exe.name and "SuperDL-cli.exe" not in targets and \
            ("SuperDL-cli.exe" in assets or (folder / "SuperDL-cli.exe").exists()):
        targets.append("SuperDL-cli.exe")

    pairs: list[tuple[Path, Path]] = []
    for name in targets:
        url = assets.get(name)
        if not url:
            continue
        newf = folder / (name + ".new")
        got = _download_to_file(url, newf, progress)   # lemezre + sha256
        want = (digests or {}).get(name)
        if want and got != want:
            newf.unlink(missing_ok=True)
            raise RuntimeError(
                f"A letöltött {name} ellenőrző összege nem egyezik a "
                "hivatalossal – sérült vagy manipulált letöltés. A frissítést "
                "megszakítottam, a jelenlegi verzió érintetlen.")
        pairs.append((newf, folder / name))

    if not pairs:
        raise RuntimeError("A kiadásban nincs letölthető SuperDL.exe.")

    _spawn_swapper(folder, pairs, exe.name if restart else None)
    return [t.name for _, t in pairs]
