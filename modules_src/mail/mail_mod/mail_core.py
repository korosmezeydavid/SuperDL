# -*- coding: utf-8 -*-
"""Super Mail – a levelező MAGJA (wx nélkül, tisztán tesztelhető).

Kizárólag emailezés: fogadás (IMAP/POP3), küldés (SMTP), keresés. Semmi mást
nem csinál, és SEMMIT nem továbbít sehová: a kliens közvetlenül a felhasználó
saját e-mail-szolgáltatójának szerveréhez csatlakozik, semmi máshoz. A fiók
hitelesítő adatai a felhasználó gépén, DPAPI-val titkosítva tárolódnak (a Core
store-ján át), és egyetlen céljuk, hogy az olvasás/küldés/keresés működjön.

A hálózati rész csak a Python beépített moduljaira épül (imaplib, poplib,
smtplib, email) – nincs külső függőség.
"""
import email
import email.header
import email.utils
import imaplib
import mimetypes
import os
import poplib
import re
import smtplib
import ssl
from email.message import EmailMessage
from html.parser import HTMLParser

from superdl import store


# ======================================================================
#  Fiók-adatmodell + auto-konfiguráció
# ======================================================================

# A gyakori szolgáltatók szerverei (a felhasználónak csak az e-mail címe kell).
# Ha egy domain nincs itt, a program megkísérli az imap./pop./smtp. előtagot.
_SZOLGALTATOK = {
    "gmail.com":     ("imap.gmail.com", "pop.gmail.com", "smtp.gmail.com"),
    "googlemail.com": ("imap.gmail.com", "pop.gmail.com", "smtp.gmail.com"),
    "outlook.com":   ("outlook.office365.com", "outlook.office365.com",
                      "smtp.office365.com"),
    "hotmail.com":   ("outlook.office365.com", "outlook.office365.com",
                      "smtp.office365.com"),
    "live.com":      ("outlook.office365.com", "outlook.office365.com",
                      "smtp.office365.com"),
    "yahoo.com":     ("imap.mail.yahoo.com", "pop.mail.yahoo.com",
                      "smtp.mail.yahoo.com"),
    "freemail.hu":   ("imap.freemail.hu", "pop3.freemail.hu",
                      "smtp.freemail.hu"),
    "citromail.hu":  ("imap.citromail.hu", "pop3.citromail.hu",
                      "smtp.citromail.hu"),
    "gmx.com":       ("imap.gmx.com", "pop.gmx.com", "mail.gmx.com"),
    "gmx.net":       ("imap.gmx.net", "pop.gmx.net", "mail.gmx.net"),
    "icloud.com":    ("imap.mail.me.com", "imap.mail.me.com",
                      "smtp.mail.me.com"),
}

# app-jelszót IGÉNYLŐ szolgáltatók (a sima fiókjelszó nem működik SMTP/IMAP-on)
_APP_JELSZO_KELL = {"gmail.com", "googlemail.com", "yahoo.com", "icloud.com",
                    "outlook.com", "hotmail.com", "live.com"}

# Ahol app-jelszót lehet létrehozni – EZ a kész megoldás a végfelhasználónak:
# néhány kattintás a saját fiók beállításaiban, fejlesztői regisztráció nélkül.
_APP_JELSZO_URL = {
    "gmail.com":     "https://myaccount.google.com/apppasswords",
    "googlemail.com": "https://myaccount.google.com/apppasswords",
    "yahoo.com":     "https://login.yahoo.com/account/security/app-passwords",
    "outlook.com":   "https://account.live.com/proofs/AppPassword",
    "hotmail.com":   "https://account.live.com/proofs/AppPassword",
    "live.com":      "https://account.live.com/proofs/AppPassword",
    "icloud.com":    "https://appleid.apple.com/account/manage",
}

