# -*- coding: utf-8 -*-
"""INTERNET-TESZT – a kapcsolat profi felmérése egy gombnyomásra.

Miért a MAGBAN van (és nem modulként)? Mert épp AKKOR kell működnie, amikor
valami NEM megy: nem tölt a Modulkezelő, akadozik a rádió, nem indul a
Távsegítség. Ilyenkor nem támaszkodhatunk arra, hogy egy modul betöltődött-e.
A `netcheck` (van-e egyáltalán net) és a `diagnostics` (másolható jelentés) már
a magban van – ez a réteg ezekre épül rá.

Ez a fájl SZÁNDÉKOSAN wx-mentes: csak mér és adatot ad vissza, így egy szálról
is hívható és tesztelhető. A felület a `nettestwin.py`.

MÉRÉSI ŐSZINTESÉG (zéró tolerancia a pontatlanságra):
  • Csak azt írjuk ki, amit tényleg MÉRÜNK. Csomagvesztést pl. NEM mérünk –
    ICMP nélkül nem lehet rendesen –, helyette a sikeres próbák arányát adjuk.
  • A késleltetés TCP-kapcsolatnyitás ideje (nem ICMP-ping), ezt a jelentés is
    kimondja.
  • A jitter az egymást követő minták eltérésének átlaga.

MÉRŐ-VÉGPONT (jogi óvatosság): a Cloudflare NYILVÁNOSAN DOKUMENTÁLT, ingyenes
sebességmérő végpontját használjuk (speed.cloudflare.com). Az Ookla Speedtest
API-ja NEM szabadon használható, a népszerű `speedtest-cli` nem hivatalos
végpontokat szólít meg – ezért azt tudatosan KERÜLJÜK. A végpont a
beállításokban felülírható.

ADATVÉDELEM: a publikus IP-t a hívó alapból MASZKOLVA jeleníti meg
(`maszkol_ip`), mert élő adás vagy Távsegítség közben fel is olvasódna. Semmit
nem küldünk el sehová a mérésen kívül; a napló a saját gépen marad.
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import statistics
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- végpontok

CF_DOWN = "https://speed.cloudflare.com/__down?bytes=%d"
CF_UP = "https://speed.cloudflare.com/__up"
CF_TRACE = "https://www.cloudflare.com/cdn-cgi/trace"
IPINFO = "https://ipinfo.io/json"        # szolgáltató-név, város – kulcs nélkül

# LETÖLTÉSI MÉRŐ-FORRÁSOK, sorrendben. Azért TÖBB, mert élesben kiderült: egy
# kiszolgáló időnként visszafogja a nem böngésző klienst, és akkor a mérés a
# valódi sebesség töredékét mutatná. A `%d` helyére a kért bájtszám kerül; a
# fix fájlok (GitHub) `%d` nélküliek. A felhasználó saját URL-t is megadhat.
LE_FORRASOK = (
    CF_DOWN,
    "https://github.com/korosmezeydavid/SuperDL/releases/download/"
    "v4.3.0/SuperDL.exe",                        # a saját kiadásunk, ~35 MB
    "https://proof.ovh.net/files/100Mb.dat",     # nyilvános mérőfájl
)

_FEJ = {"User-Agent": "SuperDL-nettest/1.0", "Cache-Control": "no-cache",
        "Pragma": "no-cache"}

# A SuperDL SAJÁT szolgáltatásai – ettől több ez egy sima sebességmérőnél:
# kiderül, hogy „nem az internet a baj, hanem épp a GitHub nem érhető el".
_ALAP_SZOLGALTATASOK = (
    ("Modulok és frissítés (GitHub)", "github.com", 443),
    ("Modul-letöltés (GitHub tárhely)", "objects.githubusercontent.com", 443),
    ("YouTube (letöltés, keresés)", "www.youtube.com", 443),
    ("Online játékok (Ably)", "rest.ably.io", 443),
    ("P2P kódszerver (wormhole)", "relay.magic-wormhole.io", 4000),
    ("P2P átjátszó (wormhole transit)", "transit.magic-wormhole.io", 4001),
    ("TV műsor (műsorújság-forrás)", "epgshare01.online", 443),
    ("Névfeloldás (DNS-kiszolgáló)", "1.1.1.1", 53),
)


def _wormhole_szerverek() -> list:
    """A wormhole-szervereket MAGÁTÓL A CSOMAGTÓL kérdezzük meg, ha lehet – így
    a lista akkor sem megy tévútra, ha a projekt később szervert vált (egy rossz
    porton mért „NEM érhető el" hamis riasztás lenne)."""
    ki = []
    try:
        from wormhole.cli import public_relay as pr
        for cimke, url in (("P2P kódszerver (wormhole)", pr.RENDEZVOUS_RELAY),
                           ("P2P átjátszó (wormhole transit)", pr.TRANSIT_RELAY)):
            resz = str(url).replace("tcp:", "").replace("ws://", "") \
                           .replace("wss://", "").split("/")[0]
            host, _, port = resz.partition(":")
            if host and port.isdigit():
                ki.append((cimke, host, int(port)))
    except Exception:
        pass
    return ki


def szolgaltatas_lista() -> tuple:
    dinamikus = {c: (c, h, p) for c, h, p in _wormhole_szerverek()}
    return tuple(dinamikus.get(c, (c, h, p)) for c, h, p in _ALAP_SZOLGALTATASOK)


SZOLGALTATASOK = szolgaltatas_lista()

# mérési idők és felső adatkorlátok
_MB = 1024 * 1024
_LE_IDO, _FEL_IDO = 7.0, 6.0             # éles mérés hossza (másodperc)
_LE_SZAL, _FEL_SZAL = 4, 3               # párhuzamos kapcsolatok
_LE_KORLAT, _FEL_KORLAT = 300 * _MB, 120 * _MB     # ennél többet sosem viszünk át
_TAK_LE_IDO, _TAK_FEL_IDO = 2.5, 2.0     # takarékos mérés
_TAK_LE_KORLAT, _TAK_FEL_KORLAT = 6 * _MB, 3 * _MB

_NAPLO_MAX = 200                 # ennyi korábbi mérést őrzünk meg


def _naplo_fajl() -> Path:
    return Path.home() / ".superdl" / "nettest_naplo.json"


# ------------------------------------------------------------------ adatok

@dataclass
class Sebesseg:
    le_mbps: float = 0.0
    fel_mbps: float = 0.0
    le_csucs_mbps: float = 0.0
    fel_csucs_mbps: float = 0.0
    le_mintak: list = field(default_factory=list)
    fel_mintak: list = field(default_factory=list)
    keses_ms: float = 0.0          # legkisebb TCP-válaszidő
    keses_atlag_ms: float = 0.0
    ingadozas_ms: float = 0.0      # jitter
    sikeres_probak: float = 0.0    # százalék
    dns_ms: float = 0.0
    le_bajt: int = 0
    fel_bajt: int = 0


@dataclass
class Halozat:
    helyi_ip: str = ""
    atjaro: str = ""
    dns_kiszolgalok: list = field(default_factory=list)
    kapcsolat: str = ""            # „vezeték nélküli (Wi-Fi)" / „vezetékes"…
    adapter: str = ""
    link_mbps: float = 0.0         # a hálókártya sávszélessége
    mtu: int = 0
    ipv6: bool = False
    wifi_halozat: str = ""
    wifi_jel: int = 0              # 0–100
    wifi_dbm: int = 0              # valódi jelerősség (dBm) – mesh-hez
    wifi_dbm_mert: bool = False    # True: mért; False: százalékból számolt
    wifi_sav: str = ""             # „2,4 GHz" / „5 GHz" / „6 GHz"
    wifi_csatorna: int = 0
    wifi_le_mbps: float = 0.0
    wifi_fel_mbps: float = 0.0
    vpn: str = ""                  # a talált VPN-adapter neve, ha van
    merten_gyanu: bool = False     # korlátozott (mobil/mért) kapcsolat gyanúja


@dataclass
class Publikus:
    ip: str = ""
    host: str = ""                 # fordított DNS
    szolgaltato: str = ""          # ASN-szervezet
    asn: str = ""
    varos: str = ""
    orszag: str = ""
    kiszolgalo: str = ""           # melyik mérő-központ szolgált ki (colo)


@dataclass
class Eredmeny:
    ido: str = ""
    mod: str = "teljes"
    sebesseg: Sebesseg = field(default_factory=Sebesseg)
    halozat: Halozat = field(default_factory=Halozat)
    publikus: Publikus = field(default_factory=Publikus)
    szolgaltatasok: list = field(default_factory=list)   # (név, ok, ms)
    hibak: list = field(default_factory=list)
    megszakitva: bool = False


# -------------------------------------------------------------- segédek

def maszkol_ip(ip: str) -> str:
    """A publikus IP MASZKOLT alakja – ez a MEGJELENÍTÉS alapértelmezése.
    IPv4: 84.2.xxx.xxx, IPv6: az első két csoport marad."""
    ip = (ip or "").strip()
    if not ip:
        return ""
    if ":" in ip:
        r = ip.split(":")
        return ":".join(r[:2]) + ":xxxx:xxxx" if len(r) > 2 else ip
    r = ip.split(".")
    if len(r) == 4:
        return "%s.%s.xxx.xxx" % (r[0], r[1])
    return ip


def _mbps(bajt: int, masodperc: float) -> float:
    if masodperc <= 0:
        return 0.0
    return round(bajt * 8 / masodperc / 1_000_000, 2)


def ido_szoveg(masodperc: float) -> str:
    """Emberi időtartam – „kb. 3 perc 20 másodperc"."""
    masodperc = max(0.0, float(masodperc))
    if masodperc < 60:
        return "%d másodperc" % round(masodperc)
    perc, mp = divmod(int(round(masodperc)), 60)
    if perc < 60:
        return "%d perc %d másodperc" % (perc, mp) if mp else "%d perc" % perc
    ora, perc = divmod(perc, 60)
    return "%d óra %d perc" % (ora, perc)


def egy_giga_ideje(mbps: float) -> str:
    """Mennyi ideig tart 1 GB ezen a sebességen? Ez a legkézzelfoghatóbb szám."""
    if mbps <= 0:
        return "nem mérhető"
    return ido_szoveg(1024 * 8 / mbps)


def becsult_forgalom(mod: str) -> str:
    """MENNYI ADATOT HASZNÁL a mérés – mobilneten ez pénz, ezért előre szólunk."""
    if mod == "takarekos":
        return "kb. 5 megabájt"
    if mod == "gyors":
        return "elhanyagolható (néhány kilobájt)"
    return "kb. 20–250 megabájt (a sebességedtől függ)"


# ---------------------------------------------------- helyi hálózat (ctypes)

_AF_INET, _AF_INET6 = 2, 23
_IF_ETHERNET, _IF_WIFI, _IF_TUNNEL = 6, 71, 131
_IF_WWANPP, _IF_WWANPP2 = 243, 244      # mobilnet (SIM)

_VPN_KULCSSZAVAK = ("vpn", "openvpn", "wireguard", "wintun", "tap-windows",
                    "tapwindows", "proton", "nordlynx", "expressvpn",
                    "surfshark", "anyconnect", "tailscale", "zerotier",
                    "mullvad", "hamachi", "softether")


class _SOCKADDR(ctypes.Structure):
    _fields_ = [("sa_family", ctypes.c_ushort), ("sa_data", ctypes.c_ubyte * 26)]


class _SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.POINTER(_SOCKADDR)),
                ("iSockaddrLength", ctypes.c_int)]


