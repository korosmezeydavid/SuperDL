# -*- coding: utf-8 -*-
"""MK6 – közös hibaszöveg és a figyelmet igénylő elemek.

A tesztek két dolgot védenek, és mindkettő olyan, amit egy későbbi javítás
könnyen elronthatna:

1. **A hálózat-kimaradás NEM lehet teendő.** Az MK2 egész értelme az volt, hogy
   erre a felhasználónak nem kell tennie semmit.
2. **A saját magyar mondatainkat nem fordítjuk újra.**
"""

from superdl import hibaszoveg
from superdl.manager import DownloadManager


class _P:
    def __init__(self, status="hiba", error="", conflict=False, filename=""):
        self.status = status
        self.error = error
        self.conflict = conflict
        self.filename = filename


class _J:
    def __init__(self, p, retries=0, url="http://p/x"):
        self.progress = p
        self.retries = retries
        self.url = url


# ---- a saját mondatainkhoz nem nyúlunk --------------------------------

def test_a_sajat_magyar_mondatot_nem_forditjuk_ujra():
    """Az MK3 hely-hibája már emberi nyelven szól; a mintaillesztés csak
    elronthatná."""
    sajat = ("Nincs elég hely a letöltéshez. A(z) film.mkv mérete 4,2 "
             "gigabájt, a célmeghajtón viszont csak 1,1 gigabájt szabad.")
    assert hibaszoveg.emberi(sajat) == sajat


def test_sajat_uzenet_felismerese():
    assert hibaszoveg.sajat_uzenet("Nincs elég hely a letöltéshez…")
    assert not hibaszoveg.sajat_uzenet("HTTP Error 403: Forbidden")


# ---- a torrent és a szegmens saját hibái ------------------------------

def test_aria2_nem_indul():
    sz = hibaszoveg.emberi("aria2c.exe not found")
    assert "torrent-motor" in sz
    assert "Frissítések keresése" in sz


def test_nincs_megoszto_nem_hibaztat():
    """Ez nem a felhasználó hibája és nem a programé – ezt ki kell mondani,
    különben azt hiszi, elrontott valamit."""
    sz = hibaszoveg.emberi("no peers available for this torrent")
    assert "nem a te hibád" in sz


def test_hibas_magnet_link():
    sz = hibaszoveg.emberi("invalid magnet URI")
    assert "magnet" in sz.lower()


def test_ismeretlen_hibat_NEM_talalunk_ki():
    """Kitalálni egy magyarázatot rosszabb a nyers hibánál: a hamis magyarázat
    órákat lop el (ez volt a tvmusor tanulsága)."""
    nyers = "valami teljesen ismeretlen belső hiba 12345"
    assert hibaszoveg.emberi(nyers) == nyers
    assert not hibaszoveg.van_javaslat(nyers)


def test_ures_uzenet_nem_szall_el():
    assert hibaszoveg.emberi("") == ""
    assert hibaszoveg.emberi(None) == ""
    assert not hibaszoveg.van_javaslat("")


def test_a_media_forditas_minden_motorra_elerheto():
    """A LÉNYEG: a `friendly_error` eddig csak a yt-dlp motorhoz volt bekötve.
    Egy 403-as hibát egy sima fájlletöltésnél is emberi nyelven kell mondani."""
    sz = hibaszoveg.emberi("HTTP Error 403: Forbidden")
    assert "MEGTAGADTA" in sz or "megtagadta" in sz.lower()
    assert hibaszoveg.van_javaslat("HTTP Error 403: Forbidden")


# ---- ki igényel figyelmet --------------------------------------------

def test_a_hiba_figyelmet_igenyel():
    assert DownloadManager.figyelmet_igenyel(_J(_P(status="hiba")))


def test_az_utkozes_figyelmet_igenyel():
    """DÖNTÉSRE vár, és az MK4 szerint nem is kap újrapróbát: magától soha nem
    oldódik meg."""
    assert DownloadManager.figyelmet_igenyel(
        _J(_P(status="várakozik", conflict=True)))


def test_a_HALOZATRA_VARO_NEM_igenyel_figyelmet():
    """EZ A LEGFONTOSABB TESZT A KÖRBEN. Az MK2 egész értelme az volt, hogy
    erre nem kell tenni semmit („nem kell tenned semmit: amint visszajön a
    net, magától folytatódnak"). Ha idesorolnánk, a felhasználót olyasmihez
    küldenénk, amit nem tud megjavítani – vagyis csendben visszacsinálnánk
    az MK2-t."""
    j = _J(_P(status=DownloadManager.HALOZATRA_VAR))
    assert not DownloadManager.figyelmet_igenyel(j)


