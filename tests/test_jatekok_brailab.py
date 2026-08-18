"""BraiLab PC hang a retró játékokban (Ujfalusi Zoltán jóvoltából).

Amit ŐRZÜNK ezekkel a tesztekkel:
  • a motor SZŰK fokozat-tartományait sosem lépjük túl (a DLL különben csak
    hibakódot ad, és marad a régi fokozat: a felhasználó azt hinné, nem működik);
  • a hossz-BECSLÉS soha ne legyen rövidebb a valóságosnál – ha rövid, a
    következő mondat belebeszél az előzőbe, ami vakon használhatatlan;
  • a 32 bites host esetleges hiánya/összeomlása NEM némítja el a játékot;
  • a hanglistában a BraiLab kulcsa NEM ütközik a Core saját „brailab”
    retró karakterével.
"""

import sys
import types

import pytest

sys.path.insert(0, "modules_src/jatekok")
from jatekok_mod import brailab as BL            # noqa: E402


# ------------------------------------------------------- fokozat-tartomány

def test_a_tartomanyon_kivuli_fokozat_a_legkozelebbire_szorul():
    assert BL.hatarol(99, BL.TEMPOK, 4) == 5
    assert BL.hatarol(-7, BL.TEMPOK, 4) == 0
    assert BL.hatarol(5, BL.MAGASSAGOK, 0) == 1
    assert BL.hatarol(-5, BL.HANGEROK, 0) == -1


def test_az_ertelmezhetetlen_fokozat_az_alapra_esik():
    assert BL.hatarol(None, BL.TEMPOK, 4) == 4
    assert BL.hatarol("gyors", BL.TEMPOK, 4) == 4


def test_a_motor_csak_ervenyes_fokozatot_kap():
    m = BL.BrailabMotor()
    m.beallit(magassag=9, tempo=-3, hangero=42)
    assert m.magassag in BL.MAGASSAGOK
    assert m.tempo in BL.TEMPOK
    assert m.hangero in BL.HANGEROK


# ------------------------------------------------------------- hosszbecslés

def test_a_becsult_hossz_hosszabb_szovegre_nagyobb():
    rovid = BL.becsult_hossz("Négyszáz.", 4)
    hosszu = BL.becsult_hossz("Üdvözöllek a Super D L retró játékok menüjében!", 4)
    assert hosszu > rovid > 0


def test_a_lassabb_tempo_hosszabb_beszed():
    szoveg = "Egy közepesen hosszú magyar mondat a méréshez."
    assert BL.becsult_hossz(szoveg, 0) > BL.becsult_hossz(szoveg, 5)


def test_a_becsles_nem_rovidebb_a_meresnel():
    # élő mérés a fejlesztői gépen: 47 karakter, tempónként 4,0–6,6 mp
    szoveg = "x" * 47
    for tempo in BL.TEMPOK:
        assert BL.becsult_hossz(szoveg, tempo) >= 4.0, tempo


def test_ismeretlen_tempora_is_ad_becslest():
    assert BL.becsult_hossz("szia", 77) > 0


# ------------------------------------------------- hiányzó/rossz host esetén

def test_hianyzo_keszlet_eseten_nem_szolal_meg_de_nem_is_szall_el(monkeypatch):
    monkeypatch.setattr(BL, "elerheto", lambda: False)
    m = BL.BrailabMotor()
    assert m.indit() is False
    assert m.mond("Sziasztok") == 0.0
    assert m.hiba                     # a hibát MEGMONDJUK, nem nyeljük el
    m.stop()                          # ne dobjon akkor sem, ha nincs host
    m.leallit()