class _UNICAST(ctypes.Structure):
    pass


_UNICAST._fields_ = [
    ("Length", ctypes.c_ulong), ("Flags", ctypes.c_ulong),
    ("Next", ctypes.POINTER(_UNICAST)), ("Address", _SOCKET_ADDRESS),
    ("PrefixOrigin", ctypes.c_int), ("SuffixOrigin", ctypes.c_int),
    ("DadState", ctypes.c_int), ("ValidLifetime", ctypes.c_ulong),
    ("PreferredLifetime", ctypes.c_ulong), ("LeaseLifetime", ctypes.c_ulong),
    ("OnLinkPrefixLength", ctypes.c_ubyte)]


class _CIMLANC(ctypes.Structure):
    """DNS-kiszolgáló és átjáró – mindkettő ugyanaz a forma."""
    pass


_CIMLANC._fields_ = [
    ("Length", ctypes.c_ulong), ("Reserved", ctypes.c_ulong),
    ("Next", ctypes.POINTER(_CIMLANC)), ("Address", _SOCKET_ADDRESS)]


class _ADAPTER(ctypes.Structure):
    pass


_ADAPTER._fields_ = [
    ("Length", ctypes.c_ulong), ("IfIndex", ctypes.c_ulong),
    ("Next", ctypes.POINTER(_ADAPTER)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.POINTER(_UNICAST)),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.POINTER(_CIMLANC)),
    ("DnsSuffix", ctypes.c_wchar_p),
    ("Description", ctypes.c_wchar_p),
    ("FriendlyName", ctypes.c_wchar_p),
    ("PhysicalAddress", ctypes.c_ubyte * 8),
    ("PhysicalAddressLength", ctypes.c_ulong),
    ("Flags", ctypes.c_ulong),
    ("Mtu", ctypes.c_ulong),
    ("IfType", ctypes.c_ulong),
    ("OperStatus", ctypes.c_int),
    ("Ipv6IfIndex", ctypes.c_ulong),
    ("ZoneIndices", ctypes.c_ulong * 16),
    ("FirstPrefix", ctypes.c_void_p),
    ("TransmitLinkSpeed", ctypes.c_ulonglong),
    ("ReceiveLinkSpeed", ctypes.c_ulonglong),
    ("FirstWinsServerAddress", ctypes.c_void_p),
    ("FirstGatewayAddress", ctypes.POINTER(_CIMLANC))]


def _cim_szoveg(sa: _SOCKET_ADDRESS) -> str:
    """sockaddr → IP-szöveg (nyelvfüggetlen, nincs parancssor-elemzés)."""
    try:
        if not sa.lpSockaddr:
            return ""
        p = sa.lpSockaddr.contents
        nyers = bytes(bytearray(p.sa_data))
        if p.sa_family == _AF_INET:
            return socket.inet_ntop(socket.AF_INET, nyers[2:6])
        if p.sa_family == _AF_INET6:
            return socket.inet_ntop(socket.AF_INET6, nyers[6:22])
    except Exception:
        pass
    return ""


def _lancszemek(elso):
    p = elso
    while p:
        yield p.contents
        p = p.contents.Next


def adapterek() -> list:
    """A hálózati adapterek NYELVFÜGGETLENÜL (GetAdaptersAddresses), nem az
    `ipconfig` magyar/angol kimenetét elemezve – ez utóbbi gépenként más."""
    if os.name != "nt":
        return []
    GAA_INCLUDE_GATEWAYS = 0x0080
    GAA_SKIP_MULTICAST = 0x0004
    GAA_SKIP_ANYCAST = 0x0002
    meret = ctypes.c_ulong(15000)
    puffer = ctypes.create_string_buffer(meret.value)
    r = ctypes.windll.iphlpapi.GetAdaptersAddresses(
        0, GAA_INCLUDE_GATEWAYS | GAA_SKIP_MULTICAST | GAA_SKIP_ANYCAST,
        None, ctypes.byref(puffer), ctypes.byref(meret))
    if r == 111:                      # ERROR_BUFFER_OVERFLOW → újra, nagyobbal
        puffer = ctypes.create_string_buffer(meret.value)
        r = ctypes.windll.iphlpapi.GetAdaptersAddresses(
            0, GAA_INCLUDE_GATEWAYS | GAA_SKIP_MULTICAST | GAA_SKIP_ANYCAST,
            None, ctypes.byref(puffer), ctypes.byref(meret))
    if r != 0:
        return []
    ki = []
    a = ctypes.cast(puffer, ctypes.POINTER(_ADAPTER))
    for ad in _lancszemek(a):
        ipv4, ipv6 = [], []
        for u in _lancszemek(ad.FirstUnicastAddress):
            c = _cim_szoveg(u.Address)
            if not c:
                continue
            (ipv6 if ":" in c else ipv4).append(c)
        ki.append({
            "nev": ad.FriendlyName or "", "leiras": ad.Description or "",
            "tipus": int(ad.IfType), "aktiv": int(ad.OperStatus) == 1,
            "ipv4": ipv4, "ipv6": ipv6,
            "atjaro": [_cim_szoveg(g.Address) for g in
                       _lancszemek(ad.FirstGatewayAddress)],
            "dns": [_cim_szoveg(d.Address) for d in
                    _lancszemek(ad.FirstDnsServerAddress)],
            "mtu": int(ad.Mtu), "le_bps": int(ad.ReceiveLinkSpeed),
            "fel_bps": int(ad.TransmitLinkSpeed)})
    return ki