_APP_JELSZO_LEPESEK = {
    "google": ("Gmail app-jelszó: 1) A megnyíló oldalon jelentkezz be. "
               "2) Ha kéri, előbb kapcsold be a kétlépcsős azonosítást. "
               "3) Adj nevet (pl. Super Mail), és a Google ad egy 16 jegyű "
               "jelszót. 4) Ezt másold be ide a Jelszó mezőbe (a szóközök nem "
               "számítanak)."),
    "microsoft": ("Outlook app-jelszó: 1) A megnyíló oldalon jelentkezz be. "
                  "2) Ha kell, kapcsold be a kétlépcsős azonosítást. 3) Hozz "
                  "létre egy új app-jelszót, és másold be ide a Jelszó mezőbe."),
    "yahoo": ("Yahoo app-jelszó: 1) Jelentkezz be a megnyíló oldalon. "
              "2) Generálj egy app-jelszót (Mail alkalmazáshoz). 3) Másold be "
              "ide a Jelszó mezőbe."),
    "icloud": ("iCloud app-jelszó: 1) Jelentkezz be az Apple ID oldalon. "
               "2) A Bejelentkezés és biztonságnál hozz létre app-jelszót. "
               "3) Másold be ide a Jelszó mezőbe."),
    "": ("Ehhez a szolgáltatóhoz általában a sima fiókjelszó is működik. Ha "
         "elutasít, keress rá, hogy „app-jelszó”, és a fiókod beállításainál "
         "hozz létre egyet."),
}


def _domain(cim):
    return (cim or "").strip().lower().rsplit("@", 1)[-1]


def auto_konfig(email_cim):
    """Az e-mail cím alapján kitalálja a szerverek nevét és portját. A
    felhasználó ezt kézzel felülírhatja."""
    dom = _domain(email_cim)
    if dom in _SZOLGALTATOK:
        imap, pop, smtp = _SZOLGALTATOK[dom]
    elif dom:
        imap, pop, smtp = f"imap.{dom}", f"pop.{dom}", f"smtp.{dom}"
    else:
        imap = pop = smtp = ""
    return {
        "imap_host": imap, "imap_port": 993,
        "pop_host": pop, "pop_port": 995,
        "smtp_host": smtp, "smtp_port": 465,   # 465 = SSL; 587 = STARTTLS
        "tls": True,
    }


def app_jelszo_kell(email_cim):
    """Igaz, ha a szolgáltató app-specifikus jelszót igényel (a sima fiók-
    jelszó nem elég). Ilyenkor a felületen erről tájékoztatunk."""
    return _domain(email_cim) in _APP_JELSZO_KELL


def provider_kulcs(email_cim):
    """A szolgáltató belső kulcsa (google/microsoft/yahoo/icloud), OAuth és az
    app-jelszó-útmutató kiválasztásához."""
    dom = _domain(email_cim)
    if "gmail" in dom or "google" in dom:
        return "google"
    if dom in ("outlook.com", "hotmail.com", "live.com"):
        return "microsoft"
    if "yahoo" in dom:
        return "yahoo"
    if "icloud" in dom or dom == "me.com":
        return "icloud"
    return ""


def app_jelszo_url(email_cim):
    """A szolgáltató app-jelszó-létrehozó oldala (üres, ha nem ismert)."""
    return _APP_JELSZO_URL.get(_domain(email_cim), "")


def app_jelszo_utmutato(email_cim):
    """Rövid, felolvasható lépések az app-jelszó létrehozásához."""
    return _APP_JELSZO_LEPESEK.get(provider_kulcs(email_cim),
                                   _APP_JELSZO_LEPESEK[""])


def uj_fiok(nev, email_cim, jelszo, protokoll="imap", felul=None):
    """Új fiók-rekord az auto-konfiggal (kézi felülírással)."""
    k = auto_konfig(email_cim)
    if felul:
        k.update(felul)
    return {
        "nev": (nev or email_cim).strip(),
        "email": email_cim.strip(),
        "felhasznalo": email_cim.strip(),
        "jelszo": jelszo or "",
        "protokoll": protokoll if protokoll in ("imap", "pop") else "imap",
        **k,
    }


# ======================================================================
#  Titkosított fiók-tárolás + hozzájárulás  (DPAPI a Core store-ján át)
# ======================================================================
_FIOK_FILE = store.CONFIG_DIR / "mail_accounts.dat"


def _titkos_betolt():
    try:
        return store._load_secret_config(_FIOK_FILE)
    except Exception:
        return {}


def _titkos_ment(adat):
    store.save_secret_json(_FIOK_FILE, adat)


def hozzajarulas_megvan():
    return bool(_titkos_betolt().get("hozzajarulas"))


def hozzajarulas_ment(ertek=True):
    d = _titkos_betolt()
    d["hozzajarulas"] = bool(ertek)
    _titkos_ment(d)


def fiokok_betolt():
    return list(_titkos_betolt().get("fiokok", []))


