"""Könyv-szöveg kinyerése a hangoskönyv-készítőhöz.

Támogatott: TXT, DOCX, EPUB (tiszta szöveg), PDF (best-effort). A
visszaadott Book a címet és a szakaszokat (fejezeteket) tartalmazza – ez
kell az egyben vagy fejezetenkénti MP3-hoz, és a cím a hangos bevezetőhöz.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = (".txt", ".docx", ".epub", ".pdf")


@dataclass
class Book:
    title: str
    sections: list[str] = field(default_factory=list)
    # ⚠️ IGAZ, ha a kinyert szöveg GYANÚSAN szétesett (lásd `szetszabdalt`).
    # A régi kód ilyenkor is némán továbbadta a szemetet – Turai László
    # NAV-levele így lett „N e m z e ti A d ó - é s V á m h iv a ta l".
    # A szöveg így is megy (több a semminél), de a hívó MEGTUDJA, és
    # szólhat a felhasználónak.
    gyanus: bool = False

    @property
    def text(self) -> str:
        return "\n\n".join(s for s in self.sections if s.strip())

    @property
    def chars(self) -> int:
        return sum(len(s) for s in self.sections)


def _clean(t: str) -> str:
    """FELOLVASÁSHOZ való tisztítás: a soron belüli szóköz- és tabulátor-
    sorozatok egyetlen szóközzé olvadnak. Beszédnél ez helyes – a képernyő-
    olvasó és a beszédmotor nem tud mit kezdeni a tagoló szóközökkel."""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def clean_structured(t: str) -> str:
    """SZERKEZET-TARTÓ tisztítás: a tabulátorok és a sorkezdő behúzás
    MEGMARADNAK.

    Miért kell külön: egy műsorlistában, táblázatos jegyzetben vagy programban
    a tabulátor maga a tartalom – ha szóközre cseréljük, a tagolás elvész.
    Felolvasáshoz továbbra is a `_clean` való; fájl→fájl konvertáláshoz ez.
    (Laci jelzése nyomán, 2026-08-19.)"""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # soron belül csak a SOR VÉGI felesleget vágjuk le
    t = "\n".join(sor.rstrip() for sor in t.split("\n"))
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip("\n")


def _from_txt(path: Path) -> Book:
    # A KÖZÖS dekódolóval: a régi magyar kódlapok (CP1250, CP852, CWI-2) és a
    # kettős kódolás is helyreáll. Korábban itt fix UTF-8 + `errors="replace"`
    # volt, ezért a régi könyvekben a magyar betűk pótló jelre cserélődtek, és a
    # felolvasó a kacatot mondta be – LÁTHATATLAN adatvesztéssel.
    # [Herman Tibi TEXT-P0-01]
    from . import textdecode
    raw = textdecode.read_text_file(path)
    return Book(title=path.stem, sections=[_clean(raw)])


def _from_docx(path: Path) -> Book:
    import docx
    d = docx.Document(str(path))
    title = (d.core_properties.title or path.stem).strip() or path.stem
    sections: list[str] = []
    buf: list[str] = []
    for p in d.paragraphs:
        txt = p.text.strip()
        style = (p.style.name or "").lower() if p.style else ""
        if style.startswith("heading") and buf:
            sections.append(_clean("\n".join(buf)))
            buf = []
        if txt:
            buf.append(txt)
    if buf:
        sections.append(_clean("\n".join(buf)))
    if not sections:
        sections = [""]
    return Book(title=title, sections=sections)


def _from_epub(path: Path) -> Book:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub
    book = epub.read_epub(str(path))
    title = path.stem
    try:
        md = book.get_metadata("DC", "title")
        if md:
            title = md[0][0]
    except Exception:
        pass
    sections: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        txt = _clean(soup.get_text(separator="\n"))
        if txt:
            sections.append(txt)
    if not sections:
        sections = [""]
    return Book(title=title, sections=sections)


_UNI_MARADEK = re.compile(r"/uni[0-9A-Fa-f]{4}")


def szetszabdalt(szoveg: str) -> float:
    """Mennyire „szétesett" a kinyert szöveg? 0.0 = ép, 1.0 = minden
    karakter külön áll. Az egykarakteres „szavak" arányát adja vissza.

    ⚠️ MIÉRT KELL EZ (Turai László, 2026-09-21). Kapott egy hivatalos
    NAV-levelet PDF-ben, és a TXT-be így került:

        N e m z e ti A d ó - é s  V á m h iv a ta l

    Egy másik PDF ugyanakkor hibátlanul konvertálódott. A hiba tehát nem
    a konvertálásban volt, hanem abban, hogy a kinyerőnk némán rossz
    eredményt adott, és senki nem nézte meg, hogy értelmes-e."""
    szavak = (szoveg or "").split()
    if not szavak:
        return 1.0
    egyes = sum(1 for w in szavak if len(w) == 1)
    return egyes / len(szavak)


# ⚠️ ENNYI SZÓ ALATT NEM ÍTÉLKEZÜNK. A magyarban sok az egybetűs szó
# („a", „s"), és a számok is külön állnak: „A 4 és 5 közötti szám" mérőszáma
# 0,50 – pedig tökéletesen ép. Rövid szövegen tehát a mérőszám nem
# árulkodik, és egy egysoros számlaértesítőt hamisan riasztanánk. Laci
# NAV-levele 1325 szó volt.
MINTA_MINIMUM = 40


def gyanusan_szetesett(szoveg: str) -> bool:
    """Elég nagy-e a minta ahhoz, hogy ítéljünk – és ha igen, szétesett-e?"""
    if len((szoveg or "").split()) < MINTA_MINIMUM:
        return False
    return szetszabdalt(szoveg) >= SZETSZABDALT_HATAR


def _pdf_pdfminer(path: Path) -> str:
    """pdfminer.six – ez kezeli helyesen a karakterenként pozicionált
    (kerningelt) PDF-eket. Laci NAV-levelén 7% egykarakteres szó (ép),
    a pypdf-nél 75% volt."""
    from pdfminer.high_level import extract_text
    return extract_text(str(path)) or ""


def _pdf_pypdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(parts)


def _pdf_cim(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        if reader.metadata and reader.metadata.title:
            return reader.metadata.title
    except Exception:
        pass
    return path.stem


def _from_pdf(path: Path) -> Book:
    """PDF → szöveg. TÖBB kinyerőt próbálunk, és a LEGÉPEBBET használjuk.

    ⚠️ NEM az elsőt, amelyik ad valamit. Pontosan ez volt Laci hibája: a
    pypdf „sikeresen" kinyerte a szöveget, csak épp minden betű közé
    szóközt tett – és a program ezt kérdés nélkül elfogadta. A kinyerők
    erősségei PDF-enként különböznek, ezért a `szetszabdalt()` mérőszámmal
    döntünk, nem sorrenddel.

    Ha a legjobb is szétesett, a szöveg akkor is megy (több a semminél),
    de a hívó a `Book.gyanus` mezőből MEGTUDJA, és szólhat a
    felhasználónak – a néma rossz eredmény volt az igazi baj."""
    jeloltek = []
    for nev, fv in (("pdfminer", _pdf_pdfminer), ("pypdf", _pdf_pypdf)):
        try:
            szoveg = _UNI_MARADEK.sub("", fv(path) or "")
        except Exception:
            continue
        if szoveg.strip():
            jeloltek.append((szetszabdalt(szoveg), nev, szoveg))
    if not jeloltek:
        return Book(title=_pdf_cim(path), sections=[""], gyanus=True)
    jeloltek.sort(key=lambda t: t[0])
    _pont, _nev, legjobb = jeloltek[0]
    return Book(title=_pdf_cim(path), sections=[_clean(legjobb)],
                gyanus=gyanusan_szetesett(legjobb))


# e fölött a szöveg nyilvánvalóan szétesett (Laci PDF-je 0,75 volt, egy ép
# dokumentum 0,05–0,10 körül van)
SZETSZABDALT_HATAR = 0.35


def extract(path: str) -> Book:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".txt":
        return _from_txt(p)
    if ext == ".docx":
        return _from_docx(p)
    if ext == ".epub":
        return _from_epub(p)
    if ext == ".pdf":
        return _from_pdf(p)
    raise ValueError(f"Nem támogatott formátum: {ext}")