def _vpn_nev(lista) -> str:
    for ad in lista:
        if not ad["aktiv"] or not (ad["ipv4"] or ad["ipv6"]):
            continue
        szoveg = ("%s %s" % (ad["nev"], ad["leiras"])).lower()
        if ad["tipus"] == _IF_TUNNEL or any(k in szoveg
                                            for k in _VPN_KULCSSZAVAK):
            return ad["nev"] or ad["leiras"]
    return ""


def helyi_ip() -> str:
    """A kifelé menő útvonalhoz tartozó helyi cím. UDP-„kapcsolat" – NEM küld
    egyetlen bájtot sem, csak megkérdezi az operációs rendszer útvonalválasztóját."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1.0)
        s.connect(("1.1.1.1", 53))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


# ------------------------------------------------------------------- Wi-Fi

class _DOT11_SSID(ctypes.Structure):
    _fields_ = [("uSSIDLength", ctypes.c_ulong), ("ucSSID", ctypes.c_ubyte * 32)]


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


class _WLAN_IF(ctypes.Structure):
    _fields_ = [("InterfaceGuid", _GUID),
                ("strInterfaceDescription", ctypes.c_wchar * 256),
                ("isState", ctypes.c_int)]


class _WLAN_IF_LIST(ctypes.Structure):
    _fields_ = [("dwNumberOfItems", ctypes.c_ulong),
                ("dwIndex", ctypes.c_ulong), ("InterfaceInfo", _WLAN_IF * 1)]


class _ASSOC(ctypes.Structure):
    _fields_ = [("dot11Ssid", _DOT11_SSID), ("dot11BssType", ctypes.c_int),
                ("dot11Bssid", ctypes.c_ubyte * 6), ("dot11PhyType", ctypes.c_int),
                ("uDot11PhyIndex", ctypes.c_ulong),
                ("wlanSignalQuality", ctypes.c_ulong),
                ("ulRxRate", ctypes.c_ulong), ("ulTxRate", ctypes.c_ulong)]


class _CONN(ctypes.Structure):
    _fields_ = [("isState", ctypes.c_int), ("wlanConnectionMode", ctypes.c_int),
                ("strProfileName", ctypes.c_wchar * 256),
                ("wlanAssociationAttributes", _ASSOC)]


def _sav_csatornabol(csatorna: int) -> str:
    if not csatorna:
        return ""
    if csatorna <= 14:
        return "2,4 GHz"
    if csatorna <= 177:
        return "5 GHz"
    return "6 GHz"


# A Windows RSSI-lekérdezésének kódja (wlan_intf_opcode_rssi).
_OPCODE_RSSI = 0x10000102


def _rssi(wlan, kezelo, guid):
    """A VALÓDI jelerősség dBm-ben. Visszaad: (dBm, mért-e).

    Ha a rendszer nem adja meg (régebbi illesztőprogram), a hívó a
    jelminőségből becsül – de akkor ezt ki is írjuk, hogy senki ne higgye
    mérésnek."""
    meret = ctypes.c_ulong()
    adat = ctypes.c_void_p()
    try:
        if wlan.WlanQueryInterface(kezelo, ctypes.byref(guid), _OPCODE_RSSI,
                                   None, ctypes.byref(meret),
                                   ctypes.byref(adat), None) != 0:
            return 0, False
    except Exception:
        return 0, False
    try:
        ertek = int(ctypes.cast(adat, ctypes.POINTER(ctypes.c_long)).contents.value)
    except Exception:
        return 0, False
    finally:
        try:
            wlan.WlanFreeMemory(adat)
        except Exception:
            pass
    # épeszű tartomány: a wifi RSSI −100 és −10 dBm közé esik
    return (ertek, True) if -110 <= ertek <= -5 else (0, False)


def dbm_becsles(jel_szazalek: int) -> int:
    """A Windows jelminőség-százalékából dBm. A Microsoft leírása szerint a
    0% = −100 dBm, a 100% = −50 dBm, közte egyenletesen."""
    try:
        j = max(0, min(100, int(jel_szazalek)))
    except (TypeError, ValueError):
        return 0
    return int(round(j / 2.0 - 100))


JEL_FOKOZATOK = (
    (-55, "kiváló", "Itt minden gond nélkül megy a videó és a hívás is."),
    (-65, "jó", "Ez bőven elég mindenre."),
    (-72, "elfogadható", "Böngészésre, levelezésre jó; nagy letöltésnél "
                         "lassulhat."),
    (-80, "gyenge", "Itt már akadozhat a videó és a hívás. Mesh-hálózatnál "
                    "ide érdemes még egy egységet tenni."),
    (-200, "használhatatlan", "Ezen a helyen a kapcsolat gyakorlatilag "
                              "megszakad."),
)


def jel_minosites(dbm: int) -> tuple:
    """(fokozat, magyarázat) – a dBm önmagában semmit nem mond a
    felhasználónak; a szöveges fokozat igen."""
    try:
        d = int(dbm)
    except (TypeError, ValueError):
        return "", ""
    for hatar, nev, magyarazat in JEL_FOKOZATOK:
        if d >= hatar:
            return nev, magyarazat
    return JEL_FOKOZATOK[-1][1], JEL_FOKOZATOK[-1][2]


def jel_szoveg(dbm: int, jel_szazalek: int = 0, mert: bool = True) -> str:
    """Felolvasható mondat a jelerősségről."""
    if not dbm:
        return "A Wi-Fi jelerősségét nem sikerült megállapítani."
    fokozat, magyarazat = jel_minosites(dbm)
    honnan = "" if mert else " (a jelminőségből számolva)"
    resz = ("%d dBm%s – %s" % (dbm, honnan, fokozat))
    if jel_szazalek:
        resz += ", jelminőség %d százalék" % int(jel_szazalek)
    return resz + ". " + magyarazat


def wifi() -> dict:
    """Az AKTÍV Wi-Fi kapcsolat adatai (hálózat neve, jelerősség, sáv, sebesség).
    Vakon ez aranyat ér: a „lassú a net" panaszok jó része valójában gyenge
    vagy 2,4 GHz-es wifi – ezt máshonnan nem lehet megtudni. Hiba esetén {}."""
    if os.name != "nt":
        return {}
    try:
        wlan = ctypes.windll.wlanapi
    except Exception:
        return {}
    kezelo = ctypes.c_void_p()
    valt = ctypes.c_ulong()
    try:
        if wlan.WlanOpenHandle(2, None, ctypes.byref(valt),
                               ctypes.byref(kezelo)) != 0:
            return {}
    except Exception:
        return {}
    try:
        lista = ctypes.POINTER(_WLAN_IF_LIST)()
        if wlan.WlanEnumInterfaces(kezelo, None, ctypes.byref(lista)) != 0:
            return {}
        try:
            if lista.contents.dwNumberOfItems < 1:
                return {}
            io = lista.contents.InterfaceInfo[0]
            if io.isState != 1:               # 1 = wlan_interface_state_connected
                return {}
            guid = io.InterfaceGuid
            meret = ctypes.c_ulong()
            adat = ctypes.c_void_p()
            if wlan.WlanQueryInterface(kezelo, ctypes.byref(guid), 7, None,
                                       ctypes.byref(meret), ctypes.byref(adat),
                                       None) != 0:
                return {}
            try:
                c = ctypes.cast(adat, ctypes.POINTER(_CONN)).contents
                a = c.wlanAssociationAttributes
                nev = bytes(bytearray(a.dot11Ssid.ucSSID)
                            [:a.dot11Ssid.uSSIDLength]).decode("utf-8", "replace")
                ki = {"halozat": nev, "jel": int(a.wlanSignalQuality),
                      "le_mbps": a.ulRxRate / 1000.0,
                      "fel_mbps": a.ulTxRate / 1000.0, "csatorna": 0}
            finally:
                wlan.WlanFreeMemory(adat)
            # VALÓDI jelerősség dBm-ben (mesh-hálózat építéséhez ez az igazi
            # mérőszám, nem a százalék). A százalékból számolt becslés ettől
            # érdemben eltérhet: egy gépen 88% mellett a valódi −49 dBm volt,
            # a képletből −56 jött volna ki. [felhasználói kérés, 2026-08-20]
            ki["dbm"], ki["dbm_mert"] = _rssi(wlan, kezelo, guid)
            if not ki["dbm"]:                    # nincs valódi mérés: becslés
                ki["dbm"] = dbm_becsles(ki["jel"])
            csat = ctypes.c_ulong()
            adat2 = ctypes.c_void_p()
            if wlan.WlanQueryInterface(kezelo, ctypes.byref(guid), 8, None,
                                       ctypes.byref(meret), ctypes.byref(adat2),
                                       None) == 0:
                try:
                    csat = ctypes.cast(adat2, ctypes.POINTER(ctypes.c_ulong))
                    ki["csatorna"] = int(csat.contents.value)
                finally:
                    wlan.WlanFreeMemory(adat2)
            ki["sav"] = _sav_csatornabol(ki["csatorna"])
            return ki
        finally:
            wlan.WlanFreeMemory(lista)
    except Exception:
        return {}
    finally:
        try:
            wlan.WlanCloseHandle(kezelo, None)
        except Exception:
            pass


def merten_gyanu(lista) -> bool:
    """KORLÁTOZOTT (mért) kapcsolat gyanúja – mobilnet vagy a Windowsban mértnek
    jelölt wifi. Ilyenkor a felület RÁKÉRDEZ, mielőtt sok adatot használna."""
    for ad in lista:
        if ad["aktiv"] and ad["tipus"] in (_IF_WWANPP, _IF_WWANPP2) \
                and (ad["ipv4"] or ad["ipv6"]):
            return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
                            r"\NetworkList\DefaultMediaCost") as k:
            # 1 = korlátlan, 2 = fix keret, 4 = változó díjas
            wifi_ar, _ = winreg.QueryValueEx(k, "WiFi")
            if int(wifi_ar) > 1 and any(
                    ad["aktiv"] and ad["tipus"] == _IF_WIFI for ad in lista):
                return True
    except Exception:
        pass
    return False


def halozat_adatok() -> Halozat:
    h = Halozat()
    lista = adapterek()
    h.helyi_ip = helyi_ip()
    aktiv = None
    for ad in lista:
        if ad["aktiv"] and h.helyi_ip and h.helyi_ip in ad["ipv4"]:
            aktiv = ad
            break
    if aktiv is None:
        jelolt = [ad for ad in lista if ad["aktiv"] and ad["atjaro"]
                  and ad["tipus"] in (_IF_ETHERNET, _IF_WIFI)]
        aktiv = jelolt[0] if jelolt else None
    if aktiv:
        h.adapter = aktiv["nev"] or aktiv["leiras"]
        h.atjaro = next((c for c in aktiv["atjaro"] if c), "")
        h.dns_kiszolgalok = [c for c in aktiv["dns"] if c][:4]
        h.mtu = aktiv["mtu"]
        h.link_mbps = round(max(aktiv["le_bps"], aktiv["fel_bps"]) / 1e6, 1)
        h.kapcsolat = {_IF_WIFI: "vezeték nélküli (Wi-Fi)",
                       _IF_ETHERNET: "vezetékes (kábel)",
                       _IF_WWANPP: "mobilnet", _IF_WWANPP2: "mobilnet"}.get(
                           aktiv["tipus"], "egyéb")
        if not h.helyi_ip and aktiv["ipv4"]:
            h.helyi_ip = aktiv["ipv4"][0]
    w = wifi()
    if w:
        h.wifi_halozat = w.get("halozat", "")
        h.wifi_jel = int(w.get("jel", 0))
        h.wifi_dbm = int(w.get("dbm", 0))
        h.wifi_dbm_mert = bool(w.get("dbm_mert", False))
        h.wifi_sav = w.get("sav", "")
        h.wifi_csatorna = int(w.get("csatorna", 0))
        h.wifi_le_mbps = round(w.get("le_mbps", 0.0), 1)
        h.wifi_fel_mbps = round(w.get("fel_mbps", 0.0), 1)
        if not h.kapcsolat:
            h.kapcsolat = "vezeték nélküli (Wi-Fi)"
    h.vpn = _vpn_nev(lista)
    h.merten_gyanu = merten_gyanu(lista)
    h.ipv6 = ipv6_elerheto()
    return h


def ipv6_elerheto(timeout: float = 2.5) -> bool:
    try:
        with socket.create_connection(("2606:4700:4700::1111", 53),
                                      timeout=timeout):
            return True
    except OSError:
        return False


# ------------------------------------------------------------- publikus adat

def _json_le(url: str, timeout: float = 8.0) -> dict:
    keres = urllib.request.Request(url, headers=_FEJ)
    with urllib.request.urlopen(keres, timeout=timeout) as v:
        return json.loads(v.read().decode("utf-8", "replace"))


def _trace(timeout: float = 6.0) -> dict:
    """A Cloudflare `cdn-cgi/trace` végpontja: `kulcs=érték` sorok. Kulcs nélkül,
    dokumentáltan használható; ebből jön a publikus IP, az ország és az, hogy
    melyik mérő-központ szolgál ki minket."""
    keres = urllib.request.Request(CF_TRACE, headers=_FEJ)
    with urllib.request.urlopen(keres, timeout=timeout) as v:
        szoveg = v.read().decode("utf-8", "replace")
    d = {}
    for sor in szoveg.splitlines():
        if "=" in sor:
            k, _, e = sor.partition("=")
            d[k.strip()] = e.strip()
    return d


def publikus_adatok(timeout: float = 8.0) -> Publikus:
    """Publikus IP, ország, mérő-központ (Cloudflare trace), majd – ha elérhető –
    a szolgáltató neve és a durva földrajzi hely (ipinfo.io, kulcs nélkül).
    Mindkettő HIBATŰRŐ: ha nem jön válasz, a mérés többi része megy tovább.
    ADATVÉDELEM: ezek a kiszolgálók a kapcsolatból amúgy is látják az IP-t; mi
    nem küldünk semmilyen egyéb adatot, és a felület maszkolva mutatja."""
    p = Publikus()
    try:
        d = _trace(timeout)
        p.ip = str(d.get("ip") or "")
        p.orszag = str(d.get("loc") or "")
        p.kiszolgalo = str(d.get("colo") or "")
    except Exception:
        pass
    try:
        d = _json_le(IPINFO, timeout)
        p.ip = p.ip or str(d.get("ip") or "")
        p.varos = str(d.get("city") or "")
        p.orszag = str(d.get("country") or p.orszag or "")
        p.host = str(d.get("hostname") or "")
        szerv = str(d.get("org") or "")
        if szerv.startswith("AS"):
            p.asn, _, p.szolgaltato = szerv.partition(" ")
            p.asn = p.asn[2:]
        else:
            p.szolgaltato = szerv
    except Exception:
        pass
    if p.ip and not p.host:
        regi = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(3.0)
            p.host = socket.gethostbyaddr(p.ip)[0]
        except Exception:
            p.host = ""
        finally:
            socket.setdefaulttimeout(regi)
    return p


# ------------------------------------------------------ késleltetés, DNS

def keslekedes(minta: int = 12, stop=None, cel=("1.1.1.1", 443)) -> tuple:
    """TCP-kapcsolatnyitás ideje – ez a „ping" (ICMP nélkül, jogosultság nélkül).
    Visszaad: (legkisebb ms, átlag ms, ingadozás ms, sikeres százalék)."""
    idok = []
    probalt = 0
    for _ in range(max(3, minta)):
        if stop is not None and stop.is_set():
            break
        probalt += 1
        t = time.monotonic()
        try:
            s = socket.create_connection(cel, timeout=3.0)
            idok.append((time.monotonic() - t) * 1000.0)
            s.close()
        except OSError:
            pass
        time.sleep(0.05)
    probalt = max(1, probalt)
    if not idok:
        return 0.0, 0.0, 0.0, 0.0
    elteres = [abs(idok[j] - idok[j - 1]) for j in range(1, len(idok))]
    return (round(min(idok), 1), round(statistics.fmean(idok), 1),
            round(statistics.fmean(elteres), 1) if elteres else 0.0,
            round(len(idok) / probalt * 100, 1))


def dns_ido(hostok=("github.com", "www.youtube.com", "cloudflare.com")) -> float:
    """Névfeloldás ideje (a rendszer gyorsítótára is beleszámít – a jelentés ezt
    ki is mondja, hogy senki ne értse félre)."""
    idok = []
    for h in hostok:
        t = time.monotonic()
        try:
            socket.getaddrinfo(h, 443, proto=socket.IPPROTO_TCP)
            idok.append((time.monotonic() - t) * 1000.0)
        except OSError:
            pass
    return round(statistics.median(idok), 1) if idok else 0.0


# ------------------------------------------------------------ sávszélesség

class _Szamlalo:
    """Bájtszámláló BEMELEGÍTÉS-LEVONÁSSAL.

    Miért kell? Két csapdát kerülünk el vele:
      • A kapcsolatépítés (TCP+TLS) ideje nem sebesség – az órát az ELSŐ BÁJT
        indítja, nem a kérés kiküldése.
      • A TCP „lassú indítás" miatt az első másodperc mindig lassabb a valódi
        sebességnél. Ezt a szakaszt KIHAGYJUK a számításból; a mért érték a
        bemelegítés UTÁNI, egyenletes szakaszra vonatkozik.
    Ha a mérés rövidebb a bemelegítésnél, becsületesen a teljes szakaszt
    számoljuk (jobb egy óvatos szám, mint egy hamis)."""

    def __init__(self, bemelegites: float = 1.0):
        self.zar = threading.Lock()
        self.bemelegites = bemelegites
        self.bajt = 0                 # összes átvitt bájt (a forgalomhoz)
        self._elso = None             # az első bájt ideje
        self._utolso = None
        self._meres_t0 = None         # a bemelegítés utáni mérés kezdete
        self._meres_bajt0 = 0

    def hozzaad(self, n: int) -> None:
        most = time.monotonic()
        with self.zar:
            if self._elso is None:
                self._elso = most
            self.bajt += n
            self._utolso = most
            if self._meres_t0 is None and most - self._elso >= self.bemelegites:
                self._meres_t0 = most
                self._meres_bajt0 = self.bajt

    def eredmeny(self) -> tuple:
        """(Mbit/s, összes bájt) – a Mbit/s a bemelegítés utáni szakaszból."""
        with self.zar:
            if self._elso is None or self._utolso is None:
                return 0.0, 0
            if self._meres_t0 is not None and self._utolso > self._meres_t0:
                return (_mbps(self.bajt - self._meres_bajt0,
                              self._utolso - self._meres_t0), self.bajt)
            if self._utolso > self._elso:
                return _mbps(self.bajt, self._utolso - self._elso), self.bajt
            return 0.0, self.bajt


def _le_szal(darab: int, szamlalo: _Szamlalo, stop, hibak: list,
             hatarido: float, korlat: int, url: str = "") -> None:
    """IDŐALAPÚ letöltés: a határidőig tölt, adagonként új kéréssel. (A fix,
    nagy bájtcél megbízhatatlan volt: a mérő-végpont a túl nagy adagot
    visszafogja, és a mért érték a valódi sebesség töredékére esett.)"""
    while time.monotonic() < hatarido:
        if (stop is not None and stop.is_set()) or szamlalo.bajt >= korlat:
            return
        try:
            cim = (url or CF_DOWN) % darab if "%d" in (url or CF_DOWN) \
                else (url or CF_DOWN % darab)
            keres = urllib.request.Request(cim, headers=_FEJ)
            with urllib.request.urlopen(keres, timeout=15) as v:
                while time.monotonic() < hatarido:
                    if (stop is not None and stop.is_set()) \
                            or szamlalo.bajt >= korlat:
                        return
                    b = v.read(65536)
                    if not b:
                        break
                    szamlalo.hozzaad(len(b))
        except Exception as e:
            if not (stop is not None and stop.is_set()):
                hibak.append("letöltés: %s" % e)
            return


class _Adagolo:
    """A feltöltendő adatot DARABOKBAN adjuk át (a `http.client` iterálható
    törzset is elfogad) – így mérhető a haladás menet közben."""

    def __init__(self, meret: int, szamlalo: _Szamlalo, stop, blokk: bytes):
        self.meret = meret
        self.szamlalo = szamlalo
        self.stop = stop
        self.blokk = blokk

    def __iter__(self):
        kuldve = 0
        while kuldve < self.meret:
            if self.stop is not None and self.stop.is_set():
                return
            n = min(len(self.blokk), self.meret - kuldve)
            yield self.blokk[:n]
            kuldve += n
            self.szamlalo.hozzaad(n)


def _fel_szal(darab: int, szamlalo: _Szamlalo, stop, hibak: list,
              hatarido: float, korlat: int) -> None:
    """IDŐALAPÚ feltöltés. Egy megkezdett adagot MINDIG végigküldünk (a félbehagyott
    kérés hibát dobna) – a túllövés így legfeljebb egy adagnyi."""
    blokk = os.urandom(65536)          # véletlen adat: nem tömöríthető
    while time.monotonic() < hatarido:
        if (stop is not None and stop.is_set()) or szamlalo.bajt >= korlat:
            return
        try:
            fej = dict(_FEJ)
            fej["Content-Length"] = str(darab)
            fej["Content-Type"] = "application/octet-stream"
            keres = urllib.request.Request(
                CF_UP, data=_Adagolo(darab, szamlalo, stop, blokk),
                headers=fej, method="POST")
            with urllib.request.urlopen(keres, timeout=30) as v:
                v.read(256)
        except Exception as e:
            if not (stop is not None and stop.is_set()):
                hibak.append("feltöltés: %s" % e)
            return


@dataclass
class SavEredmeny:
    mbps: float = 0.0          # a MÁSODPERCENKÉNTI minták MEDIÁNJA
    csucs_mbps: float = 0.0    # a legjobb másodperc
    bajt: int = 0
    mintak: list = field(default_factory=list)   # másodpercenkénti Mbit/s

    @property
    def ingadozo(self) -> bool:
        """Erősen ingadozó vonal: a csúcs a tipikus érték TÖBBSZÖRÖSE. Ezt vakon
        semmiből nem lehet észrevenni, pedig ez a leggyakoribb valódi panasz
        („néha megy, néha nem")."""
        return bool(self.mbps > 0 and self.csucs_mbps > 3 * self.mbps
                    and len(self.mintak) >= 4)


def _savszelesseg(fel: bool, masodperc: float, szalak: int, stop, hibak: list,
                  halad=None, darab: int = 0, korlat: int = 0,
                  url: str = "") -> SavEredmeny:
    """`szalak` párhuzamos kapcsolat `masodperc` ideig – így mérhető a valódi
    csúcs (egy kapcsolat sokszor nem tudja kitölteni a vonalat), és a mérés
    ideje kiszámítható. `korlat`: felső bájtkorlát (mobilnet-védelem).

    MÁSODPERCENKÉNT MINTÁT VESZÜNK, és a MEDIÁNT jelentjük, nem az átlagot: egy
    akadozó vonalnál (villanásnyi csúcs, aztán megállás) az átlag szépít, a
    medián az igazat mondja. A csúcsot külön megőrizzük, mert a kettő KÜLÖNBSÉGE
    maga a diagnózis."""
    darab = darab or (8 * _MB if fel else 25 * _MB)
    korlat = korlat or (_FEL_KORLAT if fel else _LE_KORLAT)
    bemelegites = min(1.0, masodperc / 4)
    szamlalo = _Szamlalo(bemelegites=bemelegites)
    hatarido = time.monotonic() + masodperc
    if fel:
        lista = [threading.Thread(target=_fel_szal,
                                  args=(darab, szamlalo, stop, hibak, hatarido,
                                        korlat), daemon=True)
                 for _ in range(szalak)]
    else:
        lista = [threading.Thread(target=_le_szal,
                                  args=(darab, szamlalo, stop, hibak, hatarido,
                                        korlat, url), daemon=True)
                 for _ in range(szalak)]
    kezdet = time.monotonic()
    for s in lista:
        s.start()
    mintak, elozo_bajt, elozo_ido = [], 0, kezdet
    while any(s.is_alive() for s in lista):
        time.sleep(0.5)
        most = time.monotonic()
        with szamlalo.zar:
            bajt_most = szamlalo.bajt
        if most - kezdet >= bemelegites and most > elozo_ido:
            mintak.append(_mbps(bajt_most - elozo_bajt, most - elozo_ido))
        elozo_bajt, elozo_ido = bajt_most, most
        if halad:
            eltelt = masodperc - max(0.0, hatarido - most)
            halad(min(1.0, eltelt / masodperc if masodperc else 1.0))
    for s in lista:
        s.join(timeout=2.0)
    atlag_mbps, bajt = szamlalo.eredmeny()
    hasznos = [m for m in mintak if m >= 0]
    kozep = round(statistics.median(hasznos), 2) if hasznos else atlag_mbps
    return SavEredmeny(mbps=kozep or atlag_mbps,
                       csucs_mbps=round(max(hasznos), 2) if hasznos else atlag_mbps,
                       bajt=bajt, mintak=[round(m, 1) for m in hasznos])


def _le_forras(stop, hibak: list, sajat: str = "") -> str:
    """MELYIK forrásból mérjünk? Sorra próbáljuk a jelölteket egy villámgyors
    mintával, és az elsőt használjuk, amelyik tényleg ad adatot. Így egyetlen
    kiszolgáló kiesése (vagy fojtása) sem teszi tönkre a mérést."""
    jeloltek = [u for u in ([sajat] if sajat else []) + list(LE_FORRASOK) if u]
    for u in jeloltek:
        if stop is not None and stop.is_set():
            return ""
        szamlalo = _Szamlalo(bemelegites=0.0)
        _le_szal(4 * _MB, szamlalo, stop, [], time.monotonic() + 2.0,
                 8 * _MB, u)
        if szamlalo.bajt >= 512 * 1024:
            return u
    hibak.append("egyik mérő-forrás sem adott adatot")
    return jeloltek[0] if jeloltek else ""


# ---------------------------------------------------------- szolgáltatások

def szolgaltatas_probak(stop=None, halad=None, alap=0.0, sav=0.0) -> list:
    ki = []
    n = len(SZOLGALTATASOK)
    for i, (nev, host, port) in enumerate(SZOLGALTATASOK):
        if stop is not None and stop.is_set():
            break
        t = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=4.0):
                ok = True
        except OSError:
            ok = False
        ki.append((nev, ok, round((time.monotonic() - t) * 1000.0, 1)))
        if halad:
            halad(alap + sav * (i + 1) / n)
    return ki


