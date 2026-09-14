# -*- coding: utf-8 -*-
"""AI-funkciók a szöveghez — MINDIG előnézettel.

⚠️ AZ AI SOHA NEM ÍR A DOKUMENTUMBA MAGÁTÓL. A javaslat külön ablakban
jelenik meg, felolvasva, és a felhasználó dönt: elfogadja, pontosítja, újra
kéri, vagy eldobja. Vakon egy néma csere a legrosszabb, ami történhet: ha nem
figyeltél, már nem tudod, mi volt ott eredetileg — a visszavonás pedig több
lépés után nem egyértelmű.
"""

FELADATOK = [
    ("javit", "Fogalmazás javítása",
     "Javítsd ki a szöveg fogalmazását és nyelvhelyességét. A TARTALMON ne "
     "változtass, ne rövidítsd és ne bővítsd. Csak a javított szöveget add "
     "vissza, magyarázat nélkül."),
    ("hivatalos", "Átírás hivatalos hangnemre",
     "Írd át a szöveget hivatalos, tárgyilagos hangnemre. A tartalom maradjon. "
     "Csak az átírt szöveget add vissza."),
    ("barati", "Átírás baráti hangnemre",
     "Írd át a szöveget közvetlen, baráti hangnemre. A tartalom maradjon. "
     "Csak az átírt szöveget add vissza."),
    ("rovid", "Rövidítés",
     "Rövidítsd le a szöveget körülbelül a felére úgy, hogy a lényeg "
     "megmaradjon. Csak a rövidített szöveget add vissza."),
    ("bovit", "Bővítés, kifejtés",
     "Fejtsd ki bővebben a szöveget, tartsd meg a stílusát és az állításait. "
     "Csak a bővített szöveget add vissza."),
    ("osszefoglal", "Összefoglalás",
     "Foglald össze a szöveget néhány mondatban. Csak az összefoglalót add "
     "vissza."),
    ("folytat", "Folytasd innen",
     "Folytasd a szöveget ugyanabban a stílusban, néhány bekezdéssel. CSAK a "
     "folytatást add vissza, az eredetit ne ismételd meg."),
    ("cim", "Címjavaslatok",
     "Adj öt címjavaslatot ehhez a szöveghez, soronként egyet, sorszám "
     "nélkül."),
    ("magyaraz", "Magyarázd el",
     "Magyarázd el egyszerű, közérthető magyarsággal, mit mond ez a szöveg. "
     "A magyarázatot add vissza, ne a szöveget."),
]

# amelyik feladat a szöveget CSERÉLI, és amelyik csak MEGMUTAT valamit
CSERELO = {"javit", "hivatalos", "barati", "rovid", "bovit"}
HOZZAFUZ = {"folytat"}


def feladat(kulcs):
    for k, nev, utasitas in FELADATOK:
        if k == kulcs:
            return k, nev, utasitas
    return None


def keres(kulcs: str, szoveg: str, pontositas: str = "") -> str:
    """Az AI megkérdezése. Hibát DOB, a hívó mondja ki érthetően."""
    f = feladat(kulcs)
    if not f:
        raise ValueError("ismeretlen feladat: %s" % kulcs)
    _, _nev, utasitas = f
    if pontositas.strip():
        utasitas += "\n\nTOVÁBBI KÉRÉS a felhasználótól: " + pontositas.strip()
    from superdl import aiclient
    return aiclient.chat(
        f"{utasitas}\n\n--- A SZÖVEG ---\n{szoveg}",
        system="Magyar nyelvű szövegszerkesztő segédje vagy. Pontosan azt add "
               "vissza, amit kérnek, bevezető és záró udvariaskodás nélkül.",
        max_tokens=4000)


def hosszu_e(szoveg: str) -> bool:
    """Túl hosszú-e ahhoz, hogy egyben elküldjük?

    Nem vágjuk fel csendben: inkább MEGMONDJUK, hogy jelöljön ki kevesebbet.
    A félig feldolgozott szöveg rosszabb, mint a világos nem."""
    return len(szoveg or "") > 24000
