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
    kat_kulcsok = {j.kulcs for j in KAT.mind()}      # RETRO + SAJÁT
    for k in JR.REGISZTER:
        assert k in kat_kulcsok, f"{k} nincs a katalógusban"


def test_minden_regisztralt_jatek_fuggveny():
    for k, f in JR.REGISZTER.items():
        assert callable(f), f"{k} nem hívható"


# ---- szerző-megjelölés (a fejlesztő KIFEJEZETT kérése) -------------------

def test_attribucio_ismert_szerzovel():
    j = KAT.keres("huszonegy")
    sz = KAT.attribucio_szoveg(j)
    assert "Ócsvári Áron" in sz
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


def test_huszonegy_aron_egy_parti_lejatszik():
    """Ócsvári Áron Huszonegye: k-val indul, húz, majd az összesítővel zárul."""
    def bot(k, ki):
        kl = k.lower()
        if "válasszon" in kl:
            return "k"
        if "újra húzni" in kl:
            return "i"
        if "még egyet" in kl:
            return "n"
        return ""
    ki = _fut("huszonegy", bot)
    assert any("eredmények" in p for _, p in ki)          # a záró összesítő


def test_huszonegy_aron_szabaly_menupont():
    """Az 's' menüpont szó szerint kiírja a forrás szabályát (Áron kreditjével),
    majd 'n'-re udvariasan búcsúzik és véget ér."""
    ki = U.lejatsz(JR.REGISZTER["huszonegy"], iter(["s", "n"]))
    assert ki[-1][0] == "vege"
    assert any("Legalább két lapot" in p for _, p in ki)   # eredeti szabály
    assert any("Ócsvári Áron" in p for _, p in ki)         # a kredit a szabályban
    assert any("Viszlát" in p for _, p in ki)


def test_huszonegy_aron_szabalytalan_megallas_kiesik():
    """A forrás szabálya: két lap alatt / 15 pont alatt megállni tilos – aki
    az első lap után megáll, „kiesett" (a partit zárja, nem lövi ki a gépet)."""
    ki = U.lejatsz(JR.REGISZTER["huszonegy"], iter(["k", "n"]))
    assert ki[-1][0] == "vege"
    assert any("kiesett" in p for _, p in ki)


def test_kocka_hat_dobas_eredmenyhirdetes():
    """KOCKA: bemutatkozás, ismertető, 6-6 dobás, majd EREDMÉNYHIRDETÉS."""
    def bot(k, ki):
        kl = k.lower()
        if "utónev" in kl:
            return "Dávid"
        if "ismertetőt" in kl:
            return "i"
        if "kezdhetjük" in kl:
            return "i"
        if "te dobsz" in kl:
            return "k"
        return ""
    ki = _fut("kocka", bot)
    assert any("EREDMÉNYHIRDETÉS" in p for _, p in ki)
    # hatszor dobtunk (hatszor kért „te dobsz")
    assert sum(1 for t, p in ki
               if t == "kerdez" and "te dobsz" in p.lower()) == 6


def test_fejtoro_tiz_kerdes_helyes_valasz_kituno():
    """FEJTÖRŐ: tíz szorzás; végig a helyes szorzatot adva 50 pont → RAGYOGÓAN."""
    import re

    def bot(k, ki):
        kl = k.lower()
        if "utónev" in kl:
            return "Dávid"
        if "ismertetőt" in kl:
            return "n"
        if "tanulást" in kl:
            return "i"
        if "mennyi" in kl:
            m = re.search(r"(\d+)\s*\*\s*(\d+)", k)
            return str(int(m.group(1)) * int(m.group(2)))
        return ""
    ki = _fut("fejtoro", bot)
    assert sum(1 for t, p in ki
               if t == "kerdez" and "mennyi" in p.lower()) == 10
    assert any("RAGYOGÓAN" in p for _, p in ki)


def test_fejtoro_ures_valasz_buta_ag():
    """Üres válasz a forrás „SZ=0" (buta vagy) ágára visz, mínusz tíz pont."""
    def bot(k, ki):
        kl = k.lower()
        if "utónev" in kl:
            return "Dávid"
        if "ismertetőt" in kl:
            return "n"
        if "tanulást" in kl:
            return "i"
        if "mennyi" in kl:
            return ""          # nincs válasz
        return ""
    ki = _fut("fejtoro", bot)
    assert any("BUTA VAGY" in p for _, p in ki)
    assert any("ELÉGTELEN" in p for _, p in ki)   # 10×(−10) → elégtelen


