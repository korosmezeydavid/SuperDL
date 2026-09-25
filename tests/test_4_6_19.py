"""4.6.19 + modulkör (Turai László, 2026-09-24).

* F5-nél „kidobott" a Hangoskönyvből: az ffprobe konzolablakot nyitott, ami
  elvitte a fókuszt → minden külső program ablak nélkül induljon.
* Nagy könyvnél 20+ másodperces fagyás a sávlista töltésénél.
* A félmásodperces kijelző nem várhat az ffprobe-ra.
* Ctrl+I: hol tartunk.
"""
import ast
import importlib.util
import inspect
import sys
import threading
import time
import types
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]


def _modul(relut: str, nev: str):
    spec = importlib.util.spec_from_file_location(nev, GYOKER / relut)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nev] = mod
    spec.loader.exec_module(mod)
    return mod


AB = _modul("modules_src/konyvek/konyvek_mod/audiobook_player.py",
            "_ab_player_4619")
ABWIN_FORRAS = (GYOKER / "modules_src/konyvek/konyvek_mod/audiobookwin.py") \
    .read_text(encoding="utf-8")


# ---- nincs konzolablak ---------------------------------------------------

def _ablakos_hivasok():
    fajlok = [GYOKER / "superdl_gui.py"] + list((GYOKER / "superdl").rglob("*.py")) \
        + list((GYOKER / "modules_src").rglob("*.py"))
    rossz = []
    for f in fajlok:
        if "mail" in f.parts:                  # a mail modul nem a miénk
            continue
        fa = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(fa):
            if not isinstance(n, ast.Call):
                continue
            fn = n.func
            if not (isinstance(fn, ast.Attribute)
                    and getattr(fn.value, "id", "") == "subprocess"
                    and fn.attr in ("run", "Popen", "check_output", "call",
                                    "check_call")):
                continue
            kw = {k.arg for k in n.keywords}
            if kw & {"creationflags", "startupinfo", None}:
                continue
            # az Intéző megnyitása maga is ablak – az szándékos
            elso = n.args[0] if n.args else None
            if isinstance(elso, ast.List) and elso.elts and \
                    getattr(elso.elts[0], "value", "") == "explorer":
                continue
            rossz.append("%s:%d" % (f.relative_to(GYOKER), n.lineno))
    return rossz


def test_minden_kulso_program_ablak_nelkul_indul():
    assert _ablakos_hivasok() == []


# ---- a kijelző nem várhat ------------------------------------------------

def test_hossz_lekerdezes_nem_blokkolja_a_fo_szalat(monkeypatch):
    kesz = threading.Event()

    def lassu(_p):
        time.sleep(0.5)
        kesz.set()
        return 123.0

    monkeypatch.setattr(AB, "media_duration", lassu)
    p = AB.AudioBookPlayer()
    p.tracks = ["x.mp3"]
    t0 = time.monotonic()
    assert p.duration_nem_var() == 0.0
    assert p.duration_nem_var() == 0.0            # nem indít második szálat
    assert time.monotonic() - t0 < 0.2
    assert kesz.wait(3)
    time.sleep(0.05)
    assert p.duration_nem_var() == 123.0


def test_a_kijelzo_a_nem_varo_valtozatot_hasznalja():
    tick = ABWIN_FORRAS.split("def _tick", 1)[1].split("\n    def ", 1)[0]
    assert "duration_nem_var()" in tick
    assert "self.player.duration()" not in tick


# ---- sávlista egy lépésben -----------------------------------------------

def test_savlista_egyetlen_set_tel_toltodik():
    fill = ABWIN_FORRAS.split("def _fill_tracklist", 1)[1] \
        .split("\n    def ", 1)[0]
    assert ".Set(" in fill
    assert ".Append(" not in fill
    assert "Freeze()" in fill and "Thaw()" in fill


# ---- Ctrl+I: hol tartunk ------------------------------------------------

def _hol_fv():
    fa = ast.parse(ABWIN_FORRAS)
    osztaly = next(n for n in fa.body if isinstance(n, ast.ClassDef))
    fv = next(n for n in osztaly.body if isinstance(n, ast.FunctionDef)
              and n.name == "_hol_tartunk_szoveg")
    modul = ast.Module(body=[fv], type_ignores=[])
    ns = {"ido_str": AB.ido_str}
    exec(compile(modul, "hol", "exec"), ns)
    return ns["_hol_tartunk_szoveg"]


class _Lejatszo:
    def __init__(self, aktiv=True, szunet=False, poz=75.0, hossz=600.0):
        self.tracks = ["/k/01.mp3", "/k/02.mp3", "/k/03.mp3"]
        self.idx = 1
        self._aktiv, self._szunet, self._poz, self._hossz = \
            aktiv, szunet, poz, hossz

    def track_count(self):
        return len(self.tracks)

    def track_id(self, ut):
        return ut.rsplit("/", 1)[1]

    def is_active(self):
        return self._aktiv

    def is_paused(self):
        return self._szunet

    def position(self):
        return self._poz

    def duration_nem_var(self, _p=None):
        return self._hossz

    def track_index_of(self, s):
        return {"03.mp3": 2}.get(s)


def _en(lejatszo, resume=None, polc=None):
    return types.SimpleNamespace(
        player=lejatszo, _title="A kőszívű", _resume_at=resume,
        _bookkey="k" if polc else "",
        lib=types.SimpleNamespace(get=lambda k: polc))


def test_hol_tartunk_szol():
    s = _hol_fv()(_en(_Lejatszo()))
    assert s.startswith("Szól: A kőszívű. 2. sáv a 3-ből: 02.mp3.")
    assert "hátra" in s


def test_hol_tartunk_szunetel():
    assert _hol_fv()(_en(_Lejatszo(szunet=True))).startswith("Szünetel")


def test_hol_tartunk_leallitva_a_polcrol_olvassa_a_helyet():
    s = _hol_fv()(_en(_Lejatszo(aktiv=False),
                      polc={"track": "03.mp3", "ms": 90000}))
    assert s.startswith("Leállítva, innen folytatod: A kőszívű. 3. sáv a 3-ből")


def test_hol_tartunk_ures():
    le = _Lejatszo()
    le.tracks = []
    assert _hol_fv()(_en(le)) == "Nincs megnyitott hangoskönyv."


def test_ctrl_i_gomb_es_sugo():
    assert "(wx.ACCEL_CTRL, ord('I'), ids[\"hol\"])" in ABWIN_FORRAS
    assert "H&ol tartunk? (Ctrl+I)" in ABWIN_FORRAS
    assert "Ctrl+I: hol tartunk" in ABWIN_FORRAS
