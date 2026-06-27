"""Modul-ZIP + modules.json-bejegyzés készítése egy modul-forrásmappából.

Egy modul forrása (pl. modules_src/docconvert/) tartalma:
    manifest.json
    <entry>/__init__.py  (+ a modul többi fájlja)

Ez a szkript ebből épít egy telepíthető ZIP-et (a manifest.json a GYÖKÉRBE, az
entry-csomag a relatív útján), kiszámolja a SHA-256-ot, és kiírja a modules.json
„modules" tömbjébe illeszthető bejegyzést. A ZIP-et a SuperDL GitHub-kiadásába
töltjük fel (tag: mod-<id>-<version>), a bejegyzést a fő repo modules.json-jába.

Használat:
    python tools/build_module.py modules_src/docconvert [dist_dir] [repo]
"""

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

DEFAULT_REPO = "korosmezeydavid/SuperDL"

# DETERMINISZTIKUS build: fix időbélyeg minden bejegyzéshez, hogy az újraépített
# ZIP SHA-256-ja STABIL legyen (a modules.json külön is karbantartható)
_FIXED_DT = (2026, 1, 1, 0, 0, 0)


def _add(z, arcname: str, data: bytes):
    zi = zipfile.ZipInfo(arcname, date_time=_FIXED_DT)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    z.writestr(zi, data)


def build(src_dir: str, dist_dir: str = "dist_modules",
          repo: str = DEFAULT_REPO):
    src = Path(src_dir)
    man = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    mid, ver, entry = man["id"], man["version"], man["entry"]

    pkg = src / entry
    if not pkg.is_dir():
        raise SystemExit(f"Hiányzik a belépési csomag: {pkg}")
    files = [("manifest.json", (src / "manifest.json").read_bytes())]
    for f in sorted(pkg.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            arc = str(f.relative_to(src)).replace("\\", "/")
            files.append((arc, f.read_bytes()))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for arc, b in sorted(files):       # stabil sorrend + fix időbélyeg
            _add(z, arc, b)
    data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()

    dist = Path(dist_dir)
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"{mid}-{ver}.zip"
    out.write_bytes(data)

    tag = f"mod-{mid}-{ver}"
    entry_json = {
        "id": mid,
        "name": man.get("name", mid),
        "category": man.get("category", "Egyéb"),
        "description": man.get("description", ""),
        "latest": {
            "version": ver,
            "min_core_api": man.get("min_core_api", "1.0"),
            "url": f"https://github.com/{repo}/releases/download/{tag}/{out.name}",
            "sha256": sha,
            "size": len(data),
        },
    }
    print(f"ZIP:     {out}  ({len(data)} byte)")
    print(f"SHA-256: {sha}")
    print(f"GitHub kiadás-tag: {tag}  (ide töltsd fel a ZIP-et)")
    print("\nmodules.json bejegyzés (a 'modules' tömbbe):")
    print(json.dumps(entry_json, ensure_ascii=False, indent=2))
    return out, sha, entry_json


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Használat: python tools/build_module.py "
                         "<modul-forrásmappa> [dist_dir] [repo]")
    a = sys.argv
    build(a[1], a[2] if len(a) > 2 else "dist_modules",
          a[3] if len(a) > 3 else DEFAULT_REPO)