# ------------------------------------------------------------- a mérés maga

def merj(mod: str = "teljes", stop=None, halad=None, le_url: str = "") -> Eredmeny:
    """A teljes mérés. `mod`: 'teljes' | 'takarekos' | 'gyors' (sebesség nélkül).
    `stop`: threading.Event a megszakításhoz. `halad(fazis, szazalek)` visszahívás.
    `le_url`: saját letöltési mérő-forrás (Beállítások – felülírja az alapokat).
    A hívó szál BLOKKOL – a felület háttérszálon hívja."""
    e = Eredmeny(ido=time.strftime("%Y-%m-%d %H:%M:%S"), mod=mod)
    hibak = e.hibak

    def jelez(fazis, pct):
        if halad:
            try:
                halad(fazis, max(0.0, min(100.0, pct)))
            except Exception:
                pass

    jelez("Helyi hálózat felmérése", 2)
    try:
        e.halozat = halozat_adatok()
    except Exception as ex:
        hibak.append("helyi hálózat: %s" % ex)
    if stop is not None and stop.is_set():
        e.megszakitva = True
        return e

    jelez("Publikus adatok lekérdezése", 8)
    try:
        e.publikus = publikus_adatok()
    except Exception as ex:
        hibak.append("publikus adatok: %s" % ex)

    jelez("Késleltetés mérése", 14)
    minta = 6 if mod == "takarekos" else 12
    kicsi, atlag, ingadozas, sikeres = keslekedes(minta=minta, stop=stop)
    e.sebesseg.keses_ms = kicsi
    e.sebesseg.keses_atlag_ms = atlag
    e.sebesseg.ingadozas_ms = ingadozas
    e.sebesseg.sikeres_probak = sikeres
    e.sebesseg.dns_ms = dns_ido()
    if stop is not None and stop.is_set():
        e.megszakitva = True
        return e

    if mod != "gyors":
        takarekos = (mod == "takarekos")
        jelez("Letöltési sebesség mérése", 20)
        forras = _le_forras(stop, hibak, sajat=le_url)
        le = _savszelesseg(
            False, _TAK_LE_IDO if takarekos else _LE_IDO,
            2 if takarekos else _LE_SZAL, stop, hibak,
            halad=lambda p: jelez("Letöltési sebesség mérése", 22 + 30 * p),
            darab=4 * _MB if takarekos else 0,
            korlat=_TAK_LE_KORLAT if takarekos else 0, url=forras)
        e.sebesseg.le_mbps = le.mbps
        e.sebesseg.le_csucs_mbps = le.csucs_mbps
        e.sebesseg.le_mintak = le.mintak
        e.sebesseg.le_bajt = le.bajt
        if stop is not None and stop.is_set():
            e.megszakitva = True
            return e

        jelez("Feltöltési sebesség mérése", 55)
        fel = _savszelesseg(
            True, _TAK_FEL_IDO if takarekos else _FEL_IDO,
            2 if takarekos else _FEL_SZAL, stop, hibak,
            halad=lambda p: jelez("Feltöltési sebesség mérése", 55 + 30 * p),
            darab=1 * _MB if takarekos else 0,
            korlat=_TAK_FEL_KORLAT if takarekos else 0)
        e.sebesseg.fel_mbps = fel.mbps
        e.sebesseg.fel_csucs_mbps = fel.csucs_mbps
        e.sebesseg.fel_mintak = fel.mintak
        e.sebesseg.fel_bajt = fel.bajt
        if stop is not None and stop.is_set():
            e.megszakitva = True
            return e

    jelez("Szolgáltatások ellenőrzése", 88)
    e.szolgaltatasok = szolgaltatas_probak(
        stop=stop, halad=lambda p: jelez("Szolgáltatások ellenőrzése", 88 + 12 * p),
        alap=0.0, sav=1.0)
    jelez("Kész", 100)
    return e


