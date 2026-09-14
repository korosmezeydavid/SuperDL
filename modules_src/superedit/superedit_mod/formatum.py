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


def _docx_olvas(ut: str) -> Dokumentum:
    import docx
    d = Dokumentum()
    doc = docx.Document(ut)
    for p in doc.paragraphs:
        stilus = "Normál"
        nev = (p.style.name or "") if p.style is not None else ""
        for szint in (1, 2, 3):
            if nev.lower() in (f"heading {szint}", f"címsor {szint}"):
                stilus = f"Címsor {szint}"
        futamok = [(r.text, bool(r.bold), bool(r.italic), bool(r.underline))
                   for r in p.runs if r.text]
        d.bekezdesek.append((p.text, stilus, futamok))
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


def _docx_ment(ut: str, bekezdesek) -> None:
    import docx
    doc = docx.Document()
    for bek in bekezdesek:
        szoveg, stilus, futamok = szet(bek)
        szint = {"Címsor 1": 1, "Címsor 2": 2, "Címsor 3": 3}.get(stilus)
        p = doc.add_heading("", level=szint) if szint else doc.add_paragraph()
        if not futamok:
            continue
        for reszszoveg, felkover, dolt, alahuzott in futamok:
            r = p.add_run(reszszoveg)
            # a címsor magától félkövér; ott csak akkor írjuk felül, ha kell
            if felkover or not szint:
                r.bold = bool(felkover)
            r.italic = bool(dolt)
            r.underline = bool(alahuzott)
    doc.save(ut)


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
