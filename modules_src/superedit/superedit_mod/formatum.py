# -*- coding: utf-8 -*-
"""Fájlformátumok: megnyitás és mentés.

Amit ÍRNI is tudunk: .docx (ez az alapértelmezett), .txt, .html, .md.
Amit csak OLVASNI: .pdf, .epub — ezekbe visszaírni nem tudunk rendesen, ezért
NEM is teszünk úgy, mintha tudnánk. A megnyitáskor kimondjuk, és a mentés
.docx-et ajánl helyettük.

⚠️ A .docx oda-vissza NEM veszteségmentes. A python-docx nem ismer minden
Word-formázást (táblázat, kép, lábjegyzet, változáskövetés). Ha ilyet találunk
megnyitáskor, azt MEGMONDJUK — a néma egyszerűsítés az a fajta hiba, amire a
felhasználó csak hetekkel később jön rá, amikor már késő.
"""

import os
import re

IRHATO = (".docx", ".txt", ".html", ".htm", ".md", ".markdown", ".log")
CSAK_OLVASHATO = (".pdf", ".epub")
MIND = IRHATO + CSAK_OLVASHATO

SZUROK = ("Word-dokumentum (*.docx)|*.docx|"
          "Szövegfájl (*.txt)|*.txt|"
          "Weblap (*.html)|*.html;*.htm|"
          "Markdown (*.md)|*.md;*.markdown|"
          "Minden támogatott|*.docx;*.txt;*.html;*.htm;*.md;*.markdown;"
          "*.log;*.pdf;*.epub")


def szet(bekezdes):
    """Egy bekezdés szétszedve: (szöveg, stílus, futamok).

    A bekezdés lehet 2-es (szöveg, stílus) vagy 3-as (szöveg, stílus,
    futamok). A futamok listája: [(részszöveg, félkövér, dőlt, aláhúzott)].
    Ha nincs futam, a teljes szöveg egy jelöletlen futam — így a mentőknek
    NEM kell két esetet ismerniük, és nem lehet elfelejteni az egyiket.
    """
    szoveg = bekezdes[0]
    stilus = bekezdes[1] if len(bekezdes) > 1 else "Normál"
    futamok = bekezdes[2] if len(bekezdes) > 2 else None
    if not futamok:
        futamok = [(szoveg, False, False, False)] if szoveg else []
    return szoveg, stilus, futamok


class Dokumentum:
    """Egy megnyitott dokumentum: bekezdések és a hozzájuk tartozó stílus.

    Szándékosan EGYSZERŰ modell: bekezdésenként egy szöveg, egy stílusnév
    (Normál, Címsor 1-3) és a betű-szintű jelölések FUTAMOKBAN
    (félkövér, dőlt, aláhúzott). Ennél többet a Super Edit nem ígér, tehát
    ennél többet nem is veszíthet el csendben.
    """

    def __init__(self):
        self.bekezdesek = []      # [(szoveg, stilus, futamok)]
        self.figyelmeztetes = ""  # amit a megnyitáskor ki kell mondani

    @property
    def szoveg(self) -> str:
        return "\n".join(b[0] for b in self.bekezdesek)


def csak_olvashato(ut: str) -> bool:
    return os.path.splitext(ut or "")[1].lower() in CSAK_OLVASHATO


def tamogatott(ut: str) -> bool:
    return os.path.splitext(ut or "")[1].lower() in MIND


# ---- megnyitás ---------------------------------------------------------

def megnyit(ut: str) -> Dokumentum:
    """A fájl beolvasása. Hibát DOB, ha nem megy – a hívó kimondja."""
    kit = os.path.splitext(ut)[1].lower()
    if kit == ".docx":
        return _docx_olvas(ut)
    if kit in (".html", ".htm"):
        return _html_olvas(ut)
    if kit in CSAK_OLVASHATO:
        return _kinyer(ut)
    return _szoveg_olvas(ut)


def _szoveg_olvas(ut: str) -> Dokumentum:
    d = Dokumentum()
    nyers = open(ut, "rb").read()
    for kodolas in ("utf-8-sig", "utf-8", "cp1250", "latin-2"):
        try:
            szoveg = nyers.decode(kodolas)
            break
        except UnicodeDecodeError:
            continue
    else:
        szoveg = nyers.decode("utf-8", "replace")
        d.figyelmeztetes = ("A fájl kódolását nem sikerült pontosan "
                            "megállapítani; néhány ékezet hibás lehet.")
    d.bekezdesek = [(s, "Normál") for s in szoveg.replace("\r\n", "\n")
                    .replace("\r", "\n").split("\n")]
    return d


