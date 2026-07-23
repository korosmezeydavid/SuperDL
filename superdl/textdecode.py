# -*- coding: utf-8 -*-
"""KÖZÖS magyar szöveg-dekódoló (régi kódlapok + mojibake-helyreállítás).

MIÉRT KELL: a dokumentum-konverter fejlett felismerést használt (CP1250, CP852,
CWI-2, kettős kódolás), a KÖNYVOLVASÓ és a HANGOSKÖNYV-KÉSZÍTŐ viszont csak
UTF-8-at feltételezett (`errors="replace"`). Ugyanaz a régi magyar TXT az egyik
eszközben helyesen, a másikban KÉRDŐJELEKKEL nyílt meg – és a felolvasó a
kacatot mondta be, láthatatlan adatvesztéssel. [Herman Tibi TEXT-P0-01]

Egyetlen forrás, mindenki ezt használja.
"""
from __future__ import annotations

# az AUTOMATIKUS felismerés egybájtos jelöltjei (a legvalószínűbbtől); a helyeset
# NEM az „elsőként hibátlanul dekódol" választja (az iso-8859-2/cp852/cp437 MINDEN
# bájtot elfogad, így kacatot is), hanem a `decode_score` szerinti LEGJOBB.
TRY_ENC = ["cp1250", "cp852", "iso-8859-2", "cp437", "cp1252"]

# a helyes magyar dekódolás erős jelei
HU_CHARS = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"
# a magyar szövegben megszokott, nem-ASCII, de RENDBEN lévő írásjelek
OK_EXTRA = set("„”“‚’‘–—…«»•·§°€£")

# CWI-2 (régi magyar DOS-kódlap, ≈CP3845): a CP437-re épül; a magyar kisbetűk
# (á é í ó ö ú ü) és az É Ö Ü nagybetűk MÁR a CP437 helyükön vannak, csak a
# ő ű Ő Ű és néhány nagybetű (Á Í Ó Ú) kerül más pozícióra. Ezért a CP437-alapot
# vesszük, és CSAK ezt a 8 magyar pozíciót írjuk felül → teljes magyar lefedettség.
_CWI2_OVERRIDES = {0x8D: "Í", 0x8F: "Á", 0x93: "ő", 0x95: "Ó",
                   0x96: "ű", 0x97: "Ú", 0x98: "Ű", 0xA7: "Ő"}
_CWI2_TABLE = list(bytes(range(256)).decode("cp437"))
for _b, _ch in _CWI2_OVERRIDES.items():
    _CWI2_TABLE[_b] = _ch
_CWI2_TABLE = "".join(_CWI2_TABLE)


def decode_cwi2(data: bytes) -> str:
    """A régi magyar CWI-2 DOS-kódlapú bájtok Unicode-ra fejtése."""
    return "".join(_CWI2_TABLE[b] for b in data)


# --- KETTŐS KÓDOLÁS (CWI→CP1250→UTF-8 „mojibake") visszafejtése ----------
# Sok magyar Windows-eszköz (jegyzettömb, levelező) a régi CWI/DOS fájlt tévesen
# CP1250-ként OLVASSA, majd UTF-8-ként MENTI/KÜLDI. Az eredmény ÉRVÉNYES UTF-8,
# de a tartalma kacat (Á→Ź, Ó→•, É→U+0090…). Mivel a torzítás egy-az-egyben
# VISSZAFORDÍTHATÓ, helyre tudjuk állítani (Turai László mintája, 2026-07-06).
_CP1250_REV: dict[str, int] = {}
for _rb in range(256):
    try:
        _CP1250_REV[bytes([_rb]).decode("cp1250")] = _rb
    except UnicodeDecodeError:
        pass
for _rb in range(0x80, 0xA0):            # az 5 undefined C1-slot önmagára képezve
    _CP1250_REV.setdefault(chr(_rb), _rb)


