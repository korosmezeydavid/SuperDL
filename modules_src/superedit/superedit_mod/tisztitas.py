# -*- coding: utf-8 -*-
"""Okos tisztítás: a beillesztett szövegből a SZEMETET szedi ki.

Amikor egy weboldalról (például egy fanfic-oldalról) másolunk be szöveget, a
tartalom mellé odajön a navigáció is: hivatkozások, „következő fejezet"
gombok szövege, kétszeres üres sorok. Ezeket megkeresni és egyenként törölni
vakon különösen fáradságos — pontosan ezért van ez.

⚠️ MINDEN SZABÁLY KÜLÖN KAPCSOLHATÓ, ÉS ELŐBB MEGSZÁMOLJUK. A felhasználó
azt látja, MENNYIT változtatnánk, és csak utána dönt. Egy néma tömeges csere
a legrosszabb, ami vakon történhet: ha nem figyeltél, már nem tudod, mi volt.
"""

import re

# http(s):// vagy www. kezdetű cím, a záró írásjelet nem nyeljük le
URL = re.compile(r"""(?:https?://|www\.)[^\s<>"')\]]+""", re.I)

# Markdown-hivatkozás: [látható szöveg](cím) – a SZÖVEGET megtartjuk
MD_LINK = re.compile(r"\[([^\]\n]+)\]\((?:[^)\s]+)\)")

# HTML-címke
HTML = re.compile(r"</?[a-zA-Z][^>\n]*>")

# Tipikus navigációs sorok egy fejezetes oldalról (magyarul és angolul).
# Csak akkor dobjuk ki, ha a sor JÓFORMÁN csak ennyi – egy mondat közepén
# szereplő „vissza" szó nem érinti.
NAV_SZAVAK = (
    "következő fejezet", "előző fejezet", "vissza a tetejére",
    "vissza az elejére", "tartalomjegyzék", "vissza a lista",
    "next chapter", "previous chapter", "prev chapter", "back to top",
    "table of contents", "chapter index", "add to favorites",
    "kedvencekhez", "megosztás", "share this", "comments", "hozzászólások",
)

_TOBB_URES = re.compile(r"\n{3,}")
_TOBB_SZOKOZ = re.compile(r"[ \t]{2,}")
_SOR_VEGI = re.compile(r"[ \t]+$", re.M)
_URES_ZAROJEL = re.compile(r"\(\s*\)|\[\s*\]")


def _nav_sor(sor: str) -> bool:
    t = sor.strip().lower().strip("·|—–-*>< \t")
    if not t or len(t) > 60:
        return False
    return any(sz in t for sz in NAV_SZAVAK)


def _url_ki(szoveg):
    return URL.subn("", szoveg)


def _md_link(szoveg):
    return MD_LINK.subn(r"\1", szoveg)


def _html_ki(szoveg):
    return HTML.subn("", szoveg)


def _nav_ki(szoveg):
    sorok = szoveg.split("\n")
    maradt = [s for s in sorok if not _nav_sor(s)]
    return "\n".join(maradt), len(sorok) - len(maradt)


def _ures_sorok(szoveg):
    return _TOBB_URES.subn("\n\n", szoveg)


def _szokozok(szoveg):
    uj, a = _TOBB_SZOKOZ.subn(" ", szoveg)
    uj, b = _SOR_VEGI.subn("", uj)
    return uj, a + b


def _ures_zarojel(szoveg):
    return _URES_ZAROJEL.subn("", szoveg)


# (kulcs, megnevezés a párbeszédben, függvény) — a sorrend SZÁMÍT:
# előbb a hivatkozás-szöveget mentjük ki, csak utána törlünk címeket.
SZABALYOK = [
    ("md", "Hivatkozások: a látható szöveg maradjon, a cím tűnjön el",
     _md_link),
    ("html", "HTML-címkék törlése (<p>, <a href=…>)", _html_ki),
    ("url", "Webcímek törlése a szövegből", _url_ki),
    ("nav", "Navigációs sorok törlése (következő fejezet, vissza a tetejére)",
     _nav_ki),
    ("zarojel", "Üresen maradt zárójelek törlése", _ures_zarojel),
    ("szokoz", "Dupla szóközök és sorvégi szóközök összevonása", _szokozok),
    ("ures", "Kettőnél több üres sor összevonása", _ures_sorok),
]

ALAP = {"md", "html", "url", "nav", "zarojel", "szokoz", "ures"}


def szamlal(szoveg: str) -> dict:
    """Szabályonként: hány helyen változtatna. NEM módosít semmit."""
    ki = {}
    for kulcs, _nev, fv in SZABALYOK:
        try:
            _uj, db = fv(szoveg)
        except Exception:
            db = 0
        ki[kulcs] = db
    return ki


def tisztit(szoveg: str, kulcsok) -> tuple:
    """A kiválasztott szabályok alkalmazása. Visszaad: (új szöveg, összesen)."""
    osszes = 0
    for kulcs, _nev, fv in SZABALYOK:
        if kulcs not in kulcsok:
            continue
        try:
            szoveg, db = fv(szoveg)
        except Exception:
            db = 0
        osszes += db
    return szoveg, osszes


def osszefoglalo(szamok: dict) -> str:
    """Egy mondat arról, mi várható — ezt mondjuk be a párbeszéd előtt."""
    reszek = []
    for kulcs, nev, _fv in SZABALYOK:
        db = szamok.get(kulcs, 0)
        if db:
            reszek.append("%s: %d" % (nev.split(":")[0].split("(")[0].strip(),
                                      db))
    if not reszek:
        return "Nem találtam tisztítanivalót ebben a szövegben."
    return "Találtam: " + "; ".join(reszek) + "."
