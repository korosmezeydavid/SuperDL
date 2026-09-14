# -*- coding: utf-8 -*-
"""A formázás HALLHATÓVÁ tétele — ez a modul lényege.

Egy látó ember a félkövért LÁTJA. Vakon a formázás vagy láthatatlan, vagy
kimondhatatlan — ezért használ sok vak felhasználó sima szövegfájlt még ott
is, ahol formázott dokumentumot várnak tőle.

Ez a szerkesztő nem attól lesz több a Jegyzettömbnél, hogy tud félkövért.
Attól, hogy MEGMONDJA. Két úton:

  * kérésre (Ctrl+Shift+I) — a teljes formázás egy mondatban;
  * váltáskor — amikor a kurzor formázott részbe lép vagy kilép belőle,
    RÖVIDEN szól („félkövér", „normál"). Ez kikapcsolható.

A rövid változat azért rövid, mert gépelés és nyilazás közben hangzik el: ott
egy teljes mondat útban van. A hosszú változat azért teljes, mert azt a
felhasználó KÉRTE, tehát meg akarja hallgatni.
"""


def _meret(pontok) -> str:
    try:
        return "%g" % float(pontok)
    except (TypeError, ValueError):
        return ""


def jegyek(betu, igazitas="", stilus="") -> list:
    """A bekapcsolt jelölések listája, magyarul."""
    ki = []
    if betu is None:
        return ki
    try:
        if betu.GetWeight() >= 600:
            ki.append("félkövér")
        if betu.GetStyle() == 93:            # wx.FONTSTYLE_ITALIC
            ki.append("dőlt")
        if betu.GetUnderlined():
            ki.append("aláhúzott")
        if betu.GetStrikethrough():
            ki.append("áthúzott")
    except Exception:
        pass
    return ki


def rovid(elozo: list, mostani: list) -> str:
    """A VÁLTÁS bemondása: csak ami megváltozott, egy-két szóban.

    Ha félkövérbe lépsz: „félkövér". Ha kilépsz belőle és nincs más jelölés:
    „normál". Ha dőltből félkövérbe: „félkövér" — a megszűnt jelölést nem
    soroljuk fel, mert gépelés közben az több zaj, mint haszon.
    """
    e, m = set(elozo or []), set(mostani or [])
    if e == m:
        return ""
    uj = [j for j in (mostani or []) if j not in e]
    if uj:
        return ", ".join(uj)
    return "normál" if not m else ", ".join(mostani)


def teljes(betu, igazitas="", stilus="", kijelolt=False) -> str:
    """A TELJES formázás egy mondatban — a Ctrl+Shift+I válasza."""
    reszek = []
    if stilus and stilus != "Normál":
        reszek.append(stilus)
    if betu is not None:
        try:
            nev = betu.GetFaceName()
            if nev:
                reszek.append(nev)
        except Exception:
            pass
        try:
            m = _meret(betu.GetPointSize())
            if m:
                reszek.append(f"{m} pont")
        except Exception:
            pass
    j = jegyek(betu)
    reszek.extend(j if j else ["normál"])
    if igazitas:
        reszek.append(igazitas)
    eleje = "A kijelölés formázása: " if kijelolt else "A kurzornál: "
    return eleje + ", ".join(reszek) + "."


IGAZITAS_NEVEK = {
    1: "balra igazítva",       # wx.TEXT_ALIGNMENT_LEFT
    2: "középre igazítva",     # CENTRE
    3: "jobbra igazítva",      # RIGHT
    4: "sorkizárt",            # JUSTIFIED
}


def igazitas_neve(kod) -> str:
    return IGAZITAS_NEVEK.get(int(kod or 0), "")


def hely(sor: int, sorok: int, bekezdes: int = 0) -> str:
    """„Hol vagyok?" — sor és bekezdés, kimondva."""
    reszek = [f"{sor}. sor a {sorok}-ból"]
    if bekezdes:
        reszek.append(f"{bekezdes}. bekezdés")
    return ", ".join(reszek) + "."


def meret_szoveg(szavak: int, karakterek: int, bekezdesek: int) -> str:
    """A számláló bemondása. Az oldalszám BECSLÉS, és ezt ki is mondjuk —
    egy pontosnak látszó, valójában tippelt szám rosszabb, mint egy vállalt
    becslés."""
    oldal = max(1, round(karakterek / 1800))
    return (f"{szavak} szó, {karakterek} karakter, {bekezdesek} bekezdés, "
            f"körülbelül {oldal} oldal.")
