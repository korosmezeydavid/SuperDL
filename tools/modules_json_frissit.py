# -*- coding: utf-8 -*-
"""A `modules.json` egy modul-bejegyzésének frissítése a manifestből és a ZIP-ből.

Kézzel szerkeszteni hibaforrás (a leírások több ezer karakteresek). Ez a szkript
a MANIFESTET tekinti igazságnak, a ZIP-ből veszi a méretet és a SHA-256-ot, és a
GitHub-release URL-t a bevett séma szerint állítja elő.

    python tools\\modules_json_frissit.py tvmusor mail
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = ("https://github.com/korosmezeydavid/SuperDL/releases/download/"
       "mod-{id}-{v}/{id}-{v}.zip")


def frissit(mod_id: str) -> str:
    man = json.loads((ROOT / "modules_src" / mod_id / "manifest.json")
                     .read_text(encoding="utf-8"))
    v = man["version"]
    zip_ut = ROOT / "dist_modules" / f"{mod_id}-{v}.zip"
    if not zip_ut.exists():
        raise SystemExit(f"HIÁNYZIK: {zip_ut} – előbb build_module.py")
    adat = zip_ut.read_bytes()

    kat = ROOT / "modules.json"
    kat_adat = json.loads(kat.read_text(encoding="utf-8"))
    for m in kat_adat["modules"]:
        if m["id"] == mod_id:
            break
    else:
        raise SystemExit(f"nincs ilyen modul a modules.json-ban: {mod_id}")

    regi = m["latest"]["version"]
    m["name"] = man["name"]
    m["category"] = man["category"]
    m["description"] = man["description"]
    m["latest"] = {
        "version": v,
        "min_core_api": man["min_core_api"],
        "min_core_version": man["min_core_version"],
        "url": URL.format(id=mod_id, v=v),
        "sha256": hashlib.sha256(adat).hexdigest(),
        "size": len(adat),
    }
    kat.write_text(json.dumps(kat_adat, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return f"{mod_id}: {regi} -> {v}  ({len(adat)} byte)"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for mid in sys.argv[1:]:
        print(frissit(mid))