def fiokok_ment(fiokok):
    d = _titkos_betolt()
    d["fiokok"] = list(fiokok)
    _titkos_ment(d)


def fiok_torol(email_cim):
    """Egy fiók (és a jelszava) végleges törlése a tárolóból."""
    megmarad = [f for f in fiokok_betolt() if f.get("email") != email_cim]
    fiokok_ment(megmarad)


# ======================================================================
#  Szöveg-segédek: fejléc-dekódolás, HTML→szöveg
# ======================================================================

def dekodol_fejlec(nyers):
    """Egy MIME-fejléc (pl. Subject, From) emberi szöveggé alakítása – a
    =?UTF-8?...?= kódolású részeket is dekódolja."""
    if nyers is None:
        return ""
    reszek = []
    for szoveg, kodolas in email.header.decode_header(str(nyers)):
        if isinstance(szoveg, bytes):
            try:
                reszek.append(szoveg.decode(kodolas or "utf-8", "replace"))
            except (LookupError, UnicodeDecodeError):
                reszek.append(szoveg.decode("latin-1", "replace"))
        else:
            reszek.append(szoveg)
    return "".join(reszek).strip()


class _SzovegKinyero(HTMLParser):
    """Egyszerű HTML→szöveg: a látható szöveget kinyeri, a linkek célját is
    megőrzi (hogy fel lehessen olvasni), a script/style tartalmát eldobja."""
    def __init__(self):
        super().__init__()
        self._ki = []
        self._skip = 0
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li"):
            self._ki.append("\n")
        elif tag == "a":
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1
        elif tag == "a" and self._href:
            if self._href and not self._href.startswith("mailto:"):
                self._ki.append(f" ({self._href})")
            self._href = None

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._ki.append(data)

    def szoveg(self):
        s = "".join(self._ki)
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
        return s.strip()


def html_to_szoveg(html):
    p = _SzovegKinyero()
    try:
        p.feed(html or "")
    except Exception:
        return re.sub(r"<[^>]+>", " ", html or "").strip()
    return p.szoveg()


_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.IGNORECASE)


def hivatkozasok_szovegbol(szoveg):
    """A szövegben található http/https hivatkozások, megjelenési sorrendben,
    duplikátumok nélkül (a törzs a HTML linkjeit is „(http…)" alakban őrzi)."""
    ki, latott = [], set()
    for u in _URL_RE.findall(szoveg or ""):
        u = u.rstrip(".,;:!?)")            # záró írásjelek levágása
        if u and u not in latott:
            latott.add(u)
            ki.append(u)
    return ki


def _imap_utf7_decode(s):
    """IMAP modified UTF-7 (RFC 3501) → Unicode, hogy a magyar ékezetes
    mappanevek (pl. Elküldött, Összes levél) helyesen jelenjenek meg."""
    import base64
    if isinstance(s, bytes):
        s = s.decode("ascii", "replace")
    ki, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "&":
            j = s.find("-", i + 1)
            if j == -1:
                ki.append(s[i:])
                break
            reszlet = s[i + 1:j]
            if reszlet == "":
                ki.append("&")                 # a „&-" a sima & jel
            else:
                b64 = reszlet.replace(",", "/")
                b64 += "=" * (-len(b64) % 4)
                try:
                    ki.append(base64.b64decode(b64).decode("utf-16-be"))
                except Exception:
                    ki.append(s[i:j + 1])
            i = j + 1
        else:
            ki.append(c)
            i += 1
    return "".join(ki)


def mappa_display(raw):
    """A mappanév felolvasható változata: INBOX → Beérkezett, az ékezetek
    (IMAP modified UTF-7) helyesen dekódolva."""
    if (raw or "").upper() == "INBOX":
        return "Beérkezett"
    return _imap_utf7_decode(raw or "")


# ======================================================================
#  Levél-elemzés (email.message → emberi mezők)
# ======================================================================

def level_fejlec_info(msg):
    """A lista-nézethez: feladó, tárgy, dátum, van-e csatolmány."""
    van_csat = any(
        (r.get_filename() or (r.get_content_disposition() == "attachment"))
        for r in msg.walk()) if msg.is_multipart() else bool(msg.get_filename())
    return {
        "felado": dekodol_fejlec(msg.get("From", "")),
        "targy": dekodol_fejlec(msg.get("Subject", "(nincs tárgy)")),
        "datum": dekodol_fejlec(msg.get("Date", "")),
        "cimzett": dekodol_fejlec(msg.get("To", "")),
        "csatolmany": bool(van_csat),
    }


