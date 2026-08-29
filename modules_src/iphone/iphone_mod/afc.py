# -*- coding: utf-8 -*-
"""iPhone-kapcsolat: usbmux + lockdown + AFC – KIZÁRÓLAG a Python beépített
könyvtáraival (socket, ssl, plistlib, struct).

MIÉRT ÍRJUK MEG MAGUNK? Létezik kész könyvtár (pymobiledevice3), de az több
mint negyven csomagot húz magával, köztük C-fordítást igénylőket – egy modul
nem hozhat ekkora terhet, és a SuperDL magjában sincs meg hozzá minden. Az itt
használt három protokoll viszont egyszerű és stabil, így saját, függőség nélküli
megvalósítást kap. Semmit nem törünk fel: a telefon SAJÁT párosítási rekordját
használjuk, amit a felhasználó a „Megbízom ebben a gépben” gombbal engedélyezett.

A rétegek:
  usbmux    – az Apple háttérszolgáltatása a 127.0.0.1:27015 porton; ez adja a
              csatlakoztatott készülékek listáját és nyit csatornát a telefon
              egy portjára. (A Windowsra telepített Apple Devices vagy iTunes
              hozza magával; nélküle nincs kapcsolat.)
  lockdown  – a telefon „recepciója” a 62078-as porton: azonosítás a párosítási
              rekorddal, TLS-re váltás, majd szolgáltatás indítása.
  AFC       – Apple File Conduit: a fájlműveletek (listázás, olvasás, írás,
              törlés) egyszerű bináris protokollja.
"""
from __future__ import annotations

import plistlib
import socket
import ssl
import struct
import tempfile
import threading
import os

USBMUX_PORT = 27015
LOCKDOWN_PORT = 62078

# ---- AFC műveletkódok (a protokoll állandói) -----------------------------
OP_STATUS = 0x01
OP_DATA = 0x02
OP_READ_DIR = 0x03
OP_REMOVE_PATH = 0x08
OP_MAKE_DIR = 0x09
OP_GET_FILE_INFO = 0x0A
OP_FILE_OPEN = 0x0D
OP_FILE_OPEN_RES = 0x0E
OP_FILE_READ = 0x0F
OP_FILE_WRITE = 0x10
OP_FILE_CLOSE = 0x14
OP_REMOVE_PATH_AND_CONTENTS = 0x22

MODE_READ = 1
MODE_WRITE = 3          # létrehoz / csonkol

_AFC_MAGIC = b"CFA6LPAA"
_AFC_FEJ = struct.Struct("<8sQQQQ")     # magic, teljes hossz, ez a hossz, sorszám, művelet


class IPhoneHiba(Exception):
    """Minden itteni hiba ezt kapja, hogy a felület egységesen kezelhesse."""


class NincsSzolgaltatas(IPhoneHiba):
    """Nem fut az Apple háttérszolgáltatása (nincs telepítve az Apple Devices)."""


class NincsKeszulek(IPhoneHiba):
    """Nincs csatlakoztatott (vagy nincs megbízhatónak jelölt) telefon."""


class Megszakitva(IPhoneHiba):
    """A felhasználó állította le a műveletet – ez nem hiba, csak vége."""


# =====================================================================
#  usbmux
# =====================================================================

def _usbmux_kapcsolat():
    try:
        s = socket.create_connection(("127.0.0.1", USBMUX_PORT), timeout=15)
    except OSError as ex:
        raise NincsSzolgaltatas(
            "Nem érem el az Apple eszköz-szolgáltatását. Telepítsd a Microsoft "
            "Store-ból az „Apple Devices” alkalmazást (vagy az iTunes-t), "
            "indítsd el egyszer, és dugd be a telefont.") from ex
    s.settimeout(30)
    return s


def _usbmux_kuld(s, uzenet: dict, tag: int = 1):
    adat = plistlib.dumps(uzenet)
    s.sendall(struct.pack("<IIII", 16 + len(adat), 1, 8, tag) + adat)