_HAMIS = ("0", "false", "off")


def _kapcsolo(rpr, nev, qn) -> bool:
    """Egy rPr-kapcsoló (w:b, w:i) értéke: jelen van és nem „0/false/off"."""
    if rpr is None:
        return False
    e = rpr.find(qn(nev))
    return e is not None and (e.get(qn("w:val")) or "true").lower() not in _HAMIS


def _docx_olvas(ut: str) -> Dokumentum:
    """Word-dokumentum beolvasása KÖZVETLENÜL az XML-fából.

    ⚠️ A python-docx `p.style` / `p.runs` / `r.text` útja bekezdésenként
    több keresést fut: egy 40 000 bekezdéses dokumentum megnyitása ~90 mp
    volt (mérés, 2026-09-26). Itt egyetlen bejárás – ugyanazt adja vissza,
    amit a régi út (szöveg, stílus, futamok), a hivatkozások szövegével."""
    import docx
    from docx.oxml.ns import qn
    d = Dokumentum()
    doc = docx.Document(ut)
    # stílus-azonosító → név, EGYSZER
    nevek = {}
    for s in doc.styles:
        try:
            nevek[s.style_id] = s.name or ""
        except Exception:
            continue
    W_P, W_R, W_HL = qn("w:p"), qn("w:r"), qn("w:hyperlink")
    W_PPR, W_PSTYLE, W_RPR, W_VAL = (qn("w:pPr"), qn("w:pStyle"),
                                    qn("w:rPr"), qn("w:val"))
    W_T, W_TAB, W_PTAB = qn("w:t"), qn("w:tab"), qn("w:ptab")
    W_BR, W_CR, W_NBH = qn("w:br"), qn("w:cr"), qn("w:noBreakHyphen")
    W_U = qn("w:u")
    for p in doc.element.body.iterchildren(W_P):
        stilus = "Normál"
        ppr = p.find(W_PPR)
        ps = ppr.find(W_PSTYLE) if ppr is not None else None
        nev = nevek.get(ps.get(W_VAL), "") if ps is not None else ""
        for szint in (1, 2, 3):
            if nev.lower() in (f"heading {szint}", f"címsor {szint}"):
                stilus = f"Címsor {szint}"
        futamok, reszek = [], []
        for elem in p:
            if elem.tag == W_R:
                runok = (elem,)
            elif elem.tag == W_HL:
                runok = tuple(elem.iterchildren(W_R))
            else:
                continue
            for r in runok:
                sz = []
                for c in r:
                    if c.tag == W_T:
                        sz.append(c.text or "")
                    elif c.tag in (W_TAB, W_PTAB):
                        sz.append("\t")
                    elif c.tag == W_CR or (c.tag == W_BR and (
                            c.get(qn("w:type")) or "textWrapping")
                            == "textWrapping"):
                        # az oldal- és hasábtörés nem szöveg (a python-docx
                        # is üresnek veszi)
                        sz.append("\n")
                    elif c.tag == W_NBH:
                        sz.append("-")
                szoveg = "".join(sz)
                if not szoveg:
                    continue
                reszek.append(szoveg)
                rpr = r.find(W_RPR)
                u = rpr.find(W_U) if rpr is not None else None
                alahuzott = u is not None and \
                    (u.get(W_VAL) or "single").lower() not in ("none",) + _HAMIS
                futamok.append((szoveg, _kapcsolo(rpr, "w:b", qn),
                                _kapcsolo(rpr, "w:i", qn), alahuzott))
        d.bekezdesek.append(("".join(reszek), stilus, futamok))
    # ⚠️ amit NEM tudunk visszaírni – ezt ki kell mondani, nem elhallgatni
    veszit = []
    if doc.tables:
        veszit.append(f"{len(doc.tables)} táblázat")
    try:
        if doc.inline_shapes:
            veszit.append(f"{len(doc.inline_shapes)} kép")
    except Exception:
        pass
    if veszit:
        d.figyelmeztetes = (
            "Ebben a dokumentumban van " + " és ".join(veszit) +
            ". A Super Edit ezeket nem tudja szerkeszteni, és mentéskor "
            "KIMARADNÁNAK. Ha meg akarod tartani, mentsd más néven, vagy "
            "szerkeszd Wordben.")
    return d