def _resz_szoveg(resz):
    toltet = resz.get_payload(decode=True)
    if toltet is None:
        return ""
    kod = resz.get_content_charset() or "utf-8"
    try:
        return toltet.decode(kod, "replace")
    except (LookupError, UnicodeDecodeError):
        return toltet.decode("latin-1", "replace")


def level_szovegtorzs(msg):
    """A levél FELOLVASHATÓ törzse: a text/plain rész elsőbbséget élvez, ha
    csak HTML van, azt alakítjuk tiszta szöveggé. A csatolmányokat kihagyja."""
    plain, html = None, None
    if msg.is_multipart():
        for resz in msg.walk():
            if resz.is_multipart():
                continue
            if resz.get_content_disposition() == "attachment":
                continue
            tipus = resz.get_content_type()
            if tipus == "text/plain" and plain is None:
                plain = _resz_szoveg(resz)
            elif tipus == "text/html" and html is None:
                html = _resz_szoveg(resz)
    else:
        if msg.get_content_type() == "text/html":
            html = _resz_szoveg(msg)
        else:
            plain = _resz_szoveg(msg)
    if plain and plain.strip():
        return plain.strip()
    if html:
        return html_to_szoveg(html)
    return ""


def csatolmanyok(msg):
    """A csatolmányok listája: [(fájlnév, bájtok), …]."""
    ki = []
    for resz in msg.walk():
        if resz.is_multipart():
            continue
        nev = resz.get_filename()
        if nev or resz.get_content_disposition() == "attachment":
            adat = resz.get_payload(decode=True) or b""
            ki.append((dekodol_fejlec(nev) or "csatolmany", adat))
    return ki


# ======================================================================
#  Levél összeállítása küldéshez (MIME)
# ======================================================================

# Az önlejátszó hang jelölő-fejléce: a fogadó Super Mail ebből tudja, hogy a
# levél megnyitásakor magától megszólaltassa a megadott nevű hang-csatolmányt.
AUTOSOUND_FEJLEC = "X-SuperMail-Autosound"

_HANG_KITERJESZTESEK = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus",
                        ".wav", ".flac", ".wma", ".mp2")


def level_epit(felado, cimzett, targy, torzs, masolat="", csatolmanyok_lista=None,
               valasz_id=None, titkos="", autosound_nev=""):
    """Kimenő levél MIME-üzenetté formázása. `csatolmanyok_lista`: fájl-utak
    listája; `titkos`: Bcc-címzettek; `autosound_nev`: ha meg van adva, a levél
    önlejátszó-hang jelölést kap erre a csatolmány-fájlnévre. EmailMessage-t ad."""
    m = EmailMessage()
    m["From"] = felado
    m["To"] = cimzett
    if masolat:
        m["Cc"] = masolat
    if titkos:
        m["Bcc"] = titkos           # a send_message a Bcc-t kiszedi, de elküldi
    m["Subject"] = targy or "(nincs tárgy)"
    if valasz_id:
        m["In-Reply-To"] = valasz_id
        m["References"] = valasz_id
    if autosound_nev:
        m[AUTOSOUND_FEJLEC] = os.path.basename(autosound_nev)
    m.set_content(torzs or "")
    for ut in (csatolmanyok_lista or []):
        try:
            with open(ut, "rb") as f:
                adat = f.read()
        except OSError:
            continue
        tipus, _ = mimetypes.guess_type(ut)
        fo, al = (tipus.split("/", 1) if tipus else ("application",
                                                     "octet-stream"))
        m.add_attachment(adat, maintype=fo, subtype=al,
                         filename=os.path.basename(ut))
    return m


def cimzettek(cim_szoveg):
    """Vesszővel/pontosvesszővel elválasztott címzettek listája (tiszta címek)."""
    if not cim_szoveg:
        return []
    nyers = re.split(r"[;,]", cim_szoveg)
    ki = []
    for r in nyers:
        nev, cim = email.utils.parseaddr(r.strip())
        if cim:
            ki.append(cim)
    return ki


