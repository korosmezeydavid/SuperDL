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
import time
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
    """A lista-nézethez: feladó, tárgy, dátum, van-e csatolmány.

    A SZABÁLYOKHOZ néhány további mező is kell (levelezőlista, hírlevél-jelleg,
    másolat, azonosító). Ezek olcsók – ugyanabban a fejléc-letöltésben jönnek –,
    és nélkülük a „minden erről a listáról" típusú szabály nem volna
    megfogalmazható."""
    van_csat = any(
        (r.get_filename() or (r.get_content_disposition() == "attachment"))
        for r in msg.walk()) if msg.is_multipart() else bool(msg.get_filename())
    lista_id = dekodol_fejlec(msg.get("List-Id", ""))
    leiratkozas = dekodol_fejlec(msg.get("List-Unsubscribe", ""))
    # „tömeges küldemény": a hírlevelek/reklámok szabvány szerint jelölik
    # magukat – vagy leiratkozó fejléccel, vagy a Precedence/Auto-Submitted
    # mezővel. Ez a jelölés a KÜLDŐÉ, tehát megbízhatóbb bármilyen
    # szó-kitalálásnál (a „reklám" szóra keresés téves találatokat adna).
    precedence = _norm_fejlec(msg.get("Precedence", ""))
    marketing = bool(leiratkozas) or precedence in ("bulk", "list", "junk")
    return {
        "felado": dekodol_fejlec(msg.get("From", "")),
        "targy": dekodol_fejlec(msg.get("Subject", "(nincs tárgy)")),
        "datum": dekodol_fejlec(msg.get("Date", "")),
        "cimzett": dekodol_fejlec(msg.get("To", "")),
        "masolat": dekodol_fejlec(msg.get("Cc", "")),
        "csatolmany": bool(van_csat),
        "lista_id": lista_id,
        "leiratkozas": leiratkozas,
        "marketing": marketing,
        "azonosito": (msg.get("Message-ID", "") or "").strip(),
        "valaszcim": dekodol_fejlec(msg.get("Reply-To", "")),
        "leiratkozas_post": dekodol_fejlec(
            msg.get("List-Unsubscribe-Post", "")),
        "valasz_erre": (msg.get("In-Reply-To", "") or "").strip(),
        "hivatkozasok": (msg.get("References", "") or "").strip(),
    }


def _norm_fejlec(ertek) -> str:
    return str(ertek or "").strip().lower()


_ALAIRAS_TIPUSOK = ("PKCS7-SIGNATURE", "PKCS7-MIME", "PGP-SIGNATURE",
                    "X-PKCS7-SIGNATURE", "PGP-KEYS")


def csatolmany_a_szerkezetbol(nyers) -> bool:
    """Van-e CSATOLMÁNY a levélben – a levél SZERKEZETE (IMAP BODYSTRUCTURE)
    alapján, a teljes levél letöltése nélkül.

    MIÉRT KELL: a listához csak a fejléceket töltjük le (gyors, keveset
    forgalmaz), a csatolmány viszont a levél TESTÉBEN van. Emiatt a lista
    eddig SOSEM tudta, hogy van-e melléklet – egy felhasználó jelezte, hogy
    így „elsikkad a melléklet”. A BODYSTRUCTURE viszont pont a szerkezetet
    írja le, és ugyanabban a lekérésben megkapható.

    Amit csatolmánynak veszünk:
      • aminek a szerkezete „attachment” elhelyezést jelöl;
      • a nevesített (fájlnevet kapott) alkalmazás-részek – ezeket a
        levelezők is mellékletként mutatják.
    Amit NEM: a levél testébe ágyazott képek (inline, cid:) és a digitális
    aláírások – ezek nem melléklet, és ha jeleznénk őket, a jelzés
    elértéktelenedne."""
    if not nyers:
        return False
    if isinstance(nyers, (bytes, bytearray)):
        nyers = bytes(nyers).decode("utf-8", "replace")
    nagy = str(nyers).upper()
    if "BODYSTRUCTURE" not in nagy and "BODY (" not in nagy:
        return False

    # RÉSZENKÉNT vizsgálunk, nem az egész szövegben keresünk: egy aláírt
    # levélben ugyanis az aláírás-rész is „APPLICATION", fájlnévvel – ha
    # globálisan néznénk, minden aláírt levélre csatolmányt jeleznénk.
    for i in _reszek_kezdetei(nagy, '("APPLICATION"'):
        resz = nagy[i:i + 400]
        altipus = ""
        m = re.match(r'\("APPLICATION"\s+"([^"]+)"', resz)
        if m:
            altipus = m.group(1)
        if any(a in altipus for a in _ALAIRAS_TIPUSOK):
            continue                       # digitális aláírás: nem melléklet
        if ('"ATTACHMENT"' in resz or '"NAME"' in resz
                or '"FILENAME"' in resz):
            return True

    # nem alkalmazás-típusú melléklet (kép, hang, szöveg csatolmányként):
    # ilyenkor az „attachment" elhelyezés-jelölés a döntő – a levél testébe
    # ágyazott képek ugyanis „inline" jelölést kapnak
    for i in _reszek_kezdetei(nagy, '"ATTACHMENT"'):
        elozmeny = nagy[max(0, i - 300):i]
        if not any(a in elozmeny for a in _ALAIRAS_TIPUSOK):
            return True
    return False


