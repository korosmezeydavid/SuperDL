# -*- coding: utf-8 -*-
"""A TELJES dokumentum fordítása, darabokban, majd összefűzve.

Két motorral, ugyanazzal a felülettel:

* AI — a beállított szolgáltatóval. Jó minőség, de a szöveg ELHAGYJA A GÉPET.
* Helyi gépi fordító — a szöveg EL SEM HAGYJA A GÉPET, viszont nyelvenként
  egyszer le kell tölteni a modellt.

⚠️ MIÉRT DARABOKBAN. Egy egész könyvet egy kérésben elküldeni nem lehet: a
szolgáltató levágja a választ, és a vége CSENDBEN elveszik. Ezért bekezdés-
határon darabolunk, minden darabot külön fordítunk, és a végén fűzzük össze.
A bekezdéshatár azért fontos, mert egy mondat közepén elvágott szöveget a
fordító félreért — nem hibázik, hanem MÁST mond, és azt utólag nem látni.

⚠️ A FEJEZETJELÖLŐT NEM FORDÍTJUK. Az technikai jel a hangoskönyv-készítőnek;
ha lefordulna, a darabolás némán elromlana.
"""

DARAB_MERET = 3500          # karakter; a felhasználó kérése ~3–4000

NYELVEK = [
    ("hu", "magyar"),
    ("en", "angol"),
    ("de", "német"),
    ("fr", "francia"),
    ("es", "spanyol"),
    ("it", "olasz"),
    ("pl", "lengyel"),
    ("ru", "orosz"),
    ("sk", "szlovák"),
    ("ro", "román"),
    ("hr", "horvát"),
    ("sr", "szerb"),
    ("cs", "cseh"),
    ("uk", "ukrán"),
    ("nl", "holland"),
    ("pt", "portugál"),
    ("tr", "török"),
]

NYELV_NEV = dict(NYELVEK)


def nyelv_neve(kod: str) -> str:
    return NYELV_NEV.get(kod, kod)


def _jelolo_sor(sor: str) -> bool:
    try:
        from superdl import fejezet
        return fejezet.jelolo_e(sor)
    except Exception:
        return False


def darabol(szoveg: str, meret: int = DARAB_MERET) -> list:
    """Bekezdéshatáron darabol. A fejezetjelölő SAJÁT darab lesz.

    Így a jelölő sosem kerül a fordító elé egy mondat közepén, és a
    visszafűzésnél pontosan ott marad, ahol volt.
    """
    darabok, mostani = [], []

    def zar():
        if mostani:
            darabok.append("\n".join(mostani))
            mostani.clear()

    hossz = 0
    for sor in (szoveg or "").split("\n"):
        if _jelolo_sor(sor):
            zar()
            hossz = 0
            darabok.append(sor)                  # önálló, NEM fordítandó darab
            continue
        if hossz + len(sor) + 1 > meret and mostani:
            zar()
            hossz = 0
        mostani.append(sor)
        hossz += len(sor) + 1
    zar()
    return darabok


def forditando(darab: str) -> bool:
    """Ezt a darabot tényleg el kell küldeni? (jelölő és üres darab: nem)"""
    if not darab.strip():
        return False
    sorok = [s for s in darab.split("\n") if s.strip()]
    return not (len(sorok) == 1 and _jelolo_sor(sorok[0]))


UTASITAS = (
    "Fordítsd le a következő szöveget {honnan} nyelvről {hova} nyelvre.\n"
    "SZABÁLYOK:\n"
    "- CSAK a fordítást add vissza, semmilyen bevezetőt, magyarázatot vagy "
    "megjegyzést ne írj.\n"
    "- A bekezdésbeosztást tartsd meg pontosan: ahány sor jött, annyi menjen "
    "vissza.\n"
    "- Ha egy sor csak technikai jelölés (például szögletes zárójelek között), "
    "azt változatlanul hagyd.\n"
    "- A tulajdonneveket ne fordítsd le.\n"
    "- A szöveg egy hosszabb mű RÉSZLETE; ne írj hozzá lezárást."
)


