"""A SuperDL saját frissítése a GitHub-kiadásokból.

A program a megadott GitHub-tárhely legújabb kiadását (Release) figyeli.
Ha a kiadás verziója újabb a futónál, letölti a hozzá tartozó exe-t, és
kicseréli magát. Windows alatt a futó exe nem írható felül, de átnevezhető,
ezért:
  1. a régi SuperDL.exe -> SuperDL.old.exe (átnevezés futás közben is megy)
  2. az új exe a helyére kerül
  3. a program újraindul; induláskor törli a .old.exe maradékot.

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


def latest_release(repo: str) -> tuple[str, dict]:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    tag = d.get("tag_name", "")
    assets = {a["name"]: a["browser_download_url"]
              for a in d.get("assets", [])}
    return tag, assets


def check() -> dict:
    """Visszaadja: {update, current, latest, assets, error}."""
    repo = get_repo()
    res = {"update": False, "current": __version__, "latest": None,
           "assets": {}, "error": None, "repo": repo}
    if not repo:
        res["error"] = "nincs beállítva a frissítési tárhely"
        return res
    try:
        tag, assets = latest_release(repo)
    except Exception as e:
        res["error"] = str(e)
        return res
    latest = tag.lstrip("vV")
    res["latest"] = latest
    res["assets"] = assets
    res["update"] = _ver(latest) > _ver(__version__)
    return res


def _download(url: str, progress=None) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length", 0) or 0)
        buf = bytearray()
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            buf += chunk
            if progress and total:
                progress(len(buf) / total)
    return bytes(buf)


def cleanup_old() -> None:
    """A korábbi frissítés .old.exe maradékának törlése (induláskor)."""
    try:
        folder = Path(sys.executable).parent
        for p in folder.glob("*.old.exe"):
            try:
                p.unlink()
            except OSError:
                pass
    except Exception:
        pass


def apply(assets: dict, progress=None, restart: bool = True) -> list[str]:
    """A futó exe (és a SuperDL-cli.exe, ha van rá kiadás) cseréje."""
    if not is_frozen():
        raise RuntimeError(
            "Automatikusan csak a kész exe frissíthető. Forrásból a "
            "megfelelő a 'git pull' a tárhelyről.")
    exe = Path(sys.executable)
    folder = exe.parent
    targets = [exe.name]
    if "SuperDL-cli.exe" not in targets and \
            ("SuperDL-cli.exe" in assets or (folder / "SuperDL-cli.exe").exists()):
        targets.append("SuperDL-cli.exe")

    swapped = []
    for name in targets:
        url = assets.get(name)
        if not url:
            continue
        data = _download(url, progress)
        newf = folder / (name + ".new")
        newf.write_bytes(data)
        target = folder / name
        oldf = folder / (Path(name).stem + ".old.exe")
        if target.exists():
            try:
                if oldf.exists():
                    oldf.unlink()
            except OSError:
                pass
            os.replace(target, oldf)        # futó exe átnevezése – Windows: OK
        os.replace(newf, target)
        swapped.append(name)

    if not swapped:
        raise RuntimeError("A kiadásban nincs letölthető SuperDL.exe.")
    if restart:
        subprocess.Popen([str(folder / exe.name)], close_fds=True)
    return swapped