def _reszek_kezdetei(szoveg: str, minta: str):
    """A minta összes előfordulásának kezdőpozíciója."""
    hely, ki = szoveg.find(minta), []
    while hely >= 0:
        ki.append(hely)
        hely = szoveg.find(minta, hely + 1)
    return ki


def _meret_a_metabol(meta) -> int:
    """A levél mérete bájtban, az IMAP válasz meta-részéből (RFC822.SIZE).
    Ha a szerver nem adja meg, 0 – a méret-feltétel ilyenkor nem illeszkedik
    (inkább ne tegyen semmit, mint hogy rosszul döntsön)."""
    m = re.search(rb"RFC822\.SIZE (\d+)", meta or b"")
    return int(m.group(1)) if m else 0


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


def level_html_torzs(msg) -> str:
    """A levél HTML része nyersen (üres, ha nincs).

    A biztonsági ellenőrzéshez kell: a megtévesztő hivatkozás („OTP Bank” néven
    egy orosz cím) CSAK a HTML-forrásban látszik – a szöveggé alakított
    változatban már nem."""
    if msg.is_multipart():
        for resz in msg.walk():
            if resz.is_multipart():
                continue
            if resz.get_content_disposition() == "attachment":
                continue
            if resz.get_content_type() == "text/html":
                return _resz_szoveg(resz)
        return ""
    return _resz_szoveg(msg) if msg.get_content_type() == "text/html" else ""


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


def felado_fejlec(fiok):
    """A kimenő levél „From” fejléce: „Név <cim@pelda.hu>”, ha a fiókhoz van
    megjelenítendő NÉV; különben a puszta cím.

    MIÉRT FONTOS (tesztelői visszajelzés): eddig CSAK a nyers e-mail címet
    küldtük feladóként, ezért a címzett levelezője (és a képernyőolvasója) a
    hosszú e-mail címet mondta be a neved helyett. A név a fiók beállításából
    (Fiókok → Név) jön."""
    cim = (fiok.get("email") or "").strip()
    nev = (fiok.get("nev") or "").strip()
    if nev and nev.lower() != cim.lower():
        return email.utils.formataddr((nev, cim))
    return cim


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
    # SAJÁT AZONOSÍTÓ: enélkül a szerver adja, mi pedig nem tudnánk, melyik
    # levélre jött vissza az olvasási visszaigazolás (tértivevény).
    m["Message-ID"] = email.utils.make_msgid(domain=_domain(felado) or None)
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


def cimjegyzek_becenev(email_cim, becenev):
    """BECENÉV egy címhez: „anyu”, „doki”, „lista”.

    Vakon ez sokat ér: nem kell hosszú címet betűzni, elég a becenév. A
    keresés a becenevet is nézi, és a becenévvel PONTOSAN egyező találat
    kerül előre."""
    em = (email_cim or "").strip().lower()
    lista = cimjegyzek_betolt()
    for c in lista:
        if c.get("email", "").lower() == em:
            c["becenev"] = (becenev or "").strip()
            cimjegyzek_ment(lista)
            return True
    return False


def cimjegyzek_kereses(reszlet, limit=30):
    """A beírt szöveget TARTALMAZÓ címek (névben, e-mailben vagy BECENÉVBEN),
    gyakoriság + frissesség szerint rendezve (üres részletnél a
    leggyakoribbak). A becenévvel PONTOSAN egyező találat mindig legelöl van."""
    r = (reszlet or "").strip().lower()
    lista = cimjegyzek_betolt()

    def talalat(c):
        return (r in c.get("email", "").lower()
                or r in c.get("nev", "").lower()
                or r in (c.get("becenev", "") or "").lower())

    def pontos_becenev(c):
        return bool(r) and (c.get("becenev", "") or "").lower() == r
    szurt = [c for c in lista if (not r or talalat(c))]
    szurt.sort(key=lambda c: (pontos_becenev(c), int(c.get("db", 0)),
                              c.get("utoljara", 0)), reverse=True)
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
# ---------------------------------------------------------------------------
# ALÁÍRÁS
# ---------------------------------------------------------------------------

