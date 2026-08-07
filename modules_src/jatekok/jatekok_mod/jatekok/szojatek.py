# -*- coding: utf-8 -*-
"""Szójátékok.

Egy szó mint száz (az azonos nevű homelabos játék mechanikája nyomán): a gép
gondol egy szóra, és mond róla egy meghatározást; te kitalálod. Ha nem megy,
kérhetsz (vagy tévesztéskor kapsz) egy-egy betűt a szóból – de közben a
fortunád (a fordulóért járó pont) feleződik: nyolc, négy, kettő, egy. A másik
fordulóban a gép a szó betűit ábécérendben mondja, és abból kell kitalálnod.

A gépi kódot nem másoltuk; a játékmenetet a portolási sablon szellemében
írtuk újra, és a szótár is saját, tiszta magyar szavakból és
meghatározásokból áll.
"""
import random

from ._util import ekezet_nelkul, igen


# (szó, meghatározás) – saját, tiszta szótár közismert főnevekből
_SZOTAR = [
    ("alma", "Piros vagy zöld gyümölcs, a fáján érik, ropogósra harapod."),
    ("kutya", "Hűséges házi állat, ugat, és csóválja a farkát."),
    ("iskola", "Ide jársz tanulni, tanárok és osztálytársak várnak."),
    ("folyó", "Hosszan kanyargó víz, a tengerbe vagy tóba ömlik."),
    ("kenyér", "Lisztből sült alapélelmiszer, szeletelve eszed."),
    ("hegedű", "Négyhúros vonós hangszer, az áll alá fogod."),
    ("napraforgó", "Sárga tányérvirág, a nap felé fordul, a magját rágcsálod."),
    ("villamos", "Síneken járó városi jármű, felsővezetékről kap áramot."),
    ("gyertya", "Viaszrúd kanóccal, lángja fényt ad, ha nincs áram."),
    ("könyvtár", "Ide jársz könyvet kölcsönözni, csendben olvasol."),
    ("teknős", "Lassú, páncélos állat, a fejét be tudja húzni."),
    ("hóember", "Télen hógolyókból gördíted, répa az orra."),
    ("mozdony", "A vonat elején húzza a szerelvényt a síneken."),
    ("esernyő", "Esőben kinyitod a fejed fölé, hogy ne ázz meg."),
    ("méhecske", "Zümmögő rovar, virágport gyűjt, mézet készít."),
    ("óra", "Megmutatja, hány óra van; mutatós vagy digitális."),
    ("erdő", "Sok fa együtt, vadak és madarak otthona."),
    ("zongora", "Fekete-fehér billentyűs hangszer, a húrjait kalapácsok ütik."),
    ("csillag", "Éjjel pislákol az égen, a Nap is egy ilyen."),
    ("répa", "Narancssárga gyökérzöldség, a nyuszik kedvence."),
    ("hajó", "Vízen úszó jármű, embert vagy árut szállít."),
    ("tükör", "Belenézel, és visszanéz rád a saját képed."),
    ("labda", "Gömbölyű játékszer, rúgod, dobod, pattogtatod."),
    ("felhő", "Az égen lebeg, esőt vagy havat hozhat."),
    ("párna", "Puha fejtámasz, erre hajtod a fejed alváskor."),
    ("kulcs", "Ezzel nyitod-zárod az ajtót vagy a lakatot."),
    ("gomba", "Erdőben nő, kalapja és tönkje van; van ehető és mérgező."),
    ("szivárvány", "Eső után az égen, hét színben ível át."),
    ("postás", "Ő hordja ki a leveleket és a csomagokat."),
    ("torony", "Magas, keskeny épület vagy építmény, messzire ellátni róla."),
    ("citrom", "Sárga, savanyú gyümölcs, teába facsarod."),
    ("béka", "Ugráló kétéltű, a tó partján brekeg."),
    ("kalapács", "Szöget versz be vele, nehéz feje és nyele van."),
    ("hóvirág", "Az egyik legkorábbi tavaszi virág, fehér és lehajló."),
    ("térkép", "Rajzon mutatja a tájat, várost, országot; eligazít."),
    ("fészek", "A madár építi ágakból, ebben költi ki a tojásait."),
]


def _talalos(ctx, szo, felvezetes):
    """Egy találós forduló: 8 fortunával indul, minden segítség/tévesztés egy
    betűt fed fel és felezi a fortunát (8-4-2-1). Visszaadja a megszerzett
    fortunát (0, ha nem sikerült)."""
    yield ctx.mond(felvezetes + f" A szó {len(szo)} betűs.")
    fortuna = 8
    felfedve = {}
    while True:
        v = yield ctx.kerdez("Mi a szó? (vagy: segítség / feladom)")
        t = (v or "").strip().lower()
        if t in ("feladom", "feladás", "feladas", "passz", "pass"):
            yield ctx.mond(f"Sajnos ez a forduló nem sikerült. A szó ez "
                           f"volt: {szo}.")
            return 0
        seged = t in ("segítség", "segitseg", "?", "kérek", "kerek")
        if not seged:
            if ekezet_nelkul(t) == ekezet_nelkul(szo):
                yield ctx.mond(f"Csakugyan! A szó ez: {szo}. {fortuna} "
                               "fortunát kapsz.")
                return fortuna
            yield ctx.mond("Ez nem az a szó, tévedtél.")
        if fortuna <= 1:
            yield ctx.mond(f"Elfogyott a fortunád ebben a fordulóban. A szó "
                           f"ez volt: {szo}.")
            return 0
        rejtett = [i for i in range(len(szo)) if i not in felfedve]
        if rejtett:
            p = random.choice(rejtett)
            felfedve[p] = szo[p]
            yield ctx.mond(f"Adok egy betűt: a szó {p + 1}. betűje: {szo[p]}.")
        fortuna //= 2


def jatek_egyszo(ctx):
    yield ctx.mond(
        "Egy szó mint száz. Gondolok egy szóra, és mondok róla egy "
        "meghatározást – neked ki kell találnod. Ha egyből eltalálod, nyolc "
        "fortunát kapsz. Ha nem megy, kérhetsz segítséget (vagy tévesztéskor "
        "kapsz) egy-egy betűt a szóból, de közben a fortunád feleződik: nyolc, "
        "négy, kettő, egy. Minden második fordulóban a szó betűit ábécérendben "
        "mondom, abból kell kitalálnod. Írd be: segítség, ha betűt kérsz, vagy "
        "feladom, ha továbblépnél.")
    keszlet = _SZOTAR[:]
    random.shuffle(keszlet)
    pont = 0
    fordulo = 0
    while True:
        if not keszlet:
            keszlet = _SZOTAR[:]
            random.shuffle(keszlet)
        szo, meghat = keszlet.pop()
        fordulo += 1
        if fordulo % 2 == 1:
            felvezetes = "A meghatározás: " + meghat
        else:
            betuk = " ".join(sorted(szo.lower()))
            felvezetes = ("Most a betűk ábécérendben következnek: " + betuk
                          + ".")
        szerzett = yield from _talalos(ctx, szo, felvezetes)
        pont += szerzett
        yield ctx.mond(f"Eddig összesen {pont} fortunád van.")
        v = yield ctx.kerdez("Jöhet a következő szó? (igen/nem)")
        if not igen(v, True):
            break
    yield ctx.mond(f"A játék végeredménye: {pont} fortuna.")
    if pont >= 40:
        yield ctx.mond("Nagyszerű szókincs – gratulálok!")
    elif pont >= 16:
        yield ctx.mond("Szép teljesítmény!")
    yield ctx.vege("Köszönöm a játékot!")
