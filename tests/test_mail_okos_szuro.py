"""Dávid (2026-09-28): OKOS SZŰRŐ – „ismerje föl a levelet, hogy vannak-e
benne hivatkozások, pl. hírlevelek, és azt HTML-ben mutassa. De kikapcsolható
legyen." A hétköznapi és a levelezőlistás levél marad egyszerű."""
import ast
import sys
from email.message import EmailMessage
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GYOKER / "modules_src" / "mail"))

import pytest                            # noqa: E402
from mail_mod import mail_core as MC     # noqa: E402

# A Super Mail forrása külön munkában van (a tárolóban még az 1.5.x):
# ott, ahol az új függvények nincsenek meg (CI), a teszt kimarad.
if not hasattr(MC, "okos_html_kell"):
    pytest.skip("Super Mail 1.6.1 forrása nincs ebben a tárolóban",
                allow_module_level=True)


def _level(html=True, fejlec=None):
    m = EmailMessage()
    m["From"] = "a@b.hu"
    m["Subject"] = "x"
    for k, v in (fejlec or {}).items():
        m[k] = v
    m.set_content("sima szöveg")
    if html:
        m.add_alternative("<p>szia <a href='https://a.hu'>x</a></p>",
                          subtype="html")
    return m


def test_hirlevel_egy_hivatkozassal_html():
    m = _level(fejlec={"List-Unsubscribe": "<https://le.hu/x>"})
    assert MC.hirlevel_e(m)
    assert MC.okos_html_kell(m, 1) is True


def test_sok_hivatkozas_html():
    assert MC.okos_html_kell(_level(), MC.OKOS_LINK_KUSZOB) is True


def test_keves_hivatkozas_marad_egyszeru():
    assert MC.okos_html_kell(_level(), MC.OKOS_LINK_KUSZOB - 1) is False
    assert MC.okos_html_kell(_level(), 0) is False


def test_levelezolista_hozzaszolas_nem_hirlevel():
    m = _level(fejlec={"List-Unsubscribe": "<mailto:x@lev-lista.hu>",
                       "List-Post": "<mailto:superdl@lev-lista.hu>"})
    assert not MC.hirlevel_e(m)
    assert MC.okos_html_kell(m, 1) is False


def test_html_resz_nelkul_marad_szoveg():
    m = _level(html=False, fejlec={"List-Unsubscribe": "<https://le.hu/x>"})
    assert MC.okos_html_kell(m, 10) is False


def test_alapbol_bekapcsolva():
    assert MC._ALTALANOS_ALAP["okos_szuro"] is True


def _mailwin():
    return (GYOKER / "modules_src" / "mail" / "mail_mod"
            / "mailwin.py").read_text(encoding="utf-8")


def test_az_olvaso_ablak_hasznalja_es_menti():
    src = _mailwin()
    ast.parse(src)
    assert '_alt.get("okos_szuro", True)' in src
    assert "MC.okos_html_kell(msg, len(self._linkek))" in src
    assert '"okos_szuro": bool(self.alt_okos.GetValue())' in src
    # HTML nézetben a fókusz nem a rejtett szövegmezőre megy
    assert "self._html if self._html_nezet" in src
