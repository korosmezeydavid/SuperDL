# -*- coding: utf-8 -*-
"""TV műsor – az EPG-MOTOR (XMLTV értelmezés, keresés, „most/ma este”).

Fejetlen (nincs wx), így gépi teszttel ellenőrizhető. A műsorújság szabványos
XMLTV-ből jön, amit a FELHASZNÁLÓ által megadott (vagy az alapértelmezett)
címről töltünk le – a SuperDL semmilyen műsoradatot nem tárol és nem terjeszt,
csak megjeleníti a forrást, forrásmegjelöléssel.

Az IPTV-modul EPG-jétől abban tér el, hogy ÖNÁLLÓAN is működik: a csatornák
nevét magából az XMLTV `<channel>` elemeiből olvassa ki, tehát NEM kell hozzá
m3u/Xtream előfizetés – elég egy nyilvános EPG-cím.
"""
import datetime as _dt
import os
import re
import unicodedata
import xml.etree.ElementTree as ET

# Alapértelmezett, ingyenes magyar EPG-források (a felhasználó felülírhatja).
# Közösségi/hobbi szolgáltatások: ha az egyik nem válaszol, a következőt
# próbáljuk. A SuperDL semmilyen műsoradatot NEM tárol és NEM terjeszt – csak
# megjeleníti a választott forrást, forrásmegjelöléssel.
ALAP_EPG_URL = "https://www.open-epg.com/files/hungary1.xml"
TARTALEK_URLEK = [
    "https://www.open-epg.com/files/hungary1.xml",
    "https://www.open-epg.com/files/hungary3.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_HU1.xml.gz",
    "https://epg.anything.hu/all/guide.xml",
]

# ⚠️ EZ ALATT A FORRÁS NYILVÁNVALÓAN HIÁNYOS (Turai László jelzése,
# 2026-09-21: „a csatornák lapfülre lépve csak 3 db csatornát látok").
#
# MIT MÉRTÜNK. Az addigi elsődleges forrás (epgshare01 HU1) aznap 193
# `<channel>` elemet hirdetett, de MŰSORT csak HÁROMHOZ adott. A régi kód
# ezt SIKERNEK vette – „van csatorna, tehát jó" –, elmentette a
# gyorsítótárba, és ezzel FELÜLÍRTA a korábbi, 164 csatornás jó adatot.
# Onnantól a felhasználó hat órán át három csatornát látott, magyarázat
# nélkül. A tartalék forrás (epg.anything.hu) közben 523-mal elhalt.
#
# Ezért három dolog változott:
#   1. nem az ELSŐ nem-üres forrás nyer, hanem az első NEM HIÁNYOS;
#   2. hiányos adat NEM írja felül a gazdagabb gyorsítótárat;
#   3. a hívó megtudja, hogy hiányos forrásból dolgozik (`hianyos` jelzés).
#
# ⚠️ MIÉRT ARÁNY ÉS NEM DARABSZÁM. Első nekifutásra egy egyszerű
# „húsz csatorna alatt hiányos" küszöböt írtam – de az megbüntette volna
# azt, aki SZÁNDÉKOSAN ad meg egy kicsi, saját EPG-forrást (öt csatorna,
# mind a öthöz van műsor: az teljes, nem hiányos). A valódi jel az ARÁNY:
# Laci forrása 193 csatornát HIRDETETT, és háromhoz adott műsort (1,5%).
ELEG_CSATORNA = 20          # ez alatt a forrás mérete nem árulkodó
HIANYOS_ARANY = 0.25        # a hirdetett csatornák ekkora hányada alatt hiányos


def hianyos_e(tv) -> bool:
    """Csonka-e ez a műsorújság? Nem a MÉRETE számít, hanem hogy a
    HIRDETETT csatornák töredékéhez van csak műsor."""
    musoros = len(tv.csatorna_lista())
    if not musoros:
        return True
    hirdetett = len(tv.csatornak)
    return (hirdetett >= ELEG_CSATORNA
            and musoros < hirdetett * HIANYOS_ARANY)


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _local_offset(mikor=None) -> _dt.timedelta:
    """A HELYI idő eltolása az UTC-től (az adott pillanatban, nyári időszámítást
    is figyelembe véve). FONTOS: pontos, PERCRE kerekített érték – a naiv
    `now() - utcnow()` mikroszekundumos maradéka miatt a műsorok 1 percet
    csúsztak volna (pl. 20:00 helyett 19:59)."""
    t = mikor or _dt.datetime.now()
    off = t.astimezone().utcoffset() or _dt.timedelta(0)
    # biztonságból egész percre kerekítjük (az időzónák percben értendők)
    percek = round(off.total_seconds() / 60.0)
    return _dt.timedelta(minutes=percek)


