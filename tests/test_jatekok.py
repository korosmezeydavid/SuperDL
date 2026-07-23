# -*- coding: utf-8 -*-
"""A Játékok modul RETRÓ játékainak tesztjei – felület (wx) NÉLKÜL.

A játékok generátor-korutinok, ezért egy egyszerű „bottal" végigjátszhatók és
gépi teszttel ellenőrizhetők. Minden játékra: fusson le hibátlanul és érjen
`vege`-hez. Emellett: a segédek, a szerző-megjelölés és a jogtisztaság.
"""
import importlib

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
KAT = importlib.import_module(BASE + ".katalogus")


def _fut(kulcs, bot):
    ki = U.lejatsz(JR.REGISZTER[kulcs], bot)
    assert ki, f"{kulcs}: nincs kimenet"
    assert ki[-1][0] == "vege", f"{kulcs}: nem ért véget rendben"
    return ki


# ---- segédek -------------------------------------------------------------

def test_igen_nem():
    assert U.igen("igen") is True
    assert U.igen("i") is True
    assert U.igen("nem") is False
    assert U.igen("n") is False
    assert U.igen("", alap=True) is True
    assert U.igen("hmm", alap=None) is None


def test_szam_tartomany():
    assert U.szam("3", 1, 3) == 3
    assert U.szam("4", 1, 3) is None
    assert U.szam("nem szám") is None
    assert U.szam(" 7 ") == 7


def test_egyezik_ekezet_es_kisbetu():
    assert U.egyezik("PÁRIZS", "párizs")
    assert U.egyezik("becs", "Bécs")
    assert U.egyezik("tokio", "Tokió", aliasok=("Tokyo",))
    assert not U.egyezik("Madrid", "Róma")


# ---- minden RETRÓ játék indítható-e a katalógusból -----------------------

def test_regiszter_kulcsai_a_katalogusban_vannak():
    kat_kulcsok = {j.kulcs for j in KAT.RETRO}
    for k in JR.REGISZTER:
        assert k in kat_kulcsok, f"{k} nincs a katalógusban"


def test_minden_regisztralt_jatek_fuggveny():
    for k, f in JR.REGISZTER.items():
        assert callable(f), f"{k} nem hívható"


# ---- szerző-megjelölés (a fejlesztő KIFEJEZETT kérése) -------------------

def test_attribucio_ismert_szerzovel():
    j = KAT.keres("huszonegy")
    sz = KAT.attribucio_szoveg(j)
    assert "Pille" in sz
    assert "Modernizálta Kőrösmezey Dávid" in sz
    assert "szerzői jogok" in sz


def test_attribucio_ismeretlen_szerzonel():
    j = KAT.keres("parbaj")            # nincs ismert szerző
    sz = KAT.attribucio_szoveg(j)
    assert "várjuk a szerző jelentkezését" in sz
    assert "Modernizálta Kőrösmezey Dávid" in sz


def test_minden_retro_jateknak_van_ertelmes_attribucioja():
    for j in KAT.RETRO:
        sz = KAT.attribucio_szoveg(j)
        assert "Modernizálta Kőrösmezey Dávid" in sz
        assert "órákért" in sz


# =========================================================================
#  Végigjátszások – egy-egy „bot" vezérli a játékot a végkifejletig.
# =========================================================================

def test_nim_vegigjatszhato():
    def bot(k, ki):
        kl = k.lower()
        if "kezdesz" in kl:
            return "igen"
        if "raksz le" in kl:
            return "1"
        if "új játék" in kl:
            return "nem"
        return ""
    ki = _fut("nim", bot)
    assert any("Maradt" in p for _, p in ki)


def test_nim_gep_optimalisan_jatszik():
    """Ha a játékos hibázik (mindig 1-et rak a 20-ból induló nyerő helyzetben),
    a gép a misère-optimumot játssza, és a JÁTÉKOS veszít."""
    def bot(k, ki):
        kl = k.lower()
        if "kezdesz" in kl:
            return "igen"
        if "raksz le" in kl:
            return "1"
        if "új játék" in kl:
            return "nem"
        return ""
    ki = U.lejatsz(JR.REGISZTER["nim"], bot)
    szoveg = U.szoveg(ki)
    assert "vesztettél" in szoveg, "a gép nem használta ki a nyerő stratégiát"


def test_mastermind_vegigjatszhato_es_ad_visszajelzest():
    def bot(k, ki):
        kl = k.lower()
        if "tipped" in kl:
            volt = any(("fekete" in p) or ("Feladtad" in p) for _, p in ki)
            return "0" if volt else "pkzb"
        if "új játék" in kl:
            return "nem"
        return ""
    ki = _fut("mastermind", bot)
    assert any("fekete" in p for _, p in ki)