# ======================================================================
#  Okos címjegyzék – a postafiókból tanul (küldött + kapott levelekből)
# ======================================================================
_CIMJEGYZEK_FILE = store.CONFIG_DIR / "mail_contacts.json"


def cimjegyzek_betolt():
    return list(store.load_json(_CIMJEGYZEK_FILE, []) or [])


def cimjegyzek_ment(lista):
    store.save_json(_CIMJEGYZEK_FILE, list(lista))


def _cim_bont(szoveg):
    """„Név <email>, ..." → [(nev, email_kisbetűs), …] – a fejléc-kódolt neveket
    is dekódolja."""
    ki = []
    for nev, cim in email.utils.getaddresses([szoveg or ""]):
        cim = (cim or "").strip().lower()
        if "@" in cim and "." in cim.rsplit("@", 1)[-1]:
            ki.append((dekodol_fejlec(nev).strip(), cim))
    return ki


def cimjegyzek_felvesz(email_cim, nev=""):
    """Egy címet felvesz/frissít (dedup e-mail szerint; gyakoriság + idő)."""
    import time
    email_cim = (email_cim or "").strip().lower()
    if "@" not in email_cim:
        return False
    lista = cimjegyzek_betolt()
    for c in lista:
        if c.get("email", "").lower() == email_cim:
            c["db"] = int(c.get("db", 0)) + 1
            c["utoljara"] = time.time()
            if nev and not c.get("nev"):
                c["nev"] = nev
            cimjegyzek_ment(lista)
            return False           # már volt
    lista.append({"email": email_cim, "nev": nev or "", "db": 1,
                  "utoljara": time.time()})
    cimjegyzek_ment(lista)
    return True                    # új


def cimjegyzek_felvesz_szovegbol(szoveg):
    """Egy címzett-mező („Név <email>, ...") minden címét felveszi. Visszaad:
    hány ÚJ került be."""
    uj = 0
    for nev, cim in _cim_bont(szoveg):
        if cimjegyzek_felvesz(cim, nev):
            uj += 1
    return uj


def cimek_kinyerese_uzenetbol(msg):
    """Egy üzenet From/To/Cc címei [(nev, email), …] – a passzív tanuláshoz."""
    ki = []
    for fejlec in ("From", "To", "Cc"):
        ki += _cim_bont(msg.get(fejlec, ""))
    return ki


def cimjegyzek_megjelenit(c):
    """Egy kontakt megjeleníthető alakja: „Név <email>" vagy „email"."""
    nev = (c.get("nev") or "").strip()
    return f"{nev} <{c['email']}>" if nev else c.get("email", "")


def cimjegyzek_kereses(reszlet, limit=30):
    """A beírt szöveget TARTALMAZÓ címek (névben vagy e-mailben), gyakoriság +
    frissesség szerint rendezve (üres részletnél a leggyakoribbak)."""
    r = (reszlet or "").strip().lower()
    lista = cimjegyzek_betolt()

    def talalat(c):
        return (r in c.get("email", "").lower()
                or r in c.get("nev", "").lower())
    szurt = [c for c in lista if (not r or talalat(c))]
    szurt.sort(key=lambda c: (int(c.get("db", 0)), c.get("utoljara", 0)),
               reverse=True)
    return szurt[:limit]


# ---- fiókonkénti „új levél" értesítő (hang vagy felolvasott szöveg) ----
_ERTESITO_FILE = store.CONFIG_DIR / "mail_notify.json"


def ertesito_betolt():
    return dict(store.load_json(_ERTESITO_FILE, {}) or {})


def ertesito_fiok(email_cim):
    """Egy fiók értesítő-beállítása. Alap: felolvasott „Új leveled érkezett."."""
    d = ertesito_betolt().get((email_cim or "").lower())
    if not isinstance(d, dict):
        return {"tipus": "szoveg", "szoveg": "Új leveled érkezett.", "hang": ""}
    return {"tipus": d.get("tipus", "szoveg"),
            "szoveg": d.get("szoveg", "Új leveled érkezett."),
            "hang": d.get("hang", "")}


def ertesito_fiok_ment(email_cim, tipus, szoveg="", hang=""):
    """Értesítő mentése: tipus = 'nincs' | 'szoveg' | 'hang'."""
    d = ertesito_betolt()
    d[(email_cim or "").lower()] = {"tipus": tipus, "szoveg": szoveg,
                                    "hang": hang}
    store.save_json(_ERTESITO_FILE, d)