# A felhasználó által SZERKESZTHETŐ (akár törölhető) alapértelmezett aláírás.
# A „Super Mail-lel küldve" SZÁNDÉKOSAN nincs benne: azt a fix zárósor mondja
# ki a levél legalján, és kétszer leírva bántóan ismételne.
ALAP_ALAIRAS = ("Super DL: ahol a hozzáférés nem termék, hanem jog.\n"
                "https://super-dl.com")

# A levél legaljára KERÜLŐ, rövid zárósor. Szándékosan link nélküli és egy
# soros: a linkes-reklámos lábléceket a szigorúbb spamszűrők pontozzák, és egy
# hosszú blokk minden levélben mások postaládájában is zavaró lenne.
FIX_ZAROSOR = "Super Mail-lel küldve."


def torzs_zarosorral(torzs: str) -> str:
    """KÜLDÉSKOR: a levél szövege + a fix zárósor a legaljára.

    Az aláírást NEM tesszük hozzá újra: az már a szerkesztőben ott van (a
    levélíró ablak illeszti be nyitáskor), és a felhasználó akár át is írta
    vagy törölte – az az ő döntése. Ha a zárósor már szerepel a szövegben,
    nem duplázzuk."""
    torzs = (torzs or "").rstrip()
    if FIX_ZAROSOR in torzs:
        return torzs + "\n"
    return (torzs + "\n\n" + FIX_ZAROSOR).strip() + "\n"


def torzs_alairassal(torzs: str, alairas: str = None) -> str:
    """A levél szövege + a felhasználó aláírása + a fix zárósor. (A levélíró
    ablak a szerkesztőbe illesztéshez használja az aláírás-részt; a küldéshez a
    `torzs_zarosorral` való.) Semmit nem teszünk be kétszer."""
    torzs = (torzs or "").rstrip()
    if alairas is None:
        alairas = altalanos_betolt().get("alairas", ALAP_ALAIRAS)
    alairas = (alairas or "").strip()
    if alairas and alairas not in torzs:
        torzs = (torzs + "\n\n-- \n" + alairas).strip()
    return torzs_zarosorral(torzs)


