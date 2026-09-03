# -*- coding: utf-8 -*-
"""MK8 és MK10 – kilépés-kockázat, seed-mondat, előzmények, rendezés."""

import time

from superdl import elozmenyek, lemezhely, rendezes, report, retrypolicy


class _P:
    def __init__(self, status="letöltés", **kw):
        self.status = status
        self.error = ""
        self.conflict = False
        self.filename = kw.get("filename", "")
        self.belso_probak = kw.get("belso_probak", 0)


class _J:
    def __init__(self, p, url="http://p/x"):
        self.progress = p
        self.url = url


# ---- MK8: a belső újrapróba KÜLÖN lépték ------------------------------

def test_a_belso_szunet_MASODPERCES_nem_perces():
    """⚠️ A perces job-szintű politikát ráhúzni a szegmensekre a letöltést a
    töredékére lassítaná: ott EGY szegmens akad meg nyolcból, míg a másik hét
    dolgozik. Két különböző fogalom, két különböző lépték."""
    assert retrypolicy.belso_szunet(0) < 5
    assert max(retrypolicy.BELSO_SZUNETEK) < min(retrypolicy.SZUNETEK)


def test_a_belso_szunet_no_majd_beall():
    a = [retrypolicy.belso_szunet(i) for i in range(8)]
    assert a[0] < a[1] < a[2]
    assert a[-1] == retrypolicy.BELSO_SZUNETEK[-1]


def test_a_kuzd_uzenet_megnyugtat():
    """A lassú és az akadozó közt vakon nincs különbség – de a válasz más:
    az egyikre várni kell, a másikra nem. Ezt ki kell mondani."""
    sz = retrypolicy.kuzd_uzenet(3)
    assert "akadozik" in sz
    assert "Nem kell tenned semmit" in sz


# ---- MK8: seed-mondat -------------------------------------------------

def test_seed_mondat_kimondja_a_feltoltott_mennyiseget():
    sz = report.seed_mondat("film.mkv", 500 * 1024 ** 2, 0.5, 3, 1024 * 200)
    assert "film.mkv" in sz
    assert "megabájt" in sz
    assert "3 társ" in sz


def test_seed_mondat_a_nema_seedelest_KIMONDJA():
    """A néma seedelés úgy néz ki, mintha elakadt volna – pedig nem hiba."""
    sz = report.seed_mondat("film.mkv", 1024, 0.0, 0, 0.0)
    assert "senki nem tölti tőled" in sz
    assert "nem hiba" in sz


def test_seed_mondat_nincs_benne_tizedespont():
    """Ugyanaz a csapda, mint az MK5-ben: a felolvasó a tizedespontot
    mondatvégi pontnak mondja."""
    sz = report.seed_mondat("f", 5.3 * 1024 ** 2, 1.5, 2, 0)
    assert "5.3" not in sz and "1.5" not in sz
    assert "1,5-szerese" in sz


# ---- MK8: hely-ellenőrzés a méret nélküli motorokra --------------------

def test_indulas_elott_ismeretlen_meretnel_is_szol(monkeypatch):
    """A yt-dlp és a torrent indulás előtt NEM ismeri a méretet – eddig ott
    semmilyen ellenőrzés nem futott, pedig ezek töltik meg a lemezt."""
    monkeypatch.setattr(lemezhely, "BEKAPCSOLVA", True)
    monkeypatch.setattr(lemezhely, "szabad", lambda ut: 100 * 1024 ** 2)
    sz = lemezhely.indulas_elott("C:/x")
    assert "Kevés a hely" in sz


def test_indulas_elott_hallgat_ha_van_hely(monkeypatch):
    monkeypatch.setattr(lemezhely, "BEKAPCSOLVA", True)
    monkeypatch.setattr(lemezhely, "szabad", lambda ut: 500 * 1024 ** 3)
    assert lemezhely.indulas_elott("C:/x") == ""


def test_indulas_elott_ismert_meretnel_a_pontos_ellenorzest_adja(monkeypatch):
    monkeypatch.setattr(lemezhely, "BEKAPCSOLVA", True)
    monkeypatch.setattr(lemezhely, "szabad", lambda ut: 1024 ** 3)
    sz = lemezhely.indulas_elott("C:/x", 5 * 1024 ** 3, "film.mkv")
    assert "Nincs elég hely" in sz and "film.mkv" in sz