def xmltv_ido(s: str):
    """XMLTV időbélyeg → HELYI idő (naiv datetime), vagy None.
    Pl. '20260624080000 +0100'."""
    m = re.match(r"\s*(\d{14})(?:\s*([+-]\d{4}))?", s or "")
    if not m:
        return None
    try:
        t = _dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    if m.group(2):
        elojel = 1 if m.group(2)[0] == "+" else -1
        off = _dt.timedelta(hours=int(m.group(2)[1:3]),
                            minutes=int(m.group(2)[3:5])) * elojel
        # a forrás idejéből UTC, majd a HELYI idő – az eltolást az ADOTT
        # időpontra kérjük (nyári időszámítás-váltás miatt)
        t = (t - off) + _local_offset(t)
    return t


def _norm(s: str) -> str:
    """Kereséshez: kisbetű, ékezet nélkül."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def szep_nev(nyers: str) -> str:
    """A csatorna nevének FELOLVASHATÓ alakja.

    ⚠️ Nem szépészet: a forrásokban a technikai toldalékok FELOLVASVA
    zavaróak. Az open-epg magyar listájában minden név „.hu"-ra végződik
    („AMC (HD).hu" → a képernyőolvasó „pont hu"-t mond minden sornál), a
    másik listában „HU - " előtaggal jön. A műsor attól még ugyanaz."""
    n = " ".join((nyers or "").split())
    n = re.sub(r"^(?:HU|HUN|HU-TV)\s*[-–—:]\s*", "", n, flags=re.I)
    n = re.sub(r"\.hu$", "", n, flags=re.I)
    return n.strip() or (nyers or "").strip()


def _letolt_szoveg(url: str, idokorlat: int = 120) -> str:
    """Egy EPG-forrás letöltése szöveggé (a .gz-t kicsomagolja)."""
    import requests
    v = requests.get(url, timeout=idokorlat,
                     headers={"User-Agent": _UA,
                              "Accept": "application/xml, text/xml, */*"})
    v.raise_for_status()
    nyers = v.content
    if url.lower().endswith(".gz") or nyers[:2] == b"\x1f\x8b":
        import gzip
        nyers = gzip.decompress(nyers)
    return nyers.decode("utf-8", "replace")


def _gyorsitotar_ut() -> str:
    """A letöltött műsorújság helye (a SuperDL beállítás-mappájában)."""
    try:
        from superdl import store
        return str(store.CONFIG_DIR / "tvmusor_epg.xml")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".superdl",
                            "tvmusor_epg.xml")


def _friss_e(ut: str, max_ora: int) -> bool:
    try:
        import time
        return (os.path.isfile(ut)
                and (time.time() - os.path.getmtime(ut)) < max_ora * 3600)
    except OSError:
        return False


def _gyorsitotar_ment(ut: str, szoveg: str) -> None:
    try:
        os.makedirs(os.path.dirname(ut), exist_ok=True)
        with open(ut, "w", encoding="utf-8") as f:
            f.write(szoveg)
    except OSError:
        pass