def has_c1_controls(text: str) -> bool:
    """A C1 vezérlők (U+0080..U+009F) valós szövegben SOHA nem fordulnak elő; a
    jelenlétük a kettős kódolás (mojibake) erős, hamis-pozitívtól mentes jele."""
    return any(0x80 <= ord(c) <= 0x9F for c in text)


def undouble_cwi(uni: str) -> str:
    """A CWI→CP1250→UTF-8 mojibake visszafejtése: a CP1250-értelmezést
    visszabájtozzuk, majd a HELYES CWI-2 táblával dekódoljuk."""
    raw = bytes(_CP1250_REV.get(ch, ord(ch) & 0xFF) for ch in uni)
    return decode_cwi2(raw)


def read_cwi(data: bytes) -> str:
    """CWI-szöveg beolvasása AKÁR nyers egybájtos CWI, AKÁR CWI→CP1250→UTF-8
    kettős kódolás formában érkezik (a kézi „CWI" választás is ezt hívja)."""
    try:
        uni = data.decode("utf-8")
        if has_c1_controls(uni):        # valójában kettősen kódolt CWI
            return undouble_cwi(uni)
    except UnicodeDecodeError:
        pass
    return decode_cwi2(data)            # valódi egybájtos CWI


def decode_score(text: str) -> int:
    """A dekódolt szöveg „hihetőségének" pontszáma. A magyar ékezetes betűk
    ERŐSEN növelik, a vezérlő-/dobozrajz-/pótló-karakterek CSÖKKENTIK – így a
    régi DOS-kódlapok (cp852/cp437) helyesen felismerhetők a mindent elfogadó
    iso-8859-2 helyett."""
    good = bad = 0
    for ch in text:
        if ch in "\r\n\t":
            continue
        o = ord(ch)
        if ch in HU_CHARS:              # magyar ékezetes – a jó kódlap erős jele
            good += 3
        elif o < 0x80:                  # ASCII
            if o < 32 or o == 0x7f:     # vezérlőkarakter
                bad += 5
            else:                       # normál ASCII betű/szám/írásjel
                good += 1
        elif ch in OK_EXTRA:            # megszokott európai írásjel
            good += 1
        else:                           # bármi más nem-ASCII (nem magyar): gyanús
            bad += 2                    # (Š, Ł, ŕ, ˘, dobozrajz, pótló-karakter…)
    return good - bad


def auto_decode(data: bytes) -> str:
    """A bájtokat a legvalószínűbb kódlappal fejti meg: előbb szigorú UTF-8
    (ha tiszta), aztán a jelöltek közül a `decode_score` szerinti LEGJOBB.
    Kezeli a CWI→CP1250→UTF-8 kettős kódolást is (érvényes UTF-8, de kacat)."""
    utf = None
    for enc in ("utf-8-sig", "utf-8"):
        try:
            utf = data.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    # tiszta UTF-8 (nincs gyanús C1-vezérlő) → kész, semmi regresszió a jó fájlokon
    if utf is not None and not has_c1_controls(utf):
        return utf
    if utf is not None:
        # érvényes UTF-8, de C1-vezérlőkkel → valószínű kettős kódolás:
        # az „ahogy van" UTF-8 vs. a visszafejtett CWI közül a jobb pontszámú nyer
        candidates = [utf, undouble_cwi(utf)]
    else:
        # nem UTF-8 → egybájtos jelöltek + a nyers CWI-2 tábla
        candidates = [data.decode(e, errors="replace") for e in TRY_ENC]
        candidates.append(decode_cwi2(data))
    best_text, best_score = None, None
    for t in candidates:
        sc = decode_score(t)
        if best_score is None or sc > best_score:
            best_text, best_score = t, sc
    return best_text if best_text is not None else data.decode("utf-8",
                                                               errors="replace")


def read_text_file(path) -> str:
    """Egy szövegfájl beolvasása a legjobb kódlappal (a könyves eszközökhöz)."""
    from pathlib import Path as _P
    return auto_decode(_P(path).read_bytes())
