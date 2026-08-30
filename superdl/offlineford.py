# -*- coding: utf-8 -*-
"""OFFLINE FORDÍTÁS – a szöveg EL SEM HAGYJA A GÉPET.

Miért a magban van? Mert fordított (bináris) futtatókörnyezetet igényel
(CTranslate2), amit egy modul-ZIP nem tud telepíteni a lefagyasztott programba.
A modulok (pl. a Super Mail) ezen a rétegen át érik el – ha a Core régebbi és
nincs benne, a modul szépen visszalép az online fordításra.

MI KELL HOZZÁ?
  • a programba épített futtatókörnyezet (CTranslate2 + szövegdaraboló) – ez
    már itt van;
  • NYELVENKÉNT egy modell-csomag, amit a felhasználó tölt le EGYSZER
    (kb. 60–100 MB), és utána örökre offline megy.

A modellek az Argos OpenTech nyílt (MIT/CC) csomagjai. KÉTFÉLE szövegdarabolót
használnak – van, amelyik `bpe.model`-t (subword-nmt), van, amelyik
`sentencepiece.model`-t. A motor MINDKETTŐT kezeli (élesben mindkettőt
kipróbáltuk: en→hu BPE-vel, pl→en sentencepiece-szel).

PIVOT: a nyílt modellek angol-központúak, tehát lengyel→magyar úgy megy, hogy
lengyel→angol→magyar. Ezt kimondjuk a felhasználónak, mert két lépés két
modellt (és két letöltést) jelent, a minőség pedig kicsit gyengébb.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import threading
import urllib.request
import zipfile
from pathlib import Path

INDEX_URL = ("https://raw.githubusercontent.com/argosopentech/argospm-index/"
             "main/index.json")
_FEJ = {"User-Agent": "SuperDL/4.5 (offline-translate)"}
_zar = threading.Lock()
_betoltott: dict = {}          # (honnan,hova) -> motor, hogy ne töltsük újra


def modell_mappa() -> Path:
    return Path.home() / ".superdl" / "forditomodellek"


def ct2():
    """A CTranslate2 futtatókörnyezet behozása – a KÉSZ programban is.

    Miért nem elég a sima `import ctranslate2`:

    A fagyasztott (PyInstaller) programból SZÁNDÉKOSAN kihagyjuk a
    `ctranslate2.converters` alcsomagot, mert az a torch-ot húzná be
    (+365 megabájt), a fordításhoz viszont semmi köze – az csak modellek
    ÁTALAKÍTÁSÁHOZ kell, mi meg kész modelleket töltünk le.

    Csakhogy a csomag `__init__.py`-ja FELTÉTEL NÉLKÜL importálja
    (`from ctranslate2 import converters, models, specs`), ezért a kész
    programban a sima `import ctranslate2` ImportError-ral elszállt. Innen a
    hiba, amit Dávid látott: az F9 csak KÉT fordítót ajánlott fel, a helyben
    futó – ami pedig ott van a gépen – csendben eltűnt a listából, mert az
    `elerheto()` hamisat adott. Forrásból futtatva sosem látszott, ott
    ugyanis a converters megvan. [2026-08-30]

    Megoldás: ha az import a hiányzó converters miatt hasal el, beadunk a
    helyére egy ÜRES pótmodult, és újrapróbáljuk. A DLL-betöltést és a
    `_ext` bővítményt így is a csomag saját `__init__`-je végzi el."""
    import sys
    import types
    try:
        import ctranslate2
        return ctranslate2
    except ImportError:
        pass
    sys.modules.setdefault("ctranslate2.converters",
                           types.ModuleType("ctranslate2.converters"))
    sys.modules.pop("ctranslate2", None)
    import ctranslate2
    return ctranslate2


def elerheto() -> bool:
    """Van-e a programban fordító-futtatókörnyezet? (Régi Core-ban nincs.)"""
    try:
        ct2()
        return True
    except Exception:
        return False


def telepitett_parok() -> list:
    """A már letöltött nyelvpárok: [(honnan, hova), …]."""
    ki = []
    gyoker = modell_mappa()
    if not gyoker.is_dir():
        return ki
    for m in sorted(gyoker.iterdir()):
        adat = m / "metadata.json"
        if not adat.is_file():
            continue
        try:
            d = json.loads(adat.read_text(encoding="utf-8"))
            ki.append((d["from_code"], d["to_code"]))
        except Exception:
            continue
    return ki


def _index() -> list:
    keres = urllib.request.Request(INDEX_URL, headers=_FEJ)
    with urllib.request.urlopen(keres, timeout=60) as v:
        return json.loads(v.read().decode("utf-8", "replace"))


def utvonal(honnan: str, hova: str, index=None) -> list:
    """MELYIK modellek kellenek? Közvetlen pár, vagy angolon át (pivot).
    Üres lista = ezt a nyelvet nem tudjuk offline fordítani."""
    index = index if index is not None else _index()
    parok = {(p.get("from_code"), p.get("to_code")): p for p in index}
    if (honnan, hova) in parok:
        return [parok[(honnan, hova)]]
    if (honnan, "en") in parok and ("en", hova) in parok:
        return [parok[(honnan, "en")], parok[("en", hova)]]
    return []


def hianyzo(honnan: str, hova: str, index=None) -> list:
    """A `utvonal`-ból az, ami MÉG NINCS letöltve."""
    megvan = set(telepitett_parok())
    return [p for p in utvonal(honnan, hova, index)
            if (p["from_code"], p["to_code"]) not in megvan]


def _csomag_url(p: dict) -> str:
    for kulcs in ("links", "link", "url"):
        ertek = p.get(kulcs)
        if isinstance(ertek, list) and ertek:
            return ertek[0]
        if isinstance(ertek, str) and ertek:
            return ertek
    return ""


def letolt(p: dict, halad=None) -> Path:
    """Egy modell-csomag letöltése és kicsomagolása. A csomag ~60–100 MB, de
    EGYSZER kell, utána offline megy."""
    url = _csomag_url(p)
    if not url:
        raise RuntimeError("Ehhez a nyelvpárhoz nincs letöltési cím.")
    cel = modell_mappa() / ("%s_%s" % (p["from_code"], p["to_code"]))
    if (cel / "metadata.json").is_file():
        return cel
    cel.parent.mkdir(parents=True, exist_ok=True)
    ideiglenes = cel.parent / (cel.name + ".letoltes")
    keres = urllib.request.Request(url, headers=_FEJ)
    with urllib.request.urlopen(keres, timeout=900) as v:
        ossz = int(v.headers.get("Content-Length", 0) or 0)
        kesz = 0
        with open(ideiglenes, "wb") as f:
            while True:
                b = v.read(1 << 20)
                if not b:
                    break
                f.write(b)
                kesz += len(b)
                if halad and ossz:
                    halad(kesz / ossz)
    # A csomag egyetlen mappát tartalmaz – annak a TARTALMÁT tesszük a helyére.
    ideiglenes_mappa = cel.parent / (cel.name + ".kicsom")
    shutil.rmtree(ideiglenes_mappa, ignore_errors=True)
    with zipfile.ZipFile(ideiglenes) as z:
        z.extractall(ideiglenes_mappa)
    belso = [x for x in ideiglenes_mappa.iterdir() if x.is_dir()]
    forras = belso[0] if len(belso) == 1 else ideiglenes_mappa
    shutil.rmtree(cel, ignore_errors=True)
    shutil.move(str(forras), str(cel))
    shutil.rmtree(ideiglenes_mappa, ignore_errors=True)
    try:
        os.remove(ideiglenes)
    except OSError:
        pass
    # a stanza-mappa csak mondatvágáshoz kellene – nálunk saját vágó van,
    # ezért kidobjuk (több tíz megabájt megspórolva a felhasználó gépén)
    shutil.rmtree(cel / "stanza", ignore_errors=True)
    return cel


class _Motor:
    """Egy nyelvpár betöltött modellje. Kétféle szövegdarabolót kezel, mert a
    csomagok kétfélét használnak (`bpe.model` vagy `sentencepiece.model`)."""

    def __init__(self, mappa: Path, honnan: str, hova: str):
        ctranslate2 = ct2()          # a kész programban is működő behozás
        self.honnan, self.hova = honnan, hova
        self.ford = ctranslate2.Translator(str(mappa / "model"), device="cpu")
        self.bpe = self.sp = None
        if (mappa / "bpe.model").is_file():
            from subword_nmt import apply_bpe
            self.bpe = apply_bpe.BPE(
                io.open(str(mappa / "bpe.model"), encoding="utf-8"))
        elif (mappa / "sentencepiece.model").is_file():
            import sentencepiece
            self.sp = sentencepiece.SentencePieceProcessor(
                str(mappa / "sentencepiece.model"))
        else:
            raise RuntimeError("A modell-csomagból hiányzik a szövegdaraboló.")
        from sacremoses import MosesDetokenizer, MosesTokenizer
        self.mt = MosesTokenizer(lang=honnan)
        self.md = MosesDetokenizer(lang=hova)

    def fordit(self, mondatok: list) -> list:
        if self.sp is not None:
            koteg = [self.sp.encode(m, out_type=str) for m in mondatok]
        else:
            koteg = [self.bpe.process_line(
                " ".join(self.mt.tokenize(m, escape=False))).split()
                for m in mondatok]
        ki = self.ford.translate_batch(koteg, beam_size=4)
        eredmeny = []
        for k in ki:
            darabok = k.hypotheses[0]
            if self.sp is not None:
                eredmeny.append(self.sp.decode(darabok))
            else:
                szoveg = " ".join(darabok).replace("@@ ", "").replace("@@", "")
                eredmeny.append(self.md.detokenize(szoveg.split()))
        return eredmeny


def _motor(honnan: str, hova: str) -> _Motor:
    with _zar:
        kulcs = (honnan, hova)
        if kulcs not in _betoltott:
            mappa = modell_mappa() / ("%s_%s" % (honnan, hova))
            if not (mappa / "metadata.json").is_file():
                raise RuntimeError("Ez a nyelvpár nincs letöltve: %s→%s"
                                   % (honnan, hova))
            _betoltott[kulcs] = _Motor(mappa, honnan, hova)
        return _betoltott[kulcs]


def mondatokra(szoveg: str) -> list:
    """MONDATONKÉNT fordítunk. Ez nem szépészeti kérdés: egyben beadva a modell
    az első mondat után egyszerűen ELHAGYJA a szöveg többi részét (élesben
    pontosan ez történt a próbán)."""
    darabok = []
    for sor in re.split(r"\n{2,}", szoveg or ""):
        for m in re.split(r"(?<=[.!?…])\s+", sor):
            m = m.strip()
            if m:
                darabok.append(m)
    return darabok


def fordit(szoveg: str, honnan: str, hova: str = "hu", halad=None) -> str:
    """OFFLINE fordítás. A hiányzó modelleket NEM tölti le magától – azt a
    hívó kérdezze meg a felhasználótól (mert nagy fájlok)."""
    mondatok = mondatokra(szoveg)
    if not mondatok:
        return ""
    lepesek = [(honnan, hova)] if (modell_mappa() / ("%s_%s" % (honnan, hova))
                                   / "metadata.json").is_file() \
        else [(honnan, "en"), ("en", hova)]
    aktualis = mondatok
    for i, (a, b) in enumerate(lepesek):
        aktualis = _motor(a, b).fordit(aktualis)
        if halad:
            halad((i + 1) / len(lepesek))
    return "\n".join(aktualis).strip()
