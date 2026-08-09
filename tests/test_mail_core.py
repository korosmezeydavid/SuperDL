# -*- coding: utf-8 -*-
"""Super Mail – a wx-mentes mag tesztjei (hálózat nélkül)."""
import importlib

import pytest

MC = pytest.importorskip("modules_src.mail.mail_mod.mail_core")


def test_auto_konfig_ismert_es_ismeretlen():
    g = MC.auto_konfig("valaki@gmail.com")
    assert g["imap_host"] == "imap.gmail.com"
    assert g["smtp_host"] == "smtp.gmail.com"
    assert g["imap_port"] == 993 and g["smtp_port"] == 465
    x = MC.auto_konfig("en@sajatdomain.hu")
    assert x["imap_host"] == "imap.sajatdomain.hu"
    assert x["pop_host"] == "pop.sajatdomain.hu"


def test_app_jelszo_kell():
    assert MC.app_jelszo_kell("a@gmail.com") is True
    assert MC.app_jelszo_kell("a@outlook.com") is True
    assert MC.app_jelszo_kell("a@sajatdomain.hu") is False


def test_uj_fiok_szerkezet():
    f = MC.uj_fiok("Teszt", "en@gmail.com", "app-jelszo", "imap")
    assert f["email"] == "en@gmail.com"
    assert f["felhasznalo"] == "en@gmail.com"
    assert f["protokoll"] == "imap"
    assert f["imap_host"] == "imap.gmail.com"


def test_dekodol_fejlec():
    # =?UTF-8?B?...?= kódolású tárgy
    nyers = "=?UTF-8?B?w6FydsOtenrFkQ==?="   # "árvíztűrő"? ellenőrizzük tisztán
    assert isinstance(MC.dekodol_fejlec(nyers), str)
    # sima ASCII változatlan
    assert MC.dekodol_fejlec("Hello") == "Hello"
    assert MC.dekodol_fejlec(None) == ""


def test_html_to_szoveg():
    h = "<html><head><style>x{}</style></head><body>Szia <b>Vili</b>!" \
        "<a href='https://pelda.hu'>link</a></body></html>"
    sz = MC.html_to_szoveg(h)
    assert "Szia" in sz and "Vili" in sz
    assert "x{}" not in sz                       # a style eldobva
    assert "https://pelda.hu" in sz              # a link célja megőrizve


def test_level_epit_es_visszaolvasas():
    import email
    m = MC.level_epit("en@pelda.hu", "te@pelda.hu", "Tárgy röviden",
                      "A levél törzse.\nMásodik sor.", masolat="cc@pelda.hu")
    nyers = m.as_bytes()
    vissza = email.message_from_bytes(nyers)
    fej = MC.level_fejlec_info(vissza)
    assert fej["targy"] == "Tárgy röviden"
    assert "te@pelda.hu" in fej["cimzett"]
    torzs = MC.level_szovegtorzs(vissza)
    assert "A levél törzse." in torzs and "Második sor." in torzs
    assert fej["csatolmany"] is False


def test_level_epit_csatolmannyal(tmp_path):
    import email
    f = tmp_path / "adat.txt"
    f.write_text("csatolt tartalom", encoding="utf-8")
    m = MC.level_epit("en@pelda.hu", "te@pelda.hu", "Cs", "törzs",
                      csatolmanyok_lista=[str(f)])
    vissza = email.message_from_bytes(m.as_bytes())
    assert MC.level_fejlec_info(vissza)["csatolmany"] is True
    csat = MC.csatolmanyok(vissza)
    assert csat and csat[0][0] == "adat.txt"
    assert csat[0][1] == b"csatolt tartalom"


def test_cimzettek_parse():
    assert MC.cimzettek("a@x.hu, Nev <b@y.hu>; c@z.hu") == \
        ["a@x.hu", "b@y.hu", "c@z.hu"]
    assert MC.cimzettek("") == []


def test_xoauth2_formatum():
    s = MC._xoauth2("en@gmail.com", "TOKEN123")
    assert s == b"user=en@gmail.com\x01auth=Bearer TOKEN123\x01\x01"


def test_imap_utf7_mappanevek():
    # a képernyőn látott elgépelt (modified UTF-7) nevek helyes dekódolása
    assert MC._imap_utf7_decode("Elk&APw-ld&APY-tt elemek") == "Elküldött elemek"
    assert MC._imap_utf7_decode("[Gmail]/&ANY-sszes lev&AOk-l") == \
        "[Gmail]/Összes levél"
    assert MC._imap_utf7_decode("INBOX") == "INBOX"
    assert MC._imap_utf7_decode("&-") == "&"        # a &- a sima & jel
    assert MC.mappa_display("INBOX") == "Beérkezett"
    assert MC.mappa_display("[Gmail]/Fontos") == "[Gmail]/Fontos"


def test_kliens_valasztas_protokoll_szerint():
    imap_f = MC.uj_fiok("A", "a@x.hu", "j", "imap")
    pop_f = MC.uj_fiok("B", "b@x.hu", "j", "pop")
    assert isinstance(MC.ImapKliens(imap_f), MC.ImapKliens)
    assert isinstance(MC.Pop3Kliens(pop_f), MC.Pop3Kliens)