def cimjegyzek_torol(email_cim):
    """Egy cím törlése a címjegyzékből."""
    em = (email_cim or "").strip().lower()
    lista = [c for c in cimjegyzek_betolt() if c.get("email", "").lower() != em]
    cimjegyzek_ment(lista)


def cimjegyzek_frissit(email_cim, nev):
    """Egy meglévő cím nevének módosítása (vagy felvétele, ha még nincs)."""
    em = (email_cim or "").strip().lower()
    if "@" not in em:
        return
    lista = cimjegyzek_betolt()
    for c in lista:
        if c.get("email", "").lower() == em:
            c["nev"] = nev or ""
            cimjegyzek_ment(lista)
            return
    cimjegyzek_felvesz(em, nev)


# ---- általános beállítások (háttér-ellenőrzés stb.) ----
_ALTALANOS_FILE = store.CONFIG_DIR / "mail_settings.json"
_ALTALANOS_ALAP = {"auto_ellenoriz": True, "ellenoriz_perc": 3,
                   "lista_limit": 50}


def altalanos_betolt():
    d = dict(_ALTALANOS_ALAP)
    try:
        d.update(store.load_json(_ALTALANOS_FILE, {}) or {})
    except Exception:
        pass
    return d


def altalanos_ment(d):
    store.save_json(_ALTALANOS_FILE, dict(d))


def cimjegyzek_tanul(szovegek):
    """Passzív tanulás: több fejléc-cím (pl. a lista feladói) ÚJ címeit felveszi
    egyetlen mentéssel. A meglévők számlálóját NEM növeli (nehogy a frissítés
    felfújja). Visszaad: hány ÚJ cím került be."""
    import time
    lista = cimjegyzek_betolt()
    meglevo = {c.get("email", "").lower() for c in lista}
    uj = 0
    for sz in (szovegek or []):
        for nev, cim in _cim_bont(sz):
            if cim not in meglevo:
                lista.append({"email": cim, "nev": nev or "", "db": 1,
                              "utoljara": time.time()})
                meglevo.add(cim)
                uj += 1
    if uj:
        cimjegyzek_ment(lista)
    return uj


# ---- önlejátszó hang a levélben (Super Mailen belül) ----

def onlejatszo_hang(msg):
    """Ha a levél önlejátszó hangot hordoz (X-SuperMail-Autosound fejléc, vagy
    egyáltalán van hang-csatolmánya), visszaad: (fájlnév, bájtok); különben None.
    A megnyitáskori automatikus megszólaltatáshoz."""
    jelolt = (dekodol_fejlec(msg.get(AUTOSOUND_FEJLEC, "")) or "").strip().lower()
    hangok = [(n, a) for n, a in csatolmanyok(msg)
              if os.path.splitext(n)[1].lower() in _HANG_KITERJESZTESEK]
    if jelolt:
        for n, a in hangok:
            if n.lower() == jelolt:
                return (n, a)
    return hangok[0] if (jelolt and hangok) else None


# ---- OAuth2 (XOAUTH2) segéd -------------------------------------------------
# Az OAuth2-fiókoknál jelszó helyett rövid életű hozzáférési token megy –
# ezt a mail_oauth modul szerzi be/frissíti. Itt csak a SASL-sztringet gyártjuk.

def _xoauth2(felhasznalo, token):
    return (f"user={felhasznalo}\x01auth=Bearer {token}\x01\x01").encode()


def _oauth_e(fiok):
    return fiok.get("auth") == "oauth"


# ======================================================================
#  IMAP-kliens
# ======================================================================

