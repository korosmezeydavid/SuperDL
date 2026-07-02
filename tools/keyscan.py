"""DPAPI-tudatos kulcs-szkenner a publikálandó SuperDL-fájlokhoz.

Betölti (DEKÓDOLVA) a felhasználó tárolt AI/TTS-kulcsait a store-on át, majd
MINDEN megadott fájlban (és mappában rekurzívan) megkeresi azokat NYERS
BYTE-ként. Ha BÁRMELYIK kulcs előfordul → NE PUBLIKÁLD.

Használat:
  python keyscan.py <fájl-vagy-mappa> [<továbbiak>…]
Kilépési kód: 0 = TISZTA, 2 = KULCS TALÁLAT.
"""

import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\msn\Documents\Audacity\SuperDownloader")
from superdl import store


def collect_keys() -> set[str]:
    keys: set[str] = set()

    def walk(o):
        if isinstance(o, str):
            s = o.strip()
            if len(s) >= 12:            # csak érdemi hosszúságú kulcsok (a zaj ki)
                keys.add(s)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    for loader in ("load_ai_config", "load_tts_keys"):
        try:
            walk(getattr(store, loader)())
        except Exception as e:
            print(f"  ({loader} olvasás hiba: {e})")
    return keys


def iter_files(targets):
    for t in targets:
        p = Path(t)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    yield f


def main(targets):
    keys = collect_keys()
    print(f"Betöltött (dekódolt) kulcsok száma: {len(keys)}")
    if not keys:
        print("FIGYELEM: nincs betöltött AI/TTS-kulcs – nincs mit keresni "
              "(vagy nincs beállítva kulcs ezen a gépen).")
    key_bytes = [(k, k.encode("utf-8")) for k in keys if k]
    hits, nfiles = [], 0
    for f in iter_files(targets):
        nfiles += 1
        try:
            data = f.read_bytes()
        except OSError:
            continue
        for k, kb in key_bytes:
            if kb and kb in data:
                hits.append((str(f), k[:6] + "…"))
    print(f"Átvizsgált fájlok: {nfiles}")
    if hits:
        print("\n‼‼ KULCS TALÁLAT – NE PUBLIKÁLD ‼‼")
        for f, km in hits:
            print("   ", f, "->", km)
        return 2
    print("\n✅ TISZTA — egyetlen tárolt kulcs sem található a fájlokban.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
