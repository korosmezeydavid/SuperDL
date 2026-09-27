# -*- coding: utf-8 -*-
"""Egy akciós termék – boltfüggetlen alak.

A felület és a bevásárlólista CSAK ezt látja; hogy a termék a Penny
weboldaláról, a Lidl PDF-jéből vagy az Aldi lapozós újságjából jött, az a
`forrasok` dolga. Így egy új bolt (dm, Rossmann, Tesco…) csak egy új
forrás-függvény, a felülethez nem kell nyúlni."""
from dataclasses import dataclass, asdict
import datetime as _dt
import re
import unicodedata


@dataclass
class Termek:
    bolt: str                    # "Penny", "Lidl", "Aldi"
    nev: str
    ar: int | None = None        # forint, amit fizetsz (kártya nélkül)
    kartyas_ar: int | None = None  # hűségkártyás / appos ár, ha van
    kartya_nev: str = ""         # "PENNY Kártyával", "Lidl Plus-szal"
    regi_ar: int | None = None   # áthúzott (eredeti) ár, ha van
    kedvezmeny: str = ""         # "-30%"
    kiszereles: str = ""         # "300 g"
    egysegar: str = ""           # "1 kg = 3897 Ft"
    ervenyes: str = ""           # "09.24–09.30."
    kategoria: str = ""
    kod: str = ""                # a bolt azonosítója (URL vagy cikkszám)
    megjegyzes: str = ""
    csoport: str = ""            # közös termékcsoport (csoport.besorol)
    url: str = ""                # a termék oldala a bolt honlapján, ha van

    def sor(self, bolttal: bool = False, legjobb_elol: bool = False) -> str:
        """A listasor. ⚠️ A sor ELEJÉN a név és az ár: nyilazáskor ez
        hangzik el először, a többi csak utána.

        `bolttal=True` (Minden bolt nézet): a bolt neve közvetlenül az ár
        után – Petrus József: „a legolcsóbbtól a legdrágábbig, persze
        feltüntetve az áruház nevét".

        `legjobb_elol=True` (Ár szerint rendezve): ELSŐNEK az az ár hangzik
        el, ami szerint a lista rendezve van (`legjobb_ar`). Ha a kártyás ár
        az olcsóbb, az kerül előre, a kártya nélküli ár hátra. Különben
        nyilazáskor a kártya nélküli árat hallod, a sorrend viszont a
        kártyás szerint megy – ez „összekutyulódott" (Petrus József,
        2026-09-27)."""
        if (legjobb_elol and self.kartyas_ar is not None
                and (self.ar is None or self.kartyas_ar < self.ar)):
            reszek = [self.nev, "%s %s" % (self.kartya_nev or "kártyával",
                                           ft(self.kartyas_ar))]
            if bolttal and self.bolt:
                reszek.append(self.bolt)
            if self.ar is not None:
                reszek.append("kártya nélkül %s" % ft(self.ar))
            if self.kedvezmeny:
                reszek.append(self.kedvezmeny)
            if (self.kiszereles
                    and self.kiszereles.lower() not in self.nev.lower()):
                reszek.append(self.kiszereles)
            return ", ".join(reszek)
        reszek = [self.nev]
        if self.ar is not None:
            reszek.append(ft(self.ar))
        if bolttal and self.bolt:
            reszek.append(self.bolt)
        if self.kartyas_ar is not None:
            reszek.append("%s %s" % (self.kartya_nev or "kártyával",
                                     ft(self.kartyas_ar)))
        if self.kedvezmeny:
            reszek.append(self.kedvezmeny)
        if self.kiszereles and self.kiszereles.lower() not in self.nev.lower():
            reszek.append(self.kiszereles)       # ha a névben már benne van, ne
        return ", ".join(reszek)

    def reszletek(self) -> str:
        sorok = [self.nev, "Bolt: %s" % self.bolt]
        if self.csoport:
            sorok.append("Termékcsoport: %s" % self.csoport)
        if self.ar is not None:
            sorok.append("Ár: %s" % ft(self.ar))
        if self.kartyas_ar is not None:
            sorok.append("%s: %s" % (self.kartya_nev or "Kártyával",
                                     ft(self.kartyas_ar)))
        if self.regi_ar is not None:
            sorok.append("Eredeti ár: %s" % ft(self.regi_ar))
        for cim, ertek in (("Kedvezmény", self.kedvezmeny),
                           ("Kiszerelés", self.kiszereles),
                           ("Egységár", self.egysegar),
                           ("Érvényes", self.ervenyes),
                           ("Kategória", self.kategoria),
                           ("Megjegyzés", self.megjegyzes)):
            if ertek:
                sorok.append("%s: %s" % (cim, ertek))
        if self.hivatkozas():
            sorok.append("Weboldal: %s" % self.hivatkozas())
        return "\n".join(sorok)

    def hivatkozas(self) -> str:
        """A termék saját oldala a bolt honlapján – ha a bolt ad ilyet (a
        régebbi forrásoknál a `kod` maga a cím)."""
        if self.url:
            return self.url
        if (self.kod or "").startswith("http"):
            return self.kod
        return ""

    def legjobb_ar(self) -> int | None:
        arak = [a for a in (self.ar, self.kartyas_ar) if a is not None]
        return min(arak) if arak else None

    def szotar(self) -> dict:
        return asdict(self)

    @classmethod
    def szotarbol(cls, d: dict) -> "Termek":
        mezok = cls.__dataclass_fields__
        return cls(**{k: v for k, v in (d or {}).items() if k in mezok})