class ImapKliens:
    """Vékony IMAP-burkoló: mappák, levéllista, teljes levél, jelölés, keresés.
    A rejtvény sosem megy sehová – közvetlenül a szolgáltató szerveréhez köt."""

    def __init__(self, fiok, token_lekero=None):
        self.fiok = fiok
        self.token_lekero = token_lekero      # OAuth2-fiókhoz: access token
        self.M = None

    def kapcsolodik(self):
        ctx = ssl.create_default_context()
        self.M = imaplib.IMAP4_SSL(self.fiok["imap_host"],
                                   int(self.fiok.get("imap_port", 993)),
                                   ssl_context=ctx)
        if _oauth_e(self.fiok) and self.token_lekero:
            token = self.token_lekero(self.fiok)
            self.M.authenticate(
                "XOAUTH2",
                lambda _: _xoauth2(self.fiok["felhasznalo"], token))
        else:
            self.M.login(self.fiok["felhasznalo"], self.fiok["jelszo"])
        return self

    def mappak(self):
        ki = []
        typ, adat = self.M.list()
        if typ != "OK":
            return ["INBOX"]
        for sor in adat:
            if not sor:
                continue
            resz = sor.decode("utf-8", "replace")
            # a mappa neve az utolsó idézőjeles/space utáni rész
            nev = resz.split(' "')[-1].strip().strip('"')
            if nev:
                ki.append(nev)
        return ki or ["INBOX"]

    def valaszt(self, mappa="INBOX"):
        typ, adat = self.M.select(mappa, readonly=False)
        return int(adat[0]) if typ == "OK" and adat and adat[0] else 0

    def _uid_lista(self, keresés="ALL", limit=50):
        typ, adat = self.M.uid("search", None, keresés)
        if typ != "OK" or not adat or not adat[0]:
            return []
        uidok = adat[0].split()
        return [u.decode() for u in uidok[-limit:][::-1]]   # legújabb elöl

    def lista(self, mappa="INBOX", limit=50):
        """A mappa legutóbbi leveleinek fejléc-infói (feladó, tárgy, dátum,
        olvasott, csatolmány) – UID-del."""
        self.valaszt(mappa)
        ki = []
        for uid in self._uid_lista("ALL", limit):
            typ, adat = self.M.uid(
                "fetch", uid,
                "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE TO)])")
            if typ != "OK" or not adat or not adat[0]:
                continue
            nyers = adat[0][1]
            flags = imaplib.ParseFlags(adat[0][0]) if adat[0][0] else ()
            msg = email.message_from_bytes(nyers)
            info = level_fejlec_info(msg)
            info["uid"] = uid
            info["olvasott"] = b"\\Seen" in flags
            ki.append(info)
        return ki

    def teljes(self, uid, mappa="INBOX"):
        """Egy levél teljes letöltése (email.message)."""
        self.valaszt(mappa)
        typ, adat = self.M.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not adat or not adat[0]:
            return None
        return email.message_from_bytes(adat[0][1])

    def olvasottnak(self, uid, mappa="INBOX"):
        self.valaszt(mappa)
        self.M.uid("store", uid, "+FLAGS", "(\\Seen)")

    def olvasatlannak(self, uid, mappa="INBOX"):
        self.valaszt(mappa)
        self.M.uid("store", uid, "-FLAGS", "(\\Seen)")

    def torol(self, uid, mappa="INBOX"):
        """VÉGLEGES törlés: \\Deleted jelölés + EXPUNGE. A szerver válaszát
        ELLENŐRZI, hogy ne jelezzünk hamis sikert. Hibát dob, ha elutasítja."""
        self.valaszt(mappa)
        typ, _ = self.M.uid("store", uid, "+FLAGS", "(\\Deleted)")
        if typ != "OK":
            raise RuntimeError("A szerver elutasította a törlés-jelölést.")
        typ, _ = self.M.expunge()
        if typ != "OK":
            raise RuntimeError("A szerver elutasította a végleges törlést "
                               "(EXPUNGE).")

    def masol(self, uid, cel_mappa, forras_mappa="INBOX"):
        """Levél(ek) MÁSOLÁSA a cél-mappába (a forrás megmarad). Az `uid` lehet
        egyetlen UID vagy vesszővel elválasztott UID-halmaz (kötegelt)."""
        self.valaszt(forras_mappa)
        typ, _ = self.M.uid("copy", uid, cel_mappa)
        return typ == "OK"

    def athelyez(self, uid, cel_mappa, forras_mappa="INBOX"):
        """Levél(ek) ÁTHELYEZÉSE a cél-mappába (kivágás → beillesztés). UID MOVE-ot
        használ, ha a szerver támogatja (RFC 6851); különben copy+delete+expunge.
        Az `uid` lehet vesszővel elválasztott UID-halmaz is."""
        self.valaszt(forras_mappa)
        try:
            typ, _ = self.M.uid("move", uid, cel_mappa)
            if typ == "OK":
                return True
        except Exception:
            pass
        typ, _ = self.M.uid("copy", uid, cel_mappa)
        if typ != "OK":
            return False
        self.M.uid("store", uid, "+FLAGS", "(\\Deleted)")
        self.M.expunge()
        return True

    def legujabb_uid(self, mappa="INBOX"):
        """A mappa LEGNAGYOBB (legfrissebb) UID-ja – pehelysúlyú új-levél
        ellenőrzéshez (nem tölt le fejlécet)."""
        self.valaszt(mappa)
        typ, adat = self.M.uid("search", None, "ALL")
        if typ != "OK" or not adat or not adat[0]:
            return 0
        uidok = adat[0].split()
        try:
            return int(uidok[-1]) if uidok else 0
        except (ValueError, IndexError):
            return 0

    def keres(self, kifejezes, mappa="INBOX", limit=50):
        """Szerver-oldali keresés (feladó VAGY tárgy VAGY törzs)."""
        self.valaszt(mappa)
        krit = f'(OR OR FROM "{kifejezes}" SUBJECT "{kifejezes}" ' \
               f'TEXT "{kifejezes}")'
        ki = []
        for uid in self._uid_lista(krit, limit):
            typ, adat = self.M.uid(
                "fetch", uid,
                "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE TO)])")
            if typ == "OK" and adat and adat[0]:
                msg = email.message_from_bytes(adat[0][1])
                info = level_fejlec_info(msg)
                info["uid"] = uid
                info["olvasott"] = (adat[0][0] and
                                    b"\\Seen" in imaplib.ParseFlags(adat[0][0]))
                ki.append(info)
        return ki

    def bezar(self):
        try:
            self.M.logout()
        except Exception:
            pass