def _html_olvas(ut: str) -> Dokumentum:
    from bs4 import BeautifulSoup
    d = Dokumentum()
    leves = BeautifulSoup(open(ut, encoding="utf-8", errors="replace").read(),
                          "html.parser")
    for elem in leves.find_all(["h1", "h2", "h3", "p", "li", "div"]):
        szoveg = elem.get_text(" ", strip=True)
        if not szoveg:
            continue
        nev = elem.name
        stilus = {"h1": "Címsor 1", "h2": "Címsor 2",
                  "h3": "Címsor 3"}.get(nev, "Normál")
        d.bekezdesek.append((szoveg, stilus))
    if not d.bekezdesek:
        d.bekezdesek = [(leves.get_text("\n", strip=True), "Normál")]
    return d


def _kinyer(ut: str) -> Dokumentum:
    """PDF és EPUB: a Core szövegkinyerőjével, CSAK olvasásra."""
    from superdl import booktext
    d = Dokumentum()
    konyv = booktext.extract(ut)
    szoveg = getattr(konyv, "text", "") or ""
    d.bekezdesek = [(s, "Normál") for s in szoveg.split("\n")]
    d.figyelmeztetes = (
        "Ez a fájl csak OLVASÁSRA nyílt meg: a formázását nem tudjuk "
        "visszaírni. Ha szerkeszted, mentsd Word-dokumentumként.")
    return d


# ---- mentés ------------------------------------------------------------

def ment(ut: str, bekezdesek) -> None:
    """Mentés a kiterjesztés szerint. Hibát DOB, ha nem megy."""
    kit = os.path.splitext(ut)[1].lower()
    if kit == ".docx":
        _docx_ment(ut, bekezdesek)
    elif kit in (".html", ".htm"):
        _html_ment(ut, bekezdesek)
    elif kit == ".pdf":
        _pdf_ment(ut, bekezdesek)
    else:
        _szoveg_ment(ut, bekezdesek)


def _szoveg_ment(ut: str, bekezdesek) -> None:
    # A sima szövegfájl nem ismer formázást – ezt a hívó mondja ki, nem itt
    # hallgatjuk el.
    with open(ut, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(b[0] for b in bekezdesek))


# az XML-ben tiltott vezérlőkarakterek (a lxml elutasítaná őket, és akkor a
# mentés elszállna – pl. PDF-ből kinyert szövegben előfordulnak)
_TILTOTT = dict.fromkeys(c for c in range(32) if c not in (9, 10, 13))
_TAGOLO = re.compile(r"([\t\n])")