# ------------------------------------------------------------- értékelés

def ingadozo(kozep: float, csucs: float, mintak) -> bool:
    """Erősen ingadozó-e a vonal: a csúcs a tipikus érték többszöröse. Ez a
    „néha megy, néha nem” panasz mérhető formája – és vakon máshonnan nem
    észlelhető, mert a fájl csak „lassan” tölt, nem hibázik."""
    return bool(kozep > 0 and csucs > 3 * kozep and len(mintak or []) >= 4)


def _fokozat(le: float) -> str:
    if le <= 0:
        return "nem mérhető"
    if le < 5:
        return "lassú"
    if le < 30:
        return "átlagos"
    if le < 100:
        return "gyors"
    if le < 500:
        return "nagyon gyors"
    return "kiemelkedően gyors"


# (funkció, kell letöltés, kell feltöltés, kell késleltetés alatt)
_IGENYEK = (
    ("Zenehallgatás, internetes rádió", 0.5, 0.0, 0.0),
    ("Videónézés HD-ben (1080p)", 8.0, 0.0, 0.0),
    ("Videónézés 4K-ban", 25.0, 0.0, 0.0),
    ("Hangkonferencia (Csevejcenter)", 1.0, 0.5, 200.0),
    ("Távsegítség (hang és vezérlés)", 1.5, 1.0, 250.0),
    ("Online játékok (UNO, Póker…)", 0.5, 0.3, 400.0),
    ("Élő multistream (Super Stream)", 2.0, 5.0, 0.0),
)