# ---- MK10: előzmények -------------------------------------------------

def test_rogzit_es_keres():
    lista = elozmenyek.rogzit("http://a/1", "film.mkv", 100, "C:/le",
                              tetelek=[])
    assert elozmenyek.keres("film", lista)
    assert elozmenyek.keres("a/1", lista)
    assert not elozmenyek.keres("nincsilyen", lista)


def test_ures_keresore_MINDENT_ad():
    """A „mi van az előzményben" ugyanolyan jogos kérdés, mint a célzott."""
    lista = elozmenyek.rogzit("http://a/1", "x", 1, "C:/le", tetelek=[])
    assert len(elozmenyek.keres("", lista)) == 1


def test_ugyanaz_az_url_nem_duplikalodik():
    """Az előzmény arra válaszol, MIKOR töltöttem le utoljára – nem arra,
    hogy hányszor."""
    lista = elozmenyek.rogzit("http://a/1", "regi", 1, "C:/le", tetelek=[])
    lista = elozmenyek.rogzit("http://a/1", "uj", 2, "C:/le", tetelek=lista)
    assert len(lista) == 1
    assert lista[0]["nev"] == "uj"


def test_a_legfrissebb_van_elol():
    lista = elozmenyek.rogzit("http://a/1", "elso", 1, "C:/le", tetelek=[])
    lista = elozmenyek.rogzit("http://a/2", "masodik", 1, "C:/le",
                              tetelek=lista)
    assert lista[0]["nev"] == "masodik"


def test_takarit_a_regieket_dobja():
    regi = [{"url": "http://a", "mikor": time.time() - 400 * 86400}]
    uj = [{"url": "http://b", "mikor": time.time()}]
    maradt = elozmenyek.takarit(regi + uj, most=time.time())
    assert len(maradt) == 1 and maradt[0]["url"] == "http://b"


def test_mar_letoltve_CSAK_ha_a_fajl_is_megvan(tmp_path):
    """Ha a felhasználó azóta kitörölte, nincs mit duplikálni – és egy kérdés
    arról, hogy „ezt már letöltötted", miközben a fájl sehol, bosszantó."""
    f = tmp_path / "van.bin"
    f.write_bytes(b"x")
    lista = [{"url": "http://a/1", "nev": "van.bin", "mappa": str(tmp_path),
              "mikor": time.time(), "meret": 1},
             {"url": "http://a/2", "nev": "nincs.bin", "mappa": str(tmp_path),
              "mikor": time.time(), "meret": 1}]
    assert elozmenyek.mar_letoltve("http://a/1", lista) is not None
    assert elozmenyek.mar_letoltve("http://a/2", lista) is None


def test_mar_letoltve_ismeretlen_url():
    assert elozmenyek.mar_letoltve("http://nincs", []) is None
    assert elozmenyek.mar_letoltve("", []) is None


def test_a_duplikatum_kerdes_kimondja_a_mikort_es_a_hovat():
    t = {"url": "http://a/1", "nev": "film.mkv", "mappa": "C:/le",
         "meret": 3 * 1024 ** 3, "mikor": time.time()}
    sz = elozmenyek.duplikatum_kerdes(t)
    assert "film.mkv" in sz and "C:/le" in sz
    assert "gigabájt" in sz


# ---- MK10: rendezés ---------------------------------------------------

def test_csoportok():
    assert rendezes.csoport("a.mkv") == "Videók"
    assert rendezes.csoport("a.MP3") == "Zene"
    assert rendezes.csoport("a.pdf") == "Dokumentumok"
    assert rendezes.csoport("a.zip") == "Csomagok"
    assert rendezes.csoport("a.valami") == rendezes.EGYEB
    assert rendezes.csoport("kiterjesztes_nelkul") == rendezes.EGYEB


def test_rendez_athelyez(tmp_path):
    f = tmp_path / "film.mkv"
    f.write_bytes(b"x")
    uj, hiba = rendezes.rendez(f, tmp_path)
    assert not hiba
    assert (tmp_path / "Videók" / "film.mkv").is_file()
    assert not f.exists()
    assert uj.endswith("film.mkv")