def ai_darab(darab: str, honnan: str, hova: str) -> str:
    """Egy darab fordítása az AI-val. Hibát DOB, ha nem megy."""
    from superdl import aiclient
    rendszer = UTASITAS.format(honnan=nyelv_neve(honnan),
                               hova=nyelv_neve(hova))
    return (aiclient.chat(darab, system=rendszer) or "").strip("\n")


def helyi_darab(darab: str, honnan: str, hova: str) -> str:
    """Egy darab fordítása a helyi géppel. Hibát DOB, ha nem megy."""
    from superdl import offlineford
    return offlineford.fordit(darab, honnan, hova, None)


def helyi_motor_van() -> bool:
    """Van-e egyáltalán helyi fordító-futtatókörnyezet a programban?"""
    try:
        from superdl import offlineford
        return bool(offlineford.elerheto())
    except Exception:
        return False


def helyi_elerheto(honnan: str, hova: str) -> bool:
    """Le van-e töltve a helyi modell ehhez a nyelvpárhoz?"""
    try:
        from superdl import offlineford
        if not offlineford.elerheto():
            return False
        parok = set(offlineford.telepitett_parok())
        if (honnan, hova) in parok:
            return True
        # angolon át is mehet (pivot), ha mindkét fél megvan
        return (honnan, "en") in parok and ("en", hova) in parok
    except Exception:
        return False


def helyi_letoltes_kell(honnan: str, hova: str) -> int:
    """Hány nyelvi csomagot kellene letölteni ehhez a párhoz? 0 = semmit.

    -1, ha meg sem tudtuk kérdezni (nincs net, vagy nincs ilyen nyelvpár).
    """
    try:
        from superdl import offlineford
        return len(offlineford.hianyzo(honnan, hova))
    except Exception:
        return -1


def helyi_letolt(honnan: str, hova: str, halad=None) -> bool:
    """A hiányzó nyelvi csomagok letöltése. Igaz, ha utána megy a fordítás.

    ⚠️ EZ LASSÚ: csomagonként 60–100 megabájt. A hívónak KI KELL MONDANIA,
    hogy most letöltés lesz, és hogy ezért tovább tart. Egy néma, percekig
    tartó várakozás vakon megkülönböztethetetlen a lefagyástól.
    """
    from superdl import offlineford
    hianyzik = offlineford.hianyzo(honnan, hova)
    if not hianyzik:
        return helyi_elerheto(honnan, hova)
    for i, csomag in enumerate(hianyzik, 1):
        if halad is not None:
            halad(i, len(hianyzik))
        offlineford.letolt(csomag, None)
    return helyi_elerheto(honnan, hova)


def fordit(szoveg: str, honnan: str, hova: str, motor="ai",
           halad=None, megall=None) -> str:
    """A teljes szöveg fordítása, darabonként, összefűzve.

    `halad(kesz, osszes, darab_szoveg)` — a felületnek, bemondáshoz.
    `megall()` — ha igazat ad, félbehagyjuk és az EDDIGIT adjuk vissza.

    ⚠️ Ha egy darab fordítása elhasal, az EREDETI darabot tesszük vissza, nem
    hagyjuk ki. Egy hiányzó bekezdés vakon észrevehetetlen; egy le nem
    fordított bekezdés viszont feltűnik, és javítható.
    """
    egy_darab = ai_darab if motor == "ai" else helyi_darab
    darabok = darabol(szoveg)
    kell = [d for d in darabok if forditando(d)]
    osszes = len(kell)
    kesz = 0
    ki = []
    for darab in darabok:
        if megall is not None and megall():
            ki.append(darab)
            continue
        if not forditando(darab):
            ki.append(darab)
            continue
        try:
            ki.append(egy_darab(darab, honnan, hova))
        except Exception:
            ki.append(darab)                     # inkább eredetiben, mint sehogy
        kesz += 1
        if halad is not None:
            halad(kesz, osszes, darab)
    return "\n".join(ki)
