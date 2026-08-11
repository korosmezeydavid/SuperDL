# -*- coding: utf-8 -*-
"""Csevejcenter – valós idejű HANG-ÁTVITEL, HELYI hálón ÉS interneten át.

Host-modell, fizetős szerver NÉLKÜL. Egy résztvevő a HOST (UDP-port), a többiek
hozzá küldik a mikrofon-kockáikat, a host TOVÁBBÍTJA (nem keveri) minden
másiknak → mindenki a SAJÁT gépén kever térben (`terhang.Kevero`).

A felek a szoba Ably-csatornáján kicserélik a VÉGPONT-JELÖLTJEIKET:
  • LAN-cím (ugyanazon a WiFi-n működik, kis késleltetés),
  • PUBLIKUS cím (STUN-nal megtudva, interneten át).
Majd UDP HOLE-PUNCHINGgal (mindketten küldenek a másik jelöltjeire) átlyukasztják
a routereket. „Cone” NAT-nál (a legtöbb otthoni router) ez működik; a ritka
„szimmetrikus” NAT-hoz TURN kellene (későbbi, opcionális).

Csomag: [1B névhossz][név utf8][PCM16 mono]. Üres PCM = hello (hole-punch +
cím-tanulás + keepalive). Csak beépített socket+struct+numpy+sounddevice.
"""
import socket
import threading
import time

from . import stun
from .terhang import TerbeliHang, ulesek

_HELLO_GYORS = 0.4      # hole-punch alatt sűrű hello (mp)
_HELLO_LASSU = 2.0      # utána keepalive (mp)
_GYORS_DB = 30          # ennyi gyors hello után lassul (kb. 12 mp)
_ALAP_PORT = 47690      # a host preferált UDP-portja
_TAG_LEJAR = 15.0       # néma kliens kiejtése (host)


