# -*- coding: utf-8 -*-
"""Csevejcenter – valós idejű HANG-ÁTVITEL a helyi hálón (host-modell).

Nulla VPS, nulla fizetés: egy résztvevő a HOST (bindol egy UDP-portot), a
többiek hozzá küldik a mikrofon-kockáikat, a host pedig TOVÁBBÍTJA (nem keveri!)
minden másiknak – így mindenki a SAJÁT gépén keveri térben (`terhang.Kevero`).
A host LAN-címét a szoba Ably-csatornája hirdeti (a `netroom` intézi), tehát a
felhasználónak nem kell IP-t beírnia.

Csomag: [1 bájt névhossz][név utf8][PCM16 mono kocka]. A „hello” (üres PCM) a
jelenlét/cím-tanuláshoz és a tűzfal-leképezés életben tartásához kell.

Csak beépített modulok: socket, threading, struct nélkül. A tényleges hang a
`terhang.TerbeliHang` (sounddevice+numpy). Internetes (NAT-átfúró) változat
később, aiortc-vel – az Core-buildbe tartozik.
"""
import socket
import threading
import time

from .terhang import TerbeliHang, ulesek

_HELLO_KOZ = 2.0        # keepalive/hello küldés köze (mp)
_ALAP_PORT = 47690      # alapértelmezett UDP-port a hang-hosthoz


def lan_ip() -> str:
    """A gép LAN-IP-je (nem 127.0.0.1). UDP-t „connectelünk” egy külső címhez –
    nem küld semmit, csak a kimenő interfészt választja ki."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _csomag(nev: str, pcm: bytes) -> bytes:
    nb = nev.encode("utf-8")[:255]
    return bytes([len(nb)]) + nb + pcm


def _bont(p: bytes):
    if not p:
        return "", b""
    n = p[0]
    return p[1:1 + n].decode("utf-8", "replace"), p[1 + n:]


class HangHalozat:
    """A hang hálózati rétege. Vagy HOST (bind+továbbít), vagy KLIENS (a hosthoz
    küld+fogad). Mindkettő a `TerbeliHang`-ot használja: a saját mikrofon-kockát
    kiküldi, a fogadottakat a térbeli keverőbe teszi."""

    def __init__(self, sajat_nev: str):
        self.nev = sajat_nev
        self.th = TerbeliHang()
        self._sock = None
        self._host = False
        self._host_addr = None          # kliensként: (ip, port)
        self._klienesk: dict = {}       # hostként: addr -> (nev, utolso_ido)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._szalak = []

    def elerheto(self) -> bool:
        return self.th.elerheto()

    # ---- indítás hostként / kliensként --------------------------------
    def host_indit(self, port: int = _ALAP_PORT):
        """HOST: UDP-port bindolása, fogadó- és keepalive-szál, mikrofon-indítás.
        Visszaad: (ip, port). Ha a port foglalt, a következőket is próbálja."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        utolso = None
        for p in range(port, port + 8):
            try:
                s.bind(("", p))
                port = p
                break
            except OSError as e:
                utolso = e
        else:
            raise RuntimeError("Nem sikerült UDP-portot foglalni: %s" % utolso)
        s.setblocking(False)
        self._sock = s
        self._host = True
        self.th.indit(self._host_kimeno)
        self._szal(self._host_fogado)
        return lan_ip(), port

    def kliens_indit(self, host_ip: str, host_port: int):
        """KLIENS: a hosthoz köt, elindítja a mikrofon-küldést, a fogadást és a
        rendszeres hello-t (hogy a host megtanulja a címünket)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", 0))
        s.setblocking(False)
        self._sock = s
        self._host = False
        self._host_addr = (host_ip, int(host_port))
        self.th.indit(self._kliens_kimeno)
        self._szal(self._kliens_fogado)
        self._szal(self._hello_loop)

    # ---- kimenő mikrofon-kockák ---------------------------------------
    def _host_kimeno(self, pcm: bytes):
        # a host saját hangját minden kliensnek továbbítjuk (magának nem)
        self._szor(_csomag(self.nev, pcm))

    def _kliens_kimeno(self, pcm: bytes):
        self._kuld(_csomag(self.nev, pcm), self._host_addr)

    # ---- fogadó ciklusok ----------------------------------------------
    def _host_fogado(self):
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except (BlockingIOError, socket.timeout):
                time.sleep(0.005); continue
            except OSError:
                break
            nev, pcm = _bont(data)
            if not nev:
                continue
            with self._lock:
                self._klienesk[addr] = (nev, time.time())
            if pcm:                          # tényleges hang → keverőbe + továbbítás
                self.th.fogad(nev, pcm)
                self._szor(data, kiveve=addr)

    def _kliens_fogado(self):
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except (BlockingIOError, socket.timeout):
                time.sleep(0.005); continue
            except OSError:
                break
            nev, pcm = _bont(data)
            if nev and pcm:
                self.th.fogad(nev, pcm)

    def _hello_loop(self):
        while not self._stop.wait(_HELLO_KOZ):
            self._kuld(_csomag(self.nev, b""), self._host_addr)   # üres = hello

    # ---- küldés-segédek -----------------------------------------------
    def _kuld(self, data: bytes, addr):
        if addr is None or self._sock is None:
            return
        try:
            self._sock.sendto(data, addr)
        except OSError:
            pass

    def _szor(self, data: bytes, kiveve=None):
        """Hostként: a csomag szétküldése minden ismert kliensnek (kivéve a
        feladót). A régóta néma klienseket kiejtjük."""
        most = time.time()
        with self._lock:
            for addr in list(self._klienesk):
                nev, ido = self._klienesk[addr]
                if most - ido > 15.0:
                    del self._klienesk[addr]
                    self.th.elenged(nev)
                    continue
                if addr != kiveve:
                    self._kuld(data, addr)

    # ---- ülések (térbeli pozíciók) + némítás --------------------------
    def set_resztvevok(self, nevek):
        """A résztvevőkhöz térbeli pozíciók (a sajátot nem halljuk vissza)."""
        masok = [n for n in nevek if n and n != self.nev]
        self.th.set_ulesek(ulesek(masok))

    def nemit(self, ertek: bool):
        self.th.nemit(ertek)

    def _szal(self, cel):
        t = threading.Thread(target=cel, daemon=True)
        t.start()
        self._szalak.append(t)

    def leallit(self):
        self._stop.set()
        try:
            self.th.leallit()
        except Exception:
            pass
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