def test_kockaparti_ket_menet_eredmenyhirdetes():
    """KOCKAPARTI: te szabod meg a menetszámot; 2 menet után eredményhirdetés."""
    def bot(k, ki):
        kl = k.lower()
        if "utónev" in kl:
            return "Dávid"
        if "ismertetőt" in kl:
            return "n"
        if "kezdhetjük" in kl:
            return "i"
        if "hány menet" in kl:
            return "2"
        if "te dobsz" in kl:
            return "k"
        if "visszavágót" in kl:
            return "n"
        return ""
    ki = _fut("kockaparti", bot)
    assert any("EREDMÉNYHIRDETÉS" in p for _, p in ki)


def test_kockaparti_ervenytelen_menetszam():
    """0 vagy 100 fölötti menetszámra a forrás szövegével reklamál, majd újrakér."""
    def bot(k, ki):
        kl = k.lower()
        if "utónev" in kl:
            return "Dávid"
        if "ismertetőt" in kl:
            return "n"
        if "kezdhetjük" in kl:
            return "i"
        if "hány menet" in kl:
            # először 0 (túl kicsi), majd 200 (túl nagy), végül 1
            n = sum(1 for t, p in ki if t == "kerdez" and "hány menet" in p.lower())
            return {1: "0", 2: "200"}.get(n, "1")
        if "te dobsz" in kl:
            return "k"
        if "visszavágót" in kl:
            return "n"
        return ""
    ki = _fut("kockaparti", bot)
    assert any("NE SZÓRAKOZZÁL VELEM" in p for _, p in ki)
    assert any("TÚL NAGY SZÁM" in p for _, p in ki)


def test_celozz_schuck_antal_es_lezarul():
    """CÉLOZZ: a szerző (Schuck Antal) ajánlása elhangzik; a parti rendben zárul
    (10 lövedék után hadbíróság vagy találat, majd nemleges maradás)."""
    def bot(k, ki):
        kl = k.lower()
        if "felkészültél" in kl:
            return "i"
        if "koordinátát" in kl:
            return "1"
        if "maradsz" in kl:
            return "n"
        return ""
    ki = _fut("celozz", bot)
    assert any("Schuck Antal" in p for _, p in ki)
    assert any("VISZONTLÁTÁSRA" in p for _, p in ki)


def test_tizfeles_binaris_kereses_nyer():
    """TÍZ FELES: felezős tippeléssel 1–100 között 10 tippen belül BIZTOS nyer,
    tehát nem fogynak el a felesek; a végén 'n'-re udvariasan búcsúzik."""
    st = {"lo": 1, "hi": 100, "guess": None}

    def bot(k, ki):
        kl = k.lower()
        if "ismertetőt" in kl:
            return "n"
        if "legnagyobb gondolt" in kl:
            st.update(lo=1, hi=100, guess=None)
            return "100"
        if "tipp" in kl:
            monds = [p.lower() for t, p in ki if t == "mond"]
            if monds and st["guess"] is not None:
                if "nagyobb számot" in monds[-1]:
                    st["lo"] = st["guess"] + 1
                elif "kissebb számot" in monds[-1]:
                    st["hi"] = st["guess"] - 1
            st["guess"] = (st["lo"] + st["hi"]) // 2
            return str(st["guess"])
        if "szeretnél még" in kl:
            return "n"
        return ""
    ki = _fut("tizfeles", bot)
    assert not any("ELFOGYTAK A FELESEID" in p for _, p in ki)   # nem vesztett
    assert any("BARÁTOM" in p or "SZERENCSEJÁTÉKON" in p for _, p in ki)


def test_fogadas_balogh_tibor_es_lezarul():
    """FOGADÁS: egy játékos all-in fogadásokkal – vagy 800-ig jut (GYŐZTÉL), vagy
    kiesik (MINDENKI VESZTETT); mindenképp lefut egy futam és rendben zárul."""
    import re

    def bot(k, ki):
        kl = k.lower()
        if "ismertetőt" in kl:
            return "n"
        if "hány játékos" in kl:
            return "1"
        if "játékos neve" in kl:
            return "Dávid"
        if "melyik versenyzőre" in kl:
            return "Lauda"
        if "mekkora összeggel" in kl:
            m = re.search(r"és (\d+) között", k)
            return m.group(1) if m else "0"
        if "ismétlés" in kl:
            return "n"
        return ""
    ki = _fut("fogadas", bot)
    assert any("Balogh Tibor" in p for _, p in ki)      # a szerző elhangzik
    assert any("VERSENY GYŐZTESE" in p for _, p in ki)  # legalább egy futam