def minositesek(seb: Sebesseg) -> list:
    """MIRE ELÉG ez a net – a SuperDL SAJÁT funkcióihoz kötve. Ez a „profizmus",
    amit a felhasználó tudni akar: nem a számok, hanem hogy megy-e, amit szeretne."""
    ki = []
    for nev, kell_le, kell_fel, kell_keses in _IGENYEK:
        ok = True
        indok = []
        if kell_le and seb.le_mbps < kell_le:
            ok = False
            indok.append("legalább %s megabit letöltés kellene" % _szam(kell_le))
        if kell_fel and seb.fel_mbps < kell_fel:
            ok = False
            indok.append("legalább %s megabit feltöltés kellene" % _szam(kell_fel))
        if kell_keses and seb.keses_atlag_ms and seb.keses_atlag_ms > kell_keses:
            ok = False
            indok.append("a késleltetés magas")
        ki.append((nev, ok, "; ".join(indok)))
    return ki


def _szam(x: float) -> str:
    s = ("%.1f" % x).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def osszefoglalo(e: Eredmeny) -> str:
    """AZ ELSŐ MONDAT: ítélet emberi nyelven, mielőtt bármi szám jönne."""
    s = e.sebesseg
    if e.mod == "gyors":
        alap = "Gyors ellenőrzés: a kapcsolat %s." % (
            "él" if s.sikeres_probak >= 50 else "akadozik")
    elif s.le_mbps <= 0:
        alap = ("Az internet sebességét most nem sikerült megmérni. "
                "Lehet, hogy nincs kapcsolat, vagy a mérő-kiszolgáló nem elérhető.")
    else:
        alap = ("Az interneted %s: %s megabit letöltés, %s megabit feltöltés, "
                "%s ezredmásodperc késleltetés."
                % (_fokozat(s.le_mbps), _szam(s.le_mbps), _szam(s.fel_mbps),
                   _szam(s.keses_atlag_ms)))
    jo = [n for n, ok, _ in minositesek(s) if ok]
    rossz = [n for n, ok, _ in minositesek(s) if not ok]
    if s.le_mbps > 0:
        if jo:
            alap += " Elég ehhez: " + ", ".join(jo[:4]).lower() + "."
        if rossz:
            alap += " Határeset vagy kevés ehhez: " + ", ".join(rossz).lower() + "."
    if ingadozo(s.le_mbps, s.le_csucs_mbps, s.le_mintak):
        alap += (" A vonal AKADOZIK: a sebesség %s és %s megabit között ugrált a "
                 "mérés alatt. Ez tipikusan túlterhelt vonalra, gyenge wifire "
                 "vagy a szolgáltató korlátozására utal – érdemes megismételni a "
                 "mérést később is, és a naplóból megmutatni a szolgáltatónak."
                 % (_szam(min(s.le_mintak)), _szam(s.le_csucs_mbps)))
    h = e.halozat
    if h.vpn:
        alap += (" Figyelem: VPN-kapcsolat aktív (%s), ez lassíthatja és "
                 "elrejtheti a valódi helyzetet." % h.vpn)
    if h.kapcsolat.startswith("vezeték nélküli") and h.wifi_jel:
        if h.wifi_jel < 50:
            alap += (" A wifi jele gyenge (%d százalék) – a lassúság oka jó "
                     "eséllyel ez, nem a szolgáltató." % h.wifi_jel)
        elif h.wifi_sav == "2,4 GHz" and s.le_mbps < 60:
            alap += (" A wifi a lassabb 2,4 gigahertzes sávon van; ha a router "
                     "tud 5 gigahertzet, azon gyorsabb lehet.")
    rossz_szolg = [n for n, ok, _ in e.szolgaltatasok if not ok]
    if rossz_szolg:
        alap += (" Nem érhető el: %s – ez nem az internet sebességének a hibája."
                 % ", ".join(rossz_szolg))
    if e.mod == "takarekos" and s.le_mbps > 0:
        alap += (" Ez TAKARÉKOS mérés volt, kevés adatforgalommal – a sebesség "
                 "csak tájékoztató, a valódi érték ennél nagyobb is lehet.")
    if e.megszakitva:
        alap = "A mérés megszakítva. " + alap
    return alap