def lan_ip() -> str:
    """A gép LAN-IP-je (nem 127.0.0.1)."""
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
    """A hang hálózati rétege (host vagy kliens). LAN + internet (STUN + hole-
    punch). A saját mikrofon-kockát kiküldi, a fogadottakat a térbeli keverőbe
    teszi. A saját VÉGPONT-JELÖLTJEIT a `cimek` adja (a hívó a szobában hirdeti)."""

    def __init__(self, sajat_nev: str):
        self.nev = sajat_nev
        self.th = TerbeliHang()
        self._sock = None
        self._host = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._punch = set()             # (ip,port) végpontok, amikre hello-t küldünk
        self._klienesk = {}             # HOST: megerősített kliens addr -> (nev, ido)
        self._host_addr = None          # KLIENS: a megerősített host-cím
        self.cimek = []                 # a SAJÁT jelöltjeim [(ip,port),...]
        self._nemitott = set()          # HOST: némított résztvevők (nevek) – nem hallhatók
        self._tiltott = set()           # HOST: kitiltottak (nevek) – hangja teljesen figyelmen kívül

    def elerheto(self) -> bool:
        return self.th.elerheto()

    # ---- bind + STUN --------------------------------------------------
    def _bind_stun(self, port: int) -> list:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        utolso = None
        if port:
            for p in range(port, port + 8):
                try:
                    s.bind(("", p)); port = p; break
                except OSError as e:
                    utolso = e
            else:
                raise RuntimeError("Nem sikerült UDP-portot foglalni: %s" % utolso)
        else:
            s.bind(("", 0))
        helyi_port = s.getsockname()[1]
        jeloltek = [(lan_ip(), helyi_port)]
        pub = None
        try:
            pub = stun.publikus_cim(s)          # a saját socketen (leképezés-tartás)
        except Exception:
            pub = None
        if pub and tuple(pub) not in jeloltek:
            jeloltek.append((pub[0], int(pub[1])))
        s.setblocking(False)
        self._sock = s
        self.cimek = jeloltek
        return jeloltek

    # ---- indítás ------------------------------------------------------
    def host_indit(self, port: int = _ALAP_PORT) -> list:
        cand = self._bind_stun(port)
        self._host = True
        self.th.indit(self._host_kimeno)
        self._szal(self._fogado)
        self._szal(self._punch_loop)
        return cand

    def kliens_indit(self, host_cimek) -> list:
        cand = self._bind_stun(0)
        self._host = False
        self.punch_hozzaad(host_cimek)
        self.th.indit(self._kliens_kimeno)
        self._szal(self._fogado)
        self._szal(self._punch_loop)
        return cand

    def punch_hozzaad(self, cimek):
        """Új végpont-jelöltek, amikre hole-punch hello-t küldünk (a host a
        kliensek jelöltjeit, a kliens a hostét)."""
        with self._lock:
            for c in cimek or []:
                try:
                    self._punch.add((str(c[0]), int(c[1])))
                except Exception:
                    pass

    # ---- kimenő mikrofon ---------------------------------------------
    def _host_kimeno(self, pcm: bytes):
        self._szor(_csomag(self.nev, pcm))          # host hangja minden kliensnek

    def _kliens_kimeno(self, pcm: bytes):
        cs = _csomag(self.nev, pcm)
        if self._host_addr is not None:             # megerősített út
            self._kuld(cs, self._host_addr)
        else:                                       # még punch alatt: minden jelöltre
            with self._lock:
                celok = list(self._punch)
            for a in celok:
                self._kuld(cs, a)

    # ---- fogadó (közös) ----------------------------------------------
    def _fogado(self):
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except (BlockingIOError, socket.timeout):
                time.sleep(0.004); continue
            except OSError:
                break
            nev, pcm = _bont(data)
            if not nev:
                continue
            if self._host:
                with self._lock:
                    tiltott = nev in self._tiltott
                    nemitott = nev in self._nemitott
                if tiltott:
                    continue                        # kitiltott: hangját teljesen figyelmen kívül
                with self._lock:
                    self._klienesk[addr] = (nev, time.time())
                if pcm and not nemitott:            # némítottat NEM halljuk/továbbítjuk
                    self.th.fogad(nev, pcm)
                    self._szor(data, kiveve=addr)   # továbbítás a többi kliensnek
            else:
                if self._host_addr is None:         # az első hosttól jövő csomag rögzíti az utat
                    self._host_addr = addr
                if pcm:
                    self.th.fogad(nev, pcm)

    def _punch_loop(self):
        n = 0
        while not self._stop.wait(_HELLO_GYORS if n < _GYORS_DB else _HELLO_LASSU):
            n += 1
            hello = _csomag(self.nev, b"")
            with self._lock:
                celok = list(self._punch)
            for a in celok:
                self._kuld(hello, a)
            if self._host:                          # a néma klienseket kiejtjük
                self._takarit()

    # ---- küldés-segédek ----------------------------------------------
    def _kuld(self, data: bytes, addr):
        if addr is None or self._sock is None:
            return
        try:
            self._sock.sendto(data, addr)
        except OSError:
            pass

    def _szor(self, data: bytes, kiveve=None):
        with self._lock:
            celok = [a for a in self._klienesk if a != kiveve]
        for a in celok:
            self._kuld(data, a)

    def _takarit(self):
        most = time.time()
        with self._lock:
            for a in list(self._klienesk):
                nev, ido = self._klienesk[a]
                if most - ido > _TAG_LEJAR:
                    del self._klienesk[a]
                    self.th.elenged(nev)

    # ---- ülések + némítás --------------------------------------------
    def set_resztvevok(self, nevek, helyek=None):
        """A térbeli ülések a résztvevőkhöz. Alap: névsor szerinti automatikus
        elrendezés; a `helyek` (ki→pan) a BEJELENTETT saját helyekkel felülírja –
        így mindenki ott hallatszik, ahová maga helyezte magát a térben."""
        masok = [n for n in nevek if n and n != self.nev]
        pan_map = ulesek(masok)
        if helyek:
            for n, p in helyek.items():
                if n in pan_map:
                    try:
                        pan_map[n] = max(-1.0, min(1.0, float(p)))
                    except Exception:
                        pass
        self.th.set_ulesek(pan_map)

    # ---- admin (csak a HOST-nál van értelme) -------------------------
    def is_host(self) -> bool:
        return self._host

    def nemit_tag(self, nev: str, ertek: bool):
        """Hostként: egy résztvevő némítása/feloldása – némítva a hangját senki
        nem hallja (a host nem továbbítja)."""
        with self._lock:
            if ertek:
                self._nemitott.add(nev)
            else:
                self._nemitott.discard(nev)

    def nemitott_e(self, nev: str) -> bool:
        with self._lock:
            return nev in self._nemitott

    def tilt_tag(self, nev: str):
        """Hostként: egy résztvevő kitiltása – a hangját teljesen figyelmen kívül
        hagyjuk, és kidobjuk a kapcsolatból (a szoba-jelzés külön szól neki)."""
        with self._lock:
            self._tiltott.add(nev)
            for a in [addr for addr, (n, _) in self._klienesk.items() if n == nev]:
                del self._klienesk[a]
        self.th.elenged(nev)

    def felold_tilt(self, nev: str):
        with self._lock:
            self._tiltott.discard(nev)

    def nemit(self, ertek: bool):
        self.th.nemit(ertek)

    def _szal(self, cel):
        threading.Thread(target=cel, daemon=True).start()

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
