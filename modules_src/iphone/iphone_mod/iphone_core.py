# -*- coding: utf-8 -*-
"""iPhone modul – a műveletek magja (felület nélkül, hogy tesztelhető legyen).

Amit tud: a telefonon lévő ZENÉK, FOTÓK/VIDEÓK és az alkalmazások megosztott
fájljainak listázása, LEMENTÉSE a gépre és TÖRLÉSE a telefonról.

A telefon a zenéit értelmetlen néven tárolja (`F07/JQVM.mp3`), a címet és az
előadót külön adatbázisban (`MediaLibrary.sqlitedb`). Ezért a mentés ezt az
adatbázist olvassa, és RENDES néven, előadó/album mappákba írja ki a fájlokat.

A TÖRLÉS a zene-adatbázisba is beleír. Ez a legkényesebb művelet az egész
modulban, ezért szigorú rend van rá (lásd `_adatbazis_iras`): előbb teljes
biztonsági mentés, a módosítás MÁSOLATON történik, minden lépés után ellenőrzés,
és ha bármi nem stimmel, a program MAGÁTÓL visszaállít. Félkész állapotban soha
nem hagyjuk a telefont.
"""
from __future__ import annotations

import os
import random
import re
import shutil
import sqlite3
import threading
import time

from . import afc as A

DB_MAPPA = "/iTunes_Control/iTunes/"
DB_NEV = "MediaLibrary.sqlitedb"
DB_FAJLOK = (DB_NEV, DB_NEV + "-wal", DB_NEV + "-shm")

KEP_KIT = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".bmp", ".tiff",
           ".dng", ".webp")
VIDEO_KIT = (".mov", ".mp4", ".m4v", ".avi", ".hevc")


# ---------------------------------------------------------------- segédek

def _tiszta_nev(s: str, tartalek: str = "névtelen") -> str:
    """Windowson használható fájlnév – a tiltott jeleket cseréli, nem dobja el
    az egész nevet (a felhasználó zenéiben van „?”, „:” és „/” is bőven)."""
    s = (s or "").strip()
    s = re.sub(r'[<>:"/\\|?*]', "-", s)
    s = re.sub(r"[\x00-\x1f]", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or tartalek)[:120]


def _egyedi(ut: str) -> str:
    """Ha a fájl már létezik, sorszámot kap – SOHA nem írunk felül semmit."""
    if not os.path.exists(ut):
        return ut
    torzs, kit = os.path.splitext(ut)
    i = 2
    while os.path.exists("%s (%d)%s" % (torzs, i, kit)):
        i += 1
    return "%s (%d)%s" % (torzs, i, kit)


# A telefon a listákat betűrendes REKESZEKRE bontja, és minden számhoz eltárolja,
# melyik rekeszbe tartozik. A rekeszek a készülék NYELVE szerinti ábécét
# követik – a felhasználó telefonján ez a magyar (0=A, 15=L, 26=Sz, 36=Zs,
# 37=számjegy). Ha a bejegyzés ezt üresen hagyja, könnyen kimarad a listából.
_MAGYAR_ABC = ("a", "b", "c", "cs", "d", "dz", "dzs", "e", "f", "g", "gy", "h",
               "i", "j", "k", "l", "ly", "m", "n", "ny", "o", "ö", "p", "q",
               "r", "s", "sz", "t", "ty", "u", "ü", "v", "w", "x", "y", "z",
               "zs")
_SZAM_REKESZ = 37          # a számjeggyel kezdődők rekesze
_EGYEB_REKESZ = 38         # ismeretlen előadó/album


def _rendezo_kezdet(szoveg: str) -> str:
    """A rendezéshez használt kezdet: az ékezetet az alapbetűjére vezetjük
    vissza (az Á az A rekeszébe tartozik), az idézőjeleket elhagyjuk."""
    import unicodedata
    s = (szoveg or "").strip().lstrip("\"'“„”'‚[(_ ").lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    return s


def _rekesz(szoveg: str) -> int:
    """Egy cím betűrendes rekesze a magyar ábécé szerint."""
    s = _rendezo_kezdet(szoveg)
    if not s:
        return _EGYEB_REKESZ
    if s[0].isdigit():
        return _SZAM_REKESZ
    for ketjegyu in ("dzs", "dz", "cs", "gy", "ly", "ny", "sz", "ty", "zs"):
        if s.startswith(ketjegyu):
            return _MAGYAR_ABC.index(ketjegyu)
    try:
        return _MAGYAR_ABC.index(s[0])
    except ValueError:
        return _EGYEB_REKESZ