class _TorpedoBot:
    def __init__(self):
        self.i = 0
        self.cellak = [f"{chr(97 + o)} {s + 1}"
                       for o in range(10) for s in range(10)]

    def __call__(self, k, ki):
        kl = k.lower()
        if "tipp" in kl:
            c = self.cellak[self.i % 100]
            self.i += 1
            return c
        if "új játék" in kl:
            return "nem"
        return ""


def test_torpedo_megtalalja_mind_a_negyet():
    ki = _fut("torpedo", _TorpedoBot())
    assert any("Mind a négy X megvan" in p for _, p in ki)


def test_teke_lejatszik_es_eredmenyt_hirdet():
    def bot(k, ki):
        return "3" if "menetes" in k.lower() else ""
    ki = _fut("teke", bot)
    assert any(("nyert" in p) or ("Döntetlen" in p) for _, p in ki)


def test_parbaj_veget_er():
    def bot(k, ki):
        kl = k.lower()
        if "pontig" in kl:
            return "2"
        if "állsz" in kl:
            return "1"
        if "lősz" in kl:
            return "2"
        return ""
    _fut("parbaj", bot)


def test_huszonegy_egy_kor_lejatszik():
    def bot(k, ki):
        kl = k.lower()
        if "kérsz még lapot" in kl:
            return "nem"
        if "új kör" in kl:
            return "nem"
        return ""
    ki = _fut("huszonegy", bot)
    assert any("Végeredmény" in p for _, p in ki)


def test_hazard_lejatszik():
    def bot(k, ki):
        kl = k.lower()
        if "hányszor" in kl:
            return "3"
        if "melyik dobozban" in kl:
            return "1"
        return ""
    _fut("hazard", bot)


def test_snobli_veget_er():
    def bot(k, ki):
        kl = k.lower()
        if "pontig" in kl:
            return "2"
        if "rejtesz el" in kl:
            return "1"
        if "összesen" in kl:
            return "4"
        return ""
    _fut("snobli", bot)


def test_kocka3_lejatszik():
    def bot(k, ki):
        return "3" if "hányszor" in k.lower() else ""
    ki = _fut("kocka3", bot)
    assert any("pont" in p for _, p in ki)


def test_kocka1_lejatszik():
    def bot(k, ki):
        return "3" if "forduló" in k.lower() else ""
    _fut("kocka1", bot)


def test_kockadob_veget_er():
    ki = _fut("kockadob", lambda k, ki: "")
    assert any(("NYERTÉL" in p) or ("célba" in p) for _, p in ki)


class _RulettBot:
    def __init__(self):
        self.n = 0

    def __call__(self, k, ki):
        kl = k.lower()
        if "mire teszel" in kl:
            self.n += 1
            return "kilép" if self.n > 3 else "piros"
        if "tét" in kl:
            return "10"
        return ""


def test_rulett_jatszhato_es_kilep():
    ki = _fut("rulett", _RulettBot())
    assert any("golyó" in p for _, p in ki)


class _RulibuliBot:
    def __init__(self):
        self.n = 0

    def __call__(self, k, ki):
        kl = k.lower()
        if "tipp:" in kl:
            self.n += 1
            return "kilép" if self.n > 3 else "2"
        if "tét" in kl:
            return "10"
        return ""


def test_rulibuli_jatszhato_es_kilep():
    _fut("rulibuli", _RulibuliBot())


def test_gyufa_veget_er():
    def bot(k, ki):
        kl = k.lower()
        if "pontig" in kl:
            return "10"
        if "megtartod" in kl:
            return "m"
        return ""
    ki = _fut("gyufa", bot)
    assert any("pont" in p for _, p in ki)


# =========================================================================
#  Kvíz / oktató játékok
# =========================================================================
KVIZ = importlib.import_module(BASE + ".jatekok.kviz")


def test_allatism_lejatszik():
    def bot(k, ki):
        return "5" if "hány kérdést" in k.lower() else ""
    ki = _fut("allatism", bot)
    assert any("helyes válasz" in p for _, p in ki)


def test_fovaros_lejatszik():
    def bot(k, ki):
        return "5" if "hány kérdést" in k.lower() else ""
    _fut("fovaros", bot)


def test_fovaros_helyes_valaszt_elfogad():
    """Ha a játékos jól válaszol, azt Helyesnek ismeri el."""
    def bot(k, ki):
        kl = k.lower()
        if "hány kérdést" in kl:
            return "3"
        if "fővárosa" in kl:
            for orsz, (fo, _al) in KVIZ._FOVAROS.items():
                if orsz.lower() in kl:
                    return fo
        return ""
    ki = U.lejatsz(JR.REGISZTER["fovaros"], bot)
    assert any(p == "Helyes!" for _, p in ki), "a jó választ nem fogadta el"
    assert any("3 helyes válasz 3-ből" in p for _, p in ki)


