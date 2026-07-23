# -*- coding: utf-8 -*-
"""Közös segédek a játékokhoz – SZÁNDÉKOSAN wx NÉLKÜL, hogy a játéklogika
tisztán, felület nélkül is tesztelhető legyen.

A JÁTÉKMODELL: minden játék egy PYTHON GENERÁTOR-korutin, ami a `Ctx`
segédeivel „beszél":

    def jatek_valami(ctx):
        yield ctx.mond("Üdv a játékban!")
        valasz = yield ctx.kerdez("Hogy hívnak?")
        yield ctx.mond(f"Szia, {valasz}!")
        yield ctx.vege("Vége a játéknak.")

A felület (JatekKonzol) `.send()`-del hajtja: a `mond`/`vege` kimenetet
azonnal megjeleníti és felolvassa, a `kerdez`-nél megvárja a bevitelt, majd
a beírt szöveget visszaküldi a generátornak. Ugyanezt teszi a teszt-hajtó is
(`lejatsz`), csak felület helyett előre megírt válaszokkal – így minden játék
gépi teszttel ellenőrizhető.
"""
import random
import unicodedata


class Ctx:
    """A játék és a felület közötti egyszerű „beszélő" felület. A metódusok
    csak parancs-hármasokat adnak vissza, amiket a játék `yield`-el."""

    def mond(self, szoveg):
        return ("mond", str(szoveg))

    def kerdez(self, szoveg):
        return ("kerdez", str(szoveg))

    def vege(self, szoveg=""):
        return ("vege", str(szoveg))

    def hang(self, hangok):
        """Rövid hangok lejátszása: [(frekvencia_Hz, hossz_ms), …]. A felület
        szinuszként megszólaltatja; a teszt-hajtó egyszerűen átugorja."""
        return ("hang", list(hangok))


# ---- bemenet-értelmezés --------------------------------------------------

_IGEN = {"i", "igen", "y", "yes", "ok", "oké", "okay", "j", "jó"}
_NEM = {"n", "nem", "no", "dehogy", "nemá"}


def igen(txt, alap=None):
    """I/N jellegű válasz értelmezése. Üresnél az `alap`-ot adja."""
    t = (txt or "").strip().lower()
    if not t:
        return alap
    if t in _IGEN:
        return True
    if t in _NEM:
        return False
    if t[0] == "i":
        return True
    if t[0] == "n":
        return False
    return alap


def szam(txt, lo=None, hi=None):
    """Egész szám kinyerése tartomány-ellenőrzéssel. Hibánál None."""
    t = (txt or "").strip().replace(" ", "")
    try:
        n = int(t)
    except (TypeError, ValueError):
        return None
    if lo is not None and n < lo:
        return None
    if hi is not None and n > hi:
        return None
    return n


def ekezet_nelkul(s):
    """Ékezet- és kisbetűsítés a kvíz-válaszok laza összevetéséhez."""
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def egyezik(valasz, helyes, aliasok=()):
    """Laza szöveg-egyezés: kis/nagybetű és ékezet nem számít."""
    v = ekezet_nelkul(valasz)
    if not v:
        return False
    cel = {ekezet_nelkul(helyes)} | {ekezet_nelkul(a) for a in aliasok}
    return v in cel


# ---- szerencse-elemek ----------------------------------------------------

def kocka(oldal=6):
    return random.randint(1, oldal)


def valaszt(sorozat):
    return random.choice(list(sorozat))


def kever(sorozat):
    x = list(sorozat)
    random.shuffle(x)
    return x


# ---- teszt-hajtó (felület nélkül) ---------------------------------------

def lejatsz(jatek_fugg, valaszok, max_lepes=10000):
    """A játék-generátor lefuttatása felület nélkül, teszteléshez. A `valaszok`
    lehet fix lista (sorban felhasznált válaszok) VAGY egy „bot" függvény
    `bot(kerdes_szoveg, eddigi_kimenet) -> valasz`. Visszaad: a kimeneti
    hármasok listája [(típus, szöveg), …]."""
    ctx = Ctx()
    gen = jatek_fugg(ctx)
    ki = []
    bot = valaszok if callable(valaszok) else None
    valasz_iter = None if bot else iter(valaszok)
    send = None
    lepes = 0
    while True:
        lepes += 1
        if lepes > max_lepes:
            raise RuntimeError("A játék nem ért véget (végtelen ciklus?).")
        try:
            cmd = gen.send(send)
        except StopIteration:
            break
        send = None
        typ = cmd[0]
        payload = cmd[1] if len(cmd) > 1 else ""
        ki.append((typ, payload))
        if typ == "kerdez":
            if bot is not None:
                send = bot(payload, ki)
            else:
                try:
                    send = next(valasz_iter)
                except StopIteration:
                    send = ""      # kifogytak a válaszok: üres (a játék dönt)
        elif typ == "vege":
            break
    return ki


def szoveg(kimenet):
    """A lejatsz() kimenetéből az összefűzött szöveg (kereséshez a tesztben)."""
    return "\n".join(p for _, p in kimenet)
