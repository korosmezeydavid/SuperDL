"""PDF → TXT: „szóközöket tett be minden karakter után" — Turai László,
2026-09-21.

    „Kaptam egy pdf dokumentumot, amit át szerettem volna konvertálni txt
     formába. Szóközöket tett be minden karakter után. Másik pdf jól
     konvertálódott."

A NAV-levél így jött ki:

    N e m z e ti A d ó - é s  V á m h iv a ta l

MÉRÉS (a beküldött PDF-en, 2026-09-21):

    kinyerő        egykarakteres „szavak"    /uni maradék
    pypdf                    75%                 114
    pypdf layout             53%                 114
    pdfminer.six              7%                   0     ← ép

AZ IGAZI HIBA. Nem az, hogy a pypdf nem boldogul ezzel a PDF-fel — hanem
hogy a program ezt NÉMÁN elfogadta, és „Kész"-t mondott rá. A másik PDF
azért konvertálódott jól, mert azt a pypdf is tudta; a felhasználó tehát
nem érthette, mitől függ.

Ezért mostantól: TÖBB kinyerőt próbálunk, a LEGÉPEBBET használjuk, és ha
a legjobb is szétesett, azt MEGMONDJUK.
"""

import pytest

from superdl import booktext as B


# ───────────────────── a mérőszám maga ──────────────────────────────

def test_az_ep_szoveg_pontszama_alacsony():
    ep = ("Nemzeti Adó- és Vámhivatal\n"
          "Kelet-budapesti Adó- és Vámigazgatósága\n"
          "Tisztelt Ügyfelünk! Az adószámla egyenlege a következő.")
    assert B.szetszabdalt(ep) < 0.15


def test_a_szetszabdalt_szoveg_pontszama_magas():
    """Pontosan az, amit Laci kapott."""
    rossz = ("N e m z e ti A d ó - é s  V á m h iv a ta l\n"
             "K e le t-b u d a p e s ti A d ó - é s  V á m ig a z g a tó s á g a")
    assert B.szetszabdalt(rossz) > 0.6


def test_az_ures_szoveg_a_legrosszabb():
    """Üresre ne mondjuk azt, hogy ép – különben az üres kinyerő nyerne."""
    assert B.szetszabdalt("") == 1.0
    assert B.szetszabdalt("   \n\n ") == 1.0


def test_a_hatar_a_ketto_koze_esik():
    """A küszöb ne legyen se túl szigorú, se túl engedékeny."""
    assert 0.15 < B.SZETSZABDALT_HATAR < 0.6


@pytest.mark.parametrize("szoveg", [
    "a",
    "I. fejezet",
    "A 4 és 5 közötti szám",          # mérőszáma 0,50 – pedig ÉP!
    "5 db, a 3 és a 7 is jó",
])
def test_rovid_szovegre_NEM_itelkezunk(szoveg):
    """⚠️ EZEN BUKOTT EL AZ ELSŐ VÁLTOZATOM. A magyarban sok az egybetűs
    szó („a", „s"), és a számok is külön állnak: az „A 4 és 5 közötti szám"
    mérőszáma 0,50 – pedig tökéletesen ép. Egy egysoros számlaértesítőt így
    hamisan riasztottunk volna. Kevés szónál tehát nem ítélkezünk."""
    assert B.gyanusan_szetesett(szoveg) is False


def test_eleg_hosszu_szetszabdalt_szovegre_IGENIS_itelkezunk():
    rossz = ("N e m z e ti A d ó - é s V á m h iv a ta l " * 12).strip()
    assert len(rossz.split()) >= B.MINTA_MINIMUM
    assert B.gyanusan_szetesett(rossz) is True


def test_eleg_hosszu_EP_szoveget_nem_riasztunk():
    ep = ("Tisztelt Ügyfelünk! Az adószámla egyenlege a mai napon "
          "nulla forint, tehát nincs tartozása és nincs túlfizetése. " * 4)
    assert len(ep.split()) >= B.MINTA_MINIMUM
    assert B.gyanusan_szetesett(ep) is False


def test_a_minta_minimum_ertelmes():
    assert 10 <= B.MINTA_MINIMUM <= 200


# ───────────── a kinyerő a LEGÉPEBBET válassza, ne az elsőt ─────────

