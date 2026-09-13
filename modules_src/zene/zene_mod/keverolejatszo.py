# -*- coding: utf-8 -*-
"""Áttűnő lejátszó: KÉT Core-lejátszó, felváltva.

Az áttűnéshez egyszerre két hangfolyamnak kell szólnia: az egyik elhalkul, a
másik feljön. A Core `Player`-e mintaszinten állítja a hangerőt (numpy), tehát
ez pusztán két példány és egy időzítés kérdése.

MÉRVE 2026-09-12 (aria2-tanulság: külső eszköznél a mérés a lemez-ellenőrzés):
két `sd.RawOutputStream` egyszerre megnyitható és írható ezen a gépen.
DE nem minden hangkártya-beállításnál az — ezért:

⚠️ HA AZ ÁTTŰNÉS NEM MEGY, A ZENE AKKOR IS SZÓL. Ha a második hangfolyam nem
nyílik meg, azonnal átváltunk egyszerű váltásra, és többé nem próbálkozunk
ebben a munkamenetben. A „megpróbáltam, nem sikerült” itt nem semleges lenne:
néma lejátszó rosszabb, mint áttűnés nélküli lejátszó.
"""

import threading
import time

ATTUNES_MP = 3.0          # fix, a felhasználó döntése szerint
LEPES_MP = 0.1            # ennyinként állítjuk a hangerőt
FIGYELO_MP = 0.25         # ilyen sűrűn nézzük, közeleg-e a vég


