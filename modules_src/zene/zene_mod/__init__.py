# -*- coding: utf-8 -*-
"""SuperDL modul – Zene: a lehető legegyszerűbb lejátszó.

Egy mappát adsz meg, minden alatta lévő szám bekerül egy listába, fel-le
nyíllal lépkedsz, és szól.

A menüpont a **Média** almenübe kerül, nem külön főmenübe: egy zenelejátszó
miatt nem kell új főmenüt nyitni, és a Média alatt pont ott a helye, a rádió
meg a többi mellett. (Ha a Core nem tud almenüt, marad a tartalék főmenü.)
"""

_state = {"items": []}


def register(core):
    from .zenewin import ZeneFrame

    opener = core.register_window("zene_module", ZeneFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Média", "&Zene") if _sub else core.add_menu("&Zene")
    item = core.add_menu_item(
        menu, "&Zenelejátszó\tCtrl+Shift+Z", opener,
        help="Egyszerű zenelejátszó: egy mappa minden száma egy listában, "
             "fel-le nyíllal lépkedve")
    _state["items"].append(item)
    core.log.info("zene modul betöltve")


def unregister(core):
    for item in _state.pop("items", []):
        core.remove_menu_item(item)
    _state["items"] = []
    core.log.info("zene modul leszerelve")