def _rekesz_a_telefonrol(c, szoveg: str) -> int:
    """Ha a telefonon MÁR van hasonló kezdetű szám, az ő rekeszét vesszük át.

    Ez erősebb, mint bármelyik saját táblázat: pontosan azt a nyelvi rendezést
    követi, amit a készülék használ – akkor is, ha nem magyarra van állítva."""
    s = _rendezo_kezdet(szoveg)
    if not s:
        return _EGYEB_REKESZ
    try:
        r = c.execute(
            """select i.title_order_section
               from item i join item_extra e on e.item_pid = i.item_pid
               where lower(substr(e.title, 1, 1)) = ?
                 and i.title_order_section is not null limit 1""",
            (s[0],)).fetchone()
        if r and r[0] is not None:
            return r[0]
    except sqlite3.Error:
        pass
    return _rekesz(szoveg)


def _beszur(c, tabla: str, ertekek: dict):
    """Beszúrás CSAK a ténylegesen létező oszlopokba.

    A telefon zene-adatbázisának szerkezete iOS-verziónként eltérhet; ha egy
    oszlop nincs meg, attól még a szám felkerülhet – csak az a mező marad
    üresen."""
    van = {r[1] for r in c.execute("pragma table_info(%s)" % tabla)}
    hasznalt = {k: v for k, v in ertekek.items() if k in van}
    if not hasznalt:
        raise sqlite3.Error("ismeretlen tábla-szerkezet: " + tabla)
    c.execute("insert into %s (%s) values (%s)"
              % (tabla, ", ".join(hasznalt),
                 ", ".join("?" * len(hasznalt))),
              tuple(hasznalt.values()))


def _pid_hozza(c, tabla: str, mezo: str, pid_mezo: str, ertek: str):
    """Előadó/album azonosító: a meglévőt használjuk, különben újat veszünk fel.

    Enélkül minden feltöltött szám új „előadót” csinálna, és a telefon
    lejátszójában ugyanaz a név sokszor jelenne meg."""
    ertek = (ertek or "").strip()
    if not ertek:
        return 0
    try:
        r = c.execute("select %s from %s where %s = ?" % (pid_mezo, tabla, mezo),
                      (ertek,)).fetchone()
        if r:
            return r[0]
        pid = random.getrandbits(62)
        c.execute("insert into %s (%s, %s) values (?,?)"
                  % (tabla, pid_mezo, mezo), (pid, ertek))
        return pid
    except sqlite3.Error:
        return 0                     # a szám cím nélkül is felkerülhet


def mentes_mappa() -> str:
    """A biztonsági mentések helye – a felhasználó is megtalálja."""
    try:
        from superdl import store
        alap = str(store.CONFIG_DIR)
    except Exception:
        alap = os.path.join(os.path.expanduser("~"), ".superdl")
    ut = os.path.join(alap, "iphone_mentes")
    os.makedirs(ut, exist_ok=True)
    return ut


# ---------------------------------------------------------------- a telefon

