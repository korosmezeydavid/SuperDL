# -*- coding: utf-8 -*-
"""Ideiglenes tárhelyek – „egy mozdulattal feldobom" (2026-09-06).

Az androidos `share/CloudTarget.kt` és `CloudUploader.kt` windowsos testvére.
**Ugyanaz a hat tárhely, ugyanazokkal a paraméterekkel** – ha a két platform
mást mondana ugyanarról a szolgáltatásról, a felhasználó azt hinné, elromlott
valamelyik.

⚠️ **A wormhole.app KIMARADT**, és ez nem feledékenység: nincs nyilvános
API-ja, csak böngészőből megy. Egy „egy mozdulattal feldobom" gomb nem
építhető rá.

⚠️ **A FELTÖLTÉSI CÍMEK A KÓDBAN VANNAK, NEM ADATBAN.** Kísértés volt
letölthető listát csinálni belőlük (hogy egy megszűnt szolgáltató kiadás nélkül
cserélhető legyen), de egy távolról állítható feltöltési cím azt jelentené,
hogy a felhasználó fájljai bárhova átirányíthatók. Ez a döntés az androidos
körben született, és itt is tartjuk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

MB = 1024 * 1024
GB = 1024 * MB

# A felhős útra INDULÁS ELŐTT elhangzó, kötelező figyelmeztetés.
# ⚠️ Az androidos szöveggel SZÓ SZERINT egyeznie kell (share/HelpTexts) —
# két megfogalmazás ugyanarra a veszélyre két különböző dolognak látszana.
# A második mondat a windowsos kiegészítés: mivel jelszó nincs (tudatos
# döntés), a figyelmeztetés nem tiltás, hanem ÚTBAIGAZÍTÁS.
FIGYELMEZTETES = (
    "Aki megkapja a linket, letöltheti a fájlt, mert nem lesz rajta jelszó. "
    "Iratot, orvosi papírt, jelszót ne ezen az úton küldj. "
    "Ha ez titok, ne ide küldd: küldd kóddal, gépről gépre – az csak a "
    "másik félhez jut el, titkosítva."
)


@dataclass(frozen=True)
class Tarhely:
    id: str
    nev: str
    max_meret: int
    nap: float               # hány napig él (tört is lehet: uguu = 3 óra)
    egyszeri: bool           # csak EGYSZER tölthető le
    torolheto: bool          # vissza tudjuk-e vonni a tárhelyről
    url: str
    mezo: str = "file"       # a feltöltési űrlap mezőneve
    mod: str = "multipart"   # "multipart" vagy "bin" (filebin: nyers test)
    extra: tuple = ()        # további űrlapmezők (kulcs, érték) párokban


# ⚠️ EZT A LISTÁT ÉLESBEN MEGMÉRTÜK (2026-09-08, windowsos gépről).
# Az androidos körben egyik tárhely sem lett mérve, és a mérés HÁROMBÓL
# HÁROM feltevést megcáfolt:
#   • 0x0.st        → 503, „uploads disabled … AI botnet spam … no ETA"
#   • bashupload    → a tartomány NEM OLDHATÓ FEL (megszűnt)
#   • file.io       → 200-at ad, de HTML weboldalt: az ingyenes API megszűnt
# Ezek KIKERÜLTEK. Helyettük mért, működő tárhelyek jöttek.
# ⚠️ Az Androidon ugyanez a három még bent van — oda is át kell vinni.
TARHELYEK: tuple[Tarhely, ...] = (
    # nagy fájlokra, egyszerű szöveges válasz (mérve: 200, nyers URL)
    Tarhely("tempsh", "temp.sh", 4 * GB, 3, False, False,
            "https://temp.sh/upload"),
    # visszavonható: a bin egészben törölhető (mérve: 201 + JSON)
    Tarhely("filebin", "filebin.net", 2 * GB, 7, False, True,
            "https://filebin.net", mod="bin"),
    # kicsi, gyors (mérve: 200 + JSON `data.url`)
    Tarhely("tmpfiles", "tmpfiles.org", 100 * MB, 2, False, False,
            "https://tmpfiles.org/api/v1/upload"),
    # x0.at – a 0x0.st élő klónja (mérve: 200, nyers URL). Óvatos korlátok:
    # inkább mondjunk kevesebbet, mint hogy a felhasználó többre számítson.
    Tarhely("x0at", "x0.at", 100 * MB, 30, False, False,
            "https://x0.at"),
    # „ne legyen ott sokáig" – Alph kérése a bashupload/file.io mögött ez volt.
    # Az uguu 3 ÓRA után törli. (mérve: 200 + JSON `files[0].url`)
    Tarhely("uguu", "uguu.se", 128 * MB, 3 / 24, False, False,
            "https://uguu.se/upload", mezo="files[]"),
)


def valaszthatok(meret: int) -> list[Tarhely]:
    """Csak azok a tárhelyek, amelyekbe a csomag BELEFÉR.

    A méret itt szűr — de nem ez az első kérdés a folyamatban. A p2p és a
    tárhely közti valódi különbség az, hogy a p2p-hez a másik félnek EGYSZERRE
    kell gépnél lennie; a méret csak azután dönti el, melyik tárhely jöhet."""
    return [t for t in TARHELYEK if meret <= t.max_meret]


def emberi_meret(b: int) -> str:
    """Tizedesvesszővel – a felolvasó a pontot mondatvégi pontnak mondja."""
    for hatar, egyseg in ((GB, "gigabájt"), (MB, "megabájt"), (1024, "kilobájt")):
        if b >= hatar:
            ertek = b / hatar
            if ertek >= 100:
                return f"{ertek:.0f} {egyseg}"
            return f"{ertek:.1f} {egyseg}".replace(".", ",")
    return f"{int(b)} bájt"


def emberi_nap(nap: float) -> str:
    """A tört nap ÓRÁBAN hangzik el: a „0,125 napig" kimondva értelmetlen,
    és épp a legfontosabb esetnél (uguu: 3 óra) fordulna elő."""
    if nap < 1:
        ora = max(1, int(round(nap * 24)))
        return "egy óráig" if ora == 1 else f"{ora} óráig"
    nap = int(nap)
    if nap == 1:
        return "egy napig"
    if nap == 7:
        return "egy hétig"
    if nap == 30:
        return "egy hónapig"
    return f"{nap} napig"


def leiras(t: Tarhely) -> str:
    """A tárhely egyetlen, felolvasható mondatban.

    ⚠️ Az EGYSZERI letöltést külön kimondjuk, mert ez a legkellemetlenebb
    meglepetés: ha a címzett véletlenül kétszer kattint, másodszorra már nincs
    ott a fájl. Az androidos verzió is kétszer mondja ki (választáskor és a
    megerősítésnél); itt ugyanígy."""
    reszek = [f"{t.nev}: legfeljebb {emberi_meret(t.max_meret)}, "
              f"{emberi_nap(t.nap)} él"]
    if t.egyszeri:
        reszek.append("és CSAK EGYSZER tölthető le")
    if t.torolheto:
        reszek.append("a feltöltés utólag visszavonható")
    return ", ".join(reszek) + "."


def megerosito_kerdes(t: Tarhely, fajlnev: str, meret: int) -> str:
    """A megerősítés előtti mondat. A FIGYELMEZTETÉS ELŐTTE hangzik el."""
    mondat = (f"Feltöltöd ide: {t.nev}? A fájl: {fajlnev}, "
              f"{emberi_meret(meret)}. {emberi_nap(t.nap).capitalize()} lesz "
              "elérhető")
    if t.egyszeri:
        mondat += ", és CSAK EGYSZER tölthető le"
    return mondat + "."


def _html_oldal(szoveg: str) -> bool:
    """Igaz, ha a válasz egy WEBOLDAL, nem gépi felelet.

    ⚠️ **EZ A MÉRÉS LEGFONTOSABB TANULSÁGA (2026-09-08).** A file.io 200-as
    kóddal egy teljes HTML weboldalt adott vissza (megszűnt az ingyenes API-ja),
    a link-kinyerőnk pedig kiszedte belőle az első URL-t — egy háttérképet —,
    és a program **sikert jelentett egy értelmetlen linkkel**. A felhasználó ezt
    kimásolta és elküldte volna valakinek. **A hamis siker rosszabb a hibánál.**

    ⚠️ **A Content-Type NEM használható erre:** a temp.sh `text/html`-t mond, a
    törzse mégis csak egy nyers URL. A válasz ALAKJÁRA kell nézni, nem a
    fejlécére — ezt is a mérés mutatta meg."""
    eleje = (szoveg or "").lstrip()[:400].lower()
    return eleje.startswith("<!doctype html") or eleje.startswith("<html") \
        or "<head>" in eleje or "<meta " in eleje


def _link_ertelmes(link: str) -> bool:
    """Egy weboldalról leszedett kép vagy stíluslap NEM letöltési link."""
    if not link.lower().startswith(("http://", "https://")):
        return False
    vege = link.lower().rsplit("/", 1)[-1]
    return not vege.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg",
                              ".ico", ".css", ".js", ".woff", ".woff2"))


def talalt_link(szoveg: str) -> str:
    """A válaszból kiszedett letöltési link. Üres, ha nincs értelmes link.

    A tárhelyek háromféleképpen felelnek: nyers URL (temp.sh, x0.at), JSON
    (tmpfiles, uguu, filebin), vagy — ha elromlott valami — egy weboldal."""
    szoveg = (szoveg or "").strip()
    if not szoveg:
        return ""
    # 0. WEBOLDAL → nincs link. Inkább mondjunk kudarcot, mint hamis sikert.
    if _html_oldal(szoveg):
        return ""
    # 1. JSON válasz
    if szoveg[:1] in "{[":
        try:
            adat = json.loads(szoveg)
        except ValueError:
            adat = None
        if isinstance(adat, dict):
            # uguu.se: {"files": [{"url": ...}]}
            fajlok = adat.get("files")
            if isinstance(fajlok, list) and fajlok:
                elso = fajlok[0]
                if isinstance(elso, dict) and isinstance(elso.get("url"), str):
                    return elso["url"]
            for kulcs in ("link", "url", "data"):
                ertek = adat.get(kulcs)
                if isinstance(ertek, str) and ertek.startswith("http"):
                    return ertek
                if isinstance(ertek, dict):
                    for k2 in ("url", "link"):
                        if isinstance(ertek.get(k2), str):
                            return ertek[k2]
        return ""          # JSON volt, de nincs benne link – ne találgassunk
    # 2. nyers URL a szövegben
    talalat = re.search(r"https?://\S+", szoveg)
    if not talalat:
        return ""
    link = talalat.group(0).rstrip(".,)\"'>")
    return link if _link_ertelmes(link) else ""


def hibauzenet(allapot: int, tarhely_nev: str) -> str:
    """HTTP-hibakód → magyar mondat, ami megmondja, mi a TEENDŐ.

    A nyers „HTTP 413" vakon semmit nem jelent. Ugyanaz az elv, mint az MK6
    hibaszöveg-fordítójánál: ha nincs mintánk, marad a nyers szám — kitalált
    magyarázatot nem adunk."""
    if allapot in (413, 507):
        return (f"A {tarhely_nev} szerint túl nagy a fájl. Válassz másik "
                "tárhelyet, vagy küldd kóddal, gépről gépre – ott nincs "
                "méretkorlát.")
    if allapot == 403:
        return (f"A {tarhely_nev} elutasította a feltöltést. Ez a szolgáltató "
                "döntése, nem a te hibád – próbálj másik tárhelyet.")
    if allapot == 429:
        return (f"A {tarhely_nev} szerint túl sok feltöltés érkezett. "
                "Várj néhány percet, vagy válassz másik tárhelyet.")
    if allapot >= 500:
        return (f"A {tarhely_nev} most nem működik (a szolgáltató hibája). "
                "Próbáld később, vagy válassz másik tárhelyet.")
    return f"A feltöltés nem sikerült: a {tarhely_nev} {allapot} kóddal felelt."
