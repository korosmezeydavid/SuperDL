# -*- coding: utf-8 -*-
"""Könyvek modul: egyetlen függvény se hivatkozzon nem létező globális névre.

Turai László jelzése (2026-09-29, konyvek 1.3.8): a hangoskönyv-lejátszóban a
Ctrl+T (mappa teljes hossza) mindig „A számolás nem sikerült" hibát mondott,
mert az audiobookwin.py a `media_duration`-t importálás nélkül hívta
(NameError a háttérszálban). Ez a teszt a symtable-lel minden függvény
implicit globális hivatkozását összeveti a modul szintjén definiált nevekkel.
"""
import ast
import builtins
import symtable
from pathlib import Path

GYOKER = Path(__file__).resolve().parent.parent
MOD = GYOKER / "modules_src" / "konyvek" / "konyvek_mod"


def _modul_nevek(fa: ast.Module) -> set:
    """Csak a modul szintjén (try/if blokkokkal együtt) keletkező nevek -
    függvények belsejébe nem nézünk, hogy egy helyi változó ne takarjon el
    egy hiányzó globálist."""
    nevek = set()
    sor = list(fa.body)
    while sor:
        n = sor.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            nevek.add(n.name)
            continue
        sor.extend(ast.iter_child_nodes(n))
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                nevek.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            nevek.add(n.id)
    for n in ast.walk(fa):                 # `global X` függvényben is definiál
        if isinstance(n, ast.Global):
            nevek.update(n.names)
    return nevek


def _hianyzo_nevek(ut: Path) -> list:
    forras = ut.read_text(encoding="utf-8")
    ismert = _modul_nevek(ast.parse(forras)) | set(dir(builtins)) | {
        "__file__", "__name__", "__doc__", "__package__", "__spec__",
        "__builtins__", "__class__"}
    hibak = []

    def bejar(tabla):
        if tabla.get_type() != "module":
            for s in tabla.get_symbols():
                if s.is_global() and s.is_referenced() \
                        and s.get_name() not in ismert:
                    hibak.append("%s: %s()" % (s.get_name(), tabla.get_name()))
        for gy in tabla.get_children():
            bejar(gy)

    bejar(symtable.symtable(forras, str(ut), "exec"))
    return hibak


def test_audiobookwin_media_duration_importalva():
    forras = (MOD / "audiobookwin.py").read_text(encoding="utf-8")
    assert "media_duration" in _modul_nevek(ast.parse(forras))


def test_konyvek_modul_nincs_nem_letezo_nev():
    hibak = {}
    for ut in sorted(MOD.glob("*.py")):
        h = _hianyzo_nevek(ut)
        if h:
            hibak[ut.name] = h
    assert not hibak, "Nem létező globális név: %r" % hibak