def test_rendez_SOHA_nem_ir_felul(tmp_path):
    """Egy meglévő fájl csendben felülírása sokkal rosszabb volna, mint egy
    rendezetlenül maradt letöltés."""
    (tmp_path / "Videók").mkdir()
    (tmp_path / "Videók" / "film.mkv").write_bytes(b"REGI")
    f = tmp_path / "film.mkv"
    f.write_bytes(b"UJ")
    uj, hiba = rendezes.rendez(f, tmp_path)
    assert uj == "" and hiba
    assert (tmp_path / "Videók" / "film.mkv").read_bytes() == b"REGI"
    assert f.is_file(), "az eredeti a helyén marad"


def test_a_mar_almappaban_levot_bekeen_hagyjuk(tmp_path):
    """Lehet, hogy a felhasználó vagy egy lejátszási lista tette oda."""
    al = tmp_path / "sajat"
    al.mkdir()
    f = al / "film.mkv"
    f.write_bytes(b"x")
    assert rendezes.celut(f, tmp_path) is None


def test_rendez_mondat_kimondja_a_mappat():
    """Ha nem tudja, hova került, a rendezés rosszabb, mint a rendetlenség."""
    sz = rendezes.rendez_mondat("film.mkv", "Videók")
    assert "film.mkv" in sz and "Videók" in sz


# ---- MK9: időzített sebességkorlát ------------------------------------

def _ido(ora, perc=0):
    """Unix időbélyeg a HELYI idő szerinti órára (a modul localtime-ot néz)."""
    t = list(time.localtime())
    t[3], t[4], t[5] = ora, perc, 0
    return time.mktime(time.struct_time(tuple(t)))


def test_egyszeru_sav():
    from superdl import savszelesseg as sav
    rend = "08:00-20:00=500K"
    assert sav.korlat_most(rend, _ido(12)) == "500K"
    assert sav.korlat_most(rend, _ido(23)) is None


def test_EJFELEN_ATNYULO_sav():
    """⚠️ EZ A LEGFONTOSABB. A „22:00-06:00" nem üres tartomány, hanem az
    ÉJSZAKA – épp az, amit a felhasználó be akar állítani. Naiv
    `kezd <= x < veg` feltétellel a legfontosabb szabály SOSEM sülne el."""
    from superdl import savszelesseg as sav
    rend = "22:00-06:00=0"
    assert sav.korlat_most(rend, _ido(23)) == "0"
    assert sav.korlat_most(rend, _ido(2)) == "0"
    assert sav.korlat_most(rend, _ido(12)) is None


def test_tobb_szabaly_az_elso_nyer():
    from superdl import savszelesseg as sav
    rend = "00:00-23:59=1M; 08:00-20:00=500K"
    assert sav.korlat_most(rend, _ido(12)) == "1M"


def test_a_hibas_sor_csendben_kimarad():
    """Egy elgépelt szabály miatt nem állhat meg a letöltés."""
    from superdl import savszelesseg as sav
    rend = "ez hulyeseg; 08:00-20:00=500K"
    assert sav.korlat_most(rend, _ido(12)) == "500K"
    assert sav.korlat_most("csak hulyeseg", _ido(12)) is None


def test_ures_rend():
    from superdl import savszelesseg as sav
    assert sav.korlat_most("", _ido(12)) is None
    assert sav.korlat_most(None, _ido(12)) is None


def test_a_nulla_korlatlant_jelent():
    """Ugyanaz a jelentés, mint a beállítás üres mezőjében – ne legyen
    kétféle nyelv ugyanarra."""
    from superdl import savszelesseg as sav
    assert sav.emberi("0") == "korlátlan"
    assert sav.emberi("") == "korlátlan"
    assert sav.emberi("500K") == "500K"


def test_a_valtast_kimondjuk():
    """A hirtelen lelassuló letöltés magától nem érthető – a felhasználó azt
    hinné, elromlott valami."""
    from superdl import savszelesseg as sav
    assert "átváltott" in sav.valtas_mondat("500K")
