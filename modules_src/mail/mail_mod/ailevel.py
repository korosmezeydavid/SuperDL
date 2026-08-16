# -*- coding: utf-8 -*-
"""AI-LEVÉLÍRÁS – a kérés összeállítása és a válasz megtisztítása.

Felhasználói kérés (2026-08-16): legyen egy menüpont, ahol megmondom, KINEK és
MIRŐL írjunk, választok hangnemet és hosszt, az AI megírja, én meg elfogadom,
pontosítom vagy újragenerálom – és elfogadáskor AZONNAL a levélbe kerül.

Ez a fájl SZÁNDÉKOSAN wx- és hálózat-mentes: csak szöveget épít és tisztít,
így tesztelhető. A hívást a `superdl.aiclient` (a Core közös AI-kliense) végzi,
a FELHASZNÁLÓ SAJÁT kulcsával.
"""

from __future__ import annotations

import re

HANGNEMEK = [
    ("baratsagos", "Barátságos", "közvetlen, meleg hangvétel"),
    ("semleges", "Semleges", "tárgyilagos, semleges hangvétel"),
    ("hivatalos", "Hivatalos", "hivatalos, udvarias, formális hangvétel"),
]

MEGSZOLITASOK = [
    ("tegezo", "Tegeződő", "tegeződő megszólítás (te-forma)"),
    ("magazo", "Magázódó", "magázódó megszólítás (Ön-forma)"),
]

# A karakter-célok nemcsak címkék: az AI is megkapja őket utasításként.
HOSSZAK = [
    ("rovid", "Rövid", 400, 700),
    ("kozepes", "Közepes", 900, 1500),
    ("hosszu", "Hosszú", 2000, 3000),
]

RENDSZER = (
    "Magyar nyelvű e-maileket írsz egy vak felhasználó helyett, aki diktálás "
    "helyett néhány szóban megadja a lényeget. A válaszod KIZÁRÓLAG a levél "
    "szövege legyen: megszólítás, törzs, elköszönés. NE írj tárgymezőt, ne "
    "használj Markdown-jelölést, csillagokat, felsorolás-jeleket vagy "
    "kódblokkot, és ne fűzz hozzá magyarázatot arról, hogy mit csináltál. "
    "Aláírást NE tegyél a végére: azt a program teszi hozzá."
)


def _cimke(lista, kulcs, mezo=2):
    for elem in lista:
        if elem[0] == kulcs:
            return elem[mezo]
    return lista[0][mezo]


def hossz_hatar(kulcs) -> tuple:
    for k, _nev, mini, maxi in HOSSZAK:
        if k == kulcs:
            return mini, maxi
    return HOSSZAK[0][2], HOSSZAK[0][3]


def prompt_epit(mirol: str, kinek: str = "", hangnem: str = "baratsagos",
                megszolitas: str = "tegezo", hossz: str = "kozepes",
                eredeti: str = "", pontositas: str = "",
                elozo: str = "") -> str:
    """A teljes kérés szövege. `eredeti`: a levél, amire válaszolunk (csak ha a
    felhasználó ezt kérte); `pontositas` + `elozo`: újragenerálás a korábbi
    szöveg és a felhasználó javítási kérése alapján."""
    mini, maxi = hossz_hatar(hossz)
    reszek = ["Írj egy e-mailt az alábbiak szerint.", ""]
    if kinek.strip():
        reszek.append("A címzett: %s" % kinek.strip())
    reszek += [
        "A levél témája és tartalma: %s" % (mirol or "").strip(),
        "Hangnem: %s." % _cimke(HANGNEMEK, hangnem),
        "Megszólítás: %s." % _cimke(MEGSZOLITASOK, megszolitas),
        "Hossz: nagyjából %d–%d karakter (ehhez tartsd magad)." % (mini, maxi),
    ]
    if eredeti.strip():
        reszek += ["", "Ez az a levél, amelyre válaszolunk – vedd figyelembe, "
                   "és arra válaszolj:", '"""', eredeti.strip()[:6000], '"""']
    if pontositas.strip():
        reszek += ["", "A korábbi változat ez volt:", '"""',
                   (elozo or "").strip()[:6000], '"""', "",
                   "Írd át ezek szerint: %s" % pontositas.strip()]
    return "\n".join(reszek)


_MARKDOWN = re.compile(r"^\s*(#{1,6}\s+|[*\-•]\s+)", re.M)


def valasz_tisztit(szoveg: str) -> str:
    """Az AI válaszának megtisztítása: idézőjelbe csomagolás, Markdown-jelek és
    a „Tárgy:" sor eltávolítása – ezek a levélbe illesztve zavaróak lennének,
    a képernyőolvasó pedig fel is olvasná a csillagokat."""
    sz = (szoveg or "").strip()
    if sz.startswith('"""') and sz.endswith('"""'):
        sz = sz[3:-3].strip()
    if len(sz) > 1 and sz[0] == sz[-1] and sz[0] in "\"'„”":
        sz = sz[1:-1].strip()
    sz = re.sub(r"^\s*(tárgy|subject)\s*:.*\n+", "", sz, flags=re.I)
    sz = _MARKDOWN.sub("", sz)
    sz = re.sub(r"\*\*(.+?)\*\*", r"\1", sz)
    sz = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", sz)
    return sz.strip()


def targy_prompt(szoveg: str) -> str:
    return ("Adj EGYETLEN rövid, magyar tárgymezőt ehhez a levélhez. Csak a "
            "tárgyat írd, idézőjel és bevezetés nélkül, legfeljebb 60 "
            "karakterben.\n\n" + (szoveg or "")[:3000])


def targy_tisztit(szoveg: str) -> str:
    sz = valasz_tisztit(szoveg).splitlines()
    return (sz[0].strip() if sz else "")[:120]