_ALTALANOS_ALAP = {"auto_ellenoriz": True, "ellenoriz_perc": 3,
                   "lista_limit": 50,
                   # mi jelenjen meg a levéllista soraiban (testreszabható)
                   "lista_allapot": True,   # „olvasatlan” szóval
                   "lista_felado": True,    # a feladó NEVE
                   "lista_cim": False,      # a feladó e-mail CÍME
                   "lista_targy": True,
                   "lista_ido": True,
                   # helyesírás-ellenőrzés küldés előtt (a levélírás
                   # helyi menüjéből kapcsolható)
                   "helyesiras": True,
                   # a lista szélén: „bling" vagy „beszed"
                   "lista_szel": "bling",
                   # küldés előtti rákérdezés (a párbeszédben kikapcsolható,
                   # ITT bármikor visszakapcsolható – sose legyen egyirányú utca)
                   "kuldes_kerdes": True,
                   # ALÁÍRÁS: szabadon szerkeszthető, akár teljesen törölhető
                   "alairas": ALAP_ALAIRAS,
                   # induláskor az „Összes bejövő" jöjjön-e (több fióknál)
                   "indulo_osszes": True,
                   "utolso_fiok": "",
                   # az Összes bejövő nézet háttér-figyelése (perc)
                   "osszes_perc": 3,
                   # értesítő hang mindenkinek (MK3)
                   "ertesito_hang_be": True,
                   "ertesito_hang_fajl": "",
                   # a szabályok automatikus futtatása az ÚJ leveleken
                   "szabalyok_auto": True,
                   # küldés visszavonása: ennyi másodpercig vár a levél
                   "visszavonas_mp": 10,
                   # tértivevény: kérjük-e, és mit tegyünk, ha tőlünk kérik
                   "tertivevony_keres": False,
                   "tertivevony_valasz": "kerdez",
                   # válasz után bezáruljon-e az eredeti levél ablaka
                   "valasz_zarja_eredetit": False}


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

    def mappa_letrehoz(self, nev):
        """Mappa létrehozása (IMAP CREATE) – a szabályok ezzel tudnak új
        mappába rendezni anélkül, hogy a felhasználónak előbb kézzel kellene
        létrehoznia.

        Ha a mappa MÁR LÉTEZIK, azt SIKERNEK vesszük: a hívó szándéka az, hogy
        „legyen ilyen mappa”, és az teljesült. (A szerverek eltérő hibaszöveget
        adnak erre, ezért a meglétet a mappalistából ellenőrizzük.)"""
        nev = str(nev or "").strip()
        if not nev:
            raise ValueError("Üres mappanév.")
        meglevo = {m.strip().strip('"').lower() for m in self.mappak()}
        if nev.lower() in meglevo:
            return nev
        typ, adat = self.M.create(self._mappa_arg(nev))
        if typ != "OK":
            # Utolsó ellenőrzés: hátha versenyhelyzet volt, és közben létrejött.
            if nev.lower() in {m.strip().strip('"').lower()
                               for m in self.mappak()}:
                return nev
            uzenet = b" ".join(x for x in (adat or []) if isinstance(x, bytes))
            raise RuntimeError("A mappa létrehozása nem sikerült: "
                               + uzenet.decode("utf-8", "replace")[:200])
        try:                       # a Gmail csak feliratkozás után mutatja
            self.M.subscribe(self._mappa_arg(nev))
        except Exception:
            pass
        return nev

    @staticmethod
    def _mappa_arg(nev):
        """A mappanevet IMAP-argumentumként idézőjelezi, ha kell (szóköz vagy
        speciális karakter, pl. a Gmail „[Gmail]/Összes levél”). Enélkül a
        szerver a szóköznél elvágja a nevet és hibázik."""
        nev = str(nev or "INBOX")
        if nev.startswith('"'):
            return nev
        if " " in nev or nev.startswith("[") or "/" in nev:
            return '"' + nev.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return nev

    def valaszt(self, mappa="INBOX"):
        typ, adat = self.M.select(self._mappa_arg(mappa), readonly=False)
        return int(adat[0]) if typ == "OK" and adat and adat[0] else 0

    def _uid_lista(self, keresés="ALL", limit=50, offset=0):
        typ, adat = self.M.uid("search", None, keresés)
        if typ != "OK" or not adat or not adat[0]:
            return []
        # LEGÚJABB ELÖL: UID szerint csökkenő, majd offset-től limit darab (lapozás)
        uidok = sorted((int(u) for u in adat[0].split()), reverse=True)
        return [str(u) for u in uidok[offset:offset + limit]]

    _FEJLEC_FETCH = ("(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS "
                     "(FROM SUBJECT DATE TO CC MESSAGE-ID LIST-ID "
                     "LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST PRECEDENCE REPLY-TO "
                     "IN-REPLY-TO REFERENCES)] BODYSTRUCTURE)")

    def lista(self, mappa="INBOX", limit=50, offset=0):
        """A mappa leveleinek fejléc-infói (LEGÚJABB ELÖL), LAPOZÁSSAL.

        Elsődlegesen SZEKVENCIA-tartománnyal tölt (gyors, és a nagy Gmail-
        mappákhoz – Összes levél, Fontos – SEM kell a teljes UID-listát
        letölteni); ha az valamiért nem megy, UID-keresésre esik vissza."""
        exists = self.valaszt(mappa)
        if not exists:
            return []
        try:
            sor = self._lista_szekvenciaval(exists, limit, offset)
            if sor is not None:
                return sor
        except Exception:
            pass
        return self._lista_uidokkal(mappa, limit, offset)

    def _lista_szekvenciaval(self, exists, limit, offset):
        felso = exists - offset
        if felso < 1:
            return []
        also = max(1, felso - limit + 1)
        typ, adat = self.M.fetch(f"{also}:{felso}", self._FEJLEC_FETCH)
        if typ != "OK" or adat is None:
            return None
        ki = []
        for item in adat:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            meta, nyers = item[0], item[1]
            m = re.search(rb"UID (\d+)", meta or b"")
            uid = m.group(1).decode() if m else ""
            flags = imaplib.ParseFlags(meta) if meta else ()
            msg = email.message_from_bytes(nyers)
            info = level_fejlec_info(msg)
            info["uid"] = uid
            info["meret"] = _meret_a_metabol(meta)
            # CSATOLMÁNY a levél szerkezetéből: a listához nem töltjük le a
            # levél testét, ezért enélkül a melléklet SOSEM látszana.
            info["csatolmany"] = csatolmany_a_szerkezetbol(meta)
            info["olvasott"] = b"\\Seen" in flags
            ki.append(info)
        ki.reverse()        # a fetch NÖVEKVŐ szekvencia-sorrendben ad → legújabb elöl
        return ki

    def _lista_uidokkal(self, mappa, limit, offset):
        self.valaszt(mappa)
        ki = []
        for uid in self._uid_lista("ALL", limit, offset):
            typ, adat = self.M.uid("fetch", uid, self._FEJLEC_FETCH)
            if typ != "OK" or not adat or not adat[0]:
                continue
            meta, nyers = adat[0][0], adat[0][1]
            flags = imaplib.ParseFlags(meta) if meta else ()
            msg = email.message_from_bytes(nyers)
            info = level_fejlec_info(msg)
            info["uid"] = uid
            info["meret"] = _meret_a_metabol(meta)
            # CSATOLMÁNY a levél szerkezetéből: a listához nem töltjük le a
            # levél testét, ezért enélkül a melléklet SOSEM látszana.
            info["csatolmany"] = csatolmany_a_szerkezetbol(meta)
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
        typ, _ = self.M.uid("copy", uid, self._mappa_arg(cel_mappa))
        return typ == "OK"

    def athelyez(self, uid, cel_mappa, forras_mappa="INBOX"):
        """Levél(ek) ÁTHELYEZÉSE a cél-mappába (kivágás → beillesztés). UID MOVE-ot
        használ, ha a szerver támogatja (RFC 6851); különben copy+delete+expunge.
        Az `uid` lehet vesszővel elválasztott UID-halmaz is."""
        self.valaszt(forras_mappa)
        cel = self._mappa_arg(cel_mappa)
        try:
            typ, _ = self.M.uid("move", uid, cel)
            if typ == "OK":
                return True
        except Exception:
            pass
        typ, _ = self.M.uid("copy", uid, cel)
        if typ != "OK":
            return False
        self.M.uid("store", uid, "+FLAGS", "(\\Deleted)")
        self.M.expunge()
        return True

    def piszkozat_mappa(self):
        r"""A szolgáltató PISZKOZATOK mappája. Nem találgatunk vakon: előbb a
        szerver saját jelöléseit (RFC 6154 \Drafts) nézzük, és csak utána a
        szokásos neveket – így a Gmail „[Gmail]/Vázlatok" vagy egy német
        „Entwürfe" is megtalálható."""
        try:
            typ, adat = self.M.list()
        except Exception:
            return ""
        if typ != "OK" or not adat:
            return ""
        jeloltek = []
        for sor in adat:
            szoveg = sor.decode("utf-8", "replace") if isinstance(sor, bytes) else str(sor)
            nev = szoveg.split(' "', 2)[-1].strip().strip('"')
            if r"\Drafts" in szoveg:          # a szerver MAGA jelölte meg
                return nev
            jeloltek.append(nev)
        for n in jeloltek:
            kicsi = n.lower()
            if any(k in kicsi for k in ("draft", "piszkoz", "vázlat", "vazlat",
                                        "entw", "brouillon")):
                return n
        return ""

    def piszkozat_ment(self, msg, mappa=""):
        r"""A megírt levél elmentése a szolgáltató PISZKOZATOK mappájába
        (IMAP APPEND, `\Draft` jelzéssel). Így a telefonodon is ott lesz.
        Visszaadja a mappa nevét; ha nincs hova, üres sztringet."""
        mappa = mappa or self.piszkozat_mappa()
        if not mappa:
            return ""
        nyers = msg.as_bytes() if hasattr(msg, "as_bytes") else bytes(msg)
        ido = imaplib.Time2Internaldate(time.time())
        typ, _ = self.M.append(self._mappa_arg(mappa), r"\Draft", ido, nyers)
        return mappa if typ == "OK" else ""

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

    def keres(self, kifejezes, mappa="INBOX", limit=50, offset=0):
        """Szerver-oldali keresés (feladó VAGY tárgy VAGY törzs)."""
        self.valaszt(mappa)
        krit = f'(OR OR FROM "{kifejezes}" SUBJECT "{kifejezes}" ' \
               f'TEXT "{kifejezes}")'
        ki = []
        for uid in self._uid_lista(krit, limit, offset):
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

    def lista(self, limit=50, offset=0):
        """A postafiók legutóbbi leveleinek fejléc-infói (sorszámmal), lapozva."""
        db = len(self.P.list()[1])
        felso = db - offset
        ki = []
        for i in range(felso, max(0, felso - limit), -1):
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

    def max_meret(self) -> int:
        """A kiszolgáló VALÓDI méretkorlátja (RFC 1870 SIZE), bájtban.
        Nem tippelünk 25 megabájtot: a Gmail, a Freemail és egy céges szerver
        is mást enged. Ha a szerver nem mondja meg, nullát adunk vissza."""
        host = self.fiok["smtp_host"]
        port = int(self.fiok.get("smtp_port", 465))
        ctx = ssl.create_default_context()
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                    s.ehlo()
                    return int(s.esmtp_features.get("size", 0) or 0)
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                try:
                    s.starttls(context=ctx)
                    s.ehlo()
                except Exception:
                    pass
                return int(s.esmtp_features.get("size", 0) or 0)
        except Exception:
            return 0

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


