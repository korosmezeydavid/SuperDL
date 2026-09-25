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
    `_ext` bővítményt így is a csomag saját `__init__`-je végzi el.

    ⚠️ **ÉS AMIT A 4.6.12-BEN JAVÍTOTTUNK** (Farkas István, 2026-09-19):

        module 'ctranslate2' has no attribute 'Translator'

    A fenti pótmodulos trükk „sikeres" importot tudott adni olyan modulra
    is, amiben a `Translator` NINCS BENNE (csonka telepítés, félbemaradt
    `__init__`, vagy épp a mi üres pótmodulunk maradt a helyén). A régi
    `elerheto()` pedig CSAK azt nézte, hogy az import nem dob-e kivételt –
    tehát igent mondott, a felület felajánlotta a helyben futó fordítót, és
    a hiba csak a HASZNÁLAT pillanatában csapott le. Ez a legrosszabb fajta
    hiba: a program megígér valamit, amit nem tud.

    Mostantól a `ct2()` azt is ELLENŐRZI, hogy a `Translator` tényleg ott
    van-e, és ha nincs, érthető `ImportError`-t dob. A pótmodult pedig
    kudarc esetén ELTAKARÍTJUK, hogy ne mérgezzen meg egy későbbi, már jó
    importot."""
    import sys
    import types
    # ⚠️ RÉGI PROCESSZOR (Tóth Zoltán, 2026-09-24): a ctranslate2 behúzza a
    # numpyt, és ha az egyszer már elbukott, egy újabb próba natívan megöli
    # az egész programot (0xc000001d) – nála a Súgó → Hibajelentés tette
    # ezt. Ezért ELŐBB a numpy-őr: ha a numpy nem megy, a ctranslate2-höz
    # hozzá sem nyúlunk.
    from . import numpyor
    try:
        numpyor.betolt()
    except ImportError as e:
        raise ImportError("A helyben futó fordító nem indítható: %s" % e) \
            from None
    # ⚠️ A SORREND FONTOS: ELŐBB a teljes behozási tánc, és CSAK A VÉGÉN az
    # ellenőrzés. Az első változatomban az ellenőrzés az első ág végén volt,
    # és `ImportError`-t dobott – amit a lenti `except ImportError` elnyelt,
    # majd a pótmodulos ág KIVETTE a már meglévő modult a sys.modules-ból, és
    # a hiba végül félrevezető „No module named 'ctranslate2'" lett. Vagyis a
    # javítás elfedte volna pont azt az okot, amit láthatóvá akartunk tenni.
    try:
        import ctranslate2 as modul
    except ImportError:
        beadtuk = "ctranslate2.converters" not in sys.modules
        sys.modules.setdefault("ctranslate2.converters",
                               types.ModuleType("ctranslate2.converters"))
        sys.modules.pop("ctranslate2", None)
        try:
            import ctranslate2 as modul
        except Exception:
            if beadtuk:                # ne hagyjunk magunk után szemetet
                sys.modules.pop("ctranslate2.converters", None)
            raise
    return _ct2_ellenoriz(modul)


def _ct2_ellenoriz(modul):
    """A behozott modul TÉNYLEG használható-e fordításra?

    ⚠️ Nem elég, hogy az `import` lefutott. Farkas István hibája
    (`has no attribute 'Translator'`) pont olyan modult kapott, ami
    importálódott, de nem tudott fordítani."""
    if not hasattr(modul, "Translator"):
        raise ImportError(
            "A helyben futó fordító futtatókörnyezete (ctranslate2) "
            "hiányosan települt: nincs benne Translator. "
            "A helyben fordítás így nem indítható.")
    return modul


# a helyben fordításhoz MINDEN esetben kellő segédcsomagok (a szövegdaraboló
# modellfüggő, azt a `_Motor` maga nézi meg)
_SEGEDEK = ("sacremoses",)


def hianyzo_reszek() -> list:
    """Mi hiányzik a helyben fordításhoz? Üres lista = minden megvan.

    Azért adunk LISTÁT és nem csak igen/nemet, mert a felhasználónak a
    „miért nem" a használható információ, nem az, hogy „nem"."""
    ki = []
    try:
        ct2()
    except Exception as e:
        ki.append("futtatókörnyezet (ctranslate2): %s" % e)
    for nev in _SEGEDEK:
        try:
            __import__(nev)
        except Exception as e:
            ki.append("%s: %s" % (nev, e))
    return ki


def elerheto() -> bool:
    """Van-e a programban MŰKÖDŐ fordító-futtatókörnyezet?

    ⚠️ A 4.6.12 előtt ez csak azt nézte, hogy az import nem dob-e kivételt.
    Egy csonka telepítésnél tehát igent mondott, a felület felajánlotta a
    helyben fordítást, és a hiba a használatkor jött elő. Most a `ct2()`
    maga ellenőrzi a `Translator` meglétét, így az igen tényleg igen."""
    try:
        ct2()
        return True
    except Exception:
        return False


def miert_nem() -> str:
    """EGY mondat arról, miért nem megy a helyben fordítás – vagy üres, ha
    megy. A felületnek ezt kell kimondania a puszta „nem sikerült" helyett.

    ⚠️ Farkas István jelzése (2026-09-19) két bajt mutatott: a nyers angol
    mondat (`module 'ctranslate2' has no attribute 'Translator'`) vakon nem
    információ, és a Control E sem adott róla semmit. A nyers szöveg a
    naplóba való, ez a mondat pedig a felhasználónak."""
    hianyok = hianyzo_reszek()
    if not hianyok:
        return ""
    return ("A helyben futó fordító most nem indítható, mert a programban "
            "hiányosan van jelen a futtatókörnyezete. Ez nem a te géped "
            "hibája, és nem a szövegen múlik. Addig használd az online "
            "fordítót, mi pedig javítjuk. A pontos, technikai ok: "
            + "; ".join(hianyok))


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
    # ⚠️ ELŐBB NÉZZÜK MEG, HOGY EGYÁLTALÁN MŰKÖDIK-E (Farkas István,
    # 2026-09-19). Enélkül a hiba a `_Motor.__init__`-ből jött ki nyers
    # angolul (`module 'ctranslate2' has no attribute 'Translator'`), ami
    # vakon nem információ. Itt egy érthető magyar mondattal állunk meg,
    # és a technikai ok is benne van – továbbküldhetően.
    baj = miert_nem()
    if baj:
        raise RuntimeError(baj)
    lepesek = [(honnan, hova)] if (modell_mappa() / ("%s_%s" % (honnan, hova))
                                   / "metadata.json").is_file() \
        else [(honnan, "en"), ("en", hova)]
    aktualis = mondatok
    for i, (a, b) in enumerate(lepesek):
        aktualis = _motor(a, b).fordit(aktualis)
        if halad:
            halad((i + 1) / len(lepesek))
    return "\n".join(aktualis).strip()