def _docx_ment(ut: str, bekezdesek) -> None:
    """Word-mentés KÖZVETLENÜL az XML-fába.

    ⚠️ Farkas István hibajelentése (2026-09-25): egy nagy dokumentum
    mentése ~40 másodpercre megakasztotta a programot. A python-docx
    `add_run()` + `run.text =` futamonként XPath-keresést fut (a
    `clear_content`), ez ezer bekezdésenként ~1 mp. Itt ugyanazt az XML-t
    mi rakjuk össze, keresés nélkül – ugyanaz a Word-fájl, töredék idő alatt.
    """
    import docx
    from docx.oxml.ns import qn
    from lxml import etree

    doc = docx.Document()
    torzs = doc.element.body
    sectpr = torzs.find(qn("w:sectPr"))
    W_P, W_PPR, W_PSTYLE = qn("w:p"), qn("w:pPr"), qn("w:pStyle")
    W_R, W_RPR, W_T = qn("w:r"), qn("w:rPr"), qn("w:t")
    W_B, W_I, W_U, W_VAL = qn("w:b"), qn("w:i"), qn("w:u"), qn("w:val")
    W_TAB, W_BR = qn("w:tab"), qn("w:br")
    XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
    # a „Címsor N" stílus azonosítója a sablonban (ugyanaz, amit az
    # add_heading() használna)
    stilus_id = {}
    for szint in (1, 2, 3):
        try:
            stilus_id[szint] = doc.styles["Heading %d" % szint].style_id
        except KeyError:
            stilus_id[szint] = "Heading%d" % szint

    uj_p = []
    for bek in bekezdesek:
        szoveg, stilus, futamok = szet(bek)
        szint = {"Címsor 1": 1, "Címsor 2": 2, "Címsor 3": 3}.get(stilus)
        p = etree.Element(W_P)
        if szint:
            ppr = etree.SubElement(p, W_PPR)
            etree.SubElement(ppr, W_PSTYLE).set(W_VAL, stilus_id[szint])
        for reszszoveg, felkover, dolt, alahuzott in futamok:
            if not reszszoveg:
                continue
            r = etree.SubElement(p, W_R)
            if felkover or dolt or alahuzott:
                rpr = etree.SubElement(r, W_RPR)
                if felkover:
                    etree.SubElement(rpr, W_B)
                if dolt:
                    etree.SubElement(rpr, W_I)
                if alahuzott:
                    etree.SubElement(rpr, W_U).set(W_VAL, "single")
            # a tabulátor és a sortörés a Wordben külön elem (a python-docx
            # `run.text` is így írta)
            tiszta = reszszoveg.translate(_TILTOTT).replace("\r", "")
            for darab in _TAGOLO.split(tiszta):
                if darab == "\t":
                    etree.SubElement(r, W_TAB)
                elif darab == "\n":
                    etree.SubElement(r, W_BR)
                elif darab:
                    t = etree.SubElement(r, W_T)
                    t.text = darab
                    t.set(XML_SPACE, "preserve")
        uj_p.append(p)
    if sectpr is not None:
        hely = list(torzs).index(sectpr)
        torzs[hely:hely] = uj_p
    else:
        torzs.extend(uj_p)
    # félkész fájl helyett: ideiglenes névre, aztán csere (egy megszakított
    # mentés ne tegye tönkre a meglévő dokumentumot)
    tmp = ut + ".mentes.tmp"
    try:
        doc.save(tmp)
        os.replace(tmp, ut)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _html_ment(ut: str, bekezdesek) -> None:
    from html import escape
    sorok = ["<!doctype html>", '<html lang="hu"><head>',
             '<meta charset="utf-8">',
             "<title>%s</title>" % escape(os.path.basename(ut)),
             "</head><body>"]
    for bek in bekezdesek:
        szoveg, stilus, futamok = szet(bek)
        szint = {"Címsor 1": 1, "Címsor 2": 2, "Címsor 3": 3}.get(stilus)
        cimke = f"h{szint}" if szint else "p"
        belso = ""
        for reszszoveg, felkover, dolt, alahuzott in futamok:
            darab = escape(reszszoveg)
            for kell, tag in ((felkover, "strong"), (dolt, "em"),
                              (alahuzott, "u")):
                if kell:
                    darab = f"<{tag}>{darab}</{tag}>"
            belso += darab
        sorok.append(f"<{cimke}>{belso}</{cimke}>")
    sorok += ["</body></html>"]
    with open(ut, "w", encoding="utf-8") as f:
        f.write("\n".join(sorok))


def _pdf_ment(ut: str, bekezdesek) -> None:
    """PDF-EXPORT. Nem szerkeszthető formátum – egyirányú út."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # a beépített betűkészlet latin-1; az ékezeteket megtartjuk, amit lehet
    pdf.set_font("Helvetica", size=12)
    for bek in bekezdesek:
        szoveg, stilus, futamok = szet(bek)
        szint = {"Címsor 1": 18, "Címsor 2": 15, "Címsor 3": 13}.get(stilus)
        # ⚠️ A `multi_cell` a JELENLEGI x-től a jobb margóig ír. Az előző
        # bekezdés után az x a sor végén állhat, és akkor „nincs elég hely egy
        # karakternek" hibával elszáll. Ezért minden bekezdés a bal margón
        # kezdődik.
        pdf.set_x(pdf.l_margin)
        if not futamok:
            pdf.set_font("Helvetica", "", 12)
            pdf.multi_cell(w=pdf.epw, h=8, text=" ",
                           new_x="LMARGIN", new_y="NEXT")
            continue
        for reszszoveg, felkover, dolt, alahuzott in futamok:
            jel = ("B" if (felkover or szint) else "") + ("I" if dolt else "")
            if alahuzott:
                jel += "U"
            pdf.set_font("Helvetica", jel, szint or 12)
            biztos = reszszoveg.encode("latin-1", "replace").decode("latin-1")
            # a write() sortörve folytatja a soron belül – így egy bekezdésben
            # több különböző jelölésű futam is megfér
            pdf.write(8, biztos)
        pdf.ln(8)
    pdf.output(ut)