def sorok(e: Eredmeny, teljes_ip: bool = False) -> list:
    """A részletek soronként – ezt járja be a felhasználó a nyilakkal, és minden
    sor önmagában is értelmes, mert a képernyőolvasó SORONKÉNT olvassa fel."""
    s, h, p = e.sebesseg, e.halozat, e.publikus
    ki = ["Mérés ideje: %s (%s mérés)" % (e.ido, e.mod)]
    if e.mod != "gyors":
        ki += [
            "Letöltési sebesség: %s megabit per másodperc (csúcs: %s)"
            % (_szam(s.le_mbps), _szam(s.le_csucs_mbps)),
            "Feltöltési sebesség: %s megabit per másodperc (csúcs: %s)"
            % (_szam(s.fel_mbps), _szam(s.fel_csucs_mbps)),
            "Egy gigabájt letöltése ezen a sebességen: %s"
            % egy_giga_ideje(s.le_mbps),
        ]
        if ingadozo(s.le_mbps, s.le_csucs_mbps, s.le_mintak):
            ki.append("FIGYELEM – a letöltés erősen ingadozott: %s megabit "
                      "másodpercenként" % ", ".join(_szam(m)
                                                    for m in s.le_mintak))
        if ingadozo(s.fel_mbps, s.fel_csucs_mbps, s.fel_mintak):
            ki.append("FIGYELEM – a feltöltés erősen ingadozott: %s megabit "
                      "másodpercenként" % ", ".join(_szam(m)
                                                    for m in s.fel_mintak))
    ki += [
        "Késleltetés (TCP-válaszidő, nem ICMP-ping): átlag %s, legkisebb %s "
        "ezredmásodperc" % (_szam(s.keses_atlag_ms), _szam(s.keses_ms)),
        "Ingadozás (jitter): %s ezredmásodperc" % _szam(s.ingadozas_ms),
        "Sikeres kapcsolat-próbák: %s százalék" % _szam(s.sikeres_probak),
        "Névfeloldás (DNS) ideje: %s ezredmásodperc – a gyorsítótár is "
        "beleszámít" % _szam(s.dns_ms),
    ]
    if e.mod != "gyors":
        ki.append("A mérés adatforgalma: %s megabájt letöltés, %s megabájt "
                  "feltöltés" % (_szam(s.le_bajt / _MB), _szam(s.fel_bajt / _MB)))

    ki.append("— Kapcsolat —")
    ki.append("Kapcsolat típusa: %s" % (h.kapcsolat or "ismeretlen"))
    if h.adapter:
        ki.append("Hálózati eszköz: %s" % h.adapter)
    if h.link_mbps:
        ki.append("A hálókártya sávszélessége: %s megabit" % _szam(h.link_mbps))
    if h.wifi_halozat:
        ki.append("Wi-Fi hálózat: %s" % h.wifi_halozat)
        # A dBm a szakmai mérőszám (mesh-hálózat építéséhez ez kell), a
        # százalék pedig a hétköznapi – ezért mindkettőt kiírjuk, magyarázattal.
        if h.wifi_dbm:
            fokozat, magyarazat = jel_minosites(h.wifi_dbm)
            ki.append("Wi-Fi jelerősség: %d dBm%s – %s (jelminőség: %d "
                      "százalék)"
                      % (h.wifi_dbm,
                         "" if h.wifi_dbm_mert else " (számolva)",
                         fokozat, h.wifi_jel))
            ki.append("   %s" % magyarazat)
        else:
            ki.append("Wi-Fi jelerősség: %d százalék%s"
                      % (h.wifi_jel, " – gyenge, ez lassíthat"
                         if h.wifi_jel < 50 else
                         (" – közepes" if h.wifi_jel < 70 else " – jó")))
        if h.wifi_sav:
            ki.append("Wi-Fi sáv: %s (csatorna: %d)" % (h.wifi_sav, h.wifi_csatorna))
        if h.wifi_le_mbps:
            ki.append("Wi-Fi kapcsolati sebesség: le %s, fel %s megabit"
                      % (_szam(h.wifi_le_mbps), _szam(h.wifi_fel_mbps)))
    if h.helyi_ip:
        ki.append("Helyi IP-cím: %s" % h.helyi_ip)
    if h.atjaro:
        ki.append("Átjáró (router): %s" % h.atjaro)
    if h.dns_kiszolgalok:
        ki.append("DNS-kiszolgálók: %s" % ", ".join(h.dns_kiszolgalok))
    if h.mtu:
        ki.append("MTU (csomagméret): %d" % h.mtu)
    ki.append("IPv6 elérhető: %s" % ("igen" if h.ipv6 else "nem"))
    if h.vpn:
        ki.append("VPN aktív: %s – a mérés az ő útvonalán ment" % h.vpn)
    if h.merten_gyanu:
        ki.append("Korlátozott (mért) kapcsolat gyanúja: igen – vigyázz az "
                  "adatforgalommal")

    ki.append("— Publikus adatok —")
    ki.append("Publikus IP-cím: %s"
              % ((p.ip or "ismeretlen") if teljes_ip else
                 (maszkol_ip(p.ip) or "ismeretlen")))
    if not teljes_ip and p.ip:
        ki.append("(A teljes IP-cím elrejtve – a „Teljes IP megjelenítése” "
                  "gombbal kérhető)")
    if p.host:
        ki.append("Hoszt neve (fordított DNS): %s" % p.host)
    if p.szolgaltato:
        ki.append("Szolgáltató: %s%s" % (p.szolgaltato,
                                         " (AS%s)" % p.asn if p.asn else ""))
    if p.varos or p.orszag:
        ki.append("Hely a szolgáltató szerint: %s"
                  % ", ".join(x for x in (p.varos, p.orszag) if x))
    if p.kiszolgalo:
        ki.append("Mérő-kiszolgáló: %s" % p.kiszolgalo)

    if e.szolgaltatasok:
        ki.append("— SuperDL-szolgáltatások elérhetősége —")
        for nev, ok, ms in e.szolgaltatasok:
            ki.append("%s: %s (%s ezredmásodperc)"
                      % (nev, "elérhető" if ok else "NEM érhető el", _szam(ms)))

    ki.append("— Mire elég ez a net? —")
    for nev, ok, indok in minositesek(s):
        ki.append("%s: %s%s" % (nev, "megfelelő" if ok else "kevés",
                                " – %s" % indok if indok else ""))
    if e.hibak:
        ki.append("— Mérési figyelmeztetések —")
        ki += ["Figyelmeztetés: %s" % x for x in e.hibak[:6]]
    return ki


