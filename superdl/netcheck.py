"""Internetkapcsolat gyors, akadálymentes ellenőrzése az EGÉSZ programhoz.

Cél: MIELŐTT egy hálózatot igénylő művelet (letöltés, rádió, frissítés, online
hang, AI…) hosszú várakozásba vagy kriptikus hibába futna, a program AZONNAL,
érthetően jelezhesse a felhasználónak, hogy nincs internet. A `friendly_error`
(media.py) pedig a MÁR bekövetkezett hibákat is egységes üzenetté fordítja.

Adatvédelem: a kapcsolat-próba NEM küld személyes adatot – csak TCP-kapcsolatot
NYIT egy közismert DNS-szerver IP-jére (nincs domain-feloldás, nincs
kérés-tartalom, nincs adatküldés).
"""

import socket
import threading
import time

# közismert, stabil DNS-szerverek (IP:port) – kizárólag kapcsolat-nyitáshoz
_PROBES = (("1.1.1.1", 53), ("8.8.8.8", 53), ("9.9.9.9", 53))

_lock = threading.Lock()
_cache = {"ts": 0.0, "ok": False}
_CACHE_SEC = 5.0          # a friss eredményt ennyi ideig újrahasználjuk


def _probe(timeout: float) -> bool:
    for host, port in _PROBES:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def online(timeout: float = 2.0, force: bool = False) -> bool:
    """Van-e internetkapcsolat? Gyors (pár másodperc), és az eredményt RÖVID
    ideig gyorsítótárazza, hogy az egymás utáni ellenőrzések (pl. több modul) ne
    próbálgassanak feleslegesen. `force=True` friss mérést kényszerít."""
    now = time.monotonic()
    with _lock:
        if not force and (now - _cache["ts"]) < _CACHE_SEC:
            return _cache["ok"]
    ok = _probe(timeout)
    with _lock:
        _cache["ts"] = time.monotonic()
        _cache["ok"] = ok
    return ok


def service_reachable(host: str, port: int = 443, timeout: float = 3.0) -> bool:
    """Elérhető-e egy KONKRÉT szolgáltatás (hosztnév). Ezzel megkülönböztethető:
    van net, de épp az adott szerver nem válaszol."""
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


_OFFLINE = ("Nincs internetkapcsolat. Ehhez {what} internet kell. Ellenőrizd a "
            "wifit vagy a mobilnetet, majd próbáld újra.")


def require_online(what: str = "ehhez a művelethez", timeout: float = 2.0):
    """Elő-ellenőrzés egy net-igényes művelet ELŐTT. Visszaad: (ok, üzenet).
    Ha van net → (True, ''); ha nincs → (False, kész magyar mondat, amit hangosan
    és a státuszban is meg lehet jeleníteni)."""
    if online(timeout=timeout):
        return True, ""
    return False, _OFFLINE.format(what=what)


def offline_reason(host: str = "", port: int = 443):
    """Egy sikertelen net-művelet UTÁN: megmondja, egyáltalán nincs-e net, vagy
    csak az adott szolgáltatás nem elérhető (Laci mindkettőt kérte). Visszaad:
    (kód, üzenet), ahol a kód: 'no_internet' | 'service_down' | 'ok'."""
    if not online(force=True):
        return "no_internet", ("Nincs internetkapcsolat. Ellenőrizd a wifit vagy "
                               "a mobilnetet, majd próbáld újra.")
    if host and not service_reachable(host, port):
        return "service_down", ("Az internet működik, de ez a szolgáltatás most "
                                "nem elérhető. Próbáld meg később.")
    return "ok", ""


# a hálózati hibák felismeréséhez (friendly_error és a hívók használják)
_NET_HINTS = (
    "getaddrinfo failed", "name or service not known", "nodename nor servname",
    "temporary failure in name resolution", "failed to establish a new connection",
    "max retries exceeded", "connection aborted", "connection reset",
    "connection refused", "network is unreachable", "no route to host",
    "timed out", "timeout", "urlopen error", "ssl", "nem érhető el a hálózat",
    "10054", "10060", "10061", "11001",
)


def looks_like_offline(text: str) -> bool:
    """Egy hibaszövegről eldönti, hogy hálózati/kapcsolati eredetű-e."""
    t = (text or "").lower()
    return any(h in t for h in _NET_HINTS)