def test_szokita_szo_mastermind_lezarul():
    """SZOKITA: pár tipp után X-szel elárultatjuk a szót, majd nem kérünk újat."""
    def bot(k, ki):
        kl = k.lower()
        if "ismertetését" in kl:
            return "n"
        if "tipped" in kl:
            n = sum(1 for t, p in ki if t == "kerdez" and "tipped" in p.lower())
            return "X" if n > 6 else "ABC"
        if "gondoljak új" in kl:
            return "n"
        return ""
    ki = _fut("szokita", bot)
    assert any("GONDOLT SZÓ" in p for _, p in ki)     # X → elárulja


def test_szofajok_kviz_osztalyzattal():
    """SZOFAJOK: három szóra válaszolunk, a végén osztályzat, majd kilépés."""
    def bot(k, ki):
        kl = k.lower()
        if "hány kérdést" in kl:
            return "3"
        if "névelő" in kl and "számnév" in kl:        # a szófaj-kérdés
            return "f"
        if "mégegyszer" in kl:
            return "n"
        return ""
    ki = _fut("szofajok", bot)
    assert sum(1 for t, p in ki if t == "mond" and "MILYEN SZÓ" in p) == 3
    assert any("SZERBUSZ" in p for _, p in ki)


def test_reszeg_schuck_antal_binaris_nyer():
    """RÉSZEG (Schuck Antal): felezéssel 0–20 között megtaláljuk a számot →
    NYERTÉL; majd nemleges válaszra kirak."""
    st = {"lo": 0, "hi": 20, "guess": None}

    def bot(k, ki):
        kl = k.lower()
        if "ismertetőt" in kl:
            return "n"
        if "tipped" in kl:
            monds = [p.lower() for t, p in ki if t == "mond"]
            if st["guess"] is not None:
                for mp in reversed(monds):
                    if "túl nagy" in mp:
                        st["hi"] = st["guess"] - 1
                        break
                    if "túl kicsi" in mp:
                        st["lo"] = st["guess"] + 1
                        break
            st["guess"] = (st["lo"] + st["hi"]) // 2
            return str(st["guess"])
        if "inni" in kl:
            return "n"
        return ""
    ki = _fut("reszeg", bot)
    assert any("NYERTÉL" in p for _, p in ki)
    assert any("MARS KI" in p for _, p in ki)


def test_betpoker_pontallas_es_feladas():
    """BETŰPÖKER: a ** pontállást mond (nem tipp), a * feladja és elárulja a szót."""
    st = {"n": 0}

    def bot(k, ki):
        kl = k.lower()
        if "szabályokat" in kl:
            return "n"
        if "kérem a szót" in kl:
            st["n"] += 1
            return "**" if st["n"] == 1 else "*"
        if "játszunk még" in kl:
            return "n"
        return ""
    ki = _fut("betpoker", bot)
    assert any("betű" in p and "hossza" in p for _, p in ki)   # hossz-tipp
    assert any("pontod van" in p for _, p in ki)               # ** pontállás
    assert any("A szó" in p and "tipped volt" in p for _, p in ki)  # * feladás


def test_felkaru_sedi_gabor_lejatszik():
    """FÉLKARÚ BANDITA (Sédi Gábor 1985): pörget, a pénz elfogy, majd lezárul;
    a nyeremény átlagosan csökken, ezért véges kör alatt véget ér."""
    import random
    random.seed(20260726)

    def bot(k, ki):
        if "Forgatás" in k:
            return "3"
        if "Folytassuk" in k:
            return "n"           # a pénz elfogytakor kilépünk
        return ""
    ki = _fut("felkaru", bot)
    sz = U.szoveg(ki).lower()
    assert "félkarú bandita" in sz
    assert "pénzbedobás" in sz
    assert "a három tárcsa" in sz
    assert "elvesztette a pénzét" in sz          # eljut a pénz elfogyásáig
    # katalógus: az eredeti szerző megjelölve
    j = next(x for x in KAT.RETRO if x.kulcs == "felkaru")
    assert j.szerzo == "Sédi Gábor" and j.ev == "1985"


def test_felkaru_ervenytelen_forgatas_nem_fogadja_el():
    """Érvénytelen fordulatszámra a forrás szerint nem pörget, hanem szól."""
    import random
    random.seed(1)
    st = {"n": 0}

    def bot(k, ki):
        if "Forgatás" in k:
            st["n"] += 1
            return "0" if st["n"] == 1 else "2"   # előbb rossz, majd jó
        if "Folytassuk" in k:
            return "n"
        return ""
    ki = _fut("felkaru", bot)
    assert any("nem fogadom el" in p.lower() for _, p in ki)


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


def _gyufapoc_bot(k, ki):
    kl = k.lower()
    if "szabályokat" in kl:
        return "n"
    if "elérendő pontszám" in kl:
        return "6"
    if "hányan" in kl:
        return "1"
    if "írd ide a neved" in kl:
        return "Dávid"
    if "pöckölj" in kl:            # pöckölés-felszólítás (a JÁTÉKOS indítja)
        return "p"
    if "folytatod vagy marad" in kl:
        return "m"                 # az első pontnál bankolunk
    if "játszunk még" in kl:
        return "n"
    return ""


