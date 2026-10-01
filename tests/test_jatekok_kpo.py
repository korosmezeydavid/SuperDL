# -*- coding: utf-8 -*-
"""Kő-papír-olló / Répa-nyuszi-pisztoly – a mag tesztjei (wx és hálózat nélkül).

A két változat szabálya, a mondatok és hangok megléte, a ravasz gép, a meccs,
és a TELJES online protokoll két klienssel, egy memóriabeli „szobán" át –
csalással, foglalt szobával, visszavágóval. A lenyomat (hash) tesztvektora
UGYANAZ, mint a telefonos KpoGameTest-ben: a két program így biztosan érti
egymást.
"""
import os
import random

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
K = pytest.importorskip(BASE + ".kpo")
NR = pytest.importorskip(BASE + ".netroom")

MAPPA = os.path.join(os.path.dirname(K.__file__), "kpo_hang")


# ------------------------------------------------------------ szabályok, adatok

def test_ket_valtozat_harom_elemmel():
    v = K.valtozatok()
    assert set(v) == {"kpo", "rnp"}
    assert v["kpo"].elemek == ["ko", "papir", "ollo"]
    assert v["rnp"].elemek == ["repa", "nyuszi", "pisztoly"]


@pytest.mark.parametrize("valt,gyoztes,vesztes", [
    ("kpo", "papir", "ko"), ("kpo", "ollo", "papir"), ("kpo", "ko", "ollo"),
    ("rnp", "nyuszi", "repa"), ("rnp", "pisztoly", "nyuszi"), ("rnp", "repa", "pisztoly"),
])
def test_ki_kit_ut(valt, gyoztes, vesztes):
    v = K.valtozat(valt)
    assert K.eredmeny(v.index(gyoztes), v.index(vesztes)) == 1
    assert K.eredmeny(v.index(vesztes), v.index(gyoztes)) == -1
    assert v.kit_ut(gyoztes) == vesztes
    e, mondat, hang = K.kor_leiras(v, gyoztes, vesztes)
    assert e == 1 and mondat and hang
    e2, mondat2, hang2 = K.kor_leiras(v, vesztes, gyoztes)
    assert e2 == -1 and mondat2 == mondat and hang2 == hang


def test_david_szabalya_szoveggel():
    v = K.valtozat("rnp")
    assert "megeszi" in K.kor_leiras(v, "nyuszi", "repa")[1]
    assert "lelövi" in K.kor_leiras(v, "pisztoly", "nyuszi")[1]
    assert "csövét" in K.kor_leiras(v, "repa", "pisztoly")[1]


def test_dontetlen_minden_elemre_van_mondat():
    for v in K.valtozatok().values():
        for el in v.elemek:
            e, mondat, hang = K.kor_leiras(v, el, el)
            assert e == 0 and mondat and hang == "kpo_dontetlen"


def test_minden_hivatkozott_hang_megvan():
    nevek = {"kpo_dontetlen", "kpo_visszaszamlalas", "kpo_kor_nyer", "kpo_kor_veszit",
             "kpo_meccs_nyer", "kpo_meccs_veszit", "kpo_ellenfel_kesz", "kpo_belepett",
             "kpo_valasztas"}
    for v in K.valtozatok().values():
        nevek |= set(v.hang.values())
    for n in nevek:
        assert os.path.isfile(os.path.join(MAPPA, n + ".wav")), n
    assert os.path.isfile(os.path.join(MAPPA, "FORRAS.txt"))


def test_beszolasok_kitoltve():
    rng = random.Random(1)
    for fajta in ("nyersz", "vesztesz", "dontetlen", "meccs_nyersz", "meccs_vesztesz"):
        s = K.beszolas(fajta, rng, gep="Robi")
        assert s and "{" not in s
    for fajta in ("online_nyersz", "online_vesztesz", "online_dontetlen",
                  "online_meccs_nyersz", "online_meccs_vesztesz"):
        s = K.beszolas(fajta, rng, ellenfel="Józsi")
        assert s and "{" not in s


