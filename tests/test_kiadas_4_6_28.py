"""4.6.28 csomag: Józsi (érvényes újság megmarad), Laci (mappa hossza),
billentyű-ütközések a főmenüben, Modulkezelő Ctrl+Alt+K."""
import ast
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GYOKER / "modules_src" / "akciok"))

from akciok_mod import forrasok as F        # noqa: E402
from akciok_mod.termek import Termek         # noqa: E402

MA = dt.date(2026, 10, 1)                    # csütörtök: jött az új újság


def _t(nev, ar, erv):
    return Termek(bolt="Lidl", nev=nev, ar=ar, ervenyes=erv)


def test_megtartva_ervenyes_regi_marad():
    regi = [_t("Tej", 299, "09.28-tól 10.04-ig"),      # még érvényes
            _t("Vaj", 899, "09.24-tól 09.30-ig"),      # lejárt
            _t("Sajt", 1299, "a készlet erejéig"),     # nincs vége: nem
            _t("Kenyér", 499, "10.05-tól 10.11-ig")]   # az újban is benne
    uj = [_t("Kenyér", 499, "10.05-tól 10.11-ig"),
          _t("Alma", 399, "10.05-tól 10.11-ig")]
    e = F.megtartva(regi, uj, MA)
    nevek = [t.nev for t in e]
    assert nevek == ["Kenyér", "Alma", "Tej"]
    # ha a régi vasárnapja is elmúlt, a Tej is eltűnik
    e2 = F.megtartva(regi, uj, dt.date(2026, 10, 5))
    assert [t.nev for t in e2] == ["Kenyér", "Alma"]


def test_megtartva_ures_regi():
    uj = [_t("Alma", 399, "10.05-tól 10.11-ig")]
    assert F.megtartva([], uj, MA) == uj


def test_ora_perc():
    src = (GYOKER / "modules_src" / "konyvek" / "konyvek_mod"
           / "audiobookwin.py").read_text(encoding="utf-8")
    fa = ast.parse(src)
    fn = next(n for n in fa.body if isinstance(n, ast.FunctionDef)
              and n.name == "_ora_perc")
    ns = {}
    exec(compile(ast.Module([fn], []), "audiobookwin", "exec"), ns)
    ora_perc = ns["_ora_perc"]
    assert ora_perc(3725) == "1 óra 2 perc"
    assert ora_perc(90) == "1 perc 30 másodperc"
    assert ora_perc(5) == "5 másodperc"
    assert ora_perc(0) == "0 másodperc"
    assert ora_perc(26 * 3600 + 60) == "1 nap 2 óra 1 perc"


def test_fomenu_billentyuk_nem_utkoznek():
    """Főmenü-gyorsbillentyű csak egyszer szerepelhet (superdl_gui +
    modul-regisztrációk). A searchwin saját ablak, nem számít."""
    rx = re.compile(r'"[^"\n]*\\t(Ctrl\+[A-Za-z0-9+]+)"')
    files = [GYOKER / "superdl_gui.py"] + list(
        (GYOKER / "modules_src").glob("*/*/__init__.py"))
    hol = defaultdict(list)
    for f in files:
        for m in rx.finditer(f.read_text(encoding="utf-8", errors="replace")):
            hol[m.group(1)].append(f.name)
    utkozes = {k: v for k, v in hol.items() if len(v) > 1}
    assert not utkozes, utkozes
    assert "Ctrl+Alt+K" in hol                      # Modulkezelő
    for k in ("Ctrl+Alt+E", "Ctrl+Alt+V", "Ctrl+Alt+F", "Ctrl+Alt+P",
              "Ctrl+Alt+L", "Ctrl+Alt+B"):
        assert k in hol, k