class KeveroLejatszo:
    """Egy szám szól; a következőt kérésre áttűnéssel hozza be.

    Visszahívások (mind HÁTTÉRSZÁLRÓL jönnek – a hívó `wx.CallAfter`-rel
    lépjen tovább):
      on_vege()          – a szám a végére ért (áttűnés nélkül)
      on_attunes_ido()   – ATTUNES_MP másodperccel a vége előtt
      on_hiba(szoveg)    – a szám nem játszható le
    """

    def __init__(self, on_vege=None, on_attunes_ido=None, on_hiba=None):
        from superdl.audioengine import Player
        self._a = Player()
        self._b = Player()
        self._aktiv = self._a
        self._masik = self._b
        self._a.set_volume(1.0)
        self._b.set_volume(1.0)
        self.on_vege = on_vege
        self.on_attunes_ido = on_attunes_ido
        self.on_hiba = on_hiba
        self.attunes_megy = True      # amíg be nem bizonyosodik az ellenkezője
        self.fo_hangero = 1.0         # a felhasználó által beállított hangerő
        self._szorzo = 1.0            # ideiglenes szorzó (elalvás-elhalkulás)
        self._hossz = 0.0
        self._nemzedek = 0
        self._jelezve = False
        self._attunesben = False
        self._zar = threading.Lock()
        self._all = threading.Event()
        self._figyelo = threading.Thread(target=self._figyel, daemon=True)
        self._figyelo.start()

    # ---- lejátszás ----------------------------------------------------

    def jatszik(self, ut: str, hossz: float = 0.0) -> None:
        """Azonnali váltás: az eddigi elhallgat, az új teljes hangerőn szól."""
        with self._zar:
            self._nemzedek += 1
            gen = self._nemzedek
            self._jelezve = False
            self._attunesben = False
            self._hossz = max(0.0, float(hossz or 0.0))
            self._masik.stop()
            self._aktiv.stop()
            self._aktiv.set_volume(self._cel())
            self._aktiv.on_state = self._allapot_kezelo(gen)
            self._aktiv.play(ut)

    def attunes_ra(self, ut: str, hossz: float = 0.0) -> None:
        """A következő szám behozása áttűnéssel (ha nem megy: egyszerű váltás)."""
        if not self.attunes_megy:
            self.jatszik(ut, hossz)
            return
        with self._zar:
            if self._attunesben:
                return
            self._attunesben = True
            self._nemzedek += 1
            gen = self._nemzedek
            self._jelezve = False
            uj_hossz = max(0.0, float(hossz or 0.0))
            be, ki = self._masik, self._aktiv
            baj = {"van": False}

            def kezelo(szoveg, _gen=gen):
                if str(szoveg).startswith("hiba"):
                    baj["van"] = True
                self._allapot_kezelo(_gen)(szoveg)

            be.stop()
            be.set_volume(0.0)
            be.on_state = kezelo
            be.play(ut)
        threading.Thread(target=self._attun,
                         args=(be, ki, uj_hossz, baj, ut, gen),
                         daemon=True).start()

    def _attun(self, be, ki, uj_hossz, baj, ut, gen) -> None:
        """Az áttűnés menete.

        ⚠️ A NEMZEDÉKET minden lépésben ellenőrizzük. Ha a felhasználó áttűnés
        KÖZBEN másik számra nyilaz, a `jatszik()` új nemzedéket nyit — a régi
        halványító szál pedig a végén leállítaná (`ki.stop()`) azt a lejátszót,
        amin épp az ÚJ szám szól, és a hangerőt is átállítaná. A zene némán
        elhallgatna, méghozzá pont attól, amit a kényelemért építettünk.
        """
        lepesek = max(1, int(ATTUNES_MP / LEPES_MP))
        for i in range(1, lepesek + 1):
            if self._all.is_set() or gen != self._nemzedek:
                return
            if baj["van"]:
                # ⚠️ A második hangfolyam nem megy: NE maradjon néma a zene.
                self.attunes_megy = False
                self._attunesben = False
                self.jatszik(ut, uj_hossz)
                return
            arany = i / lepesek
            # A hangerő-írás és a nemzedék-ellenőrzés EGY zár alatt. Enélkül
            # a leváltott szál utolsó írása ráülhet az ÚJ számra, és ott is
            # hagyhatja félhangosan – örökre, mert utána már kilép.
            with self._zar:
                if gen != self._nemzedek:
                    return
                try:
                    cel = self._cel()
                    be.set_volume(arany * cel)
                    ki.set_volume((1.0 - arany) * cel)
                except Exception:
                    pass
            time.sleep(LEPES_MP)
        with self._zar:
            if gen != self._nemzedek:
                return          # közben másik számra váltottak – ne nyúlj bele
            try:
                ki.stop()
                ki.set_volume(self._cel())
            except Exception:
                pass
            self._aktiv, self._masik = be, ki
            self._hossz = uj_hossz
            self._attunesben = False

    # ---- vezérlés -----------------------------------------------------

    def szunet_valt(self) -> bool:
        """True, ha most SZÜNETEL."""
        return self._aktiv.toggle_pause()

    def szunetel(self) -> bool:
        return self._aktiv.is_paused()

    def teker(self, delta: float) -> None:
        """Tekerés a számon belül. Áttűnés közben nem: az két számot mozgatna."""
        if self._attunesben:
            return
        self._aktiv.relative_seek(delta)
        self._jelezve = False        # az új pozícióhoz új vég-figyelés tartozik

    def pozicio(self) -> float:
        return self._aktiv.position()

    def hossz(self) -> float:
        return self._hossz

    def szol(self) -> bool:
        return self._aktiv.is_active()

    def _cel(self) -> float:
        """A pillanatnyi célhangerő: a beállított hangerő × az ideiglenes
        szorzó (utóbbi az elalvás-elhalkuláshoz kell)."""
        return max(0.0, min(1.0, self.fo_hangero * self._szorzo))

    def hangero(self, szorzo: float = 1.0) -> None:
        """Ideiglenes szorzó (1.0 = teljes). Az elalvás ezzel halkít le."""
        self._szorzo = max(0.0, min(1.0, szorzo))
        try:
            self._aktiv.set_volume(self._cel())
        except Exception:
            pass

    def fo_hangero_allit(self, v: float) -> float:
        """A felhasználó hangereje 0 és 1 között. Visszaadja a beállítottat."""
        self.fo_hangero = max(0.0, min(1.0, v))
        try:
            self._aktiv.set_volume(self._cel())
        except Exception:
            pass
        return self.fo_hangero

    def leallit(self) -> None:
        with self._zar:
            self._nemzedek += 1
            self._hossz = 0.0
            self._jelezve = False
            self._attunesben = False
        for p in (self._a, self._b):
            try:
                p.on_state = None
                p.stop()
                p.set_volume(1.0)
            except Exception:
                pass

    def bezar(self) -> None:
        self._all.set()
        self.leallit()

    # ---- belső --------------------------------------------------------

    def _allapot_kezelo(self, gen: int):
        def kezelo(szoveg):
            if gen != self._nemzedek:
                return                   # egy LEVÁLTOTT szám üzenete
            sz = str(szoveg or "")
            if sz.startswith("hiba"):
                if self.on_hiba:
                    self.on_hiba(sz)
            elif sz == "vége" and not self._attunesben:
                if self.on_vege:
                    self.on_vege()
        return kezelo

    def _figyel(self) -> None:
        """Egy szál, negyed másodpercenként: közeleg-e a szám vége?

        Csak akkor szól, ha ISMERJÜK a hosszt. Ha nem (nincs ffprobe), a
        váltást a „vége” jelzés intézi — áttűnés nélkül, de nem némán.
        """
        while not self._all.is_set():
            time.sleep(FIGYELO_MP)
            try:
                if (self._hossz > ATTUNES_MP and not self._jelezve
                        and not self._attunesben and self._aktiv.is_active()
                        and not self._aktiv.is_paused()
                        and self.pozicio() >= self._hossz - ATTUNES_MP):
                    self._jelezve = True
                    if self.on_attunes_ido:
                        self.on_attunes_ido()
            except Exception:
                pass