# ------------------------------------------------------------ meccs, gép

@pytest.mark.parametrize("kor_db,cel", [(1, 1), (3, 2), (5, 3), (7, 4)])
def test_meccs_celja(kor_db, cel):
    m = K.Meccs(kor_db)
    assert m.cel == cel
    for _ in range(cel - 1):
        m.rogzit(1)
    m.rogzit(0)                         # a döntetlen nem számít
    assert not m.vege
    m.rogzit(1)
    assert m.vege and m.nyertel


def test_ravasz_gep_kiismeri_a_megszokast():
    """Aki mindig követ mutat, azt a ravasz gép többnyire megveri."""
    g = K.RavaszGep(random.Random(7))
    nyert = 0
    for _ in range(200):
        gi = g.valaszt()
        if K.eredmeny(gi, 0) == 1:
            nyert += 1
        g.megfigyel(0)
    assert nyert > 120


def test_ravasz_gep_a_korforgast_is():
    """Kő → papír → olló körforgást is megtanul (átmenetek alapján)."""
    g = K.RavaszGep(random.Random(3))
    nyert = 0
    for i in range(300):
        te = i % 3
        if K.eredmeny(g.valaszt(), te) == 1:
            nyert += 1
        g.megfigyel(te)
    assert nyert > 170


def test_szerencses_gep_minden_elemet_valaszt():
    g = K.SzerencsesGep(random.Random(2))
    assert {g.valaszt() for _ in range(100)} == {0, 1, 2}


# ------------------------------------------------------------ online protokoll

def test_lenyomat_tesztvektor_azonos_a_telefonnal():
    assert K.hash_tipp(3, "nyuszi", "a1b2c3d4e5f60708") == \
        "3f1c5532152925042e2fe3a6d7ad96ac8f8d1881f9287a7eeffc646f30a5c609"


class Busz:
    """Memóriabeli Ably-szoba: mindenki minden üzenetet megkap (a sajátját is)."""

    def __init__(self):
        self.tagok = []
        self.sor = []

    def kuldo(self, nev):
        return lambda tipus, adat: self.sor.append({"tipus": tipus, "ki": nev, "adat": adat})

    def kezbesit(self):
        esemenyek = {id(t): [] for t in self.tagok}
        while self.sor:
            u = self.sor.pop(0)
            for t in self.tagok:
                esemenyek[id(t)] += t.fogad(u)
        return esemenyek


def _par(valt="rnp", kor_db=3):
    b = Busz()
    host = K.OnlineJatek("Dávid", True, b.kuldo("Dávid"), valtozat_kulcs=valt,
                         kor_db=kor_db, rng=random.Random(1))
    vendeg = K.OnlineJatek("Józsi", False, b.kuldo("Józsi"), rng=random.Random(2))
    b.tagok = [host, vendeg]
    vendeg.belep()
    ev = b.kezbesit()
    assert ("belepett", "Józsi") in ev[id(host)]
    assert host.inditas()
    ev = b.kezbesit()
    assert ev[id(vendeg)] == [("start", "Dávid", valt, kor_db)]
    assert vendeg.valt.kulcs == valt and vendeg.kor_db == kor_db
    return b, host, vendeg