def test_gyufapoc_forrashu_lezarul():
    """A GYUFAPOC forráshű átültetése: szabály-kérdés, elérendő pontszám,
    játékosszám, majd P-vel pöckölés a Brailab gép ellen a célpontszámig."""
    ki = _fut("gyufa", _gyufapoc_bot)
    assert any("GYUFAPÖCKÖLŐ JÁTÉK" in p for _, p in ki)
    assert any("Brailab" in p for _, p in ki)       # a gép mint Brailab
    assert ki[-1][0] == "vege"


def test_gyufapoc_elso_pockolest_a_jatekos_inditja():
    """Homelab-listás bug: eddig a gép pöckölt a játékos helyett. Most az első
    dobás-eredmény ELŐTT a JÁTÉKOST kéri pöckölni (P)."""
    ki = _fut("gyufa", _gyufapoc_bot)
    tipusok = list(ki)
    kezd = next(i for i, (t, p) in enumerate(tipusok)
                if t == "mond" and "kezdd el a játékot" in p)
    kov_kerdes = next(p for t, p in tipusok[kezd:] if t == "kerdez")
    assert "pöckölj" in kov_kerdes.lower()          # nem azonnali gép-dobás


def test_gyufapoc_szabaly_menupont():
    """Az 'i'-re kiírja a szabályt (pöckölés-pontok), majd 'Értetted?'-re tovább."""
    lepesek = iter(["i", "i", "2", "1", "Teszt", "p", "m", "n"])
    ki = U.lejatsz(JR.REGISZTER["gyufa"], lepesek)
    assert any("népszerű játék" in p for _, p in ki)
    assert ki[-1][0] == "vege"


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