# ======================================================================
#  POP3-kliens (csak Beérkezett; letölt)
# ======================================================================

class Pop3Kliens:
    def __init__(self, fiok, token_lekero=None):
        self.fiok = fiok
        self.token_lekero = token_lekero
        self.P = None

    def kapcsolodik(self):
        import base64
        ctx = ssl.create_default_context()
        self.P = poplib.POP3_SSL(self.fiok["pop_host"],
                                 int(self.fiok.get("pop_port", 995)),
                                 context=ctx)
        if _oauth_e(self.fiok) and self.token_lekero:
            token = self.token_lekero(self.fiok)
            b64 = base64.b64encode(
                _xoauth2(self.fiok["felhasznalo"], token)).decode()
            self.P._shortcmd("AUTH XOAUTH2 " + b64)
        else:
            self.P.user(self.fiok["felhasznalo"])
            self.P.pass_(self.fiok["jelszo"])
        return self

    def lista(self, limit=50):
        """A postafiók legutóbbi leveleinek fejléc-infói (sorszámmal)."""
        db = len(self.P.list()[1])
        ki = []
        for i in range(db, max(0, db - limit), -1):
            nyers = b"\r\n".join(self.P.retr(i)[1])
            msg = email.message_from_bytes(nyers)
            info = level_fejlec_info(msg)
            info["szam"] = i
            info["olvasott"] = True         # POP3-nál nincs szerver-oldali flag
            ki.append(info)
        return ki

    def teljes(self, szam):
        nyers = b"\r\n".join(self.P.retr(int(szam))[1])
        return email.message_from_bytes(nyers)

    def torol(self, szam):
        self.P.dele(int(szam))

    def bezar(self):
        try:
            self.P.quit()
        except Exception:
            pass


# ======================================================================
#  SMTP-küldő
# ======================================================================

class SmtpKuldo:
    def __init__(self, fiok, token_lekero=None):
        self.fiok = fiok
        self.token_lekero = token_lekero

    def _belep(self, s):
        if _oauth_e(self.fiok) and self.token_lekero:
            import base64
            token = self.token_lekero(self.fiok)
            b64 = base64.b64encode(
                _xoauth2(self.fiok["felhasznalo"], token)).decode()
            s.ehlo()
            kod, valasz = s.docmd("AUTH", "XOAUTH2 " + b64)
            if kod not in (235, 334):
                raise smtplib.SMTPAuthenticationError(kod, valasz)
        else:
            s.login(self.fiok["felhasznalo"], self.fiok["jelszo"])

    def kuld(self, msg):
        host = self.fiok["smtp_host"]
        port = int(self.fiok.get("smtp_port", 465))
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx) as s:
                self._belep(s)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as s:
                s.ehlo()
                s.starttls(context=ctx)
                self._belep(s)
                s.send_message(msg)
