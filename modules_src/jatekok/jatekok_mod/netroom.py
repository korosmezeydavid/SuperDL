# -*- coding: utf-8 -*-
"""Ably-alapú „szoba" a gépek közti, KÖRÖKRE OSZTOTT online játékhoz.

Minden szoba egy Ably-CSATORNA (a szobakód alapján). A kliens REST-en PUBLIKÁL
egy üzenetet, és a csatorna ELŐZMÉNYÉT (history) pollozza az újakért. Nincs
SDK-függőség: csak a Core-ban már meglévő `requests`. Host-authoritative: a
játéklogika a KLIENSBEN fut, a szerver csak továbbít – így a rejtvény sosem
megy le a tippelőkhöz (nem lehet csalni).

A kulcs sosem kerül a forrásba: env `SUPERDL_ABLY_KEY`, vagy a
`~/.superdl/ably_key.txt` fájlból olvassuk.
"""
import json
import os
import random
import threading

import requests

_REST = "https://rest.ably.io"
# bemondható szobakód: a félreérthető 0/O és 1/I kihagyva
_KOD_ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def ably_kulcs() -> str:
    """Az Ably API-kulcs (appId.keyId:secret) vagy üres, ha nincs beállítva.

    Sorrend: env → a fejlesztő helyi kulcsa (~/.superdl/ably_key.txt) → a
    modulba CSOMAGOLT közös kulcs. Ez utóbbi teszi lehetővé, hogy MINDEN
    felhasználó beállítás nélkül, csak internettel játszhasson. A csomagolt
    kulcs NEM kerül a nyilvános forráskódba (git-ignorált), csak a kiadott
    csomagba – érdemes hozzá korlátozott (csak publish/subscribe) kulcsot adni."""
    k = (os.environ.get("SUPERDL_ABLY_KEY") or "").strip()
    if k:
        return k
    try:
        from superdl import store
        p = store.CONFIG_DIR / "ably_key.txt"
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    try:
        bp = os.path.join(os.path.dirname(__file__), "ably_kulcs_beepitett.txt")
        if os.path.isfile(bp):
            with open(bp, encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def szobakod(hossz: int = 5) -> str:
    """Rövid, hangosan bemondható szobakód (pl. GK7QP)."""
    return "".join(random.choice(_KOD_ABC) for _ in range(hossz))


class NetSzoba:
    """Egy online játék-szoba (egy Ably-csatorna). Nem tud a játékról semmit,
    csak üzeneteket küld/fogad a szobában."""

    def __init__(self, kod: str, nev: str, kulcs: str = ""):
        self.kod = (kod or "").strip().upper()
        self.nev = nev
        self._kulcs = kulcs or ably_kulcs()
        self._chan = f"szerencsekerek:{self.kod}"
        self._last = 0                 # utolsó látott üzenet ideje (ms)
        self._seen: set = set()        # látott üzenet-id-k (dedup)
        self._stop = threading.Event()
        self._cb = None
        self._thread = None

    def elerheto(self) -> bool:
        return bool(self._kulcs) and bool(self.kod)

    def _auth(self):
        # az Ably-kulcs: 'appId.keyId:secret' -> HTTP basic (user, pass)
        reszek = self._kulcs.split(":", 1)
        return (reszek[0], reszek[1] if len(reszek) > 1 else "")

    def kuld(self, tipus: str, adat=None) -> bool:
        """Egy üzenet a szobába. `tipus` = üzenet neve, `adat` = tetszőleges JSON."""
        body = {"name": tipus,
                "data": json.dumps({"ki": self.nev, "adat": adat or {}})}
        r = requests.post(f"{_REST}/channels/{self._chan}/messages",
                          auth=self._auth(), json=body, timeout=15)
        r.raise_for_status()
        return True

    def uj_uzenetek(self) -> list:
        """Az utolsó lekérés ÓTA érkezett üzenetek, időrendben (dedupolva)."""
        params = {"limit": 100, "direction": "forwards"}
        if self._last:
            params["start"] = self._last + 1
        r = requests.get(f"{_REST}/channels/{self._chan}/messages",
                         auth=self._auth(), params=params, timeout=15)
        r.raise_for_status()
        ki = []
        for m in r.json():
            mid = m.get("id")
            if mid and mid in self._seen:
                continue
            if mid:
                self._seen.add(mid)
            ts = int(m.get("timestamp", 0) or 0)
            self._last = max(self._last, ts)
            try:
                d = json.loads(m.get("data") or "{}")
            except Exception:
                d = {}
            ki.append({"tipus": m.get("name"), "ki": d.get("ki"),
                       "adat": d.get("adat", {}), "ido": ts})
        return ki

    def figyel(self, callback, koz: float = 1.0):
        """Háttérben pollozza az új üzeneteket, és mindegyikre meghívja a
        callbackot (a felület wx.CallAfter-rel tegye a UI-ra)."""
        self._cb = callback
        self._thread = threading.Thread(target=self._loop, args=(koz,),
                                        daemon=True)
        self._thread.start()

    def _loop(self, koz):
        while not self._stop.wait(koz):
            try:
                for u in self.uj_uzenetek():
                    if self._cb:
                        self._cb(u)
            except Exception:
                pass

    def leallit(self):
        self._stop.set()