def test_teljes_online_meccs():
    b, host, vendeg = _par("rnp", 3)
    # 1. kör: a host nyuszi, a vendég répa → a host nyer
    host.valaszt("nyuszi")
    ev = b.kezbesit()
    assert ("ellen_kesz", "Dávid") in ev[id(vendeg)]
    vendeg.valaszt("repa")
    ev = b.kezbesit()
    kh = [e for e in ev[id(host)] if e[0] == "kor"]
    kv = [e for e in ev[id(vendeg)] if e[0] == "kor"]
    assert kh and kh[0][1] == 1 and kh[0][2:4] == ("nyuszi", "repa")
    assert kv and kv[0][1] == -1 and kv[0][2:4] == ("repa", "nyuszi")
    assert "megeszi" in kh[0][4]
    # 2. kör: döntetlen, 3. kör: a host nyer → vége (2 nyert kör)
    for h, v in (("pisztoly", "pisztoly"), ("repa", "pisztoly")):
        vendeg.valaszt(v)
        host.valaszt(h)
        ev = b.kezbesit()
    assert host.fazis == vendeg.fazis == "vege"
    assert ("meccs_vege", True) in ev[id(host)]
    assert ("meccs_vege", False) in ev[id(vendeg)]
    assert (host.meccs.te, host.meccs.ellen) == (2, 0)
    assert (vendeg.meccs.te, vendeg.meccs.ellen) == (0, 2)


def test_ketszer_nem_valaszthatsz_egy_korben():
    b, host, vendeg = _par()
    host.valaszt("repa")
    host.valaszt("nyuszi")
    b.kezbesit()
    assert host.sajat[0] == "repa"


def test_lenyomat_elott_nem_latszik_a_valasztas():
    b, host, vendeg = _par()
    host.valaszt("pisztoly")
    tippek = [u for u in b.sor if u["tipus"] == "tipp"]
    assert tippek and "pisztoly" not in str(tippek)
    assert not [u for u in b.sor if u["tipus"] == "felfed"]


def test_csalas_eszrevetele():
    b, host, vendeg = _par()
    host.valaszt("repa")
    b.kezbesit()
    vendeg.valaszt("nyuszi")
    # a vendég felfedését meghamisítjuk: mást mond, mint amire a lenyomat szólt
    for u in b.sor:
        if u["tipus"] == "felfed" and u["ki"] == "Józsi":
            u["adat"]["valasztas"] = "pisztoly"
    ev = b.kezbesit()
    assert ("csalas", "Józsi") in ev[id(host)]
    assert host.meccs.korok == 0


def test_foglalt_szoba():
    b, host, vendeg = _par()
    harmadik = K.OnlineJatek("Laci", False, b.kuldo("Laci"))
    b.tagok.append(harmadik)
    harmadik.belep()
    ev = b.kezbesit()
    assert ("tele",) in ev[id(harmadik)]
    assert host.ellen_nev == "Józsi"


def test_visszavago_a_vendeg_keresere():
    b, host, vendeg = _par("kpo", 1)
    host.valaszt("papir")
    vendeg.valaszt("ko")
    b.kezbesit()
    assert host.fazis == "vege"
    vendeg.visszavago()
    ev = b.kezbesit()
    assert ("start", "Dávid", "kpo", 1) in ev[id(vendeg)]
    assert host.fazis == vendeg.fazis == "jatek"
    assert host.meccs.korok == 0


def test_kilepes():
    b, host, vendeg = _par()
    vendeg.kilep()
    ev = b.kezbesit()
    assert ("kilepett", "Józsi") in ev[id(host)]
    assert host.ellen_pid == ""


def test_csevej_meccs_elott_is():
    b = Busz()
    host = K.OnlineJatek("Dávid", True, b.kuldo("Dávid"))
    vendeg = K.OnlineJatek("Józsi", False, b.kuldo("Józsi"))
    b.tagok = [host, vendeg]
    host.csevej("Szia, jössz?")
    ev = b.kezbesit()
    assert ev[id(vendeg)] == [("csevej", "Dávid", "Szia, jössz?")]
    assert ev[id(host)] == []


def test_netszoba_elotag():
    sz = NR.NetSzoba("abcde", "n", kulcs="a.b:c", elotag="kpo")
    assert sz._chan == "kpo:ABCDE"
    assert NR.NetSzoba("abcde", "n", kulcs="a.b:c")._chan == "szerencsekerek:ABCDE"