def jelentes(e: Eredmeny, teljes_ip: bool = False) -> str:
    """Másolható szöveg – ezt lehet beilleszteni egy segítségkérő levélbe."""
    fej = ["SuperDL – Internet-teszt jelentés", "=" * 40, "", osszefoglalo(e), ""]
    if not teljes_ip:
        fej.append("(A publikus IP-cím adatvédelmi okból maszkolva.)")
        fej.append("")
    return "\n".join(fej + sorok(e, teljes_ip=teljes_ip)) + "\n"


# ---------------------------------------------------------------- napló

def naplo_ment(e: Eredmeny) -> None:
    """Időbélyeges napló: két hét múlva ebből derül ki, hogy „minden este
    nyolckor beesik a sebesség" – ezzel már érdemben lehet reklamálni.
    A publikus IP-t SZÁNDÉKOSAN maszkolva mentjük."""
    try:
        f = _naplo_fajl()
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            naplo = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(naplo, list):
                naplo = []
        except Exception:
            naplo = []
        d = asdict(e)
        d["publikus"]["ip"] = maszkol_ip(e.publikus.ip)
        naplo.append(d)
        del naplo[:-_NAPLO_MAX]
        ideiglenes = f.with_suffix(".tmp")
        ideiglenes.write_text(json.dumps(naplo, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        os.replace(ideiglenes, f)
    except Exception:
        pass


def naplo_betolt() -> list:
    try:
        d = json.loads(_naplo_fajl().read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def naplo_sorok(darab: int = 30) -> list:
    """A korábbi mérések felolvasható, egysoros összefoglalói (legújabb elöl)."""
    ki = []
    for d in reversed(naplo_betolt()[-darab:]):
        s = d.get("sebesseg", {})
        ki.append("%s – le %s, fel %s megabit, késleltetés %s ezredmásodperc"
                  % (d.get("ido", ""), _szam(s.get("le_mbps", 0)),
                     _szam(s.get("fel_mbps", 0)),
                     _szam(s.get("keses_atlag_ms", 0))))
    return ki or ["Még nincs korábbi mérés."]


def naplo_atlag(darab: int = 10) -> str:
    d = naplo_betolt()[-darab:]
    le = [x.get("sebesseg", {}).get("le_mbps", 0) for x in d
          if x.get("sebesseg", {}).get("le_mbps", 0) > 0]
    if not le:
        return ""
    return ("Az utolsó %d mérés átlaga: %s megabit letöltés."
            % (len(le), _szam(statistics.fmean(le))))


# ======================================================================
#  WI-FI JELERŐSSÉG-FIGYELŐ  (mesh-hálózat építéséhez)
# ======================================================================
#
# Felhasználói kérés (2026-08-20): „olyan eszközt keresnék, ami kiírná, hogy
# milyen jelerősségű az épp használt wifi-kapcsolat, a dBm értéket megadva…
# mesh hálót építek éppen ki, jó lenne látnom laptopon is, hogy hol milyen
# erős még a kapcsolat.”
#
# A dBm kiírása önmagában kevés lenne: a mesh-építés közben az ember JÁRKÁL a
# lakásban, és közben nem tud a képernyőt nézni – vakon pedig végképp nem.
# Ezért a figyelő folyamatosan mér, és a változást KIMONDJA, illetve egy
# hangmagassággal is jelzi (minél erősebb a jel, annál magasabb a hang).

JEL_HANG_ALSO_HZ = 220.0        # −85 dBm
JEL_HANG_FELSO_HZ = 1320.0      # −35 dBm


def jel_frekvencia(dbm: int) -> float:
    """A jelerősséghez tartozó hangmagasság. Járkálás közben ez a leggyorsabb
    visszajelzés: nem kell megvárni a bemondást, a fül azonnal hallja, hogy
    erősödik vagy gyengül."""
    try:
        d = float(dbm)
    except (TypeError, ValueError):
        return JEL_HANG_ALSO_HZ
    d = max(-85.0, min(-35.0, d))
    arany = (d + 85.0) / 50.0                     # 0.0 … 1.0
    # zenei (logaritmikus) lépték: a fül így hallja egyenletesnek
    return JEL_HANG_ALSO_HZ * (JEL_HANG_FELSO_HZ / JEL_HANG_ALSO_HZ) ** arany


class JelNaplo:
    """A bejárás naplója: mérések, megjelölt pontok, összesítés.

    Szándékosan wx-mentes, hogy tesztelhető legyen: az időzítést és a
    bemondást a felület intézi."""

    def __init__(self, valtozas_kuszob: int = 3):
        self.meresek = []           # [(dbm, jel_szazalek)]
        self.pontok = []            # [(nev, dbm, jel_szazalek)]
        self.kuszob = max(1, int(valtozas_kuszob))
        self._utoljara_mondott = None

    # ---- mérés
    def hozzaad(self, dbm: int, jel_szazalek: int = 0) -> bool:
        """Új mérés. Igaz, ha ÉRDEMES kimondani (elég nagyot változott).

        Miért kell küszöb: a jel másodpercenként ingadozik 1-2 dBm-et. Ha
        minden rezdülést bemondanánk, a program folyamatosan beszélne, és a
        felhasználó nem hallaná a lényeget."""
        self.meresek.append((int(dbm), int(jel_szazalek or 0)))
        if self._utoljara_mondott is None \
                or abs(int(dbm) - self._utoljara_mondott) >= self.kuszob:
            self._utoljara_mondott = int(dbm)
            return True
        return False

    # ---- statisztika
    def legjobb(self) -> int:
        return max((m[0] for m in self.meresek), default=0)

    def leggyengebb(self) -> int:
        return min((m[0] for m in self.meresek), default=0)

    def atlag(self) -> int:
        if not self.meresek:
            return 0
        return int(round(statistics.fmean(m[0] for m in self.meresek)))

    # ---- megjelölt pontok
    def pont(self, nev: str) -> tuple:
        """A mostani helyszín megjelölése („konyha”, „hálószoba”)."""
        if not self.meresek:
            return ("", 0, 0)
        dbm, jel = self.meresek[-1]
        tetel = (str(nev or "").strip() or "névtelen pont", dbm, jel)
        self.pontok.append(tetel)
        return tetel

    def pont_szoveg(self, tetel) -> str:
        nev, dbm, jel = tetel
        fokozat, _ = jel_minosites(dbm)
        return "%s: %d dBm – %s" % (nev, dbm, fokozat)

    # ---- összefoglalás
    def osszefoglalo(self) -> str:
        if not self.meresek:
            return "Nem történt mérés."
        sorok = ["%d mérés. Legerősebb: %d dBm, leggyengébb: %d dBm, "
                 "átlag: %d dBm." % (len(self.meresek), self.legjobb(),
                                     self.leggyengebb(), self.atlag())]
        if self.pontok:
            sorok.append("Megjelölt helyek:")
            sorok.extend("  " + self.pont_szoveg(p) for p in self.pontok)
            gyenge = [p for p in self.pontok if p[1] < -72]
            if gyenge:
                sorok.append("Ezeken a helyeken gyenge a jel, ide érdemes még "
                             "egy mesh-egységet tenni: "
                             + ", ".join(p[0] for p in gyenge) + ".")
            else:
                sorok.append("A megjelölt helyeken mindenhol legalább "
                             "elfogadható a jel.")
        return "\n".join(sorok)

    def mentheto_szoveg(self, halozat: str = "") -> str:
        """A bejárás fájlba menthető jegyzőkönyve."""
        fej = ["SuperDL – Wi-Fi jelerősség-bejárás"]
        if halozat:
            fej.append("Hálózat: %s" % halozat)
        fej.append("")
        fej.append(self.osszefoglalo())
        fej.append("")
        fej.append("Minden mérés (dBm):")
        fej.append(", ".join(str(m[0]) for m in self.meresek))
        return "\n".join(fej)