def _pontosan(s, n: int) -> bytes:
    ki = b""
    while len(ki) < n:
        d = s.recv(n - len(ki))
        if not d:
            raise IPhoneHiba("A kapcsolat idő előtt megszakadt.")
        ki += d
    return ki


def _usbmux_valasz(s) -> dict:
    hossz = struct.unpack("<I", _pontosan(s, 4))[0]
    if hossz < 16:
        raise IPhoneHiba("Értelmezhetetlen válasz az eszköz-szolgáltatástól.")
    _pontosan(s, 12)                      # verzió, üzenettípus, tag – nem kell
    return plistlib.loads(_pontosan(s, hossz - 16))


def keszulekek() -> list:
    """A csatlakoztatott iPhone-ok/iPadek listája: [{'id', 'udid'}, …]."""
    s = _usbmux_kapcsolat()
    try:
        _usbmux_kuld(s, {"MessageType": "ListDevices",
                         "ClientVersionString": "SuperDL",
                         "ProgName": "SuperDL"})
        v = _usbmux_valasz(s)
        ki = []
        for d in v.get("DeviceList", []):
            tul = d.get("Properties", {})
            ki.append({"id": tul.get("DeviceID"),
                       "udid": tul.get("SerialNumber", ""),
                       "kapcsolat": tul.get("ConnectionType", "")})
        return ki
    finally:
        s.close()


def _parositasi_rekord(udid: str) -> dict:
    """A telefon párosítási rekordja – EZT hozta létre a „Megbízom ebben a
    gépben” gomb. Nem mi állítjuk elő és nem kerülöket meg semmit."""
    s = _usbmux_kapcsolat()
    try:
        _usbmux_kuld(s, {"MessageType": "ReadPairRecord",
                         "PairRecordID": udid,
                         "ClientVersionString": "SuperDL",
                         "ProgName": "SuperDL"})
        v = _usbmux_valasz(s)
        adat = v.get("PairRecordData")
        if not adat:
            raise NincsKeszulek(
                "Ez a telefon még nincs párosítva ezzel a géppel. Dugd be, és a "
                "telefonon nyomd meg a „Megbízom ebben a gépben” gombot.")
        return plistlib.loads(adat)
    finally:
        s.close()


def _csatorna(device_id: int, port: int):
    """Nyers csatorna a telefon egy portjára (az usbmuxon keresztül)."""
    s = _usbmux_kapcsolat()
    _usbmux_kuld(s, {"MessageType": "Connect", "DeviceID": device_id,
                     "PortNumber": socket.htons(port),
                     "ClientVersionString": "SuperDL", "ProgName": "SuperDL"})
    v = _usbmux_valasz(s)
    if v.get("Number") != 0:
        s.close()
        raise IPhoneHiba("A telefon %d-es portja nem nyílt meg (kód: %s)."
                         % (port, v.get("Number")))
    return s


# =====================================================================
#  lockdown
# =====================================================================