def test_a_legepebb_kinyero_nyer(monkeypatch, tmp_path):
    """⚠️ EZ A LÉNYEG. A régi kód az első (pypdf) eredményt fogadta el."""
    pdf = tmp_path / "proba.pdf"
    pdf.write_bytes(b"%PDF-1.4 proba")
    monkeypatch.setattr(B, "_pdf_pdfminer",
                        lambda p: "Nemzeti Adó- és Vámhivatal")
    monkeypatch.setattr(B, "_pdf_pypdf",
                        lambda p: "N e m z e ti A d ó - é s V á m h iv a ta l")
    monkeypatch.setattr(B, "_pdf_cim", lambda p: "proba")
    book = B._from_pdf(pdf)
    assert book.text == "Nemzeti Adó- és Vámhivatal"
    assert book.gyanus is False


def test_forditva_is_a_legepebb_nyer(monkeypatch, tmp_path):
    """Nem a NÉV számít, hanem a minőség: ha a pypdf a jobb, az nyer."""
    pdf = tmp_path / "proba.pdf"
    pdf.write_bytes(b"%PDF-1.4 proba")
    monkeypatch.setattr(B, "_pdf_pdfminer",
                        lambda p: "N e m z e ti A d ó")
    monkeypatch.setattr(B, "_pdf_pypdf", lambda p: "Nemzeti Adó")
    monkeypatch.setattr(B, "_pdf_cim", lambda p: "proba")
    assert B._from_pdf(pdf).text == "Nemzeti Adó"


def test_egy_kinyero_kiesese_nem_baj(monkeypatch, tmp_path):
    """Régi telepítésen nem lesz pdfminer – attól még menjen."""
    pdf = tmp_path / "proba.pdf"
    pdf.write_bytes(b"%PDF-1.4 proba")

    def nincs(p):
        raise ImportError("nincs pdfminer")
    monkeypatch.setattr(B, "_pdf_pdfminer", nincs)
    monkeypatch.setattr(B, "_pdf_pypdf", lambda p: "Nemzeti Adó")
    monkeypatch.setattr(B, "_pdf_cim", lambda p: "proba")
    assert B._from_pdf(pdf).text == "Nemzeti Adó"


def test_ha_mindegyik_szetesett_akkor_SZOLUNK(monkeypatch, tmp_path):
    """A szöveg akkor is menjen (több a semminél), de a hívó tudja meg."""
    pdf = tmp_path / "proba.pdf"
    pdf.write_bytes(b"%PDF-1.4 proba")
    rossz = ("N e m z e ti A d ó - é s V á m h iv a ta l " * 12).strip()
    monkeypatch.setattr(B, "_pdf_pdfminer", lambda p: rossz)
    monkeypatch.setattr(B, "_pdf_pypdf", lambda p: rossz)
    monkeypatch.setattr(B, "_pdf_cim", lambda p: "proba")
    book = B._from_pdf(pdf)
    assert book.gyanus is True
    assert book.text.strip(), "a szöveg akkor is menjen"


def test_ha_egyik_sem_ad_semmit(monkeypatch, tmp_path):
    pdf = tmp_path / "proba.pdf"
    pdf.write_bytes(b"%PDF-1.4 proba")
    monkeypatch.setattr(B, "_pdf_pdfminer", lambda p: "")
    monkeypatch.setattr(B, "_pdf_pypdf", lambda p: "   ")
    monkeypatch.setattr(B, "_pdf_cim", lambda p: "proba")
    book = B._from_pdf(pdf)
    assert book.gyanus is True
    assert book.text == ""


# ───────────────── a /uniXXXX szemét eltakarítása ───────────────────

def test_a_glifnev_maradek_eltunik(monkeypatch, tmp_path):
    """A beküldött PDF-ben 114 darab `/uni00A0` került a szövegbe —
    a felolvasó ezt karakterenként mondta volna ki."""
    pdf = tmp_path / "proba.pdf"
    pdf.write_bytes(b"%PDF-1.4 proba")
    monkeypatch.setattr(B, "_pdf_pdfminer",
                        lambda p: "Tisztelt/uni00A0Ügyfelünk!/uni00A0")
    monkeypatch.setattr(B, "_pdf_pypdf", lambda p: "")
    monkeypatch.setattr(B, "_pdf_cim", lambda p: "proba")
    book = B._from_pdf(pdf)
    assert "/uni" not in book.text
    assert "Tisztelt" in book.text and "Ügyfelünk" in book.text


# ───────────────── a Book alapból nem gyanús ────────────────────────

def test_a_tobbi_formatum_valtozatlan():
    """A `gyanus` mező alapértéke hamis – a TXT/DOCX/EPUB út nem változott."""
    b = B.Book(title="x", sections=["szöveg"])
    assert b.gyanus is False