# ---------------------------------------------------------------------------
# ÖSSZES BEJÖVŐ – az egyesített nézet segédei (wx-mentes, tesztelhető)
# ---------------------------------------------------------------------------

OSSZES_MAPPA = "\x00OSSZES"        # ál-mappanév: sosem ütközik valódi IMAP-névvel
OSSZES_NEV = "Összes bejövő (minden fiók)"


def datum_kulcs(info) -> float:
    """Egy levél rendezési kulcsa: a küldés ideje másodpercben (UTC).

    Miért kell? Az egyesített nézetben a levelek eddig FIÓKONKÉNT, egymás után
    kerültek a listába (előbb az első fiók 30 levele, aztán a másodiké…), ami
    tíz fiókkal nem egyesített postaláda, hanem tíz egymás alá ragasztott lista.
    Hiányzó vagy értelmezhetetlen dátum → 0.0, vagyis a lista végére kerül (a
    dátum nélküli levelet nem tesszük a friss levelek elé)."""
    nyers = (info or {}).get("datum") or ""
    try:
        d = email.utils.parsedate_to_datetime(nyers)
    except (TypeError, ValueError):
        return 0.0
    if d is None:
        return 0.0
    try:
        if d.tzinfo is None:            # időzóna nélküli fejléc: helyi időnek vesszük
            d = d.astimezone()
        return d.timestamp()
    except (OverflowError, OSError, ValueError):
        return 0.0