def test_a_host_indulasi_hibaja_a_valaszban_jon_vissza(monkeypatch):
    monkeypatch.setattr(BL, "elerheto", lambda: True)

    class HamisFolyamat:
        def __init__(self):
            self.stdin = types.SimpleNamespace(write=lambda s: None,
                                               flush=lambda: None)
            self.stdout = types.SimpleNamespace(
                readline=lambda: "ERR init -24\n")

        def poll(self):
            return None

        def wait(self, t=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(BL.subprocess, "Popen",
                        lambda *a, **k: HamisFolyamat())
    m = BL.BrailabMotor()
    assert m.indit() is False
    assert "-24" in m.hiba


def test_a_menet_kozben_elszallo_host_egyszer_ujraindul(monkeypatch):
    monkeypatch.setattr(BL, "elerheto", lambda: True)
    indulasok = []

    class HamisFolyamat:
        def __init__(self, sorok):
            self.sorok = list(sorok)
            self.elo = True
            self.kapott = []
            self.stdin = types.SimpleNamespace(
                write=self.kapott.append, flush=lambda: None)
            self.stdout = types.SimpleNamespace(readline=self._olvas)

        def _olvas(self):
            return (self.sorok.pop(0) + "\n") if self.sorok else ""

        def poll(self):
            return None if self.elo else 0

        def wait(self, t=None):
            self.elo = False
            return 0

        def kill(self):
            self.elo = False

    def gyar(*a, **k):
        # az ELSŐ host READY-t ad, de a SPEAK-re üresen elhal;
        # a MÁSODIK rendben kimondja
        # sorrend: READY, majd a három fokozat-válasz, végül a SPEAK válasza
        p = HamisFolyamat(["READY", "OK", "OK", "OK", "OK"] if indulasok
                          else ["READY", "OK", "OK", "OK", ""])
        indulasok.append(p)
        return p

    monkeypatch.setattr(BL.subprocess, "Popen", gyar)
    m = BL.BrailabMotor()
    hossz = m.mond("Sziasztok!")
    assert len(indulasok) == 2, "elszállás után ÚJRA kell indítani a hostot"
    assert hossz > 0, "az újraindítás után meg KELL szólalnia"


def test_az_ujsort_nem_kuldjuk_a_sor_alapu_protokollba(monkeypatch):
    monkeypatch.setattr(BL, "elerheto", lambda: True)
    kapott = []

    class HamisFolyamat:
        def __init__(self):
            self.stdin = types.SimpleNamespace(write=kapott.append,
                                               flush=lambda: None)
            self.stdout = types.SimpleNamespace(readline=self._olvas)
            self.valaszok = ["READY", "OK", "OK", "OK", "OK"]

        def _olvas(self):
            return (self.valaszok.pop(0) + "\n") if self.valaszok else ""

        def poll(self):
            return None

        def wait(self, t=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(BL.subprocess, "Popen", lambda *a, **k: HamisFolyamat())
    m = BL.BrailabMotor()
    m.mond("Első sor\nmásodik sor")
    beszed = [s for s in kapott if s.startswith("SPEAK ")]
    assert beszed, "el kell hangoznia"
    assert beszed[0] == "SPEAK Első sor második sor\n"


# ------------------------------------------------------------ kulcs-ütközés

def test_a_brailab_kulcs_nem_utkozik_a_core_retro_gepeivel():
    from superdl import retrospeech as RS
    assert BL.KULCS not in [g.kulcs for g in RS.GEPEK], \
        "a Core-ban MÁR VAN „brailab” karakter (saját újraalkotás)"


def test_a_motor_egyetlen_peldany():
    assert BL.motor() is BL.motor()


# ------------------------------------------- a játék-konzol beszéd-útvonala

def test_a_konzol_a_brailabot_hasznalja_ha_azt_valasztottak(monkeypatch):
    """A BraiLab-nál NEM WAV-ot szintetizálunk (RS.synth), hanem a motor szól."""
    pytest.importorskip("wx")
    from jatekok_mod import jatekkonzol as JK

    hivasok = []

    class HamisMotor:
        def mond(self, szoveg):
            hivasok.append(szoveg)
            return 0.1          # rövid becsült hossz, hogy pörögjön a teszt

        def stop(self):
            hivasok.append("STOP")

    monkeypatch.setattr(JK.brailab, "motor", lambda: HamisMotor())
    monkeypatch.setattr(JK.RS, "synth",
                        lambda *a, **k: pytest.fail(
                            "BraiLab-nál nem szabad WAV-ot szintetizálni"))

    h = JK.RetroHang(lambda: (JK.brailab.KULCS, 1.0))
    h.mond("Sziasztok!")
    for _ in range(100):
        if hivasok:
            break
        __import__("time").sleep(0.05)
    h.leallit()
    assert hivasok and hivasok[0] == "Sziasztok!"