class Telefon:
    """Egy csatlakoztatott iPhone. Használat:  with Telefon() as t: …"""

    def __init__(self, keszulek: dict | None = None):
        k = keszulek or (A.keszulekek() or [None])[0]
        if not k:
            raise A.NincsKeszulek(
                "Nem látok csatlakoztatott iPhone-t. Dugd be USB-kábellel, és "
                "ha a telefon rákérdez, nyomd meg a „Megbízom ebben a gépben” "
                "gombot.")
        self.ld = A.Lockdown(k)
        e = self.ld.ertekek
        self.nev = e.get("DeviceName") or "iPhone"
        self.ios = e.get("ProductVersion") or ""
        self.modell = e.get("ProductType") or ""
        self._afc = None
        self._nyitas_zar = threading.RLock()

    # ---- kapcsolat ----
    @property
    def afc(self) -> A.Afc:
        # Két szál egyszerre nyitná meg – zár nélkül két csatorna keletkezne,
        # és az egyik gazdátlanul maradna.
        with self._nyitas_zar:
            if self._afc is None:
                self._afc = A.Afc(self.ld.szolgaltatas("com.apple.afc"))
            return self._afc

    def bezar(self):
        if self._afc is not None:
            self._afc.bezar()
            self._afc = None
        self.ld.bezar()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.bezar()

    # =============================================================== ZENE
    def _db_letolt(self, cel_mappa: str) -> str:
        """Az adatbázis HÁRMASA (fő fájl + napló) – a napló nélkül a friss
        változások hiányoznának, és félkész képet kapnánk."""
        os.makedirs(cel_mappa, exist_ok=True)
        for n in DB_FAJLOK:
            try:
                self.afc.letolt(DB_MAPPA + n, os.path.join(cel_mappa, n))
            except A.IPhoneHiba:
                pass                      # a napló hiányozhat – az rendben van
        fo = os.path.join(cel_mappa, DB_NEV)
        if not os.path.exists(fo):
            raise A.IPhoneHiba("A telefon zene-adatbázisa nem érhető el.")
        return fo

    def zenek(self) -> list:
        """A telefonon lévő zenék: cím, előadó, album, hossz, méret, útvonal."""
        import tempfile
        munka = tempfile.mkdtemp(prefix="sdl_iphone_")
        try:
            fo = self._db_letolt(munka)
            c = sqlite3.connect(fo)
            try:
                helyek = {r[0]: r[1] for r in
                          c.execute("select base_location_id, path "
                                    "from base_location")}
                q = """select e.item_pid, e.title, a.item_artist, al.album,
                              e.total_time_ms, e.file_size, e.location,
                              i.base_location_id
                       from item_extra e
                       join item i on i.item_pid = e.item_pid
                       left join item_artist a
                              on a.item_artist_pid = i.item_artist_pid
                       left join album al on al.album_pid = i.album_pid
                       where e.location is not null and e.location <> ''"""
                ki = []
                for (pid, cim, eloado, album, ms, meret, hely, blid) in c.execute(q):
                    alap = helyek.get(blid, "")
                    if not alap:
                        continue
                    ki.append({
                        "pid": pid,
                        "cim": cim or "névtelen",
                        "eloado": eloado or "",
                        "album": album or "",
                        "mp": int(round((ms or 0) / 1000)),
                        "meret": int(meret or 0),
                        "ut": "/" + alap.strip("/") + "/" + hely,
                    })
                ki.sort(key=lambda x: (x["eloado"].lower(), x["album"].lower(),
                                       x["cim"].lower()))
                return ki
            finally:
                c.close()
        finally:
            shutil.rmtree(munka, ignore_errors=True)

    def zene_ment(self, tetelek: list, cel_mappa: str, mappakba: bool = True,
                  on_progress=None, on_bajt=None, megszakit=None) -> tuple:
        """A megadott zenék mentése a gépre RENDES néven.

        `mappakba=True` esetén előadó/album szerinti mappákba rendez.
        Visszaad: (sikeres darab, hibák listája)."""
        os.makedirs(cel_mappa, exist_ok=True)
        ok, hibak = 0, []
        n = len(tetelek)
        for i, t in enumerate(tetelek, 1):
            try:
                kit = os.path.splitext(t["ut"])[1].lower() or ".mp3"
                mappa = cel_mappa
                if mappakba:
                    if t["eloado"]:
                        mappa = os.path.join(mappa, _tiszta_nev(t["eloado"],
                                                                "ismeretlen előadó"))
                    if t["album"]:
                        mappa = os.path.join(mappa, _tiszta_nev(t["album"], "album"))
                    os.makedirs(mappa, exist_ok=True)
                nev = _tiszta_nev(t["cim"]) + kit
                if not mappakba and t["eloado"]:
                    nev = _tiszta_nev("%s - %s" % (t["eloado"], t["cim"])) + kit
                cel = _egyedi(os.path.join(mappa, nev))
                self.afc.letolt(t["ut"], cel, on_progress=on_bajt,
                                megszakit=megszakit)
                ok += 1
            except A.Megszakitva:
                break
            except Exception as ex:
                hibak.append("%s: %s" % (t.get("cim", "?"), ex))
            if on_progress:
                on_progress(i, n, t.get("cim", ""), ok)
        return ok, hibak

    def zene_torol(self, tetelek: list, on_progress=None) -> tuple:
        """A megadott zenék törlése a telefonról – a hangfájl ÉS a bejegyzés is.

        Ez a modul legkényesebb művelete, ezért:
          1. teljes biztonsági mentés az adatbázisról (megmarad a lemezen),
          2. a módosítás MÁSOLATON, majd épség-ellenőrzés,
          3. csak ezután írjuk vissza a telefonra,
          4. visszaolvasás; ha bármi nem stimmel, MAGÁTÓL visszaáll a mentés.
        Visszaad: (törölt darab, mentés útja)."""
        import tempfile
        if not tetelek:
            return 0, ""
        munka = tempfile.mkdtemp(prefix="sdl_iphone_")
        biztonsag = os.path.join(mentes_mappa(),
                                 time.strftime("zene_%Y%m%d_%H%M%S"))
        try:
            fo = self._db_letolt(munka)
            os.makedirs(biztonsag, exist_ok=True)
            for n in DB_FAJLOK:                       # 1. BIZTONSÁGI MENTÉS
                p = os.path.join(munka, n)
                if os.path.exists(p):
                    shutil.copy2(p, os.path.join(biztonsag, n))

            pidek = [t["pid"] for t in tetelek]
            c = sqlite3.connect(fo)                   # 2. MÓDOSÍTÁS MÁSOLATON
            try:
                elotte = c.execute("select count(*) from item_extra "
                                   "where location is not null").fetchone()[0]
                c.executemany("delete from item_extra where item_pid=?",
                              [(p,) for p in pidek])
                c.executemany("delete from item where item_pid=?",
                              [(p,) for p in pidek])
                c.commit()
                c.execute("pragma wal_checkpoint(TRUNCATE)")
                utana = c.execute("select count(*) from item_extra "
                                  "where location is not null").fetchone()[0]
                ep = c.execute("pragma integrity_check").fetchone()[0]
            finally:
                c.close()
            if ep != "ok":
                raise A.IPhoneHiba("Az adatbázis nem maradt ép – nem írok "
                                   "vissza semmit. A telefon érintetlen.")
            if utana >= elotte or (elotte - utana) != len(set(pidek)):
                raise A.IPhoneHiba(
                    "A törlés eredménye nem a várt (%d helyett %d szám maradt) "
                    "– nem írok vissza semmit. A telefon érintetlen."
                    % (elotte - len(set(pidek)), utana))

            self._adatbazis_iras(fo, biztonsag, utana)   # 3–4. ÍRÁS + ŐRSZEM

            torolt = 0                                 # 5. és a hangfájlok
            n = len(tetelek)
            for i, t in enumerate(tetelek, 1):
                try:
                    self.afc.torol(t["ut"])
                    torolt += 1
                except A.IPhoneHiba:
                    pass                  # a bejegyzés már nincs; ez nem végzetes
                if on_progress:
                    on_progress(i, n, t.get("cim", ""), torolt)
            return torolt, biztonsag
        finally:
            shutil.rmtree(munka, ignore_errors=True)

    # ------------------------------------------------------- FELTÖLTÉS
    def zene_feltolt(self, fajlok: list, on_progress=None, on_bajt=None,
                     megszakit=None) -> tuple:
        """Zene FELVITELE a telefon gyári Zene alkalmazásába.

        A telefon két helyen tartja a zenét: a hangfájl az `iTunes_Control/Music`
        egyik almappájában (értelmetlen, négybetűs néven), a CÍM és az ELŐADÓ
        pedig a zene-adatbázisban. Ezért mindkettőt el kell helyezni, különben
        vagy nem látszik a szám, vagy névtelen sor lesz belőle.

        A rend ugyanaz, mint a törlésnél: biztonsági mentés → módosítás
        másolaton → épség- és darabszám-ellenőrzés → írás → visszaolvasás →
        hiba esetén AUTOMATIKUS visszaállítás. Ha az adatbázis nem megy át, a
        feltöltött hangfájlokat is eltakarítjuk, hogy ne maradjon szemét.

        Visszaad: (sikeres darab, hibák listája, mentés útja)."""
        import tempfile
        from . import cimkek

        fajlok = [f for f in (fajlok or []) if os.path.isfile(f)]
        if not fajlok:
            return 0, [], ""
        munka = tempfile.mkdtemp(prefix="sdl_iphone_")
        biztonsag = os.path.join(mentes_mappa(),
                                 time.strftime("feltoltes_%Y%m%d_%H%M%S"))
        feltoltott = []
        hibak = []
        try:
            fo = self._db_letolt(munka)
            os.makedirs(biztonsag, exist_ok=True)
            for n in DB_FAJLOK:
                p = os.path.join(munka, n)
                if os.path.exists(p):
                    shutil.copy2(p, os.path.join(biztonsag, n))

            c = sqlite3.connect(fo)
            try:
                elotte = c.execute("select count(*) from item_extra "
                                   "where location is not null").fetchone()[0]
                helyek = {r[1]: r[0] for r in
                          c.execute("select base_location_id, path "
                                    "from base_location "
                                    "where path like 'iTunes_Control/Music/%'")}
                if not helyek:
                    raise A.IPhoneHiba(
                        "Ezen a telefonon nincs zene-mappa, amibe írhatnék. "
                        "Tegyél rá legalább egy számot a szokásos módon, "
                        "utána már működni fog.")
                n = len(fajlok)
                for i, ut in enumerate(fajlok, 1):
                    if megszakit is not None and megszakit():
                        break
                    try:
                        adat = cimkek.beolvas(ut)
                        cel_mappa, cel_nev = self._szabad_hely(helyek)
                        with open(ut, "rb") as f:
                            self.afc.ir(cel_mappa + "/" + cel_nev, f.read())
                        feltoltott.append(cel_mappa + "/" + cel_nev)
                        self._db_uj_szam(c, helyek[cel_mappa.strip("/")],
                                         cel_nev, adat, os.path.getsize(ut))
                    except Exception as ex:
                        hibak.append("%s: %s" % (os.path.basename(ut), ex))
                    if on_progress:
                        on_progress(i, n, os.path.basename(ut),
                                    len(feltoltott))
                c.commit()
                c.execute("pragma wal_checkpoint(TRUNCATE)")
                utana = c.execute("select count(*) from item_extra "
                                  "where location is not null").fetchone()[0]
                ep = c.execute("pragma integrity_check").fetchone()[0]
            finally:
                c.close()

            if ep != "ok" or utana != elotte + len(feltoltott):
                self._feltoltott_takarit(feltoltott)
                raise A.IPhoneHiba(
                    "A zene-adatbázis nem a várt módon alakult, ezért NEM írok "
                    "vissza semmit, és a feltöltött fájlokat is eltakarítottam. "
                    "A telefonod érintetlen.")
            if not feltoltott:
                return 0, hibak, biztonsag

            try:
                self._adatbazis_iras(fo, biztonsag, utana)
            except Exception:
                self._feltoltott_takarit(feltoltott)
                raise
            return len(feltoltott), hibak, biztonsag
        finally:
            shutil.rmtree(munka, ignore_errors=True)

    def _feltoltott_takarit(self, utak: list):
        """Ha az adatbázis nem ment át, a hangfájlok se maradjanak ott
        gazdátlanul – azok már senkinek nem kellenek."""
        for u in utak:
            try:
                self.afc.torol(u)
            except A.IPhoneHiba:
                pass

    def _szabad_hely(self, helyek: dict) -> tuple:
        """Szabad, négybetűs fájlnév a telefon egyik zene-mappájában.

        A telefon maga is így nevezi a fájljait; ha eltérnénk ettől, az feltűnő
        és kockázatos lenne."""
        for _ in range(200):
            mappa = "/" + random.choice(sorted(helyek))
            nev = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                          for _ in range(4)) + ".mp3"
            if not self.afc.letezik(mappa + "/" + nev):
                return mappa, nev
        raise A.IPhoneHiba("Nem találtam szabad helyet a telefon zene-mappáiban.")

    @staticmethod
    def _db_uj_szam(c, base_location_id: int, fajlnev: str, adat: dict,
                    meret: int):
        """Egy új szám bejegyzése – a telefon saját szerkezete szerint."""
        import random
        pid = random.getrandbits(62)
        # az előadó és az album KÜLÖN táblában él; ha már van ilyen, azt
        # használjuk, hogy ne szaporítsuk a duplikátumokat a lejátszóban
        eloado_pid = _pid_hozza(c, "item_artist", "item_artist",
                                "item_artist_pid", adat["eloado"])
        album_pid = _pid_hozza(c, "album", "album", "album_pid", adat["album"])
        # az Apple időszámítása 2001-01-01-től ketyeg
        most = int(time.time() - 978307200)
        # Csak azokat az oszlopokat töltjük ki, amelyek a TELEFONON tényleg
        # léteznek: az adatbázis szerkezete iOS-verziónként változhat, és egy
        # fix oszlop-lista egy újabb (vagy régebbi) rendszeren felborulna.
        # A RENDEZÉSI KULCS: a telefon rangsor-értéket tárol, 2^32-es lépésekben.
        # A meglévők közé nem tudunk beszúrni (nincs hely két érték között),
        # ezért a sor VÉGÉRE kerül. A lejátszóban ettől még ott lesz, csak a
        # betűrendben hátrébb – ez sokkal jobb, mint üresen hagyni, mert az
        # üres kulcsú sor könnyen kimarad a listából.
        try:
            legnagyobb = c.execute(
                "select max(title_order) from item").fetchone()[0] or 0
        except sqlite3.Error:
            legnagyobb = 0
        rendkulcs = int(legnagyobb) + (1 << 32)
        rekesz = _rekesz_a_telefonrol(c, adat["cim"])

        _beszur(c, "item", {
            "item_pid": pid, "media_type": 8, "item_artist_pid": eloado_pid,
            "album_pid": album_pid, "base_location_id": base_location_id,
            "keep_local": 1, "keep_local_status": 2, "in_my_library": 1,
            "date_added": most, "disc_number": 1,
            "title_order": rendkulcs, "title_order_section": rekesz,
            "item_artist_order_section":
                _rekesz(adat["eloado"]) if adat["eloado"] else _EGYEB_REKESZ,
            "album_order_section":
                _rekesz(adat["album"]) if adat["album"] else _EGYEB_REKESZ,
            "album_artist_order_section": _EGYEB_REKESZ,
            "composer_order_section": _EGYEB_REKESZ,
            "genre_order_section": _EGYEB_REKESZ,
            "series_name_order_section": _EGYEB_REKESZ})
        _beszur(c, "item_extra", {
            "item_pid": pid, "title": adat["cim"],
            "total_time_ms": float(adat["ms"]), "location": fajlnev,
            "file_size": meret, "date_modified": most,
            "media_kind": 1, "location_kind_id": 42})

        # A KÍSÉRŐ SOR: minden valódi számhoz tartozik egy `item_store`
        # bejegyzés is. Enélkül a szám „félkész” marad a telefon szemében.
        try:
            _beszur(c, "item_store", {
                "item_pid": pid, "sync_id": random.getrandbits(62),
                "sync_in_my_library": 1, "cloud_status": 0})
        except sqlite3.Error:
            pass                     # nincs ilyen tábla – akkor sincs baj

        # A LEJÁTSZHATÓSÁG JELZŐJE: a valódi számoknál 1, és nem trigger
        # tölti ki, hanem a telefon zene-szolgáltatása. Mi is beállítjuk,
        # hátha ez hiányzott ahhoz, hogy a szám megjelenjen a listában.
        try:
            c.execute("update item_state set is_valid_content_type = 1 "
                      "where item_pid = ?", (pid,))
        except sqlite3.Error:
            pass
        return pid

    def _adatbazis_iras(self, helyi_db: str, biztonsag: str, vart_darab: int):
        """Az adatbázis visszaírása – ŐRSZEMMEL.

        A telefon rendszerszolgáltatása folyamatosan ír a naplóba (WAL), ezért
        azt kiürítjük, hogy a régi állapot ne írja felül a frisset. Írás után
        VISSZAOLVASSUK: ha nem ép, vagy nem annyi szám van benne, amennyit
        vártunk, azonnal visszaállítjuk a biztonsági mentést."""
        import tempfile
        for u in ("-wal", "-shm"):
            try:
                self.afc.ir(DB_MAPPA + DB_NEV + u, b"")
            except A.IPhoneHiba:
                pass
        with open(helyi_db, "rb") as f:
            self.afc.ir(DB_MAPPA + DB_NEV, f.read())

        ell = tempfile.mkdtemp(prefix="sdl_iphone_ell_")
        try:
            # Az ellenőrzés MINDEN hibája visszaállítást jelent – akkor is, ha
            # a visszaolvasott fájl nem is adatbázis (ilyenkor az SQLite nyers
            # hibát dob, ami a puszta érték-vizsgálatot megkerülné, és a telefon
            # félkész állapotban maradna).
            ep, db = "", -1
            try:
                p = os.path.join(ell, DB_NEV)
                self.afc.letolt(DB_MAPPA + DB_NEV, p)
                c = sqlite3.connect(p)
                try:
                    ep = c.execute("pragma integrity_check").fetchone()[0]
                    db = c.execute("select count(*) from item_extra "
                                   "where location is not null").fetchone()[0]
                finally:
                    c.close()
            except Exception:
                ep = "olvashatatlan"
            if ep != "ok" or db != vart_darab:
                self.visszaallit(biztonsag)
                raise A.IPhoneHiba(
                    "A telefon nem fogadta el rendben a változtatást, ezért "
                    "VISSZAÁLLÍTOTTAM az eredeti állapotot. A zenéid megvannak.")
        finally:
            shutil.rmtree(ell, ignore_errors=True)

    def visszaallit(self, mentes_ut: str):
        """Egy korábbi biztonsági mentés visszaírása a telefonra."""
        fo = os.path.join(mentes_ut, DB_NEV)
        if not os.path.exists(fo):
            raise A.IPhoneHiba("Ebben a mappában nincs menthető adatbázis: "
                               + mentes_ut)
        for n in DB_FAJLOK:                # a naplót is, hogy egyben álljon
            p = os.path.join(mentes_ut, n)
            if os.path.exists(p):
                with open(p, "rb") as f:
                    self.afc.ir(DB_MAPPA + n, f.read())

    # ======================================================= FOTÓ / VIDEÓ
    def kepek(self, videok_is: bool = True, kepek_is: bool = True) -> list:
        """A telefon fotói és videói (a DCIM mappából)."""
        ki = []
        try:
            albumok = self.afc.listaz("/DCIM")
        except A.IPhoneHiba:
            return ki
        for alb in sorted(albumok):
            if alb.startswith("."):
                continue                  # rejtett rendszermappa
            ut = "/DCIM/" + alb
            try:
                nevek = self.afc.listaz(ut)
            except A.IPhoneHiba:
                continue
            for n in sorted(nevek):
                kit = os.path.splitext(n)[1].lower()
                video = kit in VIDEO_KIT
                if video and not videok_is:
                    continue
                if not video and kit not in KEP_KIT:
                    continue
                if not video and not kepek_is:
                    continue
                teljes = ut + "/" + n
                try:
                    meret = self.afc.meret(teljes)
                except A.IPhoneHiba:
                    meret = 0
                ki.append({"nev": n, "ut": teljes, "album": alb,
                           "meret": meret, "video": video})
        return ki

    def kep_ment(self, tetelek: list, cel_mappa: str, on_progress=None,
                 on_bajt=None, megszakit=None) -> tuple:
        os.makedirs(cel_mappa, exist_ok=True)
        ok, hibak = 0, []
        n = len(tetelek)
        for i, t in enumerate(tetelek, 1):
            try:
                cel = _egyedi(os.path.join(cel_mappa, _tiszta_nev(t["nev"])))
                self.afc.letolt(t["ut"], cel, on_progress=on_bajt,
                                megszakit=megszakit)
                ok += 1
            except A.Megszakitva:
                break
            except Exception as ex:
                hibak.append("%s: %s" % (t.get("nev", "?"), ex))
            if on_progress:
                on_progress(i, n, t.get("nev", ""), ok)
        return ok, hibak

    def kep_torol(self, tetelek: list, on_progress=None) -> tuple:
        """Fotók/videók törlése a telefonról.

        FIGYELEM: a Fotók alkalmazásnak SAJÁT nyilvántartása van; a fájl
        eltűnik, de a Fotók appban maradhat egy üres helye, amíg a telefon
        magától rendbe nem teszi. Ezért a felület ezt ki is mondja."""
        ok, hibak = 0, []
        n = len(tetelek)
        for i, t in enumerate(tetelek, 1):
            try:
                self.afc.torol(t["ut"])
                ok += 1
            except Exception as ex:
                hibak.append("%s: %s" % (t.get("nev", "?"), ex))
            if on_progress:
                on_progress(i, n, t.get("nev", ""), ok)
        return ok, hibak

    # ====================================================== ALKALMAZÁSOK
    def alkalmazasok(self) -> list:
        return A.alkalmazasok(self.ld)

    def app_fajlok(self, bundle: str) -> list:
        """Egy alkalmazás megosztott fájljai (pl. a diktafon felvételei)."""
        f = A.alkalmazas_mappaja(self.ld, bundle)
        try:
            ki = []
            for gyoker in ("Documents",):
                try:
                    nevek = f.listaz(gyoker)
                except A.IPhoneHiba:
                    continue
                for n in sorted(nevek):
                    ut = gyoker + "/" + n
                    try:
                        a = f.adatok(ut)
                    except A.IPhoneHiba:
                        continue
                    if a.get("st_ifmt") == "S_IFDIR":
                        continue
                    ki.append({"nev": n, "ut": ut,
                               "meret": int(a.get("st_size", 0))})
            return ki
        finally:
            f.bezar()

    def app_ment(self, bundle: str, tetelek: list, cel_mappa: str,
                 on_progress=None, on_bajt=None, megszakit=None) -> tuple:
        os.makedirs(cel_mappa, exist_ok=True)
        f = A.alkalmazas_mappaja(self.ld, bundle)
        ok, hibak = 0, []
        n = len(tetelek)
        try:
            for i, t in enumerate(tetelek, 1):
                try:
                    cel = _egyedi(os.path.join(cel_mappa, _tiszta_nev(t["nev"])))
                    f.letolt(t["ut"], cel, on_progress=on_bajt,
                             megszakit=megszakit)
                    ok += 1
                except A.Megszakitva:
                    break
                except Exception as ex:
                    hibak.append("%s: %s" % (t.get("nev", "?"), ex))
                if on_progress:
                    on_progress(i, n, t.get("nev", ""), ok)
        finally:
            f.bezar()
        return ok, hibak

    def app_feltolt(self, bundle: str, utak: list, on_progress=None,
                    on_bajt=None, megszakit=None) -> tuple:
        """Fájlok feltöltése egy alkalmazás megosztott mappájába.

        EZ a megbízható út a telefonra: a gyári Zene alkalmazás könyvtárát a
        telefon saját szolgáltatása birtokolja, és a kívülről írt bejegyzéseket
        előbb-utóbb felülírja (élőben megmértük). Egy lejátszó alkalmazás saját
        mappája viszont a miénk: amit oda teszünk, az ott is marad.

        Visszaad: (sikeres darab, hibák listája)."""
        utak = [u for u in (utak or []) if os.path.isfile(u)]
        if not utak:
            return 0, []
        f = A.alkalmazas_mappaja(self.ld, bundle)
        ok, hibak = 0, []
        n = len(utak)
        try:
            for i, u in enumerate(utak, 1):
                if megszakit is not None and megszakit():
                    break
                try:
                    nev = _tiszta_nev(os.path.basename(u))
                    cel = "Documents/" + nev
                    if f.letezik(cel):                 # ne írjunk felül semmit
                        torzs, kit = os.path.splitext(nev)
                        k = 2
                        while f.letezik("Documents/%s (%d)%s" % (torzs, k, kit)):
                            k += 1
                        cel = "Documents/%s (%d)%s" % (torzs, k, kit)
                    with open(u, "rb") as be:
                        f.ir(cel, be.read())
                    ok += 1
                except Exception as ex:
                    hibak.append("%s: %s" % (os.path.basename(u), ex))
                if on_progress:
                    on_progress(i, n, os.path.basename(u), ok)
        finally:
            f.bezar()
        return ok, hibak

    def app_torol(self, bundle: str, tetelek: list, on_progress=None) -> tuple:
        f = A.alkalmazas_mappaja(self.ld, bundle)
        ok, hibak = 0, []
        n = len(tetelek)
        try:
            for i, t in enumerate(tetelek, 1):
                try:
                    f.torol(t["ut"])
                    ok += 1
                except Exception as ex:
                    hibak.append("%s: %s" % (t.get("nev", "?"), ex))
                if on_progress:
                    on_progress(i, n, t.get("nev", ""), ok)
        finally:
            f.bezar()
        return ok, hibak


# ------------------------------------------------------------- kényelem

def csatlakoztatva() -> bool:
    try:
        return bool(A.keszulekek())
    except A.IPhoneHiba:
        return False


def meret_szoveg(b: int) -> str:
    for egyseg, hatar in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if b >= hatar:
            return "%.1f %s" % (b / hatar, egyseg)
    return "%d bájt" % b


def ido_szoveg(mp: int) -> str:
    if mp <= 0:
        return ""
    return "%d:%02d" % (mp // 60, mp % 60)
