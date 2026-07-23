# -*- coding: utf-8 -*-
"""Közös URL-biztonsági réteg (SSRF- és erőforrás-védelem).

MIÉRT KELL: a hírolvasó, a podcast-feliratkozás és a külső naptár (ICS) is
TETSZŐLEGES, felhasználótól vagy távoli feedből származó címet tölt le. Védelem
nélkül ez elérhetné a gép saját szolgáltatásait (localhost), a házi hálózat
eszközeit (router, NAS, kamera), vagy egy óriási/„tömörítési bombának" szánt
válasszal elfogyaszthatná a memóriát.

MIT VÉD:
  • csak http/https séma (nincs file:, ftp:, custom protokoll);
  • nincs loopback / privát / link-local / multicast cél – ÁTIRÁNYÍTÁS UTÁN SEM
    (a DNS-t minden lépésnél újra ellenőrizzük);
  • korlátozott átirányítás-szám;
  • korlátozott válaszméret (streamelve olvasunk, nem `read()` mindent).

[Herman Tibi CAL-P0-07 / NEWS-P0-02 / POD-P0-02]
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit

DEFAULT_MAX_BYTES = 8 * 1024 * 1024      # 8 MB – bőven elég feedhez/cikkhez
DEFAULT_TIMEOUT = 20
MAX_REDIRECTS = 5
_UA = {"User-Agent": "SuperDL"}


class UrlNotAllowed(ValueError):
    """A cím biztonsági okból nem tölthető le (magyar, felolvasható indoklás)."""


def _ip_is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return True                      # értelmezhetetlen cím: inkább tiltjuk
    return (a.is_private or a.is_loopback or a.is_link_local
            or a.is_multicast or a.is_reserved or a.is_unspecified)


def _resolve_all(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise UrlNotAllowed(f"A kiszolgáló neve nem oldható fel: {host} ({e})")
    return [i[4][0] for i in infos]


def check_url(url: str) -> str:
    """A cím ellenőrzése. Visszaadja a normalizált URL-t, vagy UrlNotAllowed-ot
    dob magyar indoklással."""
    u = (url or "").strip()
    if not u:
        raise UrlNotAllowed("Nincs megadva cím.")
    s = urlsplit(u)
    if s.scheme.lower() not in ("http", "https"):
        raise UrlNotAllowed(
            "Csak webes (http vagy https) cím tölthető le. "
            f"Ez a cím „{s.scheme or 'ismeretlen'}” típusú.")
    if not s.hostname:
        raise UrlNotAllowed("A címben nincs kiszolgálónév.")
    for ip in _resolve_all(s.hostname):
        if _ip_is_private(ip):
            raise UrlNotAllowed(
                "Ez a cím a saját géped vagy a helyi hálózatod egyik eszközére "
                "mutat, ezért biztonsági okból nem töltöm le.")
    return u


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Minden átirányítást ÚJRA ellenőrzünk (a támadó az első, ártalmatlan
    címről irányíthatna át a belső hálózatra)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)                       # dob, ha nem megengedett
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_open(url: str, timeout: int = DEFAULT_TIMEOUT):
    """Ellenőrzött megnyitás (a hívó olvassa a választ)."""
    url = check_url(url)
    op = urllib.request.build_opener(_SafeRedirectHandler)
    return op.open(urllib.request.Request(url, headers=_UA), timeout=timeout)


def safe_read(url: str, *, max_bytes: int = DEFAULT_MAX_BYTES,
              timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """Ellenőrzött, MÉRETKORLÁTOS letöltés. A választ darabokban olvassuk, így
    egy óriási vagy végtelen válasz sem eszi meg a memóriát."""
    with safe_open(url, timeout=timeout) as r:
        # ha a kiszolgáló bemondja a méretet, előre elutasíthatjuk
        try:
            n = int(r.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            n = 0
        if n and n > max_bytes:
            raise UrlNotAllowed(
                f"A letöltendő tartalom túl nagy ({n // 1024} kilobájt), "
                f"a biztonsági korlát {max_bytes // 1024} kilobájt.")
        out = bytearray()
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            out += chunk
            if len(out) > max_bytes:
                raise UrlNotAllowed(
                    "A letöltendő tartalom túllépte a biztonsági méretkorlátot "
                    f"({max_bytes // 1024} kilobájt).")
        return bytes(out)


def safe_read_text(url: str, *, encoding: str = "utf-8",
                   max_bytes: int = DEFAULT_MAX_BYTES,
                   timeout: int = DEFAULT_TIMEOUT) -> str:
    return safe_read(url, max_bytes=max_bytes, timeout=timeout).decode(
        encoding, errors="replace")


def is_web_url(url: str) -> bool:
    """Böngészőben/külső programban megnyitható-e? (csak http/https)
    A hírolvasó és a podcast „Megnyitás böngészőben" gombja feedből származó
    címet kap – az nem indíthat helyi protokollt. [NEWS-P1-10 / POD-P1-12]"""
    try:
        return urlsplit((url or "").strip()).scheme.lower() in ("http", "https")
    except Exception:
        return False