def test_atomvad_lejatszik():
    def bot(k, ki):
        kl = k.lower()
        if "új molekula" in kl:
            return "nem"
        return "1"                    # a pozíció-kérdésekre
    ki = _fut("atomvad", bot)
    assert any("molekula összeállt" in p for _, p in ki)


def test_braille_ket_mod():
    for mod in ("1", "2"):
        def bot(k, ki, _m=mod):
            kl = k.lower()
            if "hány kérdést" in kl:
                return "4"
            if "mód" in kl:
                return _m
            return ""
        _fut("braille", bot)


def test_morse_gyakorlas_es_lemorzezes():
    def bot1(k, ki):
        kl = k.lower()
        if "mit szeretnél" in kl:
            return "1"
        if "hány kérdést" in kl:
            return "4"
        return ""
    _fut("morse", bot1)

    def bot2(k, ki):
        kl = k.lower()
        if "mit szeretnél" in kl:
            return "2"
        if "írj be egy szót" in kl:
            return "sos"
        if "újabb szöveg" in kl:
            return "nem"
        return ""
    ki = _fut("morse", bot2)
    assert any("Morze:" in p for _, p in ki)


def test_kitalal_veget_er():
    def bot(k, ki):
        return "nem" if "új fogalom" in k.lower() else ""
    _fut("kitalal", bot)


def test_szamtan_lejatszik_es_ures_muvelet():
    def bot(k, ki):
        kl = k.lower()
        if "legnagyobb szám" in kl:
            return "20"
        if "műveletek" in kl:
            return "+ -"
        if "hány feladatot" in kl:
            return "5"
        return ""
    _fut("szamtan", bot)

    def bot_ures(k, ki):
        kl = k.lower()
        if "legnagyobb szám" in kl:
            return "10"
        if "műveletek" in kl:
            return "xyz"           # nincs érvényes jel
        if "hány feladatot" in kl:
            return "2"
        return ""
    ki = _fut("szamtan", bot_ures)
    assert any("minek ébresztettél fel" in p for _, p in ki)


def test_memoria_veget_er_hibanal():
    def bot(k, ki):
        kl = k.lower()
        if "írd vissza" in kl:
            return "biztosan-rossz-valasz"
        if "új játék" in kl:
            return "nem"
        return ""
    ki = _fut("memoria", bot)
    assert any("Hiba!" in p for _, p in ki)


class _MemoryBot:
    """Tanul a felfedett értékekből, és párokat alkot – így végigjátssza."""

    def __init__(self):
        import re
        self._re = re.compile(r"^([a-d][1-4]): (.+)\.$")
        self.ertek = {}
        self.matched = set()
        self.elso = None
        self.masodik = None

    def _tanul(self, ki):
        for _, p in ki[-4:]:
            m = self._re.match(p)
            if m:
                self.ertek[m.group(1)] = m.group(2)
        for _, p in ki[-2:]:
            if p.startswith("Pár!") and self.elso and self.masodik:
                self.matched.update((self.elso, self.masodik))

    def __call__(self, k, ki):
        self._tanul(ki)
        kl = k.lower()
        rejtett = [f"{o}{s}" for s in range(1, 5) for o in "abcd"
                   if f"{o}{s}" not in self.matched]
        if "első mező" in kl:
            for c in rejtett:
                if c in self.ertek:
                    for d in rejtett:
                        if d != c and self.ertek.get(d) == self.ertek[c]:
                            self.elso, self.masodik = c, d
                            return c
            for c in rejtett:
                if c not in self.ertek:
                    self.elso, self.masodik = c, None
                    return c
            self.elso, self.masodik = rejtett[0], None
            return rejtett[0]
        if "második mező" in kl:
            if self.masodik:
                return self.masodik
            for c in rejtett:
                if c != self.elso and c not in self.ertek:
                    self.masodik = c
                    return c
            for c in rejtett:
                if c != self.elso:
                    self.masodik = c
                    return c
            return self.elso
        return ""


def test_memory_vegigjatszhato():
    ki = _fut("memory", _MemoryBot())
    assert any("Minden párt megtaláltál" in p for _, p in ki)


def test_parver_tiz_kor():
    _fut("parver", lambda k, ki: "")


# ---- jogtisztaság: a játékkód nem hív idegen beszédmotort/alfolyamatot ----

def test_jatekok_nem_hasznalnak_idegen_fuggoseget():
    import ast
    import inspect
    for modnev in ("kartya", "logika", "kviz", "_util"):
        mod = importlib.import_module(f"{BASE}.jatekok.{modnev}")
        fa = ast.parse(inspect.getsource(mod))
        for csp in ast.walk(fa):
            if isinstance(csp, (ast.Import, ast.ImportFrom)):
                nev = ((getattr(csp, "module", "") or "") + " "
                       + " ".join(a.name for a in csp.names)).lower()
                for tilt in ("espeak", "subprocess", "os.system"):
                    assert tilt not in nev, f"{modnev}: idegen függőség: {nev}"
