# -*- coding: utf-8 -*-
"""Kártya / kocka / szerencse retró játékok: Huszonegy, Itt a piros, Snóbli,
három- és egyszerű kocka, mezőverseny, Rulett, Rulibuli, Gyufapöci.

Minden pénz JÁTÉKPÉNZ – valódi tét, fizetés vagy szerencsejáték NINCS és nem
is lehet. Ezek a klasszikusok akadálymentes, tisztán szórakoztató másai.
"""
import random

from ._util import igen, szam, kocka, valaszt


def _eredmeny(en, gep, mien="Te", ove="A gép"):
    if en > gep:
        return f"{mien} nyert! {en} – {gep}. Gratulálok!"
    if gep > en:
        return f"{ove} nyert. {en} – {gep}. Legközelebb sikerül!"
    return f"Döntetlen: {en} – {gep}."


# ============================================================== HUSZONEGY (21)
_LAPOK = [("alsó", 2), ("felső", 3), ("király", 4), ("hetes", 7),
          ("nyolcas", 8), ("kilences", 9), ("tízes", 10), ("ász", 11)]
_KSZIN = ["tök", "makk", "piros", "zöld"]


def _pakli():
    p = [(sz, nev, ert) for sz in _KSZIN for nev, ert in _LAPOK]
    random.shuffle(p)
    return p


def _ossz(kez):
    return sum(e for _, _, e in kez)


def _lapok(kez):
    return ", ".join(f"{sz} {nev}" for sz, nev, _ in kez)


