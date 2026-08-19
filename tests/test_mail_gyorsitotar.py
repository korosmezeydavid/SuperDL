# -*- coding: utf-8 -*-
"""Super Mail – offline olvasás (helyi gyorsítótár).

„Vonaton, nyaralásban, kieső hálózatnál is működjön.” És ami a legfontosabb:
a mentett listába NEM kerülhet bele a fiók jelszava.
"""

import sys
import time
from email.message import EmailMessage

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import gyorsitotar as GY            # noqa: E402


def _lista():
    fiok = {"email": "en@sajat.hu", "jelszo": "SZUPERTITKOS", "imap_host": "x"}
    return [{"uid": "1", "felado": "Mari", "targy": "Szia", "olvasott": False,
             "_fiok": fiok, "_mappa": "INBOX"},
            {"uid": "2", "felado": "Béla", "targy": "Számla",
             "_fiok": fiok, "_mappa": "INBOX"}]


def test_lista_mentese_es_visszatoltese(tmp_path):
    GY.lista_ment("en@sajat.hu", "INBOX", _lista(), str(tmp_path))
    vissza, mikor = GY.lista_betolt("en@sajat.hu", "INBOX", str(tmp_path))
    assert len(vissza) == 2
    assert vissza[0]["targy"] == "Szia"
    assert time.time() - mikor < 5


def test_a_jelszo_SOHA_nem_kerul_a_gyorsitotarba(tmp_path):
    """A lista-elemekben ott a teljes fiók-adat, jelszóval együtt – ezt
    kiszűrjük, mert a gyorsítótár sima fájl."""
    GY.lista_ment("en@sajat.hu", "INBOX", _lista(), str(tmp_path))
    tartalom = ""
    for p in tmp_path.iterdir():
        tartalom += p.read_text(encoding="utf-8", errors="replace")
    assert "SZUPERTITKOS" not in tartalom
    assert "jelszo" not in tartalom
    assert "en@sajat.hu" in tartalom, "a fiók CÍME viszont kell a nézethez"


def test_hianyzo_mentes_eseten_ures(tmp_path):
    vissza, mikor = GY.lista_betolt("nincs@ilyen.hu", "INBOX", str(tmp_path))
    assert vissza == [] and mikor == 0.0


def test_serult_mentes_nem_szall_el(tmp_path):
    GY.lista_ment("en@sajat.hu", "INBOX", _lista(), str(tmp_path))
    for p in tmp_path.iterdir():
        p.write_text("{nem json", encoding="utf-8")
    assert GY.lista_betolt("en@sajat.hu", "INBOX", str(tmp_path)) == ([], 0.0)


def test_teljes_level_mentese_es_visszaolvasasa(tmp_path):
    m = EmailMessage()
    m["From"] = "mari@x.hu"
    m["Subject"] = "Szerződés"
    m.set_content("Kedves Dávid!")
    GY.level_ment("en@sajat.hu", "42", m, str(tmp_path))
    vissza = GY.level_betolt("en@sajat.hu", "42", str(tmp_path))
    assert vissza is not None
    assert "Kedves Dávid" in vissza.get_content()
    assert GY.level_betolt("en@sajat.hu", "99", str(tmp_path)) is None


def test_kulon_fiokok_nem_keverednek(tmp_path):
    m = EmailMessage()
    m["Subject"] = "A"
    m.set_content("egy")
    GY.level_ment("egyik@sajat.hu", "1", m, str(tmp_path))
    assert GY.level_betolt("masik@sajat.hu", "1", str(tmp_path)) is None


def test_uritas_es_meret(tmp_path):
    GY.lista_ment("en@sajat.hu", "INBOX", _lista(), str(tmp_path))
    assert GY.meret(str(tmp_path)) > 0
    assert GY.urit(str(tmp_path)) >= 1
    assert GY.meret(str(tmp_path)) == 0


@pytest.mark.parametrize("tel,resz", [
    (10, "az imént"), (300, "5 perce"), (7200, "2 órája"),
    (3 * 86400, "3 napja")])
def test_kor_szovege(tel, resz):
    most = time.time()
    assert resz in GY.kor_szoveg(most - tel, most)


def test_ismeretlen_ido():
    assert "ismeretlen" in GY.kor_szoveg(0)