_HONAP_NAP = re.compile(r"(?<!\d)(\d{1,2})\.\s*(\d{1,2})(?!\d)")


def _datum(honap: int, nap: int, ma: _dt.date):
    """Hónap.nap → dátum a MAI naphoz legközelebbi évvel (az évfordulón át
    is jó: decemberben a „01.05" jövő január)."""
    for ev in (ma.year, ma.year + 1, ma.year - 1):
        try:
            d = _dt.date(ev, honap, nap)
        except ValueError:
            return None
        if abs((d - ma).days) <= 183:
            return d
    return None


def lejart(ervenyes: str, ma: _dt.date | None = None) -> bool:
    """Lejárt-e az akció? Schibik Miklós (2026-09-28): „az előző heti
    akciók is benne vannak" – a Lidl két hét újságját adja, és a hét eleji
    (09.24–09.27) tételek a hét végén még a listában voltak.

    „09.24-tól 09.30-ig", „2026. 09. 02–09. 29.", „09.28–10.04." → az
    UTOLSÓ hónap.nap a vég. Csak kezdet („09.21-tól", Aldi): két hét után
    tekintjük lejártnak. Üres vagy érthetetlen: nem lejárt (nem dobunk el
    olyat, amiről nem tudjuk)."""
    ma = ma or _dt.date.today()
    parok = _HONAP_NAP.findall(ervenyes or "")
    if not parok:
        return False
    h, n = (int(x) for x in parok[-1])
    veg = _datum(h, n, ma)
    if veg is None:
        return False
    if len(parok) == 1 and "-ig" not in (ervenyes or ""):
        return (ma - veg).days > 13         # csak kezdet ismert
    return veg < ma


def ft(osszeg: int) -> str:
    """1169 → „1169 forint” (a képernyőolvasó a „Ft”-t sokszor betűzi)."""
    return "%d forint" % osszeg


def ar_szam(szoveg: str) -> int | None:
    """„1 169 Ft”, „1169 Ft”, „899.-” → 1169 / 899. Nincs szám: None."""
    s = (szoveg or "").replace(" ", " ").replace("\xa0", " ").replace(" ", " ")
    m = re.search(r"(\d{1,3}(?:[ .]\d{3})+|\d+)", s)
    if not m:
        return None
    try:
        return int(re.sub(r"[ .]", "", m.group(1)))
    except ValueError:
        return None


def ekezet_nelkul(s: str) -> str:
    """Kereséshez: kisbetű, ékezet nélkül („Rántott” → „rantott”)."""
    n = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in n if not unicodedata.combining(c))


def illik(termek: Termek, kereses: str) -> bool:
    """Minden beírt szó szerepel-e a termékben (név, kategória, bolt)."""
    szavak = ekezet_nelkul(kereses).split()
    if not szavak:
        return True
    # a megjegyzésben is keresünk: ott áll pl. az Illatoriumnál, melyik
    # parfüm ihlette („versace"), a Pepcónál a termék leírása
    mibol = ekezet_nelkul(" ".join((termek.nev, termek.kategoria,
                                    termek.bolt, termek.kiszereles,
                                    termek.megjegyzes)))
    return all(sz in mibol for sz in szavak)
