"""Korlátos HTTP-olvasás; az URL-védelem minden átirányításra érvényes."""
from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urljoin, urlsplit

import requests

MAX_BYTES = 3 * 1024 * 1024
USER_AGENT = "SuperDL-SuperSurf/0.1 (public article reader)"


class FetchError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def public_url(url: str) -> str:
    """Csak nyilvános HTTP(S) cél; DNS és redirect ellenőrzés is szükséges."""
    try:
        parsed = urlsplit(url.strip())
        host = parsed.hostname
        port = parsed.port
    except (ValueError, AttributeError):
        raise FetchError("invalid_input", "Érvénytelen webcím.") from None
    if parsed.scheme.lower() not in ("http", "https") or not host or parsed.username or parsed.password:
        raise FetchError("unsupported_url", "Csak nyilvános HTTP vagy HTTPS webcím olvasható.")
    if port not in (None, 80, 443):
        raise FetchError("blocked_url", "Ez a webcím nem engedélyezett hálózati portot használ.")
    if host.rstrip(".").lower() in ("localhost",) or host.lower().endswith((".local", ".internal")):
        raise FetchError("blocked_url", "Helyi hálózati cím nem olvasható.")
    try:
        addresses = socket.getaddrinfo(host, port or (443 if parsed.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        raise FetchError("network", "A webcím nem érhető el.", True) from None
    if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
        raise FetchError("blocked_url", "Helyi vagy nem nyilvános hálózati cím nem olvasható.")
    return url


class HttpClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

    def get(self, url: str, *, expected: str) -> tuple[bytes, str, str]:
        current = url
        for _ in range(5):
            public_url(current)
            try:
                with self.session.get(current, headers={"User-Agent": USER_AGENT, "Accept":
                                      "application/json" if expected == "json" else "text/html,application/xhtml+xml"},
                                      timeout=(5, 12), allow_redirects=False, stream=True) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise FetchError("http_error", "A weboldal hibás átirányítást adott.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code == 404:
                        raise FetchError("no_content", "Nem található tartalom ezen a címen.")
                    if response.status_code == 429:
                        raise FetchError("rate_limited", "A forrás átmenetileg korlátozza a lekérdezéseket.", True)
                    if response.status_code >= 400:
                        raise FetchError("http_error", f"A forrás hibát jelzett ({response.status_code}).", response.status_code >= 500)
                    mime = response.headers.get("Content-Type", "").lower()
                    if expected == "json" and "json" not in mime:
                        raise FetchError("invalid_response", "A forrás nem JSON adatot küldött.")
                    if expected == "html" and not any(x in mime for x in ("text/html", "application/xhtml+xml")):
                        raise FetchError("invalid_response", "Ez a cím nem HTML cikkoldal.")
                    data = bytearray()
                    for chunk in response.iter_content(chunk_size=65536):
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise FetchError("invalid_response", "A tartalom túl nagy a biztonságos olvasáshoz.")
                    return bytes(data), response.url, mime
            except requests.Timeout:
                raise FetchError("timeout", "A lekérdezés túllépte az időkorlátot.", True) from None
            except requests.RequestException:
                raise FetchError("network", "Hálózati hiba történt a lekérdezés közben.", True) from None
        raise FetchError("invalid_response", "Túl sok átirányítást adott a weboldal.")

    def json(self, url: str) -> tuple[object, str]:
        raw, final, _ = self.get(url, expected="json")
        try:
            return json.loads(raw), final
        except (UnicodeDecodeError, ValueError):
            raise FetchError("invalid_response", "A forrás hibás JSON adatot küldött.") from None

    def html(self, url: str) -> tuple[str, str]:
        raw, final, mime = self.get(url, expected="html")
        # A HTML parser a meta charsetet is figyelembe veszi, ha bájtokat kap.
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw, "html.parser")
        return str(soup), final
