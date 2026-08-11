# -*- coding: utf-8 -*-
"""Minimál STUN-kliens (RFC 5389) – a gép PUBLIKUS (internet felőli) cím:port-ja.

Ez teszi lehetővé az internetes hang-hívást fizetős szerver NÉLKÜL: a publikus
végpontot ingyenes, nyilvános STUN-szerver mondja meg (a Google-é is jó), a két
fél pedig a szoba Ably-csatornáján kicseréli ezeket, majd UDP hole-punchinggal
átlyukasztja a routereit. FONTOS: a lekérdezést UGYANAZON a socketen kell
futtatni, amit a hanghoz is használunk – így a router-leképezés (a publikus
port) ugyanaz marad.

Csak beépített `socket`+`struct`+`os` kell (nincs függőség, nincs Core-build).
"""
import os
import socket
import struct

_MAGIC = 0x2112A442                       # STUN magic cookie
_XOR_MAPPED = 0x0020
_MAPPED = 0x0001

# ingyenes, nyilvános STUN-szerverek (több, ha az egyik nem válaszol)
SZERVEREK = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
    ("stun.nextcloud.com", 3478),
]


def _keres() -> tuple:
    txid = os.urandom(12)
    return struct.pack(">HHI12s", 0x0001, 0, _MAGIC, txid), txid


def _valasz_cim(data: bytes):
    """A STUN-válaszból kiolvassa a (publikus_ip, port)-ot (XOR-MAPPED, illetve
    tartalék a sima MAPPED-ADDRESS-ből)."""
    if len(data) < 20:
        return None
    _, mlen, magic = struct.unpack(">HHI", data[:8])
    if magic != _MAGIC:
        return None
    i, veg = 20, 20 + mlen
    while i + 4 <= veg and i + 4 <= len(data):
        atype, alen = struct.unpack(">HH", data[i:i + 4])
        i += 4
        val = data[i:i + alen]
        i += alen + ((4 - alen % 4) % 4)
        if atype in (_XOR_MAPPED, _MAPPED) and len(val) >= 8 and val[1] == 0x01:
            if atype == _XOR_MAPPED:
                port = struct.unpack(">H", val[2:4])[0] ^ (_MAGIC >> 16)
                ipnum = struct.unpack(">I", val[4:8])[0] ^ _MAGIC
            else:                            # sima MAPPED (nem XOR-olt)
                port = struct.unpack(">H", val[2:4])[0]
                ipnum = struct.unpack(">I", val[4:8])[0]
            ip = socket.inet_ntoa(struct.pack(">I", ipnum))
            return (ip, port)
    return None


def publikus_cim(sock, timeout: float = 2.0):
    """A megadott (UDP) socket PUBLIKUS cím:port-ja a nyilvános STUN szerint,
    vagy None, ha egyik szerver sem válaszol. A socket blokkolási állapotát a
    hívó után visszaállítja (a lekérdezés idejére időtúllépést állít be)."""
    regi_to = sock.gettimeout()
    try:
        for host, port in SZERVEREK:
            try:
                cel = socket.getaddrinfo(host, port, socket.AF_INET,
                                         socket.SOCK_DGRAM)[0][4]
            except Exception:
                continue
            req, txid = _keres()
            sock.settimeout(timeout)
            try:
                sock.sendto(req, cel)
                # több választ is fogadhatunk (más forgalom is jöhet) – néhányat
                for _ in range(4):
                    data, _addr = sock.recvfrom(2048)
                    if len(data) >= 20 and data[8:20] == txid:
                        cim = _valasz_cim(data)
                        if cim:
                            return cim
            except (socket.timeout, OSError):
                continue
        return None
    finally:
        try:
            sock.settimeout(regi_to)
        except Exception:
            pass
