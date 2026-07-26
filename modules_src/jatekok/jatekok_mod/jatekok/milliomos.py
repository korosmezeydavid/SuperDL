# -*- coding: utf-8 -*-
"""MILLIOMOS KVÍZ – a népszerű „Legyen Ön is Milliomos" kvízműsor által
INSPIRÁLT, akadálymentes kvízjáték (nem retró, SuperDL saját játék).

Jogtiszta: kizárólag a tényszerű kérdés-adatbázist használja (a felhasználó
engedélyével kapott kérdéscsomagból), NEM a műsor zenéjét/hangjait, és nem
tartalmaz semmilyen műsor-hangfelvételt. A saját, eredeti hangvilág később
kerül bele – egyelőre a képernyőolvasó/beszéd viszi az egészet.

Játékmenet: 15-lépcsős pénzlétra 5 000 Ft-tól 40 000 000 Ft-ig, garantált
ponttal az 5. és a 10. kérdésnél; három egyszer használható segítség (felezés,
telefonos segítség, közönségszavazás); a 6. kérdéstől „Végleges?" megerősítés;
bármikori kiszállás a megszerzett pénzzel."""
import json
import os
import random

from ._util import igen

_LETRA = [5_000, 10_000, 25_000, 50_000, 100_000, 200_000, 300_000, 500_000,
          800_000, 1_500_000, 3_000_000, 5_000_000, 10_000_000, 20_000_000,
          40_000_000]
_GARANTALT = {4, 9}                 # 0-alapú szintek: 100 000 és 1 500 000 biztos
_BETUK = ("A", "B", "C", "D")

_kerdesek_cache = None


def _kerdesek():
    global _kerdesek_cache
    if _kerdesek_cache is None:
        p = os.path.join(os.path.dirname(__file__), "milliomos_kerdesek.json")
        with open(p, encoding="utf-8") as f:
            _kerdesek_cache = json.load(f)
    return _kerdesek_cache


def _ft(osszeg):
    return f"{osszeg:,}".replace(",", " ") + " forint"


def _valassz_kerdes(nehezseg, hasznalt):
    """Egy még nem használt kérdés a kért nehézségről; ha ott nincs, a
    legközelebbi elérhető nehézségről (a magas szinteken kevés a kérdés)."""
    keszlet = _kerdesek()
    for tav in range(0, 15):
        for n in {nehezseg - tav, nehezseg + tav}:
            jeloltek = [i for i, k in enumerate(keszlet)
                        if k["nehezseg"] == n and i not in hasznalt]
            if jeloltek:
                idx = random.choice(jeloltek)
                hasznalt.add(idx)
                return keszlet[idx]
    return None


def _telefon(ctx, k, aktiv):
    """Telefonos segítség: a barát tippel, könnyű kérdésnél megbízhatóbban."""
    p = max(0.4, min(0.95, 1.0 - 0.045 * (k["nehezseg"] - 1)))
    if random.random() < p and k["helyes"] in aktiv:
        biztos = random.choice(["egészen biztos vagyok benne",
                                "majdnem teljesen biztos vagyok benne",
                                "úgy emlékszem"])
        yield ctx.mond(f"Felhívtad a barátodat. Azt mondja: {biztos}, hogy a "
                       f"{k['helyes']} válasz a helyes.")
    else:
        tipp = random.choice(aktiv)
        yield ctx.mond(f"Felhívtad a barátodat. Azt mondja: nem biztos benne, de "
                       f"tippre a {tipp} lehet – de a döntés a tiéd.")


def _kozonseg(ctx, k, aktiv):
    """Közönségszavazás: a helyes válasz magasabb alapsúlyt kap (könnyűnél
    magasabbat), a többi véletlenül oszlik; a végén 100%-ra korrigálva."""
    helyes_suly = max(28, 82 - 3 * (k["nehezseg"] - 1))
    sulyok = {b: (helyes_suly if b == k["helyes"] else random.randint(4, 28))
              for b in aktiv}
    ossz = sum(sulyok.values()) or 1
    szaz = {b: round(100 * sulyok[b] / ossz) for b in aktiv}
    szaz[aktiv[0]] += 100 - sum(szaz.values())     # kerekítés-korrekció
    yield ctx.mond("A közönség szavazott! Az eredmény:")
    for b in aktiv:
        yield ctx.mond(f"{b}: {szaz[b]} százalék.")