def jatek_huszonegy(ctx):
    yield ctx.mond(
        "HUSZONEGY, magyar kártyával. A cél, hogy a lapjaid összege minél "
        "közelebb legyen a 21-hez, de 14 és 21 között maradj. Az ász 11, a "
        "tízes 10, a kilences 9, nyolcas 8, hetes 7, király 4, felső 3, alsó 2.")
    pakli = _pakli()
    en = gep = 0
    while True:
        if len(pakli) < 8:
            pakli = _pakli()
            yield ctx.mond("Új pakli megkeverve.")
        kezem = [pakli.pop()]
        gepe = [pakli.pop()]
        yield ctx.mond(f"Az első lapod: {_lapok(kezem)}. Összeg: {_ossz(kezem)}.")
        while _ossz(kezem) < 21:
            v = yield ctx.kerdez(
                f"Összeged {_ossz(kezem)}. Kérsz még lapot? (igen/nem)")
            if not igen(v, False):
                break
            if not pakli:
                pakli = _pakli()
            kezem.append(pakli.pop())
            yield ctx.mond(f"Húztál: {_lapok(kezem[-1:])}. "
                           f"Összeg: {_ossz(kezem)}.")
        while _ossz(gepe) < 14 or (14 <= _ossz(gepe) <= 16
                                   and random.random() < 0.5):
            if _ossz(gepe) >= 21 or not pakli:
                break
            gepe.append(pakli.pop())
        oe, og = _ossz(kezem), _ossz(gepe)
        yield ctx.mond(f"A te lapjaid: {_lapok(kezem)} = {oe}. "
                       f"A gép lapjai: {_lapok(gepe)} = {og}.")
        ee, eg = 14 <= oe <= 21, 14 <= og <= 21
        if ee and eg:
            if oe > og:
                en += 1
                uz = "Ez a kör a tiéd!"
            elif og > oe:
                gep += 1
                uz = "Ez a kör a gépé."
            else:
                uz = "Döntetlen kör, senki nem kap pontot."
        elif ee:
            en += 1
            uz = "Nyertél, a gép érvénytelen összeget ért el."
        elif eg:
            gep += 1
            uz = "A gép nyert, a te összeged érvénytelen."
        else:
            uz = "Egyikőtök sem érvényes – senki nem kap pontot."
        yield ctx.mond(f"{uz} Állás: te {en} – gép {gep}.")
        v = yield ctx.kerdez("Új kör? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege(f"Vége. Végeredmény: te {en} – gép {gep}. Köszönöm a játékot!")


# ======================================================= ITT A PIROS (HAZARD)
def jatek_hazard(ctx):
    v = yield ctx.kerdez("Hányszor játsszunk? (például 5)")
    korok = szam(v, 1, 100) or 5
    yield ctx.mond(
        "ITT A PIROS, HOL A PIROS? Három gyufásdoboz, egyben a piros golyó. "
        "Tippelj: 1, 2 vagy 3.")
    en = gep = 0
    for k in range(1, korok + 1):
        golyo = random.randint(1, 3)
        v = yield ctx.kerdez(f"{k}. kör. Melyik dobozban a piros? (1-3)")
        tipp = szam(v, 1, 3)
        gep_tipp = random.randint(1, 3)
        reszek = [f"A golyó a {golyo}. dobozban volt."]
        if tipp == golyo:
            en += 1
            reszek.append("Eltaláltad!")
        else:
            reszek.append("Te mellé tippeltél.")
        if gep_tipp == golyo:
            gep += 1
            reszek.append("A gép is eltalálta.")
        else:
            reszek.append("A gép mellé tippelt.")
        yield ctx.mond(" ".join(reszek) + f" Állás: te {en} – gép {gep}.")
    yield ctx.mond(_eredmeny(en, gep))
    yield ctx.vege("Köszönöm a játékot!")


# ===================================================================== SNÓBLI
def jatek_snobli(ctx):
    v = yield ctx.kerdez("Hány pontig játsszunk? (például 5)")
    cel = szam(v, 1, 100) or 5
    yield ctx.mond(
        "SNÓBLI. Mindketten elrejtetek 0-tól 3-ig érmét, majd tippeltek, "
        "összesen hány érme van a kezekben, 0 és 6 között. Aki eltalálja, "
        "az nyeri a kört.")
    en = gep = 0
    while en < cel and gep < cel:
        v = yield ctx.kerdez("Hány érmét rejtesz el? (0-3)")
        enrejt = szam(v, 0, 3)
        if enrejt is None:
            yield ctx.mond("Nulla és három közötti számot kérek.")
            continue
        geprejt = random.randint(0, 3)
        ossz = enrejt + geprejt
        v = yield ctx.kerdez("Tippelj: hány érme van összesen? (0-6)")
        entipp = szam(v, 0, 6)
        if entipp is None:
            yield ctx.mond("Nulla és hat közötti számot kérek.")
            continue
        geptipp = geprejt + random.randint(0, 3)
        reszek = [f"A gép {geprejt} érmét rejtett, összesen {ossz} volt."]
        et, gt = entipp == ossz, geptipp == ossz
        if et and not gt:
            en += 1
            reszek.append("Eltaláltad – tiéd a kör!")
        elif gt and not et:
            gep += 1
            reszek.append("A gép találta el.")
        elif et and gt:
            reszek.append("Mindketten eltaláltátok – döntetlen kör.")
        else:
            reszek.append("Senki nem találta el.")
        yield ctx.mond(" ".join(reszek) + f" Állás: te {en} – gép {gep}.")
    yield ctx.mond(_eredmeny(en, gep))
    yield ctx.vege("Köszönöm a játékot!")


# ========================================================= KOCKA – HÁROM KOCKA
def _kocka3_pont(d):
    if d == [6, 6, 6]:
        return 6
    if d[0] == d[1] == d[2]:
        return 3
    if len(set(d)) == 2:
        return 2
    return 0


def jatek_kocka3(ctx):
    v = yield ctx.kerdez("Hányszor dobjunk? (például 5)")
    korok = szam(v, 1, 100) or 5
    yield ctx.mond(
        "KOCKADOBÁS, három kockával. Három hatos 6 pont, három egyforma 3 "
        "pont, két egyforma 2 pont. Nyomj Entert a dobáshoz!")
    en = gep = 0
    for k in range(1, korok + 1):
        yield ctx.kerdez(f"{k}. kör – Enter a dobásodhoz!")
        d = [kocka(), kocka(), kocka()]
        p = _kocka3_pont(d)
        en += p
        yield ctx.mond(f"Dobtál: {d[0]}, {d[1]}, {d[2]} – {p} pont. "
                       f"Összesen {en}.")
        dg = [kocka(), kocka(), kocka()]
        pg = _kocka3_pont(dg)
        gep += pg
        yield ctx.mond(f"A gép: {dg[0]}, {dg[1]}, {dg[2]} – {pg} pont. "
                       f"Neki {gep}.")
    yield ctx.mond(_eredmeny(en, gep))
    yield ctx.vege("Köszönöm a játékot!")


# ======================================================== KOCKA – EGYSZERŰ ÖSSZEG
def jatek_kocka1(ctx):
    v = yield ctx.kerdez("Hány forduló legyen? (például 5)")
    korok = szam(v, 1, 100) or 5
    yield ctx.mond(
        "KOCKAJÁTÉK. Két kockával dobtok felváltva, az értékek összeadódnak. "
        "A több pont nyer. Nyomj Entert a dobáshoz!")
    en = gep = 0
    for k in range(1, korok + 1):
        yield ctx.kerdez(f"{k}. forduló – Enter a dobásodhoz!")
        a, b = kocka(), kocka()
        en += a + b
        yield ctx.mond(f"Dobtál {a} és {b}, az összeg {a + b}. Összesen {en}.")
        c, d = kocka(), kocka()
        gep += c + d
        yield ctx.mond(f"A gép {c} és {d}, összeg {c + d}. Neki {gep}.")
    yield ctx.mond(_eredmeny(en, gep))
    yield ctx.vege("Köszönöm a játékot!")


# =========================================================== KOCKA – MEZŐVERSENY
def jatek_kockadob(ctx):
    hossz = 20
    yield ctx.mond(
        f"KOCKADOBÁS, mezőverseny. A pálya {hossz} mezős. Felváltva dobtok egy "
        "kockával és annyit léptek. Ha a másik mezőjére érsz, visszaküldöd a "
        "startra! Cél a huszadik mező. Enter a dobáshoz.")
    pos = [0, 0]           # 0 = te, 1 = gép
    te = True
    while max(pos) < hossz:
        if te:
            yield ctx.kerdez("Te jössz – Enter a dobáshoz!")
            d = kocka()
            pos[0] = min(hossz, pos[0] + d)
            uz = f"Dobtál {d}-t, a {pos[0]}. mezőn állsz."
            if pos[0] == pos[1] and pos[0] < hossz:
                pos[1] = 0
                uz += " Kiütötted a gépet, vissza a startra!"
            yield ctx.mond(uz)
        else:
            d = kocka()
            pos[1] = min(hossz, pos[1] + d)
            uz = f"A gép {d}-t dobott, a {pos[1]}. mezőn áll."
            if pos[1] == pos[0] and pos[1] < hossz:
                pos[0] = 0
                uz += " Kiütött téged, vissza a startra!"
            yield ctx.mond(uz)
        if max(pos) >= hossz:
            break
        te = not te
    if pos[0] >= hossz:
        yield ctx.mond("Célba értél – NYERTÉL!")
    else:
        yield ctx.mond("A gép ért célba előbb. Legközelebb sikerül!")
    yield ctx.vege("Köszönöm a játékot!")


# ===================================================================== RULETT
_PIROS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def _rulett_tet(v):
    """(fajta, adat, hiba) – a tét értelmezése."""
    t = (v or "").strip().lower()
    if not t:
        return None, None, "Nem értem a tétet."
    if t.startswith("kil") or t == "k":
        return "kilep", None, "Kiléptél a kaszinóból."
    if t.startswith("piros") or t == "p":
        return "szin", "piros", None
    if t.startswith("fekete") or t == "f":
        return "szin", "fekete", None
    if t.startswith("párat") or t.startswith("parat"):
        return "paritas", "paratlan", None
    if t.startswith("páros") or t.startswith("paros"):
        return "paritas", "paros", None
    if t.startswith("tucat"):
        d = szam("".join(c for c in t if c.isdigit()), 1, 3)
        if d is None:
            return None, None, "Melyik tucat? 1, 2 vagy 3."
        return "tucat", d, None
    n = szam(t, 0, 36)
    if n is not None:
        return "szam", n, None
    return None, None, "Nem értem a tétet. Próbáld: szám, piros, fekete, páros, páratlan vagy tucat."


def _rulett_nyer(fajta, adat, szam_ki, piros, paros):
    """A profit-szorzó (0 = vesztes)."""
    if fajta == "szam":
        return 35 if adat == szam_ki else 0
    if fajta == "szin":
        if szam_ki == 0:
            return 0
        return 1 if (adat == "piros") == piros else 0
    if fajta == "paritas":
        if szam_ki == 0:
            return 0
        return 1 if (adat == "paros") == paros else 0
    if fajta == "tucat":
        if szam_ki == 0:
            return 0
        tucat = (szam_ki - 1) // 12 + 1
        return 2 if tucat == adat else 0
    return 0


def jatek_rulett(ctx):
    penz = 1000
    yield ctx.mond(
        "RULETT. A kezdő tőkéd 1000 forint – ez játékpénz. Tehetsz konkrét "
        "számra 0-tól 36-ig, színre (piros vagy fekete), párosra, páratlanra, "
        "vagy tucatra (1, 2 vagy 3). A szám 35-szörös, a tucat kétszeres, a "
        "többi egyszeres nyereményt fizet.")
    while penz > 0:
        v = yield ctx.kerdez(
            f"Pénzed {penz}. Mire teszel? (szám / piros / fekete / páros / "
            "páratlan / tucat 1-3 – vagy 'kilép')")
        fajta, adat, hiba = _rulett_tet(v)
        if fajta == "kilep":
            break
        if hiba:
            yield ctx.mond(hiba)
            continue
        v = yield ctx.kerdez(f"Mekkora a tét? (1-{penz} forint)")
        tet = szam(v, 1, penz)
        if tet is None:
            yield ctx.mond("Érvényes tétet kérek.")
            continue
        szam_ki = random.randint(0, 36)
        piros = szam_ki in _PIROS
        paros = szam_ki > 0 and szam_ki % 2 == 0
        szin = "piros" if piros else ("fekete" if szam_ki > 0 else "zöld")
        parleiras = "" if szam_ki == 0 else (", páros" if paros else ", páratlan")
        yield ctx.mond(f"A golyó a {szam_ki}-es {szin}{parleiras} számon "
                       "állt meg.")
        nyer = _rulett_nyer(fajta, adat, szam_ki, piros, paros)
        if nyer > 0:
            penz += tet * nyer
            yield ctx.mond(f"Nyertél! {tet * nyer} forint nyereség. "
                           f"Pénzed: {penz}.")
        else:
            penz -= tet
            yield ctx.mond(f"Ezt elvitte a bank. Pénzed: {penz}.")
    if penz <= 0:
        yield ctx.mond("Elfogyott a játékpénzed. Viszlát a kaszinóban!")
    yield ctx.vege("Köszönöm a játékot!")


# =================================================================== RULIBULI
def jatek_rulibuli(ctx):
    penz = 100
    yield ctx.mond(
        "RULIBULI. Dollárbébi ad neked 100 dollár játékpénzt. Tippeld meg, a "
        "kigurult szám páros vagy páratlan lesz-e. A páratlan találat "
        "kétszeres, a páros találat háromszoros. A cél 10000 dollár!")
    while 0 < penz < 10000:
        v = yield ctx.kerdez(
            f"Pénzed {penz}. Tipp: 1 = páratlan, 2 = páros (vagy 'kilép')")
        t = (v or "").strip().lower()
        if t.startswith("k"):
            break
        tipp = szam(t, 1, 2)
        if tipp is None:
            yield ctx.mond("1 (páratlan) vagy 2 (páros) legyen.")
            continue
        v = yield ctx.kerdez(f"Mekkora a tét? (1-{penz})")
        tet = szam(v, 1, penz)
        if tet is None:
            yield ctx.mond("Érvényes tétet kérek.")
            continue
        sz = random.randint(0, 36)
        paros = sz % 2 == 0
        reszek = [f"A szám {sz}, ami {'páros' if paros else 'páratlan'}."]
        if paros == (tipp == 2):
            profit = tet * 2 if paros else tet
            penz += profit
            reszek.append(f"Eltaláltad! Plusz {profit} dollár.")
        else:
            penz -= tet
            reszek.append(f"Nem talált, mínusz {tet} dollár.")
        yield ctx.mond(" ".join(reszek) + f" Pénzed: {penz}.")
    if penz >= 10000:
        yield ctx.mond("Elérted a 10000 dollárt – megnyerted a Rulibulit!")
    elif penz <= 0:
        yield ctx.mond("Elfogyott a pénzed. Viszlát!")
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================= GYUFAPÖCI
def _gyufa_pocc():
    # lapjára 0, másik oldalára 2, élére 5, a legkisebb lapjára 10
    return valaszt([0, 0, 0, 2, 2, 2, 5, 5, 10])


def jatek_gyufa(ctx):
    v = yield ctx.kerdez("Hány pontig játsszunk? (például 20)")
    cel = szam(v, 5, 200) or 20
    yield ctx.mond(
        f"GYUFAPÖCI. Pöckölöd a dobozt: lapjára 0, másik oldalára 2, élére 5, "
        f"a legkisebb lapjára 10 pont. A körben gyűjtött pontot megtarthatod, "
        f"de ha újra pöckölsz és lapjára esik, elszáll az egész köröd! "
        f"Célpontszám: {cel}. Ellenfeled a Brailab PC.")
    en = gep = 0
    while en < cel and gep < cel:
        yield ctx.mond("Te jössz.")
        bank = 0
        # az ELSŐ pöckölést is a JÁTÉKOS kezdeményezi (eddig a gép pöckölt
        # helyette – Homelab-listás visszajelzés); a további pöckölést a „P" indítja
        yield ctx.kerdez("Pöckölj egyet! (nyomj Entert)")
        while True:
            p = _gyufa_pocc()
            if p == 0:
                yield ctx.mond("Lapjára esett – 0 pont, elszállt a köröd!")
                bank = 0
                break
            bank += p
            v = yield ctx.kerdez(
                f"{p} pont, a körben eddig {bank}. Megtartod (M) vagy "
                "pöckölsz még (P)?")
            if (v or "").strip().lower().startswith("m"):
                break
        en += bank
        yield ctx.mond(f"Összpontod: {en}.")
        if en >= cel:
            break
        gbank = 0
        while True:
            p = _gyufa_pocc()
            if p == 0:
                gbank = 0
                break
            gbank += p
            if gbank >= 5 or gep + gbank >= cel:
                break
        gep += gbank
        yield ctx.mond(f"A Brailab PC köre után neki {gep} pontja van.")
    yield ctx.mond(_eredmeny(en, gep, "Te", "A Brailab PC"))
    yield ctx.vege("Köszönöm a játékot!")