class Musor:
    """Egy műsor: kezdés, vége, cím, leírás, csatorna-azonosító."""

    __slots__ = ("kezd", "veg", "cim", "leiras", "csatorna")

    def __init__(self, kezd, veg, cim, leiras="", csatorna=""):
        self.kezd, self.veg = kezd, veg
        self.cim, self.leiras = cim, leiras
        self.csatorna = csatorna

    @property
    def idopont(self) -> str:
        return self.kezd.strftime("%H:%M") if self.kezd else ""

    @property
    def hossz_perc(self) -> int:
        if not (self.kezd and self.veg):
            return 0
        return max(0, int((self.veg - self.kezd).total_seconds() // 60))

    def felolvasva(self, csatornanev="") -> str:
        """Egy sor, ahogy a képernyőolvasó felolvassa."""
        reszek = [self.idopont]
        if csatornanev:
            reszek.append(csatornanev)
        reszek.append(self.cim or "(nincs cím)")
        if self.hossz_perc:
            reszek.append("%d perc" % self.hossz_perc)
        return " – ".join(reszek)


class TvMusor:
    """Egy betöltött műsorújság: csatornák (azonosító→név) + műsorok."""

    def __init__(self):
        self.csatornak = {}          # tvg-id → megjelenítendő név
        self.musorok = {}            # tvg-id → [Musor] időrendben

    # ------------------------------------------------------------ betöltés
    @classmethod
    def ertelmez(cls, xml_szoveg: str) -> "TvMusor":
        tv = cls()
        try:
            gyoker = ET.fromstring(xml_szoveg)
        except ET.ParseError:
            return tv
        # 1) csatornák: <channel id="..."><display-name>RTL</display-name>
        for ch in gyoker.findall("channel"):
            cid = (ch.get("id") or "").strip()
            if not cid:
                continue
            nev = ""
            for dn in ch.findall("display-name"):
                if (dn.text or "").strip():
                    nev = dn.text.strip()
                    break
            tv.csatornak[cid] = szep_nev(nev) or cid
        # 2) műsorok
        for pr in gyoker.findall("programme"):
            cid = (pr.get("channel") or "").strip()
            kezd = xmltv_ido(pr.get("start", ""))
            veg = xmltv_ido(pr.get("stop", ""))
            if not (cid and kezd):
                continue
            if not veg:
                veg = kezd + _dt.timedelta(hours=1)
            cim_el = pr.find("title")
            le_el = pr.find("desc")
            tv.musorok.setdefault(cid, []).append(Musor(
                kezd, veg,
                (cim_el.text or "").strip() if cim_el is not None else "",
                (le_el.text or "").strip() if le_el is not None else "",
                cid))
            tv.csatornak.setdefault(cid, szep_nev(cid))  # ha nem volt <channel>
        for lista in tv.musorok.values():
            lista.sort(key=lambda m: m.kezd)
        return tv

    @classmethod
    def letolt(cls, url: str = "", idokorlat: int = 120) -> "TvMusor":
        """Letöltés URL-ről vagy beolvasás helyi fájlból (egyetlen forrás)."""
        forras = (url or ALAP_EPG_URL).strip()
        if re.match(r"^https?://", forras, re.I):
            return cls.ertelmez(_letolt_szoveg(forras, idokorlat))
        with open(os.path.expanduser(forras), encoding="utf-8",
                  errors="replace") as f:
            return cls.ertelmez(f.read())

    @staticmethod
    def _gyorsitotar_olvas(gyt):
        """(TvMusor, szöveg) a gyorsítótárból, vagy (None, '')."""
        if not os.path.isfile(gyt):
            return None, ""
        try:
            with open(gyt, encoding="utf-8", errors="replace") as f:
                szoveg = f.read()
        except OSError:
            return None, ""
        return TvMusor.ertelmez(szoveg), szoveg

    @classmethod
    def betolt_okosan(cls, url: str = "", gyorsitotar=True, max_ora: int = 6):
        """A JAVASOLT betöltés. Visszaad: (TvMusor, honnan), ahol a honnan
        'gyorsitotar' | 'halozat' | 'regi' | 'hianyos' | ''.

        ⚠️ AMI ITT A LÉNYEG, ÉS AMIÉRT ÁTÍRTUK (Turai László, 2026-09-21).
        A régi változat az ELSŐ nem-üres forrást fogadta el. Amikor az
        elsődleges forrás 193 csatornát hirdetett, de műsort csak HÁROMHOZ
        adott, ez „siker" volt: a három csatornás adat felülírta a
        gyorsítótárban lévő 164 csatornást, és a felhasználó hat órán át
        három csatornát látott. Most:
          • MINDEN forrást megnézünk, és a LEGTÖBB csatornát adó nyer
            (a bőséges forrásnál persze azonnal megállunk);
          • ha a legjobb letöltés is hiányos, de a gyorsítótárban TÖBB van,
            a gyorsítótár nyer, és a hívó 'regi'-t kap;
          • hiányos adat SOHA nem írja felül a gazdagabb gyorsítótárat;
          • ha tényleg csak hiányos adat van, 'hianyos'-t adunk vissza, hogy
            a felület MEGMONDHASSA, mi történt – a néma három csatorna volt
            az igazi hiba, nem maga a szám.
        """
        utak = []
        for u in ([url.strip()] if url and url.strip() else []) + TARTALEK_URLEK:
            if u and u not in utak:
                utak.append(u)
        gyt = _gyorsitotar_ut()

        gyt_tv, _ = cls._gyorsitotar_olvas(gyt) if gyorsitotar else (None, "")
        gyt_db = len(gyt_tv.csatorna_lista()) if gyt_tv else 0
        # friss ÉS teljes gyorsítótár: azonnal jó. A „friss, de hiányos"
        # gyorsítótárat NEM fogadjuk el – épp az volt a csapda.
        if gyt_tv is not None and not hianyos_e(gyt_tv) \
                and _friss_e(gyt, max_ora):
            return gyt_tv, "gyorsitotar"

        legjobb_tv, legjobb_szoveg, legjobb_db, legjobb_ok = None, "", 0, False
        for u in utak:
            try:
                szoveg = (_letolt_szoveg(u) if re.match(r"^https?://", u, re.I)
                          else open(os.path.expanduser(u), encoding="utf-8",
                                    errors="replace").read())
                tv = cls.ertelmez(szoveg)
                db = len(tv.csatorna_lista())
            except Exception:
                continue
            if db > legjobb_db:
                legjobb_tv, legjobb_szoveg, legjobb_db = tv, szoveg, db
                legjobb_ok = not hianyos_e(tv)
            if legjobb_ok:
                break                      # teljes forrás – nincs mit keresni

        if legjobb_ok:
            if gyorsitotar:
                _gyorsitotar_ment(gyt, legjobb_szoveg)
            return legjobb_tv, "halozat"

        # Innentől a hálózat csak hiányosat adott (vagy semmit).
        if gyt_db > legjobb_db:
            return gyt_tv, "regi"          # a mentett adat a jobb – ne rontsunk
        if legjobb_db:
            # ⚠️ SZÁNDÉKOSAN NEM MENTJÜK: a hiányos adat nem írhatja felül a
            # következő indulás esélyét egy jobb letöltésre.
            return legjobb_tv, "hianyos"
        if gyt_tv is not None:
            return gyt_tv, "regi"
        return cls(), ""

    # ------------------------------------------------------------ lekérdezők
    def csatorna_nev(self, cid: str) -> str:
        return self.csatornak.get(cid, cid)

    def csatorna_lista(self) -> list:
        """(azonosító, név) párok név szerint rendezve – csak ahol VAN műsor."""
        elemek = [(cid, self.csatorna_nev(cid))
                  for cid in self.musorok if self.musorok.get(cid)]
        elemek.sort(key=lambda t: _norm(t[1]))
        return elemek

    def most_kovetkezo(self, cid: str, mikor=None):
        """(épp futó, következő) az adott csatornán."""
        mikor = mikor or _dt.datetime.now()
        progs = self.musorok.get(cid) or []
        futo = kov = None
        for i, m in enumerate(progs):
            if m.kezd <= mikor < m.veg:
                futo = m
                kov = progs[i + 1] if i + 1 < len(progs) else None
                break
            if m.kezd > mikor:
                kov = m
                break
        return futo, kov

    def naprend(self, cid: str, mikor=None, darab: int = 30) -> list:
        """Az adott csatorna műsorai a megadott időtől (alapból: mostantól)."""
        mikor = mikor or _dt.datetime.now()
        return [m for m in (self.musorok.get(cid) or []) if m.veg > mikor][:darab]

    # ---- NAPRA BONTÁS (Laci kérése, 2026-08-24) -----------------------
    #
    # „Hány napra előre tudnál megjeleníteni egy csatorna műsorát? Lehetne
    # napot állítani a csatornalistában, ha nem az aktuálisra kíváncsi az
    # ember.” – Eddig csak MOSTANTÓL előre lehetett nézni a műsort; így a
    # holnaputáni film megkeresése végignyilazást jelentett.

    def elerheto_napok(self, cid: str = "") -> list:
        """Mely NAPOKRA van egyáltalán adat? (dátumok, növekvő sorrendben)

        Ha `cid` meg van adva, csak arra a csatornára néz – a források ugyanis
        nem minden csatornára adnak ugyanannyit: van, amelyik négy napra
        előre, van, amelyik csak holnapig."""
        listak = ([self.musorok.get(cid) or []] if cid
                  else list(self.musorok.values()))
        napok = set()
        for lista in listak:
            for m in lista:
                napok.add(m.kezd.date())
        return sorted(napok)

    def nap_musora(self, cid: str, nap=None, hajnal_ora: int = 5) -> list:
        """Egy csatorna EGÉSZ napi műsora – nem csak mostantól.

        A `hajnal_ora` azért kell, mert a tévénézők fejében a nap nem éjfélkor
        ér véget: a „ma esti" film, ami hajnali fél egykor kezdődik, MÉG a mai
        naphoz tartozik. Ezért a nap 5:00-tól másnap 5:00-ig tart."""
        nap = nap or _dt.date.today()
        kezdet = _dt.datetime.combine(nap, _dt.time(hajnal_ora, 0))
        veg = kezdet + _dt.timedelta(days=1)
        return [m for m in (self.musorok.get(cid) or [])
                if kezdet <= m.kezd < veg]

    @staticmethod
    def nap_neve(nap, ma=None) -> str:
        """A nap FELOLVASHATÓ neve: „ma", „holnap", vagy „csütörtök, 08. 28."."""
        ma = ma or _dt.date.today()
        kulonbseg = (nap - ma).days
        if kulonbseg == 0:
            elotag = "ma"
        elif kulonbseg == 1:
            elotag = "holnap"
        elif kulonbseg == 2:
            elotag = "holnapután"
        elif kulonbseg == -1:
            elotag = "tegnap"
        else:
            elotag = ""
        napnevek = ("hétfő", "kedd", "szerda", "csütörtök", "péntek",
                    "szombat", "vasárnap")
        alap = "%s, %s" % (napnevek[nap.weekday()], nap.strftime("%m. %d."))
        return ("%s – %s" % (elotag, alap)) if elotag else alap

    def mi_megy_most(self, mikor=None) -> list:
        """MINDEN csatorna épp futó műsora: (csatornanév, Musor) párok."""
        mikor = mikor or _dt.datetime.now()
        ki = []
        for cid, _nev in self.csatorna_lista():
            futo, _ = self.most_kovetkezo(cid, mikor)
            if futo:
                ki.append((self.csatorna_nev(cid), futo))
        return ki

    def ma_este(self, mikor=None, ettol=20, eddig=23) -> list:
        """A ma esti főműsoridő (alapból 20:00–23:00) műsorai minden csatornán,
        kezdés szerint rendezve: (csatornanév, Musor)."""
        mikor = mikor or _dt.datetime.now()
        nap = mikor.date()
        kezdet = _dt.datetime.combine(nap, _dt.time(ettol, 0))
        veg = _dt.datetime.combine(nap, _dt.time(eddig, 0))
        ki = []
        for cid, nev in self.csatorna_lista():
            for m in self.musorok.get(cid) or []:
                if kezdet <= m.kezd < veg:
                    ki.append((nev, m))
        ki.sort(key=lambda t: (t[1].kezd, _norm(t[0])))
        return ki

    def kedvencek_talalat(self, cimek, mikortol=None, darab: int = 100) -> list:
        """KEDVENC-FIGYELŐ: a megadott címek (filmek, sorozatok) közül melyik jön
        a műsorban? Visszaad: (kedvenc_cím, csatornanév, Musor) hármasok
        IDŐRENDBEN – így egyetlen mondatban megmondható, „lesz a kedvenced itt és
        ekkor”.

        Ugyanazt a műsort csak EGYSZER adja vissza, akkor is, ha több kedvencre
        is illik (pl. „Kevin” és „Reszkessetek”)."""
        mikortol = mikortol or _dt.datetime.now()
        ki, latott = [], set()
        for cim in (cimek or []):
            cim = (cim or "").strip()
            if not cim:
                continue
            for nev, m in self.keres(cim, mikortol=mikortol, darab=darab):
                kulcs = (m.csatorna, m.kezd, _norm(m.cim))
                if kulcs in latott:
                    continue
                latott.add(kulcs)
                ki.append((cim, nev, m))
        ki.sort(key=lambda t: t[2].kezd)
        return ki[:darab]

    def keres(self, kifejezes: str, mikortol=None, darab: int = 200) -> list:
        """Cím (és leírás) szerinti keresés MINDEN csatornán – ékezet- és
        kisbetű-érzéketlen. Visszaad: (csatornanév, Musor), időrendben.
        Ezzel derül ki, hogy „mikor megy a Reszkessetek betörők?”."""
        k = _norm(kifejezes).strip()
        if not k:
            return []
        mikortol = mikortol or _dt.datetime.now()
        ki = []
        for cid, nev in self.csatorna_lista():
            for m in self.musorok.get(cid) or []:
                if m.veg <= mikortol:
                    continue
                if k in _norm(m.cim) or (m.leiras and k in _norm(m.leiras)):
                    ki.append((nev, m))
        ki.sort(key=lambda t: t[1].kezd)
        return ki[:darab]