def rendez_ido_szerint(lista) -> list:
    """A legfrissebb levél elöl. Stabil: az azonos idejűek megtartják a
    beérkezési sorrendjüket, így a lista nem ugrál frissítésenként."""
    return sorted(list(lista or []), key=datum_kulcs, reverse=True)


# ---------------------------------------------------------------------------
# HTML-LEVÉL – jelölésekből (a szerkesztő SIMA SZÖVEG marad)
# ---------------------------------------------------------------------------
#
# Miért így? Egy formázott (rich text) szerkesztő vakon rémálom: a
# képernyőolvasók akadoznak rajta, a kurzor ugrál. Ezért a felhasználó SIMA
# SZÖVEGET ír, benne LÁTHATÓ, FELOLVASHATÓ jelölésekkel:
#     [itt éred el](https://pelda.hu)      → kattintható hivatkozás
#     [kép: naplemente.jpg]                → a levél testébe ágyazott kép
# Küldéskor ebből KÉT változat készül (multipart/alternative): egy HTML és egy
# sima szöveges. A szöveges rész nem udvariassági gesztus: sok vak felhasználó
# levelezője ezt olvassa, és a spamszűrők is jobban fogadják.

LINK_JELOLO = re.compile(r"\[([^\]\n]*)\]\((https?://[^\s)]+)\)")
KEP_JELOLO = re.compile(r"\[kép:\s*([^\]\n]+)\]", re.IGNORECASE)


def van_html_jeloles(szoveg: str) -> bool:
    """Van-e a szövegben olyan jelölés, amiért érdemes HTML-t is küldeni?
    Ha nincs, marad a sima szöveg – fölösleges HTML-t nem gyártunk."""
    sz = szoveg or ""
    return bool(LINK_JELOLO.search(sz) or KEP_JELOLO.search(sz))


