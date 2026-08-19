# -*- coding: utf-8 -*-
"""Super Mail – OFFLINE OLVASÁS (helyi gyorsítótár).

„A letöltött levelek internet nélkül is olvashatók.” Vonaton, nyaralásban,
kieső hálózatnál a program ne egy hibaüzenet legyen, hanem működjön tovább
azzal, ami már nálunk van.

MIT TÁROLUNK: a listák fejléc-adatait (feladó, tárgy, dátum…) mappánként, és a
MEGNYITOTT levelek teljes szövegét. Csak azt, amit a felhasználó tényleg
megnézett – nem szippantjuk le az egész postaládát a háta mögött.

HOL: a felhasználó saját gépén, a többi Super Mail-adat mellett. Semmi nem megy
sehova; ez ugyanaz az elv, mint a helyben futó fordításnál.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

MAPPA_NEV = "gyorsitotar"
MAX_LEVEL = 500                # ennyi teljes levelet őrzünk fiókonként


def alap_mappa() -> str:
    from superdl import store
    return os.path.join(str(store.CONFIG_DIR), MAPPA_NEV)


def _kulcs(*reszek) -> str:
    nyers = "|".join(str(r or "") for r in reszek)
    return hashlib.sha256(nyers.encode("utf-8")).hexdigest()[:24]


def _biztos_ir(ut: str, adat: bytes) -> None:
    os.makedirs(os.path.dirname(ut), exist_ok=True)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "wb") as f:
        f.write(adat)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)


# ====================================================================
#  Listák (fejléc-adatok)
# ====================================================================

def lista_ment(fiok: str, mappa_nev: str, lista, mappa: str = "") -> None:
    """A betöltött lista elmentése – ebből lesz az offline nézet."""
    gyoker = mappa or alap_mappa()
    ut = os.path.join(gyoker, "lista_%s.json" % _kulcs(fiok, mappa_nev))
    tiszta = []
    for info in lista or []:
        # a fiók-objektumot NEM mentjük (jelszót tartalmazhat!) – csak a címét
        d = {k: v for k, v in info.items() if not k.startswith("_")}
        f = info.get("_fiok") or {}
        if f.get("email"):
            d["_fiok_cim"] = f.get("email")
        d["_mappa"] = info.get("_mappa", mappa_nev)
        tiszta.append(d)
    _biztos_ir(ut, json.dumps({"mentve": time.time(), "mappa": mappa_nev,
                               "lista": tiszta},
                              ensure_ascii=False).encode("utf-8"))


def lista_betolt(fiok: str, mappa_nev: str, mappa: str = ""):
    """(lista, mikor_mentettük) – ha nincs mentés: ([], 0)."""
    gyoker = mappa or alap_mappa()
    ut = os.path.join(gyoker, "lista_%s.json" % _kulcs(fiok, mappa_nev))
    try:
        with open(ut, encoding="utf-8") as f:
            d = json.load(f)
        return list(d.get("lista", [])), float(d.get("mentve", 0))
    except (OSError, ValueError):
        return [], 0.0


# ====================================================================
#  Teljes levelek
# ====================================================================

def level_ment(fiok: str, uid, msg, mappa: str = "") -> None:
    gyoker = mappa or alap_mappa()
    ut = os.path.join(gyoker, "level_%s.eml" % _kulcs(fiok, uid))
    try:
        _biztos_ir(ut, msg.as_bytes())
    except Exception:
        return
    _takarit(gyoker)


def level_betolt(fiok: str, uid, mappa: str = ""):
    import email
    from email.policy import default as _alap
    gyoker = mappa or alap_mappa()
    ut = os.path.join(gyoker, "level_%s.eml" % _kulcs(fiok, uid))
    try:
        with open(ut, "rb") as f:
            return email.message_from_binary_file(f, policy=_alap)
    except (OSError, ValueError):
        return None


def _takarit(gyoker: str) -> None:
    """A legrégebbi leveleket dobjuk el, ha túl sok gyűlt össze."""
    try:
        fajlok = [(os.path.getmtime(os.path.join(gyoker, n)),
                   os.path.join(gyoker, n))
                  for n in os.listdir(gyoker) if n.startswith("level_")]
    except OSError:
        return
    if len(fajlok) <= MAX_LEVEL:
        return
    for _ido, ut in sorted(fajlok)[:len(fajlok) - MAX_LEVEL]:
        try:
            os.remove(ut)
        except OSError:
            pass


def urit(mappa: str = "") -> int:
    """A teljes gyorsítótár törlése. Visszaadja a törölt fájlok számát."""
    gyoker = mappa or alap_mappa()
    db = 0
    try:
        nevek = os.listdir(gyoker)
    except OSError:
        return 0
    for n in nevek:
        try:
            os.remove(os.path.join(gyoker, n))
            db += 1
        except OSError:
            pass
    return db


def meret(mappa: str = "") -> int:
    gyoker = mappa or alap_mappa()
    osszes = 0
    try:
        for n in os.listdir(gyoker):
            try:
                osszes += os.path.getsize(os.path.join(gyoker, n))
            except OSError:
                pass
    except OSError:
        return 0
    return osszes


def kor_szoveg(mikor: float, most: float = 0.0) -> str:
    """„3 perce mentve” – hogy tudd, mennyire friss, amit hallasz."""
    if not mikor:
        return "ismeretlen időből"
    most = most or time.time()
    tel = max(0, int(most - mikor))
    if tel < 60:
        return "az imént mentve"
    if tel < 3600:
        return "%d perce mentve" % (tel // 60)
    if tel < 86400:
        return "%d órája mentve" % (tel // 3600)
    return "%d napja mentve" % (tel // 86400)
