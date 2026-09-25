# -*- coding: utf-8 -*-
"""Egy akciós termék – boltfüggetlen alak.

A felület és a bevásárlólista CSAK ezt látja; hogy a termék a Penny
weboldaláról, a Lidl PDF-jéből vagy az Aldi lapozós újságjából jött, az a
`forrasok` dolga. Így egy új bolt (dm, Rossmann, Tesco…) csak egy új
forrás-függvény, a felülethez nem kell nyúlni."""
from dataclasses import dataclass, asdict
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

    def sor(self) -> str:
        """A listasor. ⚠️ A sor ELEJÉN a név és az ár: nyilazáskor ez
        hangzik el először, a többi csak utána."""
        reszek = [self.nev]
        if self.ar is not None:
            reszek.append(ft(self.ar))
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
        return "\n".join(sorok)

    def legjobb_ar(self) -> int | None:
        arak = [a for a in (self.ar, self.kartyas_ar) if a is not None]
        return min(arak) if arak else None

    def szotar(self) -> dict:
        return asdict(self)

    @classmethod
    def szotarbol(cls, d: dict) -> "Termek":
        mezok = cls.__dataclass_fields__
        return cls(**{k: v for k, v in (d or {}).items() if k in mezok})


def ft(osszeg: int) -> str:
    """1169 → „1169 forint” (a képernyőolvasó a „Ft”-t sokszor betűzi)."""
    return "%d forint" % osszeg


def ar_szam(szoveg: str) -> int | None:
    """„1 169 Ft”, „1169 Ft”, „899.-” → 1169 / 899. Nincs szám: None."""
    s = (szoveg or "").replace(" ", " ").replace("\xa0", " ")
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
    mibol = ekezet_nelkul(" ".join((termek.nev, termek.kategoria,
                                    termek.bolt, termek.kiszereles)))
    return all(sz in mibol for sz in szavak)
