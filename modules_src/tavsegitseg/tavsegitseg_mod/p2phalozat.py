# -*- coding: utf-8 -*-
"""Távsegítség – ÁLTALÁNOS, alacsony-késésű P2P UDP transzport (1:1).

Ez viszi a valós idejű forgalmat: a vezérlés-eseményeket ÉS később a hangot is
(a `netroom`/Ably csak a szoba-kódot és a kézfogást intézi, mert az lassabb).
Két fél a nyilvános (STUN) + helyi cím-jelöltjeit kicseréli a szobán át, majd
UDP HOLE-PUNCHINGgal (mindkettő hello-t küld a másik jelöltjeire) átlyukasztja
a routereit, és rögzíti az élő utat.

Csomag: [1B típus][payload]. Típus 0 = hello (hole-punch/keepalive, üres),
1 = adat. A payload értelmezése a hívóé (nálunk: 1B al-típus + JSON/PCM). Csak
beépített socket/struct/threading – nincs függőség.
"""
import socket
import threading
import time

from . import stun

_TIP_HELLO = 0
_TIP_ADAT = 1


class P2PHalozat:
    def __init__(self, on_adat=None, on_kesz=None):
        self.on_adat = on_adat          # cb(payload: bytes)
        self.on_kesz = on_kesz          # cb() – amikor a peer ELŐSZÖR rögzül
        self._sock = None
        self._peer = None               # a rögzített élő társ-cím (ip, port)
        self._jeloltek = []             # a társ lehetséges címei (punch-cél)
        self._fut = False
        self._closing = False
        self._kesz_jelezve = False
        self._lock = threading.Lock()

    def _peer_rogzit(self, addr):
        """A peer első rögzítése – jelez a felső rétegnek (a lyukfúrás kész)."""
        elso = False
        with self._lock:
            if self._peer is None:
                self._peer = addr
                elso = True
            if elso and not self._kesz_jelezve:
                self._kesz_jelezve = True
        if elso and self.on_kesz:
            try:
                self.on_kesz()
            except Exception:
                pass

    # ------------------------------------------------------------ indítás
    def indit(self, stun_lekeres=True):
        """Bind + (STUN előbb, a fogadó-szál ELŐTT, hogy ne versengjenek a
        socketen), majd a fogadó- és lyukfúró-szál indítása. Visszaadja a saját
        elérési jelölteket, amiket a szobán át elküldünk a társnak."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("", 0))
        jeloltek = self._sajat_jeloltek(stun_lekeres)
        self._sock.setblocking(False)
        self._fut = True
        threading.Thread(target=self._fogado, daemon=True).start()
        threading.Thread(target=self._punch_loop, daemon=True).start()
        return jeloltek

    def _sajat_jeloltek(self, stun_lekeres):
        port = self._sock.getsockname()[1]
        jeloltek = []
        if stun_lekeres:
            try:
                pub = stun.publikus_cim(self._sock)   # a fogadó-szál még NEM fut
                if pub:
                    jeloltek.append([pub[0], pub[1]])
            except Exception:
                pass
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            if local_ip and [local_ip, port] not in jeloltek:
                jeloltek.append([local_ip, port])
        except Exception:
            pass
        jeloltek.append(["127.0.0.1", port])
        return jeloltek

    def tars_jeloltek(self, cimek):
        """A társtól kapott elérési jelöltek – ezekre kezdünk hole-punch hello-t."""
        with self._lock:
            self._jeloltek = [(c[0], int(c[1])) for c in (cimek or [])
                              if c and len(c) >= 2]

    # ------------------------------------------------------------ hurkok
    def _punch_loop(self):
        while self._fut and not self._closing:
            with self._lock:
                celok = list(self._jeloltek)
                peer = self._peer
            # amíg nincs rögzített út: hello minden jelöltre; utána keepalive
            if peer is None:
                for c in celok:
                    self._raw(_TIP_HELLO, b"", c)
                time.sleep(0.4)
            else:
                self._raw(_TIP_HELLO, b"", peer)      # keepalive (NAT-nyitva tart)
                time.sleep(3.0)

    def _fogado(self):
        while self._fut and not self._closing:
            try:
                data, addr = self._sock.recvfrom(65535)
            except (BlockingIOError, socket.timeout, OSError):
                time.sleep(0.008)
                continue
            except Exception:
                time.sleep(0.02)
                continue
            if not data:
                continue
            tip = data[0]
            if tip == _TIP_HELLO:
                self._peer_rogzit(addr)               # rögzítjük az élő utat + jelez
                self._raw(_TIP_HELLO, b"", addr)      # hello-ra hello
            elif tip == _TIP_ADAT:
                self._peer_rogzit(addr)
                if self.on_adat:
                    try:
                        self.on_adat(data[1:])
                    except Exception:
                        pass

    def _raw(self, tip, payload, addr):
        try:
            self._sock.sendto(bytes((tip,)) + payload, addr)
        except OSError:
            pass

    # ------------------------------------------------------------ küldés
    def kuld(self, payload):
        with self._lock:
            peer = self._peer
        if peer is None:
            return False
        self._raw(_TIP_ADAT, payload, peer)
        return True

    def kesz(self):
        with self._lock:
            return self._peer is not None

    def leallit(self):
        self._closing = True
        self._fut = False
        try:
            self._sock.close()
        except Exception:
            pass