def jatek_milliomos(ctx):
    yield ctx.mond(
        "Milliomos kvíz! Ez a népszerű Legyen Ön is Milliomos kvízműsor által "
        "inspirált játék. Tizenöt kérdés vezet a fődíjig, negyvenmillió "
        "forintig. Az ötödik és a tizedik kérdés garantált pont: ha addig "
        "eljutsz, azt a pénzt biztosan hazaviszed. Három segítséged van – "
        "felezés, telefonos segítség és közönségszavazás –, mindegyik egyszer "
        "használható. Bármikor megállhatsz a megszerzett pénzzel. Sok sikert!")
    yield ctx.effekt("mil_start")
    hasznalt = set()
    garantalt = 0
    seged = {"F": True, "T": True, "K": True}
    szint = 0
    while szint < 15:
        k = _valassz_kerdes(szint + 1, hasznalt)
        if k is None:
            yield ctx.vege("Elfogytak a kérdések – gratulálok az eddigi "
                           f"teljesítményhez! Hazaviszel {_ft(garantalt)}.")
            return
        tet = _LETRA[szint]
        opciok = {"A": k["a"], "B": k["b"], "C": k["c"], "D": k["d"]}
        aktiv = ["A", "B", "C", "D"]

        yield ctx.effekt("mil_kerdes")
        yield ctx.mond(f"{szint + 1}. kérdés, {_ft(tet)}. Kategória: "
                       f"{k['kategoria']}.")
        yield ctx.mond(k["kerdes"])
        for b in aktiv:
            yield ctx.mond(f"{b}: {opciok[b]}")

        while True:
            v = yield ctx.kerdez("A válaszod? (A, B, C, D — vagy F=felezés, "
                                 "T=telefon, K=közönség, I=ismétlés, "
                                 "M=megállás)")
            d = (v or "").strip().upper()[:1]

            if d == "M":
                nyeremeny = _LETRA[szint - 1] if szint > 0 else 0
                yield ctx.effekt("mil_kiszallas")
                yield ctx.vege(f"Megálltál, és hazaviszel {_ft(nyeremeny)}. "
                               "Bölcs döntés lehet – gratulálok!")
                return

            if d == "I":
                yield ctx.mond(k["kerdes"])
                for b in aktiv:
                    yield ctx.mond(f"{b}: {opciok[b]}")
                continue

            if d in ("F", "T", "K"):
                if not seged[d]:
                    yield ctx.mond("Ezt a segítséget már elhasználtad.")
                    continue
                seged[d] = False
                yield ctx.effekt({"F": "mil_felezo", "T": "mil_telefon",
                                  "K": "mil_kozonseg"}[d])
                if d == "F":
                    rosszak = [b for b in aktiv if b != k["helyes"]]
                    marad = random.choice(rosszak)
                    aktiv = [b for b in _BETUK if b in (k["helyes"], marad)]
                    yield ctx.mond("Felezés! Két rossz választ eltávolítottam. "
                                   "Marad:")
                    for b in aktiv:
                        yield ctx.mond(f"{b}: {opciok[b]}")
                elif d == "T":
                    yield from _telefon(ctx, k, aktiv)
                else:
                    yield from _kozonseg(ctx, k, aktiv)
                continue

            if d in aktiv:
                if szint + 1 >= 6:                 # a 6. kérdéstől: Végleges?
                    yield ctx.effekt("mil_vegleges")   # a zár feszültsége szól,
                    ve = yield ctx.kerdez(f"A {d} választ jelölted meg. "
                                          "Végleges? (i/n)")   # míg döntesz
                    if not igen(ve, False):
                        yield ctx.mond("Rendben, gondold át nyugodtan.")
                        continue
                if d == k["helyes"]:
                    utolso = (szint == 14)
                    if utolso:
                        yield ctx.effekt("mil_fonyeremeny")
                    elif szint in _GARANTALT:
                        yield ctx.effekt("mil_garantalt")
                    else:
                        yield ctx.effekt("mil_helyes")
                    yield ctx.mond(f"Helyes! A {d} a jó válasz. Megnyerted: "
                                   f"{_ft(tet)}.")
                    if szint in _GARANTALT:
                        garantalt = tet
                        yield ctx.mond(f"Ez garantált pont – {_ft(tet)} már "
                                       "biztosan a tiéd, bármi is történik!")
                    szint += 1
                    if szint == 15:
                        yield ctx.vege("Hihetetlen! Megválaszoltad mind a "
                                       "tizenöt kérdést, és megnyerted a "
                                       "főnyereményt, negyvenmillió forintot! Te "
                                       "vagy a milliomos! Óriási gratuláció!")
                        return
                    break
                else:
                    yield ctx.effekt("mil_rossz")
                    jo = k["helyes"]
                    yield ctx.vege(f"Sajnos a {d} nem jó. A helyes válasz a {jo}: "
                                   f"{opciok[jo]}. Hazaviszel {_ft(garantalt)}. "
                                   "Ne csüggedj, legközelebb többre jutsz!")
                    return
            else:
                yield ctx.mond("Kérlek, érvényes választ (a megmaradt betűk "
                               "egyikét) vagy segítséget adj meg.")