# =========================================================================
#  Térbeli játékok: Lóugrás verseny, Labirintus
# =========================================================================
class _HorstepBot:
    N = 7

    def __init__(self):
        self.cur = None
        self.cand = []
        self.i = 0

    def __call__(self, k, ki):
        import re
        kl = k.lower()
        if "táblaméret" in kl:
            return "1"                     # 7×7
        m = re.search(r"a\(z\) ([a-g])(\d+) mez", k, re.I)
        if m:
            cur = (m.group(1), int(m.group(2)))
            if cur != self.cur:
                self.cur = cur
                y = ord(cur[0]) - ord("a")
                x = cur[1] - 1
                self.cand = []
                for dx, dy in ((1, 2), (2, 1), (-1, 2), (-2, 1),
                               (1, -2), (2, -1), (-1, -2), (-2, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.N and 0 <= ny < self.N:
                        self.cand.append(f"{chr(ord('a') + ny)}{nx + 1}")
                self.i = 0
            else:
                self.i = (self.i + 1) % max(1, len(self.cand))
            return self.cand[self.i] if self.cand else "a1"
        return ""


def test_horstep_lejatszhato():
    ki = _fut("horstep", _HorstepBot())
    assert any(("NYERTÉL" in p) or ("gép nyert" in p) for _, p in ki)


class _LabirintBot:
    """Jobbkéz-szabályos falkövető: perfekt labirintusban garantáltan kijut."""

    def __init__(self):
        self.facing = (0, 1)
        self.order = None
        self.oi = 0
        self._cand = (0, 1)

    @staticmethod
    def _cw(d):
        return {(0, -1): (1, 0), (1, 0): (0, 1),
                (0, 1): (-1, 0), (-1, 0): (0, -1)}[d]

    @staticmethod
    def _ccw(d):
        return {(0, -1): (-1, 0), (-1, 0): (0, 1),
                (0, 1): (1, 0), (1, 0): (0, -1)}[d]

    @staticmethod
    def _name(d):
        return {(0, -1): "fel", (1, 0): "jobb",
                (0, 1): "le", (-1, 0): "bal"}[d]

    def __call__(self, k, ki):
        res = ""
        for t, p in reversed(ki[:-1]):
            if t == "mond":
                res = p
                break
        sikeres = ("Léptél" in res) or ("Kijutottál" in res) or ("LABIRINTUS" in res)
        if sikeres:
            if "LABIRINTUS" not in res:
                self.facing = self._cand
            self.order = None
        if self.order is None:
            r = self._cw(self.facing)
            self.order = [r, self.facing, self._ccw(self.facing),
                          self._cw(self._cw(self.facing))]
            self.oi = 0
        else:
            self.oi = min(self.oi + 1, 3)
        self._cand = self.order[self.oi]
        return self._name(self._cand)


def test_labirint_megoldhato():
    ki = _fut("labirint", _LabirintBot())
    assert any("Kijutottál" in p for _, p in ki)


# =========================================================================
#  Kaland játékok
# =========================================================================
def test_csata_veget_er():
    def bot(k, ki):
        return "nem" if "új csata" in k.lower() else ""
    ki = _fut("csata", bot)
    assert any(("Győzelem" in p) or ("elfoglalták" in p) or ("döntetlen" in p)
               for _, p in ki)


def test_harcos_vegigjatszhato():
    def bot(k, ki):
        return "nem" if "újrajátszod" in k.lower() else "1"
    ki = _fut("harcos", bot)
    assert any("HŐS lettél" in p for _, p in ki)


def test_allah_veget_er():
    def bot(k, ki):
        kl = k.lower()
        if "emelet" in kl:
            return "1"
        if "szoba" in kl:
            return "1"
        if "új játék" in kl:
            return "nem"
        return ""
    ki = _fut("allah", bot)
    assert any(("Megtaláltad" in p) or ("Lejárt az idő" in p) for _, p in ki)


class _ZongoraBot:
    def __init__(self):
        self.n = 0

    def __call__(self, k, ki):
        if "milyen hangot" in k.lower():
            self.n += 1
            return {1: "c d e", 2: "dallam"}.get(self.n, "kilép")
        return ""


def test_zongora_jatszik_hangot():
    ki = _fut("zongora", _ZongoraBot())
    assert any(t == "hang" for t, _ in ki), "nem szólalt meg hang"


def test_szindbad_veget_er():
    def bot(k, ki):
        kl = k.lower()
        if "neved" in kl:
            return "Ali"
        if "melyik hölgyet" in kl:
            return "3"
        if "párbaj" in kl:
            return ""
        if "új kaland" in kl:
            return "nem"
        return ""
    _fut("szindbad", bot)


# =========================================================================
#  A JATEK.EXE gyűjtemény mini-játékai
# =========================================================================
def test_domino_automatan_lejatszhato():
    ki = _fut("domino", lambda k, ki: "")     # Enter = automatikus lépés
    assert any("NYERTÉL" in p or "gép nyert" in p or "döntetlen" in p
               for _, p in ki)


def test_tozsde_tiz_nap():
    def bot(k, ki):
        return "t" if "mit teszel" in k.lower() else ""
    ki = _fut("tozsde", bot)
    assert any("vagyonod" in p for _, p in ki)


def test_korong_automatan_lejatszhato():
    ki = _fut("korong", lambda k, ki: "")     # Enter = a gép lép helyetted
    assert any("Vége!" in p for _, p in ki)


def test_korong_ervenyes_lepest_elfogad():
    """A kezdőállásból a d3 (sötét) érvényes lépés – el kell fogadni."""
    def bot(k, ki):
        kl = k.lower()
        if "hová raksz" in kl:
            return "d3"
        return ""     # a folytatásban a gépre bízzuk
    # csak az első emberi lépést vizsgáljuk determinisztikusan
    KORONG = importlib.import_module(BASE + ".jatekok.mini")
    tabla = [["."] * 8 for _ in range(8)]
    tabla[3][3] = tabla[4][4] = "O"
    tabla[3][4] = tabla[4][3] = "X"
    legal = KORONG._rev_legal(tabla, "X")
    assert (3, 2) in legal, "a d3 nem számít érvényesnek (koordináta-hiba?)"


def test_nyulfarm_lejatszik():
    def bot(k, ki):
        return "2" if "hány nyulat adsz el" in k.lower() else ""
    _fut("nyulfarm", bot)


def test_hamurabi_lejatszik():
    def bot(k, ki):
        kl = k.lower()
        if "holdat veszel" in kl:
            return "0"
        if "osztasz szét" in kl:
            return "100000"
        if "holdat vetsz" in kl:
            return "100000"
        return ""
    ki = _fut("hamurabi", bot)
    assert any(("Letelt a tíz év" in p) or ("fellázadt" in p)
               or ("Kihalt" in p) for _, p in ki)


class _MokitaBot:
    def __init__(self):
        import itertools
        self.perms = iter("".join(p)
                          for p in itertools.permutations("123456789", 3))

    def __call__(self, k, ki):
        kl = k.lower()
        if "tipp" in kl:
            return next(self.perms, "123")
        if "új játék" in kl:
            return "nem"
        return ""


def test_mokita_megfejtheto():
    ki = _fut("mokita", _MokitaBot())
    assert any("Kitaláltad" in p for _, p in ki)


# =========================================================================
#  SuperDL SAJÁT játékok (nem retró): Slot, UNO
# =========================================================================
class _SlotBot:
    def __init__(self):
        self.n = 0

    def __call__(self, k, ki):
        if "pörgetsz" in k.lower():
            self.n += 1
            return "kilép" if self.n > 8 else ""
        return ""


def test_slot_lejatszhato_es_ad_hangot():
    ki = _fut("slot", _SlotBot())
    assert any(t == "effekt" and p == "porgetes" for t, p in ki), \
        "nincs pörgetés-hang"
    assert any("érmé" in p for _, p in ki)


class _UnoBot:
    """Aktívan lerak: elsőre az 1-est, elutasításkor az első rakhatót."""

    def __call__(self, k, ki):
        import re
        kl = k.lower()
        if "milyen színt" in kl:
            return "kék"
        if "lerakod?" in kl:
            return "igen"
        if "új játék" in kl:
            return "nem"
        if "melyik lapot rakod" in kl:
            for _, p in reversed(ki):
                m = re.search(r"Rakható sorszámok: ([\d, ]+)", p)
                if m:
                    return m.group(1).split(",")[0].strip()
                if "A lapjaid:" in p:
                    break
            return "1"
        return ""


def test_uno_vegigjatszhato():
    ki = _fut("uno", _UnoBot())
    assert any(("NYERTÉL" in p) or ("nyert" in p) for _, p in ki)
    assert any(t == "effekt" and p == "kartya" for t, p in ki), \
        "nincs kártyahang"


def test_uno_huzo_bottal_is_veget_er():
    """Ha a játékos csak húz/passzol, akkor is véget ér (valamelyik gép nyer)."""
    def bot(k, ki):
        kl = k.lower()
        if "melyik lapot rakod" in kl:
            return "h"
        if "lerakod?" in kl:
            return "nem"
        if "milyen színt" in kl:
            return "piros"
        if "új játék" in kl:
            return "nem"
        return ""
    _fut("uno", bot)


# =========================================================================
#  HITELES Homelab-portok
# =========================================================================
class _BjBot:
    def __init__(self):
        self.n = 0

    def __call__(self, k, ki):
        kl = k.lower()
        if "mennyit teszel" in kl:
            self.n += 1
            return "0" if self.n > 4 else "10"
        if "biztosítást" in kl or "szétválasztod" in kl:
            return "nem"
        if "parancs" in kl:
            return "0"                     # megállás (stand)
        return ""


def test_blackjack_lejatszhato():
    ki = _fut("blackjack", _BjBot())
    assert any("EREDMÉNYEM" in p for _, p in ki)


def test_blackjack_a_forras_szovegeit_hasznalja():
    """Retró-hűség: az eredeti üzenetek megvannak a kódban."""
    import inspect
    src = inspect.getsource(
        importlib.import_module(BASE + ".jatekok.homelab"))
    for uzenet in ("TUL SOK! 500 A FELSŐ HATÁR", "A FEDETT LAPOM",
                   "AZ EREDMÉNYEM", "TUL KÉSŐ DUPLÁZNI, ÖREGEM!",
                   "ELSŐ KÉZ JÁTSZIK"):
        assert uzenet in src, f"hiányzik az eredeti üzenet: {uzenet}"


def test_blackjack_szerzoje_a_forras_szerinti():
    j = KAT.keres("blackjack")
    assert j.szerzo == "Halmágyi István" and j.ev == "1985"
    assert "Halmágyi István" in KAT.attribucio_szoveg(j)


class _Szamkit1Bot:
    """Bináris kereséssel megtalálja a számot."""

    def __init__(self):
        self.lo, self.hi, self.g = 1, 100, 50

    def __call__(self, k, ki):
        kl = k.lower()
        if "szeretnél még" in kl:
            return "N"
        if "kérem a tippet" in kl:
            for _, p in reversed(ki[:-1]):
                if "NAGYOBBAT" in p:
                    self.lo = self.g + 1
                    break
                if "KISSEBBET" in p:
                    self.hi = self.g - 1
                    break
                if "KÉREM A TIPPET" in p:
                    break
            self.g = (self.lo + self.hi) // 2
            return str(self.g)
        return ""


def test_szamkit1_kitalalhato():
    ki = _fut("szamkit1", _Szamkit1Bot())
    assert any("ELTALÁLTAD" in p for _, p in ki)
    assert any("TIPPED VOLT" in p for _, p in ki)


class _AmobaBot:
    def __init__(self):
        self.i = 0

    def __call__(self, k, ki):
        kl = k.lower()
        if "védekező" in kl:
            return "N"
        if "játszunk még" in kl:
            return "N"
        if "hová raksz" in kl:
            b = "ABCDEFGHIJKLMNOPR"
            c = b[self.i % 17]
            r = b[(self.i // 17) % 17]
            self.i += 1
            return f"{c} {r}"
        return ""


def test_amoba_lejatszhato_es_a_gep_lep():
    ki = _fut("amoba", _AmobaBot())
    assert any("Gondolkodom" in p for _, p in ki)
    assert any(("GYŐZTÉL" in p) or ("MOST ÉN NYERTEM" in p) or
               ("döntetlen" in p) for _, p in ki)


def test_amoba_ot_egy_sorban_nyer():
    """A vízszintes ötös érzékelése (a győzelmi feltétel helyes)."""
    HL = importlib.import_module(BASE + ".jatekok.homelab")
    board = [["."] * 17 for _ in range(17)]
    for c in range(5):
        board[3][c] = "X"
    assert HL._amoba_nyer(board, 3, 4, "X")
    assert not HL._amoba_nyer(board, 3, 4, "O")


class _NimBot:
    def __call__(self, k, ki):
        import re
        kl = k.lower()
        if "hány kupac" in kl:
            return "3"
        if k.startswith("A("):
            return "3"
        if "honnan veszel" in kl:
            for _, p in reversed(ki):
                if p.startswith("A kupacok:"):
                    nums = [int(x) for x in re.findall(r"\d+", p)]
                    for idx, val in enumerate(nums):
                        if val > 0:
                            return str(idx + 1)
            return "1"
        if "abból mennyit" in kl:
            return "1"
        return ""


def test_nimjatek_lejatszhato():
    ki = _fut("nimjatek", _NimBot())
    assert any(("TE NYERTÉL" in p) or ("EN NYERTEM" in p) for _, p in ki)


def test_nim_ai_nyero_allasban_nullaz():
    """XOR≠0 állásból a gép nim-összeg 0-ra visz (nyerő lépés)."""
    HL = importlib.import_module(BASE + ".jatekok.homelab")
    i, m = HL._nim_ai([1, 2, 4])          # XOR = 7 ≠ 0
    kupac = [1, 2, 4]
    kupac[i] -= m
    assert kupac[0] ^ kupac[1] ^ kupac[2] == 0


class _MemtesztBot:
    def __call__(self, k, ki):
        kl = k.lower()
        if "játszunk még" in kl:
            return "N"
        if "ismételd meg" in kl:
            for _, p in reversed(ki):
                if p.startswith("A párok:"):
                    body = p[len("A párok:"):].strip().rstrip(".")
                    return " ".join(x.strip() for x in body.split(","))
            return ""
        return ""


def test_memteszt_a_forras_szavaival_es_veget_er():
    ki = _fut("memteszt", _MemtesztBot())
    assert any("RENDKIVŰLI TELJESITMÉNY" in p for _, p in ki)
    HL = importlib.import_module(BASE + ".jatekok.homelab")
    assert "SZEKRÉNY" in HL._MEMTESZT_SZAVAK and "KILINCS" in HL._MEMTESZT_SZAVAK


def test_lotto_otos_es_hatos():
    def bot(k, ki):
        kl = k.lower()
        if "hány szelvényre" in kl:
            return "3"
        if "hagyományos" in kl:
            return "1"
        if "mondhatom" in kl:
            return "i"
        if "megismételjem" in kl:
            return "n"
        return ""
    ki = _fut("lotto", bot)
    # 5 szám / szelvény, három szelvény
    assert sum(1 for _, p in ki if p.startswith("AZ ELSŐ SZÁM")) == 3
    assert any("A TIPP ELFOGYOTT" in p for _, p in ki)


def test_lotto_csipos_duma():
    """A LOTTÓ csípős dumája (forrásból): NEM-re a lajhár-, másra a cseszegetős
    poén hangzik el, majd IGEN-re kihúzza."""
    st = {"n": 0}

    def bot(k, ki):
        kl = k.lower()
        if "hány szelvényre" in kl:
            return "1"
        if "hagyományos" in kl:
            return "1"
        if "mondhatom" in kl:
            st["n"] += 1
            return {1: "n", 2: "x"}.get(st["n"], "i")   # nem, más, majd igen
        if "megismételjem" in kl:
            return "n"
        return ""
    ki = _fut("lotto", bot)
    assert any("LAJHÁRT" in p for _, p in ki)
    assert any("CSESZEGETNI" in p for _, p in ki)


def test_lotto_hatos():
    """Hatos lottó (6/45): a hatodik szám is elhangzik."""
    def bot(k, ki):
        kl = k.lower()
        if "hány szelvényre" in kl:
            return "1"
        if "hagyományos" in kl:
            return "2"                      # hatos lottó
        if "mondhatom" in kl:
            return "i"
        if "megismételjem" in kl:
            return "n"
        return ""
    ki = _fut("lotto", bot)
    assert any(p.startswith("A HATODIK SZÁM") for _, p in ki)


def test_foldrajz_donesi_fa_ep():
    """Minden kérdés IGEN/NEM célja létező node; a végpontok tippek."""
    HL = importlib.import_module(BASE + ".jatekok.homelab")
    fa = HL._FOLDRAJZ_FA
    for node, tip in fa.items():
        if tip[0] == "q":
            assert tip[2] in fa and tip[3] in fa, f"{node}: rossz cél"
        else:
            assert tip[0] == "g" and isinstance(tip[1], str)


def test_foldrajz_franciaorszag_utvonal():
    """A forrás fája szerint: nagyobb, nem határos, nem skandináv, nem balkáni,
    nem sziget, nem szocialista, Andorrával határos, NÁTÓ-ból kilépett →
    Franciaország."""
    valaszok = iter(["I",           # Szeretnél játszani?
                     "I",           # Megvan?
                     "I",           # nagyobb Magyarországnál?
                     "N",           # Magyarországgal határos?
                     "N",           # Skandináv?
                     "N",           # Balkán?
                     "N",           # Sziget?
                     "N",           # Szocialista?
                     "I",           # Andorrával határos?
                     "I",           # NÁTÓ 1966?
                     "I",           # (a tippet elfogadom)
                     "N"])          # Szeretnél játszani? -> vége

    def bot(k, ki):
        return next(valaszok, "N")
    ki = _fut("foldrajz", bot)
    assert any("Franciaországra gondoltál?" in p for _, p in ki)


def test_foldrajz_lejatszhato_es_talal():
    def bot(k, ki):
        kl = k.lower()
        if "szeretnél játszani" in kl:
            return "N" if any("gondoltál?" in p for _, p in ki) else "I"
        if "megvan" in kl:
            return "I"
        if "gondoltál?" in kl:
            return "I"
        return "N"
    ki = _fut("foldrajz", bot)
    assert any("gondoltál?" in p for _, p in ki)
    assert any("Köszönöm a játékot" in p for _, p in ki)


class _SzamKit2Bot:
    def __init__(self):
        self.lo, self.hi, self.g = 0, None, None

    def __call__(self, k, ki):
        import re
        kl = k.lower()
        if "mekkora számig" in kl:
            return "50"
        if "mégeggyet" in kl:
            return "N"
        if "próbáld meg" in kl:
            if self.hi is None:
                for _, p in reversed(ki):
                    m = re.search(r"0 ÉS (\d+) KÖZÖTT", p)
                    if m:
                        self.hi = int(m.group(1))
                        break
                self.hi = self.hi if self.hi is not None else 50
            for _, p in reversed(ki[:-1]):
                if "NAGYOBBAT GONDOLTAM" in p:
                    self.lo = self.g + 1
                    break
                if "KISSEBBET GONDOLTAM" in p:
                    self.hi = self.g - 1
                    break
                if "GONDOLTAM EGY SZÁMOT" in p:
                    break
            self.g = (self.lo + self.hi) // 2
            return str(self.g)
        return ""


def test_szamkit2_kitalalhato():
    ki = _fut("szamkit2", _SzamKit2Bot())
    assert any("ELTALÁLTAD GRATULÁLOK" in p or "ELTALÁLTAD" in p
               for _, p in ki)


def test_dobokoc_veget_er():
    def bot(k, ki):
        kl = k.lower()
        if "dobáshoz nyomj entert" in kl:
            return ""
        if "akartok még játszani" in kl:
            return "N"
        return ""
    ki = _fut("dobokoc", bot)
    assert any("MEGNYERTED A JÁTSZMÁT" in p or "MEGNYERTE A JÁTSZMÁT" in p
               or "Döntetlen" in p for _, p in ki)


# ---- jogtisztaság: a játékkód nem hív idegen beszédmotort/alfolyamatot ----

def test_jatekok_nem_hasznalnak_idegen_fuggoseget():
    import ast
    import inspect
    for modnev in ("kartya", "logika", "kviz", "kaland", "terkep", "mini",
                   "sajat", "homelab", "_util"):
        mod = importlib.import_module(f"{BASE}.jatekok.{modnev}")
        fa = ast.parse(inspect.getsource(mod))
        for csp in ast.walk(fa):
            if isinstance(csp, (ast.Import, ast.ImportFrom)):
                nev = ((getattr(csp, "module", "") or "") + " "
                       + " ".join(a.name for a in csp.names)).lower()
                for tilt in ("espeak", "subprocess", "os.system"):
                    assert tilt not in nev, f"{modnev}: idegen függőség: {nev}"