def test_a_halozatra_varo_akkor_sem_ha_sokat_probalt():
    """A hálózatra várakozás akkor sem lesz teendő, ha régóta tart."""
    j = _J(_P(status=DownloadManager.HALOZATRA_VAR), retries=99)
    assert not DownloadManager.figyelmet_igenyel(j)


def test_a_varakozo_es_utemezett_nem_igenyel_figyelmet():
    assert not DownloadManager.figyelmet_igenyel(_J(_P(status="várakozik")))
    assert not DownloadManager.figyelmet_igenyel(_J(_P(status="ütemezve")))


def test_a_kezzel_leallitott_NEM_igenyel_figyelmet():
    """A felhasználó saját döntését problémának nevezni bosszantó."""
    assert not DownloadManager.figyelmet_igenyel(
        _J(_P(status="leállítva"), retries=99))


def test_a_kesz_nem_igenyel_figyelmet():
    assert not DownloadManager.figyelmet_igenyel(_J(_P(status="kész")))
    assert not DownloadManager.figyelmet_igenyel(
        _J(_P(status="kész"), retries=99))


def test_a_makacsul_ujraprobalkozo_igenyel_figyelmet():
    """Az első néhány bukás magától rendbe jöhet; a sokadik nem fog."""
    j = _J(_P(status="várakozik"), retries=DownloadManager.MAKACS_PROBA)
    assert DownloadManager.figyelmet_igenyel(j)
    keves = _J(_P(status="várakozik"), retries=1)
    assert not DownloadManager.figyelmet_igenyel(keves)


def test_a_futo_letoltes_nem_igenyel_figyelmet():
    assert not DownloadManager.figyelmet_igenyel(_J(_P(status="letöltés")))


# ---- a kimondott mondat ----------------------------------------------

def test_gond_mondat_a_nevvel_kezd():
    """Vakon először azt kell tudni, MELYIK elemről beszélünk – különben a
    mondat felénél még nem tudni, mire vonatkozik, amit hallok."""
    sz = hibaszoveg.gond_mondat("film.mkv", "hiba", "HTTP Error 403")
    assert sz.startswith("film.mkv:")


def test_gond_mondat_utkozesnel_a_dontest_mondja():
    sz = hibaszoveg.gond_mondat("film.mkv", "várakozik", "", utkozes=True)
    assert "DÖNTÉSRE vár" in sz
    assert "felülírhatod" in sz


def test_gond_mondat_mondja_a_probak_szamat():
    sz = hibaszoveg.gond_mondat("f.bin", "hiba", "valami", probak=4)
    assert "4 sikertelen" in sz


def test_gond_mondat_nev_nelkul_sem_szall_el():
    sz = hibaszoveg.gond_mondat("", "hiba", "")
    assert sz.startswith("a letöltés:")


# ---- MK6/6: a kiemelés után is minden a helyén van -------------------

def test_a_media_alias_ugyanaz_a_fuggveny():
    """A `friendly_error` a `hibaszoveg.py`-ba költözött, de a `media` alól is
    hívható maradt: a `searchwin.py` és a régi kód így nem törik el."""
    from superdl import media, hibaszoveg
    assert media.friendly_error is hibaszoveg.friendly_error


def test_a_segedfuggvenyek_is_elerhetok_a_media_alol():
    """A `media.py` több helyen használja őket (bot-újrapróba, süti-hiba)."""
    from superdl import media
    assert media._is_bot_check("Sign in to confirm you're not a bot")
    assert media._is_cookie_error("Could not copy Chrome cookie database")
    assert media._looks_offline("failed to establish a new connection")


def test_nincs_korkoros_fuggoseg():
    """A `hibaszoveg` NEM importálhatja a `media`-t: a yt-dlp behúzása lassú,
    és a kör visszahozná azt a törékenységet, ami miatt a refaktor készült.
    A `hibaszoveg` önmagában, a media betöltése nélkül is működik."""
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; from superdl import hibaszoveg; "
         "assert hibaszoveg.emberi('HTTP Error 403'); "
         "print('media' in ','.join(sys.modules))"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "False" in r.stdout, "a hibaszoveg behúzta a media modult"


def test_a_szovegek_valtozatlanul_atjottek():
    """A költöztetés célja NEM a szövegek átírása volt: a fordítás minősége
    évek munkája. Néhány jellegzetes mondatrész maradjon meg."""
    from superdl import hibaszoveg
    assert "KORHATÁROS" in hibaszoveg.emberi("confirm your age")
    assert "PRIVÁT" in hibaszoveg.emberi("This video is private")
    assert "régiózár" in hibaszoveg.emberi("not available in your country")
    assert "hotspot" in hibaszoveg.emberi("Sign in to confirm you're not a bot")