def _html_ovatos(sz: str) -> str:
    return (sz.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def jelolesek_szovegge(szoveg: str) -> str:
    """A jelölések EMBERI szöveggé – ez megy a sima szöveges részbe.
    A hivatkozás így néz ki: „itt éred el: https://…” – tehát a cím akkor is
    megvan, ha a címzett csak a szöveges változatot látja."""
    def link(m):
        cimke, url = (m.group(1) or "").strip(), m.group(2)
        return "%s: %s" % (cimke, url) if cimke else url
    ki = LINK_JELOLO.sub(link, szoveg or "")
    return KEP_JELOLO.sub(lambda m: "[kép: %s]" % m.group(1).strip(), ki)


def jelolesek_htmlbe(szoveg: str, kep_cid: dict | None = None) -> str:
    """A jelölések HTML-lé. `kep_cid`: {fájlnév: cid} a beágyazott képekhez."""
    kep_cid = kep_cid or {}
    darabok, utolso = [], 0
    for m in LINK_JELOLO.finditer(szoveg or ""):
        darabok.append(_html_ovatos(szoveg[utolso:m.start()]))
        cimke = (m.group(1) or "").strip() or m.group(2)
        darabok.append('<a href="%s">%s</a>'
                       % (_html_ovatos(m.group(2)), _html_ovatos(cimke)))
        utolso = m.end()
    darabok.append(_html_ovatos((szoveg or "")[utolso:]))
    ki = "".join(darabok)

    def kep(m):
        nev = m.group(1).strip()
        cid = kep_cid.get(nev) or kep_cid.get(os.path.basename(nev))
        if not cid:
            return _html_ovatos("[kép: %s]" % nev)
        # az `alt` NEM dísz: a vak címzett ezt hallja a kép helyén
        return ('<img src="cid:%s" alt="%s" style="max-width:100%%">'
                % (cid, _html_ovatos(nev)))

    ki = KEP_JELOLO.sub(kep, ki)
    return ("<html><body style=\"font-family:sans-serif\">%s</body></html>"
            % ki.replace("\n", "<br>\n"))


def level_epit_html(felado, cimzett, targy, torzs, masolat="",
                    csatolmanyok_lista=None, valasz_id=None, titkos="",
                    kepek=None):
    """HTML + sima szöveges levél (multipart/alternative), beágyazott képekkel.
    `kepek`: a levél testébe ágyazandó képfájlok útjai. A többi csatolmány a
    szokásos módon megy."""
    kepek = list(kepek or [])
    cidek = {}
    for i, ut in enumerate(kepek):
        cidek[os.path.basename(ut)] = "kep%d@superdl" % (i + 1)

    m = EmailMessage()
    m["From"] = felado
    m["To"] = cimzett
    if masolat:
        m["Cc"] = masolat
    if titkos:
        m["Bcc"] = titkos
    m["Subject"] = targy or "(nincs tárgy)"
    m["Message-ID"] = email.utils.make_msgid(domain=_domain(felado) or None)
    if valasz_id:
        m["In-Reply-To"] = valasz_id
        m["References"] = valasz_id
    m.set_content(jelolesek_szovegge(torzs or ""))
    m.add_alternative(jelolesek_htmlbe(torzs or "", cidek), subtype="html")

    html_resz = m.get_payload()[-1]
    for ut in kepek:
        try:
            with open(ut, "rb") as f:
                adat = f.read()
        except OSError:
            continue
        tipus, _ = mimetypes.guess_type(ut)
        al = (tipus.split("/", 1)[1] if tipus and tipus.startswith("image/")
              else "png")
        html_resz.add_related(adat, maintype="image", subtype=al,
                              cid="<%s>" % cidek[os.path.basename(ut)],
                              filename=os.path.basename(ut))
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


# ---------------------------------------------------------------------------
# NAGY FÁJLOK: a szolgáltató VALÓDI korlátja + feltöltés megosztóra
# ---------------------------------------------------------------------------

# Nem tippelünk 25 megabájtot: a levél mérete a KÓDOLT méret (a base64 kb.
# 33%-kal hizlal), és minden szolgáltatónál más a korlát. Az SMTP-kiszolgáló
# belépéskor MEGMONDJA a sajátját (RFC 1870 SIZE) – azt kérdezzük meg.
ALAP_MERETKORLAT = 25 * 1024 * 1024      # csak végső tartalék, ha nem mondja meg


def becsult_meret(torzs: str, csatolmanyok=None, kepek=None) -> int:
    """A leendő levél KÓDOLT mérete bájtban (base64 = +33%, plusz fejlécek)."""
    meret = len((torzs or "").encode("utf-8", "replace")) + 4096
    for ut in list(csatolmanyok or []) + list(kepek or []):
        try:
            meret += int(os.path.getsize(ut) * 4 / 3) + 512
        except OSError:
            continue
    return meret


def meret_szoveg(bajt: int) -> str:
    if bajt >= 1024 * 1024:
        return "%.1f megabájt" % (bajt / 1024 / 1024)
    return "%.0f kilobájt" % (bajt / 1024)


# Fájlmegosztók. Cserélhető lista, mert ezek a szolgáltatások jönnek-mennek
# (a transfer.sh évekig szabvány volt, aztán elhalt) – ha az egyik nem megy,
# a hívó szólhat és válthat. A filebin.net kulcs nélküli, dokumentált API.
MEGOSZTOK = [
    {"id": "filebin", "nev": "filebin.net (7 napig él, kulcs nélkül)",
     "url": "https://filebin.net/%(bin)s/%(fajl)s",
     "letoltes": "https://filebin.net/%(bin)s"},
]


def megoszto_feltolt(ut: str, megoszto: str = "filebin", halad=None) -> dict:
    """Egy fájl feltöltése egy nyilvános megosztóra. Visszaad: {"url", "lejar",
    "nev"}.

    ADATVÉDELEM: ezek a tárhelyek NYILVÁNOSAK – akinek megvan a link, letöltheti,
    és nincs titkosítás. Ezért a hívónak KÖTELESSÉGE ezt kimondani és külön
    engedélyt kérni, mielőtt ideküld bármit."""
    import json as _json
    import secrets
    import urllib.request
    nev = os.path.basename(ut)
    biztos_nev = re.sub(r"[^A-Za-z0-9._-]", "_", nev) or "fajl"
    bin_nev = "superdl-" + secrets.token_hex(8)
    with open(ut, "rb") as f:
        adat = f.read()
    if halad:
        halad(0.1)
    m = next((x for x in MEGOSZTOK if x["id"] == megoszto), MEGOSZTOK[0])
    cel = m["url"] % {"bin": bin_nev, "fajl": biztos_nev}
    keres = urllib.request.Request(
        cel, data=adat, method="POST",
        headers={"Content-Type": "application/octet-stream",
                 "User-Agent": "SuperDL-mail/1.0", "accept": "application/json"})
    with urllib.request.urlopen(keres, timeout=900) as v:
        valasz = v.read().decode("utf-8", "replace")
    if halad:
        halad(1.0)
    lejar = ""
    try:
        lejar = (_json.loads(valasz).get("bin", {}).get("expired_at") or "")[:10]
    except Exception:
        pass
    return {"url": m["letoltes"] % {"bin": bin_nev, "fajl": biztos_nev},
            "lejar": lejar, "nev": nev}


def nagy_fajl_szoveg(feltoltott: list) -> str:
    """A levélbe kerülő szöveg a feltöltött fájlokról – jelöléssel, hogy a
    HTML-változatban kattintható legyen."""
    sorok = ["", "A csatolmány(ok) mérete miatt a fájl(ok) letölthető "
             "hivatkozásként:"]
    for f in feltoltott:
        sor = "[%s](%s)" % (f["nev"], f["url"])
        if f.get("lejar"):
            sor += " – elérhető eddig: %s" % f["lejar"]
        sorok.append("• " + sor)
    return "\n".join(sorok) + "\n"


# ---------------------------------------------------------------------------
# LEVELEZŐLISTA – „válasz a listára"
# ---------------------------------------------------------------------------
#
# Klasszikus helyzet: Karcsi ír a listára, te válaszolnál – de nem NEKI, hanem
# a LISTÁNAK. Nem kell találgatni: a listamotorok (Mailman, Google Groups és a
# magyar listaszolgáltatók is) 1998 óta megadják a lista címét a `List-Post`
# fejlécben (RFC 2369), a lista nevét pedig a `List-Id`-ben (RFC 2919).

def lista_cim(msg) -> str:
    """A levelezőlista posta-címe, vagy üres sztring, ha a levél nem listáról
    jött. Tartalék: sok lista a `Reply-To`-t állítja a saját címére."""
    nyers = (msg.get("List-Post") or "").strip()
    if nyers:
        if "NO" in nyers.upper() and "mailto:" not in nyers.lower():
            return ""                    # `List-Post: NO` = tiltott a válasz
        m = re.search(r"mailto:([^>\s,?]+)", nyers, re.I)
        if m:
            return m.group(1).strip()
    if msg.get("List-Id") or msg.get("List-Unsubscribe"):
        # listáról jött, de nem adta meg a posta-címet → Reply-To, ha van és
        # más, mint a feladó
        rt = email.utils.parseaddr(msg.get("Reply-To", ""))[1]
        felado = email.utils.parseaddr(msg.get("From", ""))[1]
        if rt and rt.lower() != (felado or "").lower():
            return rt
    return ""


def lista_neve(msg) -> str:
    """A lista emberi neve a `List-Id`-ből (pl. „Jaws-lista”), vagy a címe."""
    nyers = (msg.get("List-Id") or "").strip()
    if nyers:
        m = re.match(r'\s*"?([^"<]+?)"?\s*<', nyers)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(r"<([^>]+)>", nyers)
        if m:
            return m.group(1).split(".")[0]
        return nyers
    cim = lista_cim(msg)
    return cim.split("@")[0] if cim else ""


def listas_level(msg) -> bool:
    return bool(lista_cim(msg))