class Lockdown:
    """A telefon „recepciója”: azonosítás, majd szolgáltatás indítása."""

    def __init__(self, keszulek: dict):
        self.id = keszulek["id"]
        self.udid = keszulek["udid"]
        self.rekord = _parositasi_rekord(self.udid)
        self._s = _csatorna(self.id, LOCKDOWN_PORT)
        self._ideiglenes = []
        self.ertekek = {}
        # EGY kapcsolat, több szál: a felület párhuzamosan tölti a lapokat, és
        # két egyszerre küldött kérés összegabalyodna a vonalon (a TLS ilyenkor
        # „wrong version number”-rel áll meg). Ezért minden kérdés-felelet pár
        # oszthatatlan.
        self._zar = threading.RLock()
        self._inditas()

    # ---- alacsony szint ----
    def _kuld(self, uzenet: dict) -> dict:
        adat = plistlib.dumps(uzenet)
        with self._zar:
            self._s.sendall(struct.pack(">I", len(adat)) + adat)
            hossz = struct.unpack(">I", _pontosan(self._s, 4))[0]
            return plistlib.loads(_pontosan(self._s, hossz))

    def _inditas(self):
        v = self._kuld({"Request": "QueryType", "Label": "SuperDL"})
        if v.get("Type") != "com.apple.mobile.lockdown":
            raise IPhoneHiba("A telefon nem a várt módon válaszolt.")
        v = self._kuld({"Request": "StartSession", "Label": "SuperDL",
                        "HostID": self.rekord.get("HostID"),
                        "SystemBUID": self.rekord.get("SystemBUID")})
        if "Error" in v:
            raise NincsKeszulek(
                "A telefon nem fogadta el ezt a gépet (%s). Dugd be újra, és "
                "nyomd meg a „Megbízom ebben a gépben” gombot." % v["Error"])
        self.session = v.get("SessionID")
        if v.get("EnableSessionSSL"):
            self._s = self._tls(self._s)
        self.ertekek = self._kuld({"Request": "GetValue",
                                   "Label": "SuperDL"}).get("Value", {}) or {}

    def _tls(self, s):
        """TLS a telefon SAJÁT tanúsítványaival (a párosítási rekordból)."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # a telefon régi típusú kulcsot használ; enélkül az OpenSSL elutasítja
        try:
            ctx.set_ciphers("ALL:@SECLEVEL=0")
        except ssl.SSLError:
            pass
        cert = self._fajlba(self.rekord["HostCertificate"], ".crt")
        kulcs = self._fajlba(self.rekord["HostPrivateKey"], ".key")
        ctx.load_cert_chain(cert, kulcs)
        return ctx.wrap_socket(s)

    def _fajlba(self, adat, kiterjesztes) -> str:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=kiterjesztes)
        f.write(adat if isinstance(adat, bytes) else adat.encode())
        f.close()
        self._ideiglenes.append(f.name)
        return f.name

    # ---- szolgáltatás ----
    def szolgaltatas(self, nev: str):
        """Elindít egy szolgáltatást, és visszaadja a hozzá nyitott csatornát.

        A zár a TELJES műveletre szól: a szolgáltatás-indítás és a hozzá tartozó
        csatorna-nyitás egybe tartozik."""
        with self._zar:
            return self._szolgaltatas(nev)

    def _szolgaltatas(self, nev: str):
        v = self._kuld({"Request": "StartService", "Service": nev,
                        "Label": "SuperDL"})
        if "Error" in v:
            raise IPhoneHiba("A(z) %s szolgáltatás nem indult el (%s)."
                             % (nev, v["Error"]))
        s = _csatorna(self.id, v["Port"])
        if v.get("EnableServiceSSL"):
            s = self._tls(s)
        return s

    def bezar(self):
        try:
            self._s.close()
        except Exception:
            pass
        for f in self._ideiglenes:
            try:
                os.remove(f)                 # a tanúsítvány ne maradjon a lemezen
            except OSError:
                pass
        self._ideiglenes = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.bezar()


# =====================================================================
#  AFC – fájlműveletek
# =====================================================================

class Afc:
    """Fájlműveletek a telefonon. Minden út a szolgáltatás gyökeréhez képest
    értendő (a média-partíció, illetve alkalmazás-mappa esetén annak gyökere)."""

    def __init__(self, sock):
        self._s = sock
        self._szam = 0
        self._zar = threading.RLock()      # lásd a Lockdown megjegyzését

    # ---- protokoll ----
    def _kerdez(self, muvelet: int, fejadat: bytes, adat: bytes = b"") -> tuple:
        with self._zar:
            return self._kerdez_zar_alatt(muvelet, fejadat, adat)

    def _kerdez_zar_alatt(self, muvelet: int, fejadat: bytes,
                          adat: bytes = b"") -> tuple:
        ez = _AFC_FEJ.size + len(fejadat)
        teljes = ez + len(adat)
        self._s.sendall(_AFC_FEJ.pack(_AFC_MAGIC, teljes, ez, self._szam,
                                      muvelet) + fejadat + adat)
        self._szam += 1
        fej = _pontosan(self._s, _AFC_FEJ.size)
        magic, teljes, ez, _sorszam, op = _AFC_FEJ.unpack(fej)
        if magic != _AFC_MAGIC:
            raise IPhoneHiba("Sérült válasz a telefontól.")
        test = _pontosan(self._s, teljes - _AFC_FEJ.size) if teljes > _AFC_FEJ.size else b""
        if op == OP_STATUS:
            kod = struct.unpack("<Q", test[:8])[0] if len(test) >= 8 else 0
            if kod != 0:
                raise IPhoneHiba(_STATUSZ.get(kod, "hiba (kód: %d)" % kod))
        return op, test

    @staticmethod
    def _ut(ut: str) -> bytes:
        if not ut.startswith("/"):
            ut = "/" + ut
        return ut.encode("utf-8") + b"\x00"

    # ---- műveletek ----
    def listaz(self, ut: str) -> list:
        _op, t = self._kerdez(OP_READ_DIR, self._ut(ut))
        nevek = [n.decode("utf-8", "replace") for n in t.split(b"\x00") if n]
        return [n for n in nevek if n not in (".", "..")]

    def adatok(self, ut: str) -> dict:
        _op, t = self._kerdez(OP_GET_FILE_INFO, self._ut(ut))
        r = [n.decode("utf-8", "replace") for n in t.split(b"\x00") if n]
        return dict(zip(r[::2], r[1::2]))

    def letezik(self, ut: str) -> bool:
        try:
            self.adatok(ut)
            return True
        except IPhoneHiba:
            return False

    def meret(self, ut: str) -> int:
        return int(self.adatok(ut).get("st_size", 0))

    def mappa_e(self, ut: str) -> bool:
        return self.adatok(ut).get("st_ifmt") == "S_IFDIR"

    def _megnyit(self, ut: str, mod: int) -> int:
        op, t = self._kerdez(OP_FILE_OPEN, struct.pack("<Q", mod) + self._ut(ut))
        if op != OP_FILE_OPEN_RES:
            raise IPhoneHiba("A fájl nem nyílt meg: " + ut)
        return struct.unpack("<Q", t[:8])[0]

    def _bezar(self, fogantyu: int):
        self._kerdez(OP_FILE_CLOSE, struct.pack("<Q", fogantyu))

    def olvas(self, ut: str, on_progress=None, darab: int = 1 << 20) -> bytes:
        """Egy fájl teljes tartalma. `on_progress(kesz, teljes)` ha kell."""
        teljes = self.meret(ut)
        f = self._megnyit(ut, MODE_READ)
        try:
            ki = bytearray()
            while len(ki) < teljes:
                kell = min(darab, teljes - len(ki))
                _op, t = self._kerdez(OP_FILE_READ,
                                      struct.pack("<QQ", f, kell))
                if not t:
                    break
                ki += t
                if on_progress:
                    on_progress(len(ki), teljes)
            return bytes(ki)
        finally:
            self._bezar(f)

    def letolt(self, ut: str, cel_fajl: str, on_progress=None,
               darab: int = 1 << 20, megszakit=None) -> int:
        """Letöltés EGYENESEN fájlba – nagy fájlnál nem eszi meg a memóriát.

        `on_progress(kesz, teljes)` a FÁJLON BELÜLI haladás (egy 800 MB-os videó
        percekig tart, addig a felhasználó ne higgye, hogy lefagyott).
        `megszakit()` – ha igazat ad, a letöltés abbamarad, és a félkész fájlt
        eltakarítjuk, nehogy csonka fájl maradjon a lemezen."""
        teljes = self.meret(ut)
        f = self._megnyit(ut, MODE_READ)
        kesz = 0
        felbeszakadt = False
        try:
            with open(cel_fajl, "wb") as ki:
                while kesz < teljes:
                    if megszakit is not None and megszakit():
                        felbeszakadt = True
                        break
                    kell = min(darab, teljes - kesz)
                    _op, t = self._kerdez(OP_FILE_READ,
                                          struct.pack("<QQ", f, kell))
                    if not t:
                        break
                    ki.write(t)
                    kesz += len(t)
                    if on_progress:
                        on_progress(kesz, teljes)
            if felbeszakadt:
                try:
                    os.remove(cel_fajl)          # csonka fájl ne maradjon
                except OSError:
                    pass
                raise Megszakitva("A művelet megszakítva.")
            return kesz
        finally:
            self._bezar(f)

    def ir(self, ut: str, adat: bytes, darab: int = 1 << 20):
        f = self._megnyit(ut, MODE_WRITE)
        try:
            for i in range(0, len(adat), darab):
                self._kerdez(OP_FILE_WRITE, struct.pack("<Q", f),
                             adat[i:i + darab])
            if not adat:
                self._kerdez(OP_FILE_WRITE, struct.pack("<Q", f), b"")
        finally:
            self._bezar(f)

    def torol(self, ut: str):
        self._kerdez(OP_REMOVE_PATH, self._ut(ut))

    def torol_mindent(self, ut: str):
        """Mappa a tartalmával együtt."""
        self._kerdez(OP_REMOVE_PATH_AND_CONTENTS, self._ut(ut))

    def mappat_keszit(self, ut: str):
        self._kerdez(OP_MAKE_DIR, self._ut(ut))

    def bezar(self):
        try:
            self._s.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.bezar()


# =====================================================================
#  Alkalmazások: lista és a saját mappájuk
# =====================================================================

def _plist_kuld(s, uzenet: dict) -> dict:
    adat = plistlib.dumps(uzenet)
    s.sendall(struct.pack(">I", len(adat)) + adat)
    hossz = struct.unpack(">I", _pontosan(s, 4))[0]
    return plistlib.loads(_pontosan(s, hossz))


def alkalmazasok(ld: "Lockdown") -> list:
    """A felhasználó telepített alkalmazásai. Csak azok érdekesek, amelyek
    ENGEDIK a fájlmegosztást (`UIFileSharingEnabled`) – az Apple saját appjai
    (pl. a gyári Hangjegyzetek) zártak, azokba nem lehet belenézni."""
    s = ld.szolgaltatas("com.apple.mobile.installation_proxy")
    try:
        adat = plistlib.dumps({
            "Command": "Browse",
            "ClientOptions": {
                "ApplicationType": "User",
                "ReturnAttributes": ["CFBundleIdentifier", "CFBundleDisplayName",
                                     "CFBundleName", "UIFileSharingEnabled"]},
        })
        s.sendall(struct.pack(">I", len(adat)) + adat)
        ki = []
        while True:
            hossz = struct.unpack(">I", _pontosan(s, 4))[0]
            v = plistlib.loads(_pontosan(s, hossz))
            for a in v.get("CurrentList", []) or []:
                if not a.get("UIFileSharingEnabled"):
                    continue
                ki.append({
                    "bundle": a.get("CFBundleIdentifier", ""),
                    "nev": (a.get("CFBundleDisplayName")
                            or a.get("CFBundleName")
                            or a.get("CFBundleIdentifier", "")),
                })
            if v.get("Status") == "Complete" or "Error" in v:
                break
        ki.sort(key=lambda x: x["nev"].lower())
        return ki
    finally:
        try:
            s.close()
        except Exception:
            pass


def alkalmazas_mappaja(ld: "Lockdown", bundle: str) -> "Afc":
    """Egy alkalmazás megosztott mappája (a Fájlok appban is ez látszik)."""
    s = ld.szolgaltatas("com.apple.mobile.house_arrest")
    v = _plist_kuld(s, {"Command": "VendDocuments", "Identifier": bundle})
    if v.get("Error"):
        try:
            s.close()
        except Exception:
            pass
        raise IPhoneHiba("Ez az alkalmazás nem osztja meg a fájljait (%s)."
                         % v.get("Error"))
    return Afc(s)                       # innentől a csatorna AFC-ként beszél


_STATUSZ = {
    1: "hiba a művelet közben",
    2: "nincs ilyen fájl vagy mappa",
    3: "nincs jogosultság ehhez a művelethez",
    4: "a szolgáltatás nincs csatlakoztatva",
    5: "a művelet időtúllépés miatt megszakadt",
    7: "érvénytelen művelet",
    8: "a művelet nem támogatott",
    9: "az objektum már létezik",
    10: "nincs ilyen fájl vagy mappa",
    17: "a mappa nem üres",
}
